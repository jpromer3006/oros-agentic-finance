#!/bin/zsh
#
# oros_watchdog.sh - the guarantee layer (JP, 2026-07-08).
#
# Runs at 10:20 and 17:50 ET on weekdays via launchd (com.oros.watchdog).
# Checks whether the cloud runner already delivered today's journal commit; if
# yes, exits silently. If the cloud is silent, runs the full OROS morning
# locally so the report reaches JP's inbox with NO human intervention, ever.
#
# 2026-09-18 correction to the offline rule
# -----------------------------------------
# The old logic stood down whenever `git fetch` failed: "the Mac is offline,
# the cloud probably delivered, and a local fallback couldn't email anyway."
# On 2026-09-18 that reasoning cost the day. The Mac woke without a network,
# the 9:35 run burned itself out on a dead resolver, the watchdog fetched at
# 10:27, saw the network still down, and stood down - so the ONE component
# whose whole job is to catch a failed morning opted out of catching it.
#
# "Offline" is a temporary state, not a verdict. Wait for the network first;
# only stand down if it never comes back, and say so loudly.

set -uo pipefail
PROJECT_DIR="${OROS_PROJECT_DIR:-/Users/jpromero/Ai-Agent Oros}"
CONDA_BASE="${OROS_CONDA_BASE:-/Users/jpromero/anaconda3}"
CONDA_ENV="dev2"

NET_WAIT="${OROS_WATCHDOG_NET_WAIT:-900}"   # seconds to wait for a resolver

cd "$PROJECT_DIR" || exit 1

# Single-instance lock shared with oros_cron.sh — see cron script header.
LOCKDIR="$PROJECT_DIR/.oros_run_lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  LOCK_PID=""
  [[ -f "$LOCKDIR/pid" ]] && LOCK_PID=$(cat "$LOCKDIR/pid" 2>/dev/null)
  echo "$(date '+%Y-%m-%d %H:%M:%S') watchdog: lock held (pid ${LOCK_PID:-unknown}); cron or another run is active. Exiting." \
    >> "${OROS_LOG_DIR:-data/journal}/watchdog_$(date +%Y-%m-%d).log"
  exit 0
fi
echo $$ > "$LOCKDIR/pid"
trap 'rm -rf "$LOCKDIR"' EXIT INT TERM

LOG="${OROS_LOG_DIR:-data/journal}/watchdog_$(date +%Y-%m-%d).log"

{
  echo "==== watchdog $(date '+%Y-%m-%d %H:%M:%S %Z') ===="
  TODAY=$(date +%Y-%m-%d)
  HOUR=$(date +%H)

  # Two patrols per trading day. The evening patrol must NOT be satisfied by
  # the morning's journal commit, so it only counts commits after 16:30.
  if [[ ${HOUR} -ge 16 ]]; then
    SINCE="${TODAY} 16:30:00"
    PATROL="close-wrap (16:50 cloud slot)"
  else
    SINCE="${TODAY} 00:00:00"
    PATROL="morning (9:05 cloud slot)"
  fi

  # Wait for a resolver before concluding anything. This is the same gate the
  # morning run uses, so the two agree on what "offline" means.
  if ! PYTHONPATH=. python3 -c "
import sys
from data.netcheck import wait_for_network, NetworkUnavailable
try:
    waited = wait_for_network(timeout=${NET_WAIT})
    print(f'network up after {waited:.0f}s')
except NetworkUnavailable as exc:
    print(f'network never came up: {exc}')
    sys.exit(1)
"; then
    echo "OFFLINE for ${NET_WAIT}s - standing down. This machine had no resolver"
    echo "for the whole window; neither a fetch nor an email would have worked."
    exit 0
  fi

  if ! git fetch origin main --quiet 2>/dev/null; then
    echo "network is up but git fetch still failed - treating the cloud as"
    echo "silent and running the local fallback rather than skipping the day."
  elif git log origin/main --grep="journal ${TODAY}" --since="${SINCE}" --oneline | grep -q journal; then
    echo "cloud already delivered the ${PATROL} run - nothing to do"
    exit 0
  fi

  echo "NO cloud journal for the ${PATROL} - running local fallback"
  if [[ -f "$CONDA_BASE/bin/activate" ]]; then
    source "$CONDA_BASE/bin/activate"
    conda activate "$CONDA_ENV" 2>/dev/null
  fi
  # scan cap comes from ml/oros_config.py — never restated in runner scripts
  # (the old hard-coded 800 here wrote 787-name breadth entries for a week)
  OROS_RUN_SOURCE=watchdog PYTHONPATH=. python3 scripts/oros_run.py --mandate auto
  wrc=$?
  echo "watchdog fallback finished: exit $wrc"
  case $wrc in
    3) echo "  (exit 3 = lost the network again mid-run; nothing journaled)" ;;
    4) echo "  (exit 4 = feed gave no fresh bars; nothing journaled, alert sent)" ;;
  esac
} >> "$LOG" 2>&1

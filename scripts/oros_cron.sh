#!/bin/bash
#
# oros_cron.sh — launchd/cron wrapper for the unattended OROS morning run.
#
# Activates the conda env, runs scripts/oros_run.py (propose-and-journal-only;
# it NEVER trades), and appends all output to a dated log in data/journal/.
# Invoked by ~/Library/LaunchAgents/com.oros.morningrun.plist.
#
# 2026-09-18: added a retry ladder. launchd fires the missed 9:35 calendar
# event the instant the Mac wakes, which on this machine is BEFORE the network
# is up. oros_run.py now waits for DNS itself and aborts with a distinct code
# rather than scanning stale bars; this wrapper gives it more than one chance
# so a wake at 09:42 with a network that returns at 10:05 still delivers.
#
#   exit 3 = no network inside the preflight window   -> retry
#   exit 4 = network up but no fresh market data      -> retry (feed throttle)
#   any other code                                    -> final

set -uo pipefail

PROJECT_DIR="${OROS_PROJECT_DIR:-/Users/jpromero/Ai-Agent Oros}"
CONDA_BASE="${OROS_CONDA_BASE:-/Users/jpromero/anaconda3}"
CONDA_ENV="dev2"

MAX_ATTEMPTS="${OROS_MAX_ATTEMPTS:-3}"
RETRY_SLEEP="${OROS_RETRY_SLEEP:-900}"     # 15 minutes between attempts

cd "$PROJECT_DIR" || { echo "ERROR: cannot cd to $PROJECT_DIR"; exit 1; }

# Single-instance lock shared with oros_watchdog.sh. Only one oros_run.py
# may execute at a time — on 2026-09-21 both scripts started within 60s of
# each other after the network came up, and yfinance failed with
# "getaddrinfo() thread failed to start" from the concurrent lookups.
LOCKDIR="$PROJECT_DIR/.oros_run_lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  LOCK_PID=""
  [[ -f "$LOCKDIR/pid" ]] && LOCK_PID=$(cat "$LOCKDIR/pid" 2>/dev/null)
  echo "OROS cron: lock held (pid ${LOCK_PID:-unknown}); another run is active. Exiting."
  exit 0
fi
echo $$ > "$LOCKDIR/pid"
trap 'rm -rf "$LOCKDIR"' EXIT INT TERM

LOG_DIR="${OROS_LOG_DIR:-$PROJECT_DIR/data/journal}"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/cron_$(date +%Y-%m-%d).log"

{
  echo "===================================================================="
  echo "OROS morning run start: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "===================================================================="

  # Activate conda env (mirrors Launch.command)
  if [[ -f "$CONDA_BASE/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$CONDA_BASE/bin/activate"
    conda activate "$CONDA_ENV" 2>/dev/null
  fi

  if [[ "${CONDA_DEFAULT_ENV:-}" != "$CONDA_ENV" ]]; then
    echo "WARN: conda env '$CONDA_ENV' not active (got '${CONDA_DEFAULT_ENV:-none}'); using python3 on PATH."
  fi

  rc=1
  for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "--- attempt $attempt of $MAX_ATTEMPTS at $(date '+%H:%M:%S %Z') ---"

    # Suppress the abort alert on every attempt but the last: one email per
    # failed DAY, not one per attempt.
    if [[ $attempt -lt $MAX_ATTEMPTS ]]; then SUPPRESS=1; else SUPPRESS=0; fi

    # scan cap comes from ml/oros_config.py — never restated in runner scripts
    OROS_RUN_SOURCE=cron OROS_SUPPRESS_ABORT_ALERT=$SUPPRESS \
      PYTHONPATH=. python3 scripts/oros_run.py --positions 12
    rc=$?

    if [[ $rc -ne 3 && $rc -ne 4 ]]; then
      break
    fi

    if [[ $attempt -lt $MAX_ATTEMPTS ]]; then
      case $rc in
        3) echo "no network (exit 3); sleeping ${RETRY_SLEEP}s before retry" ;;
        4) echo "no fresh market data (exit 4); sleeping ${RETRY_SLEEP}s before retry" ;;
      esac
      sleep "$RETRY_SLEEP"
    else
      echo "giving up after $MAX_ATTEMPTS attempts (last exit=$rc)."
      echo "Nothing was journaled. The alert email explains which gate failed."
    fi
  done

  echo "OROS morning run end: $(date '+%Y-%m-%d %H:%M:%S %Z') | exit=$rc"
  exit $rc
} >> "$LOG" 2>&1

# OROS engineering brief for Claude Code
Prepared 2026-10-14. Repo root: the folder containing `ml/`, `ui/`, `scripts/`, `data/`.

You are working on OROS, a fully autonomous paper trading research system. It
never places trades. It runs a scan, builds a portfolio, emails a morning
Daily Report and an evening Closing Bell, and publishes a narrated YouTube
video. This session has one theme: **one build, one truth, traceable end to
end.** Scan, report, video, local dashboard and the historical grade of every
report must all tell the same story.

Work the phases in order. Phases 0 and 1 are read only. Stop at each
CHECKPOINT and report before writing code.

## Ground rules

1. Read `docs/SYSTEM_MAP.md`, `docs/DEBUG_BRIEF.md` and
   `docs/CLAUDE_CODE_PROMPT_2026-09-17.md` first. They hold prior decisions
   and the reference patterns for failing loudly.
2. Never delete or overwrite anything under `data/journal/`. Read it freely.
   All new audit output goes to `evaluation/honesty_2026-10-14/`.
3. Ignore `_push_fix/`, `_cloud_fix_2026-09-21/` and
   `data/journal/_recovered_2026-09-15/`. They are copies; do not let grep
   hits from them drive a decision.
4. Do not `git push`, do not change `.github/workflows/`, and do not alter the
   launchd job. Nothing new reaches the cron until JP says so.
5. Every YouTube upload in this session is UNLISTED. Never public.
6. Do not weaken `_DISCLOSURE_SCRIPT` enforcement in `generate_video_brief`.
7. Every number you report must come with the file and field it came from,
   so JP can spot check it by hand. If you claim a few winners carry the
   book, name those exact positions with entry, exit and return.
8. Silent degradation is the house bug. Anything you add must raise or alert,
   never return `None` with a friendly note a caller swallows.

## Phase 0. Trace the three way mismatch (read only)

JP reports that the emailed report, the YouTube video, and the portfolio you
get by opening the app locally and running it did not match each other.

1. For one recent day (use Oct 13), find the exact artifact each surface
   read: `ml/daily_report.py`, `ml/daily_video.py`, `ml/evening_report.py`,
   the Portfolio tab in `ui/`, and `ml/scan_report.py`. Record path, mtime,
   and the config hash or `BotConfig` it carries.
2. Diff the three: holdings, adds and drops, Top Picks or "no setup",
   regime, P&L, throttle level.
3. Name the root cause. Check first whether it is the same family as the
   stale universe handoff bug (Trader tab served an old build), a local
   rebuild with different inputs, or a mandate mismatch (value vs
   swing_momentum vs others from `ml/strategy_registry.py`).

**CHECKPOINT 0:** report the diff table and root cause. Do not fix yet.

## Phase 1. One honesty pipeline: audit plus full history backtest (read only)

This is ONE investigation, not two tasks. The last 30 days is simply the most
recent slice of the full history. Build it as a single script,
`evaluation/honesty_audit.py`, that grades every report OROS ever published
against what the market actually did afterward, using the stop aware ruler.
It is not a new strategy simulation; it grades published calls.

For every journaled report day, per strategy (grade each strategy on its own
ruler, value as value, swing as swing, matched to whichever strategy
produced that report):

1. **Email vs scan honesty.** Diff what the email said (adds, drops, picks,
   "no setup", regime, P&L, throttle) against the scan artifact and journal
   of that day. Count mismatches by type.
2. **Outcome grade.** Each pick: triggered or not, outcome at horizon,
   stop hit or not. Each "no setup" day: what the closest near misses did.
3. **The +3% vs minus 3% tension.** The Oct 13 Daily claimed the live book
   +3.09% since 07/06 while that evening's Closing Bell reported throttle at
   QUARTER size with expectancy -3.03% over 1098 positions. Reconcile it.
   Report hit rate, average win, average loss, payoff ratio, and the top 10
   contributors by dollars. Say plainly whether a few winners mask most
   losers.
4. **Scoreboard bug regression.** Confirm `regrade_open` still walks the
   whole journal (the 2026-08-31 30 file window bug). List any position
   stuck at `outcome_exit == "open"` that should be mature. Report
   `sample_valid` and `mature_positions` before any expectancy number.
5. **Trend.** Is expectancy worsening or stabilizing over the last 30 days?
   Rolling 20 position expectancy is enough.
6. **Exit rule.** Check whether winners are still cut near +5.4% by horizon
   while losers run toward -9%, and whether reporting hides it.
7. **Churn.** Oct 6 to 13 showed ANET flipping 5 times and ADI, AIQ, LLY 4
   times. Quantify churn per day and per strategy across the full history.

Output: `evaluation/honesty_2026-10-14/report.md` (plain language, tables,
every number sourced) plus `positions.csv` and `report_diffs.csv` with the
raw rows.

**CHECKPOINT 1:** summarize findings in 10 lines max, with the raw numbers.
Wait for JP before Phase 2.

## Phase 2. One build, one artifact

Make the report, the video, and the local Portfolio tab all render from the
identical journaled scan and proposal for a given date and strategy. No
surface may rebuild independently. If the local app runs a fresh build, it
must label it clearly as a new build with its own timestamp and hash, never
present it as the published one. Add a test that loads one date and asserts
all three surfaces see the same holdings, picks and P&L.

## Phase 3. Video narration: facts locked, commentary separate

1. Remove all capstone race framing: Sports Desk standings language, the
   "day N of 18" countdown, frozen vs live vs SPY standings scene. The race
   ended 7/29.
2. Reframe OROS as a fully autonomous agent running with no human
   intervention.
3. **Facts locked to the report.** Every factual claim in narration
   (regime, P&L, adds, drops, picks or "no setup", throttle) must be read
   from the same artifact as the morning report. Add a check that fails the
   render if narration states a fact not present in the report.
4. **Commentary is Claude's own voice**, an interpretation on top of the
   locked facts, not a robot reading the report. Guardrails: no buy or sell
   advice, never contradicts the facts or the disclosure. Where it lives
   (its own segment vs woven in) is NOT decided. Prototype both options on
   the Oct 13 report, show JP the two scripts side by side, and let him pick.

## Phase 4. Dashboard: publish a report's video on demand

Extend the YouTube News tab (`ui/components/youtube_mode.py`). JP selects a
journaled report, sees its prebuilt narration script, and publishes that
video UNLISTED with no email. The backing path must really work, not a dead
button. Open questions to ask JP, not decide: edit the script before
publishing or publish as is; latest build only or any journaled day.

## Phase 5. Testing, answered as you go

At the end, print a block JP can paste into Terminal:

1. The command to run `evaluation/honesty_audit.py` and where its outputs land.
2. The command to render the Oct 13 video locally without publishing.
3. The command or click path to publish one UNLISTED test video from the
   dashboard.
4. The Phase 2 consistency test command.
5. Five raw numbers from Phase 1 JP should verify by hand, each with the
   file and field to open.

Educational research tool. Nothing here is financial advice.

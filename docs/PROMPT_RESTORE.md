# Prompt: restore scan, portfolio and YouTube

Paste the block below as the first message of a Claude Code session started from
the repo root. Background is in `docs/INCIDENT_2026-09-04.md`.

---

```
Read docs/INCIDENT_2026-09-04.md in full before doing anything.

CONTEXT
OROS has been producing nothing usable today. The scan, the portfolio, the daily
email, the audio brief and the YouTube video are all dead. I have traced it to a
single root cause: as of 2026-09-04 every yfinance download fails and the run
reports failed=0. The four prior sessions fetched 1200 or more symbols; today
fetched 0 of 1500 and the pipeline carried on as if nothing was wrong.

Your job is to get scan, portfolio and video producing again today, then install
the guard that stops this failing silently next time.

RULES
1. The stage engine, the gates, top_picks.py, entry_gates.py and the extension
   thresholds are OUT OF SCOPE. You will see "0 candidates passed all gates from
   400 scanned". That is a downstream symptom of stale data, not a calibration
   problem. Do NOT loosen a gate to make picks appear. If you believe a gate is
   genuinely wrong, tell me and stop; do not change it.
2. Verify with real output, never by reading code and concluding it should work.
   Every step below has a check. Run the check.
3. Stop and report at each STOP marker. Do not run ahead.
4. The conda env is dev2 and your shell is not interactive, so activate the way
   scripts/oros_cron.sh does: source /Users/jpromero/anaconda3/bin/activate then
   conda activate dev2. Confirm with python -c "import sys; print(sys.prefix)".

STEP 1  Confirm the root cause
Run:
  python -c "import yfinance as yf; print('yfinance', yf.__version__); d = yf.download('SPY', period='5d', progress=False); print('rows', len(d)); print(d.tail(2))"
Report the version and the row count. Zero rows or a NoneType traceback confirms
the diagnosis. If it returns real rows, the feed recovered on its own; say so and
skip to STEP 3.
STOP. Show me the output.

STEP 2  Repair the feed
  pip install --upgrade --force-reinstall yfinance curl_cffi
  rm -rf ~/.cache/py-yfinance
Then rerun the STEP 1 check. You need a non zero row count.
If the upgrade alone does not fix it, work the suspects in this order and tell me
which one it was: curl_cffi version mismatch, a stale requests_cache session, a
missing Yahoo crumb or cookie in the older client. Do not write a custom scraper
and do not switch data providers without asking me.
Also confirm the OperationalError('unable to open database file') is gone by
running a batch fetch of about 50 symbols.
STOP. Show me the working fetch.

STEP 3  Rerun the pipeline and prove all three outputs
  rm -f "data/journal/reports/oros_report_2026-09-04.sent"
  OROS_RUN_SOURCE=manual PYTHONPATH=. python scripts/oros_run.py --mandate auto
This takes roughly 450 seconds. Do not kill it early.
Then verify, and report each one as pass or fail with the evidence:
  a. The refresh line shows fetched in the 1200s, not 0.
  b. data/journal/portfolio_2026-09-04_*.json exists with a later timestamp than
     1357 and its holdings differ from the stale run.
  c. data/journal/reports/oros_report_2026-09-04.pdf was rewritten.
  d. The log contains an "email sent" line for the daily report. Today's failed
     run has none; that is the check that matters most to me.
  e. data/journal/reports/oros_brief_2026-09-04.mp3 exists.
If any of b through e fail, find out why from the log and tell me before fixing.
STOP. Report the five checks.

STEP 4  Void the stale book
portfolio_2026-09-04_1357.json was built on 100% stale bars and must never be
graded. Propose how to mark it void so the scoreboard, regrade_open and the
capstone chain all skip it, WITHOUT deleting it from the journal. Show me the
approach before you apply it.
STOP.

STEP 5  ffmpeg and the video
  which ffmpeg || brew install ffmpeg
  launchctl getenv PATH
The evening path logs "Closing Bell: skipped (no ffmpeg)" even though commit
468f287 added discovery for launchd, so the watchdog environment is not seeing
it. Set an absolute FFMPEG_BINARY in .env rather than relying on discovery, and
make the code read it.
Then render today's video end to end and tell me the output path and duration.
A missing ffmpeg must raise an alert, not log a skip. Change that.
STOP.

STEP 6  YouTube publish
Confirm the YT_REFRESH_TOKEN in .env still authorises. A stale token returns 400
from Google and has bitten this project before. If it is stale, tell me and I
will reauthorise with scripts/yt_authorize.py; do not attempt to reauthorise
yourself, it needs a browser.
Once it authorises, publish today's video and give me the URL.
STOP.

STEP 7  The guard, so this is never silent again
Scope: data/price_cache.py and scripts/oros_run.py only.
  1. In refresh_prices, a symbol whose download raised counts in rep.failed EVEN
     WHEN a stale cache is reused. Keep serving the stale data; stop calling it
     success.
  2. DataQualityReport gains stale_age_days per symbol and a degraded list.
  3. A configurable minimum fetched fraction, default 0.5. Below it,
     refresh_prices raises DataFeedError naming the fetched count and the worst
     stale age.
  4. oros_run.py catches DataFeedError, sends the loud alert email via
     ml.notifier.send_email with the counts in the body, and exits non zero. It
     journals NOTHING on that path: no proposal, no breadth, no warehouse row.
  5. A test that fakes a total download failure and asserts the run refuses to
     journal and exits non zero.
  6. Pin yfinance in requirements.txt with an upper bound as well as a lower one.
     An open >= is how a silent client change took the feed down.
Show me the diff before applying.
STOP.

COMMITS
One commit per step that changes files, each leaving the repo runnable. End
every commit message with the co-author trailer this repo already uses.

At the end, give me a short summary: what the root cause actually was, which of
the three outputs are confirmed working with evidence, and anything still broken.
```

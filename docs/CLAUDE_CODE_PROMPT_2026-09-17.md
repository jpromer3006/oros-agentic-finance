# OROS engineering brief for Claude Code
Prepared 2026-09-17. Repo root: the folder containing `ml/`, `ui/`, `scripts/`, `data/`.

You are working on OROS, a paper trading research system. It never places
trades. Two things are broken and one thing is unsafe. Work them in the order
below. Do not refactor anything outside the scope described here.

## Ground rules

1. There is an OPEN git merge in this repo with roughly 31 files in UU state,
   and a staged, deliberately unapplied recovery set at
   `data/journal/_recovered_2026-09-15/`. Do not complete, abort, reset or
   stash that merge. Do not touch anything under `data/journal/` except to
   read it. If a change you want to make requires resolving the merge, stop
   and say so instead.
2. Never delete or overwrite a file under `data/journal/`. Journals are the
   only track record this project has, and six weeks of it were already
   destroyed once by a bare `except: pass` on a read path (see
   `ml/picks_ledger.py` and `ml/capstone_tracker.py`, both now patched with
   quarantine plus raise and a shrink guard). Those two patches are the
   reference pattern for everything you write here.
3. `_push_fix/` is a duplicate copy of part of the tree. Ignore it. Do not
   edit it and do not let grep results from it drive a decision.
4. Every fix must fail loudly. Silent degradation is the root cause of all
   three problems below. A step that cannot do its job must raise or must
   emit an alert, never return `None` with a friendly note that the caller
   swallows.

## Problem 1. The morning video has not published in over a month

### Evidence

* Last video ever produced: `data/journal/reports/oros_brief_2026-08-07.mp4`.
* From `oros_brief_2026-08-27.mp3` onward, every brief is audio only:
  Aug 27, 31, Sep 1, 2, 3, 4, 7, 8, 10, 11, 15, 16.
* Sep 17 produced no brief at all, only a PDF report.
* Yesterday the cloud run emailed "OROS ALERT: daily run FAILED", Actions run
  id 35123214125.

### Mechanism already traced, verify before changing

* `ml/daily_video.py` around lines 1275 and 1733:
  `if not shutil.which("ffmpeg"): return None, "Video brief: skipped (no ffmpeg in this environment)."`
* `ml/daily_report.py` around lines 1131 to 1150: when `generate_video_brief`
  returns `None`, the code quietly calls `generate_broadcast` and takes the
  MP3 instead. Then the YouTube publish block is gated on
  `str(audio_path).endswith(".mp4")`. An MP3 therefore means no upload at
  all, and nobody is told.
* `ml/daily_video.py` lines 47 to 60 already extend `PATH` for GUI launched
  and launchd processes with Homebrew and conda locations. `/usr/bin` is not
  in that list.
* `.github/workflows/oros_daily.yml` line 76 installs ffmpeg with apt, and
  line 116 runs `scripts/oros_run.py`. So the cloud path should have ffmpeg,
  which suggests the MP3 days came from the local watchdog or Launch.command
  path while the cloud runs failed for a different reason.

### What to do

1. Determine empirically which execution path produced each brief since
   Aug 7. `ml/oros_config.py`, `scripts/oros_run.py`, `ui/components/cron_control.py`
   and `ui/components/trader_mode.py` all reference `OROS_RUN_SOURCE`. If the
   briefs do not record their run source, add that to the brief metadata
   going forward, and reconstruct the history from whatever timestamps,
   `.meta.json` files and logs do exist. Report what you find before you fix.
2. Read the Actions log for run 35123214125 if it is reachable, and the
   surrounding failed runs. Report the actual traceback. Do not assume it is
   ffmpeg. The cloud installs ffmpeg explicitly, so a cloud failure is
   probably something else, possibly credentials, quota or a data step.
3. Replace ffmpeg discovery with a single resolver used by every call site.
   It must check `shutil.which`, then an explicit list of absolute paths that
   includes `/usr/bin/ffmpeg`, `/opt/homebrew/bin/ffmpeg`, `/usr/local/bin/ffmpeg`
   and the conda env paths already listed at lines 47 to 60, and finally an
   `OROS_FFMPEG` environment variable override. Same for `ffprobe`. Log the
   resolved absolute path at INFO on every run so this is never a mystery
   again.
4. Make the missing ffmpeg case loud. `generate_video_brief` should raise a
   named exception, for example `VideoToolingMissing`, carrying the paths it
   searched. The MP3 fallback in `daily_report.py` may still run so JP gets
   something, but the run must then send the failure alert email with the
   reason, and the daily summary must say in plain words that the video did
   not render and why. A day with no video must never look like a normal day.
5. Add a preflight to `scripts/oros_run.py` that runs before any expensive
   work: resolve ffmpeg and ffprobe, check the TTS credential the video path
   needs, check the YouTube credentials that `ml/publish_youtube.py` requires
   (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, refresh token), and check write
   access to `data/journal/reports/`. Print a one screen readiness table. If
   the mandate is the morning run and the video path is not ready, alert
   immediately rather than discovering it forty minutes later.
6. Add `scripts/oros_doctor.py`, runnable by hand, that performs the same
   preflight plus a real end to end smoke test: render a five second video
   from fixed sample data, confirm the MP4 exists and is non zero, confirm
   ffprobe can read it, and confirm the YouTube publisher would accept it,
   using a dry run flag so nothing is actually uploaded. JP needs a single
   command that answers "is the morning video going to work tomorrow".
7. Do not upload anything to YouTube while testing. Use the dry run path.

## Problem 2. The tabs disagree because nothing reads the scan

This is the issue JP raised directly. He is right, and it is worse than he
thought.

### Evidence

* `scripts/oros_run.py` line 149 to 159 is correct in intent. It builds the
  scan once with `build_scan(ranked, cap=args.cap)`, saves it with
  `save_scan(scan)`, and derives `symbols` from `scan.rows`. The comment at
  line 139 says this explicitly: one scan, one grade.
* `ml/scan_report.py` line 254 `save_scan` writes both a dated file under
  `data/journal/scans/` and the pointer `data/journal/scan_latest.json`.
* `ml/scan_report.py` line 265 defines `load_latest()`. **It has zero callers
  anywhere in the repo.** Verify this yourself with grep before you act on
  it. The single source of truth is written every day and read by nothing.
* `ui/components/portfolio_mode.py` line 101 `_candidate_symbols` builds its
  own universe from `_SP100` plus `_SECTOR_LEADERS` plus `load_liquid_ranking()`
  plus `price_cache.cached_symbols()` plus `get_universe(filtered=False)`.
  It never opens the scan. Line 424 feeds that list straight to
  `build_portfolio`.
* `ui/components/multi_strategy_mode.py` line 157 calls the same
  `_candidate_symbols`, and line 179 calls `build_portfolio` with it.
* `ui/components/trader_mode.py` around line 2019 computes its own
  `latest_scan` locally.
* `scripts/oros_run.py` lines 208 to 216 already know this is a hazard. The
  invariant "the book must be a SUBSET of the scan" is checked, but a break
  only produces `log.warning("UNIVERSE BREAK: ...")` and the run continues.

So the morning run is internally consistent, and every tab in the app is a
second, independent, differently ordered walk over a different universe.
Tickers appear in the Portfolio tab that were never graded in the scan, and
the ordering differs because the liquidity ranking and the price cache drift
between the scan and the moment the tab renders.

### What to do

1. Make the saved scan the only source of the tradable universe. Add a small
   accessor module, or extend `ml/scan_report.py`, exposing something like
   `current_scan()` that loads `scan_latest.json`, validates it, and returns
   the rows plus `session_date`, `scan_hash`, `as_of`, `confirmed` and the
   skipped and substituted lists.
2. Rewrite `_candidate_symbols` in `ui/components/portfolio_mode.py` so that
   the dynamic source `_DYNAMIC_SOURCE`, labeled "Open Market, the full OROS
   Scan universe", returns exactly the scan's confirmed tickers in the scan's
   own order. It must not top up from the price cache or the raw universe.
   If the scan is missing or stale, show the user a clear message naming the
   scan date and offer to run the scan, rather than silently substituting a
   different universe. Saved watchlists and pins are a separate code path and
   may stay as they are, but a pin that is outside the current scan must be
   labeled in the UI as ungraded.
3. Apply the same change to `ui/components/multi_strategy_mode.py`.
4. Point `ui/components/trader_mode.py` at the same accessor instead of its
   local `latest_scan` computation.
5. Promote the UNIVERSE BREAK warning in `scripts/oros_run.py` to a hard
   failure. If `build_portfolio` returns a holding whose ticker is not in the
   scan set, the run must abort and alert. A book containing a name the
   scanner never graded is not a result, it is a bug, and it has been
   shipping quietly.
6. Stamp provenance on every artifact. The portfolio journal entry, the PDF
   report, the brief metadata and the UI footer of each tab must all carry
   the same `scan_hash`, `session_date` and scan `as_of`. Then add a check,
   in `scripts/oros_doctor.py`, that reads the day's artifacts and asserts
   all four carry the same hash. That is the mechanical version of what JP
   asked for: if the tabs disagree, the check fails instead of a human
   noticing months later.
7. Note on SEC. `ml/portfolio_engine.py` line 458 calls `fetch_sec_cik_map()`
   inside `build_portfolio`. Read it first: `data/universe.py` line 238. It
   is a TTL cached lookup used only to attach a CIK and resolve a sector for
   names that are already candidates. It does not add tickers. Confirm that
   for yourself, then leave it alone. The cross tab divergence is the
   `_candidate_symbols` path, not the SEC call. Do not spend effort here.
8. There are two saved scans on several days, for example
   `scan_2026-09-16_133829.json` and `scan_2026-09-16_142104.json`. Determine
   whether the morning and a later run both write `scan_latest.json`, which
   would mean a tab opened in the morning and a tab opened in the afternoon
   are reading different scans on the same day. If so, decide with an
   explicit rule which run owns the pointer, write that rule down in the
   module docstring, and enforce it.

## Problem 3. Audit the remaining silent failure paths

The journal loss, the vanished video and the diverging tabs are the same bug
three times: an exception or a missing precondition handled by returning a
neutral value that the caller cannot distinguish from success.

Sweep the repo for this pattern and produce a report before changing
anything. Look for `except Exception` with `pass` or a bare `return None`,
`except: continue`, `.get(...)` defaults standing in for required data, and
any `return None, "<some note>"` pair where the caller ignores the note.
Prioritise anything on a write path, anything that touches `data/journal/`,
and anything in the daily run chain: `scripts/oros_run.py`,
`ml/daily_report.py`, `ml/daily_video.py`, `ml/daily_broadcast.py`,
`ml/portfolio_journal.py`, `ml/breadth.py`, `ml/scan_report.py`,
`ml/publish_youtube.py`, `ml/notifier.py`.

Rank the findings by blast radius. Fix only the top ones in this pass, using
the quarantine plus raise pattern from `ml/picks_ledger.py`, and list the
rest for JP to prioritise.

## Tests

Add tests under `tests/` for each fix:

* ffmpeg resolver finds a binary at each candidate location, and raises the
  named exception with the searched paths when none exists.
* `daily_report` sends the alert and marks the day degraded when the video
  raises, rather than reporting a normal run.
* `current_scan()` raises or returns a clearly flagged stale result when
  `scan_latest.json` is missing, unreadable or older than the current session
  date.
* `_candidate_symbols` under the dynamic source returns exactly the scan's
  tickers, with a test that fails if any ticker outside the scan appears.
* The UNIVERSE BREAK abort fires when a holding is outside the scan set.
* Provenance: the artifacts of one simulated run all carry one scan hash.

## Deliverables

1. A findings report first, before any edit, covering: which execution path
   produced each brief since Aug 7, the real traceback from the failed cloud
   runs, confirmation that `load_latest()` has no callers, and the ranked
   silent failure list.
2. Then the fixes, in the order above, each as its own commit with a message
   that names the failure it prevents.
3. `scripts/oros_doctor.py` and the output of one clean run of it.
4. A short note listing anything you found that you did not fix and why.

Ask before doing any of the following: resolving or altering the open merge,
applying the recovery set, uploading to YouTube, sending any email, or
changing anything under `data/journal/`.

# OROS DEBUG BRIEF

Companion to `docs/SYSTEM_MAP.md`. Written 2026-09-04 against commit 8f0773b.
Read the map first. This file is the work queue.

Every defect below carries the evidence that established it, so no session has
to rediscover the symptom. Do not start a fix without reproducing the evidence
line first.

---

## Order of work

The order matters and is not by severity alone. Instrumentation comes before
tuning, because tuning a funnel you cannot see is guessing. Contract comes
before code, because two engineers optimising different definitions of the
same line will each be locally right.

```
Phase 0   D4 D12   make the trend spec and the gates parameters   (definition)
Phase 1   D5 D11   instrument the funnel, label calls with spec   (visibility)
Phase 2   D2 D3 D7 D8   data honesty                              (trust)
Phase 3   D6        set the shipped extension policy              (calibration)
Phase 4   D10       backfill the warehouse, then fit Track B      (evidence)
Phase 5   D1        cloud parity                                  (launch blocker)
Phase 6   D9        ffmpeg and publishing                         (distribution)
```

---

## D4  The trend spec is a constant, and three of them exist  [launch blocker]

**Symptom.** Two separate problems wearing one coat. The moving average window
cannot be chosen by a customer, and the one hard coded window is implemented
three different ways.

**Evidence.**

* `ml/stage_analyzer.py:53` `MA_WINDOW_DAYS = 150`, module level. No caller can
  override it.
* `close.rolling(150).mean()` on daily closes decides the stage.
* `ml/daily_report.py:859` `_weekly(df)["Close"].rolling(30).mean()` draws a
  true weekly 30 bar mean in the published chart.
* `close.iloc[-6]` and `ma.iloc[-6]` stand in for a weekly bar in the
  hysteresis check.
* `ml/strategy_registry.py:143` holds the only 50 and 200 day lines.

**Contract.** See `docs/SYSTEM_MAP.md` section 4.1. The trend spec is a per bot
parameter with shipped presets (Weinstein weekly 30, Minervini daily 150, long
trend daily 200, custom). The invariant survives the parameterisation: within
one run, one resolved spec governs the scan, the stop, the invalidation and
every chart drawn for that run.

**Acceptance.**
1. `TrendSpec` exists, is passed into `analyze_stage`, and has no module level
   fallback that silently applies when a caller forgets to pass one. A missing
   spec raises.
2. One function resolves the spec to a series. Scanner, stop, PDF chart and
   video chart all call it. Grep proves there is no second computation.
3. Confirmation and hysteresis compare completed bars at the spec's resolution.
   `iloc[-6]` is gone.
4. The daily 50 / 150 / 200 stack is exposed on `StageResult` as context and is
   never consulted for a stage decision.
5. Defaults reproduce today's output exactly for the Weinstein preset in daily
   mode, proven by a fixture test, so the refactor is separable from the
   behaviour change in step 6.
6. Switching the Weinstein preset to true weekly WILL move stage calls. Journal
   before and after counts across the last 60 sessions. Do not absorb the shift.

---

## D5  The pick funnel is unobservable  [high]

**Symptom.** `top picks: 0 candidates passed all gates from 400 scanned`. No
information about where the 400 died.

**Evidence.** `ml/top_picks.py:99-132`. Ten sequential `continue` statements,
none of them counted.

**Acceptance.**
1. A `FunnelReport` counts rejections per gate and per reason.
2. It is written to `data/journal/funnel_YYYY-MM-DD.json` on every scan.
3. The log line becomes a histogram, not a single zero.
4. For the ten names closest to passing, record the failing gate and the
   margin by which they missed. A near miss list is the diagnostic.
5. No behaviour change. This commit must not alter a single pick.

---

## D2  Failed downloads reported as success  [launch blocker]

**Symptom.** `price refresh: requested=1500 fetched=1293 stale_reused=207
empty=0 failed=0` in the same log that shows over 200 download errors.

**Evidence.** `data/journal/watchdog_2026-09-03.log`. `data/price_cache.py:158`
only appends to `rep.failed` when there is no cache at all to fall back on.
A symbol with a stale parquet counts as `from_stale` and the run reports
`failed=0`.

**Why it matters commercially.** Roughly 14% of the scanned universe was
staged on old bars on 2026-09-03 and nothing said so. A paid stage call on a
stale bar is a refund and a reputation problem.

**Acceptance.**
1. `DataQualityReport` gains `stale_age_days` per symbol and a `degraded` list.
2. A symbol served from cache older than a threshold is excluded from the
   scan, not silently graded.
3. The run fails loudly, with an alert email, when degraded exceeds a
   configured fraction of the universe.
4. Every StageResult carries the as of date of the bars it used, and the PDF
   prints it.

---

## D3  yfinance sqlite cache under threads  [high]

**Symptom.** `OperationalError('unable to open database file')` on tens of
symbols per batch, plus `TypeError("'NoneType' object is not subscriptable")`.

**Evidence.** Same log, multiple batches. `data/price_cache.py:150-151` passes
`threads=True` to `yf.download`.

**Likely cause.** yfinance's timezone cache is a single sqlite file and is not
safe under the thread pool, especially on a runner with a read only or absent
cache directory. The `NoneType` error is the same failure surfacing later in
the batch normaliser.

**Acceptance.**
1. Set an explicit writable yfinance cache location at process start.
2. Serialise or bound the thread pool, and retry a failed symbol individually
   before declaring it failed.
3. A batch may not report success while any symbol inside it raised.
4. Reproduce on both the Mac and an Ubuntu runner before closing.

---

## D7  Breadth journal accepts a two name scan  [medium]

**Symptom.** `data/journal/stage_breadth.json` contains an entry for
2026-09-04 with `"total": 2, "Advancing": 2`, source `scan-now`.

**Impact.** The video narrates breadth off this series. A two name scan
recorded as a day makes the season chart wrong and the narration false.

**Acceptance.**
1. `ml/breadth.record_breadth` refuses to write an entry below a minimum
   graded count, roughly 80% of the configured cap.
2. A refusal logs at warning level with the count and the source.
3. The 2026-09-04 entry is removed, with the removal noted in the commit.
4. Same guard applied to `stage_breadth_close.json`.

---

## D8  Uniformity rule silently disabled  [medium]

**Symptom.** The `changes` diff is not being written into the journaled
proposal, so report, digest, and broadcast each recompute it independently.
This is exactly the failure the uniformity rule was created to prevent.

**Evidence.** `scripts/oros_run.py:233` and `:235` reference `props`. `grep -n
"props" scripts/oros_run.py` returns only lines 204, 233, 235. There is no
assignment. `props = list_proposals()` was removed in the 2026-08-31 refactor
that replaced the windowed regrade with `regrade_open()`, and the orphaned
lines were left behind. The NameError is swallowed by `except Exception: pass`.

**Acceptance.**
1. The proposal path is captured from `record_proposal` and used directly.
   Do not reintroduce `list_proposals()` for this.
2. The bare `except Exception: pass` is replaced with a logged handler. A
   swallowed exception is how this hid for five weeks.
3. A test asserts the journaled proposal contains a `changes` key.
4. Audit the file for other bare passes around journal writes.

---

## D6  Zero picks against 216 Stage 2 names  [high, gated on D5]

**Symptom.** `picks_ledger.json`: one pick on 2026-08-27 (NDSN), then empty on
08-31, 09-01, 09-02, 09-03. Breadth on 09-03 shows 216 Advancing of 495.

**Hypothesis to test, not to assume.** The joint probability of the funnel is
near zero by construction in a tape that has been advancing:

* Extension marks a Stage 2 name `extended` at 20% above the MA when volume is
  under 1.5x, and 20% is an ordinary distance for a name that has been in
  Stage 2 for a quarter.
* `volume_surge` is a 5 day mean over the prior 50 day mean, deliberately
  centred near 1.0, so 1.5x is roughly a one in ten to one in twenty event.
* `mansfield_rs_rising` removes another slice.
* `setup_type == "watching"` still requires not extended, so extension is a
  hard wall rather than a soft penalty.

**Do not tune before D5 lands.** With the funnel report in hand:

1. Confirm which gate is the binding constraint on a normal day.
2. Ask whether the constraint is Weinstein or an artefact. Weinstein does say
   a stock far above the line has less reward left. He does not say a system
   should return nothing for a week while a quarter of the market advances.
3. If extension is binding, ship `extension_policy: penalise` as the default
   (see D12): rank the name down rather than dropping it, so the product
   always returns a ranked list with an honest quality grade attached,
   including "nothing clears the bar today, here are the three closest and
   why they miss". Leave `exclude` available for a customer who wants it.
4. Whatever changes, journal the before and after pick counts across a
   backfill of the last 60 sessions. A calibration change with no measured
   effect on history is not a decision, it is a preference.

**Commercial note.** A subscription product that emails "no setup today" four
days running is indistinguishable from a broken one to a paying subscriber.
The honest near miss list is the fix for that, whether or not the gates move.

---

## D1  Cloud run dead, product depends on one laptop  [launch blocker]

**Symptom.** Two `OROS ALERT: daily run FAILED` emails on 2026-09-03, and the
watchdog log for both slots reads `NO cloud journal for the ... slot running
local fallback`.

**Evidence.** `git log` shows the last `OROS daily run: journal` commit on
2026-08-07. Every daily artifact since was produced on the MacBook.

**Diagnosis path.**
1. Read the Actions logs for runs 33777549861 and 33814830572 directly. Do not
   guess. Suspects in order: the 55 minute timeout against a 1500 name refresh
   on a cold cache, the pip install of the full requirements file, and the
   yfinance cache errors from D3, which are worse on a runner with no writable
   cache directory.
2. The cache restore key is `oros-price-cache-${{ github.run_id }}`, which
   never hits on the first attempt and relies entirely on `restore-keys`.
   Confirm whether the cache is actually restoring.

**Acceptance.**
1. Five consecutive green cloud runs with a journal commit on each.
2. The watchdog reports "cloud journal present" and does not run a fallback.
3. Runtime measured and kept under half the timeout.
4. Until this passes, the subscription launch does not have an uptime story.
   State that plainly rather than shipping on a laptop.

---

## D9  No video since 2026-08-31  [medium]

**Symptom.** `Closing Bell: skipped (no ffmpeg).` in the 2026-09-03 watchdog
log. The channel's last upload is 2026-08-31.

**Evidence.** Commit 468f287 added ffmpeg discovery for launchd runs, yet the
watchdog path still reports it missing, so the discovery does not cover the
watchdog's environment.

**Acceptance.**
1. ffmpeg resolves under `oros_cron.sh`, `oros_watchdog.sh`, and Actions.
2. A missing ffmpeg raises an alert rather than logging a skip. A skipped
   video is a missing product, not a nice to have.
3. Confirm the `YT_REFRESH_TOKEN` secret is current before declaring publish
   fixed. A stale token was a known failure and reproduces as a 400 from
   Google.

---

## D12  Gate thresholds are module constants  [launch blocker]

**Symptom.** No customer can configure a bot, because every threshold that
defines a bot lives in module scope.

**Evidence.** `ml/stage_analyzer.py` lines 57 to 116: `STAGE1_MAX_SLOPE_PCT`,
`STAGE2_MIN_PRICE_ABOVE_MA`, `WEINSTEIN_MIN_VOLUME_SURGE`,
`WEINSTEIN_MIN_MANSFIELD_RS`, and the four `EXTENDED_*` thresholds. All fixed
at import.

**Acceptance.**
1. `GateSpec` carries every one of them, with defaults equal to today's values.
2. `BotConfig` (trend, strategies, gates, risk, universe, execution)
   serialises, validates, and hashes.
3. The resolved config and its hash are written into every journaled proposal.
   A pick without the config that produced it is unreproducible.
4. `GateSpec.extension_policy` accepts `exclude` or `penalise`. See D6.
5. A test proves output is byte identical at defaults. This commit changes
   nothing about what the system picks.

---

## D11  Stage labels do not carry their spec  [high]

**Symptom.** `Stage 2` means something different under a 30 week weekly spec
than under a 200 day daily one, and nothing in the output says which was used.

**Why it matters.** Once bots are configurable, two customers can hold
contradictory calls on the same ticker on the same day and both be correct.
Without the spec on the label, that reads as a broken product. It is also the
line between describing Weinstein's method and misrepresenting it.

**Acceptance.**
1. Every stage label rendered anywhere carries its spec: `Stage 2 (30w)`,
   `Stage 2 (200d)`.
2. `StageResult` carries the resolved spec, and the journal row stores it.
3. The PDF, the video, the UI and any API response all read that field. None
   of them reconstruct the label from a hard coded string.

---

## D10  Warehouse too shallow to fit or evaluate the ML track  [launch blocker for Track B]

**Symptom.** The ML track cannot be sold as evidence, because there is not
enough evidence.

**Evidence.** `warehouse: {'rows': 10740, 'dates': 19, 'tickers': 643,
'labeled': 7109}` from the 2026-09-03 run. Label horizon is 20 days
(`ml/data_collector.label_warehouse`).

**Diagnosis.** Nineteen dates is a wide cross section and almost no time
series. A walk forward split over 19 dates leaves a handful of test dates, and
an IC t statistic computed on those is noise. The architecture in
`ml/meta_features.py` is right; the corpus is not there yet.

**The fix is a backfill, not a wait.** Price derived features are all
reconstructible from the cached daily bars, which reach back roughly two years.
Rebuilding snapshots at weekly intervals over that window turns 19 dates into
roughly 100, and daily intervals into roughly 500.

**Acceptance.**
1. A backfill script reconstructs point in time snapshots from the price cache
   at a stated interval, using only data available as of each snapshot date.
2. Fundamental features (value, growth) are marked unavailable for backfilled
   dates rather than filled with today's values. Filling them is lookahead and
   would invalidate the whole corpus.
3. Survivorship bias is stated explicitly in the output, since the universe is
   built from current listings. This caveat does not go away and must not be
   quietly dropped.
4. Track B ships only once mean IC, its t statistic, and the top minus bottom
   spread are computed out of sample on the backfilled corpus and printed
   wherever the track is offered.
5. If the numbers are weak, the honest move is to show them, not to hide the
   track behind a blend.

---

## Opening prompt for Claude Code

Paste this as the first message in a session started from the repo root.

```
Read docs/SYSTEM_MAP.md and docs/DEBUG_BRIEF.md in full before doing anything.

You are working on OROS, an agentic market analysis system being rebuilt as a
multi tenant product: customers configure their own bot, choose their own trend
definition (30 week weekly, 200 day daily, and others), and see two separate
pick tracks — explainable rule agents and an independent ML model. Accuracy
outranks speed. The system proposes and journals only today; live execution is
a later, separately gated phase.

Work Phase 0 first, which is D4 and D12 together, and stop when it is done.
They are one refactor: every constant that defines a bot's behaviour becomes a
field on a config object, and the trend window is the most important of them.

Before you write code:
1. List every module level constant in ml/stage_analyzer.py that affects a
   stage call or a gate, with line numbers.
2. Trace every place a moving average is computed or drawn anywhere in the
   repo, with file and line, and say which become callers of one resolver.
3. Propose the TrendSpec, GateSpec and BotConfig shapes as dataclasses.
4. Tell me how you will prove the refactor changes no output at defaults.

Do not implement until I approve the design.
```
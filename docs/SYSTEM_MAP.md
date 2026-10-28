# OROS SYSTEM MAP

Ground truth for the OROS agentic finance system. Written 2026-09-04 from a
read of the working tree at commit 8f0773b.

This document is the contract. When code and this document disagree, one of
them is wrong and the disagreement is a bug to be filed, not a difference to
be tolerated. Claude Code should read this file before changing anything in
`ml/`, `data/`, or `scripts/`.

Status markers used throughout:

* `CURRENT` describes what the code does today.
* `TARGET` describes the agreed contract the code must move to.
* `BROKEN` marks a divergence with an open defect in `docs/DEBUG_BRIEF.md`.

---

## 0. Invariants

These hold everywhere and are not negotiable by any layer.

1. OROS proposes and journals. It never places an order and never moves money.
2. Every claim that reaches a subscriber must be reproducible from a journaled
   artifact. If the video says "216 Advancing", a file must say 216.
3. The book is a subset of the scan. A holding that was not in the scanned
   universe is a universe break and must be announced at write time.
4. A silent failure is worse than a loud one. Missing output must never look
   like a quiet day.
5. One number is computed once. The morning diff, the breadth counts, and the
   day tally each have exactly one writer and many readers.

---

## 1. Entry points and schedule

Five things can start a run. They are not equivalent and they are the main
source of confusion.

| Entry point | Trigger | Host | Writes |
|---|---|---|---|
| `.github/workflows/oros_daily.yml` | cron `0 12 * * 1-5` and `50 20 * * 1-5` UTC | GitHub Actions | journal committed back to repo |
| `scripts/oros_cron.sh` via `com.oros.morningrun.plist` | weekdays 09:35 ET | JP MacBook, conda env `dev2` | `data/journal/cron_YYYY-MM-DD.log` |
| `scripts/oros_watchdog.sh` via `com.oros.watchdog.plist` | weekdays 10:20 ET and 17:50 ET | JP MacBook | `data/journal/watchdog_YYYY-MM-DD.log` |
| `ui/app.py` Scan Now | human click | Streamlit | breadth entry, source `scan-now` |
| `scripts/oros_run.py` direct | manual | anywhere | `manual_run_*.log` |

The watchdog is a fallback, not a scheduler. It checks whether the cloud slot
produced a journal and runs locally only if it did not.

`CURRENT` `BROKEN` The cloud path has not committed a journal since 2026-08-07.
Every daily output since then was produced by the watchdog fallback on the
MacBook. See defect D1.

Edition resolution lives in `scripts/oros_run.py`. Eastern hour at or after
14:00 resolves to `evening` (the Closing Bell); anything earlier resolves to
`morning`.

---

## 2. Universe layer

`data/universe.py`

Sources: Nasdaq Trader `nasdaqlisted.txt` and `otherlisted.txt` for listings,
SEC `company_tickers.json` for CIK mapping used by the 10-K RAG.

Flow:

```
listing files  ->  get_universe(filtered=False)   ~8000 symbols
               ->  refresh cap (OROS_REFRESH_CAP, default 1500)
               ->  price refresh
               ->  build_liquid_ranking()          ~1137 names with cache
               ->  scan cap (OROS_CAP, default 500)
               ->  symbols[]   the OROS 500
```

Caps have exactly one home: `ml/oros_config.py`. No runner script may restate
a cap. The liquid core (`_SP100 + _SECTOR_LEADERS` from
`ml/momentum_screener.py`) is refreshed first so the cap covers real names.

Journaled by `ml/oros500.py` as the day's constituents so the broadcast's
"the OROS 500" claim is true by construction.

---

## 3. Price layer

`data/price_cache.py`

Daily OHLCV pulled from yfinance in batches of 200 with `threads=True` and
`auto_adjust=True`, cached to parquet per ticker, served back by
`get_history()` with no network call at scan time.

`DataQualityReport` fields: `requested`, `fetched`, `from_stale`, `empty`,
`failed`.

`CURRENT` `BROKEN` A ticker whose download raises is counted in `from_stale`
and not in `failed`, so the log reports `failed=0` while hundreds of names
were graded on old bars. Two error classes dominate:

* `TypeError("'NoneType' object is not subscriptable")` from yfinance on a
  failed symbol inside a batch.
* `OperationalError('unable to open database file')` from the yfinance sqlite
  timezone cache under `threads=True`.

See defects D2 and D3.

A single daily cache feeds both resolutions. There is no separate weekly pull.

---

## 4. Stage engine and the MA contract

`ml/stage_analyzer.py`

### 4.1 The contract: the trend spec is a parameter, the single source rule is not

`TARGET` Revised 2026-09-04 after the multi tenant requirement landed.

OROS is not shipping one house strategy. It is shipping configurable bots, and
customers divide on exactly this line: a Weinstein reader wants a 30 week mean
of weekly closes, a long term trend follower wants a 200 day mean of daily
closes, a Minervini reader wants the 50 / 150 / 200 daily stack. The moving
average is therefore **user input**, not a system constant.

What does not become configurable is the property that makes a call checkable.

**The trend spec.** Every bot resolves exactly one:

```
trend:
  resolution:   weekly | daily
  window:       30              # bars at that resolution
  slope_lookback: 4             # bars
  confirm_on:   completed_bar   # never an intrabar cross
  context:      [50, 150, 200]  # daily bars, display and SEPA only
```

**The invariant.** Within one bot run, the resolved trend spec governs the
scan, the stop, the invalidation and every chart drawn for that run. One
series, one run, three consumers. A second definition anywhere inside a single
run is a defect, exactly as before. The parameter varies per bot; the single
source rule holds per run.

**Presets shipped, custom allowed.**

| Preset | Resolution | Window | Notes |
|---|---|---|---|
| Weinstein | weekly | 30 | the default, matches the book |
| Minervini SEPA | daily | 150 | plus the 50 / 200 stack as gates |
| Long trend | daily | 200 | the classic 200 day line |
| Custom | either | 5 to 300 | user set, validated |

**Labels carry their spec.** A stage produced under a 200 day daily spec is
not Weinstein's Stage 2 and must never be printed as though it were. Every
stage label, journal row, chart annotation and API response carries the spec
that produced it: `Stage 2 (200d)`, `Stage 2 (30w)`. A customer comparing our
output to a Weinstein chart, or to another customer's bot, must never have to
guess which definition produced the number. This is a correctness requirement,
not a cosmetic one.

**The 30 week and 150 day lines are the same object at two resolutions.** That
is why a Weinstein chart showing MA 50 / 150 / 200 on a daily timeframe is not
a contradiction. Offering both is offering a choice of resolution, not a choice
of truth.

### 4.2 What the code does today

`CURRENT` `BROKEN`

```python
WEEKS_IN_MA = 30
TRADING_DAYS_PER_WEEK = 5
MA_WINDOW_DAYS = 150
ma = close.rolling(150).mean()      # daily closes, not weekly
```

Divergences from the contract:

0. The window is a module level constant, not a per bot parameter. Nothing in
   the engine accepts a trend spec, so no customer can choose one.
1. The stage is decided on a 150 period mean of **daily** closes.
2. Weekly close confirmation is approximated with `close.iloc[-6]` and
   `ma.iloc[-6]`, five sessions back, not a real weekly bar.
3. `ml/daily_report.py` line 859 draws a genuine weekly 30 period mean
   (`_weekly(df)["Close"].rolling(30).mean()`). The published chart therefore
   shows a different series from the one that produced the call.
4. No 50 day or 200 day line exists in the stage engine at all. They appear
   only inside the SEPA entry of `ml/strategy_registry.py` (`sma50 > sma150 >
   sma200`).

See defect D4.

### 4.3 Derived indicators

Computed in `_compute_indicators`:

| Field | Definition | Window |
|---|---|---|
| `ma_30w` | mean of closes | 150 sessions `CURRENT`, 30 weekly bars `TARGET` |
| `ma_slope_pct` | MA now vs MA 20 sessions back | 4 weeks |
| `pct_above_ma` | (close minus MA) / MA | spot |
| `ma_approach_pct` | MA now vs MA 130 sessions back | 26 weeks, separates Basing from Topping |
| `pct_above_ma_prev` | same as above, 6 bars back | hysteresis input |
| `volume_surge` | mean of last 5 sessions / mean of prior 50 | deliberately centred near 1.0 |
| `mansfield_rs` | (ratio / SMA150 of ratio minus 1) times 100, vs SPY | 150 sessions |
| `mansfield_rs_rising` | RS today >= RS 21 bars back | 4 weeks |

### 4.4 Stage assignment

| Stage | Name | Condition sketch | Action |
|---|---|---|---|
| 1 | Basing | flat MA, price within 5%, MA approached from below | watchlist |
| 2 | Advancing | price 2% or more above a rising MA | buy zone |
| 3 | Topping | flat MA, MA approached from above | trim, no new longs |
| 4 | Declining | price 2% or more below a falling MA | avoid |

Two bar hysteresis applies to promotion into Stage 2 and demotion into
Stage 4, so a single bar cannot flip a stage.

---

## 5. Strategy layer

`ml/strategy_registry.py`

Every book is a peer. Nothing is hard coded as the foundation. Each entry
implements `score(ctx) -> StrategyScore` on a common 0 to 1 scale.

| Key | Author shown in UI | Basis |
|---|---|---|
| `weinstein` | Weinstein | wraps `ml/stage_analyzer.py` |
| `sepa` | Minervini | trend template, 50 / 150 / 200 stack |
| `canslim` | O'Neil | chartable signals plus earnings growth |
| `technical` | Tech book | RSI, MACD, trend composite |
| `swing` | Swing book | short term breakout and pullback |
| `value` | Graham | P/E, P/B from fundamentals |
| `growth` | Lynch | PEG and growth, GARP |
| `ipo` | O'Neil and Minervini | wraps `ml/new_listing_scanner.py` for names under 150 sessions old |

Display names come from `display_name()`. The router may weight any strategy
to zero.

---

## 6. Orchestration and portfolio construction

`ml/agent_orchestrator.py` runs six named agents in order and records a trace
that is journaled with the proposal.

```
DataAgent          candidate universe, benchmarks removed
RegimeAgent        regime from SPY stage plus VIX
RouterAgent        regime -> base strategy weights
MemoryAgent        tilt weights by what worked in similar past states
ConstructionAgent  ensemble scores, news enrich, size the book
RiskAgent          sector concentration, cash, single name checks
```

Heavy lifting is delegated to `build_portfolio` in `ml/portfolio_engine.py`,
which receives the regime and weights already computed so nothing is
recalculated.

`ml/auto_config.py` `choose_auto_settings()` picks mandate, account, position
count, risk percent, minimum liquidity, and sector cap from the forward
scoreboard and the regime. This is the no human in the loop path.

Risk rules enforced in `portfolio_engine.entry_risk_gate`: reject entries more
than `EXTENSION_MAX` above the 150 day mean, reject setups whose nearest
support sits too far below entry, widen noise tight stops.

---

## 7. The pick funnel

`ml/top_picks.py` `weinstein_top_picks()` is the strictest path in the system.
A name must clear every one of these in order:

```
1.  history length >= _MIN_HISTORY
2.  analyze_stage() does not raise
3.  stage == 2
4.  not is_invalidated
5.  weinstein_buy_confirmed          volume >= 1.5x AND mansfield_rs > 0 AND rs rising
6.  setup_type in ("fresh", "watching")
7.  trade_setup applicable AND direction == "LONG"
8.  entry_risk_gate returns a stop
9.  entry minus stop > 0
10. shares at risk_pct > 0
```

Gate 6 is where most of the universe dies. `_classify_setup_type` marks a
Stage 2 name `extended` if any of:

| Rule | Above MA | Volume condition |
|---|---|---|
| a | 40% or more | none, unconditional |
| b | 25% or more | 1.0x or less |
| c | 20% or more | under 1.5x |
| d | 30% or more | none, pure price extension |

`CURRENT` `BROKEN` On 2026-09-03, 216 of 495 graded names were Stage 2
Advancing and zero passed the funnel. `picks_ledger.json` shows one pick since
2026-08-27 and four consecutive empty sessions. Nothing in the code records
which gate rejected which name, so an over tight model and a broken model are
indistinguishable from the outside. See defects D5 and D6.

---

## 8. Journal, the system of record

All under `data/journal/`.

| File | Writer | Readers | Shape |
|---|---|---|---|
| `portfolio_YYYY-MM-DD_HHMM.json` | `portfolio_journal.record_proposal` | report, digest, broadcast, scoreboard | one proposal, includes agent trace and `changes` |
| `stage_breadth.json` | `ml/breadth.record_breadth` | video Market Analysis scene | append per date, morning |
| `stage_breadth_close.json` | `ml/evening_report` Second Look | Closing Bell | append per date, evening |
| `picks_ledger.json` | `ml/picks_ledger` | Closing Bell grading | append per date, may be empty |
| `day_tally.json` | evening | The Race, season record | append only, live vs frozen vs SPY |
| `capstone_chain.json` | evening | live chain, idempotent per date | one entry per date |
| `alerts.log` | `ml/notifier` | human | text |
| `cost_YYYY-MM.json` | budget governor | budget gate | spent to date |
| `reports/oros_report_YYYY-MM-DD.pdf` | `ml/daily_report` | email, public mirror | PDF |
| `reports/oros_brief_YYYY-MM-DD.mp3` | `ml/daily_video` | audio brief | MP3 |
| `reports/*.sent` | notifier | same day resend guard | marker |
| `warehouse/` | `ml/data_collector` | model training | feature rows, labelled forward |

`CURRENT` `BROKEN` `stage_breadth.json` accepted an entry for 2026-09-04 with
`total: 2`. A two name scan is now a data point in the series the video
narrates. See defect D7.

`CURRENT` `BROKEN` `scripts/oros_run.py` line 233 references `props`, which is
never assigned in that function. The NameError is swallowed by a bare
`except Exception: pass`, so the `changes` diff has not been written into the
journaled proposal since the 2026-08-31 refactor. The uniformity rule in
invariant 5 is therefore unenforced: report, digest, and broadcast each
recompute the diff. See defect D8.

---

## 9. Outputs

### Morning
1. `ml/notifier` portfolio update email on a change.
2. `ml/daily_report.send_daily_report` PDF with market state, P&L, benchmark
   chart, the pick table, and the weekly chart with the MA overlay.
3. `ml/daily_video` renders the newscast MP4 with nine scenes, narration
   segmented and cached by voice and text hash so only the day's numbers hit
   ElevenLabs.
4. `ml/publish_youtube` uploads with description, chapters, and captions from
   the `.srt` and `.meta.json` sidecars.

### Evening, the Closing Bell
`ml/evening_report.send_evening_report`:
1. Refresh only what grading needs.
2. Grade the morning picks off the day's bar.
3. Live book vs frozen book vs SPY, update `day_tally.json`.
4. Update `capstone_chain.json`, idempotent per date.
5. The Second Look, rescan off closing bars into `stage_breadth_close.json`.
6. The Loop, self reflection on expectancy and the throttle.
7. Render, publish, email.

`CURRENT` `BROKEN` `Closing Bell: skipped (no ffmpeg)` on the watchdog path.
The channel's last upload is 2026-08-31. See defect D9.

### Public mirror
The workflow mirrors the day's PDF to the public `oros-reports` repo, gated by
`OROS_REPORTS_TOKEN`, refusing any PDF built with the personal book and any
PDF whose extracted text contains a personal account marker. The gate fails
closed on a parse error.

---

## 10. UI

`ui/app.py` with components in `ui/components/`: assistant mode, trader mode,
portfolio mode, multi strategy compare, research dossier, chat panel, youtube
mode, cron control, calendar heatmap, chart helpers, memo PDF, disclaimer.

`route_to_trader()` hands a built universe to Trader Mode using a content
addressable cache key, so the scan universe shown in Trader Mode is the one
that was actually scanned.

---

## 12. The bot configuration object

`TARGET` The unit the customer buys is a bot, and a bot is a serialisable
config plus the journal it accrues. Nothing about a bot may live in module
level constants.

```
BotConfig
  trend        TrendSpec            see 4.1
  strategies   {key: weight}        any registry key, any weight, zero allowed
  gates        GateSpec             volume surge, RS floor, extension policy
  risk         RiskSpec             risk per trade, max heat, sector cap, positions
  universe     UniverseSpec         cap, min price, min dollar volume
  execution    paper | live         live requires a separate consent record
```

Two rules make this safe to ship.

1. **Every gate threshold that is currently a module constant becomes a field
   with a default.** `WEINSTEIN_MIN_VOLUME_SURGE`, the four extension
   thresholds, `WEINSTEIN_MIN_MANSFIELD_RS` and the stage boundaries all move
   into `GateSpec`. Defaults reproduce today's behaviour exactly, so the move
   is a refactor with a test proving output is unchanged at defaults.
2. **Config is journaled with every proposal.** A pick without the config that
   produced it is unreproducible and therefore unsellable. The proposal record
   carries a config hash and the full resolved spec.

Extension policy deserves its own field because it is the gate that currently
returns nothing. `GateSpec.extension_policy` takes `exclude` (today's
behaviour) or `penalise` (rank down, still returned with a quality grade). A
bot that returns nothing four days running looks broken to whoever is paying
for it, so `penalise` plus an honest grade should be the shipped default.

---

## 13. Two pick tracks, deliberately separate

`TARGET` The product makes two different kinds of claim and they must never be
blended into one number.

### Track A: the agent track, explainable by construction

Weinstein, SEPA, CANSLIM and the rest. Each produces a score and a chain of
named conditions that produced it. The customer can read why. The claim is
"this is what the rule says", and the evidence is the rule.

The UI must show the conditions, not just the score: which gate passed, which
failed, and by how much. That is the whole value of a rule based track.

### Track B: the ML track, unbiased by construction

`ml/meta_features.py` and `ml/meta_model.py` already hold the right
architecture: cross sectional z scoring within each date, classic factors
(12 minus 1 momentum, 60 day realised volatility, beta to SPY, dollar volume
liquidity), walk forward training, and Information Coefficient evaluation
against forward excess return. That is a defensible design.

Four rules keep the "unbiased" claim true:

1. **Labels are market truth, never agent agreement.** Forward excess return
   over a stated horizon. A model trained to agree with Weinstein measures
   Weinstein, not the market.
2. **A model that consumes agent scores as features is a stacker, and is
   labelled a stacker.** It is a legitimate product; it is not an independent
   opinion. If the marketing says independent, the features must exclude the
   agent scores.
3. **Walk forward with an embargo.** Training data ends strictly before the
   test date, with a gap of at least the label horizon so an overlapping
   forward window cannot leak backwards.
4. **Report calibration and IC, not accuracy.** Mean IC, its t statistic, and
   the top minus bottom spread. Accuracy on an imbalanced financial label is
   marketing, not evidence.

### Where they meet

They meet at the display layer and nowhere else. The customer sees the agent
verdict, the model score, and their disagreement. Disagreement is information
and should be surfaced, not averaged away. A blended composite that hides
which track drove a pick destroys both claims at once.

`CURRENT` `BROKEN` The training warehouse holds 10,740 rows across 643 tickers
but only **19 dates**, with 7,109 labeled at a 20 day horizon. Nineteen dates
is a wide cross section and almost no time series. Any model fitted on it will
overfit, and no IC computed on it will carry a usable t statistic. See defect
D10.


---

## 11. Divergence register

Open divergences between `CURRENT` and `TARGET`, each with a defect ID in
`docs/DEBUG_BRIEF.md`.

| ID | Divergence | Severity |
|---|---|---|
| D1 | Cloud run dead since 2026-08-07, product depends on one laptop | launch blocker |
| D2 | Failed downloads reported as `failed=0`, absorbed into stale reuse | launch blocker |
| D3 | yfinance sqlite cache errors under `threads=True` | high |
| D4 | Trend spec is a module constant, and three different definitions of it exist across scan, stop, and chart | launch blocker |
| D5 | Pick funnel has no per gate instrumentation | high |
| D6 | Zero picks for four consecutive sessions against 216 Stage 2 names | high |
| D7 | Breadth journal accepts a two name scan as a day | medium |
| D8 | `props` NameError silently disables the uniformity rule | medium |
| D9 | ffmpeg missing on the watchdog path, no video since 2026-08-31 | medium |
| D10 | Training warehouse has 19 dates; too shallow to fit or evaluate the ML track | launch blocker for Track B |
| D11 | Stage labels do not carry the spec that produced them | high |
| D12 | Gate thresholds are module constants, so no bot can be configured | launch blocker |

# OROS Evidence Inventory
**Audit date:** August 27, 2026
**Purpose:** An honest separation of what OROS can currently prove from what it cannot, ahead of replying to capstone feedback.
**Audience:** JP first. Sections 1, 2 and 4 are safe to share externally. Section 3 is internal until fixed.

---

## 1. What is built and verifiable

Every figure below was read directly from the repository and the decision journals on August 27, 2026.

### System scale
| Item | Measured value | Source |
|---|---|---|
| Python modules | 118 files, 31,207 lines | repository walk |
| Agent roles in the orchestration trace | 6 (Data, Regime, Router, Memory, Construction, Risk) | `data/journal/portfolio_*.json` `agent_trace` |
| Peer strategy books in the registry | 8 (Weinstein, Trend Momentum, O'Neil, Technical, Swing, Classic Value, GARP Growth, New Issue Momentum) | `ml/strategy_registry.py` REGISTRY |
| Scanning universe | 500 names, tracked with entered and left lists | `data/journal/oros500.json` |
| Cited research memos produced | 19 PDFs | `docs/`, `Emailed Reports/` |
| Automated daily reports produced | 22 PDFs | `docs/`, `Emailed Reports/` |

### The decision record that already exists
| Artifact | Count | Window |
|---|---|---|
| Scored pick days | 19 files | May 26 to June 22, 2026 |
| Individual scored pick rows | 1,499 | same |
| Portfolio snapshots | 180 files | June 21 to August 27, 2026 |
| Watchdog run logs | 37 files | ongoing |
| Forward outcome price captures | 85 files | from May 26, 2026 |

Every pick row was written with a buy stop, a stop loss and a target **before** the outcome was known. That is the single most valuable asset in the whole project and it is worth saying so plainly.

### Validation machinery already written
1. **Point in time backtest harness** (`evaluation/backtest.py`). Rolls an as of date across the SPY calendar, slices every price series to that date, scores with the registry, routes by regime, holds a fixed horizon, and measures forward return using only future bars. Fundamentals are deliberately excluded because the only source is a current snapshot and would leak the future. The module docstring states its own remaining caveats: survivorship bias, no transaction costs, no slippage, no news layer.
2. **Retrieval evaluation harness** (`evaluation/test_retrieval.py`, results in `evaluation/results/retrieval.json`). 33 golden questions scored for section coverage and relevance.
3. **Citation validator** (`evaluation/citation_validator.py`). Extracts every numerical claim from a memo and checks for a source marker within a character window. Enforces provenance mechanically rather than by inspection.
4. **Outcome scoring with pre declared parameters** (`data/journal/outcomes_*.json`). Lookahead windows of 1, 5 and 20 trading days with hit thresholds of 0.5%, 2% and 5% written into the file itself.
5. **External consensus divergence study** (`docs/external_validation.md`). 15 tickers drawn from 6 independent professional methodologies scored through the system. Zero passed the buy gates. The document argues, correctly, that this is the intended behavior of a strict implementation rather than a calibration failure.
6. **Frozen benchmark design** (`ml/capstone_tracker.py`, `data/journal/capstone_baseline.json`). A first portfolio frozen on July 6, 2026 and never edited, tracked daily against an evolving live book and against SPY.

That list is a validation *architecture*. It is not yet a validation *result*. The distinction is the whole of the professors' point.

---

## 2. What OROS cannot currently prove

**It cannot claim performance.** Not weakly, not directionally, not yet.

The frozen July 6 portfolio is the cleanest possible test because it has never been touched. Measured today against a single consistent price series, so that both dates are computed the same way:

| As of | Frozen first portfolio | SPY over the same window | Spread |
|---|---|---|---|
| July 29, 2026 (presentation day) | $99,964 (−0.04%) | −2.90% | **+2.87 points ahead** |
| August 27, 2026 (today) | $98,985 (−1.01%) | +2.44% | **−3.45 points behind** |

Not one share changed. Not one rule changed. The spread moved 6.32 percentage points and flipped sign in 21 trading days.

For completeness, the report that actually ran on presentation day reported the frozen book at $100,602 (+0.60%) against SPY at $98,613 (−1.39%), a spread of +1.99 points. Those figures came from the price cache as it stood on July 29. Today's cache produces different closes for the same historical dates, which is defect 4 in the next section and is itself a material finding.

Either series tells the same story. A portfolio that looked like it was beating the market on presentation day is now losing to it, and nothing about the portfolio changed. Anyone who reads that understands immediately why a seven week record is not evidence.

**Secondary claims that also do not hold up yet:**

- **Retrieval quality is weak, not strong.** Of 33 golden questions, only 10 retrieved any expected section. Mean section coverage is 0.35 and mean relevance is 0.33. This is a documented weakness. Do not present the retrieval harness as a passing grade; present it as an instrument that correctly detected a problem.
- **The backtest has never been run to completion and archived.** `evaluation/backtest.py` exists and is methodologically sound. There is no results file anywhere in the repository. The harness is unexercised.
- **There is no unit test suite.** `tests/` contains only `__init__.py`.
- **Survivorship bias is unaddressed.** The universe is current listings, so every company that failed between the backtest start and today is invisible. This alone can manufacture apparent edge.

---

## 3. Integrity defects found during this audit

These are internal. Fix before any external validation claim is made.

**Defect 1: the live performance chain lost its history.**
`data/journal/capstone_chain.json` declares `start_date: 2026-07-06` but retains only 4 daily returns, beginning August 22, 2026. Running `ml.capstone_tracker.live_chain_status()` today returns +0.72% and labels it as the record since July 6. That is wrong by construction. The +3.98% over 17 trading days that was presented on July 29 is no longer reproducible from the journal.

Root cause: `update_live_chain()` rebuilds the chain dict from a default when the file fails to parse, and it writes with a plain `write_text`, so a partial write or a parse failure silently truncates the entire history and the next run starts a fresh chain under the original start date. There is no append only guarantee and no integrity check between the declared start date and the number of retained observations.

The ledger that is supposed to carry a multi year longitudinal record cannot currently survive a single bad write. Together with defect 4 this is the pair that has to be fixed before any long running study starts, because between them they mean the record can be lost and the inputs can change underneath it.

**Defect 2: `picks_ledger.json` holds one entry.** Same class of problem. The pick day files themselves survived, so the record is recoverable, but the ledger is not the durable artifact it appears to be.

**Defect 3: no hash chaining or write ahead journaling on any evidence file.** For a longitudinal study the burden is to prove that no entry was edited after the fact. Right now nothing prevents it and nothing would detect it.

**Defect 4: historical closes are not reproducible. Adjusted close drift.**
The report generated on July 29 recorded SPY closing at 740.86 that day. The current price cache returns 729.46 for the same date. The gap is dividend and split adjustment applied retroactively by the data provider, which silently rewrites every historical close every time the cache refreshes.

Consequence: no backtest result is reproducible, and no historical performance figure can be verified after the fact, because the inputs change underneath it. For a longitudinal study this is disqualifying on its own. The fix is to snapshot raw unadjusted OHLCV at capture time, store the adjustment factors separately, and reconstruct adjusted series deterministically at analysis time. This was already on the roadmap as the dividend drift item. It should be promoted to blocking.

**Defect 5: a real money book is mirrored in `data/journal/my_portfolio.json` and the file carries an account identifier.** Keep this file, and any figure derived from it, out of every external document, repository and report. Personal trading results are also the weakest possible evidence category because the sample is one account over two months.

---

## 4. The honest one paragraph summary

OROS has a complete decision provenance layer, a methodologically careful point in time backtest harness, a mechanical citation validator, a retrieval evaluation instrument, a frozen benchmark, and roughly 1,500 pre committed scored decisions with stops and targets recorded before outcomes. What it does not have is a single completed study. The correct claim today is not "the approach works." It is "the approach is instrumented well enough to be falsified, and here is the protocol that will falsify it."


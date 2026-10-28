# OROS EXECUTION SPEC

Forward spec for Phase 7, live execution. Companion to `docs/SYSTEM_MAP.md`
(what exists) and `docs/DEBUG_BRIEF.md` (what is broken). Written 2026-09-04.

Nothing in this document is built. It exists so the decisions are made before
the code, not discovered after a fill.

---

## 0. Decisions taken 2026-09-04

| Decision | Choice |
|---|---|
| Execution model | **Armed autopilot inside user set limits.** No per order approval. |
| LLM role in Agent Build | **Config author, narrator, and veto.** It may remove a candidate with a journaled reason. It may not add, reweight, or score. |
| BYO strategy depth | **Composition from registry primitives only.** No user authored code, no DSL, at any tier for now. |

Each choice below is written against these, not against the alternatives.

---

## 1. What armed autopilot changes

The current invariant, "OROS proposes and journals only", is not a disclaimer.
It is the reason every defect in `docs/DEBUG_BRIEF.md` is currently survivable.
Removing it reclassifies all of them.

| Defect | Today | Under autopilot |
|---|---|---|
| D2 stale bars reported as success | a wrong report | an order sized and priced off a bar several days old, on 14% of the universe, while the log says `failed=0` |
| D8 swallowed exception | a missing diff | an order you cannot prove you did or did not send |
| D5 no funnel instrumentation | you cannot diagnose | you cannot explain a fill to the person whose money moved |
| D7 two name scan journaled as a day | a wrong chart | a rebalance computed against a two name view of the market |
| D1 cloud dead, laptop carrying | a late email | execution that stops when a laptop sleeps, with positions open |

**Phases 0 through 5 of the debug queue are hard prerequisites for Phase 7.**
Not a parallel track. An autopilot built on top of a data layer that reports
`failed=0` while two hundred symbols failed is a system that will place a
confident wrong trade and log it as a success.

---

## 2. The duplicate order problem, which already exists

This is the highest risk item and it is not hypothetical. OROS already runs
the same day more than once and produces different books.

On 2026-09-03 the journal holds three proposals:

```
portfolio_2026-09-03_0520.json
portfolio_2026-09-03_1338.json   cron, 09:38 ET
portfolio_2026-09-03_1422.json   watchdog fallback, 10:22 ET
```

The 09:38 book held ABBV and CVX. The 10:22 book dropped both and added BIIB
and WELL. Same day, same market, two runners, four positions different. That
difference is a scheduler artifact, not a signal.

Under autopilot with naive execution, that day is four round trips of churn
paid for out of a customer's account, caused by a fallback that exists to make
sure a report gets emailed.

### Requirements

1. **A trading day has exactly one authoritative book.** A second run on the
   same day for the same bot reconciles against the existing book and may only
   act on genuinely new information, or it is a no op. It does not get to
   propose a fresh book and rebalance into it.
2. **Deterministic client order ids.** Every order carries an id derived from
   `(bot_id, trading_date, ticker, side, config_hash)`. The broker rejects a
   duplicate. A retry, a double cron fire, a watchdog overlapping a cloud run,
   and a manual rerun all collapse to the same id and cannot double fill.
3. **The watchdog may not execute.** It exists to cover a missing report. Give
   it a hard `OROS_EXECUTION=0`, so a fallback run can never trade.
4. **Broker is the source of truth for positions.** The journal records intent.
   Reconcile against the broker before computing any action, and treat any
   divergence as a halt condition rather than something to correct silently.

---

## 3. Order lifecycle

The stage engine already produces the right shape: a buy stop entry above the
pivot, a stop loss at the trend line, and a size from risk per trade. That maps
onto real order types cleanly. What is missing is everything after submission.

| Stage | Requirement |
|---|---|
| Submit | Entry as a stop order resting at the broker, not a daily "check and market buy". A breakout that happens intraday must be caught. |
| Protect | The stop loss rests at the broker from the moment of fill. A stop that exists only in the journal does not protect anyone overnight. |
| Partial fill | A partially filled entry gets a proportionally sized stop, not the full one. Journal the actual filled quantity, never the intended one. |
| Gap through stop | The trend line stop is not a guaranteed exit. Fills below it are normal and must be modelled in the risk wallet, not treated as an error. |
| Halt, delist, corporate action | Explicit handling. A split changes share counts and stop prices. A halt leaves a resting order that must be pulled. |
| Reconcile | Every run compares broker positions to the journal before acting. Divergence halts the bot and alerts. |

**Pre trade risk, not post hoc.** `max_heat` is currently a build constraint
checked during construction. Under autopilot it must be checked against actual
broker positions immediately before each submission, because the account state
at 09:31 is not the account state the book was built from.

---

## 4. Kill switch

1. One global flag halts all execution for all bots, and one per bot flag halts
   one. Both are read immediately before every submission, never cached.
2. It must work when the app is down. A flag in the database that the execution
   worker reads, not a button in Streamlit.
3. Halting cancels resting entry orders. It does not cancel protective stops,
   because an unprotected open position is worse than a halted bot.
4. Automatic halts on: broker reconciliation divergence, a data quality report
   exceeding the degraded threshold from D2, a config hash that does not match
   the armed config, and any unhandled exception in the execution path.

---

## 5. The veto layer

The LLM authors config, narrates results, and may veto. That last power needs a
tight contract or it quietly becomes selection.

### Contract

1. **Removal only.** A veto removes a candidate from the book. It cannot add a
   name, change a weight, move a stop, or alter a gate. Worst case the bot
   under trades, which is a recoverable failure. Addition is not.
2. **Budgeted.** A cap on vetoes per build, roughly two of twelve. A model
   vetoing eight of twelve is selecting, not reviewing. When the cap binds, the
   build proceeds with the cap applied and logs that it bound.
3. **Journaled in full.** Model, prompt version, temperature, the candidate
   removed, the reason in the model's own words, and the timestamp. A veto with
   no recorded reason is invalid and is discarded.
4. **The counterfactual is journaled too.** Every build records the book that
   would have existed with no vetoes applied. This is the whole point.

### Why the counterfactual matters

The book is no longer reproducible from config alone, so the unit of
reproducibility becomes `config_hash + veto_log`. That is acceptable, but only
if the veto layer can be evaluated.

With the counterfactual book journaled every day, after sixty sessions you can
answer a question almost nobody in this space answers honestly: **does the LLM
veto add value or destroy it?** Vetoed book against unvetoed book, same config,
same dates, forward returns on both.

That is a direct extension of the agent layer ablation already planned in the
longitudinal validation work, it is a publishable result, and it is a real
differentiator. It also means model choice becomes measurable rather than
marketing: the deterministic core is identical across vendors, and the veto
layer carries a per model track record.

**The claim that dies.** "Same config, any model, identical portfolio" is no
longer true once the model can veto. Do not market it. The honest version is
that the deterministic core is identical across models and the veto layer is
measured separately, per model, with its record shown.

---

## 6. BYO strategy scope

Composition from registry primitives. Concretely, a user strategy is:

```
weights      over existing registry keys, any of them zero
GateSpec     volume surge, RS floor, extension policy and thresholds
TrendSpec    resolution, window, slope lookback
RiskSpec     risk per trade, max heat, sector cap, position count
UniverseSpec cap, min price, min dollar volume
```

No code execution anywhere in the path. No expression language. No uploads.
This covers most of what people mean when they say their own strategy, and it
keeps the execution worker free of user supplied logic while it holds broker
credentials.

Revisit only after execution has been stable for a meaningful period, and only
with a sandbox that has been tested by someone whose job is breaking sandboxes.

---

## 7. The arming gate

**No config reaches execution without an out of sample record for that exact
config.**

1. On save, a config is evaluated walk forward on the backfilled corpus (see
   D10) and shown to the user with mean IC, the top minus bottom spread, the
   worst drawdown in the sample, and the survivorship caveat stated plainly.
2. Arming is a separate deliberate action from saving, with the numbers on
   screen at the moment of arming.
3. The armed config hash is stored. If the config changes, the bot disarms and
   must be armed again against the new evaluation.
4. A config whose evaluation is weak still arms if the user insists, but the
   weak numbers are recorded as having been shown.

"You built it" is only a defense if the system showed the record at the moment
the user armed it.

---

## 8. Flagged, not engineering

Armed autopilot means trading a customer's account without per order approval,
for compensation, according to a strategy the platform supplies. Whether that
makes the operator an investment adviser turns on facts, discretion,
compensation, personalisation, and holding out, not on architecture.

This must go to securities counsel **before** the execution layer is built,
because the answer changes the design. Whether the customer links their own
brokerage by OAuth or the platform holds credentials, whether discretion sits
with the user's configured bot or with the operator, and whether an adviser
registration or an exemption applies are all architectural inputs, not
paperwork to file afterwards.

This is a flag from an engineer reading the shape of the product, not legal
advice.

---

## 9. Phase plan

```
Phase 0-5   the existing debug queue                      prerequisite
Phase 6     Agent Build tab, paper only
              BotConfig authoring by LLM
              veto layer with counterfactual journaling
              arming gate against the backfilled corpus
Phase 7a    broker adapter + paper trading end to end
              deterministic client order ids
              reconciliation loop, kill switch, pre trade risk
              run in paper for a full quarter, no exceptions
Phase 7b    live execution, one account, small size
Phase 7c    live execution, customers
```

Phase 7a runs in paper for a full quarter before anything touches real money.
Not as caution theatre. As the only way to find the corporate action, the halt,
the partial fill and the gap that the code has never seen.

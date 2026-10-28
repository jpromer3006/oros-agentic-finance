# M1 — make the ML scan trustworthy

The first ML work item. Paste the block at the bottom into Claude Code from the
repo root. Everything above it is the reasoning, so the session can be audited
later.

Scope: `ml/meta_features.py`, `ml/meta_model.py`, `data/price_cache.py`.
Out of scope: the stage engine, the gates, `top_picks.py`, execution.

This runs ahead of the D4 / D12 config refactor on purpose. Track B consumes
price bars and factor math, not the stage engine, so the two do not collide,
and the corpus is the longest lead item in the whole plan.

---

## What already works

`build_quant_dataset(universe, rebalance_days, horizon, lookback_months)` walks
backwards through the SPY calendar, slices each ticker with `df.loc[:as_of]`,
scores it as of that bar, and computes a forward return `horizon` bars later.
That is a genuine point in time construction. The label is already forward
**excess** return, market neutral by cross sectional demeaning. `ic_walkforward`
already z scores within date and reports mean IC, an IC t statistic, and the
long minus short spread.

That is the right architecture. The problems are in the details, and every one
of them makes the numbers look better than they are.

---

## B1  The walk forward has no embargo, so labels leak backwards

`ic_walkforward` line 172:

```python
train, test = df[df["date"] < d], df[df["date"] == d]
```

A training row dated `d` minus 15 sessions carries a label resolved 20 sessions
after it, which is 5 sessions **after** the test date. The model is trained on
outcomes that had not happened yet at test time.

The interaction is what makes this urgent. To get more test dates the obvious
move is to lower `rebalance_days`. At `rebalance_days=5` with `horizon=20`,
three consecutive training dates leak instead of one. **The fix for the sample
size problem amplifies this bug.** They have to be done together.

Fix: exclude any training row whose label resolution date is at or after the
test date. Concretely, train only on rows whose `as_of` is at least `horizon`
trading sessions before `d`.

## B2  `min_train` counts rows, not dates

Line 161, `min_train=80`. With a 500 name universe that threshold is met by the
first rebalance date. There is effectively no minimum training history. An IC
t statistic quoted over a handful of test dates is not evidence.

Fix: a separate `min_train_dates`, defaulted to something honest (30 or more),
and refuse to report rather than reporting a number built on fewer.

## B3  The ML track is a stacker, and is not labelled as one

```python
STRAT_KEYS  = ["weinstein", "sepa", "canslim", "technical", "swing", "ipo"]
FEATURE_KEYS = STRAT_KEYS + FACTOR_KEYS
```

The model consumes the six agent scores as features. That is a legitimate and
useful model, but it is **not** an independent opinion, and the product is going
to claim two tracks, one of which is unbiased by construction. A stacker sold as
an independent second opinion is the same claim made twice.

Fix: three arms reported side by side on the same dates.

| Arm | Features |
|---|---|
| `book` | today's hand weights, unchanged, as the baseline to beat |
| `stacker` | agent scores plus factors plus macro |
| `independent` | factors plus macro only, no agent scores at all |

`independent` is Track B. The three way comparison is also the answer to the
question the capstone feedback asked for: if `independent` matches `stacker`,
the agent layer adds nothing to the ranking and that is a real finding. If
`stacker` beats it, the agents carry information the factors do not. Publish
whichever way it lands.

## B4  Only about fourteen test dates are reachable today

`DEFAULT_PERIOD = "2y"` in `data/price_cache.py`, and the builder needs 260 bars
of history before the first usable `as_of`. That leaves roughly 240 sessions,
and at the default `rebalance_days=15, lookback_months=10` the loop produces
around fourteen dates.

Fix: deepen the research history and tighten the interval. Target 40 or more
test dates surviving the embargo. Do not fabricate dates by lowering `horizon`;
the horizon is a product decision, not a knob for making n look bigger.

## B5  Rebuilding the corpus changes the past

`build_quant_dataset` calls `refresh_prices(universe + ["SPY"])` on entry, and
the cache is written with `auto_adjust=True`. Two consequences.

1. Building the dataset is a network operation that inherits D2 and D3, so a
   corpus can be built on stale or partly failed data and report nothing.
2. The cache is refreshed incrementally, so different bars in one ticker's
   parquet can carry different adjustment vintages. That produces discontinuities
   which become fake returns and therefore fake labels. The
   `unreconcilable ... factor 1.2417` warnings in the run logs are this drift
   showing up in outcome grading; the same drift sits under the corpus.

Fix: a **frozen research vintage**. Fetch deep history once, write it to a dated
immutable directory, and never refresh it. The corpus builder reads only from a
named vintage and makes no network calls. Same vintage plus same code equals the
same numbers forever, which is what makes any of this publishable and what the
evidence integrity audit was already asking for.

## B6  Survivorship bias must be printed, not just documented

The universe is built from current listings, so names that delisted are absent
and the corpus is biased upward. This does not go away with more dates. It is
noted in the module docstring today; it must appear in the printed result
wherever an IC is shown, and in any customer facing surface.

---

## What "working well" means

Not "it ran". The acceptance bar:

1. Two builds from the same frozen vintage produce byte identical corpora.
2. The corpus reports its own shape before any model runs: number of dates,
   names per date, label horizon, vintage id, and the count of rows dropped by
   the embargo.
3. Forty or more test dates survive the embargo.
4. Three arms reported on identical dates: mean IC, IC t statistic, n, and the
   long minus short spread for each.
5. Every result block prints the survivorship caveat and the vintage id.
6. A deliberately shuffled label produces mean IC near zero. If a randomised
   target still scores, the harness is broken and every other number is void.

### Calibrate your expectations before you look

A real cross sectional equity signal over a 20 day horizon lands around **0.02
to 0.05 mean IC**, and it is respectable when the t statistic clears 2 over a
decent number of dates. A long minus short spread of a few tenths of a percent
per rebalance is a genuine result.

**A mean IC of 0.15 is not alpha, it is a bug.** If the first run prints
something spectacular, the leak is still in there. Treat a great number as a
failing test until item 6 above passes.

---

## The prompt

```
Read docs/SYSTEM_MAP.md section 13, docs/DEBUG_BRIEF.md D10, and
docs/PROMPT_M1_ML_SCAN.md before doing anything.

Work item M1: make the ML scan trustworthy. Scope is ml/meta_features.py,
ml/meta_model.py and data/price_cache.py only. Do not touch the stage engine,
the gates, top_picks.py, or anything to do with execution.

Six defects are described in the M1 doc: no embargo in the walk forward,
min_train counting rows instead of dates, the ML track being a stacker without
saying so, too few reachable test dates, a corpus that changes when rebuilt,
and survivorship bias that is documented but never printed.

Before writing any code:
1. Confirm or refute each of the six by reading the code, and quote the lines.
   If you think one of them is wrong, say so — I would rather be corrected now.
2. Propose the frozen research vintage: where it lives, how it is named, how the
   builder is pointed at one, and what stops anything from refreshing it.
3. Propose the embargo implementation and tell me exactly how many test dates
   survive it at the settings you recommend.
4. Tell me how you will implement the shuffled label check from the acceptance
   bar, since that is the test that proves the harness itself.

Do not implement until I approve the plan. When you do implement, do it in this
order: frozen vintage first, then the embargo and min_train_dates, then the
three arms, then the printed caveats. Each step is a separate commit that leaves
the repo runnable.
```

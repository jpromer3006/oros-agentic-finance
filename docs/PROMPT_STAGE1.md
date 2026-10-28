# S1 — fix the Stage 1 surfaces

Two defects pulling in opposite directions: the Basing classifier is too loose
and admits extended names, and the Transition Watch is too strict to ever fire.

Paste the block at the bottom into Claude Code from the repo root.

## Evidence

**Too loose.** `ml/stage_analyzer.py:598`

```python
if slope < STAGE2_MIN_SLOPE_PCT and approach < -0.01 and pct_above > 0:
    exp.append("◯ Price above a flat MA that FELL into place → Stage 1 repair base")
    return 1, "Basing", 0.6, exp
```

`pct_above > 0` has no upper bound, so any price above a flat MA that declined
into place is called a repair base at 1% above or at 50% above. Observed live:
ICLR at **+20.1% above the MA**, slope -1.8%, rendered in the Basing panel whose
own caption reads "sideways price around a flat 30-week MA". `STAGE1_MAX_PRICE_DEVIATION = 0.05`
already exists in the file and is applied in the Stage 3 test, but not here.
The 2026-09-03 breadth count of 193 Basing is inflated by names that are not bases.

**Too strict.** `ml/transition_watch.py` requires four independent signals to
fire simultaneously on a Stage 4 name:

```
RALLY_MIN_PCT        = 0.25   # 25% off the 90 day low
ABOVE_50D_MA_MIN_PCT = 0.05   # 5% above the 50 day MA
VOL_MIN_RATIO        = 1.2    # 5 day avg vs 50 day baseline
MOMENTUM_MIN_PCT     = 0.10   # vs the close 20 sessions ago
```

Four ANDs over a pool of 65 gives an expected count well under one on a normal
day, and the panel has been showing (0). Worse, a name that clears all four has
usually stopped being Stage 4, so it leaves the pool that feeds the panel. The
detector is structurally self defeating.

Both are the same disease as the pick funnel: hard conjunctions with no
near-miss reporting, so a silent zero is indistinguishable from a broken filter.

## Note on running scans

The Yahoo feed is rate limited (HTTP 429). Run scans off the cache with
`--light` and do not trigger full refreshes while validating.

---

## The prompt

```
Read docs/PROMPT_STAGE1.md before doing anything.

Work item S1: fix the two Stage 1 surfaces. Scope is ml/stage_analyzer.py,
ml/transition_watch.py and ui/components/trader_mode.py only.

HARD RULES
1. Do NOT touch the Stage 2 promotion logic, the buy gates, top_picks.py or
   entry_gates.py. Nothing in this change may create a new Stage 2 promotion or
   a new buy signal. If a fix seems to require that, stop and tell me.
2. The data feed is rate limited right now. Validate with scans run off the
   cache (--light). Do not run a full price refresh.
3. Stop and report at each STOP marker.

TASK 1  Bound the repair base branch
stage_analyzer.py:598 returns Stage 1 Basing for any price above a flat MA that
fell into place, with no cap on how far above. Bound it by
STAGE1_MAX_PRICE_DEVIATION so a base has to look like a base.

The names this evicts still need an honest home. They are price above a flat or
falling MA, materially extended, MA not yet rising. Do NOT promote them to
Stage 2. Propose where they go: a sub-type on the Stage 1 result, a distinct
bucket, or something else. Show me the options with the tradeoffs before coding.

Then tell me, from a cached scan of the OROS 500, how many names move and which
ones. I want the before and after Basing count journaled, not absorbed.
STOP.

TASK 2  Make Transition Watch score instead of gate
Replace the four hard ANDs with a score over the same four signals. Keep 4 of 4
as the bar for a confirmed candidate, but the panel must ALWAYS show the closest
names, with which signals fired, which missed, and by how much.

This mirrors the near-miss principle I want everywhere: a panel that renders
"nothing today" teaches the user nothing and is indistinguishable from a broken
filter. "Nothing clears the bar, here are the three closest and why they miss"
is the correct empty state.

Do not loosen the four thresholds to make candidates appear. The thresholds stay;
the presentation changes.
STOP.

TASK 3  Fix the empty state copy in trader_mode.py
Both Stage 1 panels currently say a variant of "none right now". Once Task 2
lands, the Transition Watch empty state should show the near-miss list. Make the
Basing panel's caption match what the bounded classifier actually admits.
STOP.

VERIFY
Run a cached scan of the OROS 500 and report:
  a. Basing count before and after Task 1, and the names that moved
  b. ICLR specifically: what stage does it get now, and why
  c. the Transition Watch panel with its near-miss list populated
  d. that Stage 2 counts and the confirmed buy list are UNCHANGED, which proves
     rule 1 held
STOP.

One commit per task, each leaving the repo runnable, ending with the co-author
trailer this repo already uses.
```

---

## Separate, ask before starting: the panel that does not exist

Nothing in OROS watches **Stage 1 to Stage 2**, the base to breakout moment,
which is the core of the method and the only moment Weinstein actually buys.
Transition Watch covers Stage 4 repairing. The Basing panel is a static list
ranked by bull probability. Neither answers "which of my 193 basing names is
closest to breaking out".

A proper Stage 1 to 2 proximity watch would rank by distance to the base's
resistance, whether the 30 week MA slope is turning, and whether volume is
building in the base. That is the highest value panel a Weinstein user could
have, and it is also the front half of the fix for the zero-picks problem: by
the time a name clears the Stage 2 gates it is usually already extended, so the
watchlist has to be built before the breakout, not after.

Do not bundle this with S1. Scope it separately.

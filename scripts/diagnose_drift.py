"""diagnose_drift.py - Does the journaled entry still match the cached close
on the proposal date? If the cache has been re-adjusted (dividends/splits)
since the proposal was written, every past stop test is run against a
different price series than the one that produced the entry."""
from __future__ import annotations
import json, glob
from pathlib import Path
from statistics import mean
from data import price_cache

rows = []
BAD = []
for p in sorted(glob.glob("data/journal/portfolio_*.json")):
    try:
        r = json.loads(Path(p).read_text())
    except Exception:
        BAD.append(p); continue
    d = r.get("date")
    for h in r.get("holdings") or []:
        if not h.get("outcome_final"):
            continue
        df = price_cache.get_history(h["ticker"])
        if df is None or "Close" not in df.columns:
            continue
        sl = df.loc[:d]
        if sl.empty:
            continue
        cached = float(sl["Close"].iloc[-1])
        entry = float(h.get("entry") or 0)
        if entry <= 0 or cached <= 0:
            continue
        rows.append({"t": h["ticker"], "date": d, "entry": entry,
                     "cached_close": cached, "drift_pct": (cached/entry - 1)*100,
                     "exit": h.get("outcome_exit"), "ret": h.get("outcome_return"),
                     "mandate": r.get("mandate")})

print(f"CORRUPT journal files skipped: {len(BAD)} {BAD}")
print(f"positions compared: {len(rows)}")
dr = [x["drift_pct"] for x in rows]
print(f"drift entry -> cached close on the SAME date:")
print(f"  mean {mean(dr):+.3f}%   min {min(dr):+.2f}%   max {max(dr):+.2f}%")
neg = [x for x in dr if x < -0.5]
pos_ = [x for x in dr if x > 0.5]
zero = [x for x in dr if abs(x) <= 0.5]
print(f"  cached LOWER than journaled entry by >0.5%: {len(neg)} ({100*len(neg)/len(dr):.0f}%)")
print(f"  within +-0.5%:                              {len(zero)} ({100*len(zero)/len(dr):.0f}%)")
print(f"  cached HIGHER by >0.5%:                     {len(pos_)} ({100*len(pos_)/len(dr):.0f}%)")

print("\nworst 12 drifts:")
for x in sorted(rows, key=lambda z: z["drift_pct"])[:12]:
    print(f"  {x['t']:<7}{x['date']}  entry {x['entry']:>9.2f}  cached {x['cached_close']:>9.2f}"
          f"  drift {x['drift_pct']:>7.2f}%  exit={x['exit']}  ret={x['ret']}")

print("\ndrift by mandate:")
from collections import defaultdict
g = defaultdict(list)
for x in rows: g[x["mandate"]].append(x["drift_pct"])
for m, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
    print(f"  {m:<16} n={len(v):<5} mean drift {mean(v):+.3f}%")

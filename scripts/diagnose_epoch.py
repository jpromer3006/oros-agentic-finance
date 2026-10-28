"""Did the 2026-07-06 risk-gate fix change the engine? Split the scoreboard."""
from __future__ import annotations
import json, glob
from pathlib import Path
from collections import defaultdict
from statistics import mean, median

CUT = "2026-07-06"
rows=[]
for p in sorted(glob.glob("data/journal/portfolio_*.json")):
    try: r=json.loads(Path(p).read_text())
    except Exception: continue
    for h in r.get("holdings") or []:
        e,s=h.get("entry"),h.get("stop")
        if not e or not s or e<=0: continue
        rows.append({"date":r["date"],"m":r.get("mandate"),"t":h["ticker"],
                     "sd":(e-s)/e*100,"fin":bool(h.get("outcome_final")),
                     "ret":h.get("outcome_return"),"exit":h.get("outcome_exit")})

def show(label, rs):
    sd=[x["sd"] for x in rs]
    fin=[x for x in rs if x["fin"] and x["ret"] is not None]
    r=[x["ret"] for x in fin]
    stops=sum(1 for x in fin if x["exit"]=="stop")
    tight=sum(1 for x in sd if x<3.0)
    print(f"\n{label}")
    print(f"  positions {len(rs)}  | stop distance: median {median(sd):.2f}%  min {min(sd):.2f}%  "
          f"under the 3% floor: {tight} ({100*tight/len(sd):.0f}%)")
    if r:
        w=[x for x in r if x>0]; l=[x for x in r if x<=0]
        hit=len(w)/len(r); aw=mean(w) if w else 0; al=mean(l) if l else 0
        print(f"  scored {len(r)}  hit {100*hit:.1f}%  avgW {100*aw:+.2f}%  avgL {100*al:+.2f}%  "
              f"EXPECTANCY {100*(hit*aw+(1-hit)*al):+.2f}%  stop-exits {100*stops/len(r):.0f}%")
    else:
        print("  scored 0")

print("="*78); print(f"BEFORE vs AFTER the risk-gate fix ({CUT})"); print("="*78)
show("ALL TIME (what the throttle reads today)", rows)
show(f"PRE-FIX  (date <  {CUT})", [x for x in rows if x["date"]<CUT])
show(f"POST-FIX (date >= {CUT})", [x for x in rows if x["date"]>=CUT])

print("\nper mandate, POST-FIX only:")
g=defaultdict(list)
for x in rows:
    if x["date"]>=CUT: g[x["m"]].append(x)
for m,rs in sorted(g.items(), key=lambda kv:-len(kv[1])): show(f"  [{m}]", rs)

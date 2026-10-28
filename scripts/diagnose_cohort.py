"""THE test: is the scoreboard's 'FINAL outcomes only' filter survivorship-biased?

A position becomes final EITHER by hitting its stop (possible on day 1)
OR by reaching its horizon (requires the full N trading days to elapse).
In a journal younger than the horizon, only the stop path can complete.
So the 'honest ruler' can only contain losers until the journal matures.

Fix: restrict to the MATURE COHORT - proposals whose horizon has fully
elapsed. Inside that cohort both exits are possible and the sample is fair.
"""
from __future__ import annotations
import json, glob
from pathlib import Path
from collections import defaultdict
from statistics import mean
from data import price_cache

HZ={"fast_momentum":5,"swing_momentum":20,"growth_hold":60,"value_hold":120}
spy=price_cache.get_history("SPY")
LAST=len(spy)-1

def bars_since(d):
    try:
        sl=spy.loc[:d]
        return LAST-(len(sl)-1)
    except Exception: return -1

rows=[]
for p in sorted(glob.glob("data/journal/portfolio_*.json")):
    try: r=json.loads(Path(p).read_text())
    except Exception: continue
    m=r.get("mandate"); d=r.get("date"); h=HZ.get(m,20)
    for x in r.get("holdings") or []:
        rows.append({"m":m,"d":d,"t":x["ticker"],"h":h,"elapsed":bars_since(d),
                     "fin":bool(x.get("outcome_final")),"ret":x.get("outcome_return"),
                     "exit":x.get("outcome_exit")})

def stats(rs):
    f=[x for x in rs if x["fin"] and x["ret"] is not None]
    if not f: return None
    r=[x["ret"] for x in f]; w=[y for y in r if y>0]; l=[y for y in r if y<=0]
    hit=len(w)/len(r); aw=mean(w) if w else 0.0; al=mean(l) if l else 0.0
    st=sum(1 for x in f if x["exit"]=="stop")
    return dict(n=len(r),hit=100*hit,aw=100*aw,al=100*al,
                exp=100*(hit*aw+(1-hit)*al),stop=100*st/len(r))

def line(lbl,s):
    if not s: print(f"  {lbl:<46} n=0"); return
    print(f"  {lbl:<46} n={s['n']:<4} exp {s['exp']:+6.2f}%  hit {s['hit']:5.1f}%  "
          f"avgW {s['aw']:+5.2f}%  avgL {s['al']:+6.2f}%  stop-exits {s['stop']:5.1f}%")

print("="*104)
print("SURVIVORSHIP TEST: all finalized positions vs the MATURE COHORT")
print("="*104)
by=defaultdict(list)
for x in rows: by[x["m"]].append(x)
for m,rs in sorted(by.items(), key=lambda kv:-len(kv[1])):
    h=HZ.get(m,20)
    mature=[x for x in rs if x["elapsed"]>=h]
    imm=[x for x in rs if x["elapsed"]<h]
    print(f"\n{m}  (horizon {h} trading days)")
    print(f"  proposals rows {len(rs)} | horizon fully elapsed for {len(mature)} "
          f"| still inside the window {len(imm)}")
    line("(a) ALL finalized  [current scoreboard]", stats(rs))
    line("(b) MATURE cohort  [unbiased]", stats(mature))
    line("(c) IMMATURE only  [can ONLY finalize by stop]", stats(imm))
print("\n"+"="*104)

"""Why does swing_momentum exit at the stop 196 times out of 196?"""
from __future__ import annotations
import json, glob, datetime as dt
from pathlib import Path
from collections import defaultdict, Counter
from statistics import mean
from data import price_cache

HZ = {"fast_momentum":5,"swing_momentum":20,"growth_hold":60,"value_hold":120}
recs=[]
for p in sorted(glob.glob("data/journal/portfolio_*.json")):
    try: recs.append((p, json.loads(Path(p).read_text())))
    except Exception: pass

# 1) date coverage per mandate
bym=defaultdict(list)
for p,r in recs: bym[r.get("mandate")].append(r.get("date"))
print("[A] proposal DATE RANGE per mandate")
for m,ds in sorted(bym.items(), key=lambda kv:-len(kv[1])):
    ds=sorted(ds); print(f"  {m:<16} n={len(ds):<4} {ds[0]} .. {ds[-1]}  distinct={len(set(ds))}")

# 2) SPY over each window, to see if a mandate simply lived in a bad tape
spy = price_cache.get_history("SPY")
def spy_fwd(d, h):
    try:
        sl=spy.loc[:d]; pos=len(sl)-1; end=min(pos+h, len(spy)-1)
        if end<=pos: return None
        c=spy["Close"]; return float(c.iloc[end]/c.iloc[pos]-1)*100
    except Exception: return None

print("\n[B] mandate windows vs SPY forward return over the same horizon")
for m,ds in sorted(bym.items(), key=lambda kv:-len(kv[1])):
    v=[spy_fwd(d,HZ.get(m,20)) for d in ds]; v=[x for x in v if x is not None]
    if v: print(f"  {m:<16} SPY fwd {HZ.get(m,20)}d: mean {mean(v):+.2f}%  min {min(v):+.2f}%  max {max(v):+.2f}%")

# 3) per-position forensic on swing_momentum
print("\n[C] swing_momentum forensics (first 14 final positions)")
print(f"  {'TKR':<7}{'DATE':<12}{'ENTRY':>9}{'STOP':>9}{'STOP%':>7}{'MINCLOSE':>10}{'DAY':>5}{'MAXCLOSE':>10}{'RET':>8}")
n=0; below_at_day1=0; tot=0; stopdist=[]
for p,r in recs:
    if r.get("mandate")!="swing_momentum": continue
    d=r.get("date"); h20=20
    for hh in r.get("holdings") or []:
        if not hh.get("outcome_final"): continue
        df=price_cache.get_history(hh["ticker"])
        if df is None: continue
        sl=df.loc[:d]
        if sl.empty: continue
        pos=len(sl)-1; end=min(pos+h20, len(df)-1)
        if end<=pos: continue
        c=df["Close"]; e=float(hh["entry"]); s=float(hh["stop"])
        win=[float(c.iloc[i]) for i in range(pos+1,end+1)]
        if not win: continue
        tot+=1; stopdist.append((e-s)/e*100)
        if win[0]<=s: below_at_day1+=1
        if n<14:
            mn=min(win); mi=win.index(mn)+1
            print(f"  {hh['ticker']:<7}{d:<12}{e:>9.2f}{s:>9.2f}{(e-s)/e*100:>6.1f}%{mn:>10.2f}{mi:>5}{max(win):>10.2f}{100*hh['outcome_return']:>7.1f}%")
            n+=1
print(f"\n  swing positions examined: {tot}")
print(f"  ALREADY below the stop on the FIRST forward close: {below_at_day1} ({100*below_at_day1/max(tot,1):.0f}%)")
print(f"  mean planned stop distance: {mean(stopdist):.2f}%")

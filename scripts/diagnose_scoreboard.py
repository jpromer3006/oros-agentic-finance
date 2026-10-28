"""
diagnose_scoreboard.py - Is the forward scoreboard measuring the strategy,
or measuring the ruler?

compare_by_mandate() pools every (proposal, holding) pair with no
deduplication. OROS proposes daily and re-proposes the same names, and some
days carry several runs. This asks how many INDEPENDENT trades are really
behind the headline expectancy, and recomputes it three ways.

    PYTHONPATH=. python3 scripts/diagnose_scoreboard.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

J = Path(__file__).resolve().parent.parent / "data" / "journal"


def load_all():
    rows, per_file = [], []
    for p in sorted(J.glob("portfolio_*.json")):
        try:
            r = json.loads(p.read_text())
        except Exception:
            continue
        m = r.get("mandate", "?")
        d = r.get("date", "?")
        per_file.append((p.name, d, m, len(r.get("holdings") or [])))
        for h in r.get("holdings") or []:
            if h.get("outcome_final") and h.get("outcome_return") is not None:
                rows.append({
                    "file": p.name, "date": d, "mandate": m,
                    "ticker": h["ticker"],
                    "ret": float(h["outcome_return"]),
                    "exit": h.get("outcome_exit"),
                    "days": h.get("outcome_days"),
                    "entry": h.get("entry"), "stop": h.get("stop"),
                })
    return rows, per_file


def expectancy(rets):
    if not rets:
        return None, None, None, None
    w = [x for x in rets if x > 0]
    l = [x for x in rets if x <= 0]
    hit = len(w) / len(rets)
    aw = mean(w) if w else 0.0
    al = mean(l) if l else 0.0
    return hit * aw + (1 - hit) * al, hit, aw, al


def report(label, rets, exits=None):
    e, hit, aw, al = expectancy(rets)
    if e is None:
        print(f"  {label:<34} n=0")
        return
    line = (f"  {label:<34} n={len(rets):<5} "
            f"expectancy {100*e:+6.2f}%  hit {100*hit:5.1f}%  "
            f"avgW {100*aw:+6.2f}%  avgL {100*al:+6.2f}%")
    if exits:
        c = Counter(exits)
        line += f"   exits {dict(c)}"
    print(line)


def main():
    rows, per_file = load_all()
    print("=" * 78)
    print("OROS SCOREBOARD DIAGNOSTIC")
    print("=" * 78)

    # --- 1. How many proposals per calendar date? ---------------------------
    by_date = Counter(d for _, d, _, _ in per_file)
    multi = {d: n for d, n in by_date.items() if n > 1}
    print(f"\n[1] Proposal files: {len(per_file)} across {len(by_date)} distinct dates")
    print(f"    Dates with MORE THAN ONE proposal: {len(multi)}")
    if multi:
        top = sorted(multi.items(), key=lambda kv: -kv[1])[:8]
        print(f"    worst: {top}")
        dup_rows = sum(n - 1 for n in multi.values())
        print(f"    -> {dup_rows} redundant proposal files inflate every aggregate")

    # --- 2. Per mandate: pooled vs deduplicated ----------------------------
    by_mandate = defaultdict(list)
    for r in rows:
        by_mandate[r["mandate"]].append(r)

    for m, rs in sorted(by_mandate.items(), key=lambda kv: -len(kv[1])):
        print(f"\n[2] MANDATE: {m}")
        tick = Counter(r["ticker"] for r in rs)
        print(f"    scored rows {len(rs)} | unique tickers {len(tick)} | "
              f"rows per ticker avg {len(rs)/max(len(tick),1):.1f} "
              f"max {max(tick.values()) if tick else 0}")
        if tick:
            print(f"    most repeated: {tick.most_common(6)}")

        # (a) pooled, exactly what compare_by_mandate reports today
        report("(a) pooled  [current ruler]", [r["ret"] for r in rs],
               [r["exit"] for r in rs])

        # (b) one row per (ticker, date) - collapses same-day duplicate runs
        seen, ded = set(), []
        for r in sorted(rs, key=lambda x: (x["date"], x["file"])):
            k = (r["ticker"], r["date"])
            if k in seen:
                continue
            seen.add(k)
            ded.append(r)
        report("(b) dedup same-day reruns", [r["ret"] for r in ded],
               [r["exit"] for r in ded])

        # (c) one row per ticker EPISODE: first appearance, then ignore any
        #     re-proposal until the prior trade would have closed.
        eps = []
        last_close_date = {}
        for r in sorted(ded, key=lambda x: (x["ticker"], x["date"])):
            t = r["ticker"]
            if t in last_close_date and r["date"] <= last_close_date[t]:
                continue          # still inside the previous trade's window
            eps.append(r)
            last_close_date[t] = r["date"]   # conservative: block re-entry same day
        # block by actual holding length
        eps2, block = [], {}
        import datetime as dt
        for r in sorted(ded, key=lambda x: (x["ticker"], x["date"])):
            t = r["ticker"]
            d = dt.date.fromisoformat(r["date"])
            if t in block and d < block[t]:
                continue
            eps2.append(r)
            block[t] = d + dt.timedelta(days=int(1.4 * (r["days"] or 20)))
        report("(c) one row per trade EPISODE", [r["ret"] for r in eps2],
               [r["exit"] for r in eps2])

        # (d) holding-period truncation check
        hz = Counter(r["exit"] for r in rs)
        horiz = [r["ret"] for r in rs if r["exit"] == "horizon"]
        stops = [r["ret"] for r in rs if r["exit"] == "stop"]
        print(f"    exit mix: {dict(hz)}")
        if horiz:
            print(f"    horizon exits: n={len(horiz)} avg {100*mean(horiz):+.2f}% "
                  f"(winners are CUT here)")
        if stops:
            print(f"    stop exits:    n={len(stops)} avg {100*mean(stops):+.2f}% "
                  f"(losers run to the stop)")
        # theoretical stop loss if every stop were hit exactly
        planned = [(r["entry"] - r["stop"]) / r["entry"]
                   for r in rs if r.get("entry") and r.get("stop")]
        if planned and stops:
            print(f"    planned risk per trade avg {-100*mean(planned):+.2f}% vs "
                  f"realized stop exit {100*mean(stops):+.2f}%  "
                  f"(gap = gap-down slippage charged by the grader)")

    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()

"""
picks_ledger.py - Top Picks get memory (JP, 2026-07-14).

The morning show proposes; the evening show grades. This module is the
receipt book between the two:

  record_picks(picks)   - morning: journal today's Top Picks (idempotent
                          per date; a re-run replaces the day's entry).
  grade(date)           - evening: for each of that day's picks, did price
                          push up through the buy-stop (day high >= trigger)?
                          If triggered, where did it close vs the trigger?
  record_day_tally(...) - evening: who won the day (live book vs frozen
                          book vs SPY) plus the running record.

Verdicts (plain language on purpose):
  not_triggered   - the entry trigger was never hit: no trade, no loss.
  triggered_up    - entered on proof and closed above the trigger.
  triggered_down  - entered on proof, closed below; the stop is the plan.
  home_run        - a home-run-flagged pick that triggered and closed
                    >= +1% above the trigger. Celebrate honestly.

Journals: data/journal/picks_ledger.json, data/journal/day_tally.json.
Educational, not financial advice. OROS proposes and journals only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_J = Path(__file__).resolve().parent.parent / "data" / "journal"
_PICKS = _J / "picks_ledger.json"
_TALLY = _J / "day_tally.json"

_HOME_RUN_CLOSE_PCT = 1.0     # close >= +1% above trigger to call it on air


class JournalCorruption(RuntimeError):
    """An existing journal could not be read, or a write would lose rows.

    Raised instead of silently starting over. On 2026-09-15 a git merge left
    conflict markers in these files; the old loader swallowed the parse error,
    returned an empty ledger, and the next evening run wrote that emptiness
    over roughly six weeks of track record. An append-only journal that can be
    silently reinitialised is not append-only. Fail loudly instead.
    """


def _load(path: Path) -> dict:
    if path.exists():
        raw = path.read_text()
        try:
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
            quarantine = path.with_name(f"{path.name}.corrupt-{stamp}")
            quarantine.write_text(raw)
            raise JournalCorruption(
                f"{path.name} exists but does not parse ({exc}). "
                f"The unreadable file was preserved at {quarantine.name}. "
                "Refusing to continue, because writing now would erase the "
                "track record. Repair the journal, then re-run."
            ) from exc
    return {"entries": []}


def _save(path: Path, obj: dict) -> None:
    _J.mkdir(parents=True, exist_ok=True)
    new_n = len(obj.get("entries", []))
    if path.exists():
        try:
            old_n = len(json.loads(path.read_text()).get("entries", []))
        except Exception as exc:  # noqa: BLE001
            raise JournalCorruption(
                f"refusing to overwrite unreadable {path.name} ({exc})."
            ) from exc
        if new_n < old_n:
            raise JournalCorruption(
                f"refusing to shrink {path.name}: {old_n} entries on disk, "
                f"{new_n} about to be written. An append-only journal never "
                "loses rows. If this is an intentional repair, edit the file "
                "directly and record why."
            )
    path.write_text(json.dumps(obj, indent=1))


def record_picks(picks: list[dict], date: str | None = None) -> dict:
    """Journal the morning's picks. Keeps only broadcast-relevant fields."""
    date = date or f"{datetime.now():%Y-%m-%d}"
    entry = {"date": date, "picks": []}
    for p in picks or []:
        try:
            entry["picks"].append({
                "ticker": p["ticker"],
                "buy_stop": float(p["buy_stop"]),
                "stop_loss": float(p.get("stop_loss") or 0),
                "target": float(p.get("target") or 0),
                "is_etf": bool(p.get("is_etf")),
                "home_run_flag": bool(
                    p.get("setup") == "fresh"
                    and float(p.get("risk_reward") or 0) >= 3.0
                    and float(p.get("volume_surge") or 0) >= 2.0
                    and float(p.get("mansfield_rs") or 0) > 0),
            })
        except Exception:  # noqa: BLE001
            continue
    led = _load(_PICKS)
    entries = led["entries"]
    if entries and entries[-1].get("date") == date:
        entries[-1] = entry
    else:
        entries.append(entry)
    _save(_PICKS, led)
    logger.info("picks ledger: %d pick(s) journaled for %s",
                len(entry["picks"]), date)
    return entry


def grade(date: str | None = None) -> list[dict]:
    """Grade that date's picks off the daily bar (call after the close)."""
    import pandas as pd
    from data import price_cache

    date = date or f"{datetime.now():%Y-%m-%d}"
    led = _load(_PICKS)
    entry = next((e for e in reversed(led["entries"])
                  if e.get("date") == date), None)
    if not entry:
        return []
    out = []
    for p in entry["picks"]:
        v = dict(p, verdict="ungraded", day_high=None, close=None,
                 vs_trigger_pct=None)
        try:
            df = price_cache.get_history(p["ticker"])
            idx = pd.to_datetime(df.index)
            try:
                idx = idx.tz_localize(None)
            except TypeError:
                pass
            mask = idx.normalize() == pd.Timestamp(date)
            bar = df.loc[mask]
            if not len(bar):                 # market holiday / stale cache
                out.append(v)
                continue
            hi = float(bar["High"].iloc[-1]) if "High" in bar else float(bar["Close"].iloc[-1])
            cl = float(bar["Close"].iloc[-1])
            v["day_high"], v["close"] = hi, cl
            if hi < p["buy_stop"]:
                v["verdict"] = "not_triggered"
            else:
                v["vs_trigger_pct"] = 100 * (cl / p["buy_stop"] - 1)
                if p["home_run_flag"] and v["vs_trigger_pct"] >= _HOME_RUN_CLOSE_PCT:
                    v["verdict"] = "home_run"
                elif cl >= p["buy_stop"]:
                    v["verdict"] = "triggered_up"
                else:
                    v["verdict"] = "triggered_down"
        except Exception as e:  # noqa: BLE001
            logger.warning("grading %s failed: %s", p["ticker"], e)
        out.append(v)
    return out


def record_day_tally(live_pct: float | None, frozen_pct: float | None,
                     spy_pct: float | None, date: str | None = None) -> dict:
    """Journal the day's three returns; return the running record."""
    date = date or f"{datetime.now():%Y-%m-%d}"
    entry = {"date": date, "live_pct": live_pct, "frozen_pct": frozen_pct,
             "spy_pct": spy_pct}
    tal = _load(_TALLY)
    entries = tal["entries"]
    if entries and entries[-1].get("date") == date:
        entries[-1] = entry
    else:
        entries.append(entry)
    _save(_TALLY, tal)
    return running_record()


def running_record() -> dict:
    """Wins/losses of the live book vs frozen and vs SPY, plus today."""
    tal = _load(_TALLY)
    rec = {"days": len(tal["entries"]),
           "vs_frozen": {"wins": 0, "losses": 0, "ties": 0},
           "vs_spy": {"wins": 0, "losses": 0, "ties": 0},
           "today": tal["entries"][-1] if tal["entries"] else None}

    def _score(a, b, key):
        if a is None or b is None:
            return
        d = a - b
        bucket = "wins" if d > 0.005 else ("losses" if d < -0.005 else "ties")
        rec[key][bucket] += 1

    for e in tal["entries"]:
        _score(e.get("live_pct"), e.get("frozen_pct"), "vs_frozen")
        _score(e.get("live_pct"), e.get("spy_pct"), "vs_spy")
    return rec


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(json.dumps(grade(), indent=1))
    print(json.dumps(running_record(), indent=1))

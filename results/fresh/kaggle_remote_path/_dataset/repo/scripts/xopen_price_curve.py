"""xopen: leader sale-price path by day (stored data only, one process, no games). Thread xopen, 2026-09-25.

For every product and actual day d (offset-corrected: market index i holds day i+1, index 0 holds days 0 AND 1, which
are both given index 0's price) the median over the 540 corpus games (data/leader_semantics) of that game's average
sale price that day, divided by the base price; days without sales are filled from the nearest day with data, then
the path is 3-day smoothed. The EV failsafe of the exact follower (scripts/xopen_follow.py, B7 of the design review)
prices deferred production on this path instead of one constant price.

usage: .venv/Scripts/python.exe scripts/xopen_price_curve.py
writes results/fresh/xopen_20260925/price_curve.json  {"curve": {product: [30 ratios]}, "n": {product: [30 counts]}}
"""
import gzip
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEM = ROOT / "data/leader_semantics"
OUT = ROOT / "results/fresh/xopen_20260925/price_curve.json"
BASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250, "EGG": 50, "MILK": 160,
        "WOOL": 200, "FERTILIZER": 100}


def main():
    per = {p: [[] for _ in range(30)] for p in BASE}
    n_games = 0
    for f in sorted(SEM.glob("*/*.json.gz")):
        g = json.load(gzip.open(f, "rt", encoding="utf-8"))
        n_games += 1
        days = g["days"]
        for i, day in enumerate(days):
            m = day["market"]
            actual = [0, 1] if i == 0 else [i + 1]
            for p, u in m["sold_units"].items():
                if p not in BASE or not u:
                    continue
                price = float(m["sold_revenue"].get(p, 0)) / u
                for d in actual:
                    if d < 30:
                        per[p][d].append(price / BASE[p])
    curve, counts = {}, {}
    for p in BASE:
        med = [st.median(x) if x else None for x in per[p]]
        have = [d for d in range(30) if med[d] is not None]
        filled = []
        for d in range(30):
            if med[d] is not None:
                filled.append(med[d])
            elif have:
                near = min(have, key=lambda k: (abs(k - d), k))
                filled.append(med[near])
            else:
                filled.append(1.0)
        sm = [sum(filled[max(0, d - 1):d + 2]) / len(filled[max(0, d - 1):d + 2]) for d in range(30)]
        curve[p] = [round(v, 4) for v in sm]
        counts[p] = [len(x) for x in per[p]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(curve=curve, n=counts, games=n_games, source="data/leader_semantics median sale "
                                   "price / base by actual day, gap-filled, 3-day smoothed")), encoding="utf-8")
    print("games", n_games)
    for p in BASE:
        print("%-11s %s" % (p, " ".join("%.2f" % v for v in curve[p][::3])))


if __name__ == "__main__":
    main()

"""Why are our melons sold late? Exact replay of a finished harness game; per melon tile: ripe at the dawn of the harvest
day (units, distance from the shed), who harvested it and when, when the units reached the shed and were sold; plus the
units the executor had available at hours 0-1 of that day (farmer + hands hired at hour 0 act from hour 1).

usage: melon_day_trace_20260929.py --game <result.json> [--day 10]"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]


def dist_shed(i):
    x, y = i % 10, i // 10
    return min(abs(x - a) + abs(y - b) for a, b in SHED)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--day", type=int, default=10)
    a = ap.parse_args()
    r = json.load(open(ROOT / a.game))
    acts = json.load(open(ROOT / a.game.replace(".json", ".actions.json")))
    seat = r["case"]["seat"]
    w = UE.World(r["case"]["seed"], r["shops"])
    harvests, sales, places = [], [], []
    o_apply, o_commit = E._apply_unit_action, E._commit_unit

    def apply(farm, private, idx, action, *x, **k):
        mine = farm is w.farms[seat]
        before = None
        if mine and isinstance(action, list) and action and action[0] == "HARVEST":
            u = farm["farmer"] if idx == 0 else (farm["hands"][idx - 1] if idx - 1 < len(farm["hands"]) else None)
            pos = tuple(u[:2]) if isinstance(u, (list, tuple)) and len(u) >= 2 else None
            if pos:
                t = farm["tiles"][pos[1]][pos[0]]
                if isinstance(t, dict) and t.get("crop") == "MELON":
                    before = (pos[1] * 10 + pos[0], int(t.get("yield_units", 0) or 0))
        res = o_apply(farm, private, idx, action, *x, **k)
        if before:
            harvests.append((w.t, idx, before[0], before[1]))
        if mine and isinstance(action, list) and action[:2] == ["PLACE", "MELON"]:
            places.append((w.t, idx))
        return res

    def commit(op, item, price, farm, private, market, *x, **k):
        res = o_commit(op, item, price, farm, private, market, *x, **k)
        if res and op == "SELL" and item == "MELON":
            sales.append((w.t, 0 if farm is w.farms[0] else 1, float(price)))
        return res
    E._apply_unit_action, E._commit_unit = apply, commit
    ripe = None
    hands_d = None
    try:
        while w.t < min(719, 24 * (a.day + 3)):
            if w.t == 24 * a.day:
                farm = w.farms[seat]
                ripe = {}
                for y, row in enumerate(farm["tiles"]):
                    for x, t in enumerate(row):
                        if isinstance(t, dict) and t.get("crop") == "MELON":
                            ripe[y * 10 + x] = (a.day - int(t.get("planted_day", a.day)), int(t.get("yield_units", 0) or 0))
            if w.t == 24 * a.day + 2:
                hands_d = len(w.farms[seat]["hands"])
            w.step([UE.tape_action(acts[i], w.t) for i in (0, 1)])
    finally:
        E._apply_unit_action, E._commit_unit = o_apply, o_commit
    print(f"{a.game}: our seat {seat}, margin {r['margin']:+.0f}; hands on the board at hour 2 of day {a.day}: {hands_d}")
    print(f"melon tiles at dawn of day {a.day} (tile: age, units, steps from the shed):")
    print("   " + ", ".join(f"{i}: a{ag} u{u} d{dist_shed(i)}" for i, (ag, u) in sorted(ripe.items())))
    print("harvests of melon tiles (day, hour, unit, tile, units before):")
    for t, idx, tile, u in harvests:
        if t // 24 <= a.day + 2:
            print(f"   d{t // 24} h{t % 24:02d} unit {idx:2d} tile {tile:2d} (d{dist_shed(tile)}) units {u}")
    by = defaultdict(list)
    for t, s, p in sales:
        by[("ours" if s == seat else "MGT", t // 24)].append((t % 24, p))
    for k in sorted(by):
        hs = sorted({h for h, _ in by[k]})
        print(f"   sales {k[0]:4s} day {k[1]}: {len(by[k])} units, hours {hs}, mean price {sum(p for _, p in by[k]) / len(by[k]):.0f}")


if __name__ == "__main__":
    main()

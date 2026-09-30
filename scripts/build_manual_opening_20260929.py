"""Hand-written day 0-5 opening plans in the executor's TilePlanView format (user 2026-09-29: "keep 12 melons and plan an
opening that offers competitive advantage over both DSM and MGT").

A spec lists plantings (day, tile, crop), the day each one-time crop is harvested, pastures (tile, day built), animals
(day placed, tile, species) and hands per day; the builder derives the plan fields the executor reads: plant / events,
struct_by_day, animals_by_day, board (labels at the start of each day), harv_tiles (one-time cohort ends, ongoing first
harvests), removals (none), land_day (none: the stack's policy buys land from day 6) and cum_sold (empty). Days 6-29
repeat the day-6 state: the stack replaces the plan with its own every dawn from day 6. Tile index = 10 * y + x; the
first quadrant is x, y in 0..4; the shed drop-off tiles are 44, 45, 54, 55.

  dsm_ref  DSM's own opening (dsm40 plan 112570602 layout): 6 + 4 melons, 2 cows / 3 sheep, 10 strawberries on days 2-3
  m12      12 melons on day 0 (DSM's 10 tiles + its two free tiles 2 and 30), 2 cows / 2 sheep on day 0 and the third
           sheep on day 5 (cash on days 1-4 goes to strawberries), 8 strawberries on the wheat tiles on days 2-3

usage: build_manual_opening_20260929.py [--out-dir results/fresh/semantic_h2h_20260929/opening_plans]"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRST = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
ONGOING = {"TOMATO", "STRAWBERRY"}
LABEL = {"WHEAT": "WH", "CARROT": "CA", "TOMATO": "TO", "STRAWBERRY": "ST", "MELON": "ME",
         "COW": "co", "SHEEP": "sh", "GOOSE": "go"}
WHEAT0 = [0, 1, 10, 11, 12, 20, 22, 40]
WHEAT_END = {0: 2, 1: 2, 11: 2, 22: 2, 40: 2, 10: 3, 12: 3, 20: 3}
PASTURES = [44, 24, 43, 34, 42]

SPECS = {
    "dsm_ref": dict(
        plant=[(0, t, "WHEAT") for t in WHEAT0] + [(0, t, "MELON") for t in (13, 14, 21, 23, 31, 41)]
        + [(1, t, "MELON") for t in (3, 4, 32, 33)] + [(2, t, "STRAWBERRY") for t in (2, 11, 30, 40)]
        + [(3, t, "STRAWBERRY") for t in (0, 1, 10, 12, 20, 22)],
        ends=WHEAT_END, pastures=[(t, 0) for t in PASTURES],
        animals=[(0, 44, "COW"), (0, 24, "COW"), (0, 43, "SHEEP"), (0, 34, "SHEEP"), (0, 42, "SHEEP")],
        hands=[4, 4, 6, 6, 5, 6]),
    "m12": dict(
        plant=[(0, t, "WHEAT") for t in WHEAT0] + [(0, t, "MELON") for t in (13, 14, 21, 23, 31, 41, 3, 4, 32, 33, 2, 30)]
        + [(2, t, "STRAWBERRY") for t in (11, 40)] + [(3, t, "STRAWBERRY") for t in (0, 1, 10, 12, 20, 22)],
        ends=WHEAT_END, pastures=[(t, 0) for t in PASTURES],
        animals=[(0, 44, "COW"), (0, 24, "COW"), (0, 43, "SHEEP"), (0, 34, "SHEEP"), (5, 42, "SHEEP")],
        hands=[5, 4, 6, 6, 5, 6]),
}


def build(spec, n=30):
    plant = [{} for _ in range(n)]
    events = []
    ends = {}                                      # (day) -> tiles whose one-time cohort ends that day
    harv = [set() for _ in range(n)]
    for d, t, crop in sorted(spec["plant"]):
        plant[d][str(t)] = crop
        events.append([d, t, crop])
        if crop in ONGOING:
            if d + FIRST[crop] < n:
                harv[d + FIRST[crop]].add(t)
        else:
            e = spec["ends"].get(t, d + FIRST[crop]) if crop == "WHEAT" else d + FIRST[crop]
            ends.setdefault(e, set()).add((t, d))
            if e < n:
                harv[e].add(t)
    struct_by_day = [{str(t): "PASTURE" for t, db in spec["pastures"] if db <= d} for d in range(n)]
    animals_by_day = [{str(t): sp for dp, t, sp in spec["animals"] if dp <= d} for d in range(n)]
    cur = [" ." if (i % 10 < 5 and i // 10 < 5) else " L" for i in range(100)]
    board = []
    for d in range(n):
        board.append(list(cur))
        for t, db in spec["pastures"]:
            if db == d and cur[t] in (" .",):
                cur[t] = "pa"
        for dp, t, sp in spec["animals"]:
            if dp == d:
                cur[t] = LABEL[sp]
        for t, crop in plant[d].items():
            cur[int(t)] = LABEL[crop]
        for t, dplanted in ends.get(d, ()):
            if cur[t] == LABEL[next(c for dd, tt, c in spec["plant"] if tt == t and dd == dplanted)]:
                cur[t] = " ."                      # the harvested one-time crop leaves the tile at the end of its day
    hands = list(spec["hands"]) + [spec["hands"][-1]] * (n - len(spec["hands"]))
    return dict(n=n, plant=plant, events=events, struct_by_day=struct_by_day, animals_by_day=animals_by_day,
                board=board, harv_tiles=[sorted(h) for h in harv], removals=[[] for _ in range(n)], land_day={},
                hands=hands, cum_sold=[{} for _ in range(n)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="results/fresh/semantic_h2h_20260929/opening_plans")
    a = ap.parse_args()
    out = ROOT / a.out_dir
    out.mkdir(parents=True, exist_ok=True)
    for name, spec in SPECS.items():
        p = build(spec)
        (out / f"{name}.json").write_text(json.dumps(p))
        b = p["board"]
        print(name, "| day-6 board:", " ".join(f"{i}:{b[6][i]}" for i in range(100) if b[6][i].strip() not in (".", "L")),
              "| melon harvests day 10:", p["harv_tiles"][10], "| hands", p["hands"][:6])


if __name__ == "__main__":
    main()

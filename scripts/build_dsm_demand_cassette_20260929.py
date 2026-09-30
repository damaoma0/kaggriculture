"""DSM's days 12-28 counts by DEMAND (user 2026-09-29: "semantic planner fix first"). The exact day-11 start on a current
DSM 3-quadrant game (dsm3q-114393058: our planner + executor from DSM's own day-11 state, -14.1k vs DSM's continuation)
showed the planner's day 12-29 targets diverge from DSM: 2 fewer sheep (and 8 retired on day 27), wheat 3-6 tiles lower,
6 extra strawberries, tomatoes where DSM grows none (our fixed day-18 add-on); the tiler changed almost nothing.

In DSM's current games (submission 56619023, data/leader_semantics_dsmc, the leader-panel episodes held out) each
product's count at the end of day d follows the demand of the revealed shops that consume it (engine SHOPS; a
single-product shop consumes twice): tomatoes 0 without a pizza shop / farmers market and ~10 per demand unit, carrots
0 / 4 / 8 / 13 on day 14 at carrot demand 0-3, sheep 3 / 9 / 14 at 0 / 1 / 2 yarn stores, ...

table[product][day][demand] = DSM's median count at the end of that day (products: WHEAT, CARROT, STRAWBERRY, TOMATO,
MELON, COW, SHEEP, GOOSE; days 12-28), n[product][day][demand] = games.

usage: build_dsm_demand_cassette_20260929.py [--sem data/leader_semantics_dsmc/16732748]
       [--out results/fresh/semantic_h2h_20260929/models/dsm_demand_cassette.json]"""
import argparse
import gzip
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOPS = {"BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"], "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
         "YARN_STORE": ["WOOL"], "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
         "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"], "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"]}
ITEMS = {"WHEAT": ("WH", "WHEAT"), "CARROT": ("CA", "CARROT"), "STRAWBERRY": ("ST", "STRAWBERRY"), "TOMATO": ("TO", "TOMATO"),
         "MELON": ("ME", "MELON"), "COW": ("co", "MILK"), "SHEEP": ("sh", "WOOL"), "GOOSE": ("go", "EGG")}


def demand(shops, d):
    dem = Counter()
    for s in shops:
        if int(s["reveal_day"]) <= d:
            prods = SHOPS.get(s["shop"], [])
            for q in prods:
                dem[q] += 2 if len(prods) == 1 else 1
    return dem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem", default="data/leader_semantics_dsmc/16732748")
    ap.add_argument("--out", default="results/fresh/semantic_h2h_20260929/models/dsm_demand_cassette.json")
    a = ap.parse_args()
    held = {int(c["episode"]) for c in json.loads((ROOT / "results/fresh/semantic_h2h_20260929/leaders_cases.json")
                                                    .read_text())["cases"]}
    obs = defaultdict(list)
    used = 0
    for p in sorted((ROOT / a.sem).glob("*.json.gz")):
        x = json.load(gzip.open(p, "rt", encoding="utf-8"))
        if int(x["meta"]["episode"]) in held:
            continue
        used += 1
        for d in range(12, 29):
            b = Counter(x["days"][d + 1]["board"])
            dem = demand(x["shops"], d)
            for item, (lab, prod) in ITEMS.items():
                obs[(item, d, dem[prod])].append(b.get(lab, 0))
    table, n = defaultdict(lambda: defaultdict(dict)), defaultdict(lambda: defaultdict(dict))
    for (item, d, k), v in sorted(obs.items()):
        table[item][str(d)][str(k)] = int(round(st.median(v)))
        n[item][str(d)][str(k)] = len(v)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(source=a.sem, submission=56619023, games=used, days=[12, 28], shops=SHOPS,
                                   items={k: v[1] for k, v in ITEMS.items()}, table=table, n=n), indent=1), encoding="utf-8")
    print(used, "games ->", out)
    for item in ITEMS:
        print(item, {d: table[item][d] for d in ("14", "20", "26")})


if __name__ == "__main__":
    main()

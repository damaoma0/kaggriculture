"""DSM cassette for days 6-11 (user 2026-09-29: "a deterministic cassette machine up until then"). DSM's current plan
(submission 56619023, 106 recorded games) is a near-deterministic function of the revealed shop TYPES through day 11:
each milk shop adds ~3 cows, each wool shop 6-7 sheep, each egg shop 3-4 geese, melons are the same everywhere (8 early
+ 4 on day 6), strawberries are the one free quantity. The cassette is the table day x revealed shop-type mix -> DSM's
median END-OF-DAY counts (animals by species, strawberry / melon / tomato / carrot tiles), the day's wheat plantings, hands and
quadrants owned at the next dawn (end counts, not daily actions: DSM adds the same animals on different days in
different games, and per-day medians would miss them).

Shop types: MILK (pizza / ice cream / smoothie), WOOL (yarn store), EGG (bakery / brunch / pet cafe), FARM (the rest).
A mix is the sorted list of the types revealed by that day (reveal_day <= day). The recorded-leader panel episodes
(leaders_cases.json) are held out so those panels stay independent.

usage: build_dsm_cassette_20260929.py [--sem data/leader_semantics_dsmc/16732748] [--days 6-11] [--prefix] [--submission N] [--exclude-cases FILE]
       (--sem may list several folders, comma-separated)
       [--out results/fresh/semantic_h2h_20260929/models/dsm_cassette.json]"""
import argparse
import gzip
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MILK = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
EGG = {"BAKERY", "BRUNCH_SPOT", "PET_CAFE"}
SPECIES = {"co": "COW", "sh": "SHEEP", "go": "GOOSE"}


def shop_type(s):
    return "MILK" if s in MILK else ("WOOL" if s == "YARN_STORE" else ("EGG" if s in EGG else "FARM"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem", default="data/leader_semantics_dsmc/16732748")
    ap.add_argument("--days", default="6-11")
    ap.add_argument("--out", default="results/fresh/semantic_h2h_20260929/models/dsm_cassette.json")
    ap.add_argument("--submission", type=int, default=56619023, help="metadata only (2026-09-30: 56692773 for the 4Q cassette)")
    ap.add_argument("--exclude-cases", action="append", default=[], help="cases json whose episodes are also held out "
                    "(2026-09-30: the dsm4q prefix panel)")
    ap.add_argument("--prefix", action="store_true", help="also keys 'day-6 mix|later shops' for days >= 9 (user 2026-09-29: "
                    "the sorted day-9 mix pools EGG+EGG starts, 11 strawberries on day 6, with EGG+MILK starts, 21: target 22 "
                    "vs DSM's 16 for EGG+EGG starts)")
    a = ap.parse_args()
    d0, d1 = (int(x) for x in a.days.split("-"))
    held = {int(c["episode"]) for c in json.loads((ROOT / "results/fresh/semantic_h2h_20260929/leaders_cases.json")
                                                    .read_text())["cases"]}
    for f_ in a.exclude_cases:                     # 2026-09-30: more held-out episodes (default none)
        held |= {int(c["episode"]) for c in json.loads((ROOT / f_).read_text())["cases"]}
    obs = defaultdict(list)                        # (day, mix) -> [per-game action dict]
    used = 0
    for p in sorted(q for sem_ in a.sem.split(",") for q in (ROOT / sem_).glob("*.json.gz")):   # 2026-09-30: several folders
        x = json.load(gzip.open(p, "rt", encoding="utf-8"))
        if int(x["meta"]["episode"]) in held:
            continue
        used += 1
        for d in range(d0, d1 + 1):
            day, nxt = x["days"][d], x["days"][d + 1]["board"]
            mix = "+".join(sorted(shop_type(s["shop"]) for s in x["shops"] if int(s["reveal_day"]) <= d))
            plants = {c: len(t) for c, t in (day.get("planted") or {}).items() if t}
            b = Counter(nxt)                       # the board at the next dawn = the end of day d
            ends = dict(COW=b.get("co", 0), SHEEP=b.get("sh", 0), GOOSE=b.get("go", 0), STRAWBERRY=b.get("ST", 0),
                        MELON=b.get("ME", 0), TOMATO=b.get("TO", 0), CARROT=b.get("CA", 0))
            land = sum(1 for t in nxt if t != " L") // 25
            hands = int((day.get("labour") or {}).get("hands_present", 0) or 0)
            obs[(d, mix)].append(dict(plants=plants, ends=ends, land=land, hands=hands))
            if a.prefix and d >= 9:                # the ordered prefix: the day-6 mix | the later shops in reveal order
                order = [shop_type(s["shop"]) for s in sorted(x["shops"], key=lambda s: int(s["reveal_day"]))
                         if int(s["reveal_day"]) <= d]
                pk = "+".join(sorted(order[:2])) + "|" + "+".join(order[2:])
                obs[(d, pk)].append(dict(plants=plants, ends=ends, land=land, hands=hands))
    table = defaultdict(dict)
    for (d, mix), rows in sorted(obs.items()):
        med = lambda xs: int(round(st.median(xs)))  # noqa: E731
        table[str(d)][mix] = dict(
            n=len(rows),
            end_counts={k: med([r["ends"][k] for r in rows]) for k in rows[0]["ends"]},   # targets at the end of day d
            wheat_plant=med([r["plants"].get("WHEAT", 0) for r in rows]),               # wheat: the day's plantings
            land=med([r["land"] for r in rows]), hands=med([r["hands"] for r in rows]))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(source=a.sem, submission=a.submission, games=used, held_out=sorted(held), days=[d0, d1],
                                   shop_types=dict(MILK=sorted(MILK), EGG=sorted(EGG), WOOL=["YARN_STORE"], FARM="other"),
                                   table=table), indent=1), encoding="utf-8")
    print(f"{used} games -> {out}")
    for d in range(d0, d1 + 1):
        print(f"day {d}: {len(table[str(d)])} mixes: " + "; ".join(
            f"{m} (n={v['n']}): {v['end_counts']} wheat {v['wheat_plant']} land {v['land']} hands {v['hands']}"
            for m, v in sorted(table[str(d)].items(), key=lambda kv: -kv[1]["n"])[:3]))


if __name__ == "__main__":
    main()

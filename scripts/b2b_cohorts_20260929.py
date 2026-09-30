"""Cohort-by-cohort comparison of a tile-exact pair (b2b caches; same plantings in both games): for every one-time crop
cohort (tile, crop, planted day) planted from day FROM, when each game ended it (harvest / decay / still standing),
its age and units at the end, and the waterings / fertilizes it got (from the step commands and hand positions).

usage: b2b_cohorts_20260929.py CASE_ID TAG [--from 11] [--crops WHEAT,CARROT] [--list]"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_h2h_20260929/b2b"


def cohorts(g, crops, d0):
    """(tile, crop, planted_day) -> dict(end_step, end_kind, units, age, waters, ferts, water_ages)"""
    live = {}
    res = {}
    prev = None
    for f in g["frames"]:
        t = f["t"]
        b = [g["tiles"][i] for i in f["b"]]
        units = f["u"]
        a = f.get("a") or {}
        cmds = [a.get("farmer")] + list(a.get("hands") or [])
        # commands of this step act on the tile the unit stands on (position recorded after the step's moves)
        acted = defaultdict(list)
        for u, c in enumerate(cmds):
            if c and u < len(units) and c[0] in ("WATER", "FERTILIZE", "HARVEST", "DIG"):
                acted[units[u][1] * 10 + units[u][0]].append(c[0])
        for i, x in enumerate(b):
            key = (i, x.get("crop"), x.get("planted_day")) if isinstance(x, dict) and x.get("crop") else None
            if key and key[1] in crops and key[2] >= d0:
                c = live.setdefault(key, dict(waters=0, ferts=0, water_ages=[], ymax=0, last_y=0, fert_until=-1))
                c["ymax"] = max(c["ymax"], int(x.get("yield_units", 0) or 0))
                c["last_y"] = int(x.get("yield_units", 0) or 0)
                c["fert_until"] = int(x.get("fertilized_until_day", -1) or -1)
                for op in acted.get(i, ()):
                    if op == "WATER":
                        c["waters"] += 1
                        c["water_ages"].append(t // 24 - key[2])
                    elif op == "FERTILIZE":
                        c["ferts"] += 1
        # cohorts that vanished this step
        for key in list(live):
            i = key[0]
            x = b[i]
            still = isinstance(x, dict) and x.get("crop") == key[1] and x.get("planted_day") == key[2]
            if not still:
                c = live.pop(key)
                kind = "weed" if isinstance(x, dict) and x.get("kind") == "WEED" else ("harvest" if "HARVEST" in acted.get(i, ()) or True else "?")
                res[key] = dict(c, end=t, age=t // 24 - key[2], kind=kind, units=c["last_y"])
        prev = b
    for key, c in live.items():
        res[key] = dict(c, end=None, age=None, kind="standing", units=c["last_y"])
    return res


def main():
    a = sys.argv
    cid, tag = a[1], a[2]
    d0 = int(a[a.index("--from") + 1]) if "--from" in a else 11
    crops = set((a[a.index("--crops") + 1] if "--crops" in a else "WHEAT,CARROT").split(","))
    A = json.loads(gzip.open(OUT / f"{cid}.dsm.game.json.gz", "rt").read())
    B = json.loads(gzip.open(OUT / f"{cid}.{tag}.game.json.gz", "rt").read())
    ca, cb = cohorts(A, crops, d0), cohorts(B, crops, d0)
    for crop in sorted(crops):
        ka = {k for k in ca if k[1] == crop}
        kb = {k for k in cb if k[1] == crop}
        both = sorted(ka & kb, key=lambda k: (k[2], k[0]))
        print(f"== {crop}: cohorts DSM {len(ka)}, ours {len(kb)}, common {len(both)}")
        for name, cc, ks in (("DSM ", ca, ka), ("ours", cb, kb)):
            xs = [cc[k] for k in ks if cc[k]["kind"] != "standing"]
            ages = Counter(x["age"] for x in xs)
            print(f"   {name}: ended {len(xs)}, units {sum(x['units'] for x in xs)} ({sum(x['units'] for x in xs) / max(1, len(xs)):.2f}/cohort),"
                  f" harvest age {dict(sorted(ages.items()))}, waters/cohort {sum(x['waters'] for x in xs) / max(1, len(xs)):.2f},"
                  f" fertilizes/cohort {sum(x['ferts'] for x in xs) / max(1, len(xs)):.2f}, units dist {dict(sorted(Counter(x['units'] for x in xs).items()))}")
        # paired differences on common cohorts
        du = Counter()
        early = late = same = 0
        for k in both:
            x, y = ca[k], cb[k]
            if x["end"] is None or y["end"] is None:
                continue
            if y["end"] // 24 < x["end"] // 24:
                early += 1
            elif y["end"] // 24 > x["end"] // 24:
                late += 1
            else:
                same += 1
            du[(x["units"], y["units"])] += 1
        print(f"   common cohorts: we end them a day+ EARLIER {early}, same day {same}, LATER {late};"
              f" units (DSM, ours) most common: {du.most_common(8)}")
        if "--list" in a:
            for k in both[:60]:
                x, y = ca[k], cb[k]
                print(f"     tile ({k[0] % 10},{k[0] // 10}) planted d{k[2]}: DSM end d{(x['end'] or 0) // 24} age {x['age']} {x['units']}u w{x['waters']} f{x['ferts']}"
                      f" wa{x['water_ages']} | ours end d{(y['end'] or 0) // 24} age {y['age']} {y['units']}u w{y['waters']} f{y['ferts']} wa{y['water_ages']}")


if __name__ == "__main__":
    main()

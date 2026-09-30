"""Replant and planting-water audit of recorded games (b2b caches), user 2026-09-29: "For replant, how many times do we
harvest and only plant on next day? How many times a 'plant' went without 'water'?"

  replant delay   every cohort that ends (one-time crop HARVEST, or a dug / decayed plant) on days FROM..27: days until
                  the tile's next planting (0 = same day, 1 = next day, ...; 'never' = not replanted by day 29), and
                  what the tile was in between (empty / weed)
  plant w/o water every planting from day FROM: was the tile watered on its planting day after the PLANT? (a plant
                  unwatered two days running wilts); and did the planting later wilt / decay into a weed

usage: replant_audit_20260929.py CASE_ID[,CASE_ID...] KEY [KEY ...] [--from 6]"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chain_audit_20260929 import cohorts, CROPS, OUT   # noqa: E402


def main():
    a = sys.argv
    cids = a[1].split(",")
    keys = [x for x in a[2:] if not x.startswith("--") and not x.isdigit()]
    d0 = int(a[a.index("--from") + 1]) if "--from" in a else 6
    for key in keys:
        delay = defaultdict(Counter)
        between = Counter()
        pw = defaultdict(Counter)
        n = 0
        for cid in cids:
            f = OUT / f"{cid}.{key}.game.json.gz"
            if not f.exists():
                continue
            n += 1
            g = json.loads(gzip.open(f, "rt", encoding="utf-8").read())
            co = cohorts(g, 0)
            by_tile = defaultdict(list)
            for k, c in co.items():
                by_tile[k[0]].append((k[2], k, c))
            for tile, lst in by_tile.items():
                lst.sort(key=lambda x: (x[0], x[2]["first_seen"]))
                for j, (p, k, c) in enumerate(lst):
                    # planting water
                    if p >= d0:
                        ops = sorted(c["ops"])
                        plant_step = next((s for s, o in ops if o == "PLANT" and s // 24 == p), None)
                        w = any(o == "WATER" and s // 24 == p and (plant_step is None or s > plant_step) for s, o in ops)
                        end_kind = "harvested" if any(o == "HARVEST" for _, o in ops) else ("dug" if any(o == "DIG" for _, o in ops) else "")
                        died = c["end"] is not None and not end_kind
                        pw[k[1]]["plantings"] += 1
                        pw[k[1]]["watered_on_planting_day"] += int(w)
                        pw[k[1]]["NOT_watered_on_planting_day"] += int(not w)
                        pw[k[1]]["not_watered_and_died"] += int((not w) and died)
                        pw[k[1]]["died_(wilt/decay)"] += int(died)
                    # replant delay after this cohort ended
                    if c["end"] is None:
                        continue
                    e_day = c["end"] // 24
                    if not (d0 <= e_day <= 27):
                        continue
                    nxt = lst[j + 1] if j + 1 < len(lst) else None
                    how = "harvest" if any(o == "HARVEST" for _, o in c["ops"]) else ("dig" if any(o == "DIG" for _, o in c["ops"]) else "died")
                    cat = f"{k[1]}:{how}"
                    if nxt is None:
                        delay[cat]["never"] += 1
                        continue
                    dd = nxt[0] - e_day
                    delay[cat][dd if dd <= 3 else "4+"] += 1
                    if dd >= 1:                         # what stood on the tile in between
                        mid = g["frames"][min(len(g["frames"]) - 1, (e_day + 1) * 24)]
                        t = g["tiles"][mid["b"][tile]]
                        between["weed" if isinstance(t, dict) and t.get("kind") == "WEED" else ("empty" if t is None else str(t)[:20])] += 1
        print(f"== {key}: {n} world(s), per world")
        print("  replant delay (days from the cohort's end to the next planting on the tile):")
        for cat, cnt in sorted(delay.items(), key=lambda kv: -sum(kv[1].values())):
            tot = sum(cnt.values())
            order = [0, 1, 2, 3, "4+", "never"]
            print(f"    {cat:20s} {tot / n:5.1f}  " + "  ".join(f"{('same day' if o == 0 else o if o in ('4+', 'never') else f'+{o}d')}: {cnt[o] / n:.1f}"
                                                        for o in order if cnt[o]))
        print("    tile at the next dawn when not replanted the same day:", {k: round(v / n, 1) for k, v in between.items()})
        print("  plantings and the planting-day water:")
        for crop, cnt in pw.items():
            print(f"    {crop:10s} " + ", ".join(f"{k} {v / n:.1f}" for k, v in cnt.items()))


if __name__ == "__main__":
    main()

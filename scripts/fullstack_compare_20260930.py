"""Compare full-stack variants in DSM-new worlds (2026-09-30): the day-11 dawn state (quadrants, cash, animals, core tiles
off DSM's board with wheat / carrot / empty / weed as filler) and the final cash, against DSM's own game.

usage: fullstack_compare_20260930.py EP[,EP] KEY[,KEY...]   (keys as saved in results/fresh/dsm4q_d9_20260930/games,
       e.g. fsA.p264, fsCand.p264, d9c4o.p0)"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

G = Path(__file__).resolve().parents[1] / "results/fresh/dsm4q_d9_20260930/games"
FILL = {"WHEAT", "CARROT", "EMPTY", "WEED"}


def lab(t):
    if t is None:
        return "EMPTY"
    if t == "LOCKED":
        return "LOCKED"
    return t.get("crop") or t.get("animal") or t.get("kind")


def core(x):
    return "FILL" if x in FILL else x


def load(ep, key):
    f = G / f"d4q9-{ep}.{key}.game.json.gz"
    return json.loads(gzip.open(f, "rt", encoding="utf-8").read()) if f.exists() else None


def main():
    eps, keys = sys.argv[1].split(","), sys.argv[2].split(",")
    for ep in eps:
        d = load(ep, "dsm")
        bd = [lab(d["tiles"][i]) for i in d["frames"][264]["b"]]
        cd = Counter(bd)
        print(f"== world {ep}: DSM day-11 dawn quadrants {d['frames'][264]['q']}, cash {d['frames'][264]['m'][0]}, "
              f"animals {sum(cd[k] for k in ('COW', 'SHEEP', 'GOOSE'))}, final {d['cash']:.0f}")
        print("   variant | day-11: quadrants, cash, animals, crops, empty+weed, core tiles off, core comp | final cash (vs DSM)")
        for k in keys:
            g = load(ep, k)
            if not g:
                print(f"   {k:14s} (missing)")
                continue
            fr = next((f for f in g["frames"] if f["t"] == 264), None)
            if fr is None:
                print(f"   {k:14s} no day-11 frame")
                continue
            bo = [lab(g["tiles"][i]) for i in fr["b"]]
            co = Counter(bo)
            ca, cb = Counter(map(core, bo)), Counter(map(core, bd))
            comp = sum(abs(ca[x] - cb[x]) for x in set(ca) | set(cb) if x not in ("FILL", "LOCKED")) / 2
            crops = sum(co[x] for x in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"))
            print(f"   {k:14s} | {fr['q']}, {fr['m'][0]:6d}, {sum(co[x] for x in ('COW', 'SHEEP', 'GOOSE')):2d}, {crops:2d}, "
                  f"{co['EMPTY'] + co['WEED']:2d}, {sum(1 for x, y in zip(bo, bd) if core(x) != core(y)):2d}, {comp:4.1f} | "
                  f"{g['cash']:7.0f} ({g['cash'] - d['cash']:+.0f})")


if __name__ == "__main__":
    main()

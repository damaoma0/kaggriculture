"""Day-11 dawn board of our arms vs DSM's in one DSM-new world, wheat treated as filler (user 2026-09-30: replicate DSM
boards; "cut things like wheat to have minimal knock-on effect"): tiles off, non-filler tiles off (wheat, carrot,
empty, weed = filler), non-filler composition distance, counts by kind, and the handoff value gap
(scripts/dsm4q_handoff_value_20260930.py valuation). Checks the day-9 handover is exact first.

usage: board_score_20260930.py EP ARM[,ARM...] [--day 11]"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dsm4q_handoff_value_20260930 as HV  # noqa: E402
from dsm4q_d11_board_20260930 import load, label  # noqa: E402

FILL = {"WHEAT", "EMPTY", "WEED", "CARROT"}


def core(x):
    return "FILL" if x in FILL else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("arms")
    ap.add_argument("--day", type=int, default=11)
    a = ap.parse_args()
    cid = f"d4q9-{a.ep}"
    d = load(cid, "dsm")
    step = 24 * a.day
    bd = [label(d["tiles"][i]) for i in d["frames"][step]["b"]]
    HV.DAY = a.day
    prices = dict(zip(HV.GOODS, d["frames"][step]["p"]))
    vd = HV.value(d, prices)
    kinds = ("STRAWBERRY", "TOMATO", "MELON", "COW", "SHEEP", "GOOSE", "WHEAT", "CARROT", "EMPTY")
    print(f"world {a.ep}, day-{a.day} dawn; DSM: " + " ".join(f"{k[:4]} {bd.count(k)}" for k in kinds))
    print("arm | exact handover | tiles off | non-filler off | non-filler comp | counts | value gap (crops, animals, total)")
    for arm in a.arms.split(","):
        g = load(cid, f"{arm}.p216")
        if not g:
            print(f"{arm}: not run")
            continue
        exact = [label(g["tiles"][i]) for i in g["frames"][216]["b"]] == [label(d["tiles"][i]) for i in d["frames"][216]["b"]]
        bo = [label(g["tiles"][i]) for i in g["frames"][step]["b"]]
        ca, cb = Counter(map(core, bo)), Counter(map(core, bd))
        cp = sum(abs(ca[k] - cb[k]) for k in set(ca) | set(cb) if k not in ("FILL", "LOCKED")) / 2
        v = HV.value(g, prices)
        print(f"{arm:16s} | {exact} | {sum(1 for x, y in zip(bo, bd) if x != y):3d} | "
              f"{sum(1 for x, y in zip(bo, bd) if core(x) != core(y)):3d} | {cp:4.1f} | "
              + " ".join(f"{k[:4]} {bo.count(k)}" for k in kinds)
              + f" | {v['crops'] - vd['crops']:+.0f}, {v['animals'] - vd['animals']:+.0f}, {v['total'] - vd['total']:+.0f}")


if __name__ == "__main__":
    main()

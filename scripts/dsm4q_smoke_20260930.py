"""Per-world smoke table for the day-9 handover arms (user 2026-09-30: "smoke on worst offenders ... don't waste time on
full runs on multiple boards"): for the named worlds and arms, the day-11 dawn gap to DSM (value by component, care
bank, board composition distance) and the pen / planting counts that drove it.

usage: dsm4q_smoke_20260930.py EP[,EP...] ARM[,ARM...]   (arm names use {ep}, e.g. d9e68v{ep})"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dsm4q_handoff_value_20260930 as HV  # noqa: E402
from dsm4q_d11_board_20260930 import load, label, board  # noqa: E402
from dsm4q_stock_flow_20260930 import flows  # noqa: E402


def comp(g, d):
    lo = Counter(label(t) for t in board(g, 264)[0])
    ld = Counter(label(t) for t in board(d, 264)[0])
    return sum(abs(lo[k] - ld[k]) for k in set(lo) | set(ld) if k != "LOCKED") / 2


def planted(g, day):
    return sum(1 for t in board(g, 264)[0] if isinstance(t, dict) and t.get("crop") and t.get("planted_day") == day)


def main():
    eps, arms = sys.argv[1].split(","), sys.argv[2].split(",")
    HV.DAY = 11
    print("world      arm            total  crops animals  stock   cash |  bank | comp | planted d9 d10 | fed d9 d10 | escaped")
    for ep in eps:
        cid = f"d4q9-{ep}"
        d = load(cid, "dsm")
        prices = dict(zip(HV.GOODS, d["frames"][264]["p"]))
        vd, fd = HV.value(d, prices), flows(d)
        print(f"{ep}  DSM         {vd['total']:7.0f}                              | {vd['bank']:5.0f} |      |      {planted(d, 9):4d} {planted(d, 10):3d} |"
              f"  {fd['d9:fed']:4d} {fd['d10:fed']:3d} |")
        for a in arms:
            g = load(cid, a.replace("{ep}", ep) + ".p216")
            if not g:
                print(f"{ep}  {a.replace('{ep}', ''):12s} (not run)")
                continue
            if [label(t) for t in board(g, 216)[0]] != [label(t) for t in board(d, 216)[0]]:
                print(f"{ep}  {a.replace('{ep}', ''):12s} (inexact handover)")
                continue
            v, f = HV.value(g, prices), flows(g)
            esc = sum(n for k, n in f.items() if ":escaped:" in k)
            print(f"{ep}  {a.replace('{ep}', ''):12s} {v['total'] - vd['total']:+7.0f} {v['crops'] - vd['crops']:+6.0f} "
                  f"{v['animals'] - vd['animals']:+7.0f} {v['stock'] - vd['stock']:+6.0f} {v['cash'] - vd['cash']:+6.0f} |"
                  f" {v['bank'] - vd['bank']:+5.0f} | {comp(g, d):4.0f} |      {planted(g, 9):4d} {planted(g, 10):3d} |"
                  f"  {f['d9:fed']:4d} {f['d10:fed']:3d} | {esc}")


if __name__ == "__main__":
    main()

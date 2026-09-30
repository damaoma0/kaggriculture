"""Per recorded-leader case: our arms vs the leader and vs each other, from the harness ledgers - margin by day, revenue /
units / average price per product (ours | leader), spending by kind, animals / crops held by day, idle share by phase.

usage: leader_case_compare_20260929.py CASE [ARM_DIR ...]   (ARM_DIR = a folder holding <case>.json, e.g.
       results/fresh/semantic_h2h_20260929/leadersx_credit/n18 results/fresh/semantic_h2h_20260929/local_x/n18rc)"""
import json
import sys
from pathlib import Path

PRODUCTS = ["STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "WHEAT", "CARROT", "TOMATO", "FERTILIZER"]


def main():
    case, dirs = sys.argv[1], sys.argv[2:]
    R = {Path(d).name: json.loads((Path(d) / f"{case}.json").read_text()) for d in dirs}
    for name, r in R.items():
        s = r["case"]["seat"]
        us, ld = r["daily"][s], r["daily"][1 - s]
        print(f"\n=== {name} on {case}: margin {r['margin']:+.0f} (ours {r['cash']:.0f}, leader {r['opponent_cash']:.0f})")
        print("  margin by dawn of day: " + " ".join(f"d{d}:{us[d]['money'] - ld[d]['money']:+.0f}" for d in (6, 9, 12, 15, 18, 21, 24, 27, 30)))
        print("  product      ours units@price  | leader units@price | revenue gap")
        for p in PRODUCTS:
            u, ul = us[-1]["sold_units"].get(p, 0), ld[-1]["sold_units"].get(p, 0)
            rv, rl = us[-1]["revenue"].get(p, 0), ld[-1]["revenue"].get(p, 0)
            if u or ul:
                print(f"  {p:11s} {u:5.0f}@{(rv / u if u else 0):5.0f}      | {ul:5.0f}@{(rl / ul if ul else 0):5.0f}      | {rv - rl:+7.0f}")
        sp = {}
        for k, v in us[-1]["spend"].items():
            sp[k.split(":")[0]] = sp.get(k.split(":")[0], 0) - 0 + v
        spl = {}
        for k, v in ld[-1]["spend"].items():
            spl[k.split(":")[0]] = spl.get(k.split(":")[0], 0) + v
        print("  spending ours | leader: " + ", ".join(f"{k} {sp.get(k, 0):.0f} | {spl.get(k, 0):.0f}" for k in sorted(set(sp) | set(spl))))
        held = lambda D, d, k: (D[d]["tile_hours"].get(k, 0) - D[d - 1]["tile_hours"].get(k, 0)) / 24  # noqa: E731
        for k in ("animal:COW", "animal:SHEEP", "animal:GOOSE", "crop:STRAWBERRY", "crop:MELON", "crop:WHEAT", "crop:TOMATO", "crop:CARROT"):
            print(f"  {k:16s} ours " + " ".join(f"{held(us, d, k):4.1f}" for d in (7, 9, 11, 13, 16, 19, 22, 25, 28))
                  + " | leader " + " ".join(f"{held(ld, d, k):4.1f}" for d in (7, 9, 11, 13, 16, 19, 22, 25, 28)))
        for who, D in (("ours", us), ("leader", ld)):
            ph = []
            for a, b in ((6, 9), (9, 18), (18, 30)):
                p0, p1 = D[a]["physical"], D[b]["physical"]
                n = p1.get("commands", 0) - p0.get("commands", 0)
                ph.append(f"d{a}-{b - 1} idle {100 * (p1.get('op:PASS', 0) - p0.get('op:PASS', 0)) / max(1, n):.0f}% of {n}")
            ops = {k[3:]: D[-1]["physical"].get(k, 0) for k in ("op:FEED", "op:CARE", "op:WATER", "op:HARVEST", "op:FERTILIZE", "op:COLLECT_FERTILIZER", "op:PLANT")}
            print(f"  {who:6s} labour: {'; '.join(ph)} | ops {ops}")


if __name__ == "__main__":
    main()

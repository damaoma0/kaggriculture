"""Sale timing and realized prices, ours vs the leader, from a bringback_profile_20260929.py harness profile (the
profile records every executed SELL with its price). User 2026-09-29: bring-back trips as a shortfall; the price gap
(-11k a game on 8 leader worlds) turned out to be WHICH DAYS each side sells, not the hour.

usage: sale_timing_report_20260929.py PROFILE.json [--days 6-29] [--per-day PRODUCT]"""
import json
import sys
from collections import Counter, defaultdict

ITEMS = ("WOOL", "STRAWBERRY", "MILK", "MELON", "FERTILIZER", "EGG", "WHEAT", "CARROT", "TOMATO")


def main():
    R = json.load(open(sys.argv[1]))
    d0, d1 = (6, 29)
    if "--days" in sys.argv:
        d0, d1 = map(int, sys.argv[sys.argv.index("--days") + 1].split("-"))
    n = len(R)
    for side in ("ours", "leader"):
        U, V, lots = defaultdict(Counter), defaultdict(Counter), defaultdict(list)
        for g in R.values():
            for d, D in g[side].items():
                if d == "cycles" or not d0 <= int(d) <= d1:
                    continue
                for key, k in D["sells"].items():
                    h, it = key.split(":")
                    U[it][int(h) // 4] += k
                    V[it][int(h) // 4] += D.get("rev", {}).get(key, 0)
                    lots[it].append(k)
        print(side)
        for it in ITEMS:
            tot = sum(U[it].values())
            if not tot:
                continue
            L = lots[it]
            print(f"  {it:10s} {tot / n:6.1f} u/game @ {sum(V[it].values()) / tot:6.1f} | by 4h block (share@price) " +
                  " ".join(f"{b * 4:2d}:{U[it][b] / tot:.0%}@{V[it][b] / max(1, U[it][b]):.0f}" for b in range(6)) +
                  f" | {len(L) / n:.0f} sale-hours/game, {sum(L) / len(L):.1f} units each")
    if "--per-day" in sys.argv:
        it = sys.argv[sys.argv.index("--per-day") + 1]
        print(f"\n{it} per day: ours units@price | leader units@price")
        for k, g in R.items():
            line = []
            for d in range(d0, d1 + 1):
                Du, Dl = g["ours"].get(str(d)), g["leader"].get(str(d))
                if not Du or not Dl:
                    continue
                uu = sum(c for kk, c in Du["sells"].items() if kk.endswith(":" + it))
                vu = sum(v for kk, v in Du.get("rev", {}).items() if kk.endswith(":" + it))
                ul = sum(c for kk, c in Dl["sells"].items() if kk.endswith(":" + it))
                vl = sum(v for kk, v in Dl.get("rev", {}).items() if kk.endswith(":" + it))
                if uu or ul:
                    line.append(f"{d}:{uu}@{vu / max(1, uu):.0f}|{ul}@{vl / max(1, ul):.0f}")
            print(f"  {k[-14:]} " + " ".join(line))


if __name__ == "__main__":
    main()

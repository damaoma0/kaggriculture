"""One-time crop cycles (plant -> harvest) from bringback_profile_20260929.py output: per crop and side, cycles per game,
units per cycle, harvest age, fertilize ages, watering ages (the wheat cycle audit, user 2026-09-29: "our wheat cycle is
also worse, showing less output hypothetically due to a missing fertilization").

usage: crop_cycles_report_20260929.py PROFILE.json [--from-day 6]"""
import json
import sys
from collections import Counter, defaultdict


def main():
    R = json.load(open(sys.argv[1]))
    d0 = int(sys.argv[sys.argv.index("--from-day") + 1]) if "--from-day" in sys.argv else 6
    for fam in ("dsm", "mmpq"):
        games = {k: v for k, v in R.items() if f"-{fam}-" in k}
        if not games:
            continue
        for side in ("ours", "leader"):
            by = defaultdict(list)
            for g in games.values():
                for c in g[side].get("cycles", []):
                    if c["planted"] >= d0:
                        by[c["crop"]].append(c)
            n = len(games)
            for crop in ("WHEAT", "CARROT", "MELON"):
                cs = by.get(crop, [])
                if not cs:
                    continue
                units = sum(c["units"] for c in cs)
                ha = Counter(c["harvest"] for c in cs)
                fa = Counter(tuple(sorted(set(c["fert"]))) for c in cs)
                win = Counter(sum(1 for a in set(c["water"]) if (2 if crop == "WHEAT" else 2 if crop == "CARROT" else 6) <= a <= c["harvest"]) for c in cs)
                u_by_f = defaultdict(list)
                for c in cs:
                    u_by_f[bool(c["fert"])].append(c["units"])
                print(f"{fam} {side:6s} {crop:6s} cycles/game {len(cs) / n:5.1f} units/cycle {units / len(cs):4.2f} "
                      f"units/game {units / n:6.1f} | fertilized {sum(1 for c in cs if c['fert']) / len(cs):4.0%} "
                      f"(units {sum(u_by_f[True]) / max(1, len(u_by_f[True])):.2f} vs {sum(u_by_f[False]) / max(1, len(u_by_f[False])):.2f}) | "
                      f"harvest age {dict(sorted(ha.items()))} | fert ages {dict(fa.most_common(4))} | window waterings {dict(sorted(win.items()))}")


if __name__ == "__main__":
    main()

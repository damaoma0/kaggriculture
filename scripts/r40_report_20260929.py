"""40-world panel vs MGT (arms_r40_fs): per arm the win rate with a Wilson 95% interval, the mean margin with a bootstrap
95% interval, wins by seat, and for every pair of arms the paired margin change (same worlds, same shops).

usage: r40_report_20260929.py [--dir results/fresh/semantic_h2h_20260929/arms_r40_fs] [--arms n17,n18,...]"""
import argparse
import glob
import json
import math
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(d):
    out = {}
    for f in glob.glob(os.path.join(d, "*.json")):
        if f.endswith((".actions.json", ".spawns.json", "summary.json")):
            continue
        r = json.load(open(f))
        if isinstance(r, dict) and r.get("completed") and r.get("margin") is not None:
            out[r["case"]["id"]] = r
    return out


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - h, c + h)


def boot(xs, it=4000, seed=1):
    rng = random.Random(seed)
    if not xs:
        return (0.0, 0.0)
    ms = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(it))
    return (ms[int(0.025 * it)], ms[int(0.975 * it)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/fresh/semantic_h2h_20260929/arms_r40_fs")
    ap.add_argument("--arms", default=None)
    a = ap.parse_args()
    d = ROOT / a.dir
    arms = a.arms.split(",") if a.arms else sorted(p.name for p in d.iterdir() if p.is_dir() and not p.name.startswith("_"))
    data = {x: rows(d / x) for x in arms}
    print(f"{'arm':8s} {'n':>3s} {'wins':>5s} {'win%':>6s} {'95% CI':>13s} {'mean':>8s} {'95% CI':>17s}  seat0  seat1  over60s")
    for x in arms:
        R = data[x]
        m = [r["margin"] for r in R.values()]
        k = sum(v > 0 for v in m)
        lo, hi = wilson(k, len(m))
        blo, bhi = boot(m)
        s0 = [r["margin"] > 0 for r in R.values() if r["case"]["seat"] == 0]
        s1 = [r["margin"] > 0 for r in R.values() if r["case"]["seat"] == 1]
        over = sum(1 for r in R.values() if (r.get("measured_overage_used") or [0, 0])[r["case"]["seat"]] > 60)
        print(f"{x:8s} {len(m):3d} {k:5d} {100 * k / max(1, len(m)):5.1f}% [{100 * lo:4.1f},{100 * hi:5.1f}] "
              f"{(sum(m) / max(1, len(m))):+8.0f} [{blo:+7.0f},{bhi:+7.0f}]  {sum(s0)}/{len(s0)}  {sum(s1)}/{len(s1)}  {over}")
    for i, x in enumerate(arms):
        for y in arms[i + 1:]:
            ks = sorted(set(data[x]) & set(data[y]))
            if not ks:
                continue
            dm = [data[y][k]["margin"] - data[x][k]["margin"] for k in ks]
            lo, hi = boot(dm)
            flips = sum(1 for k in ks if (data[y][k]["margin"] > 0) != (data[x][k]["margin"] > 0))
            print(f"  {y} - {x}: n={len(ks)} mean {sum(dm) / len(dm):+.0f} [{lo:+.0f},{hi:+.0f}], better "
                  f"{sum(v > 0 for v in dm)} / worse {sum(v < 0 for v in dm)} / same {sum(v == 0 for v in dm)}, win flips {flips}")


if __name__ == "__main__":
    main()

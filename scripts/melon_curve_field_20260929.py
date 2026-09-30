"""Melon sale schedules of ours against the recorded melon sales of current leader games, on the engine's price curve.

Melons have no shop demand (the town centre takes one a day), so the melon margin between two farms is decided by who
sells which units into one shared curve. Each recorded farm (DSM and each of its opponents, from the exact replays in
results/fresh/dsm_melon_reaction_20260929/games.json) is one opponent sample: its unit-by-unit melon sales on days 9-14
are kept fixed (DSM does not react to the other farm's melon timing within a game) and ours replace the other farm's.
Both farms quote the same pre-commit inventory for each lockstep unit (engine `_process_market`).

usage: melon_curve_field_20260929.py [--games results/fresh/dsm_melon_reaction_20260929/games.json]"""
import argparse
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".venv/Lib/site-packages/kaggle_environments/envs/kaggriculture"))
import kaggriculture as K  # noqa: E402

I0 = K.MARKET_PARAMS["MELON"]["I0"]
SEED = K.CROPS["MELON"]["seed"]
# ours, units per (day, hour); 10 tiles x 6 = 60 units unless stated (V13 / A4 from the fresh-8 action streams)
OURS = {
    "V13 now (d10 from h10)": ({(10, 10): 2, (10, 11): 15, (10, 12): 13, (10, 13): 6, (11, 8): 6, (11, 10): 6, (11, 12): 6,
                                (11, 13): 2, (12, 1): 4}, 0),
    "A4 (d10 from h8)": ({(10, 8): 6, (10, 9): 12, (10, 10): 12, (10, 12): 6, (11, 7): 6, (11, 8): 6, (11, 10): 6, (11, 12): 2,
                          (12, 1): 4}, 0),
    "A4 + one near tile (h5)": ({(10, 5): 6, (10, 8): 6, (10, 9): 12, (10, 10): 12, (11, 7): 6, (11, 8): 6, (11, 10): 6,
                                 (11, 12): 2, (12, 1): 4}, 0),
    "10 tiles on day 0 (A4 timing)": ({(10, 8): 6, (10, 9): 24, (10, 10): 24, (10, 12): 6}, 0),
    "10 on day 0 + near tile": ({(10, 5): 6, (10, 8): 6, (10, 9): 24, (10, 10): 24}, 0),
    "12 on day 0 (A4 timing, +2 seeds)": ({(10, 8): 6, (10, 9): 30, (10, 10): 30, (10, 12): 6}, 2 * SEED),
}


def play(ours, theirs):
    inv, rev = I0 - 10, [0.0, 0.0]            # ten days of town-centre consumption, no melon sales before day 10
    for d in range(9, 15):
        if d > 10:
            inv -= 1
        for h in range(24):
            rem = [ours.get((d, h), 0), theirs.get((d, h), 0)]
            while any(rem):
                p = K.market_price("MELON", inv)
                for i in (0, 1):
                    if rem[i] > 0:
                        rev[i] += p
                        rem[i] -= 1
                        inv += 1
    return rev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", default="results/fresh/dsm_melon_reaction_20260929/games.json")
    a = ap.parse_args()
    games = json.loads((ROOT / a.games).read_text())
    for window, tag in (("56619023", "current DSM version (114.3M-114.6M)"), ("56498734", "older DSM version (112.6M-113.0M)")):
        opps = []                                  # (label, schedule)
        for r in games:
            if not r["folder"].endswith(window):
                continue
            names = r.get("names") or ["?", "?"]
            for side, name in (("dsm", "DSM"), ("opp", next((n for i, n in enumerate(names) if i != r["dsm_seat"]), "?"))):
                sch = Counter((t // 24, t % 24) for t, _ in r["sales_d9_14"][side])
                opps.append((name, sch))
        base = {i: play(OURS["V13 now (d10 from h10)"][0], s) for i, (_, s) in enumerate(opps)}
        print(f"\n=== {tag}: {len(opps)} recorded melon schedules (DSM and its opponents); opponent day-10 units mean "
              f"{st.mean(sum(v for (d, _), v in s.items() if d == 10) for _, s in opps):.1f}")
        print(f"{'our schedule':36s} {'margin vs V13 now':>18s} {'p10':>6s} {'p90':>6s} | {'vs DSM':>7s} {'vs others':>9s} | "
              f"{'ours':>6s} {'theirs':>7s}")
        for nm, (sch, extra) in OURS.items():
            dm, dd, do, oo, tt = [], [], [], [], []
            for i, (lab, s) in enumerate(opps):
                r_ = play(sch, s)
                b_ = base[i]
                m = (r_[0] - b_[0]) - (r_[1] - b_[1]) - extra
                dm.append(m)
                (dd if lab == "DSM" else do).append(m)
                oo.append(r_[0] - b_[0] - extra)
                tt.append(r_[1] - b_[1])
            q = sorted(dm)
            print(f"{nm:36s} {st.mean(dm):+18.0f} {q[len(q) // 10]:+6.0f} {q[9 * len(q) // 10]:+6.0f} | {st.mean(dd):+7.0f} "
                  f"{st.mean(do):+9.0f} | {st.mean(oo):+6.0f} {st.mean(tt):+7.0f}")
        by = defaultdict(list)
        for lab, s in opps:
            by[lab].append(s)
        top = sorted(by, key=lambda k: -len(by[k]))[:6]
        print("  by opponent (10 on day 0 + near tile vs V13 now): " + ", ".join(
            f"{k} {st.mean([(play(OURS['10 on day 0 + near tile'][0], s)[0] - play(OURS['V13 now (d10 from h10)'][0], s)[0]) - (play(OURS['10 on day 0 + near tile'][0], s)[1] - play(OURS['V13 now (d10 from h10)'][0], s)[1]) for s in by[k]]):+.0f} (n={len(by[k])})"
            for k in top))


if __name__ == "__main__":
    main()

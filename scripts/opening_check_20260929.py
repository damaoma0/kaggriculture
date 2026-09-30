"""Opening validity on random seeds, first days only (user 2026-09-29: "For your fixes just run random seeds on first few
days to check validity"). Each game runs through kaggle_environments with episodeSteps = STEPS (default 200, i.e. to day
8), our packaged agent in one seat and the opponent package in the other; one process per game.

Per game (our seat): cash at the day-1 dawn, most hands on day 1, sheep and the wool on them at the day-6 dawn (before
the day-6 harvest), cash at the dawn of days 6 / 7 / 8, quadrants at the end.

usage: opening_check_20260929.py --pkg DIR [--pkg DIR ...] --opp DIR [--n 12] [--seed0 20260929] [--steps 200]
       [--workers 4] [--out FILE.json]"""
import argparse
import json
import random
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def play(args):
    pkg, opp, seed, seat, steps_n = args
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"episodeSteps": steps_n, "actTimeout": 1}, info={"seed": seed})
    agents = [str(Path(opp) / "main.py")] * 2
    agents[seat] = str(Path(pkg) / "main.py")
    steps = env.run(agents)

    def farm(t):
        t = min(t, len(steps) - 1)
        return steps[t][0]["observation"]["farms"][seat]

    def sheep(t):
        n = y = 0
        for row in farm(t)["tiles"]:
            for x in row:
                if isinstance(x, dict) and x.get("animal") == "SHEEP":
                    n += 1
                    y += int(x.get("yield_units", 0) or 0)
        return n, y
    n6, w6 = sheep(144)
    return dict(pkg=Path(pkg).parent.name, seed=seed, seat=seat, n_steps=len(steps),
                status=steps[-1][seat]["status"],
                cash_d1=farm(24)["money"], hands_d1=max(len(farm(t)["hands"]) for t in range(25, 48)),
                sheep_d6=n6, wool_d6=w6, cash_d6=farm(144)["money"], cash_d7=farm(168)["money"], cash_d8=farm(192)["money"],
                quads=len(farm(len(steps) - 1).get("unlocked_quadrants", [])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", action="append", required=True)
    ap.add_argument("--opp", required=True)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed0", type=int, default=20260929)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out")
    a = ap.parse_args()
    rng = random.Random(a.seed0)
    seeds = [rng.randrange(1, 2 ** 31 - 1) for _ in range(a.n)]
    jobs = [(p, a.opp, s, seat, a.steps) for s in seeds for seat in (0, 1) for p in a.pkg]
    rows = []
    with ProcessPoolExecutor(max_workers=a.workers, max_tasks_per_child=1) as pool:
        for r in pool.map(play, jobs):
            rows.append(r)
            print(json.dumps(r), flush=True)
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=1))
    for p in a.pkg:
        name = Path(p).parent.name
        rs = [r for r in rows if r["pkg"] == name]
        n = len(rs)
        f = lambda k: sum(r[k] for r in rs) / n
        print(f"{name}: {n} games | day-1 dawn cash {f('cash_d1'):.1f} (<4 in {sum(1 for r in rs if r['cash_d1'] < 4)}) | day-1 hands "
              f"{f('hands_d1'):.2f} (<3 in {sum(1 for r in rs if r['hands_d1'] < 3)}) | wool on sheep day 6 {f('wool_d6'):.1f} "
              f"(sheep {f('sheep_d6'):.1f}; <18 in {sum(1 for r in rs if r['wool_d6'] < 18)}) | cash d6/d7/d8 {f('cash_d6'):.0f} / "
              f"{f('cash_d7'):.0f} / {f('cash_d8'):.0f} | quadrants {f('quads'):.2f} | status {sorted(set(r['status'] for r in rs))}")


if __name__ == "__main__":
    main()

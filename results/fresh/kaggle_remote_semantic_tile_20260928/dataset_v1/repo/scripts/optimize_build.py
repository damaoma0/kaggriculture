"""Offline search over plan_v1's build-order parameters against a fixed opponent.

Each candidate is a dict of overrides applied to plan_v1.BUILD. It is written to a temp agent
file and evaluated on paired seeds (both seats). Score = mean margin vs the opponent, with wins
weighted (the ladder counts wins only). Results are appended to results/optimize_build.jsonl.

Usage:
    python scripts/optimize_build.py --iters 60 --seeds 6 --workers 6
"""
import argparse
import json
import random
import re
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "agents" / "plan_v1.py"
TMP = ROOT / "agents" / "_opt"
OPP = str(ROOT / "agents" / "public" / "tschinkel_router_v31.py")

SPACE = {
    "melon": [8, 10, 12, 14, 16],
    "cow_final": [7, 8, 9, 10, 11],
    "sheep_final": [3, 4, 5, 6, 7],
    "straw_final": [24, 28, 33, 36, 40],
    "straw_last_plant_day": [11, 12, 13, 14],
    "carrot_from_day": [20, 22, 24],
    "land2_day": [9, 10, 11, 12],
    "sell_frac": [0.35, 0.45, 0.5, 0.6],
    "hold_days": [2, 3, 4, 6],
    "opening_hands": [4, 5, 6, 7],
    "wheat_opening": [5, 7, 9],
}


def render(cand):
    src = SRC.read_text(encoding="utf-8")
    c = cand
    cows = {0: 2, 2: 3, 3: 4, 6: min(6, c["cow_final"]), 7: min(8, c["cow_final"]), 8: c["cow_final"]}
    sheep = {0: 2, 8: min(4, c["sheep_final"]), 11: c["sheep_final"]}
    sf = c["straw_final"]
    straw = {4: 4, 5: 8, 6: 12, 7: 16, 8: 20, 11: sf} if sf >= 20 else {4: 4, 5: 8, 6: 12, 7: 16, 8: sf}
    land = {6: 1, c["land2_day"]: 2}
    hands = "[%d, 4, 4, 5, 4, 5, 8, 8, 10, 9, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 9]" % c["opening_hands"]
    reps = {
        r'"melon": \d+,': '"melon": %d,' % c["melon"],
        r'"cows":\s*\{[^}]*\},': '"cows": %r,' % cows,
        r'"sheep":\s*\{[^}]*\},': '"sheep": %r,' % sheep,
        r'"straw":\s*\{[^}]*\},': '"straw": %r,' % straw,
        r'"land":\s*\{[^}]*\},': '"land": %r,' % land,
        r'"hands":\s*\[[^\]]*\],': '"hands": %s,' % hands,
        r'"wheat_opening": \d+,': '"wheat_opening": %d,' % c["wheat_opening"],
        r'"straw_last_plant_day": \d+,': '"straw_last_plant_day": %d,' % c["straw_last_plant_day"],
        r'"carrot_from_day": \d+,': '"carrot_from_day": %d,' % c["carrot_from_day"],
        r'"sell_frac": [\d.]+,': '"sell_frac": %s,' % c["sell_frac"],
        r'"hold_days": \d+,': '"hold_days": %d,' % c["hold_days"],
    }
    for pat, rep in reps.items():
        src, n = re.subn(pat, rep, src, count=1, flags=re.S)
        assert n == 1, pat
    return src


def play(path, seed, seat):
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    env.run([path, OPP] if seat == 0 else [OPP, path])
    f = env.steps[-1]
    me, op = (f[0], f[1]) if seat == 0 else (f[1], f[0])
    return float(me.reward or 0) - float(op.reward or 0), me.status


def evaluate(cand, seeds, workers, tag):
    TMP.mkdir(exist_ok=True)
    path = TMP / f"cand_{tag}.py"
    path.write_text(render(cand), encoding="utf-8")
    jobs = [(str(path), s, seat) for s in seeds for seat in (0, 1)]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(play, *zip(*jobs)))
    margins = [r[0] for r in res]
    errors = sum(1 for r in res if r[1] != "DONE")
    wins = sum(1 for m in margins if m > 0)
    mean = sum(margins) / len(margins)
    score = mean + 4000 * wins / len(margins) - 1e6 * errors
    return {"mean_margin": mean, "wins": wins, "games": len(margins), "errors": errors, "score": score}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=40)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    seeds = [args.seed_base + i for i in range(args.seeds)]
    out = ROOT / "results" / "optimize_build.jsonl"
    out.parent.mkdir(exist_ok=True)

    base = {"melon": 12, "cow_final": 9, "sheep_final": 5, "straw_final": 33, "straw_last_plant_day": 13,
            "carrot_from_day": 22, "land2_day": 11, "sell_frac": 0.5, "hold_days": 4, "opening_hands": 5,
            "wheat_opening": 7}
    rng = random.Random(1)
    best, best_score = base, None
    for it in range(args.iters):
        if it == 0:
            cand = dict(base)
        else:
            cand = dict(best)
            for k in rng.sample(list(SPACE), k=rng.choice([1, 1, 2, 3])):
                cand[k] = rng.choice(SPACE[k])
        t0 = time.time()
        r = evaluate(cand, seeds, args.workers, it)
        r.update({"iter": it, "cand": cand, "secs": round(time.time() - t0)})
        with out.open("a") as f:
            f.write(json.dumps(r) + "\n")
        improved = best_score is None or r["score"] > best_score
        if improved:
            best, best_score = cand, r["score"]
        print(f"[{it}] mean={r['mean_margin']:.0f} wins={r['wins']}/{r['games']} err={r['errors']} "
              f"{'*BEST*' if improved else ''} {cand}", flush=True)
    print("best:", best, best_score)


if __name__ == "__main__":
    main()

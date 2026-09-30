"""Paired-seed, both-seat evaluation of one candidate agent against one or more opponents.

Usage:
    python scripts/eval.py agents/baseline.py agents/public/tschinkel_router_v31.py starter \
        --seeds 10 --workers 4

The first path is the candidate. Every following argument is an opponent (a .py path or a
built-in name: starter, random, pass). Each seed is played twice, with the candidate in seat 0
and in seat 1, so seat bias and market order cancel. Results print per opponent and are saved
as JSON under results/.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def play(candidate, opponent, seed, seat):
    """Run one game. Returns dict with banks, winner from candidate's view, statuses."""
    from kaggle_environments import make

    env = make("kaggriculture", configuration={"seed": seed}, debug=False)
    players = [candidate, opponent] if seat == 0 else [opponent, candidate]
    t0 = time.time()
    env.run(players)
    final = env.steps[-1]
    me, opp = (final[0], final[1]) if seat == 0 else (final[1], final[0])
    my_bank, opp_bank = float(me.reward or 0), float(opp.reward or 0)
    result = "W" if my_bank > opp_bank else "L" if my_bank < opp_bank else "T"
    return {
        "opponent": opponent, "seed": seed, "seat": seat, "result": result,
        "my_bank": my_bank, "opp_bank": opp_bank, "margin": my_bank - opp_bank,
        "my_status": me.status, "opp_status": opp.status, "secs": round(time.time() - t0, 1),
    }


def summarize(rows):
    by_opp = {}
    for r in rows:
        d = by_opp.setdefault(r["opponent"], {"W": 0, "L": 0, "T": 0, "margins": [],
                                               "seat0": [0, 0, 0], "seat1": [0, 0, 0],
                                               "errors": 0})
        d[r["result"]] += 1
        d["margins"].append(r["margin"])
        d["seat%d" % r["seat"]]["WLT".index(r["result"])] += 1
        if r["my_status"] != "DONE":
            d["errors"] += 1
    return by_opp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("opponents", nargs="+")
    ap.add_argument("--seeds", type=int, default=5, help="number of seeds (each played both seats)")
    ap.add_argument("--seed-base", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--tag", default=None, help="label for the results file")
    args = ap.parse_args()

    seeds = [args.seed_base + i for i in range(args.seeds)]
    jobs = [(args.candidate, opp, s, seat) for opp in args.opponents for s in seeds for seat in (0, 1)]
    print(f"{len(jobs)} games, {args.workers} workers", flush=True)

    rows = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(play, *j) for j in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            rows.append(r)
            print(f"[{i}/{len(jobs)}] {r['result']} vs {Path(r['opponent']).stem} seed={r['seed']} "
                  f"seat={r['seat']} {r['my_bank']:.0f} vs {r['opp_bank']:.0f} ({r['secs']}s)",
                  flush=True)

    print(f"\ncandidate: {args.candidate}   ({time.time() - t0:.0f}s total)")
    print(f"{'opponent':40s} {'W-L-T':>9s} {'win%':>6s} {'mean margin':>12s} {'worst':>9s} "
          f"{'seat0':>7s} {'seat1':>7s} {'err':>4s}")
    summary = summarize(rows)
    for opp, d in summary.items():
        n = d["W"] + d["L"] + d["T"]
        print(f"{Path(opp).stem:40s} {d['W']}-{d['L']}-{d['T']:<5d} {100 * d['W'] / n:5.1f}% "
              f"{sum(d['margins']) / n:12.0f} {min(d['margins']):9.0f} "
              f"{'-'.join(map(str, d['seat0'])):>7s} {'-'.join(map(str, d['seat1'])):>7s} "
              f"{d['errors']:4d}")

    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    tag = args.tag or Path(args.candidate).stem
    out = out_dir / f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}.json"
    out.write_text(json.dumps({"candidate": args.candidate, "args": vars(args), "games": rows},
                              indent=1))
    print(f"saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

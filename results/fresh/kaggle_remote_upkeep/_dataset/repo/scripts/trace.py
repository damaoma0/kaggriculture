"""Play one game and print a per-day summary of the candidate's farm, for debugging.

Usage: python scripts/trace.py agents/greedy_v1.py [opponent] [--seed N] [--seat 0|1]
"""
import argparse
import importlib.util
import json
import sys
import traceback
from pathlib import Path

from kaggle_environments import make


def load_agent(path):
    spec = importlib.util.spec_from_file_location("cand", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("opponent", nargs="?", default="starter")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--replay", default=None, help="write replay JSON here")
    args = ap.parse_args()

    inner = load_agent(args.candidate)
    errors = []

    def wrapped(obs):
        try:
            return inner(obs)
        except Exception:
            errors.append((obs.get("step"), traceback.format_exc()))
            raise

    env = make("kaggriculture", configuration={"seed": args.seed}, debug=True)
    players = [wrapped, args.opponent] if args.seat == 0 else [args.opponent, wrapped]
    env.run(players)

    me = args.seat
    print(f"{'day':>3} {'money':>8} {'opp$':>8} {'plants':>6} {'anim':>4} {'hands':>5} "
          f"{'weeds':>5} {'quads':>5}  shed")
    for step_states in env.steps:
        obs = step_states[0].observation
        step = obs["step"]
        if step % 24 != 12:
            continue
        farm = obs["farms"][me]
        opp = obs["farms"][1 - me]
        priv = step_states[me].observation["private"]
        plants = animals = weeds = 0
        for row in farm["tiles"]:
            for t in row:
                if isinstance(t, dict):
                    if t.get("kind") == "PLANT":
                        plants += 1
                    elif t.get("kind") == "WEED":
                        weeds += 1
                    elif "animal" in t:
                        animals += 1
        shed = {k: v for k, v in priv["shed"].items() if v}
        print(f"{step // 24:3d} {farm['money']:8.0f} {opp['money']:8.0f} {plants:6d} {animals:4d} "
              f"{len(farm['hands']):5d} {weeds:5d} {len(farm['unlocked_quadrants']):5d}  {shed}")
    final = env.steps[-1]
    print("final:", [(i, s.reward, s.status) for i, s in enumerate(final)])
    if errors:
        print(f"\n{len(errors)} agent exceptions; first:")
        print(errors[0][1])
    if args.replay:
        Path(args.replay).write_text(json.dumps(env.toJSON()))


if __name__ == "__main__":
    main()

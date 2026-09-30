"""Compare fresh opening policies at days 3, 6, 9; no endgame inference.

Screening uses starter; validation uses a reacting local reference opponent.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
OPPONENT = str(ROOT / "agents/public/tschinkel_router_v31.py")


def candidates():
    rows = []
    for crop, age in [("WHEAT", 2), ("WHEAT", 4), ("CARROT", 3)]:
        for land in [0, 3, 99]:
            rows.append((f"{crop.lower()}{age}-land{land}", {"cash_crop": crop, "harvest_age": age,
                        "animals": [], "melons": 0, "land_day": land, "hands": 6}))
    for name, animals in [("goose4", ["GOOSE"] * 4), ("cow4", ["COW"] * 4),
                          ("sheep4", ["SHEEP"] * 4), ("mixed4", ["COW"] * 2 + ["SHEEP"] * 2)]:
        for melons in [0, 8]:
            rows.append((f"{name}-melon{melons}", {"animals": animals, "melons": melons}))
    rows += [("melon16", {"animals": [], "melons": 16}),
             ("mixed-expand", {"land_day": 3}),
             ("mixed-strawberry", {"strawberries": 8, "strawberry_day": 4}),
             ("mixed-hands4", {"hands": 4}), ("mixed-hands8", {"hands": 8})]
    rows += [("sheep6", {"animals": ["SHEEP"] * 6, "melons": 0}),
             ("sheep8", {"animals": ["SHEEP"] * 8, "melons": 0}),
             ("mixed6", {"animals": ["COW"] * 3 + ["SHEEP"] * 3, "melons": 0}),
             ("mixed8", {"animals": ["COW"] * 4 + ["SHEEP"] * 4, "melons": 0}),
             ("wheat2-hands8", {"animals": [], "melons": 0, "harvest_age": 2, "hands": 8}),
             ("wheat2-expand-hands10", {"animals": [], "melons": 0, "harvest_age": 2, "hands": 10, "land_day": 0}),
             ("wheat4-hands8", {"animals": [], "melons": 0, "hands": 8}),
             ("carrot3-hands8", {"animals": [], "melons": 0, "cash_crop": "CARROT", "harvest_age": 3, "hands": 8})]
    return rows


def load_policy():
    spec = importlib.util.spec_from_file_location("fresh_opening", ROOT / "agents/opening_v1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def snapshot(states, seat, module):
    obs = states[seat].observation
    shared = states[0].observation
    farm = shared["farms"][seat]
    crops, animals = Counter(), Counter()
    cohorts = Counter()
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT":
                crops[tile["crop"]] += 1
                cohorts[f"{tile['crop']} planted day {tile['planted_day']}"] += 1
            if tile.get("animal"):
                animals[tile["animal"]] += 1
    land_cost = {1: 0, 2: 1000, 3: 3000, 4: 7000}[len(farm["unlocked_quadrants"])]
    crop_cost = sum(module.SEED_COST.get(c, 0) * n for c, n in crops.items())
    animal_cost = sum(module.ANIMAL_COST[c] * n for c, n in animals.items())
    return {"step": shared["step"], "cash": farm["money"],
            "opponent_cash": shared["farms"][1-seat]["money"], "crops": dict(crops),
            "cohorts": dict(cohorts), "animals": dict(animals), "quadrants": farm["unlocked_quadrants"],
            "shed": obs["private"]["shed"], "seeds": obs["private"]["seeds"],
            "shops": shared["town"]["unlocked_shops"],
            "cash_plus_installed_cost": farm["money"] + land_cost + crop_cost + animal_cost}


def play(job):
    name, config, seed, seat, opponent, save_path = job
    from kaggle_environments import make
    module = load_policy()
    controller = module.OpeningPolicy(config)
    decision_times = []
    def policy(obs):
        t0 = time.perf_counter()
        action = controller(obs)
        decision_times.append(time.perf_counter() - t0)
        return action
    # 217 recorded states executes steps 0..215, ending exactly at day 9.
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 217}, debug=False)
    players = [policy, opponent] if seat == 0 else [opponent, policy]
    start = time.perf_counter()
    env.run(players)
    statuses = [s.status for s in env.steps[-1]]
    if len(env.steps) != 217 or statuses != ["DONE", "DONE"]:
        raise RuntimeError(f"{name}: incomplete episode {len(env.steps)}, {statuses}")
    if any(s.status not in ("ACTIVE", "DONE") for states in env.steps for s in states):
        raise RuntimeError(f"{name}: an agent failed during the episode")
    stats = Counter()
    for before, after in zip(env.steps, env.steps[1:]):
        previous = before[0].observation["farms"][seat]
        current = after[0].observation["farms"][seat]
        action = after[seat].action
        for a in [action["farmer"], *action["hands"]]:
            stats[a[0]] += 1
        for y in range(10):
            for x in range(10):
                old, new = previous["tiles"][y][x], current["tiles"][y][x]
                if isinstance(old, dict) and isinstance(new, dict):
                    if old.get("kind") == "PLANT" and new.get("kind") == "WEED":
                        stats["crop_losses"] += 1
                    if old.get("animal") and not new.get("animal"):
                        stats["animal_losses"] += 1
    result = {"name": name, "config": controller.config, "seed": seed, "seat": seat,
              "opponent": opponent, "seconds": round(time.perf_counter()-start, 2), "actions": dict(stats),
              "max_decision_ms": max(decision_times) * 1000,
              "checkpoints": {str(d): snapshot(env.steps[d*24], seat, module) for d in (3, 6, 9)},
              "opponent_checkpoints": {str(d): snapshot(env.steps[d*24], 1-seat, module) for d in (3, 6, 9)}}
    if save_path:
        p = Path(save_path)
        p.mkdir(parents=True, exist_ok=False)
        (p / "replay.json").write_text(json.dumps(env.toJSON()), encoding="utf-8")
        (p / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        lines = ["# Opening moves", "", f"Policy: {name}; seed {seed}; seat {seat}.", "",
                 "Actions are requests. Check their results in replay.json. Day/hour are zero-based.", ""]
        for t, states in enumerate(env.steps[1:]):
            if t % 24 == 0:
                lines += [f"## Day {t//24}", "", "| Hour | Farmer | Hands | Market orders |", "|---:|---|---|---|"]
            a = states[seat].action
            lines.append(f"| {t%24} | `{a['farmer']}` | `{a['hands']}` | `{a['market']}` |")
        (p / "moves.md").write_text("\n".join(lines), encoding="utf-8")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["screen", "validate", "record"], default="screen")
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--seed-base", type=int, default=20261001)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", type=Path, default=ROOT / "results/fresh/openings")
    args = ap.parse_args()
    selected = [(n, c) for n, c in candidates() if not args.names or n in args.names]
    if not selected:
        raise SystemExit("No matching policies")
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = [(n, c, args.seed_base+s, seat, "starter" if args.stage == "screen" else OPPONENT,
             str(args.out / f"{n}-seed{args.seed_base+s}-seat{seat}") if args.stage == "record" else None)
            for n, c in selected for s in range(args.seeds) for seat in ([0] if args.stage == "screen" else [0, 1])]
    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(play, job) for job in jobs]
        for i, f in enumerate(as_completed(futures)):
            r = f.result()
            results.append(r)
            c = r["checkpoints"]["9"]
            print(f"{i+1}/{len(jobs)} {r['name']} seed={r['seed']} seat={r['seat']} "
                  f"cash={c['cash']:.0f} installed={c['cash_plus_installed_cost']:.0f} "
                  f"losses={r['actions'].get('crop_losses',0)}/{r['actions'].get('animal_losses',0)}", flush=True)
            (args.out / f"{args.stage}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

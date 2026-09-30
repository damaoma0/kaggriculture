"""Select openings by full-season cash margin under a frozen continuation."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
import time

from evaluate_boards import ROOT, Ledger, continuation, module_at, observation, restored_env, root_features


def candidates():
    variants = {"control-sheep6": None}
    for cows, sheep in ((6, 4), (8, 4), (10, 2), (6, 6)):
        for melons in (0, 8, 12):
            variants[f"c{cows}s{sheep}-m{melons}"] = {"cows": cows, "sheep": sheep, "melons": melons}
    variants.update({
        "early-straw": {"melons": 8, "strawberry_day": 1, "land_day": 1},
        "early-land": {"land_day": 1},
        "lean-crew": {"hands": 6, "late_hands": 8},
        "large-crew": {"hands": 10, "late_hands": 12},
        "slow-herd": {"grow_day": 3, "grow_every": 2},
        "small-herd": {"cows": 4, "sheep": 4},
    })
    return variants


def play(job):
    name, cfg, seed, future, seat, mode, save = job[:7]
    opponent_mode = job[7] if len(job) > 7 else "router"
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine
    started = time.perf_counter()
    if name.startswith("shop-"):
        module = module_at("shop_opening", ROOT / "agents/shop_opening.py")
        policy = module.ShopOpening(cfg)
        used_cfg = cfg
    elif name.startswith("route-"):
        module = module_at("router_variant", ROOT / "agents/router_opening_variant.py")
        policy = module.RouterOpeningVariant(cfg)
        used_cfg = cfg
    elif name == "reactive-copy":
        module = module_at("reactive_copy", ROOT / "agents/reactive_copy.py")
        policy = module.CopyPolicy()
        used_cfg = {"copy": "public live tiles", "hands_cap": 12, "land_buffer": 300}
    elif name == "public-router":
        module = module_at("own_public_router", ROOT / "agents/public/tschinkel_router_v31.py")
        policy = module.Agent().act
        used_cfg = {"opening": "public-router"}
    elif cfg is None:
        module = module_at("old_opening", ROOT / "agents/opening_v1.py")
        policy = module.OpeningPolicy(module.SELECTED_OPENING)
        used_cfg = dict(module.SELECTED_OPENING)
    else:
        module = module_at("growth_opening", ROOT / "agents/opening_v2.py")
        policy = module.GrowthOpening(cfg)
        used_cfg = dict(policy.growth)
    router = module_at("router", ROOT / "agents/public/tschinkel_router_v31.py")
    decision_times = []
    first_product_sale = None
    opening_ledger = None
    def ours(obs):
        nonlocal first_product_sale
        if opening_ledger is not None and first_product_sale is None:
            if any(n for p,n in opening_ledger.data[seat]["sold_units"].items() if p != "FERTILIZER"):
                first_product_sale = obs["step"]-1
        t = time.perf_counter()
        action = policy(obs)
        decision_times.append(time.perf_counter()-t)
        demand = Counter(a[1] for a in [action["farmer"], *action["hands"]] if a[0] == "PLANT")
        if name != "public-router" and not name.startswith(("route-", "shop-")):
            assert all(n <= obs["private"]["seeds"].get(c, 0) for c, n in demand.items())
        return action
    opening = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 217})
    with Ledger(engine) as opening_ledger:
        opening.run([ours, router.agent] if seat == 0 else [router.agent, ours])
    assert len(opening.steps) == 217
    assert all(s.status in ("ACTIVE", "DONE") for states in opening.steps for s in states)
    replay = opening.toJSON()
    opening_accounts = opening_ledger.data
    opening_ledger = None
    obs = observation(replay["steps"][-1], seat)
    losses = Counter()
    for before, after in zip(opening.steps, opening.steps[1:]):
        for y in range(10):
            for x in range(10):
                a, b = before[0].observation.farms[seat]["tiles"][y][x], after[0].observation.farms[seat]["tiles"][y][x]
                if isinstance(a, dict) and isinstance(b, dict):
                    losses["crop"] += a.get("kind") == "PLANT" and b.get("kind") == "WEED"
                    losses["animal"] += bool(a.get("animal")) and not b.get("animal")
    # Keep the SAME router instance: its opening memory is already initialized.
    # All candidates receive the same evaluator controller after day 9.
    if mode == "copy":
        tail = ours
    elif mode == "router":
        if name == "public-router":
            tail = ours
        else:
            handoff = module_at("handoff_router", ROOT / "agents/public/tschinkel_router_v31.py")
            assert min(d[0] for d in handoff.DECISIONS) > 216
            # No routing branch occurs before the handoff. The only other
            # persistent state is a route-derived sales cache, rebuilt lazily.
            router_policy = handoff.Agent()
            def tail(obs):
                return router_policy.act(obs)  # Do not swallow exceptions.
    else:
        tail = continuation(mode, 10, obs, engine)
    env = restored_env(replay, 216, future)
    opponent_tail = router.agent if opponent_mode == "router" else continuation(
        opponent_mode, 10, observation(replay["steps"][-1], 1-seat), engine)
    initial_cash = [f["money"] for f in env.state[0].observation.farms]
    with Ledger(engine) as ledger:
        env.run([tail, opponent_tail] if seat == 0 else [opponent_tail, tail])
    assert len(env.steps) == 720
    assert all(s.status in ("ACTIVE", "DONE") for states in env.steps[216:] for s in states)
    final_cash = [s.reward for s in env.steps[-1]]
    for i in range(2):
        account = ledger.data[i]
        assert final_cash[i] == initial_cash[i] + sum(account["revenue"].values()) - sum(account["spend"].values())
    tail_losses = Counter()
    for before, after in zip(env.steps[216:], env.steps[217:]):
        day = before[0].observation.day
        for y in range(10):
            for x in range(10):
                a = before[0].observation.farms[seat]["tiles"][y][x]
                b = after[0].observation.farms[seat]["tiles"][y][x]
                if not isinstance(a, dict):
                    continue
                if a.get("animal") and not (isinstance(b, dict) and b.get("animal")):
                    tail_losses["animal"] += 1
                if a.get("kind") == "PLANT" and isinstance(b, dict) and b.get("kind") == "WEED":
                    cd = engine.CROPS[a["crop"]]
                    expiry = a["planted_day"] + (cd["first_yield_day"] + 3*cd["interval"] if cd["ongoing"] else cd["max_yield_day"])
                    if day < expiry:
                        tail_losses["premature_crop"] += 1
    row = {"name": name, "config": used_cfg, "seed": seed, "future_seed": future, "seat": seat,
           "first_product_sale_step": first_product_sale, "opening_accounts": opening_accounts,
           "day1_cash": opening.steps[24][0].observation.farms[seat]["money"],
           "tail_losses": dict(tail_losses), "opponent_continuation": opponent_mode,
           "continuation": mode, "day9": root_features(obs, engine), "opening_losses": dict(losses),
           "our_final": final_cash[seat], "router_final": final_cash[1-seat],
           "margin": final_cash[seat] - final_cash[1-seat], "max_opening_ms": 1000*max(decision_times),
           "checkpoints": {str(d): {"ours": env.steps[d*24][0].observation.farms[seat]["money"],
                                     "router": env.steps[d*24][0].observation.farms[1-seat]["money"]} for d in (3, 6, 9, 12, 15, 20, 25, 29)},
           "seconds": time.perf_counter()-started}
    if save:
        p = Path(save)
        p.mkdir(parents=True, exist_ok=False)
        (p / "opening.json").write_text(json.dumps(replay), encoding="utf-8")
        (p / "full_replay.json").write_text(json.dumps(env.toJSON()), encoding="utf-8")
        (p / "summary.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        lines = [f"# {name}: opening moves", "", f"Seed {seed}, seat {seat}; zero-based day/hour.", ""]
        for t, states in enumerate(opening.steps[1:]):
            if t % 24 == 0:
                lines += [f"## Day {t//24}", "", "| Hour | Farmer | Hands | Market |", "|---:|---|---|---|"]
            a = states[seat].action
            lines.append(f"| {t%24} | `{a['farmer']}` | `{a['hands']}` | `{a['market']}` |")
        (p / "moves.md").write_text("\n".join(lines), encoding="utf-8")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=("smoke", "screen", "validate", "record"), default="smoke")
    ap.add_argument("--names", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", type=Path, default=ROOT / "results/fresh/growth_opening")
    args = ap.parse_args()
    variants = {n:c for n,c in candidates().items() if not args.names or n in args.names}
    if args.stage == "smoke" and not args.names:
        variants = {n:c for n,c in variants.items() if n in ("control-sheep6", "c8s4-m12", "c10s2-m8")}
    if args.stage in ("smoke", "screen"):
        scenarios = [(s, f, 0, "replant") for s,f in [(86001,96001), (86002,96002)][:1 if args.stage == "smoke" else 2]]
    elif args.stage == "validate":
        scenarios = [(s, f, seat, mode) for s,f in ((86101,96101), (86102,96102), (86103,96103), (86104,96104))
                     for seat in (0,1) for mode in ("maintain", "replant")]
    else:
        scenarios = [(86201,96201,seat,"replant") for seat in (0,1)]
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = [(n,c,s,f,seat,mode,str(args.out/f"{n}-{s}-seat{seat}") if args.stage == "record" else None)
            for n,c in variants.items() for s,f,seat,mode in scenarios]
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, future in enumerate(as_completed([pool.submit(play, j) for j in jobs])):
            r = future.result()
            rows.append(r)
            print(f"{i+1}/{len(jobs)} {r['name']} {r['continuation']} seat={r['seat']} seed={r['seed']} "
                  f"cash9={r['day9']['cash']:.0f} final={r['our_final']:.0f} margin={r['margin']:+.0f} losses={r['opening_losses']}", flush=True)
            (args.out/f"{args.stage}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for name in variants:
        group = [r for r in rows if r["name"] == name]
        print(name, "mean final", round(mean(r["our_final"] for r in group)), "mean margin", round(mean(r["margin"] for r in group)))
    (args.out/f"{args.stage}-manifest.json").write_text(json.dumps({"candidates": variants,
        "hashes": {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in
                   [ROOT/"agents/opening_v2.py",ROOT/"agents/opening_v1.py",ROOT/"scripts/evaluate_boards.py",Path(__file__)]}}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

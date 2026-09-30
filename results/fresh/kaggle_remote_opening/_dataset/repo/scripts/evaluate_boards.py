"""Offline full-state board valuation through official-engine continuations.

No purchase-cost bonus is added to terminal cash. All futures are synthetic and
invisible to policies. This is a policy/scenario-conditioned value, not V*.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import importlib.util
from importlib.metadata import version
import itertools
import json
import math
from pathlib import Path
from statistics import mean
import time

ROOT = Path(__file__).resolve().parents[1]
MODES = ("maintain", "replant", "expand")
SHARED = ("step", "day", "hour", "farms", "market", "town")


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=8)
def read_replay(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def observation(states, seat):
    obs = deepcopy(states[seat]["observation"])
    for key in SHARED:
        obs[key] = deepcopy(states[0]["observation"][key])
    return obs


def restored_env(replay, step, future_seed):
    from kaggle_environments import make
    prefix = deepcopy(replay["steps"][:step + 1])
    for state in prefix[-1]:
        state["status"] = "ACTIVE"
        state["reward"] = None
    cfg = dict(replay["configuration"], episodeSteps=720, seed=None)
    env = make("kaggriculture", configuration=cfg, info={"seed": future_seed}, steps=prefix)
    assert len(env.steps) == step + 1 and env.state[0].observation.step == step
    assert not env.done
    assert env.state[0].observation.farms == prefix[-1][0]["observation"]["farms"]
    return env


def continuation(mode, cap, initial, engine):
    base = module_at("valuation_opening", ROOT / "agents/opening_v1.py")
    initial_farm = initial["farms"][initial["player"]]
    slots = {(x, y): tile.get("animal") or tile.get("crop")
             for y, row in enumerate(initial_farm["tiles"]) for x, tile in enumerate(row)
             if isinstance(tile, dict) and (tile.get("animal") or tile.get("kind") == "PLANT")}
    if any(c == "TOMATO" for c in slots.values()):
        raise ValueError("The v1 continuation scheduler does not support tomato roots yet")

    class ServicePolicy(base.OpeningPolicy):
        def __init__(self):
            super().__init__({"animals": [], "melons": 0, "land_day": 99})
            self.crew_day = -1

        def layout(self, farm, day):
            result = {}
            for y, row in enumerate(farm["tiles"]):
                for x, tile in enumerate(row):
                    pos = (x, y)
                    if isinstance(tile, dict) and tile.get("animal"):
                        result[pos] = tile["animal"]
                    elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
                        result[pos] = tile["crop"]
                    elif mode != "maintain" and day <= 25 and tile != "LOCKED":
                        reusable = tile is None or isinstance(tile, dict) and tile.get("kind") == "WEED"
                        if reusable and (mode == "expand" or slots.get(pos) in engine.CROPS):
                            result[pos] = "WHEAT"
            return result

        def __call__(self, obs):
            farm = obs["farms"][obs["player"]]
            active = [t for row in farm["tiles"] for t in row if isinstance(t, dict)]
            self.config["animals"] = [t["animal"] for t in active if t.get("animal")]
            if self.crew_day != obs["day"]:
                animals = len(self.config["animals"])
                plants = sum(t.get("kind") == "PLANT" for t in active)
                empty_jobs = sum(v == "WHEAT" and (farm["tiles"][p[1]][p[0]] is None or
                                  farm["tiles"][p[1]][p[0]].get("kind") == "WEED")
                                 for p, v in self.layout(farm, obs["day"]).items())
                # A deliberately simple shared staffing rule, with a sensitivity
                # cap tested separately. It is not an optimized routing model.
                self.config["hands"] = min(cap, max(1, math.ceil((7*animals + 3*plants + 4*empty_jobs)/18)-1))
                self.crew_day = obs["day"]
            action = super().__call__(obs)
            if mode == "expand" and obs["day"] <= 18 and len(farm["unlocked_quadrants"]) < 3:
                cost = 1000 if len(farm["unlocked_quadrants"]) == 1 else 2000
                if farm["money"] >= cost + 1500 and len(action["market"]) < 10:
                    action["market"].append(["BUY_LAND"])
            if obs["step"] >= 712:
                actions = [action["farmer"], *action["hands"]]
                for i, (pos, inv) in enumerate(zip([farm["farmer"], *farm["hands"]], obs["private"]["inventories"])):
                    if sum(inv.get(p, 0) for p in engine.PRODUCTS):
                        goal = min(base.SHED, key=lambda p: base.distance(pos, p))
                        if base.distance(pos, goal) <= 718 - obs["step"]:
                            actions[i] = ["DROP"] if tuple(pos) == goal else base.move(pos, goal)
                action["farmer"], action["hands"] = actions[0], actions[1:]
                # Project only our legal unit actions, then sell the accessible
                # shed stock. This uses no opponent private state or action.
                projected_farm, projected_private = deepcopy(farm), deepcopy(obs["private"])
                for i, a in enumerate(actions):
                    engine._apply_unit_action(projected_farm, projected_private, i, a, 10, obs["day"], 24)
                action["market"] = [["SELL", p, n] for p, n in projected_private["shed"].items()
                                    if p in engine.PRODUCTS and n > 0][:10]
            return action

    policy = ServicePolicy()
    def call(obs):
        return policy(obs)
    return call


class Ledger:
    """Observe successful engine transactions; do not estimate from requests."""
    def __init__(self, engine):
        self.engine = engine
        self.data = [{"revenue": Counter(), "sold_units": Counter(), "spend": Counter()} for _ in range(2)]
        self.seats = {}

    def __enter__(self):
        e = self.engine
        self.original = {n: getattr(e, n) for n in ("_process_market", "_commit_unit", "_do_hire", "_do_buy_land")}
        def market(state, env):
            self.seats = {id(f): i for i, f in enumerate(state[0].observation.farms)}
            return self.original["_process_market"](state, env)
        def commit(op, item, price, farm, private, market, shed_capacity=100):
            result = self.original["_commit_unit"](op, item, price, farm, private, market, shed_capacity)
            if result:
                row = self.data[self.seats[id(farm)]]
                if op == "SELL":
                    row["revenue"][item] += price
                    row["sold_units"][item] += 1
                else:
                    row["spend"][op + ":" + item] += price
            return result
        def atomic(name, category):
            def run(farm, *args):
                before = farm["money"]
                result = self.original[name](farm, *args)
                self.data[self.seats[id(farm)]]["spend"][category] += before - farm["money"]
                return result
            return run
        e._process_market, e._commit_unit = market, commit
        e._do_hire = atomic("_do_hire", "HIRE")
        e._do_buy_land = atomic("_do_buy_land", "BUY_LAND")
        return self

    def __exit__(self, *exc):
        for name, value in self.original.items():
            setattr(self.engine, name, value)


def root_features(obs, engine):
    farm, private = obs["farms"][obs["player"]], obs["private"]
    liquidation = 0
    for product in engine.PRODUCTS:
        inv = obs["market"]["inventory"][product]
        for _ in range(private["shed"].get(product, 0)):
            price = engine.market_price(product, inv, obs["market"].get("params"))
            liquidation += price
            inv += price > 1
    crops, animals = Counter(), Counter()
    for row in farm["tiles"]:
        for tile in row:
            if isinstance(tile, dict):
                if tile.get("kind") == "PLANT":
                    crops[tile["crop"]] += 1
                if tile.get("animal"):
                    animals[tile["animal"]] += 1
    return {"cash": farm["money"], "shed_sale_value_no_other_trades": liquidation,
            "crops": dict(crops), "animals": dict(animals), "land_tiles": 25*len(farm["unlocked_quadrants"])}


def native_policies(replay, step):
    ours = module_at("native_opening", ROOT / "agents/opening_v1.py")
    router = module_at("native_router", ROOT / "agents/public/tschinkel_router_v31.py")
    policies = [ours.agent, router.agent]
    for t in range(step):
        for seat, policy in enumerate(policies):
            actual = policy(observation(replay["steps"][t], seat))
            assert actual == replay["steps"][t+1][seat]["action"], ("Native warmup mismatch", t, seat)
    return policies


def rollout(job):
    path, future_seed, modes, cap, save = job
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine
    replay = read_replay(path)
    step = len(replay["steps"]) - 1
    env = restored_env(replay, step, future_seed)
    initial = [observation(replay["steps"][step], seat) for seat in range(2)]
    native = native_policies(replay, step) if "native" in modes else None
    policies = [native[i] if modes[i] == "native" else continuation(modes[i], cap, initial[i], engine)
                for i in range(2)]
    start = time.perf_counter()
    with Ledger(engine) as ledger:
        env.run(policies)
    assert len(env.steps) == 720 and env.steps[-1][0].observation.step == 719
    assert all(s.status in ("ACTIVE", "DONE") for states in env.steps[step:] for s in states)
    final = env.steps[-1]
    cash = [s.reward for s in final]
    for i in range(2):
        account = ledger.data[i]
        calculated = initial[i]["farms"][i]["money"] + sum(account["revenue"].values()) - sum(account["spend"].values())
        assert calculated == cash[i], ("Ledger does not reconcile", i, calculated, cash[i])
    diagnostics = [Counter(), Counter()]
    for before, after in zip(env.steps[step:], env.steps[step+1:]):
        for i in range(2):
            a = after[i].action
            for op in [a["farmer"], *a["hands"]]:
                diagnostics[i][op[0]] += 1
            oldfarm, newfarm = before[0].observation.farms[i], after[0].observation.farms[i]
            day = before[0].observation.day
            for y in range(10):
                for x in range(10):
                    old, new = oldfarm["tiles"][y][x], newfarm["tiles"][y][x]
                    if not isinstance(old, dict) or not isinstance(new, dict):
                        continue
                    if old.get("animal") and not new.get("animal"):
                        diagnostics[i]["animal_losses"] += 1
                    if old.get("kind") == "PLANT" and new.get("kind") == "WEED":
                        cd = engine.CROPS[old["crop"]]
                        expiry = old["planted_day"] + (cd["first_yield_day"] + 3*cd["interval"] if cd["ongoing"] else cd["max_yield_day"])
                        diagnostics[i]["crop_transitions_to_weed"] += 1
                        if day < expiry:
                            diagnostics[i]["premature_crop_losses"] += 1
            diagnostics[i]["zero_cash_states"] += newfarm["money"] < 1
    terminal = []
    for i in range(2):
        p = final[i].observation.private
        terminal.append({"shed": p["shed"], "carried": p["inventories"], "seeds": p["seeds"]})
    row = {"root": Path(path).parent.name, "root_step": step, "future_seed": future_seed,
           "modes": modes, "crew_cap": cap, "seconds": round(time.perf_counter()-start, 2),
           "root_features": [root_features(o, engine) for o in initial], "final_cash": cash,
           "margin": cash[0]-cash[1], "ledger": ledger.data, "diagnostics": diagnostics,
           "terminal_inventory": terminal,
           "cash_path": {str(d): [env.steps[d*24][0].observation.farms[i]["money"] for i in range(2)] for d in (9, 12, 15, 20, 25, 29)}}
    if save:
        out = Path(save)
        out.mkdir(parents=True, exist_ok=True)
        (out / "replay.json").write_text(json.dumps(env.toJSON()), encoding="utf-8")
        (out / "summary.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=("smoke", "panel"), default="smoke")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", type=Path, default=ROOT / "results/fresh/board_value")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    roots = [str(ROOT / f"results/fresh/openings/sheep6-seed{seed}-seat0/replay.json") for seed in (20261201, 20261202, 20261203)]
    if args.stage == "smoke":
        jobs = [(roots[0], 84001, (m, m), 10, str(args.out / m)) for m in (*MODES, "native")]
    else:
        jobs = [(p, s, modes, 10, None) for p in roots for s in (84011, 84012, 84013) for modes in itertools.product((*MODES, "native"), repeat=2)]
        jobs += [(p, s, (m, m), cap, None) for p in roots for s in (84011, 84012, 84013)
                 for m in ("maintain", "replant") for cap in (6, 12)]
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, f in enumerate(as_completed([pool.submit(rollout, job) for job in jobs])):
            r = f.result()
            rows.append(r)
            print(f"{i+1}/{len(jobs)} {r['root']} {r['modes']} cap={r['crew_cap']} future={r['future_seed']} "
                  f"cash={r['final_cash']} premature={[d.get('premature_crop_losses',0) for d in r['diagnostics']]}", flush=True)
            (args.out / f"{args.stage}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    manifest = {"engine_version": version("kaggle-environments"),
                "files": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in
                          (ROOT / "scripts/evaluate_boards.py", ROOT / "agents/opening_v1.py", ROOT / "agents/public/tschinkel_router_v31.py")},
                "roots": {p: sha256(Path(p).read_bytes()).hexdigest() for p in roots},
                "scope": "Offline exact-private-state audit; synthetic future seeds; not a live belief-state evaluator"}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

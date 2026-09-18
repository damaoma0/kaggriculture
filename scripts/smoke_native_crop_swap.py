"""Two-game official-loader smoke test for native_crop_swap_overlay.py."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
import sys


SOURCE_ROOT = Path(r"C:\Users\xyygl\Documents\kaggriculture")
SITE = SOURCE_ROOT / ".venv" / "Lib" / "site-packages"
if str(SITE) not in sys.path:
    sys.path.insert(0, str(SITE))
ROOT = Path(__file__).resolve().parents[1]
BASE = SOURCE_ROOT / "agents" / "v45_event_opening_fixed.py"
OVERLAY = ROOT / "agents" / "native_crop_swap_overlay.py"
RIVAL = SOURCE_ROOT / "data" / "router_refresh_20260916" / "v45" / "main.py"
OUT = ROOT / "results" / "native_crop_swap_smoke.json"
SEED = 157900


def run(max_plots):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine

    source = BASE.read_text(encoding="utf-8") + "\n" + OVERLAY.read_text(encoding="utf-8")
    candidate = get_last_callable(source, path=str(BASE))
    rival = get_last_callable(RIVAL.read_text(encoding="utf-8"), path=str(RIVAL))
    candidate.__globals__["_SWAP_CONFIG"]["max_plots"] = max_plots
    assert candidate.__code__.co_filename == str(BASE)
    assert candidate.__code__.co_firstlineno > candidate.__globals__["_COHORT_PARENT"].__code__.co_firstlineno

    shops = random.Random(SEED ^ 0xA171).choices(sorted(engine.SHOPS), k=8)
    assert any(s in ("PET_CAFE", "FARMERS_MARKET") for s in shops[:4])
    env = make("kaggriculture", configuration={"seed": SEED, "episodeSteps": 720})
    original_end = engine._end_of_day
    original_apply = engine._apply_unit_action
    original_interpreter = env.interpreter
    original_process = engine._process_market
    original_commit = engine._commit_unit
    context = {"active": False, "step": -1, "seats": {}}
    actions = [[], []]
    actual = {"carrot_plants": 0, "carrot_harvest_units": 0,
              "carrot_sold_units": 0, "carrot_sale_revenue": 0}

    def end(state, environment, day):
        original_end(state, environment, day)
        unlocked = state[0].observation.town.unlocked_shops
        unlocked[:] = shops[:len(unlocked)]

    def interpreter(state, environment):
        context["active"] = True
        context["step"] = int(state[0].observation.step)
        context["seats"] = {id(f): i for i, f in enumerate(state[0].observation.farms)}
        try:
            return original_interpreter(state, environment)
        finally:
            context["active"] = False

    def apply(farm, private, idx, command, *args, **kwargs):
        if not context["active"] or context["seats"].get(id(farm)) != 0:
            return original_apply(farm, private, idx, command, *args, **kwargs)
        pos = engine._farmer_position(farm, idx)
        tile0 = deepcopy(farm["tiles"][pos[1]][pos[0]]) if pos is not None else None
        inv0 = deepcopy(private["inventories"][idx])
        value = original_apply(farm, private, idx, command, *args, **kwargs)
        tile1 = deepcopy(farm["tiles"][pos[1]][pos[0]]) if pos is not None else None
        inv1 = private["inventories"][idx]
        if (command[:2] == ["PLANT", "CARROT"] and tile0 is None
                and isinstance(tile1, dict) and tile1.get("crop") == "CARROT"):
            actual["carrot_plants"] += 1
        if (command and command[0] == "HARVEST" and isinstance(tile0, dict)
                and tile0.get("crop") == "CARROT"):
            actual["carrot_harvest_units"] += max(0, inv1.get("CARROT", 0) - inv0.get("CARROT", 0))
        return value

    def process(state, environment):
        context["seats"] = {id(f): i for i, f in enumerate(state[0].observation.farms)}
        return original_process(state, environment)

    def commit(op, item, price, farm, private, market, shed_capacity=100):
        ok = original_commit(op, item, price, farm, private, market, shed_capacity)
        if ok and context["seats"].get(id(farm)) == 0 and op == "SELL" and item == "CARROT":
            actual["carrot_sold_units"] += 1
            actual["carrot_sale_revenue"] += price
        return ok

    def wrap(agent, seat):
        def call(obs, configuration=None):
            action = agent(obs, configuration)
            assert isinstance(action, dict)
            actions[seat].append(action)
            return action
        return call

    engine._end_of_day = end
    engine._apply_unit_action = apply
    engine._process_market = process
    engine._commit_unit = commit
    env.interpreter = interpreter
    try:
        env.run([wrap(candidate, 0), wrap(rival, 1)])
    finally:
        engine._end_of_day = original_end
        engine._apply_unit_action = original_apply
        engine._process_market = original_process
        engine._commit_unit = original_commit
        env.interpreter = original_interpreter

    assert len(env.steps) == 720 and all(s.status == "DONE" for s in env.state)
    assert [len(a) for a in actions] == [719, 719]
    telemetry = {k: v for k, v in candidate.telemetry.items() if k.startswith("cohort_")}
    assert telemetry["cohort_contract_errors"] == 0, telemetry
    # The baseline itself later plants/harvests carrots, so engine totals are a
    # superset of overlay telemetry rather than an equality.
    assert 0 < telemetry["cohort_commitments"] <= actual["carrot_plants"], (telemetry, actual)
    assert 0 < telemetry["cohort_harvest_units"] <= actual["carrot_harvest_units"], (telemetry, actual)
    assert telemetry["cohort_expired_unharvested_yield"] == 0
    assert actual["carrot_sold_units"] > 0
    return {
        "seed": SEED,
        "max_plots": max_plots,
        "shops": shops,
        "cash": [s.reward for s in env.state],
        "margin": env.state[0].reward - env.state[1].reward,
        "action_calls": [len(a) for a in actions],
        "entrypoint_first_line": candidate.__code__.co_firstlineno,
        "telemetry": telemetry,
        "actual": actual,
    }


def main():
    rows = [run(2), run(4)]
    result = {
        "design": "Exactly two official-engine controlled-shop smoke games; appended source loaded through get_last_callable; corrected baseline seat 0 vs downloaded public V45 seat 1. Physical/contract test, not a strength comparison.",
        "sources": {
            "baseline": str(BASE), "baseline_sha256": sha256(BASE.read_bytes()).hexdigest(),
            "overlay": str(OVERLAY), "overlay_sha256": sha256(OVERLAY.read_bytes()).hexdigest(),
            "rival": str(RIVAL), "rival_sha256": sha256(RIVAL.read_bytes()).hexdigest(),
        },
        "games": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

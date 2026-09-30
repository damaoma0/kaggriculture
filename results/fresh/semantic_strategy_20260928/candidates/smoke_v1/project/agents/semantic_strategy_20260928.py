"""Research semantic strategy: observed opening -> counts -> tiles -> KB115LT.

This entrypoint reads only current observations and static learned artifacts.
It never receives a test-world recording, seed, episode, or future shop schedule.
The frozen benchmark snapshots its explicit dependency closure. It is not yet a
standalone competition submission; packaging follows successful development.
"""
from __future__ import annotations

import importlib.util as _importlib
import json as _json
from pathlib import Path as _Path
import sys as _sys
import time as _time

_ROOT = (_Path(__file__).resolve().parents[1] if "__file__" in globals()
         else _Path.cwd().resolve())
_sys.path.insert(0, str(_ROOT / "scripts"))
from semantic_strategy_policy_20260928 import SemanticStrategyPolicy as _Policy
from semantic_strategy_tiles_20260928 import build_plan as _build_plan, observe_own as _observe_own

_STUDY = _ROOT / "results/fresh/semantic_strategy_20260928"
_STATE = None
STRATEGY_DIAGNOSTICS = []


def _initialize():
    from semantic_strategy_opening_20260928 import make_opening
    runtime = _STUDY / "runtime"
    spec = _importlib.spec_from_file_location("_strategy_kb115lt", runtime / "agents/mgt_lead_kb115lt.py")
    kb = _importlib.module_from_spec(spec)
    spec.loader.exec_module(kb)
    recipe = _json.loads((_STUDY / "executor_recipe_online.json").read_text(encoding="utf-8"))
    kb.CFG.update(recipe)
    kb._TP_LEAK.clear()
    kb._TGT_EP = None
    config_file = _STUDY / "candidate_config.json"
    config = _json.loads(config_file.read_text(encoding="utf-8")) if config_file.exists() else {}
    if config.get("executor"):
        kb.CFG.update(config["executor"])
    model = _STUDY / config.get("model_file", "causal_daily_rows.json")
    return dict(kb=kb, policy=_Policy(model, config.get("policy")), opening=make_opening(),
                policy_memory={}, tile_memory={}, config=config, day=-1, last_step=-1,
                last_action=None, planner_seconds=0.0, initialized_at=_time.perf_counter())


def strategy_diagnostics():
    return STRATEGY_DIAGNOSTICS


def agent(observation, configuration=None):
    global _STATE
    step = int(observation.get("step", 0))
    if _STATE is None or step == 0 or step < _STATE["last_step"]:
        _STATE = _initialize()
        STRATEGY_DIAGNOSTICS.clear()
    state = _STATE
    state["last_step"] = step
    obs = dict(observation)
    day, hour = divmod(step, 24)
    obs.update(day=day, hour=hour)
    state["policy_memory"] = state["policy"].observe(obs, state["policy_memory"], state["last_action"])
    _observe_own(obs, state["tile_memory"])
    if step < 144:
        opening = state["opening"]
        result = opening(obs, configuration) if callable(opening) else opening.act(obs, configuration)
        if hour == 0:
            STRATEGY_DIAGNOSTICS.append(dict(day=day, phase="opening", cash=obs["farms"][obs["player"]]["money"]))
    else:
        kb = state["kb"]
        if day != state["day"]:
            if hour != 0:
                raise RuntimeError("Missed daily semantic planning boundary")
            started = _time.perf_counter()
            proposal = state["policy"].propose(obs, state["policy_memory"])
            state["policy_memory"] = proposal["memory"]
            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))
            kb._T = kb.TilePlanView.from_dict(plan)
            if kb._S is not None:
                kb._S["smap"].clear()
                kb._S["pmap"].clear()
            state["day"] = day
            elapsed = _time.perf_counter()-started
            state["planner_seconds"] += elapsed
            STRATEGY_DIAGNOSTICS.append(dict(day=day, phase="semantic", cash=obs["farms"][obs["player"]]["money"],
                planner_seconds=elapsed, proposal=proposal["today"], policy=proposal["diagnostics"],
                realized_plan=audit["semantic_today"], capacity_adjustments=audit["capacity_adjustments"],
                end_board=audit["today"]["end_board"], retirements=audit["today"]["retirements_started"],
                warnings=plan["planner_metadata"]["warnings"]))
        result = kb.agent(obs, configuration)
        if kb._TP_LEAK:
            raise RuntimeError("KB115LT non-interface data read: " + str(dict(kb._TP_LEAK)))
    state["last_action"] = result
    return result

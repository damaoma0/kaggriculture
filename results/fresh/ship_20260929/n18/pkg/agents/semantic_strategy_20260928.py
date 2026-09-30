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
from collections import Counter as _Counter

_ROOT = (_Path(__file__).resolve().parents[1] if "__file__" in globals()
         else _Path.cwd().resolve())
_sys.path.insert(0, str(_ROOT / "scripts"))
from semantic_strategy_policy_20260928 import SemanticStrategyPolicy as _Policy
from semantic_strategy_tiles_20260928 import build_plan as _build_plan, observe_own as _observe_own
from semantic_strategy_financing_20260928 import capital_pacing_products as _capital_pacing_products

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
    policy_kind = config.get("policy_kind", "daily_nearest")
    if policy_kind == "three_day_budget":
        from semantic_strategy_blocks_20260928 import SemanticBlockPolicy
        policy = SemanticBlockPolicy(model, config.get("policy"))
    elif policy_kind == "daily_nearest":
        policy = _Policy(model, config.get("policy"))
    else:
        raise ValueError("Unknown semantic policy kind: " + str(policy_kind))
    return dict(kb=kb, policy=policy, opening=_opening_for(config),
                policy_memory={}, tile_memory={}, config=config, day=-1, last_step=-1,
                last_action=None, planner_seconds=0.0, initialized_at=_time.perf_counter(),
                executor_defaults={k: kb.CFG[k] for k in
                    ("sd_tier", "sd_budget0", "sd_budget", "sd_step_cap", "sd_plan_once", "sd_books_sell")})



def _opening_for(config):
    """research switch (2026-09-29): config["opening"] = "umg_y3" plays days 0-5 with the packaged V9-lite's tape router"""
    if config.get("opening") == "umg_y3":
        from semantic_opening_umg_20260929 import make_opening as _umg_opening
        return _umg_opening()
    if config.get("opening") == "kb_plan":
        return None                                # days 0-5 are played by the executor on config["opening_plan"]
    if config.get("opening") == "mgt_file":        # days 0-5 from a tape-router agent file (e.g. the current DSM library)
        from semantic_opening_umg_20260929 import OpeningUMG as _TapeOpening
        return _TapeOpening(_ROOT / config["opening_source"])
    from semantic_strategy_opening_20260928 import make_opening as _dsm_opening
    return _dsm_opening()


def _unlock_execution(state, obs, day, hour):
    """Newly purchased land needs the executor's existing hourly dispatcher.

    KB's tier routes are fixed at dawn and omit then-locked squares. Switching
    only after an observed unlock retains the frozen executor implementation,
    uses actual worker positions, and restores tier planning at the next dawn.
    """
    if not state["config"].get("reactive_land_unlock") or state.get("unlock_switched"):
        return
    unlocked = len(obs["farms"][int(obs["player"])]["unlocked_quadrants"])
    if unlocked <= state["morning_land"]:
        return
    kb = state["kb"]
    kb.CFG.update(sd_tier=0, sd_budget0=.7, sd_budget=.35, sd_step_cap=.8, sd_plan_once=0)
    if kb._S is not None:
        kb._S.pop("tier", None)  # Some market guards also consult this cached route.
        for field in ("assign", "walk"):
            kb._S.get(field, {}).clear()
        lower = kb._sd_state(kb._S)
        lower["routes"].clear(); lower["walk"].clear()
        lower["lastP"] = None
        lower["first_of_day"] = True
    state["unlock_switched"] = True
    state["daily_diagnostic"]["observed_land_unlock"] = dict(day=day, hour=hour, unlocked=unlocked,
        execution="existing hourly dispatcher until next dawn")


def _committed_retirements(state, obs):
    counts = _Counter()
    farm = obs["farms"][int(obs["player"])]
    for tile, intent in state["tile_memory"].get("retirements", {}).items():
        tile = int(tile)
        current = farm["tiles"][tile//10][tile%10]
        if (isinstance(current, dict) and current.get("animal") == intent["animal"]
                and current.get("placed_day") == intent["placed_day"]):
            counts[intent["animal"]] += 1
    return dict(counts)


def _finance_execution(state, obs):
    """Release observed shed goods only while today's admitted inputs need cash."""
    kb = state["kb"]
    books, audit = _capital_pacing_products(
        obs, kb._T, kb._S, state["executor_defaults"]["sd_books_sell"],
        state["config"].get("early_financing"), kb._walk_cap)
    kb.CFG["sd_books_sell"] = books
    if audit["active"]:
        state["daily_diagnostic"].setdefault("early_financing", []).append(audit)


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
            kb.CFG.update(state["executor_defaults"])
            state["morning_land"] = len(obs["farms"][int(obs["player"])]["unlocked_quadrants"])
            state["unlock_switched"] = False
            state["policy_memory"]["committed_retirement_counts"] = _committed_retirements(state, obs)
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
                animal_tile_lookahead=plan["animals_by_day"][day:min(30, day+3)],
                retirement_count_lookahead=[r["animal_retire_counts"] for r in audit["forecast_counts"][:3]],
                warnings=plan["planner_metadata"]["warnings"]))
            state["daily_diagnostic"] = STRATEGY_DIAGNOSTICS[-1]
        _unlock_execution(state, obs, day, hour)
        _finance_execution(state, obs)
        result = kb.agent(obs, configuration)
        if kb._S is not None:
            counters = kb._sd_state(kb._S)["st"]
            state["daily_diagnostic"]["executor_errors_cumulative"] = int(counters.get("errors", 0))
            state["daily_diagnostic"]["executor_last_error"] = counters.get("last_error", "")
        if kb._TP_LEAK:
            raise RuntimeError("KB115LT non-interface data read: " + str(dict(kb._TP_LEAK)))
    state["last_action"] = result
    return result

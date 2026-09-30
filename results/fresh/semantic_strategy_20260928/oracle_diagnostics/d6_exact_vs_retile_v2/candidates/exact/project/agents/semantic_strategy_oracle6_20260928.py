"""Explicit component oracle, never a causal or competition policy.

The diagnostic harness supplies a TilePlanView compiled from source daily counts
or the exact source layout, and replays BOTH original action prefixes itself.
This entry only acts from the exact observed D6 handoff. It cannot run without
explicit oracle configuration and must not enter qualification.
"""
import importlib.util as _importlib
import json as _json
from pathlib import Path as _Path
import sys as _sys

_ROOT = _Path(__file__).resolve().parents[1] if "__file__" in globals() else _Path.cwd().resolve()
_sys.path.insert(0, str(_ROOT/"scripts"))
from semantic_strategy_oracle_hooks_20260928 import _unlock_execution, _finance_execution

_PLAN = None
_OPTIONS = None
_STATE = None
STRATEGY_DIAGNOSTICS = []


def configure_oracle(payload):
    global _PLAN, _OPTIONS, _STATE
    if payload.get("scope") != "COMPONENT_DIAGNOSTIC_NOT_POLICY":
        raise ValueError("Explicit diagnostic oracle scope required")
    _PLAN, _OPTIONS, _STATE = payload["plan"], payload["options"], None
    STRATEGY_DIAGNOSTICS.clear()


def _initialize():
    runtime = _ROOT/"results/fresh/semantic_strategy_20260928/runtime"
    spec = _importlib.spec_from_file_location("_oracle_kb115lt",runtime/"agents/mgt_lead_kb115lt.py")
    kb = _importlib.module_from_spec(spec)
    spec.loader.exec_module(kb)
    recipe = _json.loads((_ROOT/"results/fresh/semantic_strategy_20260928/executor_recipe_online.json").read_text())
    kb.CFG.update(recipe)
    kb._TP_LEAK.clear()
    kb._TGT_EP = None
    kb._T = kb.TilePlanView.from_dict(_PLAN)
    return dict(kb=kb, config=_OPTIONS, day=-1,
        executor_defaults={key:kb.CFG[key] for key in ("sd_tier","sd_budget0","sd_budget","sd_step_cap","sd_plan_once","sd_books_sell")})


def strategy_diagnostics():
    return STRATEGY_DIAGNOSTICS


def agent(observation, configuration=None):
    global _STATE
    if _PLAN is None or int(observation["step"]) < 144:
        raise RuntimeError("Oracle requires configured plan and original-prefix D6 handoff")
    if _STATE is None:
        _STATE = _initialize()
    state = _STATE
    day,hour = divmod(int(observation["step"]),24)
    obs = dict(observation,day=day,hour=hour)
    kb = state["kb"]
    if state["day"] != day:
        kb.CFG.update(state["executor_defaults"])
        state["morning_land"] = len(obs["farms"][int(obs["player"])]["unlocked_quadrants"])
        state["unlock_switched"] = False
        state["day"] = day
        diagnostic = dict(day=day, scope="COMPONENT_DIAGNOSTIC_NOT_POLICY", oracle=True,
            cash=obs["farms"][int(obs["player"])]["money"],
            target_next_morning_board=_PLAN["board"][min(day+1,len(_PLAN["board"])-1)],
            hands=_PLAN["hands"][day], removals=_PLAN["removals"][day])
        STRATEGY_DIAGNOSTICS.append(diagnostic)
        state["daily_diagnostic"] = diagnostic
    _unlock_execution(state,obs,day,hour)
    _finance_execution(state,obs)
    result = kb.agent(obs,configuration)
    if kb._S is not None:
        counters = kb._sd_state(kb._S)["st"]
        state["daily_diagnostic"].update(executor_errors_cumulative=int(counters.get("errors",0)),
            executor_last_error=counters.get("last_error",""))
    if kb._TP_LEAK:
        raise RuntimeError("Non-interface oracle executor read: "+str(dict(kb._TP_LEAK)))
    return result

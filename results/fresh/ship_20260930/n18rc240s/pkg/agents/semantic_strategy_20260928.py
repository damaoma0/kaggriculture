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
    if config.get("det_clock"):                    # smoke runs only: searches stop at their count caps
        class _DetClock:
            def perf_counter(self):
                return 1000.0

            def time(self):
                return 1000.0

            def process_time(self):
                return 1000.0

            def __getattr__(self, k):
                return getattr(_time, k)
        kb.time = _DetClock()
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


_CASSETTE_MILK = ("PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP")
_CASSETTE_EGG = ("BAKERY", "BRUNCH_SPOT", "PET_CAFE")


def _cassette_apply(state, obs, proposal, day):
    cfg = state["config"].get("cassette")
    if not cfg or not (6 <= day < int(cfg.get("until_day", 12))):
        return
    if "cassette_table" not in state:
        state["cassette_table"] = _json.loads((_STUDY / cfg["file"]).read_text(encoding="utf-8"))["table"]
    rows = state["cassette_table"].get(str(day)) or {}
    if not rows:
        return
    names = [s if isinstance(s, str) else (s or {}).get("name") for s in (obs.get("town") or {}).get("unlocked_shops", [])]
    kind = lambda s: "MILK" if s in _CASSETTE_MILK else ("WOOL" if s == "YARN_STORE" else ("EGG" if s in _CASSETTE_EGG else "FARM"))
    mine = sorted(kind(s) for s in names)
    mix = "+".join(mine)
    row, fallback = rows.get(mix), False
    if row is None:                                # same size, largest multiset overlap, then the most games
        def score(m):
            other = _Counter(m.split("+")) if m else _Counter()
            return (sum((other & _Counter(mine)).values()), rows[m]["n"])
        cands = [m for m in rows if len(m.split("+") if m else []) == len(mine)] or list(rows)
        row, fallback = rows[max(cands, key=score)], True
    farm = obs["farms"][int(obs["player"])]
    cur = _Counter()
    for r_ in farm["tiles"]:
        for t_ in r_:
            if isinstance(t_, dict):
                if t_.get("animal"):
                    cur[t_["animal"]] += 1
                elif t_.get("crop"):
                    cur[t_["crop"]] += 1
    end = row["end_counts"]
    plants = {c: max(0, int(end.get(c, 0)) - cur[c]) for c in ("STRAWBERRY", "MELON", "TOMATO", "CARROT")}
    if cfg.get("melon_day6") is not None:     # DSM's day-6 melons exactly, never a top-up on other days
        plants["MELON"] = int(cfg["melon_day6"]) if day == 6 else 0
    if int(row.get("wheat_plant", 0)):
        plants["WHEAT"] = int(round(int(row["wheat_plant"]) * float(cfg.get("wheat_scale", 1.0))))
    adds = {s: max(0, int(end.get(s, 0)) - cur[s]) for s in ("COW", "SHEEP", "GOOSE")}
    owned = len(farm.get("unlocked_quadrants") or ["NW"])
    today = proposal["today"]
    today.update(plant_counts={k: v for k, v in plants.items() if v}, animal_add_counts={k: v for k, v in adds.items() if v},
                 animal_retire_counts={}, hands=int(row["hands"]), target_land_count=max(owned, int(row["land"])),
                 land_add_count=max(0, int(row["land"]) - owned),
                 target_animals={s: cur[s] + adds[s] for s in ("COW", "SHEEP", "GOOSE")})
    state["cassette_last"] = dict(day=day, mix=mix, fallback=fallback, n=row["n"])


def _fill_free_apply(state, obs, proposal, day):
    cfg = state["config"].get("fill_free")
    if not cfg or not (int(cfg.get("from_day", 8)) <= day <= int(cfg.get("to_day", 26))):
        return
    farm = obs["farms"][int(obs["player"])]
    free = sum(1 for r_ in farm["tiles"] for t_ in r_ if t_ is None)
    today = proposal["today"]
    pc = today.setdefault("plant_counts", {})
    free -= sum(int(v) for v in pc.values()) + sum(int(v) for v in (today.get("animal_add_counts") or {}).values())
    crops = list(cfg.get("crops") or ["WHEAT", "CARROT"])
    for i in range(max(0, free)):
        c = crops[i % len(crops)]
        pc[c] = int(pc.get(c, 0)) + 1
    state["fill_free_last"] = dict(day=day, added=max(0, free))



def _seed_first(state, obs, day, result):
    sf = state["config"].get("seed_first")
    if not sf or not isinstance(result, dict) or day not in [int(x) for x in sf.get("days", [])]:
        return
    crop = sf.get("crop", "STRAWBERRY")
    plan = int(((state.get("daily_diagnostic") or {}).get("realized_plan") or {}).get("plant_counts", {}).get(crop, 0) or 0)
    if plan <= 0:
        return
    me = int(obs.get("player", 0))
    farm = (obs.get("farms") or [])[me]
    planted = sum(1 for row in farm["tiles"] for t in row if isinstance(t, dict) and t.get("crop") == crop
                  and int(t.get("planted_day", -1)) == day)
    priv = obs.get("private") or {}
    stock = int((priv.get("seeds") or {}).get(crop, 0) or 0)
    deficit = plan - planted - stock
    if deficit <= 0:
        return
    price = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}[crop]
    money = float(farm.get("money", 0) or 0)
    cost_ = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
    hold = set(sf.get("hold", ["GOOSE", "COW"]))
    market = result.setdefault("market", [])
    kept = []
    reserve = deficit * price
    for o in market:
        if isinstance(o, list) and o and o[0] == "BUY_ANIMAL" and len(o) > 1 and o[1] in hold:
            n = int(o[2]) if len(o) > 2 else 1
            if money - cost_.get(o[1], 0) * n < reserve:
                state.setdefault("seed_first_held", _Counter())[o[1]] += n
                continue
        if isinstance(o, list) and o and o[0] == "BUY_SEED" and len(o) > 1 and o[1] == crop:
            continue                                   # replaced by the deficit order below
        kept.append(o)
    # the full deficit (the engine buys unit by unit while the cash lasts), right AFTER this step's sells so their
    # proceeds pay for it (n18rc59 capped it at the pre-sale cash and put it first: fewer seeds than before)
    if len(kept) >= 10:
        for i in range(len(kept) - 1, -1, -1):
            if kept[i] and kept[i][0] != "HIRE" and kept[i][0] != "SELL":
                del kept[i]
                break
    n_ = int(deficit)
    prop_ = ((state.get("daily_diagnostic") or {}).get("proposal") or {})
    owned_ = len(farm.get("unlocked_quadrants") or [])
    if sf.get("land_first", True) and int(prop_.get("target_land_count", owned_) or owned_) > owned_:
        # the plan still buys land today (the block is planted on it): the land price comes first (n18rc61 bought 20
        # seeds at day-6 dawn in 114348036, the land slipped to day 7 and the block with it)
        land_ = (1000, 2000, 4000)[max(0, min(2, owned_ - 1))]
        sells_ = sum(int(o[2]) * float(((obs.get("market") or {}).get("prices") or {}).get(o[1], 0) or 0)
                     for o in kept if isinstance(o, list) and len(o) > 2 and o[0] == "SELL")
        n_ = min(n_, max(0, int((money + sells_ - land_) // price)))
        if not any(isinstance(o, list) and o and o[0] == "BUY_LAND" for o in kept) and money + sells_ >= land_:
            kept.insert(sum(1 for o in kept if isinstance(o, list) and o and o[0] == "SELL"), ["BUY_LAND"])
    if len(kept) < 10 and n_ > 0:
        k_ = sum(1 for o in kept if isinstance(o, list) and o and o[0] in ("SELL", "BUY_LAND"))
        kept.insert(k_, ["BUY_SEED", crop, n_])
        state.setdefault("seed_first_bought", _Counter())[day] += n_
    result["market"] = kept


def _land_reserve(state, obs, day, result):
    cfg = state["config"].get("land_reserve")
    if not cfg or not isinstance(result, dict) or day not in [int(x) for x in cfg.get("days", [])]:
        return
    me = int(obs.get("player", 0))
    farm = (obs.get("farms") or [])[me]
    owned = len(farm.get("unlocked_quadrants") or [])
    prop = ((state.get("daily_diagnostic") or {}).get("proposal") or {})
    if int(prop.get("target_land_count", owned) or owned) <= owned or owned >= 4:
        return
    price = (1000, 2000, 4000)[max(0, min(2, owned - 1))]
    prices = ((obs.get("market") or {}).get("prices") or {})
    market = list(result.get("market") or [])
    cash = float(farm.get("money", 0) or 0)
    cash += sum(int(o[2]) * float(prices.get(o[1], 0) or 0) for o in market
                if isinstance(o, list) and len(o) > 2 and o[0] == "SELL")
    hires = sum(1 for o in market if isinstance(o, list) and o and o[0] == "HIRE")
    k0 = int(farm.get("hires_today", 0) or 0)
    a, b_ = 1, 1
    fib = []
    for _ in range(k0 + hires + 1):
        fib.append(a)
        a, b_ = b_, a + b_
    cash -= sum(fib[k0:k0 + hires])
    cost = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
    seedp = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
    kept, held = [], 0
    has_land = any(isinstance(o, list) and o and o[0] == "BUY_LAND" for o in market)
    for o in market:
        if isinstance(o, list) and o and o[0] == "BUY_PRODUCT" and len(o) > 1:
            cash -= (float(prices.get(o[1], 0) or 0) + 1) * (int(o[2]) if len(o) > 2 else 1)
    if not has_land and cash >= price:
        at = max([i + 1 for i, o in enumerate(market) if isinstance(o, list) and o and o[0] in ("HIRE", "SELL")] or [0])
        market.insert(at, ["BUY_LAND"])
        has_land = True
    if has_land:
        cash -= price
    for o in market:
        if isinstance(o, list) and o and o[0] in ("BUY_ANIMAL", "BUY_SEED") and len(o) > 1:
            n = int(o[2]) if len(o) > 2 else 1
            c = (cost if o[0] == "BUY_ANIMAL" else seedp).get(o[1], 0) * n
            if not has_land and cash - c < price:
                held += 1
                continue
            cash -= c
        kept.append(o)
    result["market"] = kept[:10]
    if held:
        state.setdefault("land_reserve_held", _Counter())[day] += held

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


def _bank_account(t_call, observation, configuration):
    """the official overage bank used so far: our own call times over the 1 s allowance (research runs lift
    actTimeout, the guard still budgets 1 s), or the runner's own remainingOverageTime when it reports less"""
    state = _STATE
    if state is None:
        return
    try:
        limit = (configuration.get("actTimeout", 1) if isinstance(configuration, dict)
                 else getattr(configuration, "actTimeout", 1))
        limit = min(float(limit or 1), 1.0)
    except Exception:
        limit = 1.0
    state["bank_used"] = state.get("bank_used", 0.0) + max(0.0, _time.perf_counter() - t_call - limit)
    rem = observation.get("remainingOverageTime") if isinstance(observation, dict) else None
    if isinstance(rem, (int, float)) and rem < 60:
        state["bank_used"] = max(state["bank_used"], 60.0 - float(rem))


def _bank_guard(state, kb):
    g = state["config"].get("bank_guard")
    if not g:
        return
    used, lvl = state.get("bank_used", 0.0), state.get("bank_level", 0)
    # levels: 1 lean, 2 lean2 (optional, config "lean2" / "lean2_at"), 3 the greedy hourly dispatcher (last resort)
    if lvl < 1 and used >= float(g.get("lean_at", 25.0)):
        lvl = 1
    if g.get("lean2") and lvl < 2 and used >= float(g.get("lean2_at", 45.0)):
        lvl = 2
    if lvl < 3 and used >= float(g.get("greedy_at", 50.0)):
        lvl = 3
    state["bank_level"] = lvl
    if lvl >= 1:
        kb.CFG.update(g.get("lean") or {})
    if lvl >= 2:
        kb.CFG.update(g.get("lean2") or {})
    if lvl >= 3:                                   # the hourly dispatcher, each step capped under the 1 s allowance
        kb.CFG.update(sd_tier=0, sd_budget0=.5, sd_budget=.25, sd_step_cap=.6, sd_plan_once=0)


def _agent_inner(observation, configuration=None):
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
            _bank_guard(state, kb)
            state["morning_land"] = len(obs["farms"][int(obs["player"])]["unlocked_quadrants"])
            state["unlock_switched"] = False
            state["policy_memory"]["committed_retirement_counts"] = _committed_retirements(state, obs)
            proposal = state["policy"].propose(obs, state["policy_memory"])
            state["policy_memory"] = proposal["memory"]
            open_ = {s if isinstance(s, str) else (s or {}).get("name") for s in (obs.get("town") or {}).get("unlocked_shops", [])}
            for crop_, n_ in ((state["config"].get("plant_extra") or {}).get(str(day)) or {}).items():
                pc_ = proposal["today"].setdefault("plant_counts", {})
                gate_ = (state["config"].get("plant_extra_gate") or {}).get(crop_)
                if gate_ and not open_ & set(gate_):
                    continue
                if state["config"].get("plant_extra_topup"):
                    have_ = sum(1 for r_ in obs["farms"][int(obs["player"])]["tiles"] for t_ in r_
                                if isinstance(t_, dict) and t_.get("crop") == crop_)
                    pc_[crop_] = max(int(pc_.get(crop_, 0)), int(n_) - have_)
                else:
                    pc_[crop_] = int(pc_.get(crop_, 0)) + int(n_)
            for crop_, gate_ in (state["config"].get("plant_gate") or {}).items():
                if not open_ & set(gate_):
                    proposal["today"].setdefault("plant_counts", {}).pop(crop_, None)
            _cassette_apply(state, obs, proposal, day)
            _fill_free_apply(state, obs, proposal, day)
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
            state["daily_diagnostic"].update(bank_used=round(state.get("bank_used", 0.0), 2),
                                             bank_level=state.get("bank_level", 0))
        _unlock_execution(state, obs, day, hour)
        _finance_execution(state, obs)
        result = kb.agent(obs, configuration)
        _land_reserve(state, obs, day, result)
        _seed_first(state, obs, day, result)
        if kb._S is not None:
            counters = kb._sd_state(kb._S)["st"]
            state["daily_diagnostic"]["executor_errors_cumulative"] = int(counters.get("errors", 0))
            state["daily_diagnostic"]["executor_last_error"] = counters.get("last_error", "")
        if kb._TP_LEAK:
            raise RuntimeError("KB115LT non-interface data read: " + str(dict(kb._TP_LEAK)))
    state["last_action"] = result
    return result


def agent(observation, configuration=None):
    """entry: the strategy step, then the overage-bank count"""
    _t_call = _time.perf_counter()
    result = _agent_inner(observation, configuration)
    _bank_account(_t_call, observation, configuration)
    return result

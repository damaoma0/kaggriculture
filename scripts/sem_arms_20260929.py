"""Research variants of a frozen semantic-stack candidate inside this thread's study copy
(results/fresh/semantic_h2h_20260929/study). The other thread's study and candidates are never touched: the base is copied,
the named files are replaced, the candidate config is deep-merged and the manifest hashes are recomputed, so the frozen
harness (`play_job`) verifies the variant exactly as it verifies a frozen candidate.

usage: sem_arms_20260929.py make <new_id> [--base ID] [--executor FILE] [--land-gate] [--config JSON] [--note TEXT]
  --executor   replaces runtime/agents/mgt_lead_kb115lt.py (the executor the entry loads)
  --land-gate  patches the policy with the default-off option policy.land_min_day {"q": day}: the q-th quadrant is not
               bought before that day (a research option; the policy otherwise copies the nearest DSM day's land count)
  --config     JSON deep-merged into candidate_config.json, e.g. '{"executor": {"sd_tier_wheat_priority": 1}}'"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"
EXE = "results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py"
CFG = "results/fresh/semantic_strategy_20260928/candidate_config.json"
POLICY = "scripts/semantic_strategy_policy_20260928.py"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            merge(a[k], v)
        else:
            a[k] = v
    return a


def land_gate(src):
    old = '''        land=min(land,state["owned_quadrants"]+cfg["max_land_add_per_day"])\n'''
    new = old + '''        for q_,d_ in sorted((int(k),int(v)) for k,v in (cfg.get("land_min_day") or {}).items()):
            # research option (default none): the q_-th quadrant is not bought before day d_
            if d<d_ and land>=q_>state["owned_quadrants"]: land=q_-1
        for q_,d_ in sorted((int(k),int(v)) for k,v in (cfg.get("land_by_day") or {}).items()):
            # research option (default none): the q_-th quadrant is bought from day d_ on if the donor has not asked yet
            if d>=d_ and land<q_ and state["owned_quadrants"]==q_-1 and q_<=cfg["land_limit"]: land=q_\n'''
    if "land_min_day" in src:
        return src
    assert src.count(old) == 1
    return src.replace(old, new)


ENTRY = "agents/semantic_strategy_20260928.py"


def opening_switch(src):
    """the entry picks its day 0-5 opening from candidate_config["opening"] (default: the frozen DSM opening)"""
    old = "opening=make_opening(),"
    new = "opening=_opening_for(config),"
    helper = '''

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
'''
    if "_opening_for" in src:
        return src
    assert src.count(old) == 1
    src = src.replace(old, new)
    return src.replace("\ndef _unlock_execution(", helper + "\n\ndef _unlock_execution(", 1)


def kbplan_switch(src):
    """kb_plan opening (2026-09-29): days 0-5 on a hand-written TilePlanView played by the executor itself; the entry
    loads config["opening_plan"] (project-relative to the study folder) and config["opening_executor"] settings, which
    are restored at the day-6 dawn when the policy / tiler take over (the executor keeps its state)"""
    if "_plan_opening_step" in src:
        return src
    old1 = "opening=_opening_for(config),"
    assert src.count(old1) == 1, "apply opening_switch first"
    src = src.replace(old1, old1 + " opening_plan=_opening_plan(config),")
    old2 = '            kb.CFG.update(state["executor_defaults"])\n            state["morning_land"]'
    assert src.count(old2) == 1
    src = src.replace(old2, '            kb.CFG.update(state["executor_defaults"])\n'
                            '            kb.CFG.update(state.pop("opening_restore", None) or {})    # kb_plan settings end with day 5\n'
                            '            state["morning_land"]')
    old3 = '    if step < 144:\n        opening = state["opening"]'
    assert src.count(old3) == 1
    src = src.replace(old3, '    if step < 144 and state.get("opening_plan") is not None:\n'
                            '        result = _plan_opening_step(state, obs, configuration, day, hour)\n'
                            '    elif step < 144:\n        opening = state["opening"]')
    helper = '''

def _opening_plan(config):
    """research (2026-09-29): config["opening"] == "kb_plan" plays days 0-5 on config["opening_plan"]"""
    if config.get("opening") != "kb_plan":
        return None
    return _json.loads((_STUDY / config["opening_plan"]).read_text(encoding="utf-8"))


def _plan_opening_step(state, obs, configuration, day, hour):
    """days 0-5: the executor plays the hand-written plan with config["opening_executor"] settings (restored at the
    day-6 dawn); from day 6 the policy / tiler plan as usual and the executor keeps its state"""
    kb = state["kb"]
    if day != state["day"]:
        if "opening_restore" not in state:
            extra = state["config"].get("opening_executor") or {}
            state["opening_restore"] = {k: kb.CFG.get(k) for k in extra}
        kb.CFG.update(state["executor_defaults"])
        kb.CFG.update(state["config"].get("opening_executor") or {})
        if day == 0 or kb._T is None:
            kb._T = kb.TilePlanView.from_dict(state["opening_plan"])
        state["morning_land"] = len(obs["farms"][int(obs["player"])]["unlocked_quadrants"])
        state["unlock_switched"] = False
        state["day"] = day
        STRATEGY_DIAGNOSTICS.append(dict(day=day, phase="opening_plan", cash=obs["farms"][obs["player"]]["money"]))
        state["daily_diagnostic"] = STRATEGY_DIAGNOSTICS[-1]
    _finance_execution(state, obs)
    result = kb.agent(obs, configuration)
    if kb._TP_LEAK:
        raise RuntimeError("KB115LT non-interface data read: " + str(dict(kb._TP_LEAK)))
    return result
'''
    assert src.count("\n\ndef agent(") == 1
    return src.replace("\n\ndef agent(", helper + "\n\ndef agent(", 1)


def bank_guard(src):
    """time-bank guard (2026-09-29, shipping): the entry counts the official 60 s overage bank from its own call times
    (max(0, call - 1 s); the runner's remainingOverageTime when it reports one) and, at a day start, switches the
    executor to config["bank_guard"]["lean"] settings once lean_at seconds are used and to the greedy hourly dispatcher
    once greedy_at are used (both one-way). Without config["bank_guard"] nothing changes (the bank is still counted)."""
    if "_bank_guard" in src:
        return src
    old1 = '''def agent(observation, configuration=None):
    global _STATE
    step = int(observation.get("step", 0))'''
    new1 = '''def _bank_account(t_call, observation, configuration):
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
    step = int(observation.get("step", 0))'''
    old2 = '''            kb.CFG.update(state["executor_defaults"])
            state["morning_land"]'''
    new2 = '''            kb.CFG.update(state["executor_defaults"])
            _bank_guard(state, kb)
            state["morning_land"]'''
    old3 = '''            state["daily_diagnostic"] = STRATEGY_DIAGNOSTICS[-1]
        _unlock_execution(state, obs, day, hour)'''
    new3 = '''            state["daily_diagnostic"] = STRATEGY_DIAGNOSTICS[-1]
            state["daily_diagnostic"].update(bank_used=round(state.get("bank_used", 0.0), 2),
                                             bank_level=state.get("bank_level", 0))
        _unlock_execution(state, obs, day, hour)'''
    for o, n in ((old1, new1), (old2, new2), (old3, new3)):
        assert src.count(o) == 1, o[:60]
        src = src.replace(o, n)
    # the loaders (kaggle_environments get_last_callable, the harness) call the LAST new callable: the wrapper goes last
    return src.rstrip("\n") + '''


def agent(observation, configuration=None):
    """entry: the strategy step, then the overage-bank count"""
    _t_call = _time.perf_counter()
    result = _agent_inner(observation, configuration)
    _bank_account(_t_call, observation, configuration)
    return result
'''


def opening_until(src_entry, src_umg):
    """longer tape opening (user 2026-09-29: lay out the branches after the day-6 reveal): with the mgt_file opening the
    tape router keeps playing until config["opening_until_step"] (default 144 = day 6, unchanged), routing among the
    recorded games by the shops revealed so far; the semantic policy / tiler / executor take over at that dawn"""
    o1 = '''    if step < 144:
        opening = state["opening"]'''
    n1 = '''    if step < int(state["config"].get("opening_until_step", 144)):
        opening = state["opening"]'''
    o2 = '''        return _TapeOpening(_ROOT / config["opening_source"])'''
    n2 = '''        op_ = _TapeOpening(_ROOT / config["opening_source"])
        op_.until = int(config.get("opening_until_step", 144))
        return op_'''
    o3 = '''        if not 0 <= step < 144:'''
    n3 = '''        if not 0 <= step < getattr(self, "until", 144):'''
    if "opening_until_step" not in src_entry:
        assert src_entry.count(o1) == 1 and src_entry.count(o2) == 1
        src_entry = src_entry.replace(o1, n1).replace(o2, n2)
    if 'getattr(self, "until"' not in src_umg:
        assert src_umg.count(o3) == 1
        src_umg = src_umg.replace(o3, n3)
    return src_entry, src_umg


def plant_extra(src):
    """research option (2026-09-29, leader breakdown): config["plant_extra"] = {"day": {"CROP": n}} adds n plantings of
    CROP to the policy's proposal for that day (DSM's current plan plants 4 more melons on day 6 in every recorded game;
    our day-6+ policy never does). The tile compiler still clips to capacity."""
    old = '''            proposal = state["policy"].propose(obs, state["policy_memory"])
            state["policy_memory"] = proposal["memory"]'''
    new = '''            proposal = state["policy"].propose(obs, state["policy_memory"])
            state["policy_memory"] = proposal["memory"]
            for crop_, n_ in ((state["config"].get("plant_extra") or {}).get(str(day)) or {}).items():
                pc_ = proposal["today"].setdefault("plant_counts", {})
                pc_[crop_] = int(pc_.get(crop_, 0)) + int(n_)'''
    if "plant_extra" in src:
        return src
    assert src.count(old) == 1
    return src.replace(old, new)


def plant_extra_gate(src):
    """entry (2026-09-29, wheat tile-days): config plant_extra_gate {crop: [shops]} - a crop's plant_extra lot only when
    one of those shops is open that morning; plant_extra_topup - the lot tops the crop up to n plants (board + today's
    proposal) instead of adding n; plant_gate {crop: [shops]} - no plantings of the crop at all (policy's own included)
    while none of those shops is open. DSM plants its ~10 day-18 tomatoes only with a Farmers Market / Pizza Shop open (5 /
    5 such current-DSM 3Q worlds, 0 in the other 4); our fixed "plant_extra": {"18": {"TOMATO": 10}} planted 6-8 in the
    4 worlds without one (the tiler puts tomatoes before wheat: day-18 wheat clipped ~5 / world, tomato tile-days +46,
    wheat -82 over days 6-28)."""
    old = '''            for crop_, n_ in ((state["config"].get("plant_extra") or {}).get(str(day)) or {}).items():
                pc_ = proposal["today"].setdefault("plant_counts", {})
                pc_[crop_] = int(pc_.get(crop_, 0)) + int(n_)'''
    new = '''            open_ = {s if isinstance(s, str) else (s or {}).get("name") for s in (obs.get("town") or {}).get("unlocked_shops", [])}
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
                    proposal["today"].setdefault("plant_counts", {}).pop(crop_, None)'''
    if "plant_extra_gate" in src:
        return src
    assert src.count(old) == 1, "entry anchor for plant_extra_gate (needs --plant-extra first)"
    return src.replace(old, new)


def early_fert(src):
    """entry (2026-09-29, user: "continue the fix. Write a special rule for each day and product in days 6-10 if you
    must"): config early_fert {"from": 6, "to": 9, "detour": 2, "min": 1, "until_hour": 21} - fertilizer sold the same
    day, the way DSM does on days 1-9 (the executor recipe's sd_fert_sell 1 keeps collected fertilizer in hand to the
    midnight dump: day 6 sold 2.6 vs DSM 9.2, the day DSM buys its strawberry block). Acts on the executor's action
    after the fact, in the tier plan and in the hourly dispatcher alike, and touches FERTILIZER only (n18rc137 / 138
    lowered deliver_value for every product and moved our milk timing: opponent milk +1.2..1.8k):
      - a unit carrying fertilizer that stands on a shed-access tile PLACEs its fertilizer (only) there instead of a
        move / PASS / DROP;
      - a unit in transit (move / PASS) within "detour" steps of the shed steps toward it;
      - units doing tile work, PICKUP, PLACE of another item or FERTILIZE are left alone;
      - the shed's fertilizer plus this step's placements are sold at once (one SELL placed after the HIRE / BUY_LAND
        orders; the executor's own fertilizer sells are replaced; never pushes a HIRE past the 10-order cap)."""
    old = '''        result = kb.agent(obs, configuration)'''
    new = '''        result = kb.agent(obs, configuration)
        _early_fert_apply(state, obs, day, hour, result)'''
    fn = '''

def _early_fert_apply(state, obs, day, hour, result):
    cfg = state["config"].get("early_fert")
    if not cfg or not isinstance(result, dict) or not (int(cfg.get("from", 6)) <= day <= int(cfg.get("to", 9))):
        return
    me = int(obs.get("player", 0))
    farm = (obs.get("farms") or [])[me]
    priv = obs.get("private") or {}
    invs = priv.get("inventories") or []
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in (farm.get("hands") or [])]
    acts = [result.get("farmer")] + list(result.get("hands") or [])
    shed_tiles = [(4, 4), (5, 4), (4, 5), (5, 5)]
    moves = {(0, -1): "NORTH", (0, 1): "SOUTH", (1, 0): "EAST", (-1, 0): "WEST"}
    transit = ("NORTH", "SOUTH", "EAST", "WEST", "PASS")
    det, mn, last_h = int(cfg.get("detour", 2)), int(cfg.get("min", 1)), int(cfg.get("until_hour", 21))
    placed, diverted = 0, 0
    for u, p in enumerate(pos):
        if u >= len(acts) or u >= len(invs):
            continue
        f = int((invs[u] or {}).get("FERTILIZER", 0) or 0)
        a = acts[u] or ["PASS"]
        if f < mn or hour > last_h:
            continue
        if p in shed_tiles:
            if a[0] == "DROP":
                placed += f                        # DROP puts everything (the fertilizer too) in the shed
            elif a[0] in transit:
                acts[u] = ["PLACE", "FERTILIZER", f]
                placed += f
            continue
        if a[0] not in transit:
            continue
        q = min(shed_tiles, key=lambda s: (abs(s[0] - p[0]) + abs(s[1] - p[1]), s))
        d = abs(q[0] - p[0]) + abs(q[1] - p[1])
        if d <= det and hour + d <= last_h:
            dx, dy = q[0] - p[0], q[1] - p[1]
            acts[u] = [moves[(1 if dx > 0 else -1, 0)]] if dx else [moves[(0, 1 if dy > 0 else -1)]]
            diverted += 1
    result["farmer"] = acts[0]
    result["hands"] = acts[1:]
    n = int((priv.get("shed") or {}).get("FERTILIZER", 0) or 0) + placed
    market = [o for o in (result.get("market") or []) if not (o and o[0] == "SELL" and len(o) > 1 and o[1] == "FERTILIZER")]
    if n > 0:
        at = max([i + 1 for i, o in enumerate(market) if o and o[0] in ("HIRE", "BUY_LAND")] or [0])
        if len(market) >= 10:
            drop = next((i for i in range(len(market) - 1, -1, -1) if market[i] and market[i][0] not in ("HIRE", "BUY_LAND")), None)
            if drop is None:
                n = 0
            else:
                del market[drop]
                at = min(at, len(market))
        if n > 0:
            market.insert(at, ["SELL", "FERTILIZER", n])
    result["market"] = market
    dg = state.setdefault("early_fert_log", {})
    dg[day] = [dg.get(day, [0, 0, 0])[0] + placed, dg.get(day, [0, 0, 0])[1] + diverted, dg.get(day, [0, 0, 0])[2] + (n if n > 0 else 0)]
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["early_fert"] = dg[day]
'''
    if "_early_fert_apply" in src:
        return src
    assert src.count(old) == 1, "entry anchor for early_fert"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def seed_first_by_day(src):
    """entry (2026-09-29, day 8 of the days 6-10 rules): config seed_first.by_day {"6": "STRAWBERRY", "8": "WHEAT"} - the
    seed-first crop per day (needs --seed-first). Day 8 (9 current-DSM worlds): the plan asks 16.4 wheat on the new
    quadrant (unlock hour 8), the hourly dispatcher buys seeds only when a hand is about to plant - wheat seeds bought
    $63-98 (DSM $172) while $187-211 is left unspent at the day's end."""
    old = '''    crop = sf.get("crop", "STRAWBERRY")'''
    new = '''    crop = (sf.get("by_day") or {}).get(str(day), sf.get("crop", "STRAWBERRY"))'''
    if 'sf.get("by_day")' in src:
        return src
    assert src.count(old) == 1, "entry anchor for seed_first_by_day (needs --seed-first)"
    return src.replace(old, new)


def early_animal_jit(src):
    """entry (2026-09-29, days 6-10 rules): config early_animal_jit {"from": 6, "to": 10, "extra": 1} - an animal is bought
    only when a structure of its kind stands empty for it: BUY_ANIMAL n is cut to (empty coops / pastures on the board -
    animals of that structure kind already waiting in the shed or carried + extra). The executor buys an animal for every
    structure planned today at once (tier: '... bought at once'; dispatcher: every BUILD task's PLACE need): day 6 in
    114523301 5 geese at hour 5 ($1,981 -> $13) whose coops were built at hours 7-15, so the plan's strawberry seeds were
    never bought; DSM buys one goose as each coop is finished (hours 4, 6, 7, 9, 11, 12, 13, 15). Holding geese back
    instead (seed_first hold) cost 11 eggs a world (n18rc147)."""
    old = '''        result = kb.agent(obs, configuration)'''
    new = '''        result = kb.agent(obs, configuration)
        _early_animal_jit(state, obs, day, result)'''
    fn = '''

def _early_animal_jit(state, obs, day, result):
    cfg = state["config"].get("early_animal_jit")
    if not cfg or not isinstance(result, dict) or not (int(cfg.get("from", 6)) <= day <= int(cfg.get("to", 10))):
        return
    me = int(obs.get("player", 0))
    farm = (obs.get("farms") or [])[me]
    priv = obs.get("private") or {}
    kind = {"GOOSE": "COOP", "COW": "PASTURE", "SHEEP": "PASTURE"}
    empty = _Counter()
    for row in farm["tiles"]:
        for t in row:
            if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE") and not t.get("animal"):
                empty[t["kind"]] += 1
    waiting = _Counter()
    for sp, k in kind.items():
        waiting[k] += int((priv.get("shed") or {}).get(sp, 0) or 0)
        waiting[k] += sum(int((inv or {}).get(sp, 0) or 0) for inv in (priv.get("inventories") or []))
    room = {k: empty[k] - waiting[k] + int(cfg.get("extra", 1)) for k in ("COOP", "PASTURE")}
    kept = []
    for o in (result.get("market") or []):
        if isinstance(o, list) and o and o[0] == "BUY_ANIMAL" and len(o) > 1 and o[1] in kind:
            n = int(o[2]) if len(o) > 2 else 1
            k = kind[o[1]]
            m = max(0, min(n, room[k]))
            room[k] -= m
            if m < n:
                state.setdefault("early_animal_jit_cut", _Counter())[day] += n - m
            if m <= 0:
                continue
            o = [o[0], o[1], m]
        kept.append(o)
    result["market"] = kept
'''
    if "_early_animal_jit" in src:
        return src
    assert src.count(old) == 1, "entry anchor for early_animal_jit"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def early_fert_runner(src):
    """entry (2026-09-29, user: "Isn't our hands idling in 1-4 anyway? That should be output for free labor"): config
    early_fert_runner {"from": 6, "to": 6, "h0": 1, "h1": 5} - in that window every unit whose executor action is PASS is a
    fertilizer runner: it walks to the nearest animal whose fertilizer is still available and not claimed by another
    runner, COLLECTs it (standing on the pen), and once no unclaimed pen is left - or when the window's end minus its
    distance to the shed is near - walks to the shed and PLACEs its fertilizer (only). The shed's fertilizer is sold at
    once (one SELL after the HIRE / BUY_LAND orders). Units with real work are never touched. Day 6 in 114523301: our u3,
    u4, u6, u7, u8 PASS on the shed tiles hours 1-4 (their work is on the still-locked quadrant); 8 fertilizer sits on the
    pens from dawn; DSM sold 9 on day 6, we 3 (the rest rode in hand to the midnight dump). early_fert (n18rc140-144)
    moved only units already carrying fertilizer and pulled busy units off their routes."""
    old = '''        result = kb.agent(obs, configuration)'''
    new = '''        result = kb.agent(obs, configuration)
        _early_fert_runner(state, obs, day, hour, result)'''
    fn = '''

def _early_fert_runner(state, obs, day, hour, result):
    cfg = state["config"].get("early_fert_runner")
    if not cfg or not isinstance(result, dict) or not (int(cfg.get("from", 6)) <= day <= int(cfg.get("to", 6))):
        return
    h0, h1 = int(cfg.get("h0", 1)), int(cfg.get("h1", 5))
    back_by = int(cfg.get("back_by", h1 + 3))      # a pen is taken only if the runner is back at the shed by this hour
    home_det = int(cfg.get("home_detour", 0))      # after the window a runner carrying fertilizer this close goes home
    me = int(obs.get("player", 0))
    farm = (obs.get("farms") or [])[me]
    priv = obs.get("private") or {}
    invs = priv.get("inventories") or []
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in (farm.get("hands") or [])]
    acts = [result.get("farmer")] + list(result.get("hands") or [])
    shed_tiles = [(4, 4), (5, 4), (4, 5), (5, 5)]
    moves = {(0, -1): "NORTH", (0, 1): "SOUTH", (1, 0): "EAST", (-1, 0): "WEST"}
    dist = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])

    def step_to(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        return [moves[(1 if dx > 0 else -1, 0)]] if dx else [moves[(0, 1 if dy > 0 else -1)]]
    tiles = farm["tiles"]
    avail = {(x, y) for y, row in enumerate(tiles) for x, t in enumerate(row)
             if isinstance(t, dict) and t.get("animal") and t.get("fertilizer_available")}
    for u, a in enumerate(acts):                   # a unit with real work collecting here this step keeps its pen
        if a and a[0] == "COLLECT_FERTILIZER" and u < len(pos):
            avail.discard(pos[u])
    st = state.setdefault("efr", {"day": -1})
    if st["day"] != day:
        st.clear()
        st.update(day=day, claim={}, placed=0, collected=0, sold=0, runners=[])
    claim = st["claim"]
    placed = 0
    if h0 <= hour <= h1 + 6:
        for u, p in enumerate(pos):
            if u >= len(acts) or u >= len(invs):
                continue
            a = acts[u] or ["PASS"]
            f = int((invs[u] or {}).get("FERTILIZER", 0) or 0)
            q = min(shed_tiles, key=lambda s: (dist(p, s), s))
            if a[0] != "PASS":
                claim.pop(u, None)
                if (u in st["runners"] and f > 0 and home_det and hour > h0
                        and a[0] in ("NORTH", "SOUTH", "EAST", "WEST") and dist(p, q) <= home_det):
                    if p in shed_tiles:            # a former runner passing home: its fertilizer goes in the shed
                        acts[u] = ["PLACE", "FERTILIZER", f]
                        placed += f
                    else:
                        acts[u] = step_to(p, q)
                continue
            if p in shed_tiles and f > 0:
                acts[u] = ["PLACE", "FERTILIZER", f]
                placed += f
                claim.pop(u, None)
                continue
            if hour > h1:                          # after the window: only bring carried fertilizer home
                if f > 0:
                    acts[u] = step_to(p, q)
                continue
            taken = {t for v, t in claim.items() if v != u}
            tgt = claim.get(u)
            if tgt not in avail or tgt in taken:
                cands = sorted((t for t in avail if t not in taken), key=lambda t: (dist(p, t), t))
                tgt = cands[0] if cands else None
            if tgt is not None and hour + dist(p, tgt) + dist(tgt, q) <= back_by:
                claim[u] = tgt
                if u not in st["runners"]:
                    st["runners"].append(u)
                if p == tgt:
                    acts[u] = ["COLLECT_FERTILIZER"]
                    st["collected"] += 1
                    avail.discard(tgt)
                else:
                    acts[u] = step_to(p, tgt)
            elif f > 0:
                claim.pop(u, None)
                acts[u] = step_to(p, q)
    result["farmer"] = acts[0]
    result["hands"] = acts[1:]
    if h0 <= hour <= h1 + 6:
        n = int((priv.get("shed") or {}).get("FERTILIZER", 0) or 0) + placed
        market = [o for o in (result.get("market") or []) if not (o and o[0] == "SELL" and len(o) > 1 and o[1] == "FERTILIZER")]
        if n > 0:
            at = max([i + 1 for i, o in enumerate(market) if o and o[0] in ("HIRE", "BUY_LAND")] or [0])
            if len(market) >= 10:
                drop = next((i for i in range(len(market) - 1, -1, -1) if market[i] and market[i][0] not in ("HIRE", "BUY_LAND")), None)
                if drop is None:
                    n = 0
                else:
                    del market[drop]
                    at = min(at, len(market))
            if n > 0:
                market.insert(at, ["SELL", "FERTILIZER", n])
                st["sold"] += n
        result["market"] = market
    st["placed"] += placed
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["early_fert_runner"] = {k: st[k] for k in ("collected", "placed", "sold")}
'''
    if "_early_fert_runner" in src:
        return src
    assert src.count(old) == 1, "entry anchor for early_fert_runner"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def land_reserve(src):
    """entry (2026-09-29, days 6-10 rules): config land_reserve {"days": [8]} - on those days, while the plan still buys
    land (proposal target_land_count > owned quadrants), BUY_ANIMAL / BUY_SEED orders that would leave less cash (after
    this step's sells) than the land price are dropped; BUY_LAND goes first once affordable. HIRE, SELL and feed-wheat
    BUY_PRODUCT pass. The executor buys land only when $2,000 happens to be left after the hour's other purchases: with the
    day-6/7 fertilizer runner (n18rc158 / 159) the day-8 dawn cash matched DSM ($411 vs $414) but leaked into animals and
    the third quadrant slipped to day 9-10 in 3 / 9 worlds (day-8 plantings 9.7 / 7.3); DSM buys it at hour 5-6."""
    old = '''        result = kb.agent(obs, configuration)'''
    new = '''        result = kb.agent(obs, configuration)
        _land_reserve(state, obs, day, result)'''
    fn = '''

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
'''
    if "_land_reserve" in src:
        return src
    assert src.count(old) == 1, "entry anchor for land_reserve"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def det_clock(src):
    """entry (2026-09-29, user: "fix the random seed such that it is deterministic for the smoke runs"): config det_clock
    true - the executor module's `time` is replaced by a frozen clock, so every search stops at its count cap (route
    search sd_tier_iters, dispatcher search sd_evals0 / sd_evals, polish iterations) and never at a wall-clock budget.
    The seeds were already fixed (engine: the recorded world's seed / shops / weeds; executor rng = sd_seed * 100003 +
    step); the only nondeterminism was wall-clock cut-offs (null run: n18rc127 twice identical in 8 / 9 worlds,
    114433787 diverged on day 16). SMOKE RUNS ONLY: the shipped agent keeps its real time budgets."""
    old = '''    if config.get("executor"):
        kb.CFG.update(config["executor"])'''
    new = '''    if config.get("executor"):
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
        kb.time = _DetClock()'''
    if "_DetClock" in src:
        return src
    assert src.count(old) == 1, "entry anchor for det_clock"
    return src.replace(old, new)


def plant_scale_days(src):
    """block policy (needs --block-front): config policy.plant_scale_days [d0, d1] - policy.plant_scale acts only on days
    d0..d1 (the forecast blocks included). User 2026-09-29 ("quadrant problem and planning problem. Try to fix"): wheat
    plantings vs DSM per world - days 6-10 asked 31.4 (DSM planted 38.2), days 11-14 asked 24.1 (DSM 32.7), days 19-26
    already at DSM's level (56.3 vs 53.1); a season-wide scale would over-plant the late blocks."""
    old = """        for sp,f in (self.config.get('plant_scale') or {}).items():"""
    new = """        psd_=self.config.get('plant_scale_days')
        for sp,f in ((self.config.get('plant_scale') or {}).items() if (not psd_ or int(psd_[0])<=day<=int(psd_[1])) else ()):"""
    if "plant_scale_days" in src:
        return src
    assert src.count(old) == 1, "block policy anchor for plant_scale_days (needs --block-front)"
    return src.replace(old, new)


def cassette_wheat_scale(src):
    """entry: config cassette.wheat_scale - the cassette's fixed daily wheat plantings (days 6-11, DSM's median
    wheat_plant for the shop mix) times this factor (days 6-10 asked 31.4 a world vs DSM's 38.2 planted)."""
    old = '''        plants["WHEAT"] = int(row["wheat_plant"])'''
    new = '''        plants["WHEAT"] = int(round(int(row["wheat_plant"]) * float(cfg.get("wheat_scale", 1.0))))'''
    if 'cfg.get("wheat_scale"' in src:
        return src
    assert src.count(old) == 1, "entry anchor for cassette_wheat_scale"
    return src.replace(old, new)


def shop_crop_boost(src):
    """entry (2026-09-29, user: "why we made less carrots"): config shop_crop_boost {"PET_CAFE": {"CARROT": {"scale": 1.5,
    "add": {"8": 2, "9": 2, "10": 2}, "from": 6, "to": 26}}} - while that shop is open, the day's proposal plants the crop
    x scale (days from..to) plus add[day]. No-tomato worlds (4, all open a Pet Cafe first, day 3; 12 carrots a day):
    DSM plants 84 carrots a world (days 6-10 7.5, 11-14 13.5, 19-22 25.5, 23-26 30.0), we 54 - exactly what our plan asks
    (no tiler clip, no execution loss): the cassette pools the Pet Cafe with the other farm shops (days 6-11 asks 0.8)
    and the block planner stays below DSM; carrots sold 276 vs 192 (-3.6k margin a world)."""
    old = '''            _cassette_apply(state, obs, proposal, day)'''
    new = '''            _cassette_apply(state, obs, proposal, day)
            _shop_crop_boost(state, obs, proposal, day)'''
    fn = '''

def _shop_crop_boost(state, obs, proposal, day):
    cfg = state["config"].get("shop_crop_boost")
    if not cfg:
        return
    open_ = {s if isinstance(s, str) else (s or {}).get("name") for s in (obs.get("town") or {}).get("unlocked_shops", [])}
    pc = proposal["today"].setdefault("plant_counts", {})
    for shop, crops in cfg.items():
        if shop not in open_:
            continue
        for crop, rule in crops.items():
            if not (int(rule.get("from", 6)) <= day <= int(rule.get("to", 26))):
                continue
            n = int(pc.get(crop, 0))
            n = int(round(n * float(rule.get("scale", 1.0)))) + int((rule.get("add") or {}).get(str(day), 0))
            if n > 0:
                pc[crop] = n
'''
    if "_shop_crop_boost" in src:
        return src
    assert src.count(old) == 1, "entry anchor for shop_crop_boost"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def fill_new_land(src):
    """entry (2026-09-29, user: "we should have both fixes in" - finish each new quadrant's plantings on its opening day):
    config fill_free.new_land true - on a day the plan buys land (proposal target_land_count > owned quadrants) the new
    quadrant's 25 tiles count as free for fill_free (it counted only the tiles free at dawn, when that quadrant is still
    locked). Idle land (empty + weed tile-days) n18rc160 - DSM: days 6-10 +24.1 of +43.5 (day 7 +6.1: the day-6 plantings
    unfinished; days 9-10 +6.9 / +4.8: the day-8 quadrant planted later and slower than DSM's)."""
    old = '''    free -= sum(int(v) for v in pc.values()) + sum(int(v) for v in (today.get("animal_add_counts") or {}).values())'''
    new = '''    if cfg.get("new_land"):                        # the quadrant bought today counts as free land
        owned_ = len(farm.get("unlocked_quadrants") or ["NW"])
        free += 25 * max(0, min(4, int(today.get("target_land_count", owned_) or owned_)) - owned_)
    free -= sum(int(v) for v in pc.values()) + sum(int(v) for v in (today.get("animal_add_counts") or {}).values())'''
    if 'cfg.get("new_land")' in src:
        return src
    assert src.count(old) == 1, "entry anchor for fill_new_land"
    return src.replace(old, new)


def window_swap(src):
    """entry (2026-09-29, user: "we mostly fill in carrots when we expect 2-3 days until next crop type change instead of
    3-4 days ... wheat is 3-4 days and carrot is 2-3"): config window_swap {"from": 6, "to": 27} - after the morning plan
    is built, today's WHEAT and CARROT plantings are re-assigned among their own tiles by the tile's window (days until
    the compiled plan next plants on it or stands a structure there, else the season end): carrots to the tightest
    windows, wheat to the longest; counts unchanged, ties keep their crop. The tiler gives both crops release age 3, so
    it placed them blind to the window (last planting before a crop change, per world: DSM carrots in 2-3-day windows
    4.6 / 3-4 2.1, ours 3-4 2.7 / 4-5 2.6; DSM ends a wheat run with a carrot 21.4 times, we 9.0). With equal release ages
    the swap leaves the plan's timeline unchanged: a wheat on a loose window grows to age 4 (6 units) instead of being
    cut at age 3 by the next planting, a carrot on a tight window ends on its last day."""
    old = '''            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))'''
    new = '''            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))
            _window_swap(state, plan, day)'''
    fn = '''

def _window_swap(state, plan, day):
    cfg = state["config"].get("window_swap")
    if not cfg or not (int(cfg.get("from", 6)) <= day <= int(cfg.get("to", 27))):
        return
    n = int(plan["n"])
    P = plan["plant"]
    if day >= len(P) or not P[day]:
        return
    today = P[day]

    def has(dct, t):
        return str(t) in dct or (str(t).isdigit() and int(t) in dct)

    def nextuse(t):
        for d in range(day + 1, n):
            if has(P[d], t) or has(plan["struct_by_day"][d], t):
                return d - day
        return n - day
    ws = [t for t, c in today.items() if c == "WHEAT"]
    cs = [t for t, c in today.items() if c == "CARROT"]
    if not ws or not cs:
        return
    pool = sorted(ws + cs, key=lambda t: (nextuse(t), 0 if today[t] == "CARROT" else 1, str(t)))
    tight = set(pool[:len(cs)])
    if any(nextuse(t) < int(cfg.get("wheat_min", 3)) for t in ws + cs if t not in tight):
        return                                     # a wheat would land on a window shorter than its cycle
    changed = {t: ("CARROT" if t in tight else "WHEAT") for t in ws + cs
               if today[t] != ("CARROT" if t in tight else "WHEAT")}
    if not changed:
        return
    for t, c in changed.items():
        today[t] = c
    ti = {int(t): c for t, c in changed.items()}
    plan["events"] = [[e[0], e[1], ti.get(int(e[1]), e[2]) if int(e[0]) == day else e[2]] for e in plan["events"]]
    for t, c in ti.items():
        old_, new_ = ("WH", "CA") if c == "CARROT" else ("CA", "WH")
        for d in range(day + 1, n):
            b = plan["board"][d]
            if b[t] != old_:
                break
            b[t] = new_
    lg = state.setdefault("window_swap_log", {})
    lg[day] = len(changed)
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["window_swap"] = len(changed)
'''
    if "_window_swap" in src:
        return src
    assert src.count(old) == 1, "entry anchor for window_swap"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def gap_fill(src):
    """entry (2026-09-29, user: "harvest wheat at age 3 and plant carrots when we foresee this tile would be planted for
    strawberries 2 days later, thus saving one day. If it was wheat that is upcoming, we should simply shift the wheat
    production one day ahead"): config gap_fill {"from": 6, "to": 27, "shift_max": 2, "wheat_gap": [3, 30], "max": 99}.
    After the morning plan is compiled, every unlocked tile with no planting / structure today is checked against its
    next planned use n (planting or structure, days ahead g = n - today):
      next use WHEAT / CARROT, tile free today (empty, weed, wheat age >= 4, carrot age >= 3), 1 <= g <= shift_max:
          that planting moves to today (the replant happens on the harvest visit, not a day later)
      next use another crop / a structure, g == 2, tile free today or a wheat at age 3:
          a CARROT today (the wheat is cut at age 3 - the executor harvests a one-time crop at age >= maxday-1 to plant
          on its tile - and the carrot is cut at age 2 when the next planting arrives; tiler release age CARROT 2)
      next use another crop / a structure, g within wheat_gap, tile free today: a WHEAT today
    A wheat at age 3 with a wheat / carrot next is left to reach age 4 (tomorrow's plan shifts the replant onto it)."""
    old = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))"""
    new = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))
            _gap_fill(state, obs, plan, day)"""
    fn = '''

def _gap_fill(state, obs, plan, day):
    cfg = state["config"].get("gap_fill")
    if not cfg or not (int(cfg.get("from", 6)) <= day <= int(cfg.get("to", 27))):
        return
    n_ = int(plan["n"])
    P = plan["plant"]
    SB = plan["struct_by_day"]
    if day >= len(P):
        return
    farm = obs["farms"][int(obs["player"])]
    lab = {"WHEAT": "WH", "CARROT": "CA"}

    def has(dct, t):
        return str(t) in dct or t in dct

    def get(dct, t):
        return dct.get(str(t), dct.get(t))

    def put(d, t, crop):
        P[d][str(t)] = crop

    def drop(d, t):
        P[d].pop(str(t), None)
        P[d].pop(t, None)
    shift_max = int(cfg.get("shift_max", 2))
    wg = cfg.get("wheat_gap", [3, 30])
    cap = int(cfg.get("max", 99))
    out = {"shift": 0, "carrot": 0, "carrot_cut3": 0, "wheat": 0}
    why = {}

    def w(k):
        why[k] = why.get(k, 0) + 1
    added = []
    for t in range(100):
        if sum(out.values()) >= cap:
            break
        raw = farm["tiles"][t // 10][t % 10]
        if raw == "LOCKED" or has(P[day], t) or has(SB[day], t):
            w("locked_or_used_today")
            continue
        if raw is None or (isinstance(raw, dict) and raw.get("kind") == "WEED"):
            st = "free"
        elif isinstance(raw, dict) and raw.get("kind") == "PLANT" and raw.get("crop") in ("WHEAT", "CARROT"):
            age = day - int(raw.get("planted_day", day))
            if raw["crop"] == "WHEAT" and age >= 4 or raw["crop"] == "CARROT" and age >= 3:
                st = "free"
            elif raw["crop"] == "WHEAT" and age == 3 and int(raw.get("yield_units", 0) or 0) > 0:
                st = "wheat3"
            else:
                w("young_crop")
                continue
        else:
            w("other_occupant")
            continue
        nxt = None
        for d in range(day + 1, n_):
            if has(P[d], t):
                nxt = (d, get(P[d], t))
                break
            if has(SB[d], t):
                nxt = (d, "STRUCT")
                break
        if nxt is None:
            w(st + "_no_next_use")
            continue
        d_n, X = nxt
        g = d_n - day
        w("%s_next_%s_g%d" % (st, "WC" if X in ("WHEAT", "CARROT") else "other", min(g, 9)))
        if X in ("WHEAT", "CARROT"):
            if st == "free" and 1 <= g <= shift_max:
                drop(d_n, t)
                put(day, t, X)
                plan["events"] = [e for e in plan["events"] if not (int(e[0]) == d_n and int(e[1]) == t)]
                added.append((t, X, g))
                out["shift"] += 1
            continue
        if g == 2 and day + 2 <= 29:
            put(day, t, "CARROT")
            added.append((t, "CARROT", 2))
            out["carrot_cut3" if st == "wheat3" else "carrot"] += 1
        elif st == "free" and wg and int(wg[0]) <= g <= int(wg[1]) and day + 3 <= 29:
            put(day, t, "WHEAT")
            added.append((t, "WHEAT", min(4, g)))
            out["wheat"] += 1
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["gap_fill_why"] = dict(why, day=day)
    if not added:
        return
    for t, crop, span in added:
        plan["events"].append([day, t, crop])
        for d in range(day, min(n_, day + span)):
            plan["board"][d][t] = lab[crop]
        hv = plan.get("harv_tiles")
        if isinstance(hv, list) and day + span < len(hv) and isinstance(hv[day + span], list):
            hv[day + span].append(t)
    lg = state.setdefault("gap_fill_log", {})
    lg[day] = dict(out)
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["gap_fill"] = dict(out, day=day)
'''
    if "_gap_fill(" in src:
        return src
    assert src.count(old) == 1, "entry anchor for gap_fill"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def fert_force_plan(src):
    """entry (2026-09-29, user: "We do it only if we expect this as a 2day cycle"): config fert_force_plan {"ages":
    {"CARROT": 1}} - every morning the executor's sd_fert_force_tiles lists the plants at that age whose tile the
    compiled plan uses again tomorrow (a planting or a structure on it at age + 1). With executor sd_fert_force
    {"CARROT": [1, 1]} (v18w) only those carrots are fertilized at age 1: at the age-2 dawn they project 3 units, the
    tiler releases them (release_age CARROT 2, min_yield 3) and the planting cuts them at 3 units. Other carrots keep the
    age-2 fertilize and age-3 harvest; n18rc185d forced all of them and starved the age-2 wheat of fertilizer."""
    old = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))"""
    new = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))
            _fert_force_plan(state, obs, plan, day)"""
    fn = '''

def _fert_force_plan(state, obs, plan, day):
    cfg = state["config"].get("fert_force_plan")
    if not cfg:
        return
    P = plan["plant"]
    SB = plan["struct_by_day"]
    farm = obs["farms"][int(obs["player"])]
    ages = cfg.get("ages") or {"CARROT": 1}
    d1 = day + 1
    tiles = []
    for t in range(100):
        raw = farm["tiles"][t // 10][t % 10]
        if not (isinstance(raw, dict) and raw.get("kind") == "PLANT"):
            continue
        a = ages.get(raw.get("crop"))
        if a is None or day - int(raw.get("planted_day", day)) != int(a):
            continue
        if d1 < len(P) and (str(t) in P[d1] or t in P[d1] or str(t) in SB[d1] or t in SB[d1]):
            tiles.append(t)
    state["kb"].CFG["sd_fert_force_tiles"] = tiles
    lg = state.setdefault("fert_force_log", {})
    lg[day] = len(tiles)
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["fert_force_plan"] = dict(day=day, tiles=len(tiles))
'''
    if "_fert_force_plan(" in src:
        return src
    assert src.count(old) == 1, "entry anchor for fert_force_plan"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def straw_batch(src):
    """entry (2026-09-29, user: "it must work in coordination with a designed batched strawberry planting. We could do
    both"): config straw_batch {"days": [6, 9, 12, 15], "max_defer": 2, "to": 17, "anchor_live": {"STRAWBERRY": 0.8}}.
    Before the morning plan is compiled, every requested strawberry planting (today's and the forecast rows') moves to
    the next batch day at most max_defer days later, so the plan allocates the batch days ahead and the prior crops on
    those tiles end on the batch day. DSM (9 worlds): strawberries on days 6 / 9 / 12-13 / 15 - the shop reveal days -
    7.3 planting days a world, biggest batch 8.8; we 9.2 / 6.6 (days 6-10 spread). 74 of DSM's 85 strawberry plantings
    on used land follow a wheat harvested the same visit (ours 36 of 62, 17 after a 1-day gap). anchor_live sets the
    allocator's ANCHOR_LIVE: a tile's cost grows by weight x the distance to the nearest live plant of that crop (the
    allocator anchored only to same-day plantings), so a batch attaches to the existing block."""
    old = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))"""
    new = """            _straw_batch(state, obs, proposal, day)
""" + old
    fn = '''

def _straw_batch(state, obs, proposal, day):
    cfg = state["config"].get("straw_batch")
    if not cfg:
        return
    try:
        import semantic_tile_allocator_20260928 as _al_
        if hasattr(_al_, "ANCHOR_LIVE"):
            _al_.ANCHOR_LIVE.clear()
            _al_.ANCHOR_LIVE.update({k: float(v) for k, v in (cfg.get("anchor_live") or {}).items()})
    except Exception:
        pass
    days = sorted(int(d) for d in cfg.get("days", [6, 9, 12, 15]))
    md = int(cfg.get("max_defer", 2))
    last = int(cfg.get("to", 17))
    rows = {day: proposal["today"]}
    for r in proposal.get("forecast", []) or []:
        d = int(r.get("day", -1))
        if d > day:
            rows[d] = r

    catch = int(cfg.get("catch_up", 0))            # today plants freely for this many days after a batch day (shortfall)

    def target(d):
        if d == day and any(b < d <= b + catch for b in days):
            return d
        for b in days:
            if d <= b <= d + md:
                return b
        return d
    moved = {}
    for d in sorted(rows):
        if d > last:
            continue
        pc = rows[d].get("plant_counts") or {}
        n = int(pc.get("STRAWBERRY", 0) or 0)
        b = target(d)
        if n > 0 and b != d:
            pc.pop("STRAWBERRY", None)
            moved[b] = moved.get(b, 0) + n
    for b, n in moved.items():
        if b not in rows:
            continue
        pc = rows[b].setdefault("plant_counts", {})
        pc["STRAWBERRY"] = int(pc.get("STRAWBERRY", 0) or 0) + n
    lg = state.setdefault("straw_batch_log", {})
    lg[day] = dict(moved)
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["straw_batch"] = dict(day=day, moved={str(k): v for k, v in moved.items()},
                                                        today=int((proposal["today"].get("plant_counts") or {}).get("STRAWBERRY", 0) or 0))
'''
    if "_straw_batch(" in src:
        return src
    assert src.count(old) == 1, "entry anchor for straw_batch"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def anchor_live_alloc(src):
    """tile allocator (project scripts/semantic_tile_allocator_20260928.py): ANCHOR_LIVE {kind: weight} - a slot's
    linear cost grows by weight x the distance to the nearest live tile of that kind (any birth day)."""
    if "ANCHOR_LIVE" in src:
        return src
    old = """SECTOR = tuple("""
    assert src.count(old) == 1
    src = src.replace(old, """ANCHOR_LIVE = {}   # {kind: weight}: set by the entry's straw_batch (distance to the nearest live same-kind tile)
""" + old)
    old = """    # Linear costs use only the current state."""
    assert src.count(old) == 1
    src = src.replace(old, """    live_ = defaultdict(list)
    for t, s in state.items():
        if t not in slotset and _kind(s) in ANCHOR_LIVE:
            live_[_kind(s)].append(t)
""" + old)
    old = """            if anchors[k]:
                near = sorted(DIST[t][a] for a in anchors[k])[:2]"""
    assert src.count(old) == 1
    src = src.replace(old, """            if live_.get(k):
                cost += float(ANCHOR_LIVE[k]) * min(DIST[t][a] for a in live_[k])
""" + old)
    return src


def peak_hand(src):
    """entry (2026-09-29, user: "Isn't our strawberry gap 4k? Also there are only like 4 strawberry harvest peak days?"):
    config peak_hand {"crop": "STRAWBERRY", "ready_min": 14, "n": 1, "from": 12, "to": 28} - on a day whose dawn farm holds
    >= ready_min ready units of the crop, the day plan hires n more hands (before the tile plan). Every bring-back run so
    far took its hand off the routes (n18rc95: wheat -49, eggs -15); the extra hand of n18rc64-67 was hired on all of days
    12-28 (the 12th hire, $144 a day, ~2.4k a game; the cluster run on top of it +0.7k). Peak days (9 worlds, DSM ready at
    dawn): 16 / 18 / 20 / 22 hold 18-23 units, other days 7-13; days 15-18 carry -3.7k of our strawberry margin gap."""
    old = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))"""
    new = """            _peak_hand(state, obs, proposal, day)
""" + old
    fn = '''

def _peak_hand(state, obs, proposal, day):
    cfg = state["config"].get("peak_hand")
    if not cfg or not (int(cfg.get("from", 12)) <= day <= int(cfg.get("to", 28))):
        return
    crop = cfg.get("crop", "STRAWBERRY")
    farm = obs["farms"][int(obs["player"])]
    ready = sum(int(t.get("yield_units", 0) or 0) for row in farm["tiles"] for t in row
                if isinstance(t, dict) and t.get("crop") == crop)
    added = 0
    if ready >= int(cfg.get("ready_min", 14)):
        added = int(cfg.get("n", 1))
        proposal["today"]["hands"] = int(proposal["today"].get("hands", 0) or 0) + added
    lg = state.setdefault("peak_hand_log", {})
    lg[day] = dict(ready=ready, added=added)
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["peak_hand"] = dict(day=day, ready=ready, added=added)
'''
    if "_peak_hand(" in src:
        return src
    assert src.count(old) == 1, "entry anchor for peak_hand"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def yarn_floor(src):
    """entry (2026-09-30, user: "it should plan more sheep when hit with more sheep store"): config yarn_floor {"floor":
    {"1": 7, "2": 10}, "from": 6, "to": 20} - every morning in the window the day plan's sheep additions are topped up so
    sheep on the farm + in the shed + today's planned additions reach floor[number of open yarn stores]. DSM (9 worlds):
    the reveal day's flock goes 3 -> 7 at the first yarn store (114393058 / 114514221, day 12) and 7 -> 10 at the second
    (114393058, day 18); ours 3 -> 6 and 7 -> 8 (the block planner from day 12 under-sizes; the day 6-11 cassette keys on
    WOOL shop mixes). 114393058: 158 vs 127 sheep-days, 204 vs 172 wool, wool margin -10.5k (opponent +5.4k); wool per
    sheep-day is ours 1.35, DSM 1.29, so service is not the gap. A sheep placed after day 20 gets < 3 productions.
    by_reveal (2026-09-30, user: "difference between how much sheep DSM buys when a wool shop shows up early vs late"):
    floor = base + sum over open yarn stores of by_reveal[reveal day] x scale (shop k is revealed on day 3(k+1); key =
    the largest listed day <= the reveal day; by_reveal_order {"<store #>|<day>": n} overrides). DSM (106 games of
    56619023, flock gain until the next store): day 3 +7, 6 +6, 9 +5 (+7 as the 2nd store), 12 +4, 15 +2 (+4 as the 3rd),
    18 +1 (0 as the 2nd), 21+ 0; max flock 18."""
    old = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))"""
    new = """            _yarn_floor(state, obs, proposal, day)
""" + old
    fn = '''

def _yarn_floor(state, obs, proposal, day):
    cfg = state["config"].get("yarn_floor")
    if not cfg or not (int(cfg.get("from", 6)) <= day <= int(cfg.get("to", 20))):
        return
    names = [s if isinstance(s, str) else (s or {}).get("name") for s in (obs.get("town") or {}).get("unlocked_shops", [])]
    stores = sum(1 for n in names if n == "YARN_STORE")
    floor = int((cfg.get("floor") or {}).get(str(stores), 0) or 0)
    tab = cfg.get("by_reveal")                     # DSM's rule: sheep added per yarn store by its reveal day (shop k: day 3(k+1))
    if tab:
        reveal = [3 * (k + 1) for k, n in enumerate(names) if n == "YARN_STORE"]
        keys = sorted(int(x) for x in tab)
        floor = int(cfg.get("base", 3))
        for k, r in enumerate(reveal):
            a_ = (cfg.get("by_reveal_order") or {}).get(str(k + 1) + "|" + str(r))
            if a_ is None:
                low = [x for x in keys if x <= r]
                a_ = tab[str(low[-1])] if low else 0
            floor += int(round(float(a_) * float(cfg.get("scale", 1.0))))
    if cfg.get("match_rival") and stores > 0:      # the sheep counterfactual's best rule: max(DSM table x1, the rival's
        rf_ = obs["farms"][1 - int(obs["player"])]  # visible flock) - reached on the reveal day
        floor = max(floor, sum(1 for row in rf_["tiles"] for t in row if isinstance(t, dict) and t.get("animal") == "SHEEP"))
    farm = obs["farms"][int(obs["player"])]
    have = sum(1 for row in farm["tiles"] for t in row if isinstance(t, dict) and t.get("animal") == "SHEEP")
    have += int(((obs.get("private") or {}).get("shed") or {}).get("SHEEP", 0) or 0)
    ac = proposal["today"].setdefault("animal_add_counts", {})
    planned = int(ac.get("SHEEP", 0) or 0)
    add = max(0, floor - have - planned)
    if add:
        ac["SHEEP"] = planned + add
    cap = (cfg.get("cap") or {}).get(str(stores))     # the plan's own sheep additions stop at the cap (never removes sheep)
    cut = 0
    if cap is not None and int(ac.get("SHEEP", 0) or 0) > max(0, int(cap) - have):
        cut = int(ac.get("SHEEP", 0) or 0) - max(0, int(cap) - have)
        ac["SHEEP"] = max(0, int(cap) - have)
        if not ac["SHEEP"]:
            ac.pop("SHEEP", None)
    lg = state.setdefault("yarn_floor_log", {})
    lg[day] = dict(stores=stores, have=have, planned=planned, added=add, cut=cut, floor=floor)
    if state.get("daily_diagnostic") is not None:
        state["daily_diagnostic"]["yarn_floor"] = dict(day=day, stores=stores, have=have, planned=planned, added=add, cut=cut,
                                                         floor=floor)
'''
    if "_yarn_floor(" in src:
        return src
    assert src.count(old) == 1, "entry anchor for yarn_floor"
    src = src.replace(old, new)
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def cassette_straw_buyers(src):
    """entry (2026-09-30, user: follow DSM's plan on shop types; the cassette keys on MILK / EGG / WOOL / FARM kinds): config
    cassette.straw_table {day: {"<strawberry-buying shops revealed>|<yarn store 0/1>": {"n", "strawberry"}}} replaces the
    cassette's strawberry target (the other targets keep the kind-mix row). DSM's day-6 strawberry block follows the number of
    revealed strawberry-buying shops (BRUNCH_SPOT / ICE_CREAM_SHOP / SMOOTHIE_SHOP / FARMERS_MARKET): 0 -> 11, 1 -> 21 (19
    with a yarn store), 2 -> 26 (106 current DSM games; within-group spread 1.1 tiles vs 4.4 by kind mix). The kind mix pools
    brunch worlds (21) with bakery / pet cafe worlds (11): mean |target - DSM| day 6 3.3 -> 0.6 tiles (held-out 18 leader
    episodes 4.1 -> 0.7), targets off by >= 5 tiles 29 / 88 -> 0. Table: results/fresh/semantic_h2h_20260929/models/
    dsm_straw_by_buyers.json (leader panel held out), embedded in the candidate config."""
    old = """    plants = {c: max(0, int(end.get(c, 0)) - cur[c]) for c in ("STRAWBERRY", "MELON", "TOMATO", "CARROT")}
"""
    new = old + """    st_tab_ = cfg.get("straw_table")               # cassette_straw_buyers: DSM's strawberry block by strawberry-buying shops
    if st_tab_:
        buy_ = sum(1 for s_ in names if s_ in ("BRUNCH_SPOT", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET"))
        yarn_ = int("YARN_STORE" in names)
        T_ = st_tab_.get(str(day)) or {}
        tgt_ = T_.get(str(buy_) + "|" + str(yarn_))
        tgt_ = tgt_.get("strawberry") if isinstance(tgt_, dict) else None
        if tgt_ is None and T_:
            c_ = [k for k in T_ if k.split("|")[0] == str(buy_)]
            if not c_:                                 # more buyers than recorded that day: the largest recorded count
                mx_ = max(int(k.split("|")[0]) for k in T_)
                c_ = [k for k in T_ if k.split("|")[0] == str(mx_)]
            tgt_ = T_[max(c_, key=lambda k: T_[k]["n"])]["strawberry"]
        if tgt_ is not None:
            plants["STRAWBERRY"] = max(0, int(tgt_) - cur["STRAWBERRY"])
            state["cassette_straw_last"] = dict(day=day, buyers=buy_, yarn=yarn_, target=int(tgt_))
"""
    if "cassette_straw_last" in src:
        return src
    assert src.count(old) == 1, "entry anchor for cassette_straw_buyers"
    return src.replace(old, new)


def sm_occ_fragment(src):
    """maintenance optimizer (runtime scripts/fragments/sem_maintenance.py): SM_OCC {crop: coins per tile-day} - every
    day a crop stays on its tile after today costs that much (in product units at the crop's price). User 2026-09-29
    ("We are wasting tile-days on 3 days carrot"): the per-tile optimizer maximised each plant's own units and gave the
    tile no value for its next use, so a carrot was always kept to age 3 (4 units > 3; DSM harvests 48% at age 2, 2.53-day
    cycle vs our 3.0-3.4) and wheat went to age 4 in 42-71% of harvests (DSM 24-27%)."""
    reps = [
        ('SM_Q = 20 ', 'SM_OCC = {}                          # crop -> coins per tile-day a live crop occupies (0 = off)\nSM_Q = 20 '),
        ('''    def __init__(self, kind, fert_ok, rin, rv, fh, rc=0):
        self.kind = kind''', '''    def __init__(self, kind, fert_ok, rin, rv, fh, rc=0, ro=0):
        self.ro = ro        # crops: land cost of one more day on the tile, product units (SM_OCC / price)
        self.kind = kind'''),
        ('''        econ = SM_Q * u - inputs * self.rin - visits * self.rv + extra * self.rc''',
         '''        econ = SM_Q * u - inputs * self.rin - visits * self.rv + extra * self.rc
        if self.crop and self.ro and st2 is not None and st2 != "GONE":
            econ -= self.ro                    # the crop holds its tile another day'''),
        ('''def _sm_solver(kind, fert_ok, rin, rv, fh, rc=0):
    key = (kind, fert_ok, rin, rv, fh, rc)''', '''def _sm_solver(kind, fert_ok, rin, rv, fh, rc=0, ro=0):
    key = (kind, fert_ok, rin, rv, fh, rc, ro)'''),
        ('''        s = _SM_SOLVERS[key] = _SMSolver(kind, fert_ok, rin, rv, fh, rc)''', '''        s = _SM_SOLVERS[key] = _SMSolver(kind, fert_ok, rin, rv, fh, rc, ro)'''),
        ('''    ck = (kind, st, day, hour, bool(fert_ok), rin, rv, future_hour, rc, avail)''', '''    ro = _sm_ratio(float(SM_OCC.get(kind, 0) or 0), price) if kind in SM_CROPS else 0
    ck = (kind, st, day, hour, bool(fert_ok), rin, rv, future_hour, rc, avail, ro)'''),
        ('''    S = _sm_solver(kind, bool(fert_ok), rin, rv, future_hour, rc)''', '''    S = _sm_solver(kind, bool(fert_ok), rin, rv, future_hour, rc, ro)'''),
    ]
    if "SM_OCC = {}" in src:
        return src
    for a, b in reps:
        assert src.count(a) == 1, ("sem_maintenance anchor", a[:60], src.count(a))
        src = src.replace(a, b)
    return src


def sm_occ_executor(src):
    """executor: CFG sm_occ {crop: coins per tile-day} handed to the maintenance optimizer (SM_OCC) when it is loaded."""
    old = '''            exec(compile(fh.read(), "sem_maintenance", "exec"), ns)'''
    new = '''            exec(compile(fh.read(), "sem_maintenance", "exec"), ns)
        if CFG.get("sm_occ") and isinstance(ns.get("SM_OCC"), dict):
            ns["SM_OCC"].update({k: float(v) for k, v in CFG["sm_occ"].items()})   # land cost per tile-day'''
    if 'CFG.get("sm_occ")' in src:
        return src
    assert src.count(old) == 1, "executor anchor for sm_occ"
    return src.replace(old, new)


def keep_tier_days(src):
    """entry (2026-09-29, day-6 special case): config unlock_keep_tier_days [6] - on those days a mid-day land unlock does
    NOT switch the executor to the old hourly dispatcher (use with executor v18s sd_land_virtual, whose hour-0 route plan
    already covers the quadrant bought that day, jobs released after the unlock hour)."""
    old = '''    if not state["config"].get("reactive_land_unlock") or state.get("unlock_switched"):
        return'''
    new = '''    if not state["config"].get("reactive_land_unlock") or state.get("unlock_switched"):
        return
    if day in [int(x_) for x_ in (state["config"].get("unlock_keep_tier_days") or [])]:
        return                                     # the hour-0 route plan covers today's quadrant (sd_land_virtual)'''
    if "unlock_keep_tier_days" in src:
        return src
    assert src.count(old) == 1, "entry anchor for keep_tier_days"
    return src.replace(old, new)


def cassette(src):
    """DSM cassette (user 2026-09-29: "a deterministic cassette machine up until then"): on days 6 .. until_day-1 the
    day's targets come from config["cassette"]["file"] (scripts/build_dsm_cassette_20260929.py: DSM's median end-of-day
    counts by revealed shop-type mix) instead of the policy: animals added / strawberry, melon, tomato, carrot tiles
    planted = target - what the farm has now (never negative), wheat = DSM's plantings of the day, hands and quadrants
    as DSM. An unseen mix uses the recorded mix of the same size with the largest overlap (then the most games). The
    policy keeps observing and plans again from until_day."""
    old = '''            proposal = state["policy"].propose(obs, state["policy_memory"])
            state["policy_memory"] = proposal["memory"]'''
    new = old + '''
            _cassette_apply(state, obs, proposal, day)'''
    helper = '''

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
    if int(row.get("wheat_plant", 0)):
        plants["WHEAT"] = int(row["wheat_plant"])
    adds = {s: max(0, int(end.get(s, 0)) - cur[s]) for s in ("COW", "SHEEP", "GOOSE")}
    owned = len(farm.get("unlocked_quadrants") or ["NW"])
    today = proposal["today"]
    today.update(plant_counts={k: v for k, v in plants.items() if v}, animal_add_counts={k: v for k, v in adds.items() if v},
                 animal_retire_counts={}, hands=int(row["hands"]), target_land_count=max(owned, int(row["land"])),
                 land_add_count=max(0, int(row["land"]) - owned),
                 target_animals={s: cur[s] + adds[s] for s in ("COW", "SHEEP", "GOOSE")})
    state["cassette_last"] = dict(day=day, mix=mix, fallback=fallback, n=row["n"])
'''
    if "_cassette_apply" in src:
        return src
    assert src.count(old) == 1 and src.count("\n\ndef _unlock_execution(") == 1
    src = src.replace(old, new)
    return src.replace("\n\ndef _unlock_execution(", helper + "\n\ndef _unlock_execution(", 1)


def fill_free(src):
    """3-quadrant fixes (2026-09-29, n18rc vs the leaders): (1) config["cassette"]["melon_day6"] = n plants exactly n
    melons on day 6 (DSM's 4) instead of topping up to the cassette's 12 - topping up the day-1 tiles the opening lost
    put 42 second-wave melons into DSM's day-16 flood (138 / 100 / 72 a melon vs DSM's 183); (2) config["fill_free"] =
    {"from_day", "to_day", "crops"}: empty unlocked tiles left after the day's plantings get the listed crops in turn
    (DSM fills its 3rd quadrant with wheat on day 8 and carrots on days 9-10; we left 24 tiles empty on day 11 vs 2.8)."""
    old = '''            _cassette_apply(state, obs, proposal, day)'''
    new = '''            _cassette_apply(state, obs, proposal, day)
            _fill_free_apply(state, obs, proposal, day)'''
    old_mel = '''    plants = {c: max(0, int(end.get(c, 0)) - cur[c]) for c in ("STRAWBERRY", "MELON", "TOMATO", "CARROT")}'''
    new_mel = '''    plants = {c: max(0, int(end.get(c, 0)) - cur[c]) for c in ("STRAWBERRY", "MELON", "TOMATO", "CARROT")}
    if cfg.get("melon_day6") is not None:     # DSM's day-6 melons exactly, never a top-up on other days
        plants["MELON"] = int(cfg["melon_day6"]) if day == 6 else 0'''
    helper = '''

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
'''
    if "_fill_free_apply" in src:
        return src
    assert src.count(old) == 1 and src.count(old_mel) == 1
    src = src.replace(old, new).replace(old_mel, new_mel)
    return src.replace("\n\ndef _unlock_execution(", helper + "\n\ndef _unlock_execution(", 1)



def fill_free_count(src):
    """entry: config["fill_free"]["count"] = ["weed", "harvest", "ending"] (exact day-11 benchmark 2026-09-29: n18rc70 leaves
    3.2-3.9 tiles empty a day on days 12-17 and 2-3 weed tiles a day from day 18, DSM < 1 of each). fill_free counted
    only empty tiles and took ALL of today's plantings off them, but today's replants go onto tiles harvested today: 3
    empty tiles and 5 wheat replants filled nothing. Our ending strawberries decay into weeds (21.5 a game, DSM 2.2: it
    digs the live plant at its end and replants) that sat a median 17 steps (p90 66) before a DIG. With "count":
      weed     WEED tiles are free (the executor digs before it plants)
      harvest  one-time crop tiles at or past the tiler's release age (config tiles.release_age) are free - their
               harvest today makes room for today's replant
      ending   strawberry / tomato tiles past their last production (max_lifespan_step set) are free (they decay today)"""
    old = """    free = sum(1 for r_ in farm["tiles"] for t_ in r_ if t_ is None)
    today = proposal["today"]"""
    new = """    free = sum(1 for r_ in farm["tiles"] for t_ in r_ if t_ is None)
    cnt_ = set(cfg.get("count") or ())
    if cnt_:
        rel_ = dict({"WHEAT": 3, "CARROT": 3, "MELON": 10}, **((state["config"].get("tiles") or {}).get("release_age") or {}))
        extra_ = {"weed": 0, "harvest": 0, "ending": 0}
        for r_ in farm["tiles"]:
            for t_ in r_:
                if not isinstance(t_, dict):
                    continue
                if t_.get("kind") == "WEED" and "weed" in cnt_:
                    extra_["weed"] += 1
                elif t_.get("kind") == "PLANT":
                    c_ = t_.get("crop")
                    if (c_ in ("WHEAT", "CARROT", "MELON") and "harvest" in cnt_
                            and day - int(t_.get("planted_day", day)) >= int(rel_.get(c_, 99))):
                        extra_["harvest"] += 1
                    elif (c_ in ("STRAWBERRY", "TOMATO") and "ending" in cnt_
                          and int(t_.get("max_lifespan_step", -1) or -1) >= 0):
                        extra_["ending"] += 1
        free += sum(extra_.values())
        state["fill_free_count_last"] = dict(day=day, **extra_)
    today = proposal["today"]"""
    if "fill_free_count_last" in src:
        return src
    assert src.count(old) == 1, "entry anchor for fill_free_count (needs --fill-free)"
    src = src.replace(old, new)
    # "max": at most this many fill plantings a day (n18rc79 filled 21 wheat on day 11 and took the tiles of the
    # planner's day 12-13 strawberries and a sheep pasture: strawberries -15 units in 114514221)
    old_loop = """    for i in range(max(0, free)):
        c = crops[i % len(crops)]"""
    assert src.count(old_loop) == 1, "entry anchor for fill_free max"
    return src.replace(old_loop, """    for i in range(max(0, min(free, int(cfg.get("max", 999))))):
        c = crops[i % len(crops)]""")

def fill_look(src):
    """entry: config["fill_look"] = {"from": d0, "to": d1, "crop": "WHEAT", "span": 3, "max": n} - a lookahead fill
    (exact day-11 benchmark 2026-09-29: we idle 88 tile-days (empty + weed) after day 11, DSM 33; the count fill n18rc79
    planted 21 wheat on day 11 on the tiles the planner wanted for day 12-13 strawberries, and a daily cap only
    approximated the fix, n18rc84 +105). Pass 1 compiles today's tile plan as usual; tiles that are empty (or weeds) at
    the start of days d+1 .. d+span in that plan are free for a whole wheat cycle, so that many extra plantings of `crop`
    (at most `max`) join today's plantings and the plan is compiled again (pass 2)."""
    old = """            _fill_free_apply(state, obs, proposal, day)
            plan, state["tile_memory"], audit = _build_plan("""
    new = """            _fill_free_apply(state, obs, proposal, day)
            _fill_look_apply(state, obs, proposal, day)
            plan, state["tile_memory"], audit = _build_plan("""
    helper = '''


def _fill_look_apply(state, obs, proposal, day):
    cfg = state["config"].get("fill_look")
    if not cfg or not (int(cfg.get("from", 12)) <= day <= int(cfg.get("to", 26))):
        return
    import copy as _copy
    try:
        p1, _m1, _a1 = _build_plan(obs, _copy.deepcopy(proposal), _copy.deepcopy(state["tile_memory"]),
                                   state["config"].get("tiles"))
    except Exception as exc:
        state["fill_look_last"] = dict(day=day, error=str(exc)[:120])
        return
    B = p1.get("board") or []
    span = int(cfg.get("span", 3))
    days_ = [d_ for d_ in range(day + 1, min(day + span, 29) + 1)]
    free3 = [t for t in range(100) if days_ and all(d_ < len(B) and B[d_] and B[d_][t] == " ." for d_ in days_)]
    k = min(len(free3), int(cfg.get("max", 99)))
    if k > 0:
        pc = proposal["today"].setdefault("plant_counts", {})
        crop = cfg.get("crop", "WHEAT")
        pc[crop] = int(pc.get(crop, 0)) + k
    state["fill_look_last"] = dict(day=day, free=len(free3), added=k)
'''
    if "_fill_look_apply" in src:
        return src
    assert src.count(old) == 1, "entry anchor for fill_look"
    src = src.replace(old, new)
    anchor = "\n\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, helper + anchor)


def tile_exact(src):
    """entry (diagnostic): config["tile_exact"] = {"file": "...json", "from": 11, "extra_hands": k} - from day `from` the
    executor's tile plan (kb._T) is DSM's own recorded plan of this world (scripts/export_tile_plans.py: plantings per
    tile and day, structures, animals, removals, harvest cohorts, hands per day) instead of the planner + tiler output;
    hands[d] + k from `from` on. User 2026-09-29: "tile-exact throughout the game and action-exact up to day 11. With
    extra hand ... walk me day by day what we got wrong" (with --prefix-steps 264 the board matches DSM's at day 11)."""
    old = """            kb._T = kb.TilePlanView.from_dict(plan)
"""
    new = """            kb._T = kb.TilePlanView.from_dict(plan)
            te_ = state["config"].get("tile_exact")
            if te_ and day >= int(te_.get("from", 11)):
                if "tile_exact_plan" not in state:
                    P_ = _json.loads((_STUDY / te_["file"]).read_text(encoding="utf-8"))
                    state["tile_exact_plan"] = P_ if "n" in P_ else list(P_.values())[0]
                P_ = _json.loads(_json.dumps(state["tile_exact_plan"]))
                x_ = int(te_.get("extra_hands", 0) or 0)
                P_["hands"] = [int(h) + (x_ if d_ >= int(te_.get("from", 11)) and int(h) > 0 else 0)
                               for d_, h in enumerate(P_["hands"])]
                kb._T = kb.TilePlanView.from_dict(P_)
                state["tile_exact_day"] = day
"""
    if "tile_exact_plan" in src:
        return src
    assert src.count(old) == 1, "entry anchor for tile_exact"
    return src.replace(old, new)


def carry_over(src):
    """entry: config["carry_over"] = {"crops": ["WHEAT"], "from": 7, "to": 12, "max": 12} - yesterday's planned plantings of a
    listed crop that did not happen (compiled plan's plant counts vs the plants with yesterday's planted day on today's
    board) join today's plantings (user 2026-09-29, wheat day by day: day 8 plans 16.4 wheat as DSM plants 17.2, we plant
    9.8 - dawn cash 45 vs 414, the third quadrant bought later - and day 9 plans its usual 5.9: the missing day-8 wheat is
    never re-requested; day 10 wheat tiles 15-18 vs DSM's 25)."""
    old = """            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))
"""
    new = """            _carry_over_apply(state, obs, proposal, day)
            plan, state["tile_memory"], audit = _build_plan(obs, proposal, state["tile_memory"], state["config"].get("tiles"))
            state["_carry_planned"] = dict(day=day, counts=dict((audit.get("semantic_today") or {}).get("plant_counts") or {}))
"""
    helper = '''


def _carry_over_apply(state, obs, proposal, day):
    cfg = state["config"].get("carry_over")
    prev = state.get("_carry_planned")
    if not cfg or not prev or int(prev.get("day", -9)) != day - 1:
        return
    if not (int(cfg.get("from", 7)) <= day <= int(cfg.get("to", 12))):
        return
    farm = obs["farms"][int(obs["player"])]
    done = {}
    for r_ in farm["tiles"]:
        for t_ in r_:
            if isinstance(t_, dict) and t_.get("crop") and int(t_.get("planted_day", -1)) == day - 1:
                done[t_["crop"]] = done.get(t_["crop"], 0) + 1
    pc = proposal["today"].setdefault("plant_counts", {})
    added = {}
    for crop in cfg.get("crops") or ["WHEAT"]:
        miss = int(prev["counts"].get(crop, 0) or 0) - done.get(crop, 0)
        k = min(max(0, miss), int(cfg.get("max", 12)))
        if k > 0:
            pc[crop] = int(pc.get(crop, 0)) + k
            added[crop] = k
    state["carry_over_last"] = dict(day=day, added=added, planned=prev["counts"], done=done)
'''
    if "_carry_over_apply" in src:
        return src
    assert src.count(old) == 1, "entry anchor for carry_over"
    src = src.replace(old, new)
    anchor = "\n\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, helper + anchor)


def block_front(src):
    """block policy (scripts/semantic_strategy_blocks_20260928.py): config policy.front_load_crops = [crops] lets those
    crops use the whole 3-day block's scheduled plantings from the block's first day (the tiler still clips what does not
    fit; the rest carries to the next day); config policy.plant_scale = {crop: factor} multiplies the scheduled plantings
    of those crops. User 2026-09-29 ("if we are having empty tiles, why extra hand is not working these tiles?" -> "just
    plan more?"): after day 11 we plant exactly what the plan asks (148 / 148, DSM 183) while holding 70 idle tile-days (DSM
    33) and 262 idle hand-hours (DSM 54); the plan back-loads each block (days 21-23: 2.6 / 8.8 / 15.0, DSM 10.2 / 13.8 /
    12.7), so tiles freed on a block's first day wait."""
    old = """        for d in range(block['start'],min(day,block['end'])+1):
            for key in cumulative:cumulative[key].update(block['schedule'][str(d)][key])
"""
    new = """        for d in range(block['start'],min(day,block['end'])+1):
            for key in cumulative:cumulative[key].update(block['schedule'][str(d)][key])
        fl_=set(self.config.get('front_load_crops') or ())
        if fl_:                                    # front-load: the block's later plantings of these crops allowed now
            for d in range(min(day,block['end'])+1,block['end']+1):
                for sp,n in block['schedule'][str(d)]['plant_counts'].items():
                    if sp in fl_:cumulative['plant_counts'][sp]+=n
        for sp,f in (self.config.get('plant_scale') or {}).items():
            if cumulative['plant_counts'].get(sp):cumulative['plant_counts'][sp]=int(round(cumulative['plant_counts'][sp]*float(f)))
"""
    if "front_load_crops" in src:
        return src
    assert src.count(old) == 1, "block policy anchor for block_front"
    return src.replace(old, new)


def cassette_day6(src):
    """config["cassette"]["only_day6"] = [crops] (2026-09-29): those crops are topped up to the cassette's target on day
    6 only. Strawberries are DSM's free quantity (11-34 by game); the mix median (21-22) pushed extra strawberries in on
    days 9-11 in games where DSM kept 11, and planted then they produce into the day 19-23 price crash."""
    old = '''    adds = {s: max(0, int(end.get(s, 0)) - cur[s]) for s in ("COW", "SHEEP", "GOOSE")}'''
    new = '''    for c_ in (cfg.get("only_day6") or ()):
        if day != 6:
            plants[c_] = 0
    adds = {s: max(0, int(end.get(s, 0)) - cur[s]) for s in ("COW", "SHEEP", "GOOSE")}'''
    if "only_day6" in src:
        return src
    assert src.count(old) == 1
    return src.replace(old, new)


def late_floor(src):
    """config["cassette"]["late_floor"] = true (2026-09-29): on days 12-26 the day's plantings are raised so that wheat,
    tomato and carrot tiles reach DSM's median end-of-day counts (cassette file key "late_floor"; DSM's crops after day
    12 vary little by shop mix: wheat 16-27, tomatoes 10 from day 18, carrots rising to 18 by day 26). Only a floor:
    the planner's own plantings stand when larger; herd and strawberries are left to the planner."""
    old = '''            _fill_free_apply(state, obs, proposal, day)'''
    new = '''            _late_floor_apply(state, obs, proposal, day)
            _fill_free_apply(state, obs, proposal, day)'''
    helper = '''

def _late_floor_apply(state, obs, proposal, day):
    cfg = state["config"].get("cassette")
    if not cfg or not cfg.get("late_floor"):
        return
    if "cassette_late" not in state:
        state["cassette_late"] = _json.loads((_STUDY / cfg["file"]).read_text(encoding="utf-8")).get("late_floor") or {}
    row = state["cassette_late"].get(str(day))
    if not row:
        return
    cur = _Counter()
    for r_ in obs["farms"][int(obs["player"])]["tiles"]:
        for t_ in r_:
            if isinstance(t_, dict) and t_.get("crop"):
                cur[t_["crop"]] += 1
    pc = proposal["today"].setdefault("plant_counts", {})
    for c_, tgt_ in row.items():
        need_ = int(tgt_) - cur[c_] - int(pc.get(c_, 0))
        if need_ > 0:
            pc[c_] = int(pc.get(c_, 0)) + need_
'''
    if "_late_floor_apply" in src:
        return src
    assert src.count(old) == 1, "needs the fill_free patch"
    src = src.replace(old, new)
    return src.replace("\n\ndef _unlock_execution(", helper + "\n\ndef _unlock_execution(", 1)


def cassette_crops(src):
    """config["cassette"]["crops"] = [crops] (2026-09-29 snapshot): on cassette days only these crops take the
    cassette's plantings; every other crop keeps the planner's own count (herd, hands and land still follow the
    cassette). In lead-dsm-114436723 the planner asked for 16 carrots on day 8 (DSM had 11) and the cassette's mix
    median replaced them with 0; on day 9 the planner asked for DSM's exact 11 strawberries, the cassette 16."""
    old = '''    today.update(plant_counts={k: v for k, v in plants.items() if v}, animal_add_counts={k: v for k, v in adds.items() if v},'''
    new = '''    if cfg.get("crops") is not None:            # only the listed crops from the cassette, the rest from the planner
        keep_ = dict(today.get("plant_counts") or {})
        for c_ in list(keep_):
            if c_ in cfg["crops"]:
                keep_.pop(c_)
        for c_ in cfg["crops"]:
            if plants.get(c_):
                keep_[c_] = plants[c_]
        plants = keep_
    today.update(plant_counts={k: v for k, v in plants.items() if v}, animal_add_counts={k: v for k, v in adds.items() if v},'''
    if 'cfg.get("crops") is not None' in src:
        return src
    assert src.count(old) == 1
    return src.replace(old, new)


def cassette_boost(src):
    """config["cassette"]["end_boost"] = {crop: n} (2026-09-29): the cassette's end-of-day target for the crop is raised by
    n. Strawberry volume denies the leader's strawberry price: fewer strawberries helped the leader more than us twice
    (n18rc9 day-6-only strawberries: leader strawberry revenue +3,943; n18rc16 planner crops: +1,152)."""
    old = '''    end = row["end_counts"]'''
    new = '''    end = dict(row["end_counts"])
    for c_, n_ in (cfg.get("end_boost") or {}).items():
        end[c_] = int(end.get(c_, 0)) + int(n_)'''
    if "end_boost" in src:
        return src
    assert src.count(old) == 1
    return src.replace(old, new)


def make(new_id, base, executor, gate, config, note, add_files=(), switch=False, kbplan=False, guard=False,
         until=False, extra=False, cas=False, fill=False, cas6=False, late=False, cas_crops=False, boost=False, ebd=False, sfl=False, sdf=False, cpx=False, rab=False, hxt=False, dmc=False, orp=False, rpl=False, tlr=False, ffc=False, flk=False, tex=False, cov=False, bfr=False, peg=False, ktd=False, efe=False, sfd=False, eaj=False, efr=False, lrs=False, dcl=False, psd=False, cws=False, scb=False, fnl=False, wsw=False, smo=False, gfl=False, ffp=False, sbt=False, pkh=False, yfl=False, csb=False, e68=False):
    src, dst = STUDY / "candidates" / base, STUDY / "candidates" / new_id
    assert src.is_dir(), src
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    proj = dst / "project"
    if executor:
        shutil.copy(ROOT / executor, proj / EXE)
    if gate:
        p = proj / POLICY
        p.write_text(land_gate(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    for spec in add_files:                         # SRC:DEST (repo-relative source, project-relative destination)
        s_, d_ = spec.split(":")
        (proj / d_).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / s_, proj / d_)
    if switch or kbplan:
        p = proj / ENTRY
        p.write_text(opening_switch(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if kbplan:
        p = proj / ENTRY
        p.write_text(kbplan_switch(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if guard:
        p = proj / ENTRY
        p.write_text(bank_guard(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if until:
        pe, pu = proj / ENTRY, proj / "scripts/semantic_opening_umg_20260929.py"
        se, su = opening_until(pe.read_text(encoding="utf-8"), pu.read_text(encoding="utf-8"))
        pe.write_text(se, encoding="utf-8", newline="\n")
        pu.write_text(su, encoding="utf-8", newline="\n")
    if extra:
        p = proj / ENTRY
        p.write_text(plant_extra(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if cas:
        p = proj / ENTRY
        p.write_text(cassette(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if fill:
        p = proj / ENTRY
        p.write_text(fill_free(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if cas6:
        p = proj / ENTRY
        p.write_text(cassette_day6(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if late:
        p = proj / ENTRY
        p.write_text(late_floor(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if cas_crops:
        p = proj / ENTRY
        p.write_text(cassette_crops(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if boost:
        p = proj / ENTRY
        p.write_text(cassette_boost(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if ebd:
        p = proj / ENTRY
        p.write_text(exec_by_day(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if sfl:
        p = proj / ENTRY
        p.write_text(sell_floor(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if sdf:
        p = proj / ENTRY
        p.write_text(seed_first(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if cpx:
        p = proj / ENTRY
        p.write_text(cassette_prefix(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if rab:
        p = proj / ENTRY
        p.write_text(replay_abort(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if hxt:
        p = proj / ENTRY
        p.write_text(hands_extra(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if dmc:
        p = proj / ENTRY
        p.write_text(demand_cassette(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if orp:
        p = proj / ENTRY
        p.write_text(oracle_plan(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if rpl:
        p = proj / ENTRY
        p.write_text(replant_same_day(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if tlr:
        p = proj / "scripts/semantic_strategy_tiles_20260928.py"
        p.write_text(tiler_rules(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if ffc:
        p = proj / ENTRY
        p.write_text(fill_free_count(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if flk:
        p = proj / ENTRY
        p.write_text(fill_look(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if tex:
        p = proj / ENTRY
        p.write_text(tile_exact(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if cov:
        p = proj / ENTRY
        p.write_text(carry_over(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if bfr:
        p = proj / "scripts/semantic_strategy_blocks_20260928.py"
        p.write_text(block_front(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if peg:
        p = proj / ENTRY
        p.write_text(plant_extra_gate(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if ktd:
        p = proj / ENTRY
        p.write_text(keep_tier_days(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if efe:
        p = proj / ENTRY
        p.write_text(early_fert(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if sfd:
        p = proj / ENTRY
        p.write_text(seed_first_by_day(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if eaj:
        p = proj / ENTRY
        p.write_text(early_animal_jit(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if efr:
        p = proj / ENTRY
        p.write_text(early_fert_runner(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if lrs:
        p = proj / ENTRY
        p.write_text(land_reserve(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if dcl:
        p = proj / ENTRY
        p.write_text(det_clock(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if psd:
        p = proj / "scripts/semantic_strategy_blocks_20260928.py"
        p.write_text(plant_scale_days(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if cws:
        p = proj / ENTRY
        p.write_text(cassette_wheat_scale(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if scb:
        p = proj / ENTRY
        p.write_text(shop_crop_boost(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if fnl:
        p = proj / ENTRY
        p.write_text(fill_new_land(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if wsw:
        p = proj / ENTRY
        p.write_text(window_swap(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if csb:
        p = proj / ENTRY
        p.write_text(cassette_straw_buyers(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if yfl:
        p = proj / ENTRY
        p.write_text(yarn_floor(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if pkh:
        p = proj / ENTRY
        p.write_text(peak_hand(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if sbt:
        p = proj / ENTRY
        p.write_text(straw_batch(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        p = proj / "scripts/semantic_tile_allocator_20260928.py"
        p.write_text(anchor_live_alloc(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if ffp:
        p = proj / ENTRY
        p.write_text(fert_force_plan(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if gfl:
        p = proj / ENTRY
        p.write_text(gap_fill(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if smo:
        p = proj / "results/fresh/semantic_strategy_20260928/runtime/scripts/fragments/sem_maintenance.py"
        p.write_text(sm_occ_fragment(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
        p = proj / EXE
        p.write_text(sm_occ_executor(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if e68:
        p = proj / ENTRY
        p.write_text(e68_switch(p.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    if config:
        c = json.loads((proj / CFG).read_text(encoding="utf-8"))
        (proj / CFG).write_text(json.dumps(merge(c, json.loads(config)), indent=2), encoding="utf-8")
    m = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    for spec in add_files:
        m["files"].setdefault(spec.split(":")[1], "")
    changed = [k for k in m["files"] if m["files"][k] != sha(proj / k)]
    for k in m["files"]:
        m["files"][k] = sha(proj / k)
    m["candidate_id"] = new_id
    m["derived_from"] = dict(candidate=base, executor=executor, land_gate=gate, config=json.loads(config or "{}"), note=note,
                             changed_files=changed)
    (dst / "manifest.json").write_text(json.dumps(m, indent=1), encoding="utf-8")
    print(new_id, "<-", base, "| changed:", changed)


def e68_switch(src):
    """entry (2026-09-30, user: "for days 6-8 and 9-11 we need separate executor. For 6 we plan in all money generating
    goods to be brought back immediately then do other work"): config e68 {"days": [6, 7, 8], ...} - on those days the
    step is played by the E68 executor (agents/exec_e68.py, registered as scripts/exec_e68_20260930.py) on the day's tile
    plan (kb._T) instead of KB115LT2. The KB-only helpers (land-unlock dispatcher switch, early financing, land reserve,
    seed first) are skipped on those days; KB takes over the next day (its state starts on its first call)."""
    old = '''        _unlock_execution(state, obs, day, hour)
        _finance_execution(state, obs)
        result = kb.agent(obs, configuration)
        _land_reserve(state, obs, day, result)
        _seed_first(state, obs, day, result)'''
    new = '''        e68_ = state["config"].get("e68")
        if e68_ and day in [int(d_) for d_ in e68_.get("days", [6, 7, 8])]:
            from exec_e68_20260930 import e68_step as _e68_step
            result = _e68_step(obs, kb._T, e68_, state.setdefault("e68_state", {}))
            state["daily_diagnostic"]["e68"] = state["e68_state"].get("diag")
        else:
            _unlock_execution(state, obs, day, hour)
            _finance_execution(state, obs)
            result = kb.agent(obs, configuration)
            _land_reserve(state, obs, day, result)
            _seed_first(state, obs, day, result)'''
    if "_e68_step" in src:
        return src
    assert src.count(old) == 1, "entry anchor for e68"
    src = src.replace(old, new)
    # board check (user 2026-09-30: "cut off at day 8 and check the board"): config stop_after_day - after that day our
    # seat only PASSes (no planner / executor calls), so the rest of the game costs nothing; read the board at that dusk
    old2 = "    obs.update(day=day, hour=hour)\n"
    new2 = old2 + '''    if state["config"].get("stop_after_day") is not None and day > int(state["config"]["stop_after_day"]):
        state["last_action"] = {"farmer": ["PASS"], "hands": [], "market": []}
        return state["last_action"]
'''
    assert src.count(old2) == 1, "entry anchor for stop_after_day"
    return src.replace(old2, new2)


def exec_by_day(src):
    """entry: config["executor_by_day"] = [{"from": d0, "to": d1, "cfg": {executor key: value}}] sets those executor
    flags only on days d0..d1 (other days: the candidate's own value) - e.g. a fertilizer reserve only after the day 6-10
    cash window (n18rc19: keeping fertilizer in the cash window cost the day-8 wheat seeds and land, wheat 17.8 -> 6.8
    tiles on day 10, -5.9k in 114436723)"""
    if "_exec_by_day" in src:
        return src
    fn = '''

def _exec_by_day(state, day):
    wins = state["config"].get("executor_by_day")
    if not wins:
        return
    kb = state["kb"]
    base = state.setdefault("_ebd_base", {})
    want = {}
    for w in wins:
        for k, v in w["cfg"].items():
            if k not in base:
                base[k] = kb.CFG.get(k)
            if int(w.get("from", 0)) <= day <= int(w.get("to", 99)):
                want[k] = v
    for k, v0 in base.items():
        kb.CFG[k] = want.get(k, v0)
'''
    old = """        _finance_execution(state, obs)
        result = kb.agent(obs, configuration)"""
    assert src.count(old) == 1, "entry anchor for executor_by_day"
    src = src.replace(old, """        _finance_execution(state, obs)
        _exec_by_day(state, day)
        result = kb.agent(obs, configuration)""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def sell_floor(src):
    """entry: config["sell_floor"] = {"floors": {product: price}, "until_day": d, "room": r} - every SELL order of a listed
    product is cut so that no unit (walked one at a time up the market stock with the engine price curve) sells below
    the product's floor, on days < until_day, unless shed + carried goods are within `room` of the 100 cap (a midnight
    overflow deletes goods). Mechanism (profile_px, n18rc8x vs the leader in the same 8 worlds): on any day our price
    equals the leader's; the leader's +11k price advantage (wool 131 vs 103, strawberries 143 vs 128, milk 87 vs 75) is
    WHICH days each side sells - we keep selling into crashes (milk 23 @ 3, wool 9 @ 1, strawberries 11-17 a day @ 9-48)
    while the leader holds and sells after the market recovers (milk 26 -> 117 by day 27)."""
    if "_sell_floor" in src:
        return src
    fn = """

def _sell_floor(state, obs, day, result):
    sf = state["config"].get("sell_floor")
    if not sf or not isinstance(result, dict) or day >= int(sf.get("until_day", 29)):
        return
    dg_ = (state.get("daily_diagnostic") or {}).setdefault("sell_floor", {"calls": 0, "off_room": 0, "cut": {}, "sold": {}, "loads": []})
    dg_["calls"] += 1
    kb = state["kb"]
    priv = obs.get("private") or {}
    load = sum(int(v or 0) for v in (priv.get("shed") or {}).values())
    load += sum(int(v or 0) for inv in (priv.get("inventories") or []) for v in (inv or {}).values())
    if sf.get("room_mode") == "proj":             # the executor's own midnight projection: load now + planned harvests
        T_ = (kb._S or {}).get("tier") or {}
        if T_.get("day") == day and T_.get("_load_now") is not None:
            load = int(T_.get("_load_now", 0) or 0) + int(T_.get("_harv_left", 0) or 0)
    if sf.get("room_mode") == "hold":             # tonight's shed: held floored goods + feed wheat + the midnight dump
        T_ = (kb._S or {}).get("tier") or {}      # (carried + planned harvests); other shed goods sell during the day
        shed_ = priv.get("shed") or {}
        load = sum(int(shed_.get(p_, 0) or 0) for p_ in (sf.get("floors") or {}))
        if not sf.get("no_wheat"):               # the dawn wheat is last night's dump, used up by pickups / sales by tonight
            load += int(shed_.get("WHEAT", 0) or 0)
        load += sum(int(v or 0) for inv in (priv.get("inventories") or []) for v in (inv or {}).values())
        if T_.get("day") == day:
            load += int(T_.get("_harv_left", 0) or 0)
    if int(obs.get("step", 0) or 0) % 24 in (0, 1, 2, 6, 12, 18, 22):
        dg_["loads"].append([int(obs.get("step", 0) or 0) % 24, int(load)])
    if load >= 100 - int(sf.get("room", 12)):
        dg_["off_room"] += 1
        return
    stock = dict(((obs.get("market") or {}).get("inventory")) or {})
    floors = sf.get("floors") or {}
    excess = 0
    if sf.get("hold_max") is not None:           # held floored goods take shed room the planner's night-load logic needs
        held = sum(int(((priv.get("shed") or {}).get(p_, 0)) or 0) for p_ in floors)
        if sf.get("hold_cap"):                   # keep at most hold_max held: the excess sells at market (not the backlog)
            excess = max(0, held - int(sf["hold_max"]))
        elif held > int(sf["hold_max"]):
            return
    sold = _Counter()
    kept = []
    for o in result.get("market") or []:
        if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] in floors and o[1] in stock:
            p, n = o[1], int(o[2])
            k = 0
            while k < n and kb._mkt_price(p, int(stock[p]) + sold[p] + k) >= float(floors[p]):
                k += 1
            if excess > 0 and k < n:              # hold_cap: the units above the cap go at the market price
                x_ = min(n - k, excess)
                k += x_
                excess -= x_
            sold[p] += k
            state.setdefault("sell_floor_cut", _Counter())[p] += n - k
            dg_["cut"][p] = dg_["cut"].get(p, 0) + n - k
            dg_["sold"][p] = dg_["sold"].get(p, 0) + k
            if k <= 0:
                continue
            o = [o[0], p, k] + list(o[3:])
        kept.append(o)
    result["market"] = kept
"""
    old = """        result = kb.agent(obs, configuration)"""
    assert src.count(old) == 1, "entry anchor for sell_floor"
    src = src.replace(old, """        result = kb.agent(obs, configuration)
        _sell_floor(state, obs, day, result)""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def seed_first(src):
    """entry: config["seed_first"] = {"days": [6, 8], "crop": "STRAWBERRY", "hold": ["GOOSE", "COW"]} - on those days the
    semantic plan's plantings of the crop are funded first: while today's plan still wants more of it than is planted
    today plus seeds in stock, a BUY_SEED for the deficit goes to the front of the orders and BUY_ANIMAL orders of the
    held species that would leave less cash than those seeds cost are dropped this step. Mechanism (user 2026-09-29
    "why are our harvests flatter than the leader's?"): current DSM plants its strawberry block on day 6 (10.7 tiles a game
    in the 88 library tapes, 11.6-16.4 in the EGG+MILK / MILK+MILK / EGG+FARM / FARM+MILK starts) and builds geese over
    days 6-10; our day-6 plan asks for it (15 / 12 / 21 in 114565764 / 114314080 / 114348036) but the executor buys
    seeds just in time and the day-6 money has gone to cows, geese, land and melons (1 / 0 / 9 strawberry seeds bought)
    - the block is planted on days 8-9 instead, on both parities, and produces into the crash."""
    if "_seed_first" in src:
        return src
    fn = """

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
"""
    old = """        result = kb.agent(obs, configuration)"""
    assert src.count(old) == 1, "entry anchor for seed_first"
    src = src.replace(old, """        result = kb.agent(obs, configuration)
        _seed_first(state, obs, day, result)""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def cassette_prefix(src):
    """entry: config["cassette"]["prefix_keys"] = true - from day 9 the cassette row is looked up by the ORDERED prefix
    'day-6 mix|later shops' (build_dsm_cassette_20260929.py --prefix) when that row has >= prefix_min_n games (default 3),
    else the sorted mix as before (user 2026-09-29: the sorted day-9 mix EGG+EGG+MILK pools EGG+EGG starts, DSM 11 -> 16
    strawberries, with EGG+MILK starts, 21 -> 21: its target 22 made us plant ~11 strawberries on day 9)"""
    old = """    mix = "+".join(mine)
    row, fallback = rows.get(mix), False"""
    if "prefix_keys" in src:
        return src
    assert src.count(old) == 1, "entry anchor for cassette_prefix"
    return src.replace(old, old + """
    if cfg.get("prefix_keys") and len(names) >= 3:
        pk_ = "+".join(sorted(kind(s) for s in names[:2])) + "|" + "+".join(kind(s) for s in names[2:])
        if pk_ in rows and int(rows[pk_].get("n", 0)) >= int(cfg.get("prefix_min_n", 3)):
            row, mix = rows[pk_], pk_""")


def replay_abort(src):
    """entry: config["replay_abort"] = {"threshold": coins, "horizon": steps} - at each dawn while the tape replay runs past
    day 6 (step 144 .. opening_until_step), the router's mgt_replay_shortfall (the tape's purchases over the horizon minus
    our cash and the value of its planned sales) is logged; above the threshold the planner takes over from that dawn.
    User 2026-09-29: fix n18rcx14's swing (114565764 -16.7k: the replay spent like DSM without DSM's income - purchases
    refused, day-10 milk 3 vs 12, a smaller farm at the handover)."""
    if "_replay_check" in src:
        return src
    fn = """

def _replay_check(state, obs, step, day, hour):
    ra = state["config"].get("replay_abort")
    if not ra or state.get("replay_abort") or hour != 0 or step < 144:
        return
    if step >= int(state["config"].get("opening_until_step", 144)):
        return
    mod_ = getattr(state.get("opening"), "module", None)
    dist_ = ra.get("metric") == "distance"         # board drift from the tape's own board (tiles), else cash shortfall
    f = getattr(mod_, "mgt_replay_distance" if dist_ else "mgt_replay_shortfall", None)
    if f is None:
        return
    try:
        sf = float(f(obs) if dist_ else f(obs, int(ra.get("horizon", 24))))
    except Exception:
        return
    state.setdefault("replay_shortfall", {})[day] = round(sf)
    STRATEGY_DIAGNOSTICS.append(dict(day=day, phase="replay_check", shortfall=round(sf),
                                     cash=obs["farms"][obs["player"]]["money"]))
    if sf > float(ra.get("threshold", 300)):
        state["replay_abort"] = step
"""
    old = """    if step < int(state["config"].get("opening_until_step", 144)):
        opening = state["opening"]"""
    assert src.count(old) == 1, "entry anchor for replay_abort"
    src = src.replace(old, """    _replay_check(state, obs, step, day, hour)
    if step < int(state["config"].get("opening_until_step", 144)) and not state.get("replay_abort"):
        opening = state["opening"]""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def hands_extra(src):
    """entry: config["hands_extra"] = {"from": d0, "to": d1, "n": k} - the day plan's hand count + k on days d0..d1 (after
    the cassette and the free-tile fill, before the tile plan). User 2026-09-29: "if we could replicate DSM's sale and
    execution we could afford one extra hand (<200 a day, < 4k over 20 days) ... skipping something while trying
    bring-backs might backfire" - every bring-back arm that fired lost other production (n18rc57: carrots -22, wheat -17,
    eggs -12 units a game) because the runs took hands off their routes."""
    if "_hands_extra" in src:
        return src
    fn = """

def _hands_extra(state, proposal, day):
    he = state["config"].get("hands_extra")
    if he and int(he.get("from", 12)) <= day <= int(he.get("to", 28)):
        proposal["today"]["hands"] = int(proposal["today"].get("hands", 0) or 0) + int(he.get("n", 1))
"""
    old = """            _fill_free_apply(state, obs, proposal, day)
            plan, state["tile_memory"], audit = _build_plan("""
    assert src.count(old) == 1, "entry anchor for hands_extra"
    src = src.replace(old, """            _fill_free_apply(state, obs, proposal, day)
            _hands_extra(state, proposal, day)
            plan, state["tile_memory"], audit = _build_plan(""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def demand_cassette(src):
    """entry: config["demand_cassette"] = {"file": "...json", "from": 12, "to": 28, "items": [...], "retire": false} - on
    those days each listed product's target is DSM's median count at the end of the day for our current demand for it
    (build_dsm_demand_cassette_20260929.py: the revealed shops that consume the product, single-product shops x2;
    the nearest demand level on record when ours is missing); crops are planted up to the target, animals bought up to
    it, and no animal is retired unless "retire" (user 2026-09-29 "semantic planner fix first": from DSM's exact day-11
    state the planner's targets diverged - 2 fewer sheep, 8 sheep retired on day 27, wheat 3-6 lower, 6 extra
    strawberries, tomatoes where DSM grows none).
    "replant": 1 - one-time crop tiles at or past the tiler's release age (config tiles.release_age: harvested today) do
    not count as current, so today's replants are planted (the plain difference target - dawn count missed them: wheat
    turns every 2-3 days); "keep_planner": 1 - a crop's plantings are never below the planner's own count."""
    if "_demand_apply" in src:
        return src
    fn = """

_DEMAND_SHOPS = {"BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"], "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
                 "YARN_STORE": ["WOOL"], "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
                 "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"], "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"]}


def _demand_apply(state, obs, proposal, day):
    cfg = state["config"].get("demand_cassette")
    if not cfg or not (int(cfg.get("from", 12)) <= day <= int(cfg.get("to", 28))):
        return
    if "demand_table" not in state:
        state["demand_table"] = _json.loads((_STUDY / cfg["file"]).read_text(encoding="utf-8"))
    D = state["demand_table"]
    names = [s if isinstance(s, str) else (s or {}).get("name") for s in (obs.get("town") or {}).get("unlocked_shops", [])]
    dem = _Counter()
    for s in names:
        prods = _DEMAND_SHOPS.get(s, [])
        for q in prods:
            dem[q] += 2 if len(prods) == 1 else 1
    farm = obs["farms"][int(obs["player"])]
    cur = _Counter()
    rel_ = dict({"WHEAT": 3, "CARROT": 3, "MELON": 10}, **((state["config"].get("tiles") or {}).get("release_age") or {}))
    for r_ in farm["tiles"]:
        for t_ in r_:
            if isinstance(t_, dict):
                if t_.get("animal"):
                    cur[t_["animal"]] += 1
                elif t_.get("crop"):
                    c_ = t_["crop"]
                    if (cfg.get("replant") and c_ in ("WHEAT", "CARROT", "MELON")
                            and day - int(t_.get("planted_day", day)) >= int(rel_.get(c_, 99))):
                        continue                   # harvested today: its replant is part of today's plantings
                    cur[c_] += 1
    today = proposal["today"]
    pc = dict(today.get("plant_counts") or {})
    adds = dict(today.get("animal_add_counts") or {})
    tgt_a = dict(today.get("target_animals") or {})
    used = {}
    for item in cfg.get("items") or list(D["table"]):
        rows = (D["table"].get(item) or {}).get(str(day)) or {}
        if not rows:
            continue
        k = int(dem[D["items"][item]])
        key = str(k) if str(k) in rows else min(rows, key=lambda q: (abs(int(q) - k), -int(q)))
        tgt = int(rows[key])
        used[item] = (k, tgt)
        if item in ("COW", "SHEEP", "GOOSE"):
            adds[item] = max(0, tgt - cur[item])
            tgt_a[item] = max(cur[item], tgt)
        else:
            pc[item] = max(0, tgt - cur[item], int(pc.get(item, 0) or 0) if cfg.get("keep_planner") else 0)
    today["plant_counts"] = {k: v for k, v in pc.items() if v}
    today["animal_add_counts"] = {k: v for k, v in adds.items() if v}
    today["target_animals"] = tgt_a
    if not cfg.get("retire"):
        today["animal_retire_counts"] = {}
    state["demand_last"] = dict(day=day, used=used)
"""
    old = """            _fill_free_apply(state, obs, proposal, day)"""
    assert src.count(old) == 1, "entry anchor for demand_cassette"
    src = src.replace(old, """            _demand_apply(state, obs, proposal, day)
            _fill_free_apply(state, obs, proposal, day)""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def oracle_plan(src):
    """entry (DIAGNOSTIC, exact-prefix cases only): config["oracle_plan"] = {"file": "...json", "from": 11, "to": 28} - the
    day's targets are DSM's ACTUAL end-of-day counts from its own continuation of this game (DSM tapes' daily boards):
    crops planted / animals bought up to them, animals above them retired, DSM's hand count hired. The game is found by
    our day-11 board, which the exact prefix makes DSM's own. What gap to DSM remains is execution + selling; the part it
    removes is the planner's (user 2026-09-29, the exact day-11 benchmark: n18rc8x -12,818 vs DSM over 9 current games)."""
    if "_oracle_apply" in src:
        return src
    fn = """

_ORACLE_CODES = {"STRAWBERRY": "ST", "WHEAT": "WH", "CARROT": "CA", "TOMATO": "TO", "MELON": "ME", "COW": "co", "SHEEP": "sh",
                 "GOOSE": "go"}


def _oracle_apply(state, obs, proposal, day):
    cfg = state["config"].get("oracle_plan")
    if not cfg or not (int(cfg.get("from", 11)) <= day <= int(cfg.get("to", 28))):
        return
    if "oracle_table" not in state:
        state["oracle_table"] = _json.loads((_STUDY / cfg["file"]).read_text(encoding="utf-8"))
    farm = obs["farms"][int(obs["player"])]
    cur = _Counter()
    mine = []
    for r_ in farm["tiles"]:
        for t_ in r_:
            lab = "."
            if t_ == "LOCKED" or (isinstance(t_, dict) and t_.get("kind") == "LOCKED"):
                lab = "L"
            elif isinstance(t_, dict):
                if t_.get("animal"):
                    cur[t_["animal"]] += 1
                    lab = _ORACLE_CODES.get(t_["animal"], ".")
                elif t_.get("crop"):
                    cur[t_["crop"]] += 1
                    lab = _ORACLE_CODES.get(t_["crop"], ".")
            mine.append(lab)
    if state.get("oracle_ep") is None:
        def dist(b):
            return sum(1 for a, c in zip(mine, b) if (a if a in _ORACLE_CODES.values() else ".") != (c if c in _ORACLE_CODES.values() else "."))
        ep, b = min(state["oracle_table"].items(), key=lambda kv: dist(kv[1]["day11"]))
        state["oracle_ep"], state["oracle_dist"] = ep, dist(b["day11"])
    O = state["oracle_table"][state["oracle_ep"]]
    tgt = O["counts"].get(str(day))
    if not tgt:
        return
    today = proposal["today"]
    pc, adds, ret = {}, {}, {}
    for item, n in tgt.items():
        if item in ("COW", "SHEEP", "GOOSE"):
            if n > cur[item]:
                adds[item] = n - cur[item]
            elif n < cur[item]:
                ret[item] = cur[item] - n
        elif n > cur[item]:
            pc[item] = n - cur[item]
    if cfg.get("plants") and O.get("plants", {}).get(str(day)) is not None:
        # DSM's ACTUAL plantings of the day (its end count already holds same-day replants of the tiles it harvests;
        # "end count - dawn count" replants them a day late: n18rco1 wheat 315 tile-days vs DSM 401)
        pc = {k: int(v) for k, v in O["plants"][str(day)].items() if int(v) > 0}
    today["plant_counts"] = pc
    today["animal_add_counts"] = adds
    today["animal_retire_counts"] = ret
    today["target_animals"] = {a: int(tgt.get(a, 0)) for a in ("COW", "SHEEP", "GOOSE")}
    if O.get("hands", {}).get(str(day)):
        today["hands"] = int(O["hands"][str(day)])
    state["oracle_last"] = dict(day=day, ep=state["oracle_ep"], dist=state.get("oracle_dist"))
"""
    old = """            _fill_free_apply(state, obs, proposal, day)"""
    assert src.count(old) == 1, "entry anchor for oracle_plan"
    src = src.replace(old, """            _fill_free_apply(state, obs, proposal, day)
            _oracle_apply(state, obs, proposal, day)""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def replant_same_day(src):
    """entry: config["replant_same_day"] = {"crops": ["WHEAT", "CARROT"], "from": d0, "to": d1} - the day's plantings of each
    crop are at least the number of our tiles of that crop at its release age (the tiler's harvest-and-replant age,
    config tiles.release_age) holding yield: every tile harvested today is replanted today (user 2026-09-29: "isn't the
    wheat timing a knock-on of following DSM's plant commands? what if we require immediate replant?" - with DSM's exact
    plantings our wheat stood 335 tile-days vs DSM's 401; our dawn boards hold ~3 empty tiles vs DSM's 0.7)."""
    if "_replant_apply" in src:
        return src
    fn = """

def _replant_apply(state, obs, proposal, day):
    cfg = state["config"].get("replant_same_day")
    if not cfg or not (int(cfg.get("from", 6)) <= day <= int(cfg.get("to", 27))):
        return
    rel = ((state["config"].get("tiles") or {}).get("release_age") or {})
    crops = cfg.get("crops") or ["WHEAT", "CARROT"]
    farm = obs["farms"][int(obs["player"])]
    ready = _Counter()
    for r_ in farm["tiles"]:
        for t_ in r_:
            if isinstance(t_, dict) and t_.get("crop") in crops and int(t_.get("yield_units", 0) or 0) > 0:
                if day - int(t_.get("planted_day", day)) >= int(rel.get(t_["crop"], 3)):
                    ready[t_["crop"]] += 1
    pc = dict(proposal["today"].get("plant_counts") or {})
    for c in crops:
        if ready[c] > int(pc.get(c, 0) or 0):
            pc[c] = ready[c]
    proposal["today"]["plant_counts"] = pc
    state["replant_last"] = dict(day=day, ready=dict(ready))
"""
    old = """            plan, state["tile_memory"], audit = _build_plan("""
    assert src.count(old) == 1, "entry anchor for replant_same_day"
    src = src.replace(old, """            _replant_apply(state, obs, proposal, day)
            plan, state["tile_memory"], audit = _build_plan(""")
    anchor = "\ndef _unlock_execution("
    assert src.count(anchor) == 1
    return src.replace(anchor, fn + anchor)


def tiler_rules(src):
    """tiler (scripts/semantic_strategy_tiles_20260928.py): config tiles.min_yield {crop: units} replaces the fixed 'an
    age-at-release crop projected below {WHEAT 5, CARROT 4, MELON 6} units waits a day' rule, and config
    tiles.plant_priority replaces the fixed allocation order (strawberry, tomato, melon, carrot, wheat) when the plan
    gives none (user 2026-09-29 exact day-11 benchmark: with DSM's own daily plantings the tiler clipped 90 wheat to 65 -
    on day 11 from DSM's identical board DSM planted 14 (8 wheat) and our tiler found room for 7: its age-3 wheat below
    5 units stayed a day longer, and carrots take the scarce room before wheat)."""
    a = """            if projected < {"WHEAT": 5, "CARROT": 4, "MELON": 6}[crop]:"""
    b = """        priorities = request.get("plant_priority", ["STRAWBERRY", "TOMATO", "MELON", "CARROT", "WHEAT"])"""
    if "min_yield" in src:
        return src
    assert src.count(a) == 1 and src.count(b) == 1, "tiler anchors"
    src = src.replace(a, """            if projected < dict({"WHEAT": 5, "CARROT": 4, "MELON": 6}, **(config.get("min_yield") or {}))[crop]:""")
    return src.replace(b, """        priorities = request.get("plant_priority", config.get("plant_priority") or ["STRAWBERRY", "TOMATO", "MELON", "CARROT", "WHEAT"])""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("make",))
    ap.add_argument("new_id")
    ap.add_argument("--base", default="strategy_v13_kb115lt2_harvest_exchange")
    ap.add_argument("--executor")
    ap.add_argument("--land-gate", action="store_true")
    ap.add_argument("--config")
    ap.add_argument("--note", default="")
    ap.add_argument("--add-file", action="append", default=[], help="SRC:DEST, registered in the manifest")
    ap.add_argument("--opening-switch", action="store_true", help="entry picks the opening from config['opening']")
    ap.add_argument("--kbplan", action="store_true", help="entry supports config opening=kb_plan (days 0-5 on a plan)")
    ap.add_argument("--bank-guard", action="store_true", help="entry counts the overage bank; config bank_guard acts on it")
    ap.add_argument("--opening-until", action="store_true", help="tape opening plays until config opening_until_step")
    ap.add_argument("--plant-extra", action="store_true", help="entry adds config plant_extra plantings to the proposal")
    ap.add_argument("--cassette", action="store_true", help="entry takes days 6..until_day-1 targets from config cassette")
    ap.add_argument("--fill-free", action="store_true", help="entry: cassette melon_day6 + config fill_free (plant free tiles)")
    ap.add_argument("--cassette-day6", action="store_true", help="entry: config cassette.only_day6 crops planted on day 6 only")
    ap.add_argument("--late-floor", action="store_true", help="entry: config cassette.late_floor raises days 12-26 plantings")
    ap.add_argument("--cassette-crops", action="store_true", help="entry: config cassette.crops = crops the cassette plants")
    ap.add_argument("--cassette-boost", action="store_true", help="entry: config cassette.end_boost raises cassette targets")
    ap.add_argument("--exec-by-day", action="store_true", help="entry: config executor_by_day day-windowed executor flags")
    ap.add_argument("--sell-floor", action="store_true", help="entry: config sell_floor per-product minimum sale price")
    ap.add_argument("--seed-first", action="store_true", help="entry: config seed_first funds a crop's planned seeds first")
    ap.add_argument("--cassette-prefix", action="store_true", help="entry: config cassette.prefix_keys ordered-prefix rows from day 9")
    ap.add_argument("--replay-abort", action="store_true", help="entry: config replay_abort hands the tape replay to the planner when insolvent")
    ap.add_argument("--hands-extra", action="store_true", help="entry: config hands_extra adds hands to the day plan")
    ap.add_argument("--demand-cassette", action="store_true", help="entry: config demand_cassette DSM's days 12-28 counts by demand")
    ap.add_argument("--oracle-plan", action="store_true", help="entry (diagnostic): config oracle_plan DSM's actual day counts")
    ap.add_argument("--replant", action="store_true", help="entry: config replant_same_day replants harvested one-time crops the same day")
    ap.add_argument("--tiler-rules", action="store_true", help="tiler: config tiles.min_yield / tiles.plant_priority")
    ap.add_argument("--fill-free-count", action="store_true", help="entry: config fill_free.count adds weed / harvest / ending tiles to the free count")
    ap.add_argument("--fill-look", action="store_true", help="entry: config fill_look plants a crop on tiles the compiled plan leaves empty for span days")
    ap.add_argument("--tile-exact", action="store_true", help="entry (diagnostic): config tile_exact swaps DSM's recorded tile plan in from a day")
    ap.add_argument("--carry-over", action="store_true", help="entry: config carry_over re-requests yesterday's planned plantings that did not happen")
    ap.add_argument("--block-front", action="store_true", help="block policy: config policy.front_load_crops / policy.plant_scale")
    ap.add_argument("--plant-extra-gate", action="store_true", help="entry: config plant_extra_gate / plant_extra_topup / plant_gate (shop-gated crops)")
    ap.add_argument("--keep-tier-days", action="store_true", help="entry: config unlock_keep_tier_days - no dispatcher switch at a land unlock on those days")
    ap.add_argument("--early-fert", action="store_true", help="entry: config early_fert - days 6-9 fertilizer placed at the shed and sold the same day")
    ap.add_argument("--seed-first-by-day", action="store_true", help="entry: config seed_first.by_day - the seed-first crop per day (with --seed-first)")
    ap.add_argument("--early-animal-jit", action="store_true", help="entry: config early_animal_jit - days 6-10 animals bought only for empty structures")
    ap.add_argument("--early-fert-runner", action="store_true", help="entry: config early_fert_runner - idle (PASS) units collect pen fertilizer and bring it to the shed")
    ap.add_argument("--land-reserve", action="store_true", help="entry: config land_reserve - on land days animals / seeds held until the land is affordable")
    ap.add_argument("--det-clock", action="store_true", help="entry: config det_clock - frozen executor clock, searches stop at count caps (smoke runs only)")
    ap.add_argument("--plant-scale-days", action="store_true", help="block policy: config policy.plant_scale_days window for plant_scale (with --block-front)")
    ap.add_argument("--cassette-wheat-scale", action="store_true", help="entry: config cassette.wheat_scale multiplies the cassette's daily wheat")
    ap.add_argument("--shop-crop-boost", action="store_true", help="entry: config shop_crop_boost - a crop's plantings scaled / added while a shop is open")
    ap.add_argument("--fill-new-land", action="store_true", help="entry: config fill_free.new_land - the quadrant bought today counts as free land for fill_free")
    ap.add_argument("--cassette-straw-buyers", action="store_true", help="entry: config cassette.straw_table - the cassette strawberry target by strawberry-buying shops revealed | yarn store")
    ap.add_argument("--yarn-floor", action="store_true", help="entry: config yarn_floor - sheep topped up to floor[open yarn stores] each morning in the window")
    ap.add_argument("--peak-hand", action="store_true", help="entry: config peak_hand - one more hire on days whose dawn farm holds >= ready_min ready strawberry units")
    ap.add_argument("--straw-batch", action="store_true", help="entry: config straw_batch - strawberry plantings move to batch days (reveal days); allocator ANCHOR_LIVE glues the batch to the live block")
    ap.add_argument("--fert-force-plan", action="store_true", help="entry: config fert_force_plan - executor sd_fert_force_tiles = the age-1 carrots whose tile the morning plan uses tomorrow (needs executor v18w)")
    ap.add_argument("--gap-fill", action="store_true", help="entry: config gap_fill - morning plan: a wheat / carrot replant moves onto the harvest day, 2-day gaps before another crop get a carrot (a wheat at age 3 is cut), longer gaps a wheat")
    ap.add_argument("--window-swap", action="store_true", help="entry: config window_swap - today's wheat / carrot plantings re-assigned by tile window (carrots to tight, wheat to long)")
    ap.add_argument("--sm-occ", action="store_true", help="maintenance optimizer + executor: config executor.sm_occ {crop: coins per tile-day} land cost")
    ap.add_argument("--e68", action="store_true", help="entry: config e68 - days 6-8 played by the E68 cash-chain executor (add --add-file agents/exec_e68.py:scripts/exec_e68_20260930.py)")
    a = ap.parse_args()
    make(a.new_id, a.base, a.executor, a.land_gate, a.config, a.note, a.add_file, a.opening_switch, a.kbplan,
         a.bank_guard, a.opening_until, a.plant_extra, a.cassette, a.fill_free, a.cassette_day6, a.late_floor,
         a.cassette_crops, a.cassette_boost, a.exec_by_day, a.sell_floor, a.seed_first, a.cassette_prefix, a.replay_abort,
         a.hands_extra, a.demand_cassette, a.oracle_plan, a.replant, a.tiler_rules, a.fill_free_count, a.fill_look, a.tile_exact, a.carry_over, a.block_front, a.plant_extra_gate, a.keep_tier_days, a.early_fert, a.seed_first_by_day, a.early_animal_jit, a.early_fert_runner, a.land_reserve, a.det_clock, a.plant_scale_days, a.cassette_wheat_scale, a.shop_crop_boost, a.fill_new_land, a.window_swap, a.sm_occ, a.gap_fill, a.fert_force_plan, a.straw_batch, a.peak_hand, a.yarn_floor, a.cassette_straw_buyers, e68=a.e68)


if __name__ == "__main__":
    main()

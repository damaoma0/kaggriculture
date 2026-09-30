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


def make(new_id, base, executor, gate, config, note, add_files=(), switch=False, kbplan=False, guard=False,
         until=False, extra=False, cas=False, fill=False, cas6=False):
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
    a = ap.parse_args()
    make(a.new_id, a.base, a.executor, a.land_gate, a.config, a.note, a.add_file, a.opening_switch, a.kbplan,
         a.bank_guard, a.opening_until, a.plant_extra, a.cassette, a.fill_free, a.cassette_day6)


if __name__ == "__main__":
    main()

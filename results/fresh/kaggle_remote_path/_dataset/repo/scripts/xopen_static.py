"""xopen static checks (thread xopen, 2026-09-25): one process, NO games (the laptop is shared).

  1. parse + Kaggle loader entry (the last NEW callable of the file, = kaggle_environments.agent.get_last_callable's
     rule, replicated here without importing the framework) for every built agent
  2. E1: xopen_day=-1 == the frozen source copy of agents/mgt_lead.py on synthetic observations (same actions);
     replay mode returns the tape's action verbatim; the handoff hands a working state to T
  3. the dynamic cash-safe rule on the 12 G1 leaders' own recorded paths (design: day 11 in 11 games, 12 in 1)
  4. synthetic unit tests of the follower core: B1 (per-crop PLANT cut), B2 (roles by the k-th hire, spawn offsets),
     B3 (destructive-op guard), B4 (substitutes use surplus only; released units' shed budget), B5 (fill inference
     against the REAL engine market code, data/kaggriculture.py loaded with a stub framework module), failsafe order
     (tier 0 first, wheat buy-ahead cut first, land ranked by its assets), cumulative caps on over-asks
  5. E2: mode off == the verbatim deploy copy on synthetic observations; the follow mode starts (if plans exist)

usage: .venv/Scripts/python.exe scripts/xopen_static.py      -> results/fresh/xopen_20260925/static_checks.txt
"""
import copy
import gzip
import importlib.util
import json
import sys
import traceback
import types
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / "results/fresh/xopen_20260925"
LINES = []
FAILS = []


def say(s=""):
    LINES.append(s)
    print(s, flush=True)


def check(name, cond, detail=""):
    say(("PASS " if cond else "FAIL ") + name + ((": " + detail) if detail else ""))
    if not cond:
        FAILS.append(name)


def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def last_callable_exec(path):
    """= kaggle_environments.agent.get_last_callable: exec the source, the last callable value in insertion order."""
    raw = Path(path).read_text(encoding="utf-8")
    env = {}
    exec(compile(raw, str(path), "exec"), env)
    return [v for v in env.values() if callable(v)][-1], env


# ------------------------------------------------------------------------------------------------ synthetic observations
BASE_PRICES = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250, "EGG": 50, "MILK": 160,
               "WOOL": 200, "FERTILIZER": 100}


def new_farm(money=3000.0):
    return {"money": float(money), "tiles": [[(None if (x < 5 and y < 5) else "LOCKED") for x in range(10)] for y in range(10)],
            "farmer": [4, 4], "hands": [], "unlocked_quadrants": ["NW"], "hires_today": 0}


def new_private():
    return {"shed": {k: 0 for k in list(BASE_PRICES) + ["GOOSE", "COW", "SHEEP"]},
            "seeds": {c: 0 for c in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")}, "inventories": [{}]}


def obs_of(step, farms, private, player=0, shops=None, prices=None):
    return {"step": step, "player": player, "farms": farms, "private": private,
            "market": {"prices": dict(prices or BASE_PRICES), "inventory": {}}, "town": {"unlocked_shops": list(shops or [])},
            "day": step // 24, "hour": step % 24}


def board_from_sem(sem, d):
    """a plausible day-d farm from a semantics board: plants with their last planting day, animals with placement."""
    last = {}
    for t in range(d):
        day = sem["days"][t]
        for c, v in day["planted"].items():
            for i in v:
                last[i] = (t, c)
        for i in day["animals"]["placed"]:
            last[i] = (t, None)
    lab = sem["days"][d]["board"]
    crop = {"WH": "WHEAT", "CA": "CARROT", "TO": "TOMATO", "ST": "STRAWBERRY", "ME": "MELON"}
    tiles = []
    for y in range(10):
        row = []
        for x in range(10):
            i = y * 10 + x
            L = lab[i]
            if L == " L":
                row.append("LOCKED")
            elif L == " .":
                row.append(None)
            elif L in crop:
                pd = last.get(i, (d - 1, None))[0]
                row.append({"kind": "PLANT", "crop": crop[L], "planted_day": pd, "watered_today": False,
                            "consecutive_unwatered": 0, "yield_units": 0, "max_lifespan_step": -1, "fertilized_until_day": -1})
            elif L in ("go", "co", "sh"):
                sp = {"go": "GOOSE", "co": "COW", "sh": "SHEEP"}[L]
                row.append({"kind": "COOP" if sp == "GOOSE" else "PASTURE", "animal": sp, "placed_day": last.get(i, (d - 2, None))[0],
                            "yield_units": 0, "consecutive_unfed": 0, "fed_today": False, "cared_today": False,
                            "fertilizer_available": False, "pending_care_bonus": 0})
            elif L == "pa":
                row.append({"kind": "PASTURE"})
            else:
                row.append(None)
        tiles.append(row)
    return tiles


# ------------------------------------------------------------------------------------------------ engine (stub framework)
def load_engine():
    ke = types.ModuleType("kaggle_environments")
    ke.__path__ = []
    ku = types.ModuleType("kaggle_environments.utils")
    ku.resolve_episode_seed = lambda env: 0
    sys.modules.setdefault("kaggle_environments", ke)
    sys.modules["kaggle_environments.utils"] = ku
    p = ROOT / ".venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py"
    if not p.exists():
        p = ROOT / "data/kaggriculture.py"
    ns = {"__file__": str(p), "__name__": "kaggriculture_engine"}
    exec(compile(p.read_text(encoding="utf-8"), str(p), "exec"), ns)
    return types.SimpleNamespace(**ns)


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


# ================================================================================================= 1. parse / entry
def part1():
    say("== 1. parse and Kaggle loader entry")
    man = json.loads((OUTD / "build_manifest.json").read_text(encoding="utf-8"))
    for name, want in (("mgt_lead_xopen", "mgt_lead_xopen_agent"), ("mgt_lpv_xopen", "mgt_lpv_xopen_agent"),
                       ("mgt_lpv_xopen_off", "mgt_lpv_xopen_agent"), ("mgt_lpv_xopen_d11", "mgt_lpv_xopen_agent"),
                       ("mgt_lpv_xopen_naive", "mgt_lpv_xopen_agent"), ("mgt_lpv_xopen_d9", "mgt_lpv_xopen_agent"),
                       ("mgt_lpv_xo0", "mgt_lead_deploy_agent")):
        p = ROOT / "agents" / f"{name}.py"
        try:
            f, env = last_callable_exec(p)
            check(f"{name}: loader entry", f.__name__ == want, f.__name__)
        except Exception as exc:
            check(f"{name}: loader entry", False, f"{type(exc).__name__}: {exc}")
    src = (ROOT / "agents/mgt_lead.py").read_bytes()
    e1 = (ROOT / "agents/mgt_lead_xopen.py").read_bytes()
    frozen = (OUTD / "src" / f"mgt_lead_{man['mgt_lead_xopen']['source_sha256'][:12]}.py").read_bytes()
    check("E1 file contains the frozen mgt_lead.py verbatim", frozen in e1)
    import hashlib
    say("   (info) live agents/mgt_lead.py sha %s, built from %s; live agents/mgt_lead_deploy.py sha %s, built from %s"
        % (hashlib.sha256(src).hexdigest()[:16], man["mgt_lead_xopen"]["source_sha256"][:16],
           hashlib.sha256((ROOT / "agents/mgt_lead_deploy.py").read_bytes()).hexdigest()[:16], man["mgt_lpv_xo0"]["source_sha256"][:16]))
    fd = (OUTD / "src" / f"mgt_lead_deploy_{man['mgt_lpv_xo0']['source_sha256'][:12]}.py").read_bytes()
    xo0 = (ROOT / "agents/mgt_lpv_xo0.py").read_bytes()
    check("mgt_lpv_xo0 = the frozen deploy copy it was built from", xo0 == fd)
    for name in ("mgt_lpv_xopen", "mgt_lpv_xopen_off"):
        check(f"{name} contains the deploy copy verbatim", xo0 in (ROOT / "agents" / f"{name}.py").read_bytes())


# ================================================================================================= 2. E1
def part2():
    say("\n== 2. E1: off == the copied mgt_lead.py; replay verbatim; handoff")
    man = json.loads((OUTD / "build_manifest.json").read_text(encoding="utf-8"))
    frozen = OUTD / "src" / f"mgt_lead_{man['mgt_lead_xopen']['source_sha256'][:12]}.py"
    sem = json.load(gzip.open(ROOT / "data/leader_semantics/16732748/112655730.json.gz", "rt", encoding="utf-8"))
    tape = json.load(gzip.open(ROOT / "data/leader_tapes/16732748_56498734/112655730.json.gz", "rt", encoding="utf-8"))
    base = {"p1_min_value": 30, "release_stale_d": True, "fert_hold": 1}
    A = load_mod(ROOT / "agents/mgt_lead_xopen.py", "e1_a")
    B = load_mod(frozen, "e1_orig")
    A.configure(sem, xopen_day=-1, **base)
    B.configure(sem, **base)
    same = True
    seq = []
    # step 0, then a mid-game day-11 / day-14 state built from the leader's boards (same obs to both modules)
    f0 = [new_farm(), new_farm()]
    seq.append(obs_of(0, f0, new_private()))
    for d, money in ((11, 2405.0), (14, 15000.0)):
        fs = [new_farm(money), new_farm()]
        fs[0]["tiles"] = board_from_sem(sem, d)
        fs[0]["unlocked_quadrants"] = ["NW", "NE", "SW", "SE"][:1 + sum(1 for q in ("NE", "SW", "SE") if any(
            sem["days"][d]["board"][y * 10 + x] != " L" for y in range(10) for x in range(10)
            if (("N" if y < 5 else "S") + ("W" if x < 5 else "E")) == q))]
        pv = new_private()
        pv["shed"]["WHEAT"] = 30
        pv["shed"]["FERTILIZER"] = 5
        for h in range(3):
            fs[0]["hands"].append([4 + (h % 2), 4 + (h // 2)])
            pv["inventories"].append({})
        for hr in (0, 1, 7):
            seq.append(obs_of(d * 24 + hr, copy.deepcopy(fs), copy.deepcopy(pv)))
    for o in seq:
        a = A.agent(copy.deepcopy(o))
        b = B.agent(copy.deepcopy(o))
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            same = False
            say(f"   differs at step {o['step']}: {json.dumps(a)[:200]} | {json.dumps(b)[:200]}")
    check("E1 xopen_day=-1: same actions as the frozen mgt_lead.py (7 synthetic observations)", same)
    # replay: the tape's actions verbatim, then the handoff at day 11 hands the game to T
    C = load_mod(ROOT / "agents/mgt_lead_xopen.py", "e1_c")
    C.configure(sem, xopen_day=11, **base)
    ok = True
    for t in (0, 1, 2, 30, 263):
        o = obs_of(t, [new_farm(), new_farm()], new_private())
        a = C.agent(o)
        want = tape["actions"][t] if tape["actions"][t] else {"farmer": ["PASS"], "hands": [], "market": []}
        for k in ("farmer", "hands", "market"):
            if json.dumps(a.get(k), sort_keys=True) != json.dumps(want.get(k, [] if k != "farmer" else ["PASS"]), sort_keys=True):
                ok = False
                say(f"   step {t} key {k}: {a.get(k)} vs {want.get(k)}")
    check("E1 replay mode: tape actions verbatim (steps 0, 1, 2, 30, 263)", ok)
    fs = [new_farm(2405.0), new_farm()]
    fs[0]["tiles"] = board_from_sem(sem, 11)
    fs[0]["unlocked_quadrants"] = ["NW", "NE", "SW"]
    o = obs_of(264, fs, new_private())
    try:
        a = C.agent(o)
        rep = C.xo_e1_report()
        check("E1 handoff at day 11: T acts, state handed over", C._XO.get("handed") and C._XO.get("D") == 11 and isinstance(a, dict)
              and C._S is not None and C._S["sold"] == C._T.cum_sold[10],
              f"D={C._XO.get('D')} reason={C._XO.get('D_reason')} sold={dict(C._S['sold'])} hires={[x for x in a.get('market', []) if x[0] == 'HIRE'][:3]}")
        check("E1 report", isinstance(rep, dict) and rep.get("D") == 11)
    except Exception as exc:
        check("E1 handoff at day 11", False, traceback.format_exc()[-800:])


# ================================================================================================= 3. dynamic rule
def part3():
    say("\n== 3. dynamic cash-safe rule on the 12 G1 leaders' own recorded paths")
    sys.path.insert(0, str(ROOT / "scripts"))
    import lead_g1
    M = load_mod(ROOT / "agents/mgt_lead_xopen.py", "e1_dyn")
    res = Counter()
    for g in lead_g1.GAMES:
        team, ep = g.split(":")
        sem = json.load(gzip.open(ROOT / f"data/leader_semantics/{team}/{ep}.json.gz", "rt", encoding="utf-8"))
        di = M._xo1_dayinfo(sem)
        M.xo_init()
        M._XO["dayinfo"] = di
        M.XO_CFG["land_max"] = 3
        D = None
        for t in range(10, 13):
            M._XO["revenue"] = Counter({d: di[d]["V"] for d in range(t)})        # our revenue = the plan's (own world)
            P = {"money": di[t]["cash"]}
            ok, info = M._xo_dyn_rule(P, t * 24)
            if ok:
                D = t
                break
        res[D if D is not None else 13] += 1
    say("   handoff day distribution: " + str(dict(sorted(res.items()))))
    check("dynamic rule on the G1 leaders' own paths = design (11: 11, 12: 1)", res == Counter({11: 11, 12: 1}), str(dict(res)))


# ================================================================================================= 4. core unit tests
def mk_plan(M, steps, T0=0, days=None, team="t", ep=1):
    raw = dict(v=1, team=team, ep=ep, seat=0, seed=1, shops=[], rewards=[0, 0], final=0, T0=T0, Q0=0, steps=steps,
               days=days or [], compile={})
    return M.xo_prepare_plan(raw)


def part4():
    say("\n== 4. follower core: synthetic unit tests")
    M = load_mod(ROOT / "agents/mgt_lead_xopen.py", "core_t")
    E = load_engine()
    # ---------------- B1: 3 recorded PLANT WHEAT, 2 seeds -> 2 plantings go ahead (the engine would drop all 3)
    tiles = [[(None if (x < 5 and y < 5) else "LOCKED") for x in range(10)] for y in range(10)]
    P = dict(step=30, day=1, hour=6, me=0, money=100.0, tiles=tiles, pos=[(0, 0), (1, 0), (2, 0)],
             invs=[Counter(), Counter(), Counter()], shed=Counter(), seeds=Counter({"WHEAT": 2}), unlocked=["NW"],
             prices=dict(BASE_PRICES), shops=[], hires_today=2)
    u = lambda x, y, cmd, eff=1: [x, y, cmd, eff, y * 10 + x, [" .", None]]
    steps = [dict(u=[u(0, 0, ["PLANT", "WHEAT"]), u(1, 0, ["PLANT", "WHEAT"]), u(2, 0, ["PLANT", "WHEAT"])],
                  iv=[{}, {}, {}], sh={}, sd={"WHEAT": 3}, m=100.0, ht=2, q=0, mk=[], hs=0, ld=0, pr={})]
    pl = mk_plan(M, steps, T0=30)
    M.xo_init(plan=pl)
    M._XO["t"] = 30
    M._XO["units"] = {0: dict(role=0, mode="sync", i=30), 1: dict(role=1, mode="sync", i=30), 2: dict(role=2, mode="sync", i=30)}
    cmds, meta = M._xo_build_units(P, 30)
    post = M.xo_sim_units(P, cmds)
    n_pl = sum(1 for row in post["tiles"] for t in row if isinstance(t, dict) and t.get("kind") == "PLANT")
    blocked_engine = E._apply_unit_action is not None and 3 > 2
    check("B1 per-crop PLANT cut: 2 of 3 recorded plantings go ahead with 2 seeds", n_pl == 2 and not post["blocked"],
          f"cmds {cmds}, planted {n_pl}")
    # the engine's own atomic rule on the uncut commands: all three become PASS
    farm = new_farm()
    farm["farmer"] = [0, 0]
    farm["hands"] = [[1, 0], [2, 0]]
    priv = new_private()
    priv["seeds"]["WHEAT"] = 2
    priv["inventories"] = [{}, {}, {}]
    st = _Obj(observation=_Obj(farms=[farm, new_farm()], private=priv, step=30, market=E._new_market(), town={"unlocked_shops": []}),
              action={"farmer": ["PLANT", "WHEAT"], "hands": [["PLANT", "WHEAT"], ["PLANT", "WHEAT"]], "market": []})
    st2 = _Obj(observation=_Obj(private=new_private()), action={})
    env = _Obj(configuration=_Obj(episodeSteps=720), done=False, info={"seed": 1})
    st.observation.player = 0
    st2.observation.player = 1
    E.interpreter([st, st2], env)
    n_eng = sum(1 for row in farm["tiles"] for t in row if isinstance(t, dict) and t.get("kind") == "PLANT")
    check("B1 engine check: the uncut 3 PLANTs with 2 seeds plant nothing (why the cut is needed)", n_eng == 0, f"planted {n_eng}")
    # ---------------- B2: role = k-th hire of the day; a spawn-tile offset is walked (lag), not a remap
    steps = []
    for t in range(24, 30):
        us = [u(4, 4, ["PASS"], 0)]
        if t >= 25:
            us.append(u(5, 4, ["EAST"] if t == 25 else ["PASS"], 1 if t == 25 else 0))
        if t >= 26:
            us.append(u(4, 5, ["PASS"], 0))
        steps.append(dict(u=us, iv=[{}] * len(us), sh={}, sd={}, m=100.0, ht=len(us) - 1, q=0, mk=[], hs=0, ld=0, pr={}))
    pl = mk_plan(M, steps, T0=24)
    M.xo_init(plan=pl)
    M._XO["units"] = {0: dict(role=0, mode="sync", i=24)}
    P2 = dict(P, step=25, day=1, hour=1, pos=[(4, 4), (4, 5)], invs=[Counter(), Counter()], hires_today=1)
    M._XO["t"] = 25
    M._xo_assign_new_hands(P2, 25)
    u1 = M._XO["units"].get(1)
    check("B2 hand 1 spawned on another shed tile: keeps role 1, walks to the recorded tile (lagged)",
          u1 is not None and u1.get("role") == 1 and u1.get("mode") in ("walk", "rv"), str(u1))
    P3 = dict(P, step=26, day=1, hour=2, pos=[(4, 4), (5, 4)], invs=[Counter(), Counter()], hires_today=1)
    M.xo_init(plan=pl)
    M._XO["units"] = {0: dict(role=0, mode="sync", i=24)}
    M._XO["t"] = 26
    M._xo_assign_new_hands(P3, 26)
    u1 = M._XO["units"].get(1)
    check("B2 hand 1 hired a step late: role 1 lagged or rendezvous", u1 is not None and u1.get("role") == 1, str(u1))
    # ---------------- B3: recorded DIG / HARVEST (one-time crop) only on our tile with the same (crop, planted day)
    tiles = [[(None if (x < 5 and y < 5) else "LOCKED") for x in range(10)] for y in range(10)]
    tiles[0][0] = {"kind": "PLANT", "crop": "WHEAT", "planted_day": 3, "watered_today": False, "consecutive_unwatered": 0,
                   "yield_units": 3, "max_lifespan_step": 200, "fertilized_until_day": -1}
    steps = [dict(u=[[0, 0, ["HARVEST"], 1, 0, ["WH", 2]]], iv=[{}], sh={}, sd={}, m=0.0, ht=0, q=0, mk=[], hs=0, ld=0, pr={}),
             dict(u=[[0, 0, ["DIG"], 1, 0, ["WH", 2]]], iv=[{}], sh={}, sd={}, m=0.0, ht=0, q=0, mk=[], hs=0, ld=0, pr={})]
    pl = mk_plan(M, steps, T0=168)
    P4 = dict(P, step=168, day=7, hour=0, tiles=tiles, pos=[(0, 0)], invs=[Counter()], seeds=Counter(), hires_today=0)
    M.xo_init(plan=pl)
    M._XO["t"] = 168
    M._XO["units"] = {0: dict(role=0, mode="sync", i=168)}
    cmds, meta = M._xo_build_units(P4, 168)
    check("B3 recorded HARVEST of a one-time crop planted on another day: substituted", cmds[0] != ["HARVEST"], str(cmds))
    P5 = dict(P4, step=169, hour=1)
    M._XO["t"] = 169
    M._XO["units"] = {0: dict(role=0, mode="sync", i=169)}
    cmds, meta = M._xo_build_units(P5, 169)
    check("B3 recorded DIG of our live plant (other planting day): substituted", cmds[0] != ["DIG"], str(cmds))
    tiles[0][0]["planted_day"] = 2
    M._XO["t"] = 168
    M._XO["units"] = {0: dict(role=0, mode="sync", i=168)}
    M._XO["owned"] = set()
    cmds, meta = M._xo_build_units(dict(P4, tiles=tiles), 168)
    check("B3 same (crop, planted day): the recorded HARVEST runs verbatim", cmds[0] == ["HARVEST"], str(cmds))
    # ---------------- B4: substitute FEED only with wheat beyond what the role carried at that recorded step
    tiles = [[(None if (x < 5 and y < 5) else "LOCKED") for x in range(10)] for y in range(10)]
    tiles[1][1] = {"kind": "COOP", "animal": "GOOSE", "placed_day": 1, "yield_units": 0, "consecutive_unfed": 0,
                   "fed_today": False, "cared_today": True, "fertilizer_available": False, "pending_care_bonus": 0}
    st = dict(tiles=tiles, shed=Counter(), seeds=Counter(), pos=[(1, 1)], invs=[Counter({"WHEAT": 1})])
    steps = [dict(u=[[1, 1, ["PLANT", "WHEAT"], 1, 11, [" .", None]]], iv=[{"WHEAT": 1}], sh={}, sd={}, m=0.0, ht=0, q=0,
                  mk=[], hs=0, ld=0, pr={})]
    pl = mk_plan(M, steps, T0=200)
    M.xo_init(plan=pl)
    sub, adv = M._xo_substitute(st, 0, (1, 1), 8, pl, 0, 200, ["PLANT", "WHEAT"])
    check("B4 substitute does not feed with the wheat the role needs later (carried = recorded)", sub != ["FEED"], str(sub))
    st["invs"] = [Counter({"WHEAT": 2})]
    sub, adv = M._xo_substitute(st, 0, (1, 1), 8, pl, 0, 200, ["PLANT", "WHEAT"])
    check("B4 substitute feeds with surplus wheat (carried 2, role carried 1)", sub == ["FEED"], str(sub))
    # released units' shed budget = shed minus in-sync roles' remaining recorded pickups today
    steps = [dict(u=[[4, 4, ["PASS"], 0, 44, None], [5, 4, ["PICKUP", "WHEAT", 3], 1, 45, None]], iv=[{}, {}], sh={"WHEAT": 4},
                  sd={}, m=0.0, ht=1, q=0, mk=[], hs=0, ld=0, pr={})]
    pl = mk_plan(M, steps, T0=210)
    M.xo_init(plan=pl)
    b = M._xo_shed_budget(pl, dict(P, shed=Counter({"WHEAT": 4})), 210, 8, {1: dict(role=1, mode="sync", i=210), 2: dict(role=None, mode="rel")})
    check("B4 released units may take 1 of 4 shed wheat (an in-sync role picks 3 later today)", b.get("WHEAT") == 1, str(dict(b)))
    # ---------------- B5: fill inference vs the real engine market (SELL + BUY wheat in one step, seeds, animals, hires, land)
    ok_all = True
    cases = [
        ("sell+buy wheat, seeds, hire", 500.0, {"WHEAT": 6, "FERTILIZER": 2},
         [["SELL", "WHEAT", 4], ["HIRE"], ["BUY_SEED", "STRAWBERRY", 2], ["BUY_PRODUCT", "WHEAT", 5], ["SELL", "FERTILIZER", 2]]),
        ("cash-limited buys", 130.0, {"EGG": 1},
         [["BUY_SEED", "MELON", 1], ["HIRE"], ["HIRE"], ["BUY_ANIMAL", "GOOSE", 1], ["SELL", "EGG", 1], ["BUY_PRODUCT", "WHEAT", 3]]),
        ("land + animals + sells", 5200.0, {"MILK": 3, "WOOL": 2},
         [["SELL", "MILK", 3], ["BUY_LAND"], ["BUY_ANIMAL", "COW", 2], ["SELL", "WOOL", 2], ["BUY_PRODUCT", "FERTILIZER", 2]]),
        ("wheat sold below the stock, bought after", 60.0, {"WHEAT": 2},
         [["BUY_PRODUCT", "WHEAT", 4], ["SELL", "WHEAT", 5], ["BUY_SEED", "WHEAT", 2]]),
    ]
    for name, money, shed, orders in cases:
        farm = new_farm(money)
        priv = new_private()
        for k, v in shed.items():
            priv["shed"][k] = v
        opp_farm, opp_priv = new_farm(3000.0), new_private()
        opp_priv["shed"]["WHEAT"] = 10
        market = E._new_market()
        o0 = obs_of(40, [copy.deepcopy(farm), opp_farm], copy.deepcopy(priv))
        P0 = M._xo_parse(o0)
        post = M.xo_sim_units(P0, [["PASS"]])
        prev = dict(step=40, day=1, money=P0["money"], unl=len(P0["unlocked"]), orders=orders, post=post,
                    prices=dict(market["prices"]), hires_before=0)
        st = _Obj(observation=_Obj(farms=[farm, opp_farm], market=market, private=priv), action={"market": orders})
        st2 = _Obj(observation=_Obj(private=opp_priv), action={"market": [["SELL", "WHEAT", 3], ["BUY_PRODUCT", "WHEAT", 2]]})
        env = _Obj(configuration=_Obj(episodeSteps=720))
        seeds0, shed0, money0 = dict(priv["seeds"]), dict(priv["shed"]), farm["money"]
        E._process_market([st, st2], env)
        o1 = obs_of(41, [farm, opp_farm], priv)
        P1 = M._xo_parse(o1)
        f = M.xo_infer(prev, P1)
        true_seeds = Counter({"SEED:" + c: priv["seeds"][c] - seeds0.get(c, 0) for c in priv["seeds"] if priv["seeds"][c] - seeds0.get(c, 0) > 0})
        true_anim = Counter({"ANIMAL:" + a: priv["shed"][a] - shed0.get(a, 0) for a in ("GOOSE", "COW", "SHEEP") if priv["shed"][a] - shed0.get(a, 0) > 0})
        inf_seeds = Counter({k: v for k, v in f["buy"].items() if k.startswith("SEED:")})
        inf_anim = Counter({k: v for k, v in f["buy"].items() if k.startswith("ANIMAL:")})
        ok = (inf_seeds == true_seeds and inf_anim == true_anim and f["hires"] == farm["hires_today"]
              and f["land"] == len(farm["unlocked_quadrants"]) - 1)
        # products: net shed change must match bought - sold per item
        for it in ("WHEAT", "FERTILIZER", "MILK", "WOOL", "EGG"):
            net = priv["shed"].get(it, 0) - shed0.get(it, 0)
            if f["buy"].get("PRODUCT:" + it, 0) - f["sell"].get(it, 0) != net:
                ok = False
        resid = abs(f["rev"] - sum(0 for _ in ()))
        ok_all &= ok
        say(f"   B5 {name}: inferred buy {dict(f['buy'])} sell {dict(f['sell'])} hires {f['hires']} land {f['land']} "
            f"amb {f['amb']} | true seeds {dict(true_seeds)} animals {dict(true_anim)} hires {farm['hires_today']} "
            f"money {money0:.0f}->{farm['money']:.0f} -> {'OK' if ok else 'MISMATCH'}")
    check("B5 fill inference = the engine's fills (4 synthetic market steps)", ok_all)
    # ---------------- A.5 cumulative caps: the recording's failed over-asks buy nothing extra
    steps = [dict(u=[[4, 4, ["PASS"], 0, 44, None]], iv=[{}], sh={}, sd={}, m=100.0, ht=0, q=0,
                  mk=[[["BUY_SEED", "STRAWBERRY", 6], 2, -200.0], [["HIRE"], 1, -1.0], [["HIRE"], 0, 0.0]], hs=1, ld=0, pr={})]
    pl = mk_plan(M, steps, T0=48)
    M.xo_init(plan=pl)
    M._XO["t"] = 48
    P6 = dict(P, step=48, day=2, hour=0, pos=[(4, 4)], invs=[Counter()], money=90.0, seeds=Counter(), hires_today=0,
              tiles=[[(None if (x < 5 and y < 5) else "LOCKED") for x in range(10)] for y in range(10)])
    post = M.xo_sim_units(P6, [["PASS"]])
    mk = M._xo_market(P6, 48, post)
    buys = [o for o in mk if o[0] == "BUY_SEED"]
    hires = [o for o in mk if o[0] == "HIRE"]
    check("A.5 caps: 6 asked / 2 filled strawberry seeds -> we ask 2; 2 HIRE asked / 1 filled -> 1",
          buys == [["BUY_SEED", "STRAWBERRY", 2]] and len(hires) == 1, str(mk))
    # ---------------- failsafe ordering: tier 0 first, wheat buy-ahead cut first, land ranked by its assets' delay cost
    days = [dict(d=d, cash=0, V=500.0, R=100.0, board=[" ."] * 100, key=[[" .", None]] * 100, hidden=[None] * 100,
                 shed={}, seeds={}, q=0, land_q=[]) for d in range(30)]
    st_rows = []
    for t in range(144, 168):
        us = [[4, 4, ["PASS"], 0, 44, None], [5, 4, ["PASS"], 0, 45, None]]
        if t == 150:
            us[1] = [5, 4, ["PLANT", "STRAWBERRY"], 1, 45, [" .", None]]
        if t == 152:
            us[0] = [4, 4, ["FEED"], 1, 44, ["go", 3]]
        st_rows.append(dict(u=us, iv=[{}, {}], sh={}, sd={}, m=0.0, ht=1, q=0, mk=[], hs=0, ld=0, pr={}))
    pl = mk_plan(M, st_rows, T0=144, days=days)
    M.xo_init(plan=pl)
    M._XO["t"] = 146
    tiles = [[(None if (x < 5 and y < 5) else "LOCKED") for x in range(10)] for y in range(10)]
    tiles[4][4] = {"kind": "COOP", "animal": "GOOSE", "placed_day": 3, "yield_units": 0, "consecutive_unfed": 0,
                   "fed_today": False, "cared_today": False, "fertilizer_available": False, "pending_care_bonus": 0}
    P7 = dict(P, step=146, day=6, hour=2, tiles=tiles, pos=[(4, 4)], invs=[Counter()], money=150.0, seeds=Counter(),
              shed=Counter(), hires_today=0)
    post = M.xo_sim_units(P7, [["PASS"]])
    lst = [["BUY_PRODUCT", "WHEAT", 6], ["BUY_SEED", "STRAWBERRY", 1], ["HIRE"]]
    out = M._xo_failsafe(P7, 146, post, lst)
    cut_items = [c["item"] for c in M._XO["cuts"]]
    check("failsafe: tier-0 hire (committed role) and 1 feed wheat first; strawberry seed before wheat buy-ahead",
          out[:2] == [["HIRE"], ["BUY_PRODUCT", "WHEAT", 1]] and out.index(["BUY_SEED", "STRAWBERRY", 1]) < len(out)
          and ("PRODUCT:WHEAT" in cut_items), f"list {out}; cuts {[(c['item'], c['qty'], c['ratio']) for c in M._XO['cuts']]}")
    r_land, loss_land, _ = M._xo_item_ratio(["BUY_LAND"], dict(P7, unlocked=["NW"]), 146, 1)
    r_wheat, _, _ = M._xo_item_ratio(["BUY_PRODUCT", "WHEAT", 6], P7, 146, 1)
    say(f"   ratios: land {r_land:.4f} (loss {loss_land:.1f}), wheat buy-ahead {r_wheat:.4f}")
    check("failsafe: wheat buy-ahead has a small positive delay cost per coin (cut early)", 0 < r_wheat < 0.1, f"{r_wheat:.4f}")


# ================================================================================================= 5. E2
def part5():
    say("\n== 5. E2: mode off == the verbatim deploy copy; follow mode starts")
    try:
        fa, envA = last_callable_exec(ROOT / "agents/mgt_lpv_xopen_off.py")
        fb, envB = last_callable_exec(ROOT / "agents/mgt_lpv_xo0.py")
    except Exception as exc:
        check("E2 load", False, f"{type(exc).__name__}: {exc}")
        return
    same = True
    for t in (0, 1, 2):
        o = obs_of(t, [new_farm(), new_farm()], new_private())
        a, b = fa(copy.deepcopy(o)), fb(copy.deepcopy(o))
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            same = False
            say(f"   step {t}: {json.dumps(a)[:200]} | {json.dumps(b)[:200]}")
    check("E2 mode off: same actions as the verbatim deploy (steps 0-2)", same)
    plans = OUTD / "plans" / "16732748_112655730.json.gz"
    if not plans.exists():
        say("   (compiled plans not available yet: follow-mode start not checked here)")
        return
    try:
        f, env = last_callable_exec(ROOT / "agents/mgt_lpv_xopen.py")
        tape = json.load(gzip.open(ROOT / "data/leader_tapes/16732748_56498734/112655730.json.gz", "rt", encoding="utf-8"))
        o = obs_of(0, [new_farm(), new_farm()], new_private())
        a = f(o)
        want = tape["actions"][0]
        check("E2 follow mode, step 0 (state = the recording's): the recorded action verbatim",
              json.dumps(a, sort_keys=True) == json.dumps({"farmer": want.get("farmer", ["PASS"]), "hands": want.get("hands", []),
                                                           "market": want.get("market", [])}, sort_keys=True),
              json.dumps(a)[:300])
    except Exception as exc:
        check("E2 follow mode start", False, traceback.format_exc()[-1200:])


def main():
    for part in (part1, part2, part3, part4, part5):
        try:
            part()
        except Exception as exc:
            check(part.__name__ + " crashed", False, traceback.format_exc()[-1500:])
    say("\n%d failures: %s" % (len(FAILS), FAILS))
    (OUTD / "static_checks.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

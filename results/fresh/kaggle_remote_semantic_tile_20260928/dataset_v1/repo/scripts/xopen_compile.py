"""xopen E0: compile recorded leader games into step plans for the exact follower (scripts/xopen_follow.py).

Runs the official engine on the recording's own world (recorded seed, forced shop schedule, BOTH seats' recorded
actions = the lead_ledger harness pattern) with hooks on our seat, and writes per step: every unit's pre-command
position, its recorded command, whether it took effect and the tile signature before it, the units' inventories,
shed / seeds / money / hires_today / quadrants at step start, prices, the recorded market list with each order's
effective units and coins, effective hires and land; per day: cash, V, R (by kind, correctly dated), the day-start
state key (label + planted / placed day), hidden per-tile state, shed, seeds, quadrant purchases.

Checks per game (compile_report.json): replayed final cash = recorded reward; per-day V / R = the offset-corrected
corpus (scripts/xopen_cash_safe.sem_flows, days >= 2); the static spawn rule (least-occupied shed tile, NWSE ties)
= the engine's spawn at every hire; the follower's unit-phase simulator = the engine's state after the unit phase
at every step; the follower's fill inference (xo_infer) = the hooked fills at every step (B5).

NO LOCAL RUNS on the shared laptop: run on Kaggle (scripts/kaggle_remote/remote_panel.py pushcmd, see
results/fresh/xopen_20260925/jobs_e0.json).

usage: xopen_compile.py [--games exemplar,pool,g1 | team_ep,...] [--workers 4] [--day-hi 13] [--limit N]
       xopen_compile.py index          (rebuild plans/pool_index.json from the compiled plans)
Output: results/fresh/xopen_20260925/plans/<team>_<ep>.json.gz, pool_index.json, compile_report.json
"""
import gzip
import json
import sys
import time
import traceback
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import xopen_follow as XF  # noqa: E402

SEM = ROOT / "data/leader_semantics"
TAPES = ROOT / "data/leader_tapes"
PLANS = ROOT / "results/fresh/xopen_20260925/plans"
EXEMPLAR = "16732748_112655730"
G1 = ["16732748_112655730", "16732748_112661570", "16732748_112667461", "16732748_112673479",
      "16770421_112708229", "16770421_112714050", "16770421_112715010", "16770421_112721923",
      "16730612_112444381", "16730612_112445586", "16730612_112447950", "16730612_112449129"]
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597]


def tape_path(team, ep):
    hits = sorted(TAPES.glob(f"{team}_*/{ep}.json.gz"))
    return hits[0] if hits else None


def sem_state(sem, d):
    """= scripts/xopen_open_stats._state: per tile (label, last planting / placement day before day d)."""
    last = {}
    for t in range(d):
        day = sem["days"][t]
        for c, v in day["planted"].items():
            for i in v:
                last[i] = t
        for i in day["animals"]["placed"]:
            last[i] = t
    b = sem["days"][d]["board"]
    key = []
    for i in range(100):
        lab = b[i]
        if lab in (" .", " L") or lab in ("pa", "co") and i not in last:
            key.append((lab, None))
        else:
            key.append((lab, last.get(i)))
    return key


def pool_games():
    """corpus games whose day-6 state equals the exemplar's (the day-6 re-retrieval pool), exemplar included."""
    ex = json.load(gzip.open(SEM / "16732748" / "112655730.json.gz", "rt", encoding="utf-8"))
    k6 = sem_state(ex, 6)
    out = []
    for f in sorted(SEM.glob("*/*.json.gz")):
        g = json.load(gzip.open(f, "rt", encoding="utf-8"))
        if sem_state(g, 6) == k6:
            out.append(f"{f.parent.name}_{g['meta']['episode']}")
    return out


def compile_game(key, day_lo=0, day_hi=13):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    team, ep = key.split("_")
    tp = tape_path(team, ep)
    tape = json.load(gzip.open(tp, "rt", encoding="utf-8"))
    seat, seed = tape["seat"], tape["seed"]
    shops_by_day = [list(tape["shops"][:min(8, d // 3)]) for d in range(31)]
    mine, opp = tape["actions"], tape["opp_actions"]
    T0, T1 = day_lo * 24, min(720, (day_hi + 1) * 24)

    obs_at = {}          # step -> parsed observation (our seat) + raw pieces
    units_at = {}        # step -> list of unit records from the apply hook
    events_at = {}       # step -> market events of our farm in processing order
    postunit_at = {}     # step -> our farm state right after the unit phase
    spawn_bad = []
    farms_box, step_box = [], [0]
    old = dict(apply=E._apply_unit_action, commit=E._commit_unit, hire=E._do_hire, land=E._do_buy_land,
               end=E._end_of_day, market=E._process_market)

    def is_me(farm):
        return bool(farms_box) and farm is farms_box[0][seat]

    def apply_hook(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        if not is_me(farm):
            return old["apply"](farm, private, idx, action, board_size, day, tpd, shed_capacity)
        p0 = E._farmer_position(farm, idx)
        p0 = tuple(p0) if p0 is not None else None
        tile0 = farm["tiles"][p0[1]][p0[0]] if p0 is not None else None
        sig = XF._xo_tsig(tile0) if p0 is not None else None
        snap0 = (p0, deepcopy(tile0), deepcopy(private["inventories"][idx]) if idx < len(private["inventories"]) else {},
                 dict(private["shed"]), dict(private["seeds"]))
        r = old["apply"](farm, private, idx, action, board_size, day, tpd, shed_capacity)
        p1 = E._farmer_position(farm, idx)
        p1 = tuple(p1) if p1 is not None else None
        tile1 = farm["tiles"][p0[1]][p0[0]] if p0 is not None else None
        snap1 = (p1, tile1, private["inventories"][idx] if idx < len(private["inventories"]) else {},
                 private["shed"], private["seeds"])
        eff = int(not (snap0[0] == snap1[0] and snap0[1] == snap1[1] and snap0[2] == snap1[2]
                       and snap0[3] == snap1[3] and snap0[4] == snap1[4]))
        units_at.setdefault(step_box[0], []).append((idx, p0, action, eff, sig))
        return r

    def commit_hook(op, item, price, farm, private, market, shed_capacity=100):
        r = old["commit"](op, item, price, farm, private, market, shed_capacity)
        if is_me(farm):
            events_at.setdefault(step_box[0], []).append((op, item, float(price), bool(r)))
        return r

    def hire_hook(farm, private, board_size, mult=1):
        if not is_me(farm):
            return old["hire"](farm, private, board_size, mult)
        before = len(farm["hands"])
        pos = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        m0 = farm["money"]
        old["hire"](farm, private, board_size, mult)
        ok = len(farm["hands"]) > before
        if ok:
            occ = {t: 0 for t in XF._XO_SHED}
            for p in pos:
                if p in occ:
                    occ[p] += 1
            rule = sorted(occ.items(), key=lambda kv: (kv[1], XF._XO_SHED.index(kv[0])))[0][0]
            if tuple(farm["hands"][-1]) != tuple(rule):
                spawn_bad.append((step_box[0], list(rule), list(farm["hands"][-1])))
        events_at.setdefault(step_box[0], []).append(("HIRE", None, float(m0 - farm["money"]), ok))

    def land_hook(farm, board_size):
        if not is_me(farm):
            return old["land"](farm, board_size)
        n0, m0 = len(farm["unlocked_quadrants"]), farm["money"]
        old["land"](farm, board_size)
        events_at.setdefault(step_box[0], []).append(("BUY_LAND", len(farm["unlocked_quadrants"]) - 2,
                                                      float(m0 - farm["money"]), len(farm["unlocked_quadrants"]) > n0))

    def market_hook(state, env):
        f = state[0].observation.farms[seat]
        pv = state[seat].observation.private
        postunit_at[step_box[0]] = dict(
            tiles=deepcopy(f["tiles"]), pos=[tuple(f["farmer"])] + [tuple(h) for h in f["hands"]],
            shed=XF._xo_cnt(pv["shed"]), seeds=XF._xo_cnt(pv["seeds"]), invs=[XF._xo_cnt(i) for i in pv["inventories"]])
        return old["market"](state, env)

    def end_hook(state, environment, day):
        old["end"](state, environment, day)
        state[0].observation.town.unlocked_shops[:] = shops_by_day[min(30, day + 1)]

    box = {}

    def real(state, environment):
        farms = getattr(state[0].observation, "farms", None)
        if farms:
            farms_box[:] = [farms]
        step_box[0] = int(getattr(state[0].observation, "step", 0) or 0)
        return box["orig"](state, environment)

    def me_agent(obs):
        t = int(obs["step"])
        P = XF._xo_parse(obs)
        rec = dict(P=P, t=t)
        if t % 24 == 0:
            rec["key"] = XF._xo_statekey(P["tiles"])
            rec["hidden"] = [XF._xo_hidden(x) for row in P["tiles"] for x in row]
            rec["board"] = [XF._xo_label(x) for row in P["tiles"] for x in row]
        obs_at[t] = rec
        a = mine[t] if t < len(mine) and isinstance(mine[t], dict) else {}
        return deepcopy(a) if a else {"farmer": ["PASS"], "hands": [], "market": []}

    def opp_agent(obs):
        t = int(obs["step"])
        a = opp[t] if t < len(opp) else {}
        return deepcopy(a) if a else {"farmer": ["PASS"], "hands": [], "market": []}

    E._apply_unit_action, E._commit_unit, E._do_hire = apply_hook, commit_hook, hire_hook
    E._do_buy_land, E._end_of_day, E._process_market = land_hook, end_hook, market_hook
    try:
        env = make("kaggriculture", configuration={"episodeSteps": 720}, info={"seed": seed})
        box["orig"] = env.interpreter
        env.interpreter = real
        agents = [None, None]
        agents[seat] = me_agent
        agents[1 - seat] = opp_agent
        env.run(agents)
        final = [float(s.reward) for s in env.state]
    finally:
        E._apply_unit_action, E._commit_unit, E._do_hire = old["apply"], old["commit"], old["hire"]
        E._do_buy_land, E._end_of_day, E._process_market = old["land"], old["end"], old["market"]

    # ---- attribute market events to our recorded (post-cap) orders
    def attribute(t):
        a = mine[t] if t < len(mine) and isinstance(mine[t], dict) else {}
        orders = list(a.get("market", []) or [])[:10]
        ev = list(events_at.get(t, []))
        out, hs, ld, lq = [], 0, 0, []
        for o in orders:
            op = o[0] if isinstance(o, list) and o else None
            if op in ("HIRE", "BUY_LAND"):
                e = ev.pop(0) if ev and ev[0][0] == op else None
                ok = bool(e and e[3])
                out.append([o, int(ok), -e[2] if (e and ok) else 0.0])
                hs += op == "HIRE" and ok
                if op == "BUY_LAND" and ok:
                    ld += 1
                    lq.append(e[1])
                continue
            valid = isinstance(o, list) and len(o) >= 3
            try:
                q = int(o[2]) if valid else 0
            except (TypeError, ValueError):
                q = 0
            item = o[1] if valid else None
            valid = valid and q > 0 and (
                (op == "SELL" and item in XF._XO_PRODUCTS) or (op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"))
                or (op == "BUY_SEED" and item in XF._XO_CROPS) or (op == "BUY_ANIMAL" and item in XF._XO_ANIMALS))
            if not valid:
                out.append([o, 0, 0.0])
                continue
            fill, coins = 0, 0.0
            while ev and ev[0][0] == op and ev[0][1] == item and fill < q:
                e = ev.pop(0)
                if not e[3]:
                    break
                fill += 1
                coins += e[2] if op == "SELL" else -e[2]
            out.append([o, fill, round(coins, 4)])
        return out, hs, ld, lq, ev

    steps, days = [], []
    attr_left = 0
    sim_bad, inf_bad = [], []
    V, R, Rk, landq = Counter(), Counter(), {}, {}
    for t in range(0, 719):
        mk, hs, ld, lq, left = attribute(t)
        attr_left += len(left)
        d = t // 24
        for o, fill, coins in mk:
            op = o[0] if isinstance(o, list) and o else None
            if op == "SELL":
                V[d] += coins
            elif op in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "HIRE", "BUY_LAND"):
                R[d] += -coins
                kk = "wages" if op == "HIRE" else "land" if op == "BUY_LAND" else \
                    ("seeds" if op == "BUY_SEED" else "animals" if op == "BUY_ANIMAL" else str(o[1]).lower())
                Rk.setdefault(d, Counter())[kk] += -coins
        if lq:
            landq.setdefault(d, []).extend(lq)
        rec = obs_at.get(t)
        if rec is None:
            continue
        P = rec["P"]
        a = mine[t] if t < len(mine) and isinstance(mine[t], dict) else {}
        cmds_tape = [a.get("farmer") or ["PASS"]] + list(a.get("hands") or [])
        n_units = len(P["pos"])
        cmds = [(cmds_tape[i] if i < len(cmds_tape) else ["PASS"]) for i in range(n_units)]
        hooked = {u[0]: u for u in units_at.get(t, [])}
        ulist = []
        for i in range(n_units):
            h = hooked.get(i)
            x, y = P["pos"][i]
            eff = int(h[3]) if h else 0
            sig = h[4] if h else XF._xo_tsig(P["tiles"][y][x])
            cmd = cmds[i] if isinstance(cmds[i], list) and cmds[i] else ["PASS"]
            ulist.append([x, y, cmd, eff, y * 10 + x, sig])
        # check: the follower's unit-phase simulator = the engine's state after the unit phase
        sim = XF.xo_sim_units(P, cmds)
        pu = postunit_at.get(t)
        if pu is not None:
            bad = []
            if [tuple(p) for p in sim["pos"]] != pu["pos"]:
                bad.append("pos")
            if sim["shed"] != pu["shed"]:
                bad.append("shed")
            if sim["seeds"] != pu["seeds"]:
                bad.append("seeds")
            if [XF._xo_cnt(i) for i in sim["invs"][:len(pu["invs"])]] != pu["invs"]:
                bad.append("invs")
            if sim["tiles"] != pu["tiles"]:
                bad.append("tiles")
            if bad and len(sim_bad) < 20:
                sim_bad.append((t, bad))
        # check: fill inference of step t-1 from the observation delta = the hooked fills of step t-1
        prv = obs_at.get(t - 1)
        if prv is not None and t - 1 >= 0:
            a1 = mine[t - 1] if isinstance(mine[t - 1], dict) else {}
            c1 = [a1.get("farmer") or ["PASS"]] + list(a1.get("hands") or [])
            P1 = prv["P"]
            c1 = [(c1[i] if i < len(c1) else ["PASS"]) for i in range(len(P1["pos"]))]
            orders1 = list(a1.get("market", []) or [])[:10]
            prev = dict(step=t - 1, day=(t - 1) // 24, money=P1["money"], unl=len(P1["unlocked"]), orders=orders1,
                        post=XF.xo_sim_units(P1, c1), prices=P1["prices"], hires_before=P1["hires_today"])
            f = XF.xo_infer(prev, P)
            mk1, hs1, ld1, _, _ = attribute(t - 1)
            want_b, want_s = Counter(), Counter()
            for o, fill, coins in mk1:
                k = XF._xo_okey(o)
                if k and fill:
                    want_b[k] += fill
                elif isinstance(o, list) and o and o[0] == "SELL" and fill:
                    want_s[o[1]] += fill
            same_day = (t // 24) == ((t - 1) // 24)
            ok = (+f["buy"] == +want_b and +f["sell"] == +want_s and f["land"] == ld1 and (f["hires"] == hs1 or not same_day))
            if not ok and len(inf_bad) < 30:
                inf_bad.append(dict(step=t - 1, infer_buy=dict(f["buy"]), hook_buy=dict(want_b),
                                    infer_sell=dict(f["sell"]), hook_sell=dict(want_s), hires=(f["hires"], hs1),
                                    land=(f["land"], ld1), amb=f["amb"]))
        if T0 <= t < T1:
            steps.append(dict(u=ulist, iv=[dict(i) for i in P["invs"]], sh=dict(P["shed"]), sd=dict(P["seeds"]),
                              m=P["money"], ht=P["hires_today"], q=len(P["unlocked"]) - 1, mk=mk, hs=hs, ld=ld,
                              pr={k: v for k, v in P["prices"].items()}))
        if t % 24 == 0:
            days.append(dict(d=d, cash=P["money"], board=rec["board"], key=rec["key"], hidden=rec["hidden"],
                             shed=dict(P["shed"]), seeds=dict(P["seeds"]), q=len(P["unlocked"]) - 1))
    for di in days:
        d = di["d"]
        di["V"] = round(V[d], 2)
        di["R"] = round(R[d], 2)
        di["R_kind"] = {k: round(v, 2) for k, v in Rk.get(d, {}).items()}
        di["land_q"] = landq.get(d, [])
    # corpus flows (offset-corrected) vs the hooked ones, days >= 2
    vr_err = None
    sp = SEM / team / f"{ep}.json.gz"
    if sp.exists():
        import xopen_cash_safe as xcs
        fl = xcs.sem_flows(json.load(gzip.open(sp, "rt", encoding="utf-8")))
        vr_err = max(max(abs(fl["V"][d] - V[d]), abs(fl["R"][d] - R[d])) for d in range(2, 29))
    rep = dict(key=key, seat=seat, final=final[seat], recorded=tape["rewards"][seat],
               cash_match=round(final[seat]) == round(tape["rewards"][seat]), opp_match=round(final[1 - seat]) == round(tape["rewards"][1 - seat]),
               vr_err_days2_28=vr_err, spawn_bad=len(spawn_bad), spawn_bad_first=spawn_bad[:3],
               sim_bad=len(sim_bad), sim_bad_first=sim_bad[:5], infer_bad=len(inf_bad), infer_bad_first=inf_bad[:5],
               unattributed_events=attr_left, T0=T0, T1=T1)
    plan = dict(v=1, team=team, ep=int(ep), seat=seat, seed=seed, shops=tape["shops"], rewards=tape["rewards"],
                final=final[seat], T0=T0, Q0=int(obs_at[T0]["P"]["unlocked"].__len__() - 1) if T0 in obs_at else 0,
                steps=steps, days=days, compile=rep)
    return plan, rep


def job(args):
    key, lo, hi = args
    try:
        t0 = time.time()
        plan, rep = compile_game(key, lo, hi)
        PLANS.mkdir(parents=True, exist_ok=True)
        with gzip.open(PLANS / f"{key}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(plan, fh, separators=(",", ":"))
        rep["wall"] = round(time.time() - t0, 1)
        return rep
    except Exception as exc:
        return dict(key=key, error=f"{type(exc).__name__}: {exc}", tb=traceback.format_exc()[-2500:])


def build_index():
    """pool_index.json: every compiled plan that starts by day 6 -> day-6 / day-9 state keys, shed, seeds, cash."""
    out = []
    for f in sorted(PLANS.glob("*.json.gz")):
        p = json.load(gzip.open(f, "rt", encoding="utf-8"))
        dd = {x["d"]: x for x in p["days"]}
        if p["T0"] > 6 * 24 or 6 not in dd:
            continue
        row = dict(team=p["team"], ep=p["ep"], shops=p["shops"], T0=p["T0"])
        for d in (6, 9):
            if d in dd and d * 24 >= p["T0"]:
                row["key%d" % d] = dd[d]["key"]
                row["shed%d" % d] = dd[d]["shed"]
                row["seeds%d" % d] = dd[d]["seeds"]
                row["cash%d" % d] = dd[d]["cash"]
        out.append(row)
    (PLANS / "pool_index.json").write_text(json.dumps(out), encoding="utf-8")
    print("pool_index:", len(out), "plans")
    return out


def main():
    argv = sys.argv[1:]
    if argv and argv[0] == "index":
        build_index()
        return
    sel, workers, day_hi, limit = "exemplar,g1,pool", 4, 13, None
    i = 0
    while i < len(argv):
        if argv[i] == "--games":
            sel = argv[i + 1]; i += 2
        elif argv[i] == "--workers":
            workers = int(argv[i + 1]); i += 2
        elif argv[i] == "--day-hi":
            day_hi = int(argv[i + 1]); i += 2
        elif argv[i] == "--limit":
            limit = int(argv[i + 1]); i += 2
        else:
            i += 1
    jobs = {}
    for s in sel.split(","):
        if s == "exemplar":
            jobs[EXEMPLAR] = (0, day_hi)
        elif s == "g1":
            for k in G1:
                jobs[k] = (0, 29)                    # full games: the leader-world controls (F29, capped replay)
        elif s == "pool":
            for k in pool_games():
                jobs.setdefault(k, (6, day_hi))
        elif "_" in s:
            jobs.setdefault(s, (0, day_hi))
    if EXEMPLAR in jobs:
        jobs[EXEMPLAR] = (0, max(day_hi, jobs[EXEMPLAR][1]))
    todo = [(k, lo, hi) for k, (lo, hi) in sorted(jobs.items())]
    if limit:
        todo = todo[:limit]
    print(len(todo), "games to compile", flush=True)
    t0 = time.time()
    reps = []
    if workers <= 1:
        for j in todo:
            r = job(j)
            reps.append(r)
            print(json.dumps({k: r.get(k) for k in ("key", "cash_match", "vr_err_days2_28", "spawn_bad", "sim_bad", "infer_bad", "error", "wall")}), flush=True)
    else:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for r in pool.map(job, todo):
                reps.append(r)
                print(json.dumps({k: r.get(k) for k in ("key", "cash_match", "vr_err_days2_28", "spawn_bad", "sim_bad", "infer_bad", "error", "wall")}), flush=True)
    PLANS.mkdir(parents=True, exist_ok=True)
    old = {}
    rp = PLANS / "compile_report.json"
    if rp.exists():
        old = {r["key"]: r for r in json.loads(rp.read_text(encoding="utf-8"))}
    for r in reps:
        old[r["key"]] = r
    rp.write_text(json.dumps(list(old.values()), indent=1, default=str), encoding="utf-8")
    ok = [r for r in reps if "error" not in r]
    print(f"compiled {len(ok)}/{len(reps)} in {time.time() - t0:.0f}s; cash_match {sum(r['cash_match'] for r in ok)}; "
          f"spawn rule exact {sum(r['spawn_bad'] == 0 for r in ok)}; simulator exact {sum(r['sim_bad'] == 0 for r in ok)}; "
          f"fill inference exact {sum(r['infer_bad'] == 0 for r in ok)}; max V/R error days 2-28 "
          f"{max([r['vr_err_days2_28'] or 0 for r in ok] or [0]):.2f}")
    build_index()


if __name__ == "__main__":
    main()

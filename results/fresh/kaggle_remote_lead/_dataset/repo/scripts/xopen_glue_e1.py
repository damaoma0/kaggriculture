# ===== XOPEN E1 GLUE (scripts/xopen_glue_e1.py; pasted by scripts/xopen_build.py after the verbatim mgt_lead.py and
# the follower core) ==================================================================================================
"""Leader-world exact opening (thread xopen E1): the leader's own recorded tape actions are replayed exactly (the
recording's own world: same seed, forced shops, recorded opponent), then T (the executor above = agents/mgt_lead.py
verbatim) plays from hour 0 of the handoff day D. Options come through configure(sem, **cfg) like every T option:
  xopen_day    -1 = off: every call goes to T unchanged (identical to the copied mgt_lead.py); D >= 1 = T plays from
               day D (days 0..D-1 replayed); >= 30 = replay the whole game (control: the leader's recorded cash).
  xopen_rule   "fixed" (D = xopen_day) | "dynamic": the cash-safe rule of the design (0.4) on our live money: at hour 0
               of days xopen_floor..xopen_cap-1 hand off on the first day our money keeps the plan funded on every
               morning through day 14 with the plan's revenue cut by max(0.30, our measured shortfall) and a 25%
               margin; at xopen_cap hand off regardless. The plan's flows come from the recording's semantics
               (scripts/xopen_cash_safe.sem_flows logic, offset-corrected); our revenue from the fill inference (B5).
  xopen_mode   "replay" = the tape verbatim | "follow" = the follower core on the compiled full-game plan (identical to
               the replay while our state equals the recording's, i.e. always in the recording's own world).
Handoff (design D.2): T's state is created fresh at hour 0 of day D with sold = the recording's cumulative sold units
through day D-1; configure(sem) already made the leader's game T's target and the board equals the leader's, so
T's plant / structure maps are the identity. T hires the target's hands for day D at hour 0.
"""
import glob as _xo1_glob

XO_E1 = {"day": -1, "rule": "fixed", "mode": "replay", "floor": 10, "cap": 13}
_XO_E1S = {"sem": None, "tape": None, "tape_path": None, "team_id": None, "last_step": -1}
_XO_INNER_AGENT = agent
_XO_INNER_CONFIGURE = configure


def _xo1_root():
    return _xo_root_default()


def _xo1_find_tape(sem):
    """the recording of this seat: data/leader_tapes/<team>_<sub>/<ep>.json.gz with the same seat and seed (a met pair
    of leaders shares an episode id, one file per seat)."""
    meta = sem.get("meta", {})
    ep, seat, seed = int(meta.get("episode")), meta.get("seat"), meta.get("seed")
    hits = sorted(_xo1_glob.glob(_xo_os.path.join(_xo1_root(), "data", "leader_tapes", "*", "%d.json.gz" % ep)))
    hits += sorted(_xo1_glob.glob(_xo_os.path.join(_xo1_root(), "data", "leader_tapes", "*", "%d.json" % ep)))
    for p in hits:
        op = _xo_gzip.open if p.endswith(".gz") else open
        with op(p, "rt", encoding="utf-8") as fh:
            tp = _xo_json.load(fh)
        if tp.get("seat") == seat and (seed is None or tp.get("seed") == seed):
            team_id = _xo_os.path.basename(_xo_os.path.dirname(p)).split("_")[0]
            return tp, p, team_id
    return None, None, None


def _xo1_fibsum(n):
    a, b, s = 1, 1, 0
    for _ in range(int(n)):
        s += a
        a, b = b, a + b
    return s


def _xo1_dayinfo(sem):
    """{day: {V, R, land_q, cash}} from the recording's semantics, = scripts/xopen_cash_safe.sem_flows: market index i
    holds day i+1 and index 0 holds days 0 AND 1 (booked on day 1); wages = fib-sum of hands_present; land from the
    locked-tile counts; structures are free."""
    days = sem["days"]
    n = len(days)
    locked = [(x["board"].count(" L") if isinstance(x["board"], str) else sum(1 for v in x["board"] if v == " L"))
              for x in days]
    land, land_q, bought_q = [0.0] * n, [[] for _ in range(n)], 0
    for t in range(n - 1):
        for _ in range(max(0, (locked[t] - locked[t + 1]) // 25)):
            land[t] += _XO_LAND_PRICES[min(bought_q, 2)]
            land_q[t].append(min(bought_q, 2))
            bought_q += 1
    wages = [float(_xo1_fibsum(int(x["labour"]["hands_present"]))) for x in days]

    def mk(i):
        m = days[i]["market"]
        return float(sum(m["sold_revenue"].values())), float(sum(m["bought_spend"].values()))
    V, R = [0.0] * n, [0.0] * n
    for t in range(2, n):
        v, r = mk(t - 1)
        V[t], R[t] = v, r + wages[t] + land[t]
    v, r = mk(0)
    V[1], R[1] = v, r + wages[0] + wages[1] + land[0] + land[1]
    out = {}
    for d in range(n):
        out[d] = dict(V=V[d], R=R[d], land_q=(land_q[0] + land_q[1]) if d == 1 else ([] if d == 0 else land_q[d]),
                      cash=float(days[d]["cash_start"]))
    return out


def _xo1_setup():
    """per-game follower state (called at step 0)."""
    sem, tape = _XO_E1S["sem"], _XO_E1S["tape"]
    XO_CFG["land_max"] = 3                         # the leader world replays all its land
    XO_CFG["reretrieve6"] = XO_CFG["reretrieve9"] = False
    XO_CFG["D_fixed"] = XO_E1["day"] if XO_E1["rule"] == "fixed" else 99
    XO_CFG["dyn"] = XO_E1["rule"] == "dynamic"
    XO_CFG["D_floor"], XO_CFG["D_cap"] = XO_E1["floor"], XO_E1["cap"]
    plan = None
    if XO_E1["mode"] == "follow":
        XO_CFG["mode"] = "follow"
        plan = xo_load_plan("%s_%s" % (_XO_E1S["team_id"], int(sem["meta"]["episode"])))
    else:
        XO_CFG["mode"] = "replay"
    xo_init(plan=plan, tape=tape)
    _XO["dayinfo"] = _xo1_dayinfo(sem) if sem is not None else {}
    _XO["e1"] = dict(XO_E1, tape=_XO_E1S["tape_path"])


def configure(sem, **cfg):
    """T's configure (target = this leader game, T's options) plus the xopen_* options above."""
    for k in list(cfg):
        if k.startswith("xopen_"):
            XO_E1[k[len("xopen_"):]] = cfg.pop(k)
    XO_E1["day"] = int(XO_E1["day"])
    _XO_INNER_CONFIGURE(sem, **cfg)
    _XO_E1S["sem"] = sem
    _XO_E1S["last_step"] = -1
    if XO_E1["day"] >= 0:
        tp, path, team_id = _xo1_find_tape(sem)
        _XO_E1S.update(tape=tp, tape_path=path, team_id=team_id)
    _XO.clear()


def _xo1_handoff(step, reason):
    """T takes the game at this step (hour 0 of day D)."""
    global _S
    day = step // 24
    _XO["handed"], _XO["D"], _XO["D_reason"] = True, day, reason
    S = _new_state()
    S["last_step"] = step - 1                      # agent() keeps a state whose last_step is below the current step
    S["sold"] = Counter({k: int(v) for k, v in _T.cum_sold[max(0, min(day - 1, _T.n - 1))].items()})
    _S = S
    _XO["handoff_sold_plan"] = dict(S["sold"])
    _XO["handoff_sold_inferred"] = dict(_XO.get("sold") or {})
    _xo_log("handoff", cause=reason, day=day)


def _xo1_decide(P, step):
    """hour 0: hand off now? (fixed / dynamic rule; the dynamic rule is also evaluated in shadow for fixed runs)."""
    day = step // 24
    if XO_E1["floor"] <= day < XO_E1["cap"] and _XO.get("D_shadow") is None:
        ok, info = _xo_dyn_rule(P, step)
        _XO.setdefault("dyn_trace", {})[day] = info
        if ok:
            _XO["D_shadow"] = day
    if XO_E1["rule"] == "dynamic":
        if _XO.get("D_shadow") == day:
            return "dyn"
        if day >= XO_E1["cap"]:
            return "cap"
        return None
    return "fixed" if day >= XO_E1["day"] else None


def agent(obs, config=None):
    """T with an exactly replayed opening (xopen_day >= 0), else T unchanged."""
    if XO_E1["day"] < 0:
        return _XO_INNER_AGENT(obs, config)
    step = int(_xo_g(obs, "step", 0))
    try:
        if step == 0 or not _XO or step < _XO_E1S["last_step"]:
            _xo1_setup()
        _XO_E1S["last_step"] = step
        if not _XO.get("handed"):
            if XO_E1["mode"] == "follow":
                act, reason = xo_follow_step(obs)
                if act is not None:
                    return act
                _xo1_handoff(step, reason)
            else:
                P = _xo_parse(obs)
                prev = _XO.get("prev")
                if prev is not None and prev["step"] == step - 1:        # fills of the previous step, before the rule
                    _xo_apply_fills(xo_infer(prev, P), P, prev["day"])
                    _XO["prev"] = None
                reason = _xo1_decide(P, step) if step % 24 == 0 else None
                if reason is None:
                    return xo_replay_step(obs)
                _xo1_handoff(step, reason)
    except Exception as exc:                        # never crash a game: log and let T play from here
        _XO.setdefault("errors", []).append("%s: %s" % (type(exc).__name__, exc))
        if not _XO.get("handed"):
            try:
                _xo1_handoff(step, "error")
            except Exception:
                pass
    xo_observe(obs)
    return _XO_INNER_AGENT(obs, config)


def xo_e1_report():
    """per-game report of the xopen layer (the runner stores it next to the ledger)."""
    if not _XO:
        return {}
    rep = xo_report()
    rep["e1"] = _XO.get("e1")
    rep["handoff_sold_plan"] = _XO.get("handoff_sold_plan")
    rep["handoff_sold_inferred"] = _XO.get("handoff_sold_inferred")
    rep["plants_by_day"] = {str(d): v for d, v in sorted((_XO.get("plants_by_day") or {}).items())}
    rep["errors"] = _XO.get("errors")
    return rep


# ===== the Kaggle loader's entry: the LAST new callable of the file ============================================
def mgt_lead_xopen_agent(obs, config=None):
    return agent(obs, config)

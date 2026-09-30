# ===== XOPEN E2 GLUE (scripts/xopen_glue_e2.py; pasted by scripts/xopen_build.py after the verbatim
# mgt_lead_deploy.py and the follower core) ============================================================================
"""New-world exact opening (thread xopen E2). Until the cash-safe date D the deploy's day-0 exemplar (DSM's seat of
112655730, compiled by scripts/xopen_compile.py) is followed exactly by the follower core above: unit commands verbatim
while feasible (repairs and substitutes otherwise, roles by the k-th successful hire of the day), the recorded market
lists capped by the recording's effective totals, the EV failsafe when cash is short (tier 0 = wages of committed
roles and feed wheat, never cut; the rest by expected value lost per coin freed, deferred before cancelled), a day-6
re-pick among the corpus games whose day-6 state equals ours by our two revealed shops (day 9 only to an exactly
state-identical game). Land: the recording's purchases up to the deploy's land_max (2 quadrants; the exemplar's
$4,000 SE purchase on day 10 is cancelled and logged). At hour 0 of D the deploy (entry mgt_lead_deploy_agent above,
unchanged) takes over: its Target = the followed recording (days >= compose_from: the count model as usual), a fresh
executor state with the structure map onto our farm, the reveal days not reached yet re-opened for its own
retrieval (B6). D: XO_CFG dyn True = the dynamic rule (floor D_floor, cap D_cap), else D_fixed; an abort (Hamming > 8
at a day start, > 12 executor-owned tiles, tier-0 shortfalls on two consecutive days) hands off early.
XO_CFG mode "off" = the deploy unchanged (every call goes to mgt_lead_deploy_agent). Research override:
XOPEN_CFG_JSON='{"key": value}'.
"""
XO_CFG.update({"mode": "follow", "dyn": True, "D_floor": 10, "D_cap": 13, "D_fixed": 11,
               "plan": "16732748_112655730", "reretrieve6": True, "reretrieve9": True, "failsafe": "ev"})
XO_CFG.update({})   # __XO_VARIANT__ (scripts/xopen_build.py writes an arm's overrides here)
XO_HOOKS["root"] = lambda: _DEP_ROOT
_XO_E2S = {"last_step": -1}
try:                                    # research overrides (arms): XOPEN_CFG_JSON='{"key": value}'
    XO_CFG.update(_dep_json.loads(_dep_os.environ.get("XOPEN_CFG_JSON") or "{}"))
except Exception:
    pass


def _xo2_init():
    """per-game state at step 0: the deploy's (exemplar target, logs) with its own retrieval suspended, and the follower
    on the day-0 recording."""
    _dep_init()
    _DEP["switched"] = set(DEP_CFG["switch_days"])     # the deploy's retrieval does not fire while we follow
    XO_CFG["land_max"] = int(DEP_CFG.get("land_max", 2))
    xo_init(plan=xo_load_plan(XO_CFG["plan"]))
    _XO["e2"] = {k: XO_CFG.get(k) for k in ("mode", "dyn", "D_floor", "D_cap", "D_fixed", "plan", "failsafe",
                                              "reretrieve6", "reretrieve9", "land_max", "cash_rate")}


def _xo2_handoff(obs, reason):
    """the deploy takes the game at this step (hour 0 of D, or now on an error)."""
    global _T, _S
    step = int(_xo_g(obs, "step", 0))
    day = step // 24
    _XO["handed"], _XO["D"], _XO["D_reason"] = True, day, reason
    pl = _XO.get("plan")
    me = int(_xo_g(obs, "player", 0))
    tiles = _xo_g(obs, "farms")[me]["tiles"]
    if pl is not None:
        try:
            t_f = Target(_dep_load_sem(int(pl["ep"]), str(pl["team"])))
            _T = _DepTarget(t_f)                     # days < compose_from follow the recording, then the count model
            _DEP["lead_t"] = t_f
            if int(pl["ep"]) != _DEP_EXEMPLAR:
                _DEP["picks"].append((day, int(pl["ep"])))
                _MGT_HISTORY.append((day, int(pl["ep"])))
        except Exception as exc:
            _XO.setdefault("errors", []).append("handoff_target %s: %s" % (type(exc).__name__, exc))
    for i in range(DEP_CFG["land_max"], 3):
        _T.land_day[LAND_ORDER[i]] = 99
    # B6: a reveal day not reached yet (an abort before day 9) is re-opened for the deploy's own retrieval
    _DEP["switched"] = {d for d in DEP_CFG["switch_days"] if d < day or (d == day and step % 24 != 0)}
    S = _new_state()
    S["last_step"] = step - 1
    try:
        S["smap"] = _dep_struct_map(_T, day, tiles)
    except Exception:
        pass
    _S = S
    _DEP["last_step"] = step
    _XO["pending_at_handoff"] = dict(
        queue=dict(_XO.get("queue") or {}), queue_coins=round(float(_XO.get("queue_coins", 0.0)), 1),
        jobs=[[j["op"], j["arg"], j["tile"], j["src"]] for j in (_XO.get("jobs") or {}).values()][:60],
        owned=sorted(_XO.get("owned") or ()))
    _xo_log("handoff", cause=reason, day=day)


def _xo2_report(step):
    try:
        xo_report()
        _XO_REPORT["plants_by_day"] = {str(d): v for d, v in sorted((_XO.get("plants_by_day") or {}).items())}
        _XO_REPORT["e2"] = _XO.get("e2")
        _XO_REPORT["errors"] = _XO.get("errors")
        _XO_REPORT["last_step"] = step
    except Exception as exc:
        _XO_REPORT["report_error"] = "%s: %s" % (type(exc).__name__, exc)


# ===== the entry point: the LAST new callable of the file (Kaggle's loader, scripts/ladder_panel.py) ===============
def mgt_lpv_xopen_agent(obs, config=None):
    if XO_CFG.get("mode") == "off":
        return mgt_lead_deploy_agent(obs, config)
    step = int(_xo_g(obs, "step", 0))
    hour = step % 24
    if step == 0 or not _XO or step < _XO_E2S["last_step"]:
        _xo2_init()
    _XO_E2S["last_step"] = step
    if not _XO.get("handed"):
        try:
            _DEP["last_step"] = step                # the deploy entry must not re-initialise when it takes over
            act, reason = xo_follow_step(obs)
            if act is not None:
                if hour == 23:
                    _xo2_report(step)
                return act
            _xo2_handoff(obs, reason)
        except Exception as exc:                    # never crash a game: log and let the deploy play from here
            _XO.setdefault("errors", []).append("%s: %s @%d" % (type(exc).__name__, exc, step))
            if not _XO.get("handed"):
                try:
                    _xo2_handoff(obs, "error")
                except Exception as exc2:
                    _XO["errors"].append("handoff %s: %s" % (type(exc2).__name__, exc2))
    xo_observe(obs)
    out = mgt_lead_deploy_agent(obs, config)
    if hour == 23 or step >= 718:
        _xo2_report(step)
    return out

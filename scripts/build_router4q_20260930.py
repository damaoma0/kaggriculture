"""4Q leader opening libraries for the tape router (2026-09-30, user: "imitate leader openings on each type of store
combination ... to give us a good start on 4 quadrants").

Same pipeline as the n18rc223d opening file agents/mgt_dsm_ch.py, only the tapes change:
  1. scripts/build_mg_tape_agent.py <name>_c --tape-dir data/leader_semantics_router4q --subs <dirs> --normalize-hires
     (mgt_dsm_c.py = the same call over data/dsm_tapes/56619023; re-running it today reproduces mgt_dsm_c.py byte for byte)
  2. the opening hire guard of scripts/make_dsm_router_hirekeep_20260929.py (mgt_dsm_c -> mgt_dsm_ch: hold on day 0,
     re-hire on day 1), applied to <name>_c.py -> <name>.py
  3. a research trace hook (absent on Kaggle, inert unless MGT_TRACE_DIR is set): at every day start the router's pick,
     its history and report are written to MGT_TRACE_DIR/trace_<pid>_p<player>.json (smoke games run one game per process)

Tapes: data/leader_semantics_router4q/<team_id>_<submission>/ (scripts/router4q_convert_20260930.py, exact replays, both
cash totals reproduced). The router keys tapes by the revealed shops (demand at the checkpoints 2 / 4 / 5 / 6 / 8 shops)
among tapes whose recorded board that day is within max_hamming 8 tiles of ours, exactly as in mgt_dsm_ch.

usage: build_router4q_20260930.py dsm|pool|all"""
import importlib.util
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPE_DIR = "data/leader_semantics_router4q"
LIBS = {
    "dsm": ("router4q_dsm", ["16732748_56692773"]),
    "pool": ("router4q_pool", ["16732748_56692773", "16681125_56679033", "16623559_56688636", "16621497_56686384"]),
    # opponent-style study (2026-09-30): M&M&P&Q and DECEM cross-fit (R2 0.90-0.93) -> one pool; Victor and DSM apart
    "md": ("router4q_md", ["16681125_56679033", "16623559_56688636"]),
    "victor": ("router4q_victor", ["16621497_56686384"]),
}

TRACE = '''

# research hook (absent on Kaggle; inert unless MGT_TRACE_DIR is set, 2026-09-30 router4q smokes): the router's pick at
# every day start, with its history / report, goes to MGT_TRACE_DIR/trace_<pid>_p<player>.json
if _mgt_os.environ.get('MGT_TRACE_DIR'):
    _mgt_trace_inner = _MGT_IMPL.chassis.router

    def _mgt_trace_router(observation, step, state):
        r = _mgt_trace_inner(observation, step, state)
        if step % 24 == 0:
            try:
                _p = _int(_get(observation, 'player', 0))
                _f = _mgt_os.path.join(_mgt_os.environ['MGT_TRACE_DIR'], 'trace_%d_p%d.json' % (_mgt_os.getpid(), _p))
                with open(_f, 'w') as _h:
                    _mgt_json.dump(dict(step=step, route=r, ep=_MGT_TAPES[r]['ep'], ntapes=len(_MGT_TAPES),
                                        exclude=_mgt_os.environ.get('MGT_EXCLUDE'), history=_MGT_HISTORY,
                                        report=_MGT_REPORT, shops=list((_get(observation, 'town', {}) or {}).get('unlocked_shops', []) or []),
                                        money=_get(observation['farms'][_p], 'money', None)), _h)
            except Exception:
                pass
        return r
    _MGT_IMPL.chassis.router = _mgt_trace_router
'''


LAND = '''

# 4Q opening land guard (2026-09-30, router4q; off in router4q_dsm / router4q_pool, on in the _lr / _lrh builds). The
# closed-loop leaders buy each quadrant when their cash allows and re-request BUY_LAND after a failure; a replayed tape asks
# only at its recorded steps, so a world whose sales come an hour later misses the quadrant (fidelity, own worlds, own tape
# left out: the 4th quadrant by day 10 in 30 / 44 DSM worlds with router4q_dsm, leader 44 / 44). On days from_day..until_day,
# while we own fewer quadrants than the followed tape's board shows at the next dawn, from the tape's first BUY_LAND of the
# day (from hour 0 when we are already behind its board at dawn):
#   retry  BUY_LAND is requested every step, right after this step's SELL / HIRE orders and before any purchase, once cash +
#          this step's sales cover the price (the tape's own BUY_LAND moves there too); a failed order costs nothing
#   hold   seed / animal purchases that would leave less than the land price are held (feed wheat is never held)
_MGT_LAND = __LAND_CFG__


def _mgt_land_guard(observation, action):
    try:
        step = _step_of(observation)
        day = step // 24
        if not isinstance(action, dict) or not (_MGT_LAND.get('from_day', 6) <= day <= _MGT_LAND.get('until_day', 10)):
            return action
        me = _int(_get(observation, 'player', 0))
        route = (_MGT_IMPL_INNER.chassis.players.get(me) or {}).get('route')
        if route is None or route not in _MGT_ROUTES:
            return action
        farm = (_get(observation, 'farms', []) or [])[me]
        have = len(list(_get(farm, 'unlocked_quadrants', []) or []))
        quads = lambda d: 4 - sum(1 for x in _MGT_TAPES[route]['lab'][min(29, d)] if x == ' L') // 25
        if have >= min(4, quads(day + 1)):
            return action
        tape = _MGT_ROUTES[route]
        if quads(day) > have:
            first = day * 24
        else:
            first = next((s for s in range(day * 24, min(len(tape), day * 24 + 24)) if isinstance(tape[s], dict)
                          and any(o and o[0] == 'BUY_LAND' for o in (tape[s].get('market') or []))), None)
        if first is None or step < first:
            return action
        price = LAND_PRICES[max(0, min(len(LAND_PRICES) - 1, have - 1))]
        prices = {k: _int(v) for k, v in dict(_get(_get(observation, 'market', {}) or {}, 'prices', {}) or {}).items()}
        market = [o for o in (action.get('market') or []) if o]
        cash = float(_get(farm, 'money', 0.0) or 0.0)
        cash += sum(max(0, _int(o[2]) if len(o) > 2 else 1) * prices.get(o[1], 0)
                    for o in market if o[0] == 'SELL' and len(o) > 1)
        k0 = _int(_get(farm, 'hires_today', 0))
        cash -= sum(_fib(k0 + k) for k in range(sum(1 for o in market if o[0] == 'HIRE')))
        has = any(o[0] == 'BUY_LAND' for o in market)
        if _MGT_LAND.get('retry') and not has and cash >= price:
            if len(market) >= 10:
                drop = next((i for i in range(len(market) - 1, -1, -1) if market[i][0] not in ('SELL', 'HIRE')), None)
                if drop is None:
                    return action
                del market[drop]
            market.append(['BUY_LAND'])
            has = True
            _MGT_REPORT['land_retry'] = _MGT_REPORT.get('land_retry', 0) + 1
        if has:                                    # the land right after the sales / hires, before any purchase
            market = ([o for o in market if o[0] in ('SELL', 'HIRE')] + [['BUY_LAND']]
                      + [o for o in market if o[0] not in ('SELL', 'HIRE', 'BUY_LAND')])
        if _MGT_LAND.get('hold'):
            left, floor, kept = cash - (price if has else 0), (0 if has else price), []
            for o in market:
                if o[0] in ('BUY_SEED', 'BUY_ANIMAL') and len(o) > 1:
                    cost = (SEED_PRICE if o[0] == 'BUY_SEED' else ANIMAL_COST).get(o[1], 0) * max(1, _int(o[2]) if len(o) > 2 else 1)
                    if left - cost < floor:
                        _MGT_REPORT['land_hold'] = _MGT_REPORT.get('land_hold', 0) + 1
                        continue
                    left -= cost
                elif o[0] == 'BUY_PRODUCT' and len(o) > 1:
                    left -= (prices.get(o[1], 0) + 1) * max(1, _int(o[2]) if len(o) > 2 else 1)
                kept.append(o)
            market = kept
        action['market'] = market[:10]
    except Exception:
        _MGT_REPORT['land_errors'] = _MGT_REPORT.get('land_errors', 0) + 1
    return action


_MGT_IMPL_INNER = _MGT_IMPL


def _mgt_impl_land(observation, configuration=None):
    return _mgt_land_guard(observation, _MGT_IMPL_INNER(observation, configuration))


_mgt_impl_land.chassis = _MGT_IMPL_INNER.chassis
_MGT_IMPL = _mgt_impl_land
'''


def hirekeep(src, dst):
    spec = importlib.util.spec_from_file_location("_hk", ROOT / "scripts/make_dsm_router_hirekeep_20260929.py")
    hk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hk)
    hk.SRC, hk.DST = src, dst
    hk.main()


def build(key, land=None):
    name, dirs = LIBS[key]
    src = ROOT / "agents" / f"{name}_c.py"
    if land is None or not src.exists():
        cmd = [sys.executable, str(ROOT / "scripts/build_mg_tape_agent.py"), name + "_c", "--tape-dir", TAPE_DIR,
               "--subs", ",".join(dirs), "--normalize-hires"]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
        print([l for l in r.stdout.splitlines() if l.startswith("built")] or r.stdout[-2000:], r.returncode)
        assert r.returncode == 0, r.stderr[-3000:]
    suffix = "" if land is None else "_l" + "".join(k[0] for k in ("retry", "hold") if land.get(k))
    dst = ROOT / "agents" / f"{name}{suffix}.py"
    assert land is None or not dst.exists(), f"{dst} exists: land-guard builds never overwrite"
    hirekeep(src, dst)
    s = dst.read_text(encoding="utf-8")
    anchor = "\n\n\ndef mgt_kaggle_entry("
    assert s.count(anchor) == 1
    if land is not None:
        s = s.replace(anchor, LAND.replace("__LAND_CFG__", repr(land)) + anchor, 1)
    s = s.replace(anchor, TRACE + anchor, 1)
    s = s.replace("# (submissions ", "# 4Q leader library router4q (build_router4q_20260930.py), tape folders " + ",".join(dirs)
                  + "\n# (submissions ", 1)
    dst.write_text(s, encoding="utf-8")
    compile(s, str(dst), "exec")
    from kaggle_environments.agent import get_last_callable
    entry = get_last_callable(s, path=str(dst))
    assert getattr(entry, "__name__", "") == "mgt_kaggle_entry", entry
    print("wrote", dst, "sha", sha256(dst.read_bytes()).hexdigest()[:12], f"{dst.stat().st_size / 1e6:.2f} MB")


def main():
    keys = list(LIBS) if sys.argv[1] == "all" else sys.argv[1].split(",")
    land = None
    if "--land" in sys.argv:                       # e.g. --land retry | retry+hold (reuses agents/<name>_c.py)
        land = dict(from_day=6, until_day=10, **{k: True for k in sys.argv[sys.argv.index("--land") + 1].split("+")})
    for k in keys:
        build(k, land)


if __name__ == "__main__":
    main()

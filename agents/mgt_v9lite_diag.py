"""DIAGNOSTIC COPY of the packaged mgt_v9lite (exposes telemetry to the ladder harness; play unchanged).

mgt_v9lite submission entry (main.py of a multi-file Kaggle agent archive; builder scripts/package_v9lite.py).

Base: mgt_y3 plays every step. At the reveals of days 12, 15 and 18 (steps 288, 360, 432) the V9-lite value selector
(scripts/value_tape_search_lite.py over the unchanged V9 runtime) may commit the router to a different tape until its
`until` step. Same packaging rules as scripts/package_v9y3_main.py (package root from sys.path, gzip fallback for
decompressed libraries, bank-aware budget, a failing search keeps the native router for the rest of the game,
V9Y3_REPORT_DIR research log), plus:
  * the lite parameters below (cheaper search, see the lite module);
  * a front-loaded bank split (day 12 gets most of it: lite's day-15/18 searches are cheap);
  * WARM-UP OFF THE CLOCK: the private search runtime (a second y3 clone, the rewritten rollout, the isolated engine)
    costs several seconds to build and its caches are cold on the first search. A daemon thread builds it, and runs one
    throw-away rollout at the day-10 morning, while the game is otherwise idle between our calls (our calls take a few
    ms, so the thread uses wall time we are not charged for). The first search joins the thread, so a slow warm-up is
    charged only for what is left of it, and never runs concurrently with a search.
  * gc.freeze() during a search: the cyclic collector skips the pre-search heap (the episode history is large).
"""
import gzip as _v9_gzip
import sys as _v9_sys
import threading as _v9_threading
from copy import deepcopy as _v9_deepcopy
from pathlib import Path as _V9Path

_BASE = 'mgt_y3'
_V9_REVEALS = (288, 360, 432)
_V9_RESERVE = 8.0          # seconds of overage bank never spent on search
# FRONT-LOADED budget: the day-12 search is the expensive one (18 days of rollouts, most candidates); lite's day-15/18
# searches are cheap (same-checkpoint laptop bench: median 1.5 s, max 6.8 s). Each reveal may spend the bank minus the
# reserve minus _V9_EST_LATER per later reveal, capped per reveal. Bank 55 at day 12 -> 30 s; then day 15 <= 20 s.
_V9_CAPS = {288: 30.0, 360: 20.0, 432: 20.0}
_V9_EST_LATER = 6.0        # seconds set aside for each later reveal
_V9_MIN = 2.0              # below this a search is not started
_V9_WARM_START = None      # step at which a warm-up thread would build the runtime (None: no thread; see below)
_V9_WARM_ROLLOUT = None    # step whose observation would feed a throw-away warm-up rollout (None: no rollout)
# The warm-up thread is OFF: under kaggle_environments' official runner, which swaps the process-wide stdout/stderr
# for per-call buffers, the package with the thread died within the first game on Kaggle twice (2026-09-24), the
# second time even with V9's own redirects neutralised in threads. Without it the runtime is built inside the first
# search, as in the V9 package that passed the official runner 8/8.
_V9L_PARAMS = dict(count=7, keep=2, lazy_keep=True, worlds=4, scout_min=350.0, final_min=350.0, skip_native_commit=True,
                   max_hamming=12)


def _v9_root():
    cands = [_V9Path(p) for p in reversed(_v9_sys.path) if p]
    cands += [_V9Path('/kaggle_simulations/agent'), _V9Path.cwd(), *_V9Path.cwd().parents]
    for d in cands:
        try:
            if (d / 'scripts' / 'value_tape_search_lite.py').exists() and (d / 'agents' / f'{_BASE}.py').exists():
                return d.resolve()
        except OSError:
            continue
    raise RuntimeError('mgt_v9lite: package files (scripts/, agents/) not found next to main.py')


_V9_ROOT = _v9_root()
_v9_gz_open = _v9_gzip.open


def _v9_gz_fallback(filename, mode='rb', *args, **kwargs):
    if isinstance(filename, (str, _V9Path)):
        p = _V9Path(filename)
        if p.suffix == '.gz' and not p.exists() and p.with_suffix('').exists():
            if 't' in mode:
                return open(p.with_suffix(''), 'r', encoding=kwargs.get('encoding') or 'utf-8')
            return open(p.with_suffix(''), 'rb')
    return _v9_gz_open(filename, mode, *args, **kwargs)


_v9_gzip.open = _v9_gz_fallback
if str(_V9_ROOT / 'scripts') not in _v9_sys.path:
    _v9_sys.path.insert(0, str(_V9_ROOT / 'scripts'))
import value_tape_search as _V9_V0                        # noqa: E402

# The official runner swaps the process-wide sys.stdout / sys.stderr for per-call buffers and closes them after each
# call. V9's engine setup (research_labour_profit.engine / Simulator) wraps itself in contextlib.redirect_*; run
# from a background thread, that saves a per-call buffer and restores it after the runner closed it, and the next
# write kills the process (Kaggle, 2026-09-24: "I/O operation on closed file", "lost sys.stderr"). Outside the main
# thread those redirects therefore do nothing; in the main thread they behave exactly as before.
import contextlib as _v9_contextlib                       # noqa: E402
import threading as _v9_threading_rd                      # noqa: E402
_v9_rlp = _v9_sys.modules['research_labour_profit']


def _v9_thread_safe(original):
    def redirect(target):
        if _v9_threading_rd.current_thread() is _v9_threading_rd.main_thread():
            return original(target)
        return _v9_contextlib.nullcontext(target)
    return redirect


_v9_rlp.redirect_stdout = _v9_thread_safe(_v9_rlp.redirect_stdout)
_v9_rlp.redirect_stderr = _v9_thread_safe(_v9_rlp.redirect_stderr)

_p = _V9_ROOT / 'agents' / f'{_BASE}.py'
_V9_V0.SOURCE_PATH = _p
_V9_V0.SOURCE = _p.read_text(encoding='utf-8')
_V9_V0.CODE = compile(_V9_V0.SOURCE, str(_p), 'exec')
import value_tape_search_v9 as _V9_N                      # noqa: E402
import value_tape_search_lite as _V9_L                    # noqa: E402
import rival_trajectory_model_v3 as _V9_RTM3              # noqa: E402
# without the opponent libraries the search corrupts the game silently: refuse to load instead
assert len(_V9_RTM3.training_library()) == 115, 'V9 opponent libraries incomplete'

_V9_STATE = {}
_V9_REPORT = {'decisions': [], 'switches': 0, 'seconds': [], 'budgets': [], 'errors': 0, 'warm': []}
_V9_SPENT = [0.0]          # own estimate of overage spent (calls over the 1 s act timeout)
_V9_WARM = {}


def _v9_log(step, budget, bank, decision=None):
    import os
    d = os.environ.get('V9Y3_REPORT_DIR')
    if d:
        import json
        row = dict(pid=os.getpid(), step=step, bank=round(bank, 2), budget=round(budget, 2),
                   seconds=_V9_REPORT['seconds'][-1] if _V9_REPORT['seconds'] else None,
                   decision=_V9_REPORT['decisions'][-1] if _V9_REPORT['decisions'] else None,
                   errors=_V9_REPORT['errors'], warm=_V9_REPORT['warm'])
        if decision is not None:
            row['lite'] = _V9_L.summarize(decision)
        with open(os.path.join(d, 'v9lite_decisions.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, default=str) + chr(10))


def _v9_warm_build():
    import time
    t0 = time.perf_counter()
    try:
        _V9_N.runtime()
        _V9_N.V.isolated_engine()
        _V9_REPORT['warm'].append(['runtime', round(time.perf_counter() - t0, 2)])
    except Exception as exc:                   # the first search will build it (and fail loudly if it must)
        _V9_REPORT['warm'].append(['runtime_error', repr(exc)[:120]])


def _v9_warm_rollout(obs, memory):
    import time
    t0 = time.perf_counter()
    runner = None
    try:
        runner = _V9_N.runtime()
        if runner.busy:
            return
        runner.busy = True
        runner.prepare(obs)
        world = _V9_N.M.world(obs, 0)
        runner.rollout(obs, memory, None, world)
        _V9_REPORT['warm'].append(['rollout', round(time.perf_counter() - t0, 2)])
    except Exception as exc:
        _V9_REPORT['warm'].append(['rollout_error', repr(exc)[:120]])
    finally:
        if runner is not None:
            runner.busy = False


def _v9_start(target, *args):
    th = _V9_WARM.get('thread')
    if th is not None and th.is_alive():
        return
    th = _v9_threading.Thread(target=target, args=args, daemon=True)
    _V9_WARM['thread'] = th
    th.start()


def _v9_init():
    ours = _V9_N.V.fresh_agent()
    chassis = ours.__globals__['_MGT_IMPL'].chassis
    _V9_STATE.update(ours=ours, chassis=chassis, native=chassis.router)
    # DIAGNOSTIC COPY ONLY: expose y3's router history and overlay counters to the ladder harness (read-only)
    for _k in ('_MGT_HISTORY', '_SHP_REPORT', '_MGT_REPORT'):
        globals()[_k] = ours.__globals__[_k]


def _v9lite_act(observation):
    if not _V9_STATE:
        _v9_init()
    step = int(observation['step'] if isinstance(observation, dict) else getattr(observation, 'step', 0))
    if not _V9_STATE.get('broken'):
        try:
            if _V9_WARM_START is not None and step >= _V9_WARM_START and not _V9_WARM.get('built'):
                _V9_WARM['built'] = True
                _v9_start(_v9_warm_build)
            if _V9_WARM_ROLLOUT is not None and step == _V9_WARM_ROLLOUT and not _V9_WARM.get('rolled'):
                _V9_WARM['rolled'] = True
                th = _V9_WARM.get('thread')
                if th is None or not th.is_alive():     # never queue behind a slow build: skip instead
                    _v9_start(_v9_warm_rollout, _v9_deepcopy(observation), _V9_N.V.memory_of(_V9_STATE['ours']))
        except Exception:
            pass
    if step in _V9_REVEALS and not _V9_STATE.get('broken'):
        import time
        t0 = time.perf_counter()
        th = _V9_WARM.get('thread')
        if th is not None:
            th.join()
        waited = time.perf_counter() - t0
        try:
            bank = float(observation.get('remainingOverageTime'))
        except (AttributeError, TypeError, ValueError):
            bank = 60.0 - _V9_SPENT[0]
        later = sum(1 for s in _V9_REVEALS if s > step)
        budget = min(_V9_CAPS[step], bank - _V9_RESERVE - waited - later * _V9_EST_LATER)
        _V9_REPORT['budgets'].append(round(budget, 2))
        chassis, native = _V9_STATE['chassis'], _V9_STATE['native']
        chassis.router = native
        decision = None
        if budget >= _V9_MIN:
            import gc
            t0 = time.perf_counter()
            gc.freeze()          # the collector then skips the (large) pre-search heap: speed only, no result change
            try:
                route, decision = _V9_L.choose(_v9_deepcopy(observation), _V9_N.V.memory_of(_V9_STATE['ours']),
                                               budget_seconds=budget, **_V9L_PARAMS)
            except Exception as exc:              # keep playing the native route
                _V9_STATE['broken'] = True
                _V9_REPORT['errors'] += 1
                _V9_REPORT['last_error'] = repr(exc)[:200]
                route, decision = None, None
            finally:
                gc.unfreeze()
            _V9_REPORT['seconds'].append(round(time.perf_counter() - t0 + waited, 2))
            _V9_REPORT['decisions'].append([step // 24, (decision or {}).get('selected'), route])
            _v9_log(step, budget, bank, decision)
            if route is not None:
                _V9_REPORT['switches'] += 1
                _V9_STATE['ours'].__globals__['_SHP_REPORT']['v9_route_d%d' % (step // 24)] = route + 1   # diagnostic
                until = decision['until']

                def committed(obs, s, memory, route=route, until=until):
                    if s < until:
                        memory['route'] = route
                        return route
                    return native(obs, s, memory)
                chassis.router = committed
    return _V9_STATE['ours'](observation)


# Kaggle calls the LAST callable defined in this file: keep the entry point last
def v9lite_agent(observation, configuration=None):
    import time
    t_call = time.perf_counter()
    try:
        return _v9lite_act(observation)
    finally:
        _V9_SPENT[0] += max(0.0, time.perf_counter() - t_call - 1.0)

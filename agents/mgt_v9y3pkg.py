"""mgt_v9y3 submission entry (main.py of a multi-file Kaggle agent archive).

Base: mgt_y3 (the tape router + late-Yarn layer) plays every step. At the reveals of days 12, 15 and 18 (steps 288,
360, 432) the other agent system's value selector V9 (scripts/value_tape_search_v9.py, unchanged) may commit the
router to a different tape until its `until` step. Differences from the research wrapper agents/mgt_v9y3.py:
  * the package root is found from sys.path (Kaggle's loader appends the agent's directory while executing main.py;
    there is no __file__), then /kaggle_simulations/agent, then the working directory;
  * each search gets a time budget from the live overage bank: (remainingOverageTime - reserve) / reveals left,
    capped; V9 admits only fully evaluated candidates, so a search that runs out of budget keeps the native route;
  * if the upload pipeline decompressed the opponent libraries (*.json.gz -> *.json), gzip.open reads the plain file;
  * a failing search is logged once and the native router is kept for the rest of the game;
  * harnesses that do not pass remainingOverageTime get the bank from the wrapper's own accounting (60 s minus every
    call's time over the 1 s act timeout); V9Y3_REPORT_DIR (absent on Kaggle) appends one line per search there.
"""
import gzip as _v9_gzip
import sys as _v9_sys
from copy import deepcopy as _v9_deepcopy
from pathlib import Path as _V9Path

_BASE = 'mgt_y3'
_V9_REVEALS = (288, 360, 432)
_V9_RESERVE = 8.0          # seconds of overage bank never spent on search
_V9_CAP = 20.0             # longest single search
_V9_MIN = 3.0              # below this a search is not started


def _v9_root():
    cands = [_V9Path(p) for p in reversed(_v9_sys.path) if p]
    cands += [_V9Path('/kaggle_simulations/agent'), _V9Path.cwd(), *_V9Path.cwd().parents]
    for d in cands:
        try:
            if (d / 'scripts' / 'value_tape_search_v9.py').exists() and (d / 'agents' / f'{_BASE}.py').exists():
                return d.resolve()
        except OSError:
            continue
    raise RuntimeError('mgt_v9y3: package files (scripts/, agents/) not found next to main.py')


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
import rival_trajectory_model_v3 as _V9_RTM3              # noqa: E402
# without the opponent libraries V9's search corrupts the game silently: refuse to load instead
assert len(_V9_RTM3.training_library()) == 115, 'V9 opponent libraries incomplete'

_V9_STATE = {}
_V9_REPORT = {'decisions': [], 'switches': 0, 'seconds': [], 'budgets': [], 'errors': 0}
_V9_SPENT = [0.0]          # own estimate of overage spent (calls over the 1 s act timeout)


def _v9_log(step, budget, bank):
    import os
    d = os.environ.get('V9Y3_REPORT_DIR')
    if d:
        import json
        with open(os.path.join(d, 'v9y3_decisions.jsonl'), 'a', encoding='utf-8') as f:
            f.write(json.dumps(dict(pid=os.getpid(), step=step, bank=round(bank, 2), budget=round(budget, 2),
                                    seconds=_V9_REPORT['seconds'][-1], decision=_V9_REPORT['decisions'][-1],
                                    errors=_V9_REPORT['errors'])) + chr(10))


def _v9_init():
    ours = _V9_N.V.fresh_agent()
    chassis = ours.__globals__['_MGT_IMPL'].chassis
    _V9_STATE.update(ours=ours, chassis=chassis, native=chassis.router)


def _v9y3_act(observation):
    if not _V9_STATE:
        _v9_init()
    step = int(observation['step'] if isinstance(observation, dict) else getattr(observation, 'step', 0))
    if step in _V9_REVEALS and not _V9_STATE.get('broken'):
        import time
        try:
            bank = float(observation.get('remainingOverageTime'))
        except (AttributeError, TypeError, ValueError):
            bank = 60.0 - _V9_SPENT[0]
        left = sum(1 for s in _V9_REVEALS if s >= step)
        budget = min(_V9_CAP, (bank - _V9_RESERVE) / left)
        _V9_REPORT['budgets'].append(round(budget, 2))
        chassis, native = _V9_STATE['chassis'], _V9_STATE['native']
        chassis.router = native
        if budget >= _V9_MIN:
            t0 = time.perf_counter()
            try:
                route, decision = _V9_N.choose(_v9_deepcopy(observation), _V9_N.V.memory_of(_V9_STATE['ours']),
                                               budget_seconds=budget)
            except Exception as exc:              # keep playing the native route
                _V9_STATE['broken'] = True
                _V9_REPORT['errors'] += 1
                _V9_REPORT['last_error'] = repr(exc)[:200]
                route, decision = None, None
            _V9_REPORT['seconds'].append(round(time.perf_counter() - t0, 2))
            _V9_REPORT['decisions'].append([step // 24, (decision or {}).get('selected'), route])
            _v9_log(step, budget, bank)
            if route is not None:
                _V9_REPORT['switches'] += 1
                until = decision['until']

                def committed(obs, s, memory, route=route, until=until):
                    if s < until:
                        memory['route'] = route
                        return route
                    return native(obs, s, memory)
                chassis.router = committed
    return _V9_STATE['ours'](observation)


# Kaggle calls the LAST callable defined in this file: keep the entry point last
def v9y3_agent(observation, configuration=None):
    import time
    t_call = time.perf_counter()
    try:
        return _v9y3_act(observation)
    finally:
        _V9_SPENT[0] += max(0.0, time.perf_counter() - t_call - 1.0)

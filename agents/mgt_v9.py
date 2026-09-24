"""Research wrapper (NOT a submission file): the other agent system's value selector V9
(scripts/value_tape_search_v9.py) as a playable agent for our harnesses (ladder_panel.py, the V56 runner).

Same protocol as its own harness (scripts/evaluate_refresh_fix_20260923.py::v9): a live base agent plays every step;
at the reveals of days 12, 15 and 18 (steps 288, 360, 432) choose(observation, memory) may commit the chassis to a
different tape route until the decision's `until` step. The base is mgt_m1 unless this file is copied with another
_BASE (e.g. agents/mgt_v9y3.py). The forecast clones are built from the same base source.
It imports from scripts/, so it runs where the repo (or the Kaggle bundle) is present.
"""
import sys as _v9_sys
from copy import deepcopy as _v9_deepcopy
from pathlib import Path as _V9Path

_BASE = 'mgt_m1'
# the Kaggle loader executes this file without __file__: find the repo (or unpacked bundle) from the working dir
_V9_ROOT = next((d for d in [_V9Path.cwd(), *_V9Path.cwd().parents] if (d / 'scripts/value_tape_search.py').exists()), _V9Path.cwd())
if str(_V9_ROOT / 'scripts') not in _v9_sys.path:
    _v9_sys.path.insert(0, str(_V9_ROOT / 'scripts'))
import value_tape_search as _V9_V0                        # noqa: E402

if _BASE != 'mgt_m1':
    _p = _V9_ROOT / 'agents' / f'{_BASE}.py'
    _V9_V0.SOURCE_PATH = _p
    _V9_V0.SOURCE = _p.read_text(encoding='utf-8')
    _V9_V0.CODE = compile(_V9_V0.SOURCE, str(_p), 'exec')
import value_tape_search_v9 as _V9_N                      # noqa: E402

_V9_STATE = {}
_V9_REPORT = {'decisions': [], 'switches': 0, 'seconds': []}


def _v9_init():
    ours = _V9_N.V.fresh_agent()
    chassis = ours.__globals__['_MGT_IMPL'].chassis
    _V9_STATE.update(ours=ours, chassis=chassis, native=chassis.router)


def v9_agent(observation, configuration=None):
    if not _V9_STATE:
        _v9_init()
    step = int(observation['step'] if isinstance(observation, dict) else getattr(observation, 'step', 0))
    if step in (288, 360, 432):
        import time
        t0 = time.perf_counter()
        route, decision = _V9_N.choose(_v9_deepcopy(observation), _V9_N.V.memory_of(_V9_STATE['ours']))
        _V9_REPORT['seconds'].append(round(time.perf_counter() - t0, 2))
        chassis, native = _V9_STATE['chassis'], _V9_STATE['native']
        chassis.router = native
        _V9_REPORT['decisions'].append([step // 24, (decision or {}).get('selected'), route])
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

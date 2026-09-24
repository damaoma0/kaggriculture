"""Research wrapper (NOT a submission file): the other agent system's R3 = V9 + bounded transition repair
(scripts/value_tape_repair_r3.py; docs/tape_transition_repair_20260924.md) as a playable agent for our harnesses.
Decisions are committed with value_tape_repair_r1.commit, exactly as its own harness does: the route, plus the
TransitionRepair adapter that patches the live agent's agent/_shp_topups/_shp_work/_shp_apply_cull while a repair
is active. 18-second cooperative decision deadline (R3 default).

Same protocol as its own harness (scripts/evaluate_refresh_fix_20260923.py::v9): a live base agent plays every step;
at the reveals of days 12, 15 and 18 (steps 288, 360, 432) choose(observation, memory) may commit the chassis to a
different tape route until the decision's `until` step. The base is mgt_m1 unless this file is copied with another
_BASE (e.g. agents/mgt_v9y3.py). The forecast clones are built from the same base source.
It imports from scripts/, so it runs where the repo (or the Kaggle bundle) is present.
"""
import sys as _v9_sys
from copy import deepcopy as _v9_deepcopy
from pathlib import Path as _V9Path

_BASE = 'mgt_y3'
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
import value_tape_repair_r1 as _R3_R1                      # noqa: E402
import value_tape_repair_r3 as _R3_N                      # noqa: E402

_V9_STATE = {}
_V9_REPORT = {'decisions': [], 'switches': 0, 'seconds': []}


def _v9_init():
    ours = _V9_N.V.fresh_agent()
    chassis = ours.__globals__['_MGT_IMPL'].chassis
    _V9_STATE.update(ours=ours, chassis=chassis, native=chassis.router)


def r3_agent(observation, configuration=None):
    if not _V9_STATE:
        _v9_init()
    step = int(observation['step'] if isinstance(observation, dict) else getattr(observation, 'step', 0))
    if step in (288, 360, 432):
        import time
        t0 = time.perf_counter()
        selection, decision = _R3_N.choose(_v9_deepcopy(observation), _V9_N.V.memory_of(_V9_STATE['ours']))
        _V9_REPORT['seconds'].append(round(time.perf_counter() - t0, 2))
        route = _R3_R1.unpack(selection)[0]
        _V9_REPORT['decisions'].append([step // 24, (decision or {}).get('selected'), route,
                                        bool(_R3_R1.unpack(selection)[1])])
        if route is not None:
            _V9_REPORT['switches'] += 1
        _R3_R1.commit(_V9_STATE['ours'], selection, (decision or {}).get('until', step), _V9_STATE['native'])
    return _V9_STATE['ours'](observation)

"""Research wrapper (NOT a submission file): mgt_y3 + V9-lite (scripts/value_tape_search_lite.py) at the reveals.

Same protocol as agents/mgt_v9y3.py: mgt_y3 plays every step; at the reveals of days 12, 15 and 18 (steps 288, 360,
432) the lite value selector may commit the chassis router to a different tape until the decision's `until` step.
Lite = V9's own runtime/worlds/admission with a cheaper search (see the lite module's docstring for the cuts).

Research options (environment; all absent on Kaggle and in the default panel run):
  V9LITE_PARAMS='{"count":4,...}'  override the lite parameters
  V9LITE_REPORT_DIR=<dir>          append one JSON line per reveal (timings, compact decisions) to v9lite_decisions.jsonl
  V9LITE_ACT=v9                    run and act on full V9 instead of lite (= mgt_v9y3), logged the same way. Never run
                                   both in one game: the harness enforces the 60 s overage bank (a lite+V9 shadow game
                                   exhausted it, the agent was timed out on day 18 and lost 120k)
  V9LITE_CKPT_DIR=<dir>            pickle (observation, memory) of every reveal for offline benchmarks
"""
import json as _v9l_json
import os as _v9l_os
import sys as _v9l_sys
from copy import deepcopy as _v9l_deepcopy
from pathlib import Path as _V9LPath

_BASE = 'mgt_y3'
_V9L_REVEALS = (288, 360, 432)
_V9L_ROOT = next((d for d in [_V9LPath.cwd(), *_V9LPath.cwd().parents]
                  if (d / 'scripts/value_tape_search_lite.py').exists()), _V9LPath.cwd())
if str(_V9L_ROOT / 'scripts') not in _v9l_sys.path:
    _v9l_sys.path.insert(0, str(_V9L_ROOT / 'scripts'))
import value_tape_search as _V9L_V0                       # noqa: E402

_p = _V9L_ROOT / 'agents' / f'{_BASE}.py'
_V9L_V0.SOURCE_PATH = _p
_V9L_V0.SOURCE = _p.read_text(encoding='utf-8')
_V9L_V0.CODE = compile(_V9L_V0.SOURCE, str(_p), 'exec')
import value_tape_search_v9 as _V9L_N                     # noqa: E402
import value_tape_search_lite as _V9L_L                   # noqa: E402
import rival_trajectory_model_v3 as _V9L_RTM3             # noqa: E402
assert len(_V9L_RTM3.training_library()) == 115, 'V9 opponent libraries incomplete'

_V9L_PARAMS = dict(_V9L_L.DEFAULTS, **_v9l_json.loads(_v9l_os.environ.get('V9LITE_PARAMS') or '{}'))
_V9L_STATE = {}
_V9L_REPORT = {'decisions': [], 'switches': 0, 'seconds': []}


def _v9l_init():
    ours = _V9L_N.V.fresh_agent()
    chassis = ours.__globals__['_MGT_IMPL'].chassis
    _V9L_STATE.update(ours=ours, chassis=chassis, native=chassis.router)


def _v9l_search(observation, step):
    import time
    memory = _V9L_N.V.memory_of(_V9L_STATE['ours'])
    env = _v9l_os.environ
    if env.get('V9LITE_CKPT_DIR'):
        import pickle
        d = _V9LPath(env['V9LITE_CKPT_DIR'])
        d.mkdir(parents=True, exist_ok=True)
        tag = env.get('V9LITE_TAG', str(_v9l_os.getpid()))
        with open(d / f'{tag}_{step}.pkl', 'wb') as f:
            pickle.dump(dict(observation=_v9l_deepcopy(observation), memory=memory), f)
    t0 = time.perf_counter()
    which = 'v9' if env.get('V9LITE_ACT') == 'v9' else 'lite'
    if which == 'v9':
        route, decision = _V9L_N.choose(_v9l_deepcopy(observation), memory)
    else:
        route, decision = _V9L_L.choose(_v9l_deepcopy(observation), memory, **_V9L_PARAMS)
    lite_s = time.perf_counter() - t0
    log = {'step': step, 'tag': env.get('V9LITE_TAG'), which + '_seconds': round(lite_s, 3),
           which: _V9L_L.summarize(decision)}
    if env.get('V9LITE_REPORT_DIR'):
        with open(_V9LPath(env['V9LITE_REPORT_DIR']) / 'v9lite_decisions.jsonl', 'a', encoding='utf-8') as f:
            f.write(_v9l_json.dumps(log, default=str) + chr(10))
    return route, decision, lite_s


def v9lite_agent(observation, configuration=None):
    if not _V9L_STATE:
        _v9l_init()
    step = int(observation['step'] if isinstance(observation, dict) else getattr(observation, 'step', 0))
    if step in _V9L_REVEALS:
        route, decision, seconds = _v9l_search(observation, step)
        _V9L_REPORT['seconds'].append(round(seconds, 2))
        chassis, native = _V9L_STATE['chassis'], _V9L_STATE['native']
        chassis.router = native
        _V9L_REPORT['decisions'].append([step // 24, (decision or {}).get('selected'), route])
        if route is not None:
            _V9L_REPORT['switches'] += 1
            until = decision['until']

            def committed(obs, s, memory, route=route, until=until):
                if s < until:
                    memory['route'] = route
                    return route
                return native(obs, s, memory)
            chassis.router = committed
    return _V9L_STATE['ours'](observation)

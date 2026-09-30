"""Same-process, same-checkpoint timing of V9 and V9-lite (plus a per-stage / per-component profile of V9).

Checkpoints are the (observation, memory) pickles written by agents/mgt_v9lite.py with V9LITE_CKPT_DIR (base mgt_y3).
One process, serial: import + runtime construction (cold) are timed separately, then for every checkpoint lite and
V9 are run back to back (order alternates between checkpoints so neither always gets the warmer caches).

usage: v9lite_bench.py <out.json> <ckpt.pkl> [<ckpt.pkl> ...] [--params '{"count":4}'] [--profile]
"""
import json
import pickle
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
T0 = time.perf_counter()
import value_tape_search as V0                       # noqa: E402

_p = ROOT / 'agents' / 'mgt_y3.py'
V0.SOURCE_PATH, V0.SOURCE = _p, _p.read_text(encoding='utf-8')
V0.CODE = compile(V0.SOURCE, str(_p), 'exec')
import value_tape_search_v9 as N                     # noqa: E402
import value_tape_search_lite as L                   # noqa: E402
import rival_trajectory_model_v3 as RTM3             # noqa: E402
assert len(RTM3.training_library()) == 115
IMPORT_S = time.perf_counter() - T0


def instrument(runner, log):
    """Time every rollout (route, world index, turns) and world build; restore with the returned callable."""
    orig_rollout, orig_world = runner.rollout, N.M.world

    def rollout(obs, memory, route, world, until=None, protected=None):
        t = time.perf_counter()
        r = orig_rollout(obs, memory, route, world, until=until, protected=protected)
        log.append(dict(kind='rollout', route=route, world=world['index'], s=time.perf_counter() - t,
                        turns=r.get('boundary_step', 719) - int(obs['step']), early=bool(r.get('early_rejection'))))
        return r

    def world(obs, i):
        t = time.perf_counter()
        w = orig_world(obs, i)
        log.append(dict(kind='world', world=i, s=time.perf_counter() - t))
        return w

    runner.rollout, N.M.world = rollout, world
    return lambda: (setattr(runner, 'rollout', orig_rollout), setattr(N.M, 'world', orig_world))


def stage_of(e, native_first=True):
    if e['kind'] == 'world':
        return 'worlds'
    return 'scout(w0)' if e['world'] == 0 else ('4-world(w1-3)' if e['world'] < 4 else '8-world(w4-7)')


def main():
    args = sys.argv[1:]
    params = {}
    profile = '--profile' in args
    if '--params' in args:
        i = args.index('--params')
        params = json.loads(args[i + 1])
        del args[i:i + 2]
    args = [a for a in args if a != '--profile']
    out, ckpts = Path(args[0]), args[1:]
    t = time.perf_counter()
    runner = N.runtime()
    runtime_s = time.perf_counter() - t
    res = dict(import_s=IMPORT_S, runtime_construct_s=runtime_s, params=dict(L.DEFAULTS, **params), rows=[])
    print(f'import {IMPORT_S:.2f}s runtime {runtime_s:.2f}s', flush=True)
    if ckpts:   # the first search after the runtime is built runs on cold caches: time it once, separately
        ck = pickle.load(open(ckpts[0], 'rb'))
        t = time.perf_counter()
        L.choose(deepcopy(ck['observation']), deepcopy(ck['memory']), **dict(L.DEFAULTS, **params))
        res['first_lite_cold_s'] = time.perf_counter() - t
        print(f"first (cold) lite search {res['first_lite_cold_s']:.2f}s", flush=True)
    for k, path in enumerate(ckpts):
        ck = pickle.load(open(path, 'rb'))
        obs, mem = ck['observation'], ck['memory']
        row = dict(ckpt=Path(path).name)
        order = ['lite', 'v9'] if k % 2 == 0 else ['v9', 'lite']
        for which in order:
            log = []
            restore = instrument(runner, log)
            try:
                t = time.perf_counter()
                if which == 'lite':
                    route, dec = L.choose(deepcopy(obs), deepcopy(mem), **dict(L.DEFAULTS, **params))
                else:
                    route, dec = N.choose(deepcopy(obs), deepcopy(mem))
                s = time.perf_counter() - t
            finally:
                restore()
            stages = {}
            for e in log:
                st = stage_of(e)
                stages.setdefault(st, [0.0, 0, 0])
                stages[st][0] += e['s']
                stages[st][1] += 1
                stages[st][2] += e.get('turns', 0)
            row[which] = dict(seconds=s, selected=route, rollouts=sum(1 for e in log if e['kind'] == 'rollout'),
                              turns=sum(e.get('turns', 0) for e in log),
                              rollout_s=sum(e['s'] for e in log if e['kind'] == 'rollout'),
                              stages={k2: [round(v[0], 3), v[1], v[2]] for k2, v in stages.items()},
                              other_s=s - sum(e['s'] for e in log))
        print(row['ckpt'], {w: (round(row[w]['seconds'], 2), row[w]['selected'], row[w]['rollouts'], row[w]['turns'])
                            for w in ('v9', 'lite')}, flush=True)
        res['rows'].append(row)
        out.write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
    if profile and ckpts:
        import cProfile
        import pstats
        import io
        ck = pickle.load(open(ckpts[0], 'rb'))
        pr = cProfile.Profile()
        pr.enable()
        N.choose(deepcopy(ck['observation']), deepcopy(ck['memory']))
        pr.disable()
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats('cumulative').print_stats(45)
        res['profile_cumulative'] = s.getvalue()
        s = io.StringIO()
        pstats.Stats(pr, stream=s).sort_stats('tottime').print_stats(30)
        res['profile_tottime'] = s.getvalue()
        out.write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
    print('done', flush=True)


if __name__ == '__main__':
    main()

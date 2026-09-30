"""Serial V8 / shared-world / shared-world+packed-board equivalence and timing."""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import pickle
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time
from types import FunctionType, SimpleNamespace

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
BASE = ROOT.parent / 'tape_speed_cloud_20260923_01a0' / 'payload'
PAYLOAD = ROOT / 'payload'
OUT = ROOT / 'measurements'


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prepare():
    assert not PAYLOAD.exists(), 'Keep completed source snapshots immutable'
    manifest = json.loads((BASE / 'manifest.json').read_text())
    for name, expected in manifest['sha256'].items():
        assert sha(BASE / name) == expected, name
    shutil.copytree(BASE, PAYLOAD)
    extra = PROJECT / 'scripts/value_tape_search_v9.py'
    shutil.copy2(extra, PAYLOAD / 'scripts' / extra.name)
    manifest['sha256']['scripts/' + extra.name] = sha(extra)
    manifest['parent_manifest_sha256'] = sha(BASE / 'manifest.json')
    manifest['protocol'] = __doc__
    write(PAYLOAD / 'manifest.json', manifest)
    print(json.dumps(dict(prepared=len(manifest['sha256']), planner_sha256=sha(extra))), flush=True)


def verify():
    manifest = json.loads((PAYLOAD / 'manifest.json').read_text())
    for name, expected in manifest['sha256'].items():
        assert sha(PAYLOAD / name) == expected, name
    return manifest


def imports():
    sys.path[:0] = [str(PAYLOAD / 'scripts'), str(PAYLOAD / 'vendor')]
    newer = importlib.import_module('value_tape_search_v9')
    from kaggle_environments.utils import structify
    with gzip.open(PAYLOAD / 'checkpoints.pkl.gz', 'rb') as handle:
        points = pickle.load(handle)
    return newer, structify, points


def semantic(decision):
    ignored = {'seconds', 'rank_seconds', 'planner_sha256'}
    return {k: v for k, v in decision.items() if k not in ignored}


def choose_policy(newer, policy):
    if policy == 'v8':
        return newer.B.choose, newer.B.runtime
    if policy == 'v9':
        return newer.choose, newer.runtime
    runner = None
    def runtime():
        nonlocal runner
        if runner is None:
            runner = newer.Runtime(packed_boards=False)
        return runner
    model = SimpleNamespace(MODEL_SHA256=newer.B.M.MODEL_SHA256,
        world=lambda obs, index: runtime().world_batch.world(obs, index))
    namespace = dict(newer.B.choose.__globals__, runtime=runtime, M=model,
                     PLANNER_SHA256=newer.PLANNER_SHA256)
    choose = FunctionType(newer.B.choose.__code__, namespace, 'choose', newer.B.choose.__defaults__)
    choose.__kwdefaults__ = newer.B.choose.__kwdefaults__.copy()
    return choose, runtime


def worker(policy, case, repeats):
    verify()
    newer, structify, points = imports()
    point = points[case]
    choose, runtime = choose_policy(newer, policy)
    input_hash = digest(newer.V.canonical([point['obs'], point['memory']]))
    rows = []
    reference = None
    for repeat in range(repeats+1):
        obs = structify(point['obs'])
        t0, c0 = time.perf_counter(), time.process_time()
        selected, decision = choose(obs, point['memory'])
        wall, cpu = time.perf_counter()-t0, time.process_time()-c0
        assert input_hash == digest(newer.V.canonical([obs, point['memory']]))
        forecasts = {str(c['route']): [digest(newer.V.canonical(p)) for p in c['predictions']]
                     for c in decision['candidates']}
        assert selected == point['expected_selected'], (point['id'], selected)
        compared = 0
        for route, preds in forecasts.items():
            for i, value in enumerate(preds):
                expected = point['expected_forecasts'].get(route, [])
                if i < len(expected):
                    assert expected[i] == value, (point['id'], route, i)
                    compared += 1
        current = newer.V.canonical(semantic(decision))
        if reference is None:
            reference = current
        assert current == reference, 'Repeated decision changed'
        runner = runtime()
        cache = runner.packed_hamming.encode.cache_info()._asdict() if (
            hasattr(runner, 'packed_hamming') and runner.packed_hamming) else None
        row = dict(policy=policy, case=point['id'], repeat=repeat,
            phase='cold' if repeat == 0 else 'warm', wall_seconds=wall, cpu_seconds=cpu,
            selected=selected, forecasts=forecasts, historical_forecasts_equal=compared,
            rollouts=decision['rollouts'], simulated_turns=decision['simulated_turns'],
            semantic_sha256=digest(current), board_cache=cache,
            world_profile_evaluations=getattr(getattr(runner, 'world_batch', None), 'profile_evaluations', None),
            world_board_evaluations=getattr(getattr(runner, 'world_batch', None), 'board_evaluations', None))
        rows.append(row)
        write(OUT / f'{point["id"]}-{policy}-{repeat}.json', dict(row, decision=decision))
        print('SAMPLE ' + json.dumps({k: v for k, v in row.items() if k != 'forecasts'}), flush=True)
    write(OUT / f'worker-{point["id"]}-{policy}.json', dict(rows=rows))


def structural():
    verify()
    newer, structify, cloud_points = imports()
    original = lambda a, b: sum(x != y for x, y in zip(a, b))
    packed = newer.PackedHamming(original, maxsize=32)
    rng = random.Random(93230923)
    checks = 0
    # Each bit of either character, lane boundaries, empty and unequal lengths.
    alphabet = [chr(a)+chr(b) for a in range(0, 128, 17) for b in range(0, 128, 19)]
    for length in (0, 1, 2, 31, 99, 100, 101):
        for _ in range(100):
            a = rng.choices(alphabet, k=length)
            b = rng.choices(alphabet, k=length)
            assert packed(a, b) == original(a, b)
            if a:
                a[0] = b[0]
                assert packed(a, b) == original(a, b)
            checks += 2 if a else 1
    for a, b in [([], ['sh']), (['sh', 'co'], ['sh']),
                 ([None, 'a', 'abc', '\u4e2d\u6587'], ['sh', 'b', 'def', '\u4e2d\u6587']),
                 ([[1], {'a': 2}], [[1], {'a': 3}])]:
        assert packed(a, b) == original(a, b)
        checks += 1
    assert packed.encode.cache_info().currsize <= 32
    # Read the wider saved panel only for exact scenario equivalence, never fit.
    audit_dir = PROJECT / 'results/fresh/value_tape_ranker_20260923'
    audit = json.loads((audit_dir / 'dataset_audit.json').read_text())
    points = []
    sources = {}
    for item in sorted(audit['rows'], key=lambda x: x['id']):
        path = audit_dir / 'checkpoints' / (item['id'] + '.pkl.gz')
        assert sha(path) == item['artifact_sha256']
        sources[str(path.relative_to(PROJECT))] = sha(path)
        with gzip.open(path, 'rb') as handle:
            points.extend(pickle.load(handle))
    world_rows = []
    for p in points:
        obs = p['obs']
        input_hash = digest(newer.V.canonical(obs))
        batch = newer.WorldBatch(obs)
        fingerprints = []
        for i in range(8):
            old = newer.B.M.world(obs, i)
            new = batch.world(obs, i)
            assert old == new, (p['id'], i)
            fingerprints.append(digest(newer.V.canonical(new)))
        assert input_hash == digest(newer.V.canonical(obs))
        assert batch.profile_evaluations == 1 and batch.board_evaluations == 115
        world_rows.append(dict(case=p['id'], worlds=fingerprints))
        if len(world_rows) % 10 == 0:
            print('WORLDS ' + str(len(world_rows)), flush=True)
    # Worlds own their mutable farms; changes cannot contaminate the next batch.
    obs = deepcopy(cloud_points[0]['obs'])
    batch = newer.WorldBatch(obs)
    world = batch.world(obs, 0)
    world['farms'][int(obs['day'])]['tiles'][0][0] = 'TEST_MUTATION'
    assert batch.world(obs, 0) == newer.B.M.world(obs, 0)
    obs['farms'][1-int(obs['player'])]['tiles'][0][0] = None
    assert newer.WorldBatch(obs).world(obs, 0) == newer.B.M.world(obs, 0)
    report = dict(hamming_checks=checks, max_board_cache_entries=32,
        checkpoints=len(world_rows), equal_worlds=8*len(world_rows), rows=world_rows,
        input_sources=sources, mutable_world_and_new_input_isolation=True)
    write(ROOT / 'structural_equivalence.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows', 'input_sources')}), flush=True)


def summarize():
    workers = [json.loads(p.read_text()) for p in sorted(OUT.glob('worker-*.json'))]
    rows = [r for w in workers for r in w['rows']]
    cases = sorted({r['case'] for r in rows})
    assert len(workers) == 18 and len(cases) == 6
    comparisons = []
    for case in cases:
        group = [r for r in rows if r['case'] == case]
        assert len({r['semantic_sha256'] for r in group}) == 1, case
        assert len({(r['rollouts'], r['simulated_turns']) for r in group}) == 1
        comparisons.append(dict(case=case, selected=group[0]['selected'],
            semantic_equal=True, warm={p:{metric:statistics.mean(r[metric] for r in group
                if r['policy'] == p and r['phase'] == 'warm')
                for metric in ('wall_seconds', 'cpu_seconds')}
                for p in ('v8', 'worlds', 'v9')}))
    metrics = {p:{phase:{metric:dict(mean=statistics.mean(values),
        median=statistics.median(values), min=min(values), max=max(values), n=len(values))
        for metric in ('wall_seconds', 'cpu_seconds')
        if (values := [r[metric] for r in rows if r['policy'] == p and r['phase'] == phase])}
        for phase in ('cold', 'warm')} for p in ('v8', 'worlds', 'v9')}
    result = dict(metrics=metrics, comparisons=comparisons, decisions=len(rows),
        all_semantic_decisions_equal=True, cases=len(cases), rows=rows,
        manifest_sha256=sha(PAYLOAD/'manifest.json'))
    write(ROOT / 'summary.json', result)
    print('SUMMARY ' + json.dumps({k:v for k,v in result.items() if k != 'rows'}), flush=True)


def panel(repeats):
    verify()
    assert not list(OUT.glob('worker-*.json')), 'Use a fresh output directory'
    env = dict(os.environ)
    env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
    env['PYTHONHASHSEED'] = '0'
    hardware = dict(python=sys.version, platform=platform.platform(),
        cpu_count=os.cpu_count(), processor=os.environ.get('PROCESSOR_IDENTIFIER'))
    try:
        import psutil
        hardware['memory_start'] = dict(psutil.virtual_memory()._asdict())
        hardware['cpu_percent_start'] = psutil.cpu_percent(interval=.2)
    except ImportError:
        pass
    write(ROOT / 'hardware.json', hardware)
    t0 = time.perf_counter()
    for case in range(6):
        # Cyclic order and its reverse each occur once; one worker at a time.
        orders = [('v8','worlds','v9'), ('worlds','v9','v8'), ('v9','v8','worlds'),
                  ('v9','worlds','v8'), ('v8','v9','worlds'), ('worlds','v8','v9')]
        for policy in orders[case]:
            result = subprocess.run([sys.executable, str(Path(__file__)), '--worker', policy,
                '--case', str(case), '--repeats', str(repeats)], env=env)
            assert result.returncode == 0, (case, policy, result.returncode)
    summarize()
    write(ROOT / 'completion.json', dict(wall_seconds=time.perf_counter()-t0, completed=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--structural', action='store_true')
    parser.add_argument('--worker', choices=['v8','worlds','v9'])
    parser.add_argument('--case', type=int, default=0)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--summarize', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.structural:
        structural()
    elif args.worker:
        worker(args.worker, args.case, args.repeats)
    elif args.summarize:
        summarize()
    else:
        panel(args.repeats)

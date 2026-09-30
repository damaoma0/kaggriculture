"""Frozen, serial Kaggle CPU benchmark. No competition submission is made."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import pickle
import platform
import statistics
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'cloud_results'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def hardware():
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None
    versions = {}
    for name in ('kaggle-environments', 'jsonschema', 'requests', 'numpy'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    cpuinfo = read('/proc/cpuinfo') or ''
    return dict(python=sys.version, platform=platform.platform(), cpu_count=os.cpu_count(),
        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
        cpu_models=sorted({line.split(':', 1)[1].strip() for line in cpuinfo.splitlines()
                           if line.startswith('model name')}),
        cpu_max=read('/sys/fs/cgroup/cpu.max'),
        cpu_quota_us=read('/sys/fs/cgroup/cpu/cpu.cfs_quota_us'),
        cpu_period_us=read('/sys/fs/cgroup/cpu/cpu.cfs_period_us'),
        memory_max=read('/sys/fs/cgroup/memory.max'),
        memory_limit=read('/sys/fs/cgroup/memory/memory.limit_in_bytes'),
        cpu_stat=read('/sys/fs/cgroup/cpu.stat'),
        loadavg=read('/proc/loadavg'), installed_versions=versions,
        thread_limits={name: os.environ.get(name) for name in
            ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')})


def verify():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    for relative, expected in manifest['sha256'].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert actual == expected, f'Frozen file changed: {relative}'
    return manifest


def fingerprints(planner, decision):
    return {str(row['route']): [digest(planner.V.canonical(p)) for p in row['predictions']]
            for row in decision['candidates']}


def worker(policy, case_index, repeats, deadline):
    # Dependencies are exact copies of the local framework and engine; only the
    # unused environments/renderers are omitted. No planner source is rewritten.
    sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'vendor')]
    import_wall = time.perf_counter()
    import_cpu = time.process_time()
    planner = importlib.import_module('value_tape_search_' + policy)
    from kaggle_environments.utils import structify
    import_wall = time.perf_counter() - import_wall
    import_cpu = time.process_time() - import_cpu
    with gzip.open(ROOT / 'checkpoints.pkl.gz', 'rb') as handle:
        points = pickle.load(handle)
    point = points[case_index]
    case = point['id']
    inp = [point['obs'], point['memory']]
    initial_digest = digest(planner.V.canonical(inp))
    rows = []
    for repeat in range(repeats + 1):
        observation = structify(point['obs'])
        t0, c0 = time.perf_counter(), time.process_time()
        selected, decision = planner.choose(observation, point['memory'])
        elapsed, cpu = time.perf_counter() - t0, time.process_time() - c0
        assert initial_digest == digest(planner.V.canonical(inp)), 'Input mutated'
        hashes = fingerprints(planner, decision)
        common, mismatch = 0, []
        for route, preds in hashes.items():
            for i, value in enumerate(preds):
                reference = point['expected_forecasts'].get(route, [])
                if i < len(reference):
                    common += 1
                    if value != reference[i]:
                        mismatch.append([route, i])
        row = dict(policy=policy, case=case, day=point['obs']['day'], repeat=repeat,
            phase='cold' if repeat == 0 else 'warm', wall_seconds=elapsed, cpu_seconds=cpu,
            selected=selected, expected_selected=point['expected_selected'],
            matches_expected_selection=selected == point['expected_selected'],
            historical_common_forecasts=common, historical_forecast_mismatches=mismatch,
            rollouts=decision['rollouts'], simulated_turns=decision['simulated_turns'],
            pruned_rollouts=decision['pruned_rollouts'], forecasts=hashes,
            input_sha256=decision['input_sha256'],
            shortlisted=decision.get('shortlisted'), timed_out=decision.get('timed_out', False))
        rows.append(row)
        write(OUT / f'{case}-{policy}-{repeat}.json', dict(row, decision=decision))
        print('SAMPLE ' + json.dumps({k: v for k, v in row.items() if k != 'forecasts'}), flush=True)
    if deadline is not None and policy == 'v8':
        t0, c0 = time.perf_counter(), time.process_time()
        selected, decision = planner.choose(structify(point['obs']), point['memory'], budget_seconds=deadline)
        row = dict(policy=policy, case=case, phase='deadline', budget_seconds=deadline,
            wall_seconds=time.perf_counter()-t0, cpu_seconds=time.process_time()-c0,
            selected=selected, timed_out=decision['timed_out'], rollouts=decision['rollouts'],
            simulated_turns=decision['simulated_turns'])
        if selected is not None:
            chosen = next(r for r in decision['candidates'] if r['route'] == selected)
            assert chosen['fully_evaluated'] and chosen['admitted']
        rows.append(row)
        write(OUT / f'{case}-{policy}-deadline.json', dict(row, decision=decision))
        print('DEADLINE ' + json.dumps(row), flush=True)
    try:
        import resource
        peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:
        peak_rss = None
    write(OUT / f'worker-{case}-{policy}.json', dict(rows=rows, import_wall_seconds=import_wall,
        import_cpu_seconds=import_cpu, peak_rss_platform_units=peak_rss))


def distribution(values):
    ordered = sorted(values)
    return dict(n=len(values), mean=statistics.mean(values), median=statistics.median(values),
        p95_nearest_rank=ordered[math.ceil(.95*len(ordered))-1], min=min(values), max=max(values))


def summarize(manifest, hw, wall):
    workers = [json.loads(p.read_text()) for p in sorted(OUT.glob('worker-*.json'))]
    rows = [row for worker in workers for row in worker['rows']]
    complete = [r for r in rows if r['phase'] != 'deadline']
    mismatches = []
    comparisons = []
    for case in manifest['cases']:
        by_policy = {p: [r for r in complete if r['case'] == case['id'] and r['policy'] == p] for p in ('v7', 'v8')}
        reference = {r['policy']: r for r in complete if r['case'] == case['id'] and r['repeat'] == 0}
        common = 0
        for route, preds in reference['v8']['forecasts'].items():
            for i, value in enumerate(preds):
                older = reference['v7']['forecasts'].get(route, [])
                if i < len(older):
                    common += 1
                    if value != older[i]:
                        mismatches.append([case['id'], route, i])
        stable = all(r['selected'] == reference['v7']['selected'] and
            r['forecasts'] == reference[r['policy']]['forecasts'] for group in by_policy.values() for r in group)
        medians = {p: statistics.median(r['wall_seconds'] for r in group if r['phase'] == 'warm')
                   for p, group in by_policy.items()}
        comparisons.append(dict(case=case['id'], day=case['day'], selected=reference['v8']['selected'],
            v7_warm_median=medians['v7'], v8_warm_median=medians['v8'],
            wall_reduction=1-medians['v8']/medians['v7'],
            v7_cold=reference['v7']['wall_seconds'], v8_cold=reference['v8']['wall_seconds'],
            v7_turns=reference['v7']['simulated_turns'], v8_turns=reference['v8']['simulated_turns'],
            common_forecasts=common, stable_selections_and_forecasts=stable))
    metrics = {policy: {phase: {
        metric: distribution([r[metric] for r in complete if r['policy'] == policy and r['phase'] == phase])
        for metric in ('wall_seconds', 'cpu_seconds')}
        for phase in ('cold', 'warm')} for policy in ('v7', 'v8')}
    ratio = sum(c['v8_warm_median'] for c in comparisons) / sum(c['v7_warm_median'] for c in comparisons)
    return dict(protocol=manifest['protocol'], hardware_start=hw, hardware_end=hardware(),
        total_wall_seconds=wall, manifest_sha256=hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest(),
        metrics=metrics, cases=comparisons, warm_wall_reduction=1-ratio,
        common_forecast_mismatches=mismatches, rows=rows, workers=[{k:v for k,v in x.items() if k!='rows'} for x in workers],
        historical_selection_matches=sum(r['matches_expected_selection'] for r in complete),
        historical_selection_total=len(complete),
        historical_forecast_mismatches=[(r['case'],r['policy'],r['historical_forecast_mismatches'])
            for r in complete if r['historical_forecast_mismatches']])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker', choices=['v7', 'v8'])
    parser.add_argument('--case', type=int, default=0)
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--deadline', type=float, default=.8)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    manifest = verify()
    if args.validate_only:
        sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'vendor')]
        import value_tape_search_v8 as planner
        from kaggle_environments.utils import structify
        from test_labour_selfplay import project_input
        with gzip.open(ROOT/'checkpoints.pkl.gz','rb') as handle:
            points=pickle.load(handle)
        for point in points:
            project_input(structify(point['obs']))
        print(json.dumps(dict(files=len(manifest['sha256']), checkpoints=len(points),
            rival_examples=len(planner.M.training_library()), engine_sha256=hashlib.sha256(
                Path(planner.V.R.engine().__file__).read_bytes()).hexdigest())))
        return
    OUT.mkdir(exist_ok=True, parents=True)
    if args.worker:
        worker(args.worker, args.case, args.repeats, args.deadline)
        return
    assert not list(OUT.glob('worker-*.json')), 'Use a fresh output directory for each run'
    hw = hardware()
    write(OUT/'hardware.json', hw)
    print('HARDWARE ' + json.dumps(hw), flush=True)
    env = dict(os.environ)
    env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
    env['PYTHONHASHSEED']='0'
    start=time.perf_counter()
    for case_index, case in enumerate(manifest['cases']):
        order = ['v7','v8'] if case_index % 2 == 0 else ['v8','v7']
        for policy in order:
            print('START ' + json.dumps(dict(case=case['id'], policy=policy)), flush=True)
            t0=time.perf_counter()
            result=subprocess.run([sys.executable,str(Path(__file__)), '--worker',policy,
                '--case',str(case_index),'--repeats',str(args.repeats),'--deadline',str(args.deadline)], env=env)
            assert result.returncode == 0, f'{case["id"]} {policy} failed: {result.returncode}'
            print('WORKER_FINISHED ' + json.dumps(dict(case=case['id'],policy=policy,
                process_wall_seconds=time.perf_counter()-t0)),flush=True)
    summary=summarize(manifest,hw,time.perf_counter()-start)
    write(OUT/'summary.json',summary)
    print('SUMMARY ' + json.dumps({k:v for k,v in summary.items() if k not in ('rows','workers')}),flush=True)
    print('RESULT_BASE64 ' + base64.b64encode(gzip.compress(json.dumps(summary).encode())).decode(),flush=True)
    print('BENCHMARK_COMPLETE',flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise

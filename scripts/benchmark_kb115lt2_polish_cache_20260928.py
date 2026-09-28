"""Replay captured polish calls, demanding exact outputs before reporting speed.

No environment, live opponent, future shop input or gameplay benchmark is run.
The input fixtures must come from our verified, hash-bound local replay capture.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    manifest_path = args.fixtures / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if not manifest.get('verified'):
        raise ValueError('Capture must have completed its source-parity checks')
    basepath = ROOT / 'agents/mgt_lead_kb115lt2.py'
    fastpath = ROOT / 'agents/mgt_lead_kb115lt2_polishcache.py'
    original = load('_strategy_kb115lt', basepath)
    cached = load('_polish_cached_benchmark', fastpath)
    rows = []
    fixture_hashes = {row['file']: row['sha256'] for row in manifest['fixtures']}
    for path in sorted(args.fixtures.glob('*.pickle.gz')):
        if sha(path) != fixture_hashes.get(path.name):
            raise ValueError(f'Captured fixture changed: {path.name}')
        payload = pickle.loads(gzip.decompress(path.read_bytes()))
        fixture = pickle.loads(payload['input_pickle'])
        expected = payload['reference_output_pickle']
        # Compare values independently of pickle's representation, then compare
        # bytes as an additional preservation check when the graph serializes.
        expected_value = pickle.loads(expected)
        results = {name: [] for name in ('original', 'cached')}
        equality = []
        for repeat in range(args.repeats):
            order = [('original', original), ('cached', cached)]
            if repeat % 2:
                order.reverse()
            for name, module in order:
                for key, value in fixture['globals'].items():
                    setattr(module, key, deepcopy(value))
                inputs = pickle.loads(payload['input_pickle'])['args']
                started = time.perf_counter()
                returned = module._tier_polish(*inputs)
                elapsed = time.perf_counter() - started
                results[name].append(elapsed)
                same = inputs == expected_value and returned == payload.get('return_value')
                equality.append(dict(implementation=name, repeat=repeat, values_equal=same,
                                     pickle_equal=pickle.dumps(inputs, protocol=pickle.HIGHEST_PROTOCOL) == expected))
                if not same:
                    raise AssertionError(f'Changed captured output: {path.name}, {name}, repeat{repeat}')
        row = dict(file=path.name, sha256=sha(path), day=fixture['args'][4],
                   exact_output_checks=equality, seconds=results,
                   original_median=statistics.median(results['original']),
                   cached_median=statistics.median(results['cached']))
        row['speed_ratio'] = row['original_median'] / row['cached_median']
        rows.append(row)
        print(json.dumps({k:row[k] for k in ('file', 'day', 'original_median', 'cached_median', 'speed_ratio')}), flush=True)
    if not rows:
        raise ValueError('No fixtures found')
    out = dict(scope='CAPTURED_PURE_POLISH_CALLS_NOT_GAMEPLAY', capture_manifest_sha256=sha(manifest_path),
               original_sha256=sha(basepath), cached_sha256=sha(fastpath), script_sha256=sha(Path(__file__)),
               original_unchanged=True, iterations_and_random_draws_unchanged=True,
               rows=rows, all_outputs_equal=True,
               limitation='Isolated call speed is not a full-game runtime or profit result.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError('Preserve existing benchmark outputs; choose a new output')
    args.output.write_text(json.dumps(out, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

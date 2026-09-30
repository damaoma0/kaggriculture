"""Replay the corrected frozen V5 panel with V6; require every forecast to match.

This reuses the same worlds. It validates the implementation, not new policy
strength. Completed V5 forecasts are assertion targets only, never decision inputs.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import statistics
import time
import traceback
from types import FunctionType, SimpleNamespace

import benchmark_value_tape_generalization_v2 as B
import value_tape_search_v6 as F

OUT = B.OUT.parent / 'v6_live_equivalence'


def worker(spec):
    target = OUT / f"{spec['id']}.json"
    if target.exists():
        return json.loads(target.read_text(encoding='utf-8'))
    started = time.perf_counter()
    with target.with_suffix('.log').open('w', encoding='utf-8') as log:
        saved = [os.dup(1), os.dup(2)]
        try:
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
            reference = json.loads((B.OUT / target.name).read_text(encoding='utf-8'))
            comparisons = []
            def compare(obs, memory):
                route, decision = F.choose(obs, memory)
                old = next(d for d in reference['candidate']['decisions'] if d['day'] == decision['day'])
                assert json.loads(json.dumps(decision['candidates'])) == old['candidates']
                assert decision['worlds'] == old['worlds'] and decision['selected'] == old['selected']
                comparisons.append(dict(day=decision['day'], selected=route, seconds=decision['seconds'],
                    v5_seconds=old['seconds'], forecasts=decision['rollouts'], complete_forecast_equal=True))
                return route, decision
            game = FunctionType(B.game.__code__, dict(B.game.__globals__, F=SimpleNamespace(choose=compare)),
                'equivalence_live_game', B.game.__defaults__)
            actual = game(spec, True, OUT)
            assert actual['actions_sha256'] == reference['candidate']['actions_sha256']
            assert actual['cash'] == reference['candidate']['cash'] and actual['rival_cash'] == reference['candidate']['rival_cash']
            row = dict(id=spec['id'], completed=True, comparisons=comparisons,
                actions_and_cash_equal=True, original_margin_delta=reference['margin_delta'])
        except Exception:
            row = dict(id=spec['id'], completed=False, error=traceback.format_exc())
        finally:
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            for fd in saved:
                os.close(fd)
    row['seconds'] = time.perf_counter()-started
    target.write_text(json.dumps(row, indent=2), encoding='utf-8')
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    reference = json.loads((B.OUT / 'design.json').read_text(encoding='utf-8'))
    paths = [Path(__file__), Path(F.__file__), Path(F.F.__file__)]
    hashes = {p.name: sha256(p.read_bytes()).hexdigest() for p in paths}
    design_path = OUT / 'design.json'
    if design_path.exists():
        assert json.loads(design_path.read_text(encoding='utf-8'))['hashes'] == hashes
    else:
        design_path.write_text(json.dumps(dict(hashes=hashes, specs=reference['specs'],
            reference_design_sha256=sha256((B.OUT/'design.json').read_bytes()).hexdigest(),
            protocol=__doc__), indent=2), encoding='utf-8')
        for p in paths:
            (OUT / p.name).write_bytes(p.read_bytes())
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker, s) for s in reference['specs']]):
            row = future.result()
            rows.append(row)
            print(json.dumps(row), flush=True)
    decisions = [d for r in rows if r['completed'] for d in r['comparisons']]
    times = [d['seconds'] for d in decisions]
    summary = dict(games=len(rows), completed=sum(r['completed'] for r in rows),
        decisions=len(decisions), forecasts=sum(d['forecasts'] for d in decisions),
        seconds=dict(median=statistics.median(times), minimum=min(times), maximum=max(times)), rows=rows)
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'}), flush=True)


if __name__ == '__main__':
    main()

"""Correct the V56 entry point; retain the other twelve verified pairs.

The original sources and results stay frozen. This is a protocol correction on
the same prespecified worlds, not a new independent sample or a policy change.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import argparse
import json
from pathlib import Path
import statistics
from types import FunctionType

import benchmark_value_tape_generalization as B

OUT = B.OUT.parent / 'generalization_corrected'


def load_opponent(name):
    if name != 'v56':
        return B.load_opponent(name)
    from kaggle_environments.agent import get_last_callable
    path = B.OPPONENTS[name]
    entry = get_last_callable(path.read_text(encoding='utf-8'), path=str(path))
    assert entry.__name__ == 'e410_agent', entry.__name__
    return entry


game = FunctionType(B.game.__code__, dict(B.game.__globals__, load_opponent=load_opponent),
    'corrected_live_game', B.game.__defaults__)
_worker = FunctionType(B.worker.__code__, dict(B.worker.__globals__, OUT=OUT, game=game),
    'corrected_worker', B.worker.__defaults__)


def worker(spec):
    return _worker(spec)


def freeze_design():
    previous = json.loads((B.OUT / 'design.json').read_text(encoding='utf-8'))
    assert previous['hashes'] == B.hashes()
    code_hash = sha256(Path(__file__).read_bytes()).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'design.json'
    if path.exists():
        design = json.loads(path.read_text(encoding='utf-8'))
        assert design['correction_sha256'] == code_hash
        return design
    design = dict(previous, correction_sha256=code_hash,
        correction='V56 must invoke the Kaggle last-new-callable e410_agent, not its earlier module.agent. Rerun only those six pairs on the identical frozen worlds. Sixday and pasture already used their correct agent entry points; reuse their twelve completed, ledger-verified pairs by exact artifact hash. No selector changes.',
        reused={})
    for spec in previous['specs']:
        if spec['opponent'] == 'v56':
            continue
        source = B.OUT / f"{spec['id']}.json"
        row = json.loads(source.read_text(encoding='utf-8'))
        assert row['completed'] and row['spec'] == spec
        assert row['baseline']['ledger_verified'] and row['candidate']['ledger_verified']
        (OUT / source.name).write_bytes(source.read_bytes())
        design['reused'][source.name] = sha256(source.read_bytes()).hexdigest()
    path.write_text(json.dumps(design, indent=2), encoding='utf-8')
    (OUT / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    return design


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    design = freeze_design()
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker, s) for s in design['specs'] if s['opponent'] == 'v56']):
            print(json.dumps(future.result()), flush=True)
    rows = []
    for spec in design['specs']:
        row = json.loads((OUT / f"{spec['id']}.json").read_text(encoding='utf-8'))
        rows.append({k: row.get(k) for k in ('spec', 'completed', 'selected', 'changed', 'margin_delta',
            'cash_delta', 'rival_delta', 'seconds', 'error')})
    summary = dict(games=len(rows), completed=sum(r['completed'] for r in rows), rows=rows)
    for label, subset in [('all', rows), *[(name, [r for r in rows if r['spec']['opponent'] == name])
            for name in B.OPPONENTS], ('iid', [r for r in rows if r['spec']['group'] == 'iid']),
            ('stress', [r for r in rows if r['spec']['group'] != 'iid'])]:
        valid = [r for r in subset if r['completed']]
        values = [r['margin_delta'] for r in valid]
        summary[label] = dict(n=len(valid), changed=sum(r['changed'] for r in valid),
            mean=statistics.mean(values) if values else None, total=sum(values),
            minimum=min(values, default=None), maximum=max(values, default=None),
            positive=sum(v > 0 for v in values), negative=sum(v < 0 for v in values))
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}), flush=True)


if __name__ == '__main__':
    main()

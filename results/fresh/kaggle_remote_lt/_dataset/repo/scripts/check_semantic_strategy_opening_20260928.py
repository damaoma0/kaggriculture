"""Compare opening actions on saved observations only; execute no games."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from semantic_strategy_opening_20260928 import make_opening, CONTRACTS, _contracts
from coherent_opening_v5 import SemanticInputPolicy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/semantic_strategy_20260928/opening_parity.json'


def main():
    start = time.perf_counter()
    compact = make_opening()
    init = time.perf_counter() - start
    immutable_before = hashlib.sha256(json.dumps(_contracts(CONTRACTS)['library'], sort_keys=True).encode()).hexdigest()
    reference = SemanticInputPolicy()
    index = json.loads((ROOT / 'results/fresh/coherent_opening_20260924_01a0/extraction/full/index.json').read_text())
    cases, checked = [], 0
    # Fixed oldest source cases, selected without outcomes; each saved prefix
    # contains actual positions/private inputs/prices/opponent observations.
    for row in index[:8]:
        path = ROOT / f'data/dsm_replays/episode-{row["episode"]}-replay.json'
        if not path.exists():
            continue
        replay = json.loads(path.read_text(encoding='utf-8'))
        seat = row['seat']
        mismatch, elapsed = [], []
        for step in range(144):
            obs = deepcopy(replay['steps'][step][seat]['observation'])
            obs['step'] = step
            before = deepcopy(obs)
            expected = reference(obs, replay['configuration'])
            assert obs == before, ('reference mutated observation', row['episode'], seat, step)
            then = time.perf_counter()
            actual = compact(obs, replay['configuration'])
            elapsed.append(time.perf_counter() - then)
            assert obs == before, ('compact mutated observation', row['episode'], seat, step)
            if actual != expected:
                mismatch.append(dict(step=step, expected=expected, actual=actual))
        checked += 144
        cases.append(dict(episode=row['episode'], seat=seat, comparisons=144, mismatches=mismatch,
            max_action_seconds=max(elapsed), mean_action_seconds=sum(elapsed) / len(elapsed)))
    try:
        compact({'step': 144})
    except ValueError:
        rejects_day6 = True
    else:
        rejects_day6 = False
    immutable_after = hashlib.sha256(json.dumps(_contracts(CONTRACTS)['library'], sort_keys=True).encode()).hexdigest()
    report = dict(source_contract_sha256=hashlib.sha256(CONTRACTS.read_bytes()).hexdigest(),
        cases=cases, comparisons=checked, mismatches=sum(len(x['mismatches']) for x in cases),
        cold_initialization_seconds=init, rejects_day6=rejects_day6,
        shared_contract_unchanged=immutable_before == immutable_after, games_executed=0)
    OUT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}))
    assert checked and report['mismatches'] == 0 and rejects_day6 and immutable_before == immutable_after


if __name__ == '__main__':
    main()

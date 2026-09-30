"""Audit complete fresh scout results and write compact reviewable metrics."""
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/value_tape_ranker_20260923'


def summarize(rows):
    values = [r['margin_delta'] for r in rows]
    return dict(matchups=len(rows), worlds=len({r['spec']['seed'] for r in rows}),
        improved=sum(v>0 for v in values), unchanged=sum(v==0 for v in values), worse=sum(v<0 for v in values),
        mean_margin=statistics.mean(values), total_margin=sum(values),
        mean_own_cash=statistics.mean(r['cash_delta'] for r in rows),
        mean_rival_cash=statistics.mean(r['rival_delta'] for r in rows),
        native_wins=sum(r['baseline']['margin']>0 for r in rows),
        scout_wins=sum(r['candidate']['margin']>0 for r in rows),
        exact_wins=sum(r['exact']['margin']>0 for r in rows),
        same_as_exact_games=sum(r['candidate']['actions_sha256']==r['exact']['actions_sha256'] for r in rows),
        multiple_commitments=sum(sum(d['selected'] is not None for d in r['candidate']['decisions'])>1 for r in rows))


def main():
    folder = OUT / 'fresh_scout'
    design = json.loads((folder / 'design.json').read_text(encoding='utf-8'))
    assert all(sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in design['hashes'].items())
    rows = [json.loads((folder / f"{s['id']}.json").read_text(encoding='utf-8')) for s in design['specs']]
    for spec, row in zip(design['specs'], rows):
        assert row['completed'] and row['spec'] == spec
        assert len({row[p]['prefix_sha256'] for p in ('candidate', 'exact', 'baseline')}) == 1
        for policy in ('candidate', 'exact', 'baseline'):
            game = row[policy]
            assert game['completed'] and game['ledger_verified']
            for seat, cash in ((spec['seat'], game['cash']), (1-spec['seat'], game['rival_cash'])):
                e = game['economics'][seat]
                assert 3000+sum(e['revenue'].values())-sum(e['spend'].values()) == cash
        assert row['versus_exact'] == row['candidate']['margin']-row['exact']['margin']
    shadows = [s for r in rows for s in r['shadows']]
    scout_turns = sum(s['scout']['simulated_turns'] for s in shadows)
    exact_turns = sum(s['exact']['simulated_turns'] for s in shadows)
    changes = []
    for r in rows:
        if any(d['selected'] is not None for d in r['candidate']['decisions']):
            changes.append(dict(id=r['spec']['id'], seed=r['spec']['seed'],
                commitments=[dict(day=d['day'], route=d['selected'], episode=d['selected_episode'],
                    retains_incumbent=d['selected']==d['candidates'][1]['route'],
                    same_as_native_reveal_tape=d['selected_episode']==d['candidates'][0]['episode'])
                    for d in r['candidate']['decisions'] if d['selected'] is not None],
                margin_delta=r['margin_delta'], own_cash_delta=r['cash_delta'], rival_cash_delta=r['rival_delta'],
                before=r['baseline']['margin'], after=r['candidate']['margin'], versus_exact=r['versus_exact']))
    timing = json.loads((OUT / 'paired_scout_timing.json').read_text(encoding='utf-8'))
    paired = []
    for row in timing['rows']:
        by = {r['planner']:r for r in row['records']}
        old, new = by['value_tape_search_v7'], by['value_tape_search_v8']
        paired.append(dict(id=row['id'], exact_seconds=old['wall'], scout_seconds=new['wall'],
            wall_reduction=1-new['wall']/old['wall'], cpu_reduction=1-new['cpu']/old['cpu'],
            matched_forecasts=row['forecasts_compared'], selection_equal=old['selected']==new['selected']))
    result = dict(all=summarize(rows), by_opponent={name:summarize([r for r in rows if r['spec']['opponent']==name])
        for name in sorted({r['spec']['opponent'] for r in rows})}, changed_games=changes,
        search=dict(decisions=len(shadows), selection_equal=sum(s['equal'] for s in shadows),
            exact_turns=exact_turns, scout_turns=scout_turns, turn_reduction=1-scout_turns/exact_turns,
            exact_rollouts=sum(s['exact']['rollouts'] for s in shadows),
            scout_rollouts=sum(s['scout']['rollouts'] for s in shadows),
            scout_median_wall=statistics.median(s['scout']['seconds'] for s in shadows),
            scout_max_wall=max(s['scout']['seconds'] for s in shadows),
            scout_min_wall=min(s['scout']['seconds'] for s in shadows),
            budget_enforced=False), paired_uncached_timings=paired,
        exact_source_hashes_verified=True, complete_games=len(rows)*3, all_cash_ledgers_verified=True,
        caveats=['Six independent new demand worlds; opponents/dates within a world are correlated.',
            'The static learned ranker is experimental and is not used by V8.',
            'Candidate search is approximate; exact physical forecasts still use a modeled rival and sampled future shops.',
            'Shadow reference decisions reuse identical forecasts; compare work counts, not cached shadow wall time.',
            'No competition-time readiness claim; 1s action / 12s total overage remains the deployment gate.'])
    (OUT / 'final_metrics.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

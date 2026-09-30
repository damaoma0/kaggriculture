"""Summarize frozen paired opening games; resample whole worlds for intervals."""
from collections import defaultdict
import argparse
import json
from pathlib import Path
import random
import statistics as S

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/fresh/coherent_opening_20260924_01a0'


def interval(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row['world']].append(row[key])
    means = [S.mean(v) for v in groups.values()]
    if len(means)<2:
        return None
    rng = random.Random(831737)
    bootstrap = sorted(S.mean(rng.choices(means, k=len(means))) for _ in range(4000))
    return [bootstrap[100], bootstrap[3899]]


def summarize(folder):
    games = [json.loads(p.read_text()) for p in sorted((folder/'games').glob('*.json'))]
    failures = [{'id':g['spec']['id'],'arm':g['arm'],'error':g['error']} for g in games if not g['completed']]
    completed = [g for g in games if g['completed']]
    by_key = {(g['spec']['id'],g['arm']):g for g in completed}
    arms = sorted({g['arm'] for g in completed})
    comparisons = {}
    pairs = []
    for reference in ['baseline','dsm','normalized']:
        for arm in arms:
            if arm == reference: continue
            rows = []
            for game in completed:
                if game['arm'] != arm: continue
                baseline = by_key.get((game['spec']['id'],reference))
                if baseline is None: continue
                seat = game['spec']['seat']
                delta = game['cash'][seat]-baseline['cash'][seat]
                margin = game['cash'][seat]-game['cash'][1-seat]
                old_margin = baseline['cash'][seat]-baseline['cash'][1-seat]
                row = dict(id=game['spec']['id'],world=game['spec']['world']['id'],opponent=game['spec']['opponent'],
                    first_shop=game['spec']['world']['first_shop'],reference=reference,arm=arm,
                    cash_delta=delta,margin_delta=margin-old_margin,cash=game['cash'][seat],margin=margin,
                    baseline_cash=baseline['cash'][seat],baseline_margin=old_margin)
                rows.append(row)
            if not rows: continue
            pairs.extend(rows)
            comparisons[f'{arm}_vs_{reference}'] = dict(n=len(rows),worlds=len({r['world'] for r in rows}),
                mean_cash_delta=S.mean(r['cash_delta'] for r in rows),median_cash_delta=S.median(r['cash_delta'] for r in rows),
                mean_margin_delta=S.mean(r['margin_delta'] for r in rows),cash_ci95_world_bootstrap=interval(rows,'cash_delta'),
                margin_ci95_world_bootstrap=interval(rows,'margin_delta'),
                better=sum(r['cash_delta']>0 for r in rows),same=sum(r['cash_delta']==0 for r in rows),worse=sum(r['cash_delta']<0 for r in rows),
                wins=sum(r['margin']>0 for r in rows),reference_wins=sum(r['baseline_margin']>0 for r in rows),
                worst=min(rows,key=lambda r:r['cash_delta']),best=max(rows,key=lambda r:r['cash_delta']),
                opponents={op:dict(n=sum(r['opponent']==op for r in rows),
                    cash_delta=S.mean(r['cash_delta'] for r in rows if r['opponent']==op),
                    margin_delta=S.mean(r['margin_delta'] for r in rows if r['opponent']==op))
                    for op in {r['opponent'] for r in rows}})
    runtime = {arm:dict(games=sum(g['arm']==arm for g in completed),
        mean_game_seconds=S.mean(g['seconds'] for g in completed if g['arm']==arm),
        max_action_seconds=max(g['max_action_seconds'][g['spec']['seat']] for g in completed if g['arm']==arm)) for arm in arms}
    summary = dict(completed=len(completed),failures=failures,comparisons=comparisons,runtime=runtime,
                   caution='Development is used for tuning. World bootstrap groups both opponents; small-panel intervals are exploratory.')
    (folder/'summary.json').write_text(json.dumps(summary,indent=2))
    (folder/'paired.json').write_text(json.dumps(pairs,indent=2))
    return summary


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--phase',default='development')
    ap.add_argument('--revision',default='v1')
    args=ap.parse_args()
    result=summarize(OUT/args.phase/args.revision)
    print(json.dumps(result,indent=2))

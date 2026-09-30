"""Episode-held-out daily quantity diagnostic; no games or gate cases are run.

Archived traces contain the exact public own farm and own private stock but no
market/rival snapshot. Raw retrieval fidelity is measured without those fields;
the executable policy is assessed under an explicit neutral-market sensitivity,
not represented as its predictions under the original unrecorded market state.
"""
from collections import Counter,defaultdict
from copy import deepcopy
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import time

from semantic_strategy_policy_20260928 import (SemanticStrategyPolicy, public_state,
    row_distance, _MARKET, CROPS, ANIMALS, PRODUCTS)

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'
SPECIES=tuple(CROPS)+tuple(ANIMALS)


def quantities(x):
    return dict((s,int(x.get('plant_counts' if s in CROPS else 'animal_add_counts',{}).get(s,0))) for s in SPECIES)


def summarize(rows):
    out={}
    for variant in sorted(set(r['variant'] for r in rows)):
        items=[r for r in rows if r['variant']==variant]
        groups={'all':items,'D6':[r for r in items if r['day']==6],
                'D9':[r for r in items if r['day']==9],
                'D6_11':[r for r in items if 6<=r['day']<=11],
                'D12_18':[r for r in items if 12<=r['day']<=18],
                'D19_27':[r for r in items if 19<=r['day']<=27]}
        out[variant]={}
        for name,g in groups.items():
            n=len(g)
            out[variant][name]=dict(rows=n,
                quantity_mae=sum(abs(r['predicted'][s]-r['actual'][s]) for r in g for s in SPECIES)/(n*len(SPECIES)),
                by_species={s:dict(actual=sum(r['actual'][s] for r in g),predicted=sum(r['predicted'][s] for r in g),
                    mean_bias=sum(r['predicted'][s]-r['actual'][s] for r in g)/n,
                    mae=sum(abs(r['predicted'][s]-r['actual'][s]) for r in g)/n) for s in SPECIES},
                land_actual=sum(r['actual_land_add'] for r in g),land_predicted=sum(r['predicted_land_add'] for r in g),
                land_exact=sum(r['actual_land_add']==r['predicted_land_add'] for r in g),
                hands_actual=sum(r['actual_hands'] for r in g)/n,hands_predicted=sum(r['predicted_hands'] for r in g)/n,
                hands_above=sum(r['predicted_hands']>r['actual_hands'] for r in g),
                hands_below=sum(r['predicted_hands']<r['actual_hands'] for r in g),
                fraction_at_14=sum(r['predicted_hands']==14 for r in g)/n)
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',default='results/fresh/semantic_strategy_20260928/fidelity_diagnostic')
    args=ap.parse_args()
    started=time.perf_counter();source=STUDY/'causal_daily_rows.json';model=json.loads(source.read_text())
    ids=sorted(set(int(r['meta']['episode']) for r in model['rows']),
               key=lambda e:hashlib.sha256(('fidelity-20260928:'+str(e)).encode()).hexdigest())
    held=set(ids[:20]);train=[r for r in model['rows'] if int(r['meta']['episode']) not in held]
    test=[r for r in model['rows'] if int(r['meta']['episode']) in held]
    policies={
        'policy_neutral_market':SemanticStrategyPolicy({'rows':train},{'forecast':False}),
        'no_economics_neutral_market':SemanticStrategyPolicy({'rows':train},{'forecast':False,'economics_weight':0}),
    }
    tracecache={};records=[];nearest_only=[];cashclips=[];rankswaps=[]
    for r in test:
        path=ROOT/r['meta']['source']
        if str(path) not in tracecache:
            trace=json.load(gzip.open(path,'rt',encoding='utf-8'))
            tracecache[str(path)]={int(x['day']):x for x in trace['daily']}
        actual_state=tracecache[str(path)][r['day']]
        rival=dict(tiles=[[None]*10 for _ in range(10)],money=0,unlocked_quadrants=['NW'],hands=[],farmer=[4,4])
        obs=dict(day=r['day'],hour=0,step=24*r['day'],player=0,
            farms=[deepcopy(actual_state['farm']),rival],private=deepcopy(actual_state['private']),
            town={'unlocked_shops':list(actual_state['shops'])},
            market={'prices':{p:_MARKET[p][0] for p in PRODUCTS},'inventory':{p:10000 for p in PRODUCTS}})
        state=public_state(obs);policy=policies['policy_neutral_market'];pool=policy.byday[r['day']]
        best_i=min(range(len(pool)),key=lambda i:(row_distance(state,pool[i],policy.config),i))
        raw=pool[best_i]['target'];outputs={}
        for name,pol in policies.items():
            outputs[name]=pol.propose(obs)
        rich=deepcopy(obs);rich['farms'][0]['money']=1e9
        outputs['cash_unconstrained_neutral_market']=policy.propose(rich)
        calendar=dict(plant_counts={},animal_add_counts={},hands=int(statistics.median(x['target']['hands'] for x in pool)),
                      land_add_count=int(statistics.median(x['target']['land_add_count'] for x in pool)))
        for sp in SPECIES:
            field='plant_counts' if sp in CROPS else 'animal_add_counts'
            calendar[field][sp]=int(math.floor(statistics.median(x['target'].get(field,{}).get(sp,0) for x in pool)+.5))
        outputs['calendar_median']={'today':calendar,'diagnostics':{}}
        outputs['raw_nearest_joint_counts']={'today':raw,'diagnostics':{'row_index':best_i}}
        actual=quantities(r['target'])
        for name,out in outputs.items():
            p=out['today'];records.append(dict(episode=int(r['meta']['episode']),seat=r['meta']['seat'],day=r['day'],variant=name,
                actual=actual,predicted=quantities(p),actual_land_add=r['target']['land_add_count'],
                predicted_land_add=p['land_add_count'],actual_hands=r['target']['hands'],predicted_hands=p['hands'],
                neighbor_row=out['diagnostics'].get('row_index'),cash=state['cash']))
        n=outputs['policy_neutral_market'];u=outputs['cash_unconstrained_neutral_market']
        if quantities(n['today'])!=quantities(u['today']):
            cashclips.append(dict(episode=r['meta']['episode'],day=r['day'],cash=state['cash'],
                predicted=quantities(n['today']),unconstrained=quantities(u['today']),actual=actual,
                predicted_land_add=n['today']['land_add_count']))
        if n['diagnostics']['row_index']!=best_i:
            rankswaps.append(dict(episode=r['meta']['episode'],day=r['day'],nearest=best_i,chosen=n['diagnostics']['row_index'],
                chosen_distance=n['diagnostics']['distance'],nearest_distance=row_distance(state,pool[best_i],policy.config)))
    summary=summarize(records)
    out=dict(schema=1,purpose='within-training episode-held-out imitation diagnostic; not gameplay validation',
        feature_limitations=['Market and rival snapshots absent: executable-policy rows use base prices, inventory10000 and empty rival farm.',
                            'Cash-unconstrained is a diagnostic intervention, not an executable policy.',
                            'No competition gate episode or future target-world shop/outcome is evaluated.'],
        split=dict(method='first20 unique episodes sorted by SHA256(fidelity-20260928:episode), before outcomes',
                   heldout_episodes=sorted(held),training_episodes=sorted(set(ids)-held),heldout_rows=len(test),training_rows=len(train)),
        source_model_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        policy_sha256=hashlib.sha256((ROOT/'scripts/semantic_strategy_policy_20260928.py').read_bytes()).hexdigest(),
        elapsed_seconds=time.perf_counter()-started,summary=summary,cash_sensitive_rows=cashclips,economic_neighbor_swaps=rankswaps,rows=records)
    destination=ROOT/args.out;destination.mkdir(parents=True,exist_ok=True)
    (destination/'report.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    lines=['# Causal strategy quantity fidelity diagnostic','',
        'Twenty whole training episodes were held out before fitting. No gate games were evaluated. '
        'This measures quantity imitation, not competitive strength. Market and rival snapshots are absent in the archives: '
        'policy predictions below use base prices, market inventory 10,000, and an empty rival farm. Raw nearest-neighbor '
        'quantity retrieval does not require those substituted fields.','',
        '| Variant | MAE per species/day | D6 strawberry bias | D6 cow bias | D9 strawberry bias | Late wheat bias | Hands mean |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for name,s in summary.items():
        lines.append('| '+name+' | '+' | '.join(f'{x:.3f}' for x in [s['all']['quantity_mae'],s['D6']['by_species']['STRAWBERRY']['mean_bias'],
            s['D6']['by_species']['COW']['mean_bias'],s['D9']['by_species']['STRAWBERRY']['mean_bias'],
            s['D19_27']['by_species']['WHEAT']['mean_bias'],s['all']['hands_predicted']])+' |')
    lines += ['',f'Cash-sensitive decisions: {len(cashclips)}/{len(test)}. Economics chose a different neighbor from pure distance in {len(rankswaps)}/{len(test)} decisions.',
              '',f'Model SHA256: `{out["source_model_sha256"]}`. Policy SHA256: `{out["policy_sha256"]}`.',
              '', 'The full JSON contains species/window totals, land accuracy, hand-count errors, and each prediction. '
              'All figures are development diagnostics under the stated missing-feature assumptions.']
    (destination/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(path=str(destination),elapsed=out['elapsed_seconds'],heldout_rows=len(test),cash_sensitive=len(cashclips),economic_swaps=len(rankswaps),
        mae={k:v['all']['quantity_mae'] for k,v in summary.items()}),indent=2))


if __name__=='__main__':main()

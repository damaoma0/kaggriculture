"""Summarize every predeclared plan case and assign cohorts to concrete tiles."""
from collections import Counter,defaultdict
import json
import argparse
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,o):p.write_text(json.dumps(o,indent=2),encoding='utf-8')
def materialize(case,mode):
    from cumulative_plan_solver import _profile_candidates
    snapshot=case['snapshot'];start=case['day'];end=30
    candidates={x['name']:x for x in _profile_candidates(dict(snapshot,require_primary_animal_output=False))}
    existing=[];available={}
    for y,row in enumerate(snapshot['tiles']):
        for x,t in enumerate(row):
            if t is None:available[(x,y)]=start
            elif isinstance(t,dict) and (t.get('crop') or t.get('animal')):
                existing.append((x,y));available[(x,y)]=end
    rows=[];new=[]
    for sel in case['modes'][mode]['selections']:
        r=candidates[sel['decision']];release=max(r['land'],default=start-1)+1
        if r['existing']:
            tile=existing[r['existing_group']];available[tile]=release
            rows.append(dict(decision=r['name'],tile=list(tile),from_day=start,reuse_day=release,
                current_asset=True,outputs=r['outputs'],work=r['work'],inputs=r['inputs']))
        else:
            for _ in range(sel['quantity']):new.append(r)
    for r in sorted(new,key=lambda x:(min(x['land']),x['name'])):
        d=min(r['land']);options=[tile for tile,free in available.items() if free<=d]
        assert options,('aggregate schedule not interval-colorable',case['episode'],mode,d)
        tile=min(options,key=lambda t:(abs(t[0]-4)+abs(t[1]-4),t))
        release=max(r['land'])+1;available[tile]=release
        rows.append(dict(decision=r['name'],tile=list(tile),from_day=d,reuse_day=release,current_asset=False,
                         outputs=r['outputs'],work=r['work'],inputs=r['inputs']))
    return dict(episode=case['episode'],day=start,mode=mode,assignments=rows,
        note='Coordinates assign the aggregate cohorts without tile overlap. Reserve-until dates are conservative. Worker visits, cargo transfer, future weeds and market execution are not solved.')
def main(guarded=False):
    case_dir='cases_guarded' if guarded else 'cases';suffix='_guarded' if guarded else ''
    protocol=read(OUT/'plans/protocol.json');cases=[read(OUT/f'plans/{case_dir}/{e}-d{d}.json') for e in protocol['episodes'] for d in protocol['days']]
    table=[];errors=[];materialized=0
    for day in protocol['days']:
        for mode in protocol['modes']:
            selected=[c['modes'][mode] for c in cases if c['day']==day]
            okay=[x for x in selected if 'error' not in x]
            table.append(dict(day=day,mode=mode,n=len(selected),solved=len(okay),optimal=sum(x['solver']['optimal'] for x in okay),
                exact_targets=sum(x['aggregate_feasible'] for x in okay),
                mean_timed_mae_to_forecast=float(np.mean([x['all_target_mae_to_forecast'] for x in okay])),
                mean_timed_mae_to_realized=float(np.mean([x['all_target_mae_to_realized'] for x in okay])),
                mean_end_mae_to_forecast=float(np.mean([abs(t['plan']-t['forecast']) for x in okay for t in x['evaluation_full_timed_targets'] if t['day']==30])),
                mean_solve_seconds=float(np.mean([x['elapsed_seconds'] for x in okay]))))
    for case in cases:
        for mode in protocol['modes']:
            if 'error' in case['modes'][mode]:errors.append(dict(episode=case['episode'],day=case['day'],mode=mode,error=case['modes'][mode]['error']));continue
            assignment=materialize(case,mode);materialized+=1
            if case['episode']==protocol['episodes'][0] and case['day']==12 and mode=='forecast_timed':
                save(OUT/f'plans/example_tile_plan{suffix}.json',assignment)
                save(OUT/f'plans/example_plan{suffix}.json',case)
    pair=[]
    for c in cases:
        a=c['modes']['forecast_end_only'];b=c['modes']['forecast_timed']
        if 'error' in a or 'error' in b:continue
        pair.append(dict(episode=c['episode'],day=c['day'],end_only=a['all_target_mae_to_forecast'],timed=b['all_target_mae_to_forecast']))
    by_episode=defaultdict(list)
    for r in pair:by_episode[r['episode']].append([r['end_only'],r['timed']])
    v=np.array([np.mean(x,axis=0) for x in by_episode.values()]);rng=np.random.default_rng(20260925)
    sampled=v[rng.integers(0,len(v),(5000,len(v)))].mean(1)
    reduction=1-v[:,1].mean()/v[:,0].mean();ci=np.quantile(1-sampled[:,1]/sampled[:,0],[.025,.975])
    summary=dict(cases=len(cases),plan_variants=len(cases)*len(protocol['modes']),table=table,errors=errors,
        tile_assignments_checked=materialized,paired_timed_target_error_reduction=float(reduction),episode_bootstrap95_reduction=ci.tolist(),
        interpretation='These errors measure schedule fidelity to production targets under the aggregate model; they are not economic profit or leaderboard performance.')
    save(OUT/f'plans/summary{suffix}.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--guarded',action='store_true');a=p.parse_args();main(a.guarded)

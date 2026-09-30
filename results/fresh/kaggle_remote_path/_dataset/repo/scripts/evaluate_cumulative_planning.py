"""Frozen diagnostic protocol for forecast -> whole-farm aggregate plans.

Run --freeze before looking at test forecasts. Actual compilation is performed
after the engine-validated planner interface is ready. This study does not run
a live strategy or use later shops to formulate forecast plans.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=2),encoding='utf-8')
def freeze():
    dest=OUT/'plans/protocol.json'
    if dest.exists():raise SystemExit('Protocol already frozen; will not overwrite')
    m=read(OUT/'data_manifest.json')
    ids=[g['episode'] for g in m['games'] if g['split']=='test'][:10]
    save(dest,dict(schema_version=1,episodes=ids,days=[12,18,24],
        selection='First ten test episodes in the existing outcome-independent frozen manifest; every listed episode at all three days.',
        manifest_sha256=sha256((OUT/'data_manifest.json').read_bytes()).hexdigest(),
        modes=['forecast_end_only','forecast_timed','realized_timed_oracle'],
        funding='Starting cash only; no credit for future sales. Static seed/animal prices; feed/fertilizer valued at checkpoint prices, conditional on those procurement prices.',
        hires_per_day=11,travel_fraction=0.30,animal_addition_cap_each=2,
        max_seconds_per_solve=5,
        assets='Preserve current productive animals; preserve current crops to the engine-profile release. Reclaim only legal free or explicitly cleaned tiles.',
        targets='Nine actual harvested/collected products; cumulative remaining output up to exclusive horizon next3,next6,end. Compare end-only and timed forecast against the SAME full timed forecast vector; realized oracle is labelled hindsight.',
        interpretation='Diagnostic aggregate resource/target projection only. No path/worker/cargo execution proof or profit claim. Infeasible targets report deviations. Solver timeouts reported.'))
    print('frozen',len(ids)*3,'checkpoints, three target modes')

def prepare_targets(trajectory):
    by_day={}
    for r in trajectory['horizons']:by_day[r['end_day']]=r['remaining']
    return [{'day':day,'product':p,'units':int(round(units))} for day,vector in by_day.items() for p,units in vector.items()]

def evaluate_job(job):
    from cumulative_trajectory_model import load,predict_trajectory
    from cumulative_plan_solver import checkpoint_to_snapshot,solve,ENGINE
    game,day,protocol=job;checkpoint=game['checkpoints'][str(day)]
    snapshot=checkpoint_to_snapshot(checkpoint)
    snapshot.update(hire_schedule={str(d):protocol['hires_per_day'] for d in range(day,30)},
        require_primary_animal_output=protocol.get('case_dir')=='cases_guarded',
        travel_fraction=protocol['travel_fraction'],animal_purchase_budget={a:protocol['animal_addition_cap_each'] for a in ENGINE.ANIMALS},
        seed_purchase_budget={p:1000 for p in ENGINE.CROPS},feed_purchase_budget=1000,fertilizer_budget=1000,
        resource_prices=checkpoint['observation']['market']['prices'],solver_time_limit=protocol['max_seconds_per_solve'],
        farm_hand_cost_mult=game['configuration'].get('farmHandCostMult',1))
    targets=prepare_targets(predict_trajectory(load(),checkpoint))
    oracle=[]
    for t in targets:
        q=dict(t);q['units']=sum(s['output'][q['product']] for s in game['segments'] if day<=s['days'][0]<t['day']);oracle.append(q)
    result=dict(episode=game['episode'],seat=game['seat'],day=day,snapshot=snapshot,forecast_targets=targets,realized_targets=oracle,modes={})
    for mode in protocol['modes']:
        requested=oracle if mode=='realized_timed_oracle' else [t for t in targets if mode!='forecast_end_only' or t['day']==30]
        start_time=time.monotonic()
        try:
            plan=solve(snapshot,requested)
            # Evaluate every mode at the same forecast deadlines, independent
            # of the subset optimized by the end-only ablation.
            full=[]
            for t,o in zip(targets,oracle):
                value=sum(r['expected_output'].get(t['product'],0) for d,r in plan['daily'].items() if int(d)<t['day'])
                full.append(dict(day=t['day'],product=t['product'],plan=value,forecast=t['units'],realized=o['units']))
            plan['evaluation_full_timed_targets']=full
            plan['all_target_mae_to_forecast']=sum(abs(r['plan']-r['forecast']) for r in full)/len(full)
            plan['all_target_mae_to_realized']=sum(abs(r['plan']-r['realized']) for r in full)/len(full)
            result['modes'][mode]=plan
        except Exception as e:result['modes'][mode]={'error':str(e)}
        result['modes'][mode]['elapsed_seconds']=time.monotonic()-start_time
    dest=OUT/f"plans/{protocol.get('case_dir','cases')}/{game['episode']}-d{day}.json";save(dest,result)
    return game['episode'],day,{k:v.get('solver',{}).get('status',v.get('error')) for k,v in result['modes'].items()}

def run(guarded=False):
    protocol=read(OUT/'plans/protocol.json');data=read(OUT/'dataset_test.json')
    if guarded:protocol['case_dir']='cases_guarded'
    chosen={g['episode']:g for g in data['games']}
    case_dir=protocol.get('case_dir','cases')
    jobs=[(chosen[e],d,protocol) for e in protocol['episodes'] for d in protocol['days'] if not (OUT/f'plans/{case_dir}/{e}-d{d}.json').exists()]
    save(OUT/f'plans/implementation_manifest_{case_dir}.json',dict(protocol_sha256=sha256((OUT/'plans/protocol.json').read_bytes()).hexdigest(),
        source_sha256={p:sha256((ROOT/'scripts'/p).read_bytes()).hexdigest() for p in ['cumulative_plan_solver.py','cumulative_engine_profiles.py','cumulative_trajectory_model.py']},
        target_generator='Frozen trained_model.json; no held-out outcome fitting',model_sha256=sha256((OUT/'forecast/trained_model.json').read_bytes()).hexdigest(),
        quantity_cap_rule='Seed/feed/fertilizer procurement caps each1000; actual buys constrained by starting cash and usage. They are not free resources.',
        refinement='Guarded run excludes new animals that cannot harvest their main product by season end. Added after diagnostic exposed late fertilizer-only animal purchase; this is a post-analysis planning diagnostic, not another sealed forecast test.' if guarded else None))
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(evaluate_job,j) for j in jobs]):print('case',f.result(),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--run',action='store_true');p.add_argument('--guarded',action='store_true');a=p.parse_args()
    if a.freeze:freeze()
    if a.run:run(a.guarded)

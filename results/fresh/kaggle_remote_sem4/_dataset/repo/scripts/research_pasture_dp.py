"""Paired species continuations, then a frozen full-policy held-out test."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from importlib.metadata import version
from copy import deepcopy
import argparse,json,sys,time,random
from market_corpus import ROOT,PATHS,load
from audit_router_advantage import OUT
from evaluate_boards import Ledger


def run(job,phase):
    seed,seat,opponent,mode=job
    sys.path.insert(0,str(ROOT/'agents'))
    policy_path=ROOT/'agents'/('pasture_investment_v1.py' if phase=='train' else 'pasture_investment_dp.py')
    PasturePolicy=load('pasture_policy',policy_path).PasturePolicy
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    own=load('pasture_own',PATHS['sixday']);opp=load('pasture_opp',PATHS[opponent])
    policy=PasturePolicy(own,'dp' if mode=='current' else mode,'current' if mode=='current' else 'visible')
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720});initial=[f.money for f in env.state[0].observation.farms]
    original_end=E._end_of_day
    if phase=='shops':
        schedule=random.Random(seed^0x4A27F).choices(sorted(E.SHOPS),k=8)
        schedule[0]=sorted(E.SHOPS)[seed-113000]
        def controlled_end(state,environment,day):
            original_end(state,environment,day)
            town=state[0].observation.town
            town.unlocked_shops[:]=schedule[:len(town.unlocked_shops)]
        E._end_of_day=controlled_end
    snapshots=[];elapsed=[];branches=[]
    def act(o):
        t=time.perf_counter();a=policy.act(o);elapsed.append(time.perf_counter()-t)
        if o['step']%144==0:branches.append([o['step'],own._SESSIONS[seat][1]])
        if policy.target is not None and o['step']%24==0:
            x,y=policy.target;snapshots.append({'step':o['step'],'tile':deepcopy(o['farms'][seat]['tiles'][y][x])})
        return a
    def other(o):return opp.agent(o)
    agents=[None,None];agents[seat]=act;agents[1-seat]=other
    start=time.perf_counter()
    try:
        with Ledger(E) as ledger:env.run(agents)
    finally:E._end_of_day=original_end
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    actions=[ss[seat].action for ss in env.steps[1:]]
    decision=policy.decision
    placement_failed=bool(decision and policy.target is None)
    if placement_failed:
        (OUT/phase/f'failed-replay-{seed}-{seat}-{opponent}-{mode}.json').write_text(json.dumps(env.toJSON()))
    row={'seed':seed,'seat':seat,'opponent':opponent,'mode':mode,'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
      'ledger':ledger.data,'decision':decision,'stats':dict(policy.stats),'target':policy.target,'snapshots':snapshots,'placement_failed':placement_failed,
      'max_action_seconds':max(elapsed),'seconds':time.perf_counter()-start,'branches':branches,
      'shops':env.state[0].observation.town.unlocked_shops,
      'predecision_hash':sha256(json.dumps(actions[:decision['step']] if decision else actions,sort_keys=True).encode()).hexdigest()}
    (OUT/phase/f'{seed}-{seat}-{opponent}-{mode}.json').write_text(json.dumps(row,indent=2))
    return {k:row[k] for k in ('seed','seat','opponent','mode','cash','max_action_seconds')}|{'selected':decision['selected'] if decision else None}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['train','validate','test','shops'],required=True);ap.add_argument('--manifest-only',action='store_true');args=ap.parse_args()
    phase=args.phase;(OUT/phase).mkdir(parents=True,exist_ok=True)
    seeds=list(range(111000,111004)) if phase in ('train','validate') else list(range(112000,112006)) if phase=='test' else list(range(113000,113008))
    modes=['original','cow','sheep'] if phase=='train' else ['original','cow','sheep','dp'] if phase=='validate' else ['original',json.loads((OUT/'selection.json').read_text())['fixed_species']] if phase=='shops' else ['raw','original','current','dp',json.loads((OUT/'selection.json').read_text())['fixed_species']]
    opponents=['old'] if phase in ('train','validate') else ['sixday','pasture']
    manifest={'phase':phase,'seeds':seeds,'modes':modes,'opponents':opponents,'engine':version('kaggle-environments'),
      'policy_sha':sha256((ROOT/'agents'/('pasture_investment_v1.py' if phase=='train' else 'pasture_investment_dp.py')).read_bytes()).hexdigest(),
      'forecast_sha':sha256((ROOT/'agents/market_forecast.py').read_bytes()).hexdigest(),
      'sources':{k:sha256(v.read_bytes()).hexdigest() for k,v in PATHS.items()},
      'scope':'First unambiguous single pasture purchase during turns144..288; fixed movement/service route. Milk/wool liquidation adapter common to all non-raw candidates.'}
    if phase=='shops':manifest['shop_control']='First shop stratified across all eight types in sorted order; remaining draws sampled with Random(seed XOR 0x4A27F). Only revealed shops visible to policies. Natural weed evolution retained.'
    mp=OUT/f'{phase}_manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==manifest,'Frozen experiment changed'
    else:mp.write_text(json.dumps(manifest,indent=2))
    if args.manifest_only:return
    jobs=[(s,i,o,m) for s in seeds for i in (0,1) for o in opponents for m in modes]
    pending=[j for j in jobs if not (OUT/phase/('{}-{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        futures={pool.submit(run,j,phase):j for j in pending}
        for f in as_completed(futures):
            try:print(f.result(),flush=True)
            except Exception:print('FAILED',futures[f],flush=True);raise
    rows=[json.loads((OUT/phase/('{}-{}-{}-{}.json'.format(*j))).read_text()) for j in jobs]
    (OUT/f'{phase}_results.json').write_text(json.dumps(rows,indent=2));print('COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()

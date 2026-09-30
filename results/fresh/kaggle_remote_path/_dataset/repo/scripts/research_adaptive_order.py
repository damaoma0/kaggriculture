"""Frozen matched full-season tests of causal product-ordering heuristics."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from importlib.metadata import version
import argparse,json,random,sys,time
from copy import deepcopy
from market_corpus import ROOT,PATHS,load
from evaluate_boards import Ledger

OUT=ROOT/'results/fresh/adaptive_order'
BASE=ROOT/'agents/market_priority_selected.py'
OPPONENTS=['sixday','pasture','prompt','priority','stockpiler']


def run(job,phase):
    seed,seat,opponent,mode=job
    sys.path.insert(0,str(ROOT/'agents'))
    from adaptive_market_order import AdaptiveOrder
    from opponent_sales import Stockpiler
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    reference=load('adaptive_own',BASE)
    class RecordingBase:
        def agent(self,obs):
            action=reference.agent(obs);self.last=deepcopy(action);return action
    recorder=RecordingBase()
    if mode=='available':
        from available_market_order import AvailabilityOrder
        own=AvailabilityOrder(recorder)
    else:own=AdaptiveOrder(recorder,mode)
    packaged=None
    if phase=='confirmation' and mode==json.loads((OUT/'selection.json').read_text())['mode']:
        packaged=load('adaptive_packaged_confirmation',ROOT/'agents/adaptive_order_candidate.py')
    path=BASE if opponent=='priority' else ROOT/'agents/production_selected.py' if opponent in ('prompt','stockpiler') else PATHS[opponent]
    other=load('adaptive_other',path)
    if opponent=='stockpiler':other=Stockpiler(other)
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    initial=[f.money for f in env.state[0].observation.farms]
    original_end=E._end_of_day
    if phase=='shops':
        shops=random.Random(seed^0xA827).choices(sorted(E.SHOPS),k=8);shops[0]=sorted(E.SHOPS)[seed-125000]
        def end(state,environment,day):
            original_end(state,environment,day)
            revealed=state[0].observation.town.unlocked_shops;revealed[:]=shops[:len(revealed)]
        E._end_of_day=end
    elapsed=[];events=[];clock=[0]
    def act(o):
        clock[0]=o['step'];start=time.perf_counter();a=own.agent(o);elapsed.append(time.perf_counter()-start)
        before=recorder.last
        assert a['farmer']==before['farmer'] and a['hands']==before['hands']
        assert sorted(map(json.dumps,a['market']))==sorted(map(json.dumps,before['market']))
        assert all(a['market'][i]==order for i,order in enumerate(before['market']) if order[0]!='SELL')
        if o['step']<216:assert a==before
        if packaged is not None:
            actual=packaged.agent(o);assert actual==a,('Packaged action differs',seed,o['step'])
            return actual
        return a
    def rival(o):clock[0]=o['step'];return other.agent(o)
    agents=[None,None];agents[seat]=act;agents[1-seat]=rival
    try:
        with Ledger(E) as ledger:
            original_commit=E._commit_unit
            def commit(op,item,price,f,p,m,shed_capacity=100):
                ok=original_commit(op,item,price,f,p,m,shed_capacity)
                if ok and op in ('SELL','BUY_PRODUCT'):events.append([clock[0],ledger.seats[id(f)],item,1 if op=='SELL' else -1,price])
                return ok
            E._commit_unit=commit
            env.run(agents)
            E._commit_unit=original_commit
    finally:E._end_of_day=original_end
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    actions=[ss[seat].action for ss in env.steps[1:]]
    r={'seed':seed,'seat':seat,'opponent':opponent,'mode':mode,'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
       'ledger':ledger.data,'stats':dict(own.stats),'flow_stats':dict(own.flow.stats),'inferred':own.inferred,'events':events,
       'decisions':own.decisions,'max_action_seconds':max(elapsed),'shops':env.state[0].observation.town.unlocked_shops,
       'physical_hash':sha256(json.dumps([{k:a[k] for k in ('farmer','hands')} for a in actions],sort_keys=True).encode()).hexdigest(),
       'opening_hash':sha256(json.dumps(actions[:216],sort_keys=True).encode()).hexdigest(),'constraint_checks':len(actions),
       'packaged_parity_actions':len(actions) if packaged is not None else 0}
    (OUT/phase/('{}-{}-{}-{}.json'.format(*job))).write_text(json.dumps(r))
    return {k:r[k] for k in ('seed','seat','opponent','mode','cash','opponent_cash','stats')}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['discovery','shops','confirmation'],required=True);ap.add_argument('--workers',type=int,default=8);ap.add_argument('--availability',action='store_true');args=ap.parse_args();phase=args.phase
    (OUT/phase).mkdir(parents=True,exist_ok=True)
    seeds=list(range(124000,124004)) if phase=='discovery' else list(range(125000,125008)) if phase=='shops' else list(range(126000,126008))
    opponents=OPPONENTS if phase!='shops' else ['priority','stockpiler']
    modes=['fixed','static','clock','visible'] if phase!='confirmation' else ['fixed',json.loads((OUT/'selection.json').read_text())['mode']]
    if args.availability:assert phase!='confirmation';modes=['available']
    elif phase=='confirmation' and modes[-1]!='available':modes.append('available')
    sources=[BASE,ROOT/'agents/production_selected.py',ROOT/'agents/adaptive_market_order.py',ROOT/'agents/opponent_sales.py',ROOT/'agents/market_forecast.py',*PATHS.values()]
    if 'available' in modes:sources.append(ROOT/'agents/available_market_order.py')
    if phase=='confirmation':sources.append(ROOT/'agents/adaptive_order_candidate.py')
    manifest={'seeds':seeds,'opponents':opponents,'modes':modes,'engine':version('kaggle-environments'),
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sources},
      'scope':'Reorder existing SELL slots after turn 216; quantities and non-SELL positions unchanged. No holding.',
      'shop_control':phase=='shops'}
    suffix='_available' if args.availability else ''
    mp=OUT/(phase+suffix+'_manifest.json')
    if mp.exists():assert json.loads(mp.read_text())==manifest,'Frozen experiment changed'
    else:mp.write_text(json.dumps(manifest,indent=2))
    jobs=[(s,i,o,m) for s in seeds for i in (0,1) for o in opponents for m in modes]
    pending=[j for j in jobs if not (OUT/phase/('{}-{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        futures={pool.submit(run,j,phase):j for j in pending}
        for f in as_completed(futures):
            try:print(f.result(),flush=True)
            except Exception:print('FAILED',futures[f],flush=True);raise
    rows=[json.loads((OUT/phase/('{}-{}-{}-{}.json'.format(*j))).read_text()) for j in jobs]
    (OUT/(phase+suffix+'_results.json')).write_text(json.dumps(rows));print('COMPLETE',len(rows),flush=True)


if __name__=='__main__':main()

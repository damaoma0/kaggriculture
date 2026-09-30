"""Causal delivery-forecast corpus and frozen adversarial sales experiments."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from importlib.metadata import version
from collections import Counter
import argparse,json,random,sys,time
from market_corpus import ROOT,PATHS,load
from evaluate_boards import Ledger

OUT=ROOT/'results/fresh/opponent_sales'
BASE=ROOT/'agents/production_selected.py'

def run(job,phase,method):
    seed,seat,opponent,mode=job
    sys.path.insert(0,str(ROOT/'agents'))
    from opponent_sales import OpponentPolicy,Stockpiler,GOODS
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    own=OpponentPolicy(load('adversarial_own',BASE),mode,method)
    opp=load('adversarial_other',BASE if opponent in ('prompt','stockpiler') else PATHS[opponent])
    if opponent=='stockpiler':opp=Stockpiler(opp)
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720});initial=[f.money for f in env.state[0].observation.farms]
    original_end=E._end_of_day
    if phase=='shops':
        schedule=random.Random(seed^0xB723).choices(sorted(E.SHOPS),k=8);schedule[0]=sorted(E.SHOPS)[seed-122000]
        def end(state,environment,day):
            original_end(state,environment,day)
            shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
        E._end_of_day=end
    clock=[0];events=[];elapsed=[];inferred=[]
    def act(o):
        clock[0]=o['step'];start=time.perf_counter();a=own.act(o);elapsed.append(time.perf_counter()-start)
        if own.model.history:inferred.append(dict(own.model.history[-1]))
        return a
    def other(o):clock[0]=o['step'];return opp.agent(o)
    agents=[None,None];agents[seat]=act;agents[1-seat]=other
    try:
        with Ledger(E) as ledger:
            original_commit=E._commit_unit
            def commit(op,item,price,f,p,m,shed_capacity=100):
                ok=original_commit(op,item,price,f,p,m,shed_capacity)
                if ok and op=='SELL' and item in GOODS:events.append([clock[0],ledger.seats[id(f)],item,price])
                return ok
            E._commit_unit=commit
            env.run(agents)
            E._commit_unit=original_commit
    finally:E._end_of_day=original_end
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    assert own.lot is None,'Lot remains at end of season'
    actions=[ss[seat].action for ss in env.steps[1:]]
    physical=[{k:a[k] for k in ('farmer','hands')} for a in actions]
    r={'seed':seed,'seat':seat,'opponent':opponent,'mode':mode,'method':method,
       'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,'ledger':ledger.data,
       'stats':dict(own.stats),'model_stats':dict(own.model.stats),'forecasts':own.forecasts,'inferred':inferred,'events':events,
       'decisions':own.decisions,'max_action_seconds':max(elapsed),'shops':env.state[0].observation.town.unlocked_shops,
       'action_hash':sha256(json.dumps(actions,sort_keys=True).encode()).hexdigest(),
       'physical_hash':sha256(json.dumps(physical,sort_keys=True).encode()).hexdigest()}
    (OUT/phase/f'{seed}-{seat}-{opponent}-{mode}.json').write_text(json.dumps(r))
    return {k:r[k] for k in ('seed','seat','opponent','mode','cash','opponent_cash','max_action_seconds','stats')}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=['train','test','shops'],required=True);args=ap.parse_args();phase=args.phase
    (OUT/phase).mkdir(parents=True,exist_ok=True)
    seeds=list(range(120000,120002)) if phase=='train' else list(range(121000,121004)) if phase=='test' else list(range(122000,122008))
    opponents=['sixday','pasture','prompt','stockpiler'] if phase!='shops' else ['prompt','stockpiler']
    modes=['baseline'] if phase=='train' else ['baseline','priority','profit','margin']
    method='visible' if phase=='train' else json.loads((OUT/'forecast_selection.json').read_text())['method']
    manifest={'phase':phase,'engine':version('kaggle-environments'),'seeds':seeds,'opponents':opponents,'modes':modes,'forecast':method,
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in [BASE,ROOT/'agents/opponent_sales.py',ROOT/'agents/market_forecast.py',*PATHS.values()]},
      'shop_control':'All eight first-shop types; later draws fixed across policies' if phase=='shops' else 'Official natural shops',
      'limits':'Only milk/wool; one lot <=6 units; 12-turn hold target; 24-turn payoff horizon; cash>=2500 and storage guard; source routes unchanged except downstream router reactions.'}
    mp=OUT/f'{phase}_manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==manifest,'Frozen experiment changed'
    else:mp.write_text(json.dumps(manifest,indent=2))
    jobs=[(s,i,o,m) for s in seeds for i in (0,1) for o in opponents for m in modes]
    pending=[j for j in jobs if not (OUT/phase/('{}-{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        fs={pool.submit(run,j,phase,method):j for j in pending}
        for f in as_completed(fs):
            try:print(f.result(),flush=True)
            except Exception:print('FAILED',fs[f],flush=True);raise
    rows=[json.loads((OUT/phase/('{}-{}-{}-{}.json'.format(*j))).read_text()) for j in jobs]
    (OUT/f'{phase}_results.json').write_text(json.dumps(rows));print('COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()

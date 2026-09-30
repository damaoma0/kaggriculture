"""Fresh native-RNG corpus; forecast features collected before agent decisions."""
import argparse,json,time
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from market_corpus import ROOT,load
from compare_router_refresh import PATHS as PUBLIC
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit

OUT=ROOT/'results/fresh/event_prices'
PATHS={**PUBLIC,'baseline':ROOT/'agents/v45_our_selected.py'}
def jobs(phase):
    seeds=range(145000,145004) if phase=='train' else range(146000,146008)
    return [(phase,s,i,o) for s in seeds for i in (0,1) for o in ('v45','twocoins','farmingv5')]

def run(job):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    phase,seed,seat,opponent=job
    module=load('event_model',ROOT/'agents/event_price_forecast.py');model=module.EventModel()
    own=load('event_own',PATHS['baseline']);rival=load('event_rival',PATHS[opponent]);records=[];actual={};times=[]
    def call(obs):
        start=time.perf_counter();model.observe(obs)
        actual[int(obs['step'])]=dict(prices=dict(obs['market']['prices']),inventory=dict(obs['market']['inventory']))
        if 216<=obs['step']<=636 and obs['step']%12==0:
            for item in module.ITEMS:
                for horizon in module.HORIZONS:
                    records.append(dict(step=int(obs['step']),item=item,horizon=horizon,**model.features(obs,item,horizon)))
        times.append(time.perf_counter()-start)
        return own.agent(obs)
    players=[None,None];players[seat]=call;players[1-seat]=rival.agent
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    with Ledger(E) as ledger:
        with WheatAudit(E,env):env.run(players)
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    for r in records:
        future=actual[r['step']+r['horizon']]
        r['actual_price']=future['prices'][r['item']];r['actual_inventory']=future['inventory'][r['item']]
        r['target_flow']=r['actual_inventory']-r['inventory']+r['drain']
    row=dict(phase=phase,seed=seed,seat=seat,opponent=opponent,records=records,max_feature_seconds=max(times),
             cash=[s.reward for s in env.state],telemetry=getattr(own.agent,'telemetry',{}),diagnostics=own._IMPL.chassis.diagnostics)
    path=OUT/'games'/('-'.join(map(str,job))+'.json');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(row),encoding='utf-8')
    return dict(job=job,records=len(records),max_seconds=max(times))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('train','test'),required=True);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    paths={PATHS[k] for k in ('baseline','v45','twocoins','farmingv5')}|set(PATHS['twocoins'].parent.glob('*.py'))|{PATHS['twocoins'].parent/'actions.json',PATHS['twocoins'].parent/'settings.json',ROOT/'agents/event_price_forecast.py',ROOT/'scripts/research_event_prices.py',ROOT/'scripts/evaluate_event_prices.py'}
    manifest=dict(jobs=jobs('train')+jobs('test'),sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
        design='Native RNG; unchanged V45 hybrid; four training seeds, eight held-out seeds; both seats; three rivals. Ridge regularization selected only by training leave-one-seed-out validation.',
        gate='Primary: WHEAT/CARROT at 24/48/72 turns. Event model must improve MAE >=5% versus current, flow and no-event calibrated control; beat each on >=6/8 held-out seeds; neither crop MAE >5% worse versus best control for that crop. No policy integration unless passed.')
    p=OUT/'manifest.json'
    if p.exists():assert json.loads(p.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
    else:p.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs(args.phase) if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()

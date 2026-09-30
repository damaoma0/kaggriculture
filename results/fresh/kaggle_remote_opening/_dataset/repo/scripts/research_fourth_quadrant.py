"""Paired expansion interventions with active opponents and controlled shops."""
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
import argparse,json,random,time
from market_corpus import ROOT,load
from evaluate_boards import Ledger
from compare_router_refresh import PATHS

OUT=ROOT/'results/fresh/fourth_quadrant'
BASE=ROOT/'agents/v45_event_opening_fixed.py'
CONFIGS={
 'no_tomato':['ICE_CREAM_SHOP','BAKERY','BRUNCH_SPOT','ICE_CREAM_SHOP','BAKERY','BRUNCH_SPOT'],
 'tomato1':['ICE_CREAM_SHOP','BAKERY','PIZZA_SHOP','BRUNCH_SPOT','ICE_CREAM_SHOP','BAKERY'],
 'tomato2':['ICE_CREAM_SHOP','BAKERY','PIZZA_SHOP','FARMERS_MARKET','ICE_CREAM_SHOP','BAKERY'],
 'tomato3':['ICE_CREAM_SHOP','BAKERY','PIZZA_SHOP','FARMERS_MARKET','PIZZA_SHOP','BAKERY'],
 'tomato4':['ICE_CREAM_SHOP','PIZZA_SHOP','PIZZA_SHOP','FARMERS_MARKET','PIZZA_SHOP','BAKERY'],
 'tomato6':['PIZZA_SHOP','FARMERS_MARKET']*3,
 'yarn1':['YARN_STORE','BAKERY','BRUNCH_SPOT','ICE_CREAM_SHOP','BAKERY','BRUNCH_SPOT'],
 'yarn2':['YARN_STORE','BAKERY','YARN_STORE','ICE_CREAM_SHOP','BAKERY','BRUNCH_SPOT'],
 'yarn4':['YARN_STORE','BAKERY','YARN_STORE','YARN_STORE','ICE_CREAM_SHOP','YARN_STORE'],
 'carrot':['PET_CAFE','BRUNCH_SPOT','PET_CAFE','ICE_CREAM_SHOP','PET_CAFE','BAKERY']}

def configure(agent,mode):
    g=agent.__globals__;tomato=g['_v219_qualifies'];sheep=g['_v233_eligible']
    def tq(obs,native):
        if mode in ('none','sheep'):return False
        if mode=='native':return tomato(obs,native)
        view=deepcopy(obs);view['market']['prices']['TOMATO']=max(70,view['market']['prices']['TOMATO'])
        view['town']['unlocked_shops']+=['FARMERS_MARKET']*3
        return tomato(view,native)
    def sq(obs,native):
        if mode in ('none','tomato'):return False
        if mode=='native':return sheep(obs,native)
        view=deepcopy(obs);view['market']['prices']['WOOL']=max(220,view['market']['prices']['WOOL']);view['market']['prices']['WHEAT']=min(45,view['market']['prices']['WHEAT'])
        view['town']['unlocked_shops']+=['YARN_STORE']*2
        return sheep(view,native)
    g['_v219_qualifies']=tq;g['_v233_eligible']=sq
    return agent

def jobs(phase):
    configs=list(CONFIGS)
    if phase=='smoke':return [(phase,155900+i,configs[i],0,'v45',m) for i in (0,5) for m in ('none','native','tomato','sheep')]
    return [(phase,155000+i,c,s,o,m) for i,c in enumerate(configs) for s in (0,1) for o in ('v45','twocoins') for m in ('none','native','tomato','sheep')]

def run(job):
    destination=OUT/'games'/('-'.join(map(str,job))+'.json')
    if destination.exists():return str(destination)
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    phase,seed,config,seat,opponent,mode=job
    own=configure(get_last_callable(BASE.read_text(encoding='utf-8'),path=str(BASE)),mode)
    other=load('fourth_rival',PATHS[opponent])
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=CONFIGS[config]+random.Random(seed^0xFA19).choices(sorted(E.SHOPS),k=2)
    end=E._end_of_day
    def locked(state,environment,day):
        end(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=locked;features=[];times=[]
    def ours(obs):
        if obs['step'] in (288,432):features.append(deepcopy(obs))
        now=time.perf_counter();a=own(obs);times.append(time.perf_counter()-now);return a
    players=[None,None];players[seat]=ours;players[1-seat]=other.agent
    try:
        with Ledger(E) as ledger:env.run(players)
    finally:E._end_of_day=end
    assert len(env.steps)==720 and all(s.status=='DONE' for s in env.state)
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    g=own.__globals__
    row=dict(zip(('phase','seed','configuration','seat','opponent','mode'),job))
    row.update(cash=env.state[seat].reward,opponent_cash=env.state[1-seat].reward,margin=env.state[seat].reward-env.state[1-seat].reward,shops=schedule,ledger=ledger.data,features=features,
        tomato=g['_V219_REPORT'],sheep=g['_V233_REPORT'],forecast=g['_EVENT_STATS'],max_seconds=max(times),final_quadrants=len(env.state[seat].observation.farms[seat]['unlocked_quadrants']))
    path=OUT/'games'/('-'.join(map(str,job))+'.json');path.write_text(json.dumps(row,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in row.items() if k in ('seed','configuration','seat','opponent','mode','margin','final_quadrants','tomato','sheep')}),flush=True)
    return str(path)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['smoke','discovery'],required=True);args=p.parse_args()
    (OUT/'games').mkdir(parents=True,exist_ok=True)
    manifest=dict(design='Ten deliberately chosen shop configurations, both seats, two adaptive source opponents, paired four-policy interventions. Different config cells have different seeds; within-cell comparisons have identical shops. Future shops remain hidden from agents. A diagnostic stress grid, not the natural-frequency ladder distribution.',base_sha256=sha256(BASE.read_bytes()).hexdigest(),opponents={k:sha256(PATHS[k].read_bytes()).hexdigest() for k in ('v45','twocoins')},configs=CONFIGS,jobs=jobs(args.phase))
    (OUT/f'{args.phase}_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs(args.phase) if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):f.result()

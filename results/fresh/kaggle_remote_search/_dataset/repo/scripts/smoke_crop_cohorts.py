"""Small mechanism check while the independent benchmark harness is prepared."""
import sys,json,time,random
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from research_fourth_quadrant import ROOT,PATHS,Ledger
from kaggle_environments.agent import get_last_callable

def run(name):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    path=ROOT/'agents'/('v45_event_opening_fixed.py' if name=='baseline' else f'v45_cohort_{name}.py')
    own=get_last_callable(path.read_text(encoding='utf-8'),path=str(path))
    rival=get_last_callable(PATHS['v45'].read_text(encoding='utf-8'),path=str(PATHS['v45']))
    env=make('kaggriculture',configuration={'seed':157000,'episodeSteps':720})
    old=E._end_of_day;shops=['ICE_CREAM_SHOP','PIZZA_SHOP','FARMERS_MARKET','PET_CAFE','PIZZA_SHOP','PET_CAFE','BAKERY','BRUNCH_SPOT']
    def end(state,environment,day):
        old(state,environment,day);current=state[0].observation.town.unlocked_shops;current[:]=shops[:len(current)]
    E._end_of_day=end
    calls=[];events=[]
    def agent(obs):
        a=own(obs);assert isinstance(a,dict);calls.append(obs['step'])
        if obs['step']%24==23 or obs['step']==718:
            g=own.__globals__;managed=g.get('_COHORT_STATE',{}).get('managed',{})
            events.append(dict(day=obs['step']//24,tiles=[dict(xy=xy,tile=obs['farms'][0]['tiles'][xy[1]][xy[0]]) for xy in managed],stats=dict(g.get('_COHORT_STATS',{}))))
        return a
    with Ledger(E) as ledger:env.run([agent,rival])
    assert len(calls)==719,(name,len(calls),env.logs[-2:])
    assert all(isinstance(s[0].action,dict) for s in env.steps[1:])
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    row=dict(name=name,rewards=[s.reward for s in env.state],ledger=ledger.data,stats=own.__globals__.get('_COHORT_STATS',{}),events=events)
    out=ROOT/'results/fresh/crop_cohorts/smoke';out.mkdir(parents=True,exist_ok=True)
    (out/f'{name}.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in row.items() if k in ('name','rewards','stats')}),flush=True)

if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,n) for n in sys.argv[1:] or ['baseline','carrot_stagger','carrot_batch','tomato_stagger','tomato_batch']]):f.result()

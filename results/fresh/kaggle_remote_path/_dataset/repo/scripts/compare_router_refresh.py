"""Frozen comparison of current submission, its exact parent and newer routers."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from statistics import mean
import json,random,time
from market_corpus import ROOT,load
from evaluate_boards import Ledger

DATA=ROOT/'data/router_refresh_20260916'
OUT=ROOT/'results/fresh/router_refresh'
PATHS={name:DATA/name/'main.py' for name in ('v45','v44','farmingv5','pasture2700','twocoins')}
PATHS.update(selected=ROOT/'agents/market_impact_selected.py',sixday=DATA/'sixday_latest/main.py')

def run(job):
    panel,seed,seat,policy,opponent=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    own=load('refresh_own',PATHS[policy]);rival=load('refresh_rival',PATHS[opponent])
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=random.Random(seed^0xA171).choices(sorted(E.SHOPS),k=8)
    if panel=='firstshops':schedule[0]=sorted(E.SHOPS)[seed-134000]
    original=E._end_of_day
    def end(state,environment,day):
        original(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=end
    times=[[],[]]
    def wrapper(module,i):
        def call(o):
            start=time.perf_counter();a=module.agent(o);times[i].append(time.perf_counter()-start);return a
        return call
    players=[None,None];players[seat]=wrapper(own,seat);players[1-seat]=wrapper(rival,1-seat)
    try:
        with Ledger(E) as ledger:env.run(players)
    finally:E._end_of_day=original
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss),(job,len(env.steps),env.logs[-2:])
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    row=dict(zip(('panel','seed','seat','policy','opponent'),job))
    row.update(cash=env.state[seat].reward,opponent_cash=env.state[1-seat].reward,margin=env.state[seat].reward-env.state[1-seat].reward,
      shops=schedule,ledger=ledger.data,max_seconds=[max(x) for x in times],total_seconds=[sum(x) for x in times],
      telemetry=[getattr(m.agent,'telemetry',{}) for m in (own,rival)])
    (OUT/'games'/('-'.join(map(str,job))+'.json')).write_text(json.dumps(row,indent=2))
    return {k:row[k] for k in ('seed','seat','policy','opponent','margin')}

def jobs():
    rivals=('v45','v44','farmingv5','pasture2700','twocoins')
    out=[('randomshops',s,i,p,o) for s in range(133000,133008) for i in (0,1) for p in ('selected','sixday') for o in rivals]
    out += [('randomshops',s,i,'selected','sixday') for s in range(133000,133008) for i in (0,1)]
    out += [('firstshops',s,i,'selected','v45') for s in range(134000,134008) for i in (0,1)]
    return out

def main():
    from importlib.metadata import version
    (OUT/'games').mkdir(parents=True,exist_ok=True)
    sources=set(PATHS.values())|set((DATA/'twocoins').glob('*.py'))|{DATA/'twocoins/actions.json',DATA/'twocoins/settings.json',ROOT/'scripts/compare_router_refresh.py'}
    manifest={'engine':version('kaggle-environments'),'jobs':jobs(),
      'shop_control':'Uniform independent draws with replacement, common across policies, hidden until revealed. Additional first-shop panel fixes each of eight possible first shops once.',
      'purpose':'Comparison only; no policy tuning, promotion or submission.',
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(sources)}}
    path=OUT/'manifest.json'
    if path.exists():assert json.loads(path.read_text())==json.loads(json.dumps(manifest))
    else:path.write_text(json.dumps(manifest,indent=2))
    pending=[j for j in jobs() if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text()) for j in jobs()]
    summary={}
    for panel,policy,opponent in sorted({(r['panel'],r['policy'],r['opponent']) for r in rows}):
        rs=[r for r in rows if (r['panel'],r['policy'],r['opponent'])==(panel,policy,opponent)]
        summary[f'{panel}/{policy}/{opponent}']={'games':len(rs),'wins':sum(r['margin']>0 for r in rs),'ties':sum(r['margin']==0 for r in rs),'losses':sum(r['margin']<0 for r in rs),'mean_cash':mean(r['cash'] for r in rs),'mean_margin':mean(r['margin'] for r in rs),'worst_margin':min(r['margin'] for r in rs)}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

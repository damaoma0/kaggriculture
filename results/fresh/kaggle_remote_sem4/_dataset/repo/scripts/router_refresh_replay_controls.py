"""Diagnostic controls against fixed recorded rival actions, not live rival code."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import json
from compare_router_refresh import ROOT,DATA,OUT,PATHS,load,Ledger

REPLAYS={109609580:ROOT/'results/fresh/qq_farming/episode-109609580-replay.json',109611734:ROOT/'results/fresh/napster_y/episode-109611734-replay.json',
    109613921:DATA/'live_replays/episode-109613921-replay.json',109617159:DATA/'live_replays/episode-109617159-replay.json'}

def run(job):
    episode,policy=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    r=json.loads(REPLAYS[episode].read_text());seat=next(i for i,a in enumerate(r['info']['Agents']) if a['Name']=='Yiyang Xu')
    m=load('refresh_control',PATHS[policy]);env=make('kaggriculture',configuration=r['configuration'],info={'seed':r['info']['seed']})
    original=E._end_of_day;draws=r['steps'][-1][0]['observation']['town']['unlocked_shops']
    def end(state,environment,day):
        original(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=draws[:len(shops)]
    E._end_of_day=end
    def own(o):return m.agent(o)
    def rival(o):return deepcopy(r['steps'][o['step']+1][1-seat]['action'])
    players=[None,None];players[seat]=own;players[1-seat]=rival
    try:
        with Ledger(E) as ledger:env.run(players)
    finally:E._end_of_day=original
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    if policy=='selected':
        for a,b in zip(env.steps,r['steps']):
            for i in (0,1):
                for key in ('farms','market','town','private'):assert a[i].observation[key]==b[i]['observation'][key],(episode,i,key)
    row={'episode':episode,'opponent':r['info']['Agents'][1-seat]['Name'],'policy':policy,'seat':seat,'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
      'margin':env.state[seat].reward-env.state[1-seat].reward,'ledger':ledger.data,'shops':draws}
    (OUT/'replay_controls'/f'{episode}-{policy}.json').write_text(json.dumps(row,indent=2));return {k:v for k,v in row.items() if k not in ('ledger','shops')}

def main():
    (OUT/'replay_controls').mkdir(parents=True,exist_ok=True)
    jobs=[(e,p) for e in REPLAYS for p in ('selected','sixday','v45')]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs if not (OUT/'replay_controls'/f'{j[0]}-{j[1]}.json').exists()]):print(f.result(),flush=True)

if __name__=='__main__':main()

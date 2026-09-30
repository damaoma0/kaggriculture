"""Audit public leader replays and compare V45 under fixed opponent streams."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import json
from market_corpus import ROOT,load
from evaluate_boards import Ledger

OUT=ROOT/'results/fresh/leader_opening'

def snapshot(states,seat,ledger):
    obs=states[0].observation;farm=obs.farms[seat]
    tiles=[v for row in farm['tiles'] for v in row if isinstance(v,dict)]
    return dict(step=obs.step,cash=farm['money'],crops=dict(Counter(v['crop'] for v in tiles if v.get('crop'))),
        animals=dict(Counter(v['animal'] for v in tiles if v.get('animal'))),land=len(farm['unlocked_quadrants']),
        hands=len(farm['hands']),ledger=deepcopy(ledger.data[seat]),shops=list(obs.town.unlocked_shops),
        shed=dict(states[seat].observation.private.shed))

def run(path):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay=json.loads(path.read_text(encoding='utf-8'));eid=replay['info']['EpisodeId']
    seat=replay['info']['TeamNames'].index('Majkel1337');result=dict(episode=eid,seat=seat,teams=replay['info']['TeamNames'],seed=replay['info']['seed'],rewards=replay['rewards'],sha256=sha256(path.read_bytes()).hexdigest())
    for policy in ('leader','v45'):
        agent=load('leader_compare_v45',ROOT/'agents/v45_event_candidate.py') if policy=='v45' else None
        env=make('kaggriculture',configuration=replay['configuration'],info={'seed':replay['info']['seed']})
        snapshots=[];orders=[];physical=[];now=[0];lastday=[-1]
        original_end=E._end_of_day
        def end(state,environment,day):
            original_end(state,environment,day)
            if policy=='v45':
                state[0].observation.town.unlocked_shops[:]=replay['steps'][(day+1)*24][0]['observation']['town']['unlocked_shops']
        E._end_of_day=end
        with Ledger(E) as ledger:
            def player(i):
                def act(obs):
                    now[0]=int(obs['step'])
                    if i==seat and obs['step']%24==0:
                        snapshots.append(snapshot(env.state,seat,ledger))
                    a=agent.agent(obs) if i==seat and policy=='v45' else deepcopy(replay['steps'][obs['step']+1][i]['action'])
                    if i==seat and obs['step']<288:
                        if a.get('market'):orders.append(dict(step=obs['step'],market=a['market']))
                        farm=obs['farms'][seat]
                        for actor,(pos,cmd) in enumerate(zip([farm['farmer'],*farm['hands']],[a.get('farmer',['PASS']),*a.get('hands',[])])):
                            if cmd and cmd[0] in ('PLANT','PLACE','BUILD_PASTURE','HARVEST','DIG'):
                                physical.append(dict(step=obs['step'],actor=actor,pos=list(pos),command=cmd))
                    return a
                return act
            try:env.run([player(0),player(1)])
            finally:E._end_of_day=original_end
            assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
            for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
            snapshots.append(snapshot(env.state,seat,ledger))
            if policy=='leader':
                for t,states in enumerate(env.steps):
                    for i in (0,1):
                        for field in ('farms','market','town','private'):
                            assert states[i].observation[field]==replay['steps'][t][i]['observation'][field],(eid,t,i,field)
            result[policy]=dict(snapshots=snapshots,orders=orders,physical=physical,cash=[s.reward for s in env.state],ledger=ledger.data[seat])
    (OUT/f'audit-{eid}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return dict(episode=eid,seat=seat,shops=result['leader']['snapshots'][6]['shops'],leader_cash=replay['rewards'][seat],v45_cash=result['v45']['cash'][seat],
                leader_day6=result['leader']['snapshots'][6],v45_day6=result['v45']['snapshots'][6])

def main():
    paths=sorted((OUT/'replays').glob('episode-*-replay.json'))
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,p) for p in paths]):print(json.dumps(f.result()),flush=True)

if __name__=='__main__':main()

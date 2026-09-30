"""Whole-season leader trace audit and controlled replay diagnostics."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import json,time
from market_corpus import ROOT
from evaluate_boards import Ledger
from analyze_leader_opening import snapshot

OUT=ROOT/'results/fresh/leader_strategy'
BASE=ROOT/'agents/v45_event_opening_fixed.py'

def run(path):
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay=json.loads(path.read_text(encoding='utf-8'));eid=replay['info']['EpisodeId'];seat=replay['info']['TeamNames'].index('Majkel1337')
    result=dict(episode=eid,seat=seat,teams=replay['info']['TeamNames'],seed=replay['info']['seed'],rewards=replay['rewards'],replay_sha256=sha256(path.read_bytes()).hexdigest())
    for mode in ('replay','v45_replace','leader_vs_v45'):
        agent=get_last_callable(BASE.read_text(encoding='utf-8'),path=str(BASE))
        env=make('kaggriculture',configuration=replay['configuration'],info={'seed':replay['info']['seed']})
        end=E._end_of_day;unit=E._apply_unit_action;interpreter=env.interpreter
        active=[False];seats={};step=[0]
        physical=[[Counter() for _ in range(30)] for _ in range(2)]
        snapshots=[[],[]];layouts=[{},{}];orders=[[],[]]
        def locked(state,environment,day):
            end(state,environment,day)
            if mode!='replay':state[0].observation.town.unlocked_shops[:]=replay['steps'][(day+1)*24][0]['observation']['town']['unlocked_shops']
        def real(state,environment):
            active[0]=True;step[0]=int(state[0].observation.step)
            seats.clear();seats.update({id(f):i for i,f in enumerate(state[0].observation.farms)})
            try:return interpreter(state,environment)
            finally:active[0]=False
        def work(farm,private,idx,action,*args,**kwargs):
            if not active[0] or id(farm) not in seats:return unit(farm,private,idx,action,*args,**kwargs)
            if idx>=len(private['inventories']):
                physical[seats[id(farm)]][step[0]//24]['missing_worker_commands']+=1
                return unit(farm,private,idx,action,*args,**kwargs)
            row=physical[seats[id(farm)]][step[0]//24];op=action[0];row['commands']+=1;row['op:'+op]+=1
            if op in E.FARMER_MOVES:row['moves']+=1
            before=deepcopy(private['inventories'][idx]);seeds0=dict(private['seeds']);pos=E._farmer_position(farm,idx)
            tile0=deepcopy(farm['tiles'][pos[1]][pos[0]]) if pos else None
            value=unit(farm,private,idx,action,*args,**kwargs)
            after=private['inventories'][idx]
            if op in ('HARVEST','COLLECT_FERTILIZER'):
                for item in E.PRODUCTS:
                    delta=after.get(item,0)-before.get(item,0)
                    if delta>0:row['produced:'+item]+=delta
            if op=='FEED':row['wheat_fed']+=before.get('WHEAT',0)-after.get('WHEAT',0)
            if op=='FERTILIZE':row['fertilizer_used']+=before.get('FERTILIZER',0)-after.get('FERTILIZER',0)
            if op in ('PLANT','HARVEST','WATER','CARE','FEED','FERTILIZE','COLLECT_FERTILIZER'):
                tile1=farm['tiles'][pos[1]][pos[0]] if pos else None
                if before==after and tile0==tile1 and seeds0==private['seeds']:row['no_effect:'+op]+=1
            return value
        E._end_of_day=locked;E._apply_unit_action=work;env.interpreter=real
        with Ledger(E) as ledger:
            def player(i):
                def act(obs):
                    t=int(obs['step'])
                    if t%24==0:
                        snap=snapshot(env.state,i,ledger)
                        farm=obs['farms'][i]; tiles=farm['tiles']
                        snap['plots']=sum(isinstance(v,dict) and bool(v.get('crop') or v.get('animal')) for row in tiles for v in row)
                        snapshots[i].append(snap)
                        if t in (24,72,144,216,288,360,432,504,576,648,696):
                            layouts[i][t]=[[v.get('crop') or v.get('animal') or v.get('kind') if isinstance(v,dict) else v for v in row] for row in tiles]
                    replace=(mode=='v45_replace' and i==seat) or (mode=='leader_vs_v45' and i!=seat)
                    a=agent(obs) if replace else deepcopy(replay['steps'][t+1][i]['action'])
                    if a.get('market'):orders[i].append(dict(step=t,market=a['market']))
                    return a
                return act
            try:env.run([player(0),player(1)])
            finally:E._end_of_day=end;E._apply_unit_action=unit;env.interpreter=interpreter
            assert len(env.steps)==720 and all(s.status=='DONE' for s in env.state)
            for i in (0,1):
                assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
                snapshots[i].append(snapshot(env.state,i,ledger))
            if mode=='replay':
                for t,states in enumerate(env.steps):
                    for i in (0,1):
                        for field in ('farms','market','town','private'):
                            assert states[i].observation[field]==replay['steps'][t][i]['observation'][field],(eid,t,i,field)
            result[mode]=dict(cash=[s.reward for s in env.state],snapshots=snapshots,ledger=ledger.data,physical=physical,layouts=layouts,orders=orders)
        (OUT/f'audit-{eid}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(dict(episode=eid,mode=mode,seat=seat,cash=result[mode]['cash'])),flush=True)
    (OUT/f'audit-{eid}.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return eid

if __name__=='__main__':
    paths=sorted((OUT/'replays').glob('episode-*-replay.json'))
    manifest=dict(retrieved_at=time.strftime('%Y-%m-%d %H:%M:%S'),leader='Majkel1337',team_id=16718819,submission=56156662,baseline=str(BASE.relative_to(ROOT)),baseline_sha256=sha256(BASE.read_bytes()).hexdigest(),episodes=[p.name for p in paths],design='Eleven consecutive recent completed episodes available in the downloaded list, five newly downloaded plus six from prior opening audit. All are retained, including losses. Exact replay and two fixed-action controls with original shops. Controls are not live matches.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,p) for p in paths if not (OUT/f'audit-{p.name.split("-")[1]}.json').exists()]):print('completed',f.result(),flush=True)

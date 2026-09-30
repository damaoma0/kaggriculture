"""Reproduce BigAngel loss and isolate opening capital protection."""
from copy import deepcopy
from collections import Counter
from hashlib import sha256
import json
from market_corpus import ROOT
from evaluate_boards import observation

OUT=ROOT/'results/fresh/bigangel'
ARCHIVE=ROOT/'submissions/2026-09-16-v45_event/main.py'

def build():
    src=ARCHIVE.read_text(encoding='utf-8')
    # Freeze the actual uploaded callable, including its existing forecast behavior.
    suffix='''
# Buy the five required feed units before the opponent can move the market.
# Keep this capital protection separate from the forecast entry-point correction.
_CAPITAL_PARENT=[v for v in globals().values() if callable(v)][-1]
def agent(observation, configuration=None):
    action=_CAPITAL_PARENT(observation, configuration)
    step=int(observation['step'])
    if step==0 and action.get('market')==[['BUY_PRODUCT','WHEAT',70],['SELL','WHEAT',70]]:
        action=dict(action, market=[['BUY_PRODUCT','WHEAT',5]])
    elif step==1 and action.get('market',[])[:2]==[['SELL','WHEAT',13],['BUY_PRODUCT','WHEAT',5]]:
        action=dict(action, market=action['market'][2:])
    return action
agent=globals().pop('agent')
'''
    path=ROOT/'agents/v45_opening_capital_fixed.py'
    path.write_text(src+suffix,encoding='utf-8')
    corrected=ROOT/'agents/v45_event_entrypoint_fixed.py'
    (ROOT/'agents/v45_event_opening_fixed.py').write_text(corrected.read_text(encoding='utf-8')+suffix.replace('# Keep this capital protection separate from the forecast entry-point correction.','# Includes the corrected forecast entry point.'),encoding='utf-8')
    return path

def main():
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay=json.loads((OUT/'replays/episode-109709600-replay.json').read_text(encoding='utf-8'))
    fixed=build();seat=1
    original=get_last_callable(ARCHIVE.read_text(encoding='utf-8'),path=str(ARCHIVE))
    parity=[t for t in range(719) if original(observation(replay['steps'][t],seat))!=replay['steps'][t+1][seat]['action']]
    result={'episode':109709600,'seed':replay['info']['seed'],'archive_sha256':sha256(ARCHIVE.read_bytes()).hexdigest(),'parity_mismatches':parity,'runs':{}}
    for policy in ('replay','capital','entrypoint','combined'):
        src=(ROOT/'agents/v45_event_entrypoint_fixed.py' if policy in ('entrypoint','combined') else fixed)
        agent=get_last_callable(src.read_text(encoding='utf-8'),path=str(src))
        env=make('kaggriculture',configuration=replay['configuration'],info={'seed':replay['info']['seed']})
        end=E._end_of_day
        def locked(state,environment,day):
            end(state,environment,day)
            state[0].observation.town.unlocked_shops[:]=replay['steps'][(day+1)*24][0]['observation']['town']['unlocked_shops']
        E._end_of_day=locked
        def player(i):
            def act(obs):
                if policy=='replay' or i!=seat:return deepcopy(replay['steps'][obs['step']+1][i]['action'])
                a=agent(obs)
                if policy=='combined':
                    if obs['step']==0:a=dict(a,market=[['BUY_PRODUCT','WHEAT',5]])
                    elif obs['step']==1:a=dict(a,market=a['market'][2:])
                return a
            return act
        try:env.run([player(0),player(1)])
        finally:E._end_of_day=end
        assert len(env.steps)==720 and all(s.status=='DONE' for s in env.state)
        if policy=='replay':
            for t,states in enumerate(env.steps):
                for i in (0,1):
                    for field in ('farms','market','town','private'):
                        assert states[i].observation[field]==replay['steps'][t][i]['observation'][field],(t,i,field)
        snapshots=[]
        for t in [1,2,24,48,72,96,120,144,288,719]:
            f=env.steps[t][seat].observation.farms[seat]
            snapshots.append(dict(step=t,cash=f.money,crops=dict(Counter(v['crop'] for row in f.tiles for v in row if isinstance(v,dict) and v.get('crop')))))
        result['runs'][policy]={'rewards':[s.reward for s in env.state],'snapshots':snapshots}
        print(policy,json.dumps(result['runs'][policy]),flush=True)
    (OUT/'diagnosis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('parity',parity,flush=True)

if __name__=='__main__':main()

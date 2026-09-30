"""Verify the standalone combined fix using Kaggle's actual file loader."""
from copy import deepcopy
from hashlib import sha256
import json
from diagnose_bigangel import build,OUT
from market_corpus import ROOT,load
from evaluate_boards import Ledger

def main():
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    build();path=ROOT/'agents/v45_event_opening_fixed.py'
    exported=get_last_callable(path.read_text(encoding='utf-8'),path=str(path))
    named=load('combined_named',path)
    replay=json.loads((OUT/'replays/episode-109709600-replay.json').read_text(encoding='utf-8'))
    env=make('kaggriculture',configuration=replay['configuration'],info={'seed':replay['info']['seed']})
    end=E._end_of_day;turns=[]
    def locked(state,environment,day):
        end(state,environment,day);state[0].observation.town.unlocked_shops[:]=replay['steps'][(day+1)*24][0]['observation']['town']['unlocked_shops']
    E._end_of_day=locked
    def own(obs):
        a=exported(deepcopy(obs));assert a==named.agent(deepcopy(obs)),obs['step'];turns.append(obs['step']);return a
    def rival(obs):return deepcopy(replay['steps'][obs['step']+1][0]['action'])
    try:
        with Ledger(E) as ledger:env.run([rival,own])
    finally:E._end_of_day=end
    assert turns==list(range(719))
    rewards=[s.reward for s in env.state]
    assert rewards==[129570,123161]
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==rewards[i]
    assert exported.__globals__['_EVENT_MODEL'] is not None
    result=dict(file=str(path.relative_to(ROOT)),sha256=sha256(path.read_bytes()).hexdigest(),parity_actions=len(turns),rewards=rewards,event_stats=exported.__globals__['_EVENT_STATS'],ledger=ledger.data)
    (OUT/'combined_export.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)

if __name__=='__main__':main()

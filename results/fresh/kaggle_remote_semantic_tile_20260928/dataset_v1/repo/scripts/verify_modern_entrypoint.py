"""Full-game integration check through Kaggle's file-path agent loader."""
import json
from hashlib import sha256
from market_corpus import ROOT
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit

def main():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    out=ROOT/'results/fresh/modern_router'
    selected=ROOT/'agents/modern_router_selected.py'
    selection=json.loads((out/'selection.json').read_text(encoding='utf-8'))
    assert sha256(selected.read_bytes()).hexdigest()==selection['sha256']
    env=make('kaggriculture',configuration={'seed':139999,'episodeSteps':720})
    with Ledger(E) as ledger:
        with WheatAudit(E,env):
            env.run([str(selected),str(ROOT/'data/router_refresh_20260916/v44/main.py')])
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss),(len(env.steps),env.logs[-2:])
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    result=dict(seed=139999,sha256=selection['sha256'],steps=len(env.steps),statuses=[s.status for s in env.state],
        cash=[s.reward for s in env.state],note='Native shop RNG; file-path loading check, not part of policy selection.')
    (out/'entrypoint_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()

"""Native-RNG full game through the standalone competition loader."""
import json
from hashlib import sha256
from market_corpus import ROOT
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit

def main():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    path=ROOT/'agents/v45_delivery_candidate.py'
    env=make('kaggriculture',configuration={'seed':144999,'episodeSteps':720})
    with Ledger(E) as ledger:
        with WheatAudit(E,env):env.run([str(path),str(ROOT/'agents/v45_our_selected.py')])
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    result=dict(sha256=sha256(path.read_bytes()).hexdigest(),seed=144999,steps=len(env.steps),
                statuses=[s.status for s in env.state],cash=[s.reward for s in env.state])
    (ROOT/'results/fresh/delivery_inputs/entrypoint.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()

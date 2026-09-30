"""Run the discovery winner as a standalone competition file."""
import json
from hashlib import sha256
from copy import deepcopy
from market_corpus import ROOT,load
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit
from evaluate_leader_hybrids import OUT,PATHS

def main():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    choice=json.loads((OUT/'discovery_selection.json').read_text(encoding='utf-8'))['candidate']
    source=PATHS[choice]
    path=ROOT/f'agents/v45_leader_{choice}_submission.py'
    path.write_text(source.read_text(encoding='utf-8')+"\n# Ensure Kaggle's last-callable loader selects the intended entry point.\nagent=globals().pop('agent')\n",encoding='utf-8')
    named=load('hybrid_named_parity',source)
    from kaggle_environments.agent import get_last_callable
    exported=get_last_callable(path.read_text(encoding='utf-8'),path=str(path))
    assert exported.__code__.co_firstlineno==named.agent.__code__.co_firstlineno
    parity=[]
    def call(obs,config):
        expected=named.agent(deepcopy(obs),config)
        actual=exported(deepcopy(obs),config)
        assert actual==expected,obs['step']
        parity.append(int(obs['step']))
        return actual
    env=make('kaggriculture',configuration={'seed':151999,'episodeSteps':720})
    with Ledger(E) as ledger:
        with WheatAudit(E,env):env.run([call,str(PATHS['baseline'])])
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    assert parity==list(range(719))
    result=dict(candidate=choice,source_sha256=sha256(source.read_bytes()).hexdigest(),sha256=sha256(path.read_bytes()).hexdigest(),
                packaged_file=str(path.relative_to(ROOT)),seed=151999,steps=len(env.steps),action_parity_count=len(parity),statuses=[s.status for s in env.state],cash=[s.reward for s in env.state])
    if (OUT/'entrypoint.json').exists() and not (OUT/'entrypoint_initial.json').exists():
        (OUT/'entrypoint_initial.json').write_bytes((OUT/'entrypoint.json').read_bytes())
    (OUT/'entrypoint.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()

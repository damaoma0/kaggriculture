"""Audit the existing submitted export and prepare a parity-checked correction.

Original source and submitted archive remain immutable. No upload is performed.
"""
from copy import deepcopy
from hashlib import sha256
import json
from market_corpus import ROOT,load
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit

def main():
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    source=ROOT/'agents/v45_event_candidate.py'
    text=source.read_text(encoding='utf-8')
    path=ROOT/'agents/v45_event_entrypoint_fixed.py'
    path.write_text(text+"\n# Explicit final callable for Kaggle's file loader.\nagent=globals().pop('agent')\n",encoding='utf-8')
    named=load('event_export_reference',source)
    fixed=get_last_callable(path.read_text(encoding='utf-8'),path=str(path))
    original=get_last_callable(text,path=str(source))
    assert fixed.__code__.co_firstlineno==named.agent.__code__.co_firstlineno
    assert original.__code__.co_firstlineno!=named.agent.__code__.co_firstlineno
    turns=[]
    def own(obs,config):
        a=named.agent(deepcopy(obs),config);b=fixed(deepcopy(obs),config)
        assert a==b,obs['step'];turns.append(obs['step']);return b
    env=make('kaggriculture',configuration={'seed':152999,'episodeSteps':720})
    with Ledger(E) as ledger:
        with WheatAudit(E,env):env.run([own,original])
    assert turns==list(range(719)) and len(env.steps)==720
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    g=original.__globals__
    result=dict(original_sha256=sha256(source.read_bytes()).hexdigest(),corrected_file=str(path.relative_to(ROOT)),sha256=sha256(path.read_bytes()).hexdigest(),
        named_entry_line=named.agent.__code__.co_firstlineno,original_loaded_entry_line=original.__code__.co_firstlineno,
        original_event_model_initialized=g['_EVENT_MODEL'] is not None,original_event_stats=g['_EVENT_STATS'],
        fixed_event_stats=fixed.__globals__['_EVENT_STATS'],parity_actions=len(turns),steps=len(env.steps),cash=[s.reward for s in env.state],
        conclusion='Original file selects the parent wrapper, bypassing event-model initialization. The corrected export matches all named-agent research actions. No resubmission performed.')
    out=ROOT/'results/fresh/leader_hybrids/event_export_fix.json';out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

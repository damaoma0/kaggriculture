"""Compare named-module and actual Kaggle file entry points on a live game."""
from pathlib import Path
from hashlib import sha256
import importlib.util,json,sys,time
from benchmark_crop_replacement import load_file_agent,OPPONENT_PATHS,Ledger
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    path=ROOT/'agents/v45_native_carrot_value.py'
    actual=load_file_agent(path)
    spec=importlib.util.spec_from_file_location('native_crop_export_check',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    assert actual.__code__.co_firstlineno==module.agent.__code__.co_firstlineno
    env=make('kaggriculture',configuration={'seed':159000,'episodeSteps':720})
    calls=[];timings=[]
    def checked(obs):
        now=time.perf_counter();a=actual(obs);timings.append(time.perf_counter()-now)
        b=module.agent(obs)
        assert a==b,(obs['step'],a,b)
        assert actual.__globals__['_COHORT_STATS']==module._COHORT_STATS
        calls.append(obs['step']);return a
    with Ledger(E) as ledger:env.run([checked,load_file_agent(OPPONENT_PATHS['v45'])])
    assert len(calls)==719 and all(isinstance(s[0].action,dict) for s in env.steps[1:])
    assert all(s.status=='DONE' for s in env.state)
    stats=actual.__globals__['_COHORT_STATS']
    assert stats['contract_errors']==stats['expired_unharvested_yield']==0
    assert stats['commitments']>0
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    result=dict(sha256=sha256(path.read_bytes()).hexdigest(),actions_equal=len(calls),seed=159000,
                entrypoint_line=actual.__code__.co_firstlineno,max_seconds=max(timings),stats=stats,cash=[s.reward for s in env.state])
    (ROOT/'results/fresh/crop_cohorts/export_check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

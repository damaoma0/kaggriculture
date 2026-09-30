"""Fresh natural-seed confirmation of the packaged priority-only candidate."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from importlib.metadata import version
import json
import sys
import time
from research_opponent_sales import ROOT,OUT,BASE
from market_corpus import load,PATHS
from evaluate_boards import Ledger


def run(job):
    seed,seat,opponent,mode=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    sys.path.insert(0,str(ROOT/'agents'))
    from opponent_sales import Stockpiler
    own=load('priority_confirm_own',BASE if mode=='baseline' else ROOT/'agents/market_priority_candidate.py')
    other=load('priority_confirm_other',BASE if opponent in ('prompt','stockpiler') else PATHS[opponent])
    if opponent=='stockpiler':other=Stockpiler(other)
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    initial=[f.money for f in env.state[0].observation.farms];elapsed=[]
    def act(o):
        start=time.perf_counter();a=own.agent(o);elapsed.append(time.perf_counter()-start);return a
    def rival(o):return other.agent(o)
    agents=[None,None];agents[seat]=act;agents[1-seat]=rival
    with Ledger(E) as ledger:env.run(agents)
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    actions=[ss[seat].action for ss in env.steps[1:]]
    r={'seed':seed,'seat':seat,'opponent':opponent,'mode':mode,'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
       'ledger':ledger.data,'max_action_seconds':max(elapsed),'shops':env.state[0].observation.town.unlocked_shops,'stats':{},
       'physical_hash':sha256(json.dumps([{k:a[k] for k in ('farmer','hands')} for a in actions],sort_keys=True).encode()).hexdigest()}
    (OUT/'confirmation'/('{}-{}-{}-{}.json'.format(*job))).write_text(json.dumps(r))
    return {k:r[k] for k in ('seed','seat','opponent','mode','cash','opponent_cash')}


def main():
    (OUT/'confirmation').mkdir(exist_ok=True)
    manifest={'seeds':list(range(123000,123008)),'opponents':['sixday','pasture','prompt','stockpiler'],'modes':['baseline','priority'],
      'engine':version('kaggle-environments'),
      'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in [BASE,ROOT/'agents/market_priority_candidate.py',ROOT/'agents/opponent_sales.py',*PATHS.values()]},
      'purpose':'Independent confirmation of the simple market-order control across eight new natural seeds; no forecast model or holding.'}
    mp=OUT/'confirmation_manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==manifest
    else:mp.write_text(json.dumps(manifest,indent=2))
    jobs=[(s,i,o,m) for s in manifest['seeds'] for i in (0,1) for o in manifest['opponents'] for m in manifest['modes']]
    pending=[j for j in jobs if not (OUT/'confirmation'/('{}-{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)
    rows=[json.loads((OUT/'confirmation'/('{}-{}-{}-{}.json'.format(*j))).read_text()) for j in jobs]
    (OUT/'confirmation_results.json').write_text(json.dumps(rows));print('COMPLETE',len(rows),flush=True)


if __name__=='__main__':main()

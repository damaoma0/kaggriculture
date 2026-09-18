"""Fresh confirmation of the isolated, self-contained liquidation adapter."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
import json,sys,time,ast
from audit_router_advantage import ROOT,OUT
from market_corpus import PATHS,load
from evaluate_boards import Ledger

def run(job):
    seed,seat,opponent,mode=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    sys.path.insert(0,str(ROOT/'agents'))
    from pasture_investment_dp import PasturePolicy
    candidate=ROOT/'agents/production_candidate.py'
    own=load('confirmation_own',candidate if mode=='adapter' else PATHS['sixday'])
    opp=load('confirmation_opp',PATHS[opponent])
    parity=PasturePolicy(load('parity_reference',PATHS['sixday']),'original') if mode=='adapter' and seed==114000 else None
    if mode=='adapter':assert [k for k,v in own.__dict__.items() if callable(v)][-1]=='agent'
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720});initial=[f.money for f in env.state[0].observation.farms]
    elapsed=[]
    def act(o):
        start=time.perf_counter();a=own.agent(o);elapsed.append(time.perf_counter()-start)
        if parity is not None:assert a==parity.act(o),('Packaged adapter differs',o['step'])
        return a
    def other(o):return opp.agent(o)
    agents=[None,None];agents[seat]=act;agents[1-seat]=other
    with Ledger(E) as ledger:env.run(agents)
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    r={'seed':seed,'seat':seat,'opponent':opponent,'mode':mode,'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
       'ledger':ledger.data,'max_action_seconds':max(elapsed),'parity_actions':719 if parity else 0,
       'shops':env.state[0].observation.town.unlocked_shops}
    (OUT/'confirmation'/f'{seed}-{seat}-{opponent}-{mode}.json').write_text(json.dumps(r,indent=2))
    return {k:r[k] for k in ('seed','seat','opponent','mode','cash','opponent_cash')}

def main():
    (OUT/'confirmation').mkdir(exist_ok=True)
    p=ROOT/'agents/production_candidate.py'
    tree=ast.parse(p.read_text(encoding='utf-8'))
    imports=[a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
    assert set(imports)<=set(('base64','json','zlib','copy','sys'))
    assert not any(isinstance(n,ast.ImportFrom) for n in ast.walk(tree))
    manifest={'seeds':list(range(114000,114008)),'opponents':['sixday','pasture'],'modes':['raw','adapter'],
      'candidate_sha256':sha256(p.read_bytes()).hexdigest(),'purpose':'Fresh confirmation selected after the production holdout isolated a competitive benefit from the sales adapter; no DP or species changes.'}
    mp=OUT/'confirmation_manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==manifest
    else:mp.write_text(json.dumps(manifest,indent=2))
    jobs=[(s,i,o,m) for s in manifest['seeds'] for i in (0,1) for o in manifest['opponents'] for m in manifest['modes']]
    pending=[j for j in jobs if not (OUT/'confirmation'/('{}-{}-{}-{}.json'.format(*j))).exists()]
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)
    rows=[json.loads((OUT/'confirmation'/('{}-{}-{}-{}.json'.format(*j))).read_text()) for j in jobs]
    (OUT/'confirmation_results.json').write_text(json.dumps(rows,indent=2));print('COMPLETE',len(rows),flush=True)

if __name__=='__main__':main()

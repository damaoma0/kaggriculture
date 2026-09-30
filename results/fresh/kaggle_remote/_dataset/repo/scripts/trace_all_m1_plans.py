"""Reproduce archived m1 decisions on reconstructed native observations."""
import sys, json, gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from collections import Counter
from research_labour_profit import Simulator,engine
OUT=ROOT/'results/fresh/all_umg_m1/plans'
def run(path):
    g=json.loads(path.read_text(encoding='utf8'));eid=g['episode'];target=OUT/f'{eid}.json'
    if target.exists():return eid,'cached'
    with gzip.open(ROOT/f'data/ladder_panel/56395605/{eid}.json.gz','rt',encoding='utf8') as f: game=json.load(f)
    E=engine()
    from kaggle_environments.agent import get_last_callable
    source=ROOT/'submissions/2026-09-20-mgt_m1/main.py'
    entry=get_last_callable(source.read_text(encoding='utf8'),path=str(source));G=entry.__globals__
    actions=[None,None];s=game['seat'];actions[s]=game['our_actions'];actions[1-s]=game['opp_actions'];mismatch=[]
    with Simulator(game) as sim:
        old=E.interpreter
        def inter(state,env):
            act=entry(deepcopy(state[s].observation),None)
            if json.dumps(act,sort_keys=True)!=json.dumps(actions[s][sim.t],sort_keys=True):mismatch.append(sim.t)
            return old(state,env)
        E.interpreter=inter
        try:r=sim.run(sim.initial,0,719,actions)
        finally:E.interpreter=old
    assert r['money']==game['rewards']
    hist=[list(h) for h in G.get('_MGT_HISTORY',[])];donor=None
    if hist:
        ep=hist[-1][1]
        for sub in ('56266758','56266899'):
            p=ROOT/f'data/mg_tapes/{sub}/{ep}.json.gz'
            if p.exists():
                with gzip.open(p,'rt',encoding='utf8') as f:d=json.load(f)
                donor=dict(episode=ep,shops=d['shops'][29]);break
    doc=dict(episode=eid,mismatch=mismatch,history=hist,donor=donor,actualShops=game['shops'][29],router=G.get('_MGT_REPORT',{}),overlay=G.get('_SHP_REPORT',{}))
    OUT.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(doc),encoding='utf8')
    return eid,len(mismatch)
if __name__=='__main__':
    paths=list((ROOT/'results/fresh/all_umg_m1/losses').glob('*.json'))
    if len(sys.argv)>1:paths=paths[:int(sys.argv[1])]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for n,f in enumerate(as_completed([pool.submit(run,p) for p in paths]),1): print(n,len(paths),f.result(),flush=True)

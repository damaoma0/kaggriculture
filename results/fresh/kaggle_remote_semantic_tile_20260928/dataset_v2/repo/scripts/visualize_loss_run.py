"""Reconstruct the audited V50 loss and verify against its saved ledger."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / '.venv/Lib/site-packages'))
import json
import hashlib
from collections import Counter
from copy import deepcopy
from kaggle_environments import make
from kaggle_environments.agent import get_last_callable
from kaggle_environments.envs.kaggriculture import kaggriculture as E
from evaluate_boards import Ledger

seed = int(sys.argv[1]) if len(sys.argv)>1 else 176079
seat = int(sys.argv[2]) if len(sys.argv)>2 else 1
saved = json.loads((ROOT/f'results/fresh/selfplay/games/mgt_m1-{seed}-{seat}-vs-v50_public.json').read_text())
players=[]
for name,key in [('v50_public','rival_sha256'),('mgt_m1','candidate_sha256')]:
    p=ROOT/'agents'/f'{name}.py'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==saved[key]
    players.append(get_last_callable(p.read_text(encoding='utf-8'),path=str(p)))
if seat==0: players.reverse()
env=make('kaggriculture',configuration={'episodeSteps':720},info={'seed':seed})
days=[]
expansions=[]
last_land=[1,1]
def snapshot(obs,ledger):
    fs=[]
    for i in [seat,1-seat]:
        farm=obs['farms'][i]
        tiles=[[t.get('animal') or t.get('crop') or t.get('kind') if isinstance(t,dict) else t for t in row] for row in farm['tiles']]
        fs.append(dict(cash=farm['money'],tiles=tiles,quadrants=len(farm['unlocked_quadrants']),sheep=sum(t=='SHEEP' for row in tiles for t in row),wool=ledger.data[i]['sold_units']['WOOL'],wool_revenue=ledger.data[i]['revenue']['WOOL']))
    days.append(dict(day=obs['step']/24,step=obs['step'],shops=list(obs['town']['unlocked_shops']),farms=fs))
with Ledger(E) as ledger:
    def first(obs):
        for j,i in enumerate([seat,1-seat]):
            n=len(obs['farms'][i]['unlocked_quadrants'])
            if n>last_land[j]:
                expansions.append(dict(side=j,step=obs['step'],day=obs['step']/24,quadrants=n,yarn=obs['town']['unlocked_shops'].count('YARN_STORE')))
                last_land[j]=n
        if obs['step']%24==0:snapshot(obs,ledger)
        return players[0](obs)
    env.run([first,players[1]])
    snapshot(env.state[0].observation,ledger)
    assert [env.state[seat].reward,env.state[1-seat].reward]==[saved['cash'],saved['bench_cash']]
    assert days[-1]['shops']==saved['shops']
    for i,key in [(seat,'ledger_candidate'),(1-seat,'ledger_benchmark')]:
        for field in ['revenue','sold_units','spend']:
            assert dict(ledger.data[i][field])==saved[key][field],(i,field)
assert len(env.steps)==720 and all(s.status=='DONE' for s in env.state)
arrivals=[]
for d in days:
    for shop in d['shops'][len(arrivals):]:arrivals.append(dict(day=d['day'],shop=shop))
out=ROOT/f'results/fresh/heavy_loss_audit/run-{seed}-{seat}.json'
g=players[seat].__globals__
history=[[0,g['_MGT_TAPES'][g['_MGT_CFG']['default_route']]['ep'],None,None,0]]+deepcopy(g['_MGT_HISTORY'])
switches=[h for i,h in enumerate(history) if i==0 or h[1]!=history[i-1][1]]
tapes={str(t['ep']):dict(shops=t['shops']) for t in g['_MGT_TAPES'] if t['ep'] in {h[1] for h in switches}}
out.write_text(json.dumps(dict(seed=seed,seat=seat,margin=saved['margin'],days=days,arrivals=arrivals,expansions=expansions,verified=True,router_history=history,switches=switches,tapes=tapes),ensure_ascii=True),encoding='utf-8')
print(json.dumps(dict(seed=seed,seat=seat,verified=True,final=[f['cash'] for f in days[-1]['farms']],expansions=expansions,days=len(days))))

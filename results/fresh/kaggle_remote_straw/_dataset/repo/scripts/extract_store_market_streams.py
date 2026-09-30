"""Exact recorded-game transaction streams for market-response calculations."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import json
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
OUT=ROOT/'results/fresh/store_mismatch_shift_20260923/market_streams'


def extract(episode):
 target=OUT/f'{episode}.json.gz'
 if target.exists():
  with gzip.open(target,'rt',encoding='utf8') as f:result=json.load(f)
  assert result['episode']==episode and result['validated']
  return {'episode':episode,'events':len(result['transactions']),'cached':True}
 from research_labour_profit import Simulator,economic
 with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:
  game=json.load(f)
 seat=game['seat'];actions=[None,None]
 actions[seat],actions[1-seat]=game['our_actions'],game['opp_actions']
 with Simulator(game) as sim:
  result=sim.run(sim.initial,0,719,actions)
  assert result['money']==game['rewards']
  ledgers=[economic(result['events'],s) for s in (0,1)]
  for s,e in enumerate(ledgers):
   assert 3000+sum(e['revenue'].values())-sum(e['spend'].values())==result['money'][s]
  transactions=[(t,s,op,item,price) for t,s,op,item,price in result['events']
                if op in ('BUY_PRODUCT','SELL')]
  packed=dict(episode=episode,seat=seat,seed=game['seed'],shops=game['shops'],
     transactions=transactions,cash=result['money'],ledgers=ledgers,
     validated=True,source='Official engine 1.32.7, recorded actions both seats and recorded shops; all final cash/ledgers reconcile.')
  target.parent.mkdir(parents=True,exist_ok=True)
  with gzip.open(target,'wt',encoding='utf8') as f:json.dump(packed,f,separators=(',',':'))
  return {'episode':episode,'events':len(transactions),'cached':False}


def main():
 audit=json.loads((ROOT/'results/fresh/all_umg_m1/summary.json').read_text(encoding='utf8'))
 episodes=sorted(x['episode'] for x in audit['losses'])
 with ProcessPoolExecutor(max_workers=3) as pool:
  jobs=[pool.submit(extract,e) for e in episodes]
  done=0
  for f in as_completed(jobs):
   r=f.result();done+=1
   if done%10==0 or done==len(jobs):print(json.dumps({'done':done,'total':len(jobs),'latest':r}),flush=True)


if __name__=='__main__':main()

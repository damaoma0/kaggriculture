"""Exact-engine, fixed-production test of holding small strawberry lots to D28.

Recorded physical actions and the recorded opponent stay fixed. This changes
only our market orders. Selection and confirmation episodes are frozen before
reading outcomes; the winning development arm is reported on confirmation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import random
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
sys.path.insert(0,str(ROOT/'scripts'))
OUT=ROOT/'results/fresh/larger_shift_20260923/strawberry'
ARMS=[dict(id='unchanged',start=30,cap=0),
      *[dict(id=f'd{start}-q{cap}',start=start,cap=cap)
        for start in (24,25,26,27) for cap in (6,12,24)]]
RELEASE=28*24+1


def freeze():
 path=OUT/'design.json'
 if path.exists():return json.loads(path.read_text(encoding='utf8'))
 audit=json.loads((ROOT/'results/fresh/all_umg_m1/summary.json').read_text(encoding='utf8'))
 available={int(p.name.split('.')[0]) for p in (ROOT/'data/ladder_panel/56395605').glob('*.json.gz')}
 rows=[e for e in audit['episodes'] if e['episode'] in available]
 assert len(rows)==198 and sum(e['margin']<0 for e in rows)==89
 rng=random.Random(2026092302)
 dev=[];confirm=[]
 for group in (sorted(e['episode'] for e in rows if e['margin']<0),
               sorted(e['episode'] for e in rows if e['margin']>0)):
  rng.shuffle(group)
  split=int(len(group)*0.6)
  dev.extend(group[:split]);confirm.extend(group[split:])
 result=dict(created_utc=datetime.now(timezone.utc).isoformat(),arms=ARMS,
             development=sorted(dev),confirmation=sorted(confirm),
             selection_rule='Largest mean paired competitive-margin gain on development, ties favor lower cap and later start. Report the frozen selected arm on confirmation including wins and losses.',
             method='Official engine, recorded physical actions of both seats and actual shops; only own strawberry SELL orders changed from day 24. The shed guard lifts holds at 88 items; held fruit releases at D28 h01 after the shop tick. No candidate can intentionally hold past D28.',
             caveat='Fixed recorded opponents and our recorded physical actions; not a live policy or responsive-opponent benchmark.')
 OUT.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(result,indent=2),encoding='utf8')
 return result


def run_game(episode):
 target=OUT/'cases'/f'{episode}.json'
 if target.exists():
  x=json.loads(target.read_text(encoding='utf8'))
  assert len(x['arms'])==len(ARMS)
  return dict(episode=episode,cached=True)
 from research_labour_profit import Simulator,engine,economic
 with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:g=json.load(f)
 seat=g['seat'];actions=[None,None]
 actions[seat],actions[1-seat]=g['our_actions'],g['opp_actions']
 with Simulator(g) as sim:
  E=engine()
  prefix=sim.run(sim.initial,0,24*24,actions)
  start_state=prefix['state']
  rows=[]
  for arm in ARMS:
   reserve=0;held=0;released=0;pressure=0;changes=0
   native=E._process_market

   def market(state,env):
    nonlocal reserve,held,released,pressure,changes
    t=sim.t
    if arm['cap'] and t>=arm['start']*24:
     private=state[seat].observation.private
     shed=private['shed'];available=int(shed.get('STRAWBERRY',0))
     action=state[seat].action
     orders=action.get('market') or []
     sells=[o for o in orders if o and o[0]=='SELL' and o[1]=='STRAWBERRY' and len(o)>=3]
     if t<RELEASE:
      full=sum(int(x) for x in shed.values())>=88
      # A held unit must still be physically in the shed. If inventory was
      # consumed or dropped by another action, do not reserve phantom stock.
      reserve=min(reserve,available)
      if full:
       if reserve:pressure+=1
       reserve=0
      else:
       planned=sum(int(o[2]) for o in sells)
       extra=min(arm['cap']-reserve,max(0,planned),max(0,available-reserve))
       if extra>0:
        reserve+=extra;held+=extra
       allowed=max(0,available-reserve)
       for o in sells:
        n=min(int(o[2]),allowed)
        if n<int(o[2]):changes+=1
        o[2]=n;allowed-=n
     elif t==RELEASE:
      reserve=0
      planned=sum(int(o[2]) for o in sells)
      if available>planned:
       if sells:sells[-1][2]+=available-planned
       elif len(orders)<10:
        orders.append(['SELL','STRAWBERRY',available])
        action['market']=orders
       released+=max(0,available-planned)
    return native(state,env)

   E._process_market=market
   try:out=sim.run(start_state,24*24,719,actions)
   finally:E._process_market=native
   if arm['id']=='unchanged':assert out['money']==g['rewards'],(episode,out['money'],g['rewards'])
   ledgers=[economic(out['events'],s) for s in (seat,1-seat)]
   for s,e in zip((seat,1-seat),ledgers):
    # This ledger covers D24 onward; check against the prefix cash.
    initial=prefix['money'][s]
    assert initial+sum(e['revenue'].values())-sum(e['spend'].values())==out['money'][s]
   strawberry=[defaultdict(lambda:[0,0]),defaultdict(lambda:[0,0])]
   for t,s,op,item,price in out['events']:
    if op=='SELL' and item=='STRAWBERRY':
     strawberry[s][t//24][0]+=1;strawberry[s][t//24][1]+=price
   rows.append(dict(arm=arm['id'],cash=out['money'][seat],opponent_cash=out['money'][1-seat],
                    margin=out['money'][seat]-out['money'][1-seat],held_units=held,
                    release_order_units=released,pressure_lifts=pressure,modified_market_orders=changes,
                    strawberry_sales_by_day={str(d):v for d,v in strawberry[seat].items()},
                    opponent_strawberry_sales_by_day={str(d):v for d,v in strawberry[1-seat].items()},
                    final_strawberry_shed=out['state'][seat].observation.private['shed'].get('STRAWBERRY',0),
                    ledger_verified=True))
  base=rows[0]
  for row in rows:
   row['margin_delta']=row['margin']-base['margin']
   row['cash_delta']=row['cash']-base['cash']
   row['opponent_cash_delta']=row['opponent_cash']-base['opponent_cash']
  result=dict(episode=episode,seed=g['seed'],seat=seat,recorded_rewards=g['rewards'],
              original_loss=(g['rewards'][seat]<g['rewards'][1-seat]),arms=rows)
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(json.dumps(result,indent=2),encoding='utf8')
  return dict(episode=episode,cached=False)


def main():
 design=freeze()
 episodes=design['development']+design['confirmation']
 with ProcessPoolExecutor(max_workers=3) as pool:
  jobs=[pool.submit(run_game,e) for e in episodes]
  for i,f in enumerate(as_completed(jobs),1):
   x=f.result()
   if i%20==0 or i==len(jobs):print(json.dumps({'done':i,'total':len(jobs),'latest':x}),flush=True)
 rows={e:json.loads((OUT/'cases'/f'{e}.json').read_text(encoding='utf8')) for e in episodes}
 def score(ids,arm):
  rr=[next(x for x in rows[e]['arms'] if x['arm']==arm) for e in ids]
  return dict(n=len(rr),mean_margin_delta=statistics.mean(x['margin_delta'] for x in rr),
              median_margin_delta=statistics.median(x['margin_delta'] for x in rr),
              mean_cash_delta=statistics.mean(x['cash_delta'] for x in rr),
              mean_opponent_cash_delta=statistics.mean(x['opponent_cash_delta'] for x in rr),
              better=sum(x['margin_delta']>0 for x in rr),worse=sum(x['margin_delta']<0 for x in rr),
              unchanged=sum(x['margin_delta']==0 for x in rr),
              mean_held=statistics.mean(x['held_units'] for x in rr),
              mean_final_shed=statistics.mean(x['final_strawberry_shed'] for x in rr),
              wins_before=sum(rows[e]['arms'][0]['margin']>0 for e in ids),
              wins_after=sum(x['margin']>0 for x in rr))
 dev={a['id']:score(design['development'],a['id']) for a in ARMS}
 pick=max(ARMS,key=lambda a:(dev[a['id']]['mean_margin_delta'],-a['cap'],a['start']))
 def price_trend(first,last):
  changes=[]
  for e in episodes:
   sales=rows[e]['arms'][0]['strawberry_sales_by_day']
   a,b=sales.get(str(first)),sales.get(str(last))
   if a and b:
    changes.append(b[1]/b[0]-a[1]/a[0])
  return dict(first_day=first,last_day=last,paired_games=len(changes),
              higher=sum(x>0 for x in changes),median_price_change=statistics.median(changes),
              mean_price_change=statistics.mean(changes))
 result=dict(selected_arm=pick['id'],development=dev,
             confirmation=score(design['confirmation'],pick['id']),
             confirmation_losses=score([e for e in design['confirmation'] if rows[e]['original_loss']],pick['id']),
             confirmation_wins=score([e for e in design['confirmation'] if not rows[e]['original_loss']],pick['id']),
             price_trends=[price_trend(24,28),price_trend(25,28),price_trend(26,28),price_trend(27,29)],
             design=design,source_games=198,all_controls_exact=True)
 (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps({k:result[k] for k in ('selected_arm','confirmation','confirmation_losses','confirmation_wins')}))


if __name__=='__main__':main()

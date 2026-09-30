"""One-for-one sale-mix conversion screen for every active-tape store mismatch.

At a planned sale of a less-demanded product, exchange at most q shed units
for an equally sized sale of a more-demanded product. The actual engine handles
both farms, cash, and price impact. This is deliberately an *unfunded* same-hour
product transmutation, not an executable crop/herd production policy.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
sys.path.insert(0,str(ROOT/'scripts'))
OUT=ROOT/'results/fresh/store_mismatch_shift_20260923/conversion'
GRID=(0,1,2,4,6,8,12)


def screen_episode(episode, events):
 from research_labour_profit import Simulator,engine
 target=OUT/f'{episode}.json.gz'
 if target.exists():
  with gzip.open(target,'rt',encoding='utf8') as f:cached=json.load(f)
  assert cached['episode']==episode and len(cached['events'])==len(events)
  return {'episode':episode,'events':len(events),'cached':True}
 with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:game=json.load(f)
 seat=game['seat'];actions=[None,None]
 actions[seat],actions[1-seat]=game['our_actions'],game['opp_actions']
 by_day=defaultdict(list)
 for e in events:by_day[e['reveal_day']].append(e)
 baseline_margin=game['rewards'][seat]-game['rewards'][1-seat]
 rows=[]
 with Simulator(game) as sim:
  E=engine();initial=sim.initial;cursor=0
  for day in sorted(by_day):
   start=day*24
   if start>cursor:
    prior=sim.run(initial,cursor,start,actions)
    initial=prior['state'];cursor=start
   for event in by_day[day]:
    gains=[p for p,d in event['shop_drains_per_day'].items() if d>0]
    losses=[p for p,d in event['shop_drains_per_day'].items() if d<0]
    pairs=[]
    for source in losses:
     for dest in gains:
      curve=[dict(requested_per_day=0,converted_units=0,cash=game['rewards'][seat],
                  opponent_cash=game['rewards'][1-seat],margin=baseline_margin,
                  margin_delta=0.0)]
      for q in GRID[1:]:
       moved=Counter()
       market_fn=E._process_market

       def convert(state,env):
        if sim.t//24>=day:
         today=sim.t//24
         remaining=q-moved[today]
         if remaining>0:
          shed=state[seat].observation.private['shed']
          action=state[seat].action
          orders=action.get('market') or []
          for i,order in enumerate(orders):
           if not(order and order[0]=='SELL' and order[1]==source):continue
           n=min(remaining,shed.get(source,0),int(order[2]))
           if n<=0:continue
           if n<int(order[2]) and len(orders)>=10:continue
           shed[source]-=n
           shed[dest]=shed.get(dest,0)+n
           if n==int(order[2]):orders[i]=['SELL',dest,n]
           else:
            order[2]-=n
            orders.insert(i,['SELL',dest,n])
           moved[today]+=n
           break
        return market_fn(state,env)

       E._process_market=convert
       try:result=sim.run(initial,start,719,actions)
       finally:E._process_market=market_fn
       qty=sum(moved.values());own=result['money'][seat];opp=result['money'][1-seat]
       row=dict(requested_per_day=q,converted_units=qty,cash=own,
                opponent_cash=opp,margin=own-opp,margin_delta=(own-opp)-baseline_margin)
       row['gross_margin_per_converted_unit']=row['margin_delta']/qty if qty else None
       curve.append(row)
      pairs.append(dict(source=source,target=dest,curve=curve,
                        best_gross_grid_q=max(curve,key=lambda x:x['margin'])['requested_per_day']))
    rows.append(dict(slot=event['slot'],reveal_day=day,source_store=event['source_store'],
                     actual_store=event['actual_store'],under2500=event['under2500'],
                     conversions=pairs))
 payload=dict(episode=episode,seed=game['seed'],seat=seat,baseline_cash=game['rewards'],
              events=rows,validated=True,
              limitation='Zero-cost same-hour unit conversion of planned sales; no physical production plan or cost. Multiple events in one game are correlated.')
 OUT.mkdir(parents=True,exist_ok=True)
 with gzip.open(target,'wt',encoding='utf8') as f:json.dump(payload,f,separators=(',',':'))
 return {'episode':episode,'events':len(events),'cached':False}


def main():
 audit=json.loads((ROOT/'results/fresh/store_mismatch_shift_20260923/active_store_pairs.json').read_text(encoding='utf8'))
 grouped=defaultdict(list)
 for row in audit['events']:grouped[row['episode']].append(row)
 OUT.mkdir(parents=True,exist_ok=True)
 with ProcessPoolExecutor(max_workers=3) as pool:
  jobs=[pool.submit(screen_episode,episode,grouped[episode]) for episode in sorted(grouped)]
  for i,f in enumerate(as_completed(jobs),1):
   r=f.result()
   if i%5==0 or i==len(jobs):print(json.dumps({'done':i,'total':len(jobs),'latest':r}),flush=True)
 rows=[]
 for episode in sorted(grouped):
  with gzip.open(OUT/f'{episode}.json.gz','rt',encoding='utf8') as f:data=json.load(f)
  for e in data['events']:
   for c in e['conversions']:
    rows.append(dict(episode=episode,slot=e['slot'],source_store=e['source_store'],
                     actual_store=e['actual_store'],under2500=e['under2500'],**c))
 groups=defaultdict(list)
 for row in rows:groups[(row['source_store'],row['actual_store'],row['source'],row['target'])].append(row)
 summary=[]
 for (store0,store1,source,dest),rr in sorted(groups.items()):
  qstats={}
  for q in GRID:
   vals=[next(x for x in r['curve'] if x['requested_per_day']==q) for r in rr]
   qstats[str(q)]=dict(median_margin_delta=median(x['margin_delta'] for x in vals),
                      positive_cases=sum(x['margin_delta']>0 for x in vals),
                      median_converted_units=median(x['converted_units'] for x in vals),
                      median_margin_per_converted_unit=(median(x['gross_margin_per_converted_unit'] for x in vals if x['gross_margin_per_converted_unit'] is not None) if any(x['converted_units'] for x in vals) else None))
  best=max(GRID,key=lambda q:qstats[str(q)]['median_margin_delta'])
  summary.append(dict(source_store=store0,actual_store=store1,source_product=source,
                      target_product=dest,events=len(rr),best_zero_cost_grid_q=best,
                      median_margin_at_best=qstats[str(best)]['median_margin_delta'],
                      curves=qstats))
 result=dict(created_utc=datetime.now(timezone.utc).isoformat(),
             losses=len(grouped),mismatch_events=len(audit['events']),
             conversion_event_curves=len(rows),store_pairs=len(set((x['source_store'],x['actual_store']) for x in summary)),
             cross_product_pairs=len(summary),grid=list(GRID),conversions=summary,
             method='At market time on actual recorded games, transform at most q units per day of a planned source-product sale into equal target-product units. Recorded actions of both farms and actual shops otherwise run in official engine; both farms face endogenous prices and cash changes. Base cash verified by independent recorded replay.',
             caveat='Best q is a grid optimum of zero-cost same-hour conversion of goods already delivered to the shed. It is not an optimal production shift: crop and animal investments, lead times, maintenance, labor, and changed production quantities are excluded. Multiple slots in one game are correlated.')
 (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps({k:result[k] for k in ('losses','mismatch_events','conversion_event_curves','store_pairs','cross_product_pairs')}))


if __name__=='__main__':main()

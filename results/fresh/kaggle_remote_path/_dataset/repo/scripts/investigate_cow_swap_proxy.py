"""Optimistic, route-preserving cow-to-sheep swap probe on recorded games.

At D12 one existing cow is instantaneously replaced with a sheep for $500.
Existing hand routes are unchanged; spare wool in the shed is offered for sale.
The real game requires two unfed days for the cow to escape plus a purchase,
pickup and placement, so this is a diagnostic opportunity probe, not a policy.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
sys.path.insert(0,str(ROOT/'scripts'))
OUT=ROOT/'results/fresh/larger_shift_20260923/cow_proxy'
SOURCE=ROOT/'results/fresh/larger_shift_20260923/sheep/design.json'
START=12*24
ESCAPE_START=10*24


def run(episode):
 target=OUT/'cases'/f'{episode}.json'
 if target.exists():
  return dict(episode=episode,cached=True)
 from research_labour_profit import Simulator,engine,economic
 with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:g=json.load(f)
 seat=g['seat']; actions=[None,None]
 actions[seat],actions[1-seat]=g['our_actions'],g['opp_actions']
 E=engine()
 with Simulator(g) as sim:
  prefix=sim.run(sim.initial,0,START,actions)
  start=prefix['state']
  farm=start[0].observation.farms[seat]
  cows=[(x,y) for y,row in enumerate(farm['tiles']) for x,c in enumerate(row)
        if isinstance(c,dict) and c.get('animal')=='COW']
  def continuation(coord):
   state=deepcopy(start)
   if coord is not None:
    x,y=coord;c=state[0].observation.farms[seat]['tiles'][y][x]
    assert c['animal']=='COW'
    c.update(animal='SHEEP',placed_day=12,pending_care_bonus=0,
             yield_units=0,consecutive_unfed=0,fed_today=False,cared_today=False)
    state[0].observation.farms[seat]['money']-=500
   original=E._process_market
   def market(states,env):
    # The tape may not ask to sell incremental wool. Liquidate any spare wool
    # after physical actions, while respecting the ten-order limit.
    action=states[seat].action
    orders=action.get('market') or []
    if len(orders)<10:
     available=int(states[seat].observation.private['shed'].get('WOOL',0))
     planned=sum(int(o[2]) if len(o)>2 else 1 for o in orders
                 if o and o[0]=='SELL' and o[1]=='WOOL')
     extra=max(0,available-planned)
     if extra:
      orders.append(['SELL','WOOL',extra]);action['market']=orders
    return original(states,env)
   E._process_market=market
   try:result=sim.run(state,START,719,actions)
   finally:E._process_market=original
   econ=[economic(result['events'],i) for i in (seat,1-seat)]
   return dict(cow=coord,cash=result['money'][seat],opponent_cash=result['money'][1-seat],
               margin=result['money'][seat]-result['money'][1-seat],
               own_wool=econ[0]['revenue'].get('WOOL',0),
               opp_wool=econ[1]['revenue'].get('WOOL',0),
               own_milk=econ[0]['revenue'].get('MILK',0),
               wool_units=econ[0]['units'].get('WOOL',0))
  baseline=continuation(None)
  arms=[continuation(c) for c in cows]
  for arm in arms:
   for metric in ('cash','opponent_cash','margin','own_wool','opp_wool','own_milk','wool_units'):
    arm[f'd_{metric}']=arm[metric]-baseline[metric]
  row=dict(episode=episode,seat=seat,cows=len(cows),baseline=baseline,
           swaps=arms,best=max(arms,key=lambda a:a['d_margin']) if arms else None)
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(json.dumps(row,indent=2),encoding='utf8')
  return dict(episode=episode,cows=len(cows),best=row['best']['d_margin'] if arms else None)


def run_escape(episode):
 target=OUT/'escape_cases'/f'{episode}.json'
 if target.exists():return dict(episode=episode,cached=True)
 instant=json.loads((OUT/'cases'/f'{episode}.json').read_text(encoding='utf8'))
 if not instant['best']:return dict(episode=episode,cows=0)
 coord=tuple(instant['best']['cow'])
 from research_labour_profit import Simulator,engine
 with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:g=json.load(f)
 seat=g['seat'];actions=[None,None]
 actions[seat],actions[1-seat]=g['our_actions'],g['opp_actions']
 E=engine()
 with Simulator(g) as sim:
  prefix=sim.run(sim.initial,0,ESCAPE_START,actions)
  initial=prefix['state']
  def final(start,from_t,to_t):
   original=E._process_market
   def market(states,env):
    action=states[seat].action;orders=action.get('market') or []
    if len(orders)<10:
     available=int(states[seat].observation.private['shed'].get('WOOL',0))
     planned=sum(int(o[2]) if len(o)>2 else 1 for o in orders
                 if o and o[0]=='SELL' and o[1]=='WOOL')
     extra=max(0,available-planned)
     if extra:orders.append(['SELL','WOOL',extra]);action['market']=orders
    return original(states,env)
   E._process_market=market
   try:return sim.run(start,from_t,to_t,actions)
   finally:E._process_market=original
  baseline=final(initial,ESCAPE_START,719)
  original=E._apply_unit_action
  def suppress(farm,private,idx,action,*args,**kwargs):
   if (action and action[0]=='FEED' and sim.seats.get(id(farm))==seat
       and tuple(E._farmer_position(farm,idx) or ())==coord):
    action=['PASS']
   return original(farm,private,idx,action,*args,**kwargs)
  E._apply_unit_action=suppress
  try:middle=final(initial,ESCAPE_START,START)
  finally:E._apply_unit_action=original
  state=middle['state']
  x,y=coord;tile=state[0].observation.farms[seat]['tiles'][y][x]
  escaped=isinstance(tile,dict) and tile.get('kind')=='PASTURE' and 'animal' not in tile
  if escaped:
   state[0].observation.farms[seat]['tiles'][y][x]=E._new_animal('SHEEP',12)
   state[0].observation.farms[seat]['money']-=500
  variant=final(state,START,719)
  final_money=variant['money']
  result=dict(episode=episode,cow=coord,escaped=escaped,
              baseline_cash=baseline['money'][seat],baseline_opponent=baseline['money'][1-seat],
              cash=final_money[seat],opponent_cash=final_money[1-seat],
              margin_delta=(final_money[seat]-final_money[1-seat])-(baseline['money'][seat]-baseline['money'][1-seat]),
              own_delta=final_money[seat]-baseline['money'][seat],
              opponent_delta=final_money[1-seat]-baseline['money'][1-seat],
              instant_margin_delta=instant['best']['d_margin'])
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_text(json.dumps(result,indent=2),encoding='utf8')
  return dict(episode=episode,escaped=escaped,margin_delta=result['margin_delta'])


def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=4);p.add_argument('--escape',action='store_true')
 a=p.parse_args()
 design=json.loads(SOURCE.read_text(encoding='utf8'))
 # Same high-Yarn development block as the expansion screen.
 eps=[e for e in design['development'] if e not in design['negative_controls']]
 OUT.mkdir(parents=True,exist_ok=True)
 if a.escape:
  with ProcessPoolExecutor(max_workers=a.workers,max_tasks_per_child=1) as pool:
   for future in as_completed([pool.submit(run_escape,e) for e in eps]):
    print(json.dumps(future.result()),flush=True)
  rows=[json.loads((OUT/'escape_cases'/f'{e}.json').read_text(encoding='utf8')) for e in eps]
  result=dict(method='Posthoc best instant-swap cow per game, D10-11 feed suppressed to force escape, magic D12 sheep placement and $500 charge; recorded routes unchanged.',
              games=len(rows),escaped=sum(r['escaped'] for r in rows),
              mean_margin=sum(r['margin_delta'] for r in rows)/len(rows),
              positive=sum(r['margin_delta']>0 for r in rows),
              mean_own=sum(r['own_delta'] for r in rows)/len(rows),
              mean_opponent=sum(r['opponent_delta'] for r in rows)/len(rows))
  (OUT/'escape_summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
  print(json.dumps(result,indent=2))
  return
 with ProcessPoolExecutor(max_workers=a.workers,max_tasks_per_child=1) as pool:
  for future in as_completed([pool.submit(run,e) for e in eps]):
   print(json.dumps(future.result()),flush=True)
 rows=[json.loads((OUT/'cases'/f'{e}.json').read_text(encoding='utf8')) for e in eps]
 best=[r['best']['d_margin'] for r in rows if r['best']]
 all_swaps=[x['d_margin'] for r in rows for x in r['swaps']]
 result=dict(method='Instant D12 swap, $500 charge, existing hand routes and generous wool liquidation; no two-day escape or pickup/placement cost.',
             games=len(rows),total_cows=sum(r['cows'] for r in rows),
             positive_swaps=sum(x>0 for x in all_swaps),
             mean_all_swap=sum(all_swaps)/len(all_swaps) if all_swaps else None,
             positive_best_games=sum(x>0 for x in best),
             mean_best_ex_post=sum(best)/len(best) if best else None,
             per_game=[dict(episode=r['episode'],cows=r['cows'],best=r['best']['d_margin'] if r['best'] else None,
                            mean=sum(x['d_margin'] for x in r['swaps'])/r['cows'] if r['cows'] else None)
                       for r in rows])
 (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps(result,indent=2))


if __name__=='__main__':main()

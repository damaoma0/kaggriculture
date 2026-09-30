"""Exact live-agent, fixed-opponent trace for the largest sheep-expansion loss."""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
sys.path.insert(0,str(ROOT/'scripts'))
OUT=ROOT/'results/fresh/larger_shift_20260923/sheep'
EPISODE=111890117
ARMS=('mgt_m1','sheep_early_fields')
EXTRA=((2,2),(2,1),(3,1),(3,0))


def snapshot(obs,seat):
 farm=obs['farms'][seat]
 counts=Counter()
 other=Counter()
 for row in farm['tiles']:
  for cell in row:
   if not isinstance(cell,dict):continue
   if cell.get('animal'):counts['animal:'+cell['animal']]+=1
   if cell.get('crop'):counts['crop:'+cell['crop']]+=1
 for row in obs['farms'][1-seat]['tiles']:
  for cell in row:
   if not isinstance(cell,dict):continue
   if cell.get('animal'):other['animal:'+cell['animal']]+=1
   if cell.get('crop'):other['crop:'+cell['crop']]+=1
 private=obs['private']
 tiles={f'{x},{y}':deepcopy(farm['tiles'][y][x]) for x,y in EXTRA}
 return dict(step=int(obs['step']),cash=[f['money'] for f in obs['farms']],
             wool_inventory=obs['market']['inventory']['WOOL'],
             wool_price=obs['market']['prices']['WOOL'],
             wheat_price=obs['market']['prices']['WHEAT'],
             own_counts=dict(counts),opponent_counts=dict(other),hands=len(farm['hands']),
             shed={k:int(private['shed'].get(k,0)) for k in ('WOOL','WHEAT','MILK','CARROT')},
             carried={k:sum(int(inv.get(k,0)) for inv in private['inventories'])
                      for k in ('WOOL','WHEAT','MILK','CARROT')},
             extra_tiles=tiles)


def run_arm(arm,game,design):
 from kaggle_environments.agent import get_last_callable
 from research_labour_profit import Simulator,engine,economic
 source=OUT/'sources'/f'{arm}.py'
 assert sha256(source.read_bytes()).hexdigest()==design['source_hashes'][arm]
 entry=get_last_callable(source.read_text(encoding='utf8'),path=str(source))
 seat=game['seat'];actions=[None,None]
 actions[seat],actions[1-seat]=game['our_actions'],game['opp_actions']
 E=engine();days={};changed=[];drops=[];private_seat={}
 with Simulator(game) as sim:
  original=E.interpreter
  old_drop=E._drop_inventories_to_shed
  def tracked_drop(private,capacity):
   before=dict(private['shed'])
   carried=Counter()
   for inv in private['inventories']:carried.update(inv)
   result=old_drop(private,capacity)
   after=private['shed']
   losses={item:n-(int(after.get(item,0))-int(before.get(item,0)))
           for item,n in carried.items() if n-(int(after.get(item,0))-int(before.get(item,0)))>0}
   if private_seat.get(id(private))==seat:
    drops.append(dict(day=sim.t//24,shed_before=sum(before.values()),
                      carried=dict(carried),lost=losses))
   return result
  def live(state,env):
   t=sim.t
   private_seat.update({id(state[i].observation.private):i for i in (0,1)})
   obs=deepcopy(state[seat].observation)
   if t%24==0:days[t//24]=snapshot(obs,seat)
   action=entry(obs,None)
   if action!=game['our_actions'][t]:changed.append(t)
   state[seat].action=action
   return original(state,env)
  E.interpreter=live;E._drop_inventories_to_shed=tracked_drop
  try:result=sim.run(sim.initial,0,719,actions,capture=True)
  finally:E.interpreter=original;E._drop_inventories_to_shed=old_drop
  assert result['money']==game['rewards'] if arm=='mgt_m1' else True
  if arm=='mgt_m1':assert not changed
  econ=[economic(result['events'],s) for s in (seat,1-seat)]
  final_private=result['state'][seat].observation.private
  final_stock=dict(shed={k:int(v) for k,v in final_private['shed'].items() if v},
                   carried={k:sum(int(inv.get(k,0)) for inv in final_private['inventories'])
                            for k in ('WOOL','WHEAT','MILK','CARROT')})
  sales=defaultdict(lambda:defaultdict(lambda:[0,0]))
  spend=defaultdict(lambda:defaultdict(float))
  for t,s,op,item,price in result['events']:
   side='own' if s==seat else 'opponent'
   if op=='SELL':
    r=sales[t//24][side+':'+item];r[0]+=1;r[1]+=price
   else:spend[t//24][side+':'+op+((':'+item) if item else '')]+=price
  work=defaultdict(lambda:defaultdict(int))
  physical=defaultdict(lambda:defaultdict(int))
  for row in result['work']:
   side='own' if row['seat']==seat else 'opponent'
   cmd=row['cmd'][0]
   work[row['t']//24][side+':'+cmd]+=1
   for item,change in row['delta'].items():
    if change:
     physical[row['t']//24][side+':'+cmd+':'+item]+=change
     if row['seat']==seat and tuple(row['pos']) in EXTRA:
      physical[row['t']//24][side+':extra:'+cmd+':'+item]+=change
   if row['seat']==seat and cmd in ('HARVEST','FEED','CARE','DIG','PLACE','BUILD_PASTURE'):
    work[row['t']//24][side+':'+cmd+':'+str(row['pos'])]+=1
  return dict(arm=arm,episode=EPISODE,seat=seat,final_money=result['money'],
              final_stock=final_stock,
              overnight_drops=drops,
              action_changes=len(changed),first_change=changed[0] if changed else None,
              economics=econ,overlay=entry.__globals__.get('_SHP_REPORT',{}),
              router=entry.__globals__.get('_MGT_REPORT',{}),
              days=days,sales={str(k):dict(v) for k,v in sales.items()},
              spend={str(k):dict(v) for k,v in spend.items()},
              work={str(k):dict(v) for k,v in work.items()},
              physical={str(k):dict(v) for k,v in physical.items()})


def main():
 global EPISODE,EXTRA
 import argparse
 parser=argparse.ArgumentParser()
 parser.add_argument('--episode',type=int,default=EPISODE)
 args=parser.parse_args()
 EPISODE=args.episode
 design=json.loads((OUT/'design.json').read_text(encoding='utf8'))
 candidate=json.loads((OUT/'historical'/f'sheep_early_fields-{EPISODE}.json').read_text(encoding='utf8'))
 decisions=candidate['overlay'].get('decisions') or []
 if decisions:EXTRA=tuple(tuple(p) for p in decisions[-1]['tiles'])
 with gzip.open(ROOT/f'data/ladder_panel/56395605/{EPISODE}.json.gz','rt',encoding='utf8') as f:game=json.load(f)
 rows={a:run_arm(a,game,design) for a in ARMS}
 target=OUT/f'worst_loss_trace_{EPISODE}.json'
 target.write_text(json.dumps(rows,indent=2),encoding='utf8')
 print(json.dumps(dict(episode=EPISODE,source=str(target),
                       final={a:r['final_money'] for a,r in rows.items()},
                       changes={a:r['action_changes'] for a,r in rows.items()})))


if __name__=='__main__':main()

"""Pair the original full-game replay with the day-17-only diagnostic replay."""
from __future__ import annotations

import base64
from collections import Counter
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
sys.path.insert(0,str(ROOT/'scripts'))
OUT=ROOT/'results/fresh/store_mismatch_shift_20260923/care_grid'
CASE=111678108


def prior_before():
 html=(ROOT/'viz/tape-109740300-before-after.html').read_text(encoding='utf8')
 payload=html.split('<script id="data" type="application/json">',1)[1].split('</script>',1)[0]
 data=json.loads(payload)
 assert data['episode']==CASE and len(data['games'])==2
 before=data['games'][0]
 assert before['verified'] and before['rewards']==[87878.0,98302.0]
 payload=json.loads(gzip.decompress(base64.b64decode(before['packed'])))
 assert len(payload['frames'])==720
 return before


def build_after():
 from kaggle_environments.agent import get_last_callable
 from research_labour_profit import Simulator,engine,economic

 source=OUT/'agent-17.py'
 expected=json.loads((OUT/'arm-17.json').read_text(encoding='utf8'))
 assert sha256(source.read_bytes()).hexdigest()==expected['source_sha256']
 with gzip.open(ROOT/f'data/ladder_panel/56395605/{CASE}.json.gz','rt',encoding='utf8') as f:game=json.load(f)
 entry=get_last_callable(source.read_text(encoding='utf8'),path=str(source))
 seat=game['seat'];actions=[None,None]
 actions[seat],actions[1-seat]=game['our_actions'],game['opp_actions']
 tiles=[];lookup={};frames=[];changed=[]
 harvested=[Counter(),Counter()];sold=[Counter(),Counter()]
 revenue=[Counter(),Counter()];spend=[Counter(),Counter()]
 cursor_work=cursor_events=0

 def tile_id(tile):
  key=json.dumps(tile,sort_keys=True,separators=(',',':'))
  if key not in lookup:
   lookup[key]=len(tiles);tiles.append(deepcopy(tile))
  return lookup[key]

 with Simulator(game) as sim:
  native=engine().interpreter

  def capture(state):
   nonlocal cursor_work,cursor_events
   for work in sim.work[cursor_work:]:
    if work['cmd'][0]=='HARVEST':
     harvested[work['seat']].update({p:n for p,n in work['delta'].items() if n>0})
   for _,s,op,item,price in sim.events[cursor_events:]:
    if op=='SELL':sold[s][item]+=1;revenue[s][item]+=price
    else:spend[s][op+(':'+item if item else '')]+=price
   cursor_work=len(sim.work);cursor_events=len(sim.events)
   obs=state[seat]['observation']
   farms=[]
   for s,farm in enumerate(obs['farms']):
    farms.append(dict(money=farm['money'],units=deepcopy([farm['farmer'],*farm['hands']]),
      board=[tile_id(tile) for row in farm['tiles'] for tile in row],
      private=deepcopy(dict(state[s]['observation']['private'])),
      action=deepcopy(state[s].action),harvested=dict(harvested[s]),
      sold=dict(sold[s]),revenue=dict(revenue[s]),spend=dict(spend[s])))
   frames.append(dict(step=int(obs['step']),farms=farms,prices=deepcopy(obs['market']['prices']),
                      shops=list(obs['town']['unlocked_shops'])))

  def live(state,env):
   action=entry(deepcopy(state[seat].observation),None)
   if action!=game['our_actions'][sim.t]:changed.append(sim.t)
   state[seat].action=action
   capture(state)
   return native(state,env)

  engine().interpreter=live
  try:result=sim.run(sim.initial,0,719,actions,capture=True)
  finally:engine().interpreter=native
  capture(result['state'])
  assert len(frames)==720 and [f['step'] for f in frames]==list(range(720))
  assert result['money'][seat]==expected['cash']
  assert result['money'][1-seat]==expected['opponent_cash']
  assert changed==expected['changed_steps']
  assert dict(harvested[seat])==expected['harvested']
  assert [economic(result['events'],s) for s in (seat,1-seat)]==expected['ledgers']
  for s in (seat,1-seat):
   assert 3000+sum(revenue[s].values())-sum(spend[s].values())==result['money'][s]
  assert entry.__globals__['_TV_REPORT']['decisions']==expected['decisions']
  pack=dict(tiles=tiles,frames=frames)
  raw=json.dumps(pack,separators=(',',':')).encode()
  compressed=gzip.compress(raw,mtime=0)
  meta=dict(id=1,label='After · day-17-only care revision',arm='mgt_tape_care_d17',
            episode=CASE,seed=game['seed'],
            names=['After · day-17-only care revision' if s==seat else game['names'][s] for s in (0,1)],
            seat=seat,rewards=result['money'],source_sha256=expected['source_sha256'],
            changed_steps=changed,decisions=expected['decisions'],verified=True,
            packed=base64.b64encode(compressed).decode())
  dest=OUT/'after-d17.replay.json.gz'
  with gzip.open(dest,'wt',encoding='utf8') as f:
   json.dump(dict({k:v for k,v in meta.items() if k!='packed'},**pack),f,separators=(',',':'))
  return meta


def main():
 before=prior_before()
 after=build_after()
 data=dict(games=[before,after],episode=CASE,variant='109740300-milk-care-to-wool-d17-diagnostic',
           method='Official engine reconstruction · identical recorded opponent commands and shop schedule · both cash ledgers verified',
           changed_days=[17],first_edit=409)
 html=(ROOT/'scripts/fragments/tape_variant_replays.html').read_text(encoding='utf8')
 html=html.replace('One worker redirects cow care to a sheep on three days. Final result: <strong>+314 own cash · +88 margin · +1 wool · −3 milk</strong>.',
                   'One worker redirects cow care to a sheep on day 17 only. Final result: <strong>+229 own cash · +237 margin · +1 wool · −1 milk</strong>.')
 html=html.replace('D19 · second edit','D19 · unchanged').replace('D21 · extra wool','D21 · unchanged')
 html=html.replace('D23 · retirement guard','D23 · unchanged')
 html=html.replace('After · care revision','After · day-17-only revision')
 payload=json.dumps(data,separators=(',',':')).replace('<','\\u003c')
 dest=ROOT/'viz/tape-109740300-before-after-d17.html'
 dest.write_text(html.replace('__DATA__',payload),encoding='utf8')
 verification=dict(episode=CASE,frames_each=720,rewards=[before['rewards'],after['rewards']],
                   changed_days=[17],source_hashes=[before['source_sha256'],after['source_sha256']],
                   prior_baseline_reused=True,after_exact_engine=True,both_ledgers_verified=True,
                   output=str(dest.relative_to(ROOT)))
 (OUT/'replay_verification.json').write_text(json.dumps(verification,indent=2),encoding='utf8')
 print(json.dumps(dict(path=str(dest),bytes=dest.stat().st_size,rewards=verification['rewards'],frames_each=720)))


if __name__=='__main__':main()

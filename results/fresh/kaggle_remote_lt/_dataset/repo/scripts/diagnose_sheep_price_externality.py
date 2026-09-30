"""Features visible immediately before expanded sheep commitments."""
from __future__ import annotations
import gzip
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
sys.path.insert(0,str(ROOT/'scripts'))
OUT=ROOT/'results/fresh/larger_shift_20260923/sheep'


def main():
 from research_labour_profit import Simulator
 design=json.loads((OUT/'design.json').read_text(encoding='utf8'))
 rows=[]
 for episode in design['development']+design['confirmation']:
  base_path=OUT/'historical'/f'mgt_m1-{episode}.json'
  cand_path=OUT/'historical'/f'sheep_early_fields-{episode}.json'
  if not(base_path.exists() and cand_path.exists()):continue
  b=json.loads(base_path.read_text(encoding='utf8'))
  c=json.loads(cand_path.read_text(encoding='utf8'))
  step=c['first_change']
  if step is None:continue
  with gzip.open(ROOT/f'data/ladder_panel/56395605/{episode}.json.gz','rt',encoding='utf8') as f:g=json.load(f)
  seat=g['seat'];actions=[None,None];actions[seat],actions[1-seat]=g['our_actions'],g['opp_actions']
  with Simulator(g) as sim:
   z=sim.run(sim.initial,0,step,actions)['state'][0].observation
   farms=z.farms
   flock=[sum(isinstance(tile,dict) and tile.get('animal')=='SHEEP' for row in farm['tiles'] for tile in row) for farm in farms]
   cows=[sum(isinstance(tile,dict) and tile.get('animal')=='COW' for row in farm['tiles'] for tile in row) for farm in farms]
   row=dict(episode=episode,stage='development' if episode in design['development'] else 'stress',
            day=step//24,step=step,margin_delta=c['margin']-b['margin'],
            own_delta=c['cash']-b['cash'],opponent_delta=c['opponent_cash']-b['opponent_cash'],
            sheep_added=c['overlay'].get('sheep_bought',0)-b['overlay'].get('sheep_bought',0),
            wool_quote=z.market['prices']['WOOL'],wool_inventory=z.market['inventory']['WOOL'],
            own_sheep=flock[seat],opponent_sheep=flock[1-seat],
            own_cows=cows[seat],opponent_cows=cows[1-seat],
            yarn_stores=list(z.town['unlocked_shops']).count('YARN_STORE'),
            baseline_own_wool=b['economics'][0]['revenue'].get('WOOL',0),
            baseline_opponent_wool=b['economics'][1]['revenue'].get('WOOL',0),
            opponent_wool_delta=c['economics'][1]['revenue'].get('WOOL',0)-b['economics'][1]['revenue'].get('WOOL',0))
   rows.append(row)
 target=OUT/'externality_features.json'
 target.write_text(json.dumps(rows,indent=2),encoding='utf8')
 for r in rows:print(json.dumps(r),flush=True)


if __name__=='__main__':main()

"""Enumerate every active-tape store substitution in audited mgt_m1 losses.

The fixed town-drain delta is a demand change, not an optimal production target.
Observed output and prices are kept beside it to identify trials worth running.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/store_mismatch_shift_20260923'
SHOPS={
 'BAKERY':('EGG','WHEAT'),
 'PIZZA_SHOP':('MILK','TOMATO','WHEAT'),
 'BRUNCH_SPOT':('EGG','WHEAT','STRAWBERRY'),
 'YARN_STORE':('WOOL',),
 'ICE_CREAM_SHOP':('STRAWBERRY','MILK','WHEAT'),
 'PET_CAFE':('CARROT',),
 'SMOOTHIE_SHOP':('STRAWBERRY','MILK'),
 'FARMERS_MARKET':('WHEAT','CARROT','TOMATO','STRAWBERRY'),
}
PRODUCTS=('WHEAT','CARROT','TOMATO','STRAWBERRY','EGG','MILK','WOOL')


def drain(shop):
 return {p:(2 if len(SHOPS[shop])==1 else 1) for p in SHOPS[shop]}


def median(values):
 return statistics.median(values) if values else None


def selected_tape_shops(losses):
 ids={r[1] for loss in losses for r in loss['plan']['history'] if r[0] in (3,6,9,12,15,18,21,24)}
 paths={int(p.name.split('.')[0]):p for p in (ROOT/'data/mg_tapes').glob('*/*.json.gz')}
 assert ids<=paths.keys()
 result={}
 for ep in ids:
  with gzip.open(paths[ep],'rt',encoding='utf8') as f:tape=json.load(f)
  result[ep]=tape['shops'][24]
  assert len(result[ep])==8
 return result


def main():
 audit=json.loads((ROOT/'results/fresh/all_umg_m1/summary.json').read_text(encoding='utf8'))
 tape_shops=selected_tape_shops(audit['losses'])
 rows=[]
 for loss in audit['losses']:
  actual=loss['plan']['actualShops']
  history={x[0]:x[1] for x in loss['plan']['history']}
  assert len(actual)==8 and all(3*i in history for i in range(1,9))
  daily=defaultdict(dict)
  for cell in loss['daily']:
   daily[cell['day']][cell['product']]=cell
  for slot,target in enumerate(actual,1):
   selected_id=history[slot*3]
   source=tape_shops[selected_id][slot-1]
   if source==target:continue
   day=slot*3
   a,b=drain(source),drain(target)
   delta={p:b.get(p,0)-a.get(p,0) for p in PRODUCTS if b.get(p,0)!=a.get(p,0)}
   # Town shops consume every fourth hour. Six drains per complete day,
   # starting with reveal day; there are 30-day days in the season.
   seasonal_demand_delta={p:n*6*(30-day) for p,n in delta.items()}
   post={}
   for p in delta:
    cells=[daily[d][p] for d in range(day,30)]
    produced=sum(c['values'][0] for c in cells)
    rival_produced=sum(c['values'][4] for c in cells)
    sold=sum(c['values'][1] for c in cells)
    rival_sold=sum(c['values'][5] for c in cells)
    quote=[c['opening_price'] for c in cells]
    product=next(x for x in loss['products'] if x['product']==p)
    post[p]=dict(our_harvested=produced,rival_harvested=rival_produced,
       harvest_gap_to_rival=produced-rival_produced,our_sold=sold,
       rival_sold=rival_sold,median_opening_quote=median(quote),
       base_price=product['base'],
       low_quote_harvested_ours=product['ours']['low_harvest'],
       season_direct_cash_gap=product['direct_cash_gap'])
   rows.append(dict(episode=loss['episode'],seed=loss['seed'],slot=slot,
      reveal_day=day,source_store=source,actual_store=target,
      under2500=loss['under2500'],opponent_rating=loss['rating'],
      loss_margin=loss['margin'],selected_tape_at_reveal=selected_id,
      selected_final_donor=loss['plan']['donor']['episode'],
      shop_drains_per_day={p:n*6 for p,n in delta.items()},
      demand_delta_to_season_end=seasonal_demand_delta,
      observed_after_reveal=post))
 groups=defaultdict(list)
 for row in rows:groups[(row['source_store'],row['actual_store'])].append(row)
 summaries=[]
 for (source,target),rr in sorted(groups.items()):
  allproducts=sorted({p for row in rr for p in row['shop_drains_per_day']})
  products={}
  for p in allproducts:
   x=[row for row in rr if p in row['shop_drains_per_day']]
   products[p]=dict(per_day_demand_delta=x[0]['shop_drains_per_day'][p],
       median_remaining_demand_delta=median([r['demand_delta_to_season_end'][p] for r in x]),
       median_observed_harvest_gap_to_rival=median([r['observed_after_reveal'][p]['harvest_gap_to_rival'] for r in x]),
       median_opening_quote=median([r['observed_after_reveal'][p]['median_opening_quote'] for r in x]),
       quote_above_base_cases=sum(r['observed_after_reveal'][p]['median_opening_quote']>r['observed_after_reveal'][p]['base_price'] for r in x))
  summaries.append(dict(source_store=source,actual_store=target,events=len(rr),games=len({r['episode'] for r in rr}),
      under2500_events=sum(r['under2500'] for r in rr),median_reveal_day=median([r['reveal_day'] for r in rr]),
      products=products,episodes=sorted({r['episode'] for r in rr}),
      evidence='Demand arithmetic is exact for this store substitution. Production gaps and prices are observed associations. No production adjustment has been optimized here.'))
 assert len(rows)==383 and len(summaries)==56 and len({r['episode'] for r in rows})==89
 result=dict(created_utc=datetime.now(timezone.utc).isoformat(),
  source='89/89 audited losing mgt_m1 games; selected tape at each reveal from the validated router trace and actual eight-store sequence.',
  method='At each store reveal, compare the actual store in that slot to the store in the tape selected after the reveal. A prior tape may have differed even when the selected tape now matches. Different slots in one game are correlated; their demand deltas cannot by themselves explain output or profit.',
  metric='Shop consumes each listed product once every four hours, twice for Yarn Store/Pet Cafe single-product shops. Six cycles per day; a slot at day d contributes through day 29.',
  counts=dict(losses=89,store_substitution_events=len(rows),directed_store_pairs=len(summaries),
              under2500_events=sum(r['under2500'] for r in rows)),
  pairs=summaries,events=rows)
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'active_store_pairs.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 print(json.dumps(result['counts']))
 for row in sorted(summaries,key=lambda r:-r['events'])[:20]:
  print(row['source_store'],'->',row['actual_store'],row['events'],{p:x['per_day_demand_delta'] for p,x in row['products'].items()})


if __name__=='__main__':main()

"""Summarize all directed active-tape store pairs and market-only conversion screens."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/store_mismatch_shift_20260923'
GRID=(0,1,2,4,6,8,12)
PRODUCT_SHORT={'WHEAT':'Wht','CARROT':'Car','TOMATO':'Tom','STRAWBERRY':'Str',
               'EGG':'Egg','MILK':'Mlk','WOOL':'Wol'}
SHOP_SHORT={'BAKERY':'Bakery','PIZZA_SHOP':'Pizza','BRUNCH_SPOT':'Brunch',
            'YARN_STORE':'Yarn','ICE_CREAM_SHOP':'Ice cream','PET_CAFE':'Pet cafe',
            'SMOOTHIE_SHOP':'Smoothie','FARMERS_MARKET':'Farmers market'}


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))


def fmt_delta(products):
 return ', '.join(f'{PRODUCT_SHORT[p]} {n["per_day_demand_delta"]:+g}' for p,n in products.items())


def main():
 audit=read(BASE/'active_store_pairs.json')
 conversion=read(BASE/'conversion/summary.json')
 care=read(BASE/'care_grid/summary.json')
 event_options={}
 for path in sorted((BASE/'conversion').glob('*.json.gz')):
  with gzip.open(path,'rt',encoding='utf8') as f:g=json.load(f)
  for e in g['events']:
   options={}
   quantities={}
   for c in e['conversions']:
    for arm in c['curve']:
     options[(c['source'],c['target'],arm['requested_per_day'])]=arm['margin_delta']
     quantities[(c['source'],c['target'],arm['requested_per_day'])]=arm['converted_units']
   event_options[(g['episode'],e['slot'])]=dict(margins=options,quantities=quantities)
 summaries=[]
 for pair in sorted(audit['pairs'],key=lambda r:(-r['events'],r['source_store'],r['actual_store'])):
  keys=[(e['episode'],e['slot']) for e in audit['events'] if e['source_store']==pair['source_store'] and e['actual_store']==pair['actual_store']]
  below_keys=[(e['episode'],e['slot']) for e in audit['events'] if e['source_store']==pair['source_store'] and e['actual_store']==pair['actual_store'] and e['under2500']]
  assert len(keys)==pair['events']
  source=[p for p,x in pair['products'].items() if x['per_day_demand_delta']<0]
  target=[p for p,x in pair['products'].items() if x['per_day_demand_delta']>0]
  candidates=[(a,b,q) for a in source for b in target for q in GRID]
  assert len(candidates)==len(event_options[keys[0]]['margins'])
  best=None;cv=None
  if candidates:
   def rank(keys2):
    return max(candidates,key=lambda x:(median(event_options[k]['margins'][x] for k in keys2),-x[2],x[0],x[1]))
   best_choice=rank(keys)
   source_p,target_p,q=best_choice
   sample=[event_options[k]['margins'][best_choice] for k in keys]
   quantities=[event_options[k]['quantities'][best_choice] for k in keys]
   below_sample=[event_options[k]['margins'][best_choice] for k in below_keys]
   best=dict(source=source_p,target=target_p,requested_per_day=q,
             median_gross_margin_delta=median(sample),positive_cases=sum(v>0 for v in sample),
             under2500_median_gross_margin_delta=(median(below_sample) if below_sample else None),
             under2500_positive_cases=sum(v>0 for v in below_sample),
             median_converted_units=median(quantities),
             median_gross_margin_per_converted_unit=(median(v/u for v,u in zip(sample,quantities) if u) if any(quantities) else None),
             within_pair_selected=True)
   episodes=sorted({e for e,_ in keys})
   if len(episodes)>=2:
    held=[];choices=[]
    for omitted_ep in episodes:
     trained=[k for k in keys if k[0]!=omitted_ep]
     choice=rank(trained)
     choices.append(choice)
     held.extend(event_options[k]['margins'][choice] for k in keys if k[0]==omitted_ep)
    cv=dict(n_events=len(keys),n_games=len(episodes),median_margin_delta=median(held),positive_cases=sum(x>0 for x in held),
            chosen_q_counts=dict(Counter(x[2] for x in choices)),
            chosen_product_pair_counts={a+'>'+b:v for (a,b),v in Counter((x[0],x[1]) for x in choices).items()})
  summaries.append(dict(source_store=pair['source_store'],actual_store=pair['actual_store'],
                        events=pair['events'],games=pair['games'],under2500_events=pair['under2500_events'],
                        median_reveal_day=pair['median_reveal_day'],
                        demand_delta_per_day={p:v['per_day_demand_delta'] for p,v in pair['products'].items()},
                        best_free_conversion=best,leave_one_game_out=cv))
 assert len(summaries)==56
 result=dict(created_utc=datetime.now(timezone.utc).isoformat(),
             source='All 89 validated mgt_m1 losses, active selected donor tape at each store reveal; all 383 mismatch events and 56 directed store pairs.',
             best_free_conversion='Same-hour one-for-one conversion of already delivered units before planned sale, with no physical production or cost. The best is selected on the same losing games and is optimistically biased.',
             cross_validation='For each game, select a product pair and q/day on events from other games with the same directed store pair by median competitive-margin gain; evaluate on all omitted-game events. Correlated slots and losing-only selection remain.',
             do_not_interpret_as='Neither the exact shop-demand delta nor the zero-cost sale-conversion grid optimum is an executable or economically optimal production shift.',
             pairs=summaries,
             feasible_care_grid=dict(episode=care['episode'],tested_days=care['tested_days'],
                                     best_tested_arm=care['best_tested_arm'],
                                     best_tested_margin_delta=care['best_tested_margin_delta'],
                                     best_tested_harvest_delta=next(x['harvest_delta'] for x in care['arms'] if x['arm']==care['best_tested_arm']),
                                     full_three_day_margin_delta=next(x['margin_delta'] for x in care['arms'] if x['arm']=='17-19-21')))
 (BASE/'pair_shift_summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
 lines=['# Store mismatches and production-shift evidence','',
  'The active `mgt_m1` tape disagreed with the newly revealed store in **383 slots across all 89 audited losses** (247 slots in the 58 losses against opponents below 2500). **All 56 directed store pairs occur.** Each slot uses the tape selected by the router *at that reveal*. This corrects the earlier final-donor comparison, which included earlier days when another tape was active. No losing game had only one mismatch, so a pair cannot be assigned its own share of a loss.','',
  'A store changes town demand by 6 units/day for each listed product, or 12 for the single-product Yarn Store and Pet Cafe. These are exact market drains from its reveal through day 29. **They are not production targets.** Opponent supply, existing farm cohorts, delay to new output, feed, labor, and the nonlinear price response set the economically useful shift.','',
  'I screened all 52 mixed-sign pairs by converting up to 0, 1, 2, 4, 6, 8 or 12 units/day of a planned sale of a lower-demand product into an equal planned sale of a higher-demand product, at the same market hour. The official engine repriced both farms and executed the remaining recorded actions. This is a deliberately generous **zero-cost sale-mix scenario**: it gives the farm the replacement good without planting, animal purchase, feed, maintenance, labor or lead time. The displayed amount is the best *requested* q/day on these losing games; actual converted units can be lower if source stock is unavailable. It must not be read as an optimal physical production shift or a bound on all other possible plans. Four pairs change only one product and have no one-for-one conversion.','',
  '## Full directed-pair screen','',
  '| Active tape → actual store | Events (<2500) | Δ town demand/day | Best free conversion, requested/day (season units) | Median margin Δ | Leave-one-game-out median / positive |',
  '|---|---:|---|---|---:|---:|']
 for row in summaries:
  name=f"{SHOP_SHORT[row['source_store']]} → {SHOP_SHORT[row['actual_store']]}"
  demand=fmt_delta({p:{'per_day_demand_delta':n} for p,n in row['demand_delta_per_day'].items()})
  if row['best_free_conversion'] is None:best='—';gain='—'
  elif row['best_free_conversion']['requested_per_day']==0:
   best='0/d (no gain)';gain='+0'
  else:
   b=row['best_free_conversion']
   best=f"{PRODUCT_SHORT[b['source']]}→{PRODUCT_SHORT[b['target']]} {b['requested_per_day']}/d ({b['median_converted_units']:g})"
   gain=f"{b['median_gross_margin_delta']:+,.0f}"
  cv=row['leave_one_game_out']
  held=(f"{cv['median_margin_delta']:+,.0f} / {cv['positive_cases']}/{cv['n_events']}" if cv else '—')
  lines.append(f"| {name} | {row['events']} ({row['under2500_events']}) | {demand} | {best} | {gain} | {held} |")
 lines += ['',
  '`Δ` is actual minus tape store. Positive means more town drain, negative less. The parenthesized unit count is the median actually converted from that reveal through season end; source stock can limit it below the requested rate. Margin changes are coins relative to unchanged replay, with both farms repriced; they are not recoverable profit estimates. The free-conversion arm and its q were chosen on the same games, so its displayed median is optimistic. Leave-one-game-out selection is a stricter stability check, but several pairs have only 1–3 cases, the cohort contains only losses, and events from one game share their future market. Full per-case and per-q curves are in `results/fresh/store_mismatch_shift_20260923/conversion/`; product addition/discard screens, which proved too unconstrained to select production amounts, are in `headroom_active/`.','',
  '## Feasible, small change tested in a complete game','',
  'The registered tape 109740300 milk-to-wool care edit was evaluated over all eight subsets of its three eligible days (17, 19, 21), with the live m1 agent and recorded opponent replayed for the full season. In the discovery case, **day 17 alone was best among these eight**: +1 wool, −1 milk harvested; our cash +229, opponent cash −8, competitive margin **+237**. The prior three-day edit gave only +88 margin. Day 19 or 21 alone removed one milk but produced no extra wool and raised opponent cash, so the exact engine rejected those added edits. This is a finite local optimum for one route and one world, not a general optimum or a validated policy. The baseline source and earlier before/after full replays are unchanged. The [new back-to-back replay](../viz/tape-109740300-before-after-d17.html) shows the day-17-only change against the same original baseline.','',
  'The day-17-only source and result are registered as a **diagnostic-only** candidate in `data/tape_variants/109740300-milk-care-to-wool-d17-diagnostic.json`. The next production test should construct similarly small, physically feasible route/cohort edits for the recurring strawberry↔tomato, wheat↔carrot, and egg/milk/wool mismatches. A shift should advance only if it improves full-game competitive margin across held-out worlds including wins. No broad routing or production policy was promoted from this screen.','',
  'Reproduce: `scripts/audit_store_mismatch_pairs.py`, `scripts/screen_store_shift_headroom.py`, `scripts/screen_store_conversion.py`, `scripts/optimize_tape_care_grid.py`, `scripts/build_care_d17_replays.py`, then `scripts/report_store_conversion.py`. Check with `scripts/check_store_mismatch_shift.py` and `scripts/check_care_d17_replays.cjs`. The exact pair/event rows and all product prices are in `active_store_pairs.json`; the source for the eight-arm care test is in `care_grid/`.']
 (ROOT/'docs/store_mismatch_production_shift.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
 print(json.dumps({'pairs':len(summaries),'events':audit['counts']['store_substitution_events'],
                   'mixed_sign_pairs':sum(x['best_free_conversion'] is not None for x in summaries),
                   'cv_positive_pairs':sum(x['leave_one_game_out'] is not None and x['leave_one_game_out']['median_margin_delta']>0 for x in summaries)}))


if __name__=='__main__':main()

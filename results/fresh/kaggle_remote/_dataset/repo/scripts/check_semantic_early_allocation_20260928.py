"""Read-only D6--10 allocation and paid-backlog audit of completed v4 games."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

import semantic_strategy_policy_20260928 as P

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_strategy_20260928'


def stock(private):
    result=Counter(private.get('shed',{}))
    for inv in private.get('inventories',[]):result.update(inv)
    return result


def delta(a,b):return {k:v-a.get(k,0) for k,v in b.items() if v-a.get(k,0)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',default='strategy_v4_modern4_finance')
    parser.add_argument('--label',default='v4');args=parser.parse_args()
    rows=[];inputs={}
    folder=BASE/'runs'/args.candidate/'development/live'
    for path in sorted(folder.glob('live-*.json')):
        if path.name.endswith('.actions.json'):continue
        raw=json.loads(path.read_text());assert raw['completed'] and raw['ledger_verified']
        seat=int(raw['case']['seat']);snaps={v['day']:v['current_observation'] for v in raw['diagnostics'][seat]}
        plans={v['day']:v for v in raw['final_diagnostics'][str(seat)]}
        actions_path=path.with_suffix('.actions.json');actions=json.loads(actions_path.read_text())[seat]
        for p in (path,actions_path):inputs[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
        for day in range(6,11):
            start=snaps[day];end=snaps[day+1];plan=plans[day]['realized_plan']
            dawnanimals=Counter(cell['animal'] for line in start['own_farm']['tiles'] for cell in line
                                if isinstance(cell,dict) and cell.get('animal'))
            pstart=start['private'];pend=end['private'];stock0=stock(pstart);stock1=stock(pend)
            births=Counter();newanimals=Counter()
            for line in end['own_farm']['tiles']:
                for cell in line:
                    if not isinstance(cell,dict):continue
                    if cell.get('crop') and cell.get('planted_day')==day:births[cell['crop']]+=1
                    if cell.get('animal') and cell.get('placed_day')==day:newanimals[cell['animal']]+=1
            spend=delta(raw['daily'][seat][day]['spend'],raw['daily'][seat][day+1]['spend'])
            revenue=delta(raw['daily'][seat][day]['revenue'],raw['daily'][seat][day+1]['revenue'])
            pendingplants={sp:max(0,n-births[sp]) for sp,n in plan['plant_counts'].items() if n>births[sp]}
            pendinganimals={sp:max(0,n-newanimals[sp]) for sp,n in plan['animal_add_counts'].items() if n>newanimals[sp]}
            paidplants={sp:min(n,pend['seeds'].get(sp,0)) for sp,n in pendingplants.items()}
            paidanimals={sp:min(n,stock1[sp]) for sp,n in pendinganimals.items()}
            unboughtseeds={sp:n-paidplants[sp] for sp,n in pendingplants.items() if n>paidplants[sp]}
            buyseed=Counter();buyanimals=Counter();seedhours=[];animalhours=[]
            for hour,action in enumerate(actions[day*24:(day+1)*24]):
                for order in action.get('market',[]):
                    if order[0]=='BUY_SEED':buyseed[order[1]]+=int(order[2]);seedhours.append(dict(hour=hour,species=order[1],count=int(order[2])))
                    if order[0]=='BUY_ANIMAL':buyanimals[order[1]]+=int(order[2]);animalhours.append(dict(hour=hour,species=order[1],count=int(order[2])))
            successes_seeds={sp:int(spend.get('BUY_SEED:'+sp,0)//v['seed']) for sp,v in P.CROPS.items()}
            successes_animals={sp:int(spend.get('BUY_ANIMAL:'+sp,0)//v['cost']) for sp,v in P.ANIMALS.items()}
            rows.append(dict(case=raw['case']['id'],day=day,cash_start=start['own_farm']['money'],cash_end=end['own_farm']['money'],
                dawn_animals=dict(dawnanimals),planned_hands=plan['hands'],
                planned=plan,actual_births=dict(births),actual_animal_placements=dict(newanimals),spend=spend,revenue=revenue,
                unfilled_plants=pendingplants,paid_unfilled_plants=paidplants,unfilled_animals=pendinganimals,paid_unfilled_animals=paidanimals,
                unbought_seeds=unboughtseeds,unbought_seed_cost=sum(n*P.CROPS[s]['seed'] for s,n in unboughtseeds.items()),
                seeds_end=pend['seeds'],animals_end_held={s:stock1[s] for s in P.ANIMALS if stock1[s]},
                held_animal_value=sum(stock1[s]*P.ANIMALS[s]['cost'] for s in P.ANIMALS),
                seed_orders=seedhours,animal_orders=animalhours,
                seed_orders_all_succeeded=all(buyseed[s]==successes_seeds[s] for s in P.CROPS),
                animal_orders_all_succeeded=all(buyanimals[s]==successes_animals[s] for s in P.ANIMALS),
                seed_purchases=successes_seeds,animal_purchases=successes_animals,
                land_unlock=plans[day].get('observed_land_unlock'),financing=plans[day].get('early_financing',[])))
    assert len(rows)==40
    totals={field:dict(sum((Counter(r[field]) for r in rows),Counter())) for field in
            ('actual_births','actual_animal_placements','unfilled_plants','paid_unfilled_plants','unfilled_animals','paid_unfilled_animals','unbought_seeds')}
    summary=dict(days=len(rows),totals=totals,
        days_unfilled_plants=sum(bool(r['unfilled_plants']) for r in rows),
        days_with_unbought_seeds_and_held_animals=sum(bool(r['unbought_seeds']) and r['held_animal_value']>0 for r in rows),
        days_missing_seed_cost_covered_by_held_animals=sum(bool(r['unbought_seeds']) and r['held_animal_value']>=r['unbought_seed_cost'] for r in rows),
        all_animal_orders_succeeded_days=sum(r['animal_orders_all_succeeded'] for r in rows),
        all_seed_orders_succeeded_days=sum(r['seed_orders_all_succeeded'] for r in rows),
        confirmed_late_animal_buys=sum(o['count'] for r in rows if r['animal_orders_all_succeeded'] for o in r['animal_orders'] if o['hour']>=20),
        confirmed_late_seed_buys=sum(o['count'] for r in rows if r['seed_orders_all_succeeded'] for o in r['seed_orders'] if o['hour']>=20))
    out=dict(purpose=__doc__,candidate=args.candidate,input_hashes=inputs,summary=summary,rows=rows,limitations=[
        'No hourly observations were retained in v4; financing logs are only hours when the helper released products.',
        'Successful daily purchases are independently obtained from ledger spend; order timing is called confirmed only when all requested daily purchases succeed.',
        'Unfilled jobs use next morning birth identities; observed current cohorts rather than order counts establish completion.',
        'Paid backlog is execution evidence, not proof that a particular routing or funding change would improve profit.'])
    path=BASE/f'early_allocation_{args.label}_diagnostic.json';path.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(path=str(path),summary=summary),indent=2))


if __name__=='__main__':main()

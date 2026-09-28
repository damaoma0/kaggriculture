"""Read-only accounting of the declared fresh-four V13/canonical V9-lite smoke.

Never fits models or imports either agent. Fresh cases remain evaluation data.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from audit_kb115lt2_v13_animal_quantities_20260928 import animals_from_engine, side_audit, sha, ENGINE
from diagnose_v8_daily_product_flow_20260928 import animal_action_trace, flat

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path(r'C:\Users\xyygl\Documents\kaggriculture')
SOURCE = MAIN/'results/fresh/semantic_strategy_20260928/fresh_smokes/v13_canonical_v9lite_fresh4_v1'


def hire_count(spend):
    # Official default multiplier is one; the frozen harness uses the default.
    a,b,total=1,1,0
    for n in range(31):
        if total == spend:
            return n
        total += a;a,b=b,a+b
    raise AssertionError(('Daily HIRE ledger does not match engine Fibonacci prices',spend))


def side(game,actions,seat,animals):
    ledger=game['daily'][seat][-1];revenue=ledger['revenue'];spend=ledger['spend']
    animal=side_audit(game,actions,seat,animals)
    days=[]
    for day in range(30):
        start,end=game['daily'][seat][day:day+2]
        obs=game['diagnostics'][seat][day]['current_observation'];tiles=flat(obs)
        wage=end['spend'].get('HIRE',0)-start['spend'].get('HIRE',0)
        land=end['spend'].get('BUY_LAND',0)-start['spend'].get('BUY_LAND',0)
        se=[t for i,t in enumerate(tiles) if i%10>=5 and i//10>=5]
        days.append(dict(day=day,cash=start['money'],actual_hires=hire_count(wage),wages=wage,land_spend=land,
            unlocked=list(obs['own_farm']['unlocked_quadrants']),fourth_quadrant_dawn_assets=dict(Counter(t.get('crop',t.get('animal',t.get('kind','EMPTY'))) for t in se)),
            daily_revenue=sum(end['revenue'].values())-sum(start['revenue'].values()),
            daily_spend=sum(end['spend'].values())-sum(start['spend'].values())))
    assert ledger['money'] == game['daily'][seat][0]['money']+sum(revenue.values())-sum(spend.values())
    early_exits=[]
    if seat==game['case']['seat']:
        traces=animal_action_trace(game,actions,seat)['days']
        hourly={r['step']:r for r in game['early_window_audit']}
        diag={r['day']:r for r in game['final_diagnostics'][str(seat)]}
        for ex in animal['exits']:
            if ex['absent_dawn']>ex['birth']+animals[ex['species']]['first_yield_day']:
                continue
            rows=[]
            for d in range(ex['birth'],ex['absent_dawn']):
                for cmd in traces[d]['commands']:
                    if cmd['tile']!=ex['tile'] or cmd['command'][0] not in ('PLACE','FEED','CARE','HARVEST','COLLECT_FERTILIZER'):
                        continue
                    snapshot=hourly.get(d*24+cmd['hour']);inv=snapshot['private']['inventories'] if snapshot else []
                    rows.append(dict(day=d,**cmd,carried_wheat_before=inv[cmd['unit']].get('WHEAT',0) if cmd['unit']<len(inv) else None))
            early_exits.append(dict(exit=ex,actual_visits=rows,
                admitted_retirements={str(d):diag[d].get('retirements',[]) for d in range(ex['birth'],ex['absent_dawn']) if d in diag}))
    return dict(final_cash=ledger['money'],revenue_total=sum(revenue.values()),spending_total=sum(spend.values()),
        spending=spend,products={p:dict(collected=ledger['physical'].get('produced:'+p,0),sold=ledger['sold_units'].get(p,0),revenue=revenue.get(p,0),
            mean_sale_price=revenue.get(p,0)/ledger['sold_units'][p] if ledger['sold_units'].get(p) else None) for p in revenue},
        physical=ledger['physical'],daily=days,actual_hired_hand_days=sum(d['actual_hires'] for d in days),
        actual_hires_histogram=dict(Counter(d['actual_hires'] for d in days)),animal_audit=animal,early_exit_execution=early_exits)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=SOURCE)
    parser.add_argument('--output',type=Path,default=ROOT/'results/fresh/semantic_kb115lt2_recovery/v13_v9fresh4_accounting.json')
    args=parser.parse_args();manifest=json.loads((args.source/'manifest.json').read_text());report=json.loads((args.source/'report.json').read_text())
    assert len(manifest['cases'])==4 and report['planned']==report['completed']==4
    assert all(r['technical_valid'] for r in report['rows'])
    animals=animals_from_engine();rows=[];hashes={str(p):sha(p) for p in (args.source/'manifest.json',args.source/'report.json',ENGINE)}
    for case in manifest['cases']:
        p=args.source/'results'/(case['id']+'.json');ap=p.with_suffix('.actions.json');hashes.update({str(x):sha(x) for x in (p,ap)})
        game=json.loads(p.read_text());actions=json.loads(ap.read_text());s=case['seat']
        assert game['case']==case and game['completed'] and game['eligible'] and game['ledger_verified']
        sides={role:side(game,actions,z,animals) for role,z in (('own',s),('opponent',1-s))}
        a,b=sides['own'],sides['opponent'];product_delta={}
        for product in set(a['products'])|set(b['products']):
            aa,bb=[r['products'].get(product,{'collected':0,'sold':0,'revenue':0,'mean_sale_price':None}) for r in (a,b)]
            product_delta[product]={k:aa[k]-bb[k] for k in ('collected','sold','revenue')}
        rev=a['revenue_total']-b['revenue_total'];cost=a['spending_total']-b['spending_total']
        assert game['margin']==rev-cost
        rows.append(dict(case=case,margin=game['margin'],shops=game['shops'],sides=sides,
            revenue_difference=rev,spending_difference=cost,product_differences=product_delta,
            spending_differences={k:a['spending'].get(k,0)-b['spending'].get(k,0) for k in set(a['spending'])|set(b['spending'])},
            canonical_opponent_diagnostics=game['final_diagnostics'][str(1-s)]))
    output=dict(scope=__doc__,new_games=0,source_hashes=hashes,script_sha256=sha(Path(__file__)),
        helper_sha256=sha(ROOT/'scripts/audit_kb115lt2_v13_animal_quantities_20260928.py'),
        trace_helper_sha256=sha(ROOT/'scripts/diagnose_v8_daily_product_flow_20260928.py'),rows=rows,
        limitations=[
            'These four fresh smoke cases are not added to training or used to fit case-specific rules.',
            'Revenue minus spending is observed accounting. Removing land/hands/animals also changes output, timing and market prices; these costs are not free recoverable savings.',
            'V9-lite override counts measure its additional value selector only. Native donor selection, routing and maintenance can change even when the extra override count is zero.',
            'Crop produced: ledger fields mean collection, not biological growth. Animal biological output is separately reconstructed from actual public cohorts and the official refresh order.',
            'Daily hire counts are uniquely inverted from successful HIRE spending using the official default Fibonacci wage schedule. No purchase quantity is inferred from requested orders.'
        ])
    args.output.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(args.output),sha256=sha(args.output),rows=[dict(case=r['case']['id'],margin=r['margin'],revenue=r['revenue_difference'],spend=r['spending_difference'],
        hand_days=[r['sides'][s]['actual_hired_hand_days'] for s in ('own','opponent')]) for r in rows]),indent=2))


if __name__=='__main__':
    main()

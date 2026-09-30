"""Arithmetic audit and compact report for already-solved tape-gap pilot plans."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
from cumulative_engine_profiles import ENGINE

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_gap_plans/pilot'

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,x): p.write_text(json.dumps(x,indent=2),encoding='utf-8')

def audit_plan(case, mode, wrapper):
    plan=wrapper['plan']; snap=case['snapshot']; stock=Counter(WHEAT=snap['wheat'],FERTILIZER=snap['fertilizer']);stock.update(plan['procurement'])
    seeds=Counter(snap['seeds']); planted=Counter(); animals=Counter(); failures=[]
    max_land=max_work=0.0
    for day,row in plan['daily'].items():
        if row['land_used']>snap['land_capacity']: failures.append([day,'land'])
        if row['workload']>row['action_capacity_after_travel']: failures.append([day,'work'])
        max_land=max(max_land,row['land_used']); max_work=max(max_work,row['workload']/max(1,row['action_capacity_after_travel']))
        planted.update(row['plant']);animals.update(row['buy_animal']);stock.update({p:q for p,q in row['expected_output'].items() if p in stock});stock.subtract(row['expected_inputs'])
        if stock['WHEAT']<0 or stock['FERTILIZER']<0: failures.append([day,'stock',dict(stock)])
    for p,n in planted.items():
        if n>seeds[p]+snap['seed_purchase_budget'][p]:failures.append(['seed',p,n])
    for a,n in animals.items():
        if n>snap['animal_purchase_budget'][a]:failures.append(['animal',a,n])
    seed_cost=sum(n*ENGINE.CROPS[p]['seed'] for p,n in planted.items());animal_cost=sum(n*ENGINE.ANIMALS[a]['cost'] for a,n in animals.items())
    procurement_cost=sum(plan['procurement'].get(p,0)*snap['resource_prices'].get(p,ENGINE.MARKET_PARAMS[p]['base']) for p in plan['procurement'])
    hire_cost=plan['labor']['total_hire_cost']; total_cost=seed_cost+animal_cost+procurement_cost+hire_cost
    if total_cost>snap['cash']+1e-6:failures.append(['cash',total_cost,snap['cash']])
    for t in plan['target_deviations']:
        actual=sum(r['expected_output'].get(t['target']['product'],0) for d,r in plan['daily'].items() if int(d)<t['target']['day'])
        if actual!=t['planned_remaining_units'] or actual+t['under']-t['over']!=t['requested_remaining_units']: failures.append(['target',t])
    groups=Counter(int(s['decision'].split('_')[3]) for s in plan['selections'] if s['decision'].startswith('keep_existing_'))
    incumbents=sum(bool(isinstance(t,dict) and (t.get('crop') or t.get('animal'))) for row in snap['tiles'] for t in row)
    if len(groups)!=incumbents or set(groups.values())!={1}:failures.append(['existing_assets',len(groups),incumbents,dict(groups)])
    costs={'seed_cost':seed_cost,'animal_cost':animal_cost,'hire_cost':hire_cost,'procurement_cost':procurement_cost,'total_cost':total_cost,'cash':snap['cash']}
    wrapper.setdefault('status',{})['cost_certificate']=costs
    wrapper['status']['arithmetic_audit']='passed' if not failures else 'failed'
    return dict(mode=mode,passed=not failures,failures=failures,cost=costs,max_land=max_land,max_workload_ratio=max_work,
                optimal=plan['solver']['optimal'],target_mae=sum(abs(t['planned_remaining_units']-t['requested_remaining_units']) for t in plan['target_deviations'])/len(plan['target_deviations']),
                next3_mae=(lambda xs: sum(xs)/len(xs) if xs else None)([abs(t['planned_remaining_units']-t['requested_remaining_units']) for t in plan['target_deviations'] if t['target']['day']==case['day']+3]))

def main():
    rows=[]
    for path in sorted(OUT.glob('*_s*_d*.json')):
        case=read(path)
        for mode,wrapper in case['modes'].items(): rows.append(dict(file=path.name,episode=case['episode'],day=case['day'],**audit_plan(case,mode,wrapper)))
        write(path,case)
    by=defaultdict(list)
    for r in rows:by[r['day'],r['mode']].append(r)
    compact=[]
    for (day,mode),rs in sorted(by.items()):compact.append(dict(day=day,mode=mode,n=len(rs),requested_target_mae=sum(r['target_mae'] for r in rs)/len(rs),next3_requested_target_mae=sum(r['next3_mae'] for r in rs if r['next3_mae'] is not None)/max(1,sum(r['next3_mae'] is not None for r in rs)),optimal=sum(r['optimal'] for r in rs),arithmetic_passed=sum(r['passed'] for r in rs)))
    audit={'plans_checked':len(rows),'passed':all(r['passed'] for r in rows),'all_solver_optimal':all(r['optimal'] for r in rows),'certificates':rows,'scope':'Arithmetic aggregate audit. Target slack is target projection error, not a resource infeasibility or routing result.'}
    write(OUT/'certificate_audit.json',audit);write(OUT/'compact_summary.json',{'per_day_mode':compact,'note':audit['scope']})
    print(json.dumps({'plans_checked':len(rows),'passed':audit['passed'],'all_solver_optimal':audit['all_solver_optimal'],'per_day_mode':compact},indent=2))
if __name__=='__main__':main()

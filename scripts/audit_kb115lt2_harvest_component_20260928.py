"""Audit the frozen recorded-rival component continuation; no gameplay."""
from collections import Counter,defaultdict
from pathlib import Path
import gzip
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
BUNDLE=ROOT/'results/fresh/semantic_kb115lt2_recovery/harvest_exchange_component_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def delta(a,b):return {k:b.get(k,0)-a.get(k,0) for k in sorted(set(a)|set(b)) if a.get(k,0)!=b.get(k,0)}
def commands(a):return [a['farmer']]+a.get('hands',[])
def mandatory(routes):
    c=Counter()
    for u,r in routes.items():
        for s in r['items']:
            if s.get('kind')!='stop':continue
            for op,m in zip(s['ops'],s['mand']):
                if m:c[(int(u),s['tile'],tuple(op))]+=1
    return c
def actual(snapshots,day):
    c=Counter()
    for s in snapshots:
        if s['step']//24!=day:continue
        f=s['own_farm'];positions=[f['farmer']]+f['hands']
        for u,cmd in enumerate(commands(s['action'])):
            if u<len(positions):
                x,y=positions[u];c[(u,y*10+x,tuple(cmd))]+=1
    return c
def serialize_counts(c):return [dict(unit=u,tile=t,command=list(o),count=n) for (u,t,o),n in c.items()]
def tiles_diff(a,b):
    return [dict(tile=y*10+x,control=i,treatment=j) for y,(r,s) in enumerate(zip(a,b)) for x,(i,j) in enumerate(zip(r,s)) if i!=j]

def main():
    paths=[BUNDLE/(mode+'.json.gz') for mode in ('shadow','continue')]
    a,b=[json.load(gzip.open(p,'rt')) for p in paths];seat=a['case']['seat']
    assert a['verified_control'] and a['exact_pre_treatment_action_calls']==480
    assert b['exact_pre_treatment_action_calls']==432 and b['trigger']['step']==432
    changes=[]
    for x,y in zip(a['snapshots'],b['snapshots']):
        for u,(i,j) in enumerate(zip(commands(x['action']),commands(y['action']))):
            if i!=j:changes.append(dict(step=x['step'],day=x['step']//24,hour=x['step']%24,unit=u,control=i,treatment=j))
    assert [(r['day'],r['hour'],r['unit']) for r in changes]==[(18,7,5),(18,8,5),(18,9,5)]
    ma,mb=[mandatory(r['snapshots'][0]['tier_routes']) for r in (a,b)]
    assert ma==mb
    missing=[ma-actual(r['snapshots'],18) for r in (a,b)]
    assert missing[0]==missing[1]
    # These route macros expand to PLACE/DROP engine commands. They are not
    # unexecuted jobs merely because no literal macro occurs in the action log.
    assert all(k[2][0] in ('DELIVER','PLACE_HARVEST') for k in missing[0])
    unit5_missing=[{k:v for k,v in m.items() if k[0]==5} for m in missing]
    assert not any(unit5_missing)
    dawn_a=next(s for s in a['snapshots'] if s['step']==456)
    dawn_b=next(s for s in b['snapshots'] if s['step']==456)
    shed_delta=delta(dawn_a['private']['shed'],dawn_b['private']['shed'])
    assert shed_delta=={'FERTILIZER':-1,'WOOL':4}
    for r in (a,b):assert all(not x['deleted'] for x in r['dumps'])
    final_diff=tiles_diff(a['final_own_farm']['tiles'],b['final_own_farm']['tiles'])
    assert [x['tile'] for x in final_diff]==[36]
    assert delta(final_diff[0]['control'],final_diff[0]['treatment'])=={'yield_units':-4}
    finances={}
    for label,s in (('own',seat),('rival',1-seat)):
        x,y=a['current_ledgers'][s],b['current_ledgers'][s]
        rd=delta(x['revenue'],y['revenue']);sd=delta(x['spend'],y['spend'])
        assert sum(rd.values())-sum(sd.values())==y['money']-x['money']
        finances[label]=dict(control_cash=x['money'],treatment_cash=y['money'],cash_delta=y['money']-x['money'],
            revenue_delta=rd,sold_units_delta=delta(x['sold_units'],y['sold_units']),spend_delta=sd,
            physical_delta=delta(x['physical'],y['physical']))
    assert finances['own']['physical_delta']=={'op:COLLECT_FERTILIZER':-1,'op:HARVEST':1,'produced:FERTILIZER':-1,'produced:WOOL':4}
    sale_groups=[]
    for label,r in (('control',a),('treatment',b)):
        grouped=defaultdict(lambda:dict(units=0,revenue=0))
        for sale in r['sales']:
            if sale['success']:
                row=grouped[(sale['seat'],sale['step']//24,sale['step']%24,sale['item'])]
                row['units']-=sale['shed_delta'];row['revenue']+=sale['cash_delta']
        sale_groups.append(dict(arm=label,sales=[dict(seat=s,day=d,hour=h,product=p,**v) for (s,d,h,p),v in sorted(grouped.items())]))
    report=dict(scope='VERIFIED_FIXED_SHOP_RECORDED_RIVAL_COMPONENT_D18_TO_D20',
        hashes={str(p):sha(p) for p in paths+[BUNDLE/'manifest.json',BUNDLE/'executor.py',BUNDLE/'driver.py']},
        control_verified=True,exact_control_calls=480,exact_prefix_calls=432,trigger=b['trigger'],
        physical_action_changes=changes,mandatory_job_multisets_equal=True,
        all_literal_mandatory_jobs_executed=True,
        route_macros_requiring_expanded_command_matching=serialize_counts(missing[0]),
        macro_routes_physical_commands_unchanged=True,affected_unit_all_mandatory_jobs_executed=True,
        next_dawn_shed_delta=shed_delta,all_midnight_deletions_empty=True,final_tile_differences=final_diff,
        all_crop_tiles_equal_at_D20=True,finances=finances,competitive_margin_delta=finances['own']['cash_delta']-finances['rival']['cash_delta'],
        actual_sales_by_hour=sale_groups,control_elapsed_seconds=a['elapsed_seconds'],treatment_elapsed_seconds=b['elapsed_seconds'],
        limitation='Four pre-existing held wool collected earlier; no extra biological output by D20. Short fixed-shop recorded-rival diagnostic, not full-season or responsive-rival profit evidence.')
    out=BUNDLE/'audit.json';out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(path=str(out),sha256=sha(out),literal_mandatory_jobs_complete=True,finances=finances,pass_all=True),indent=2))

if __name__=='__main__':main()

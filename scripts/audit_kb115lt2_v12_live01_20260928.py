"""Read-only accounting of the natural V8/V12 live01 development recordings."""
from collections import Counter
from pathlib import Path
import hashlib
import json

WORK=Path(__file__).resolve().parents[1]
MAIN=Path(r'C:\Users\xyygl\Documents\kaggriculture')
STUDY=MAIN/'results/fresh/semantic_strategy_20260928'
OUT=WORK/'results/fresh/semantic_kb115lt2_recovery/v12_live01_natural_trace.json'
VERSIONS=['strategy_v8_kb115lt2_readiness','strategy_v12_kb115lt2_runtime_fast']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def delta(a,b):return {k:b.get(k,0)-a.get(k,0) for k in sorted(set(a)|set(b)) if b.get(k,0)!=a.get(k,0)}
def commands(action):return [action.get('farmer',['PASS'])]+action.get('hands',[])
def animals(row,day):
    return {i*10+j:t for i,r in enumerate(row['diagnostics'][row['case']['seat']][day]['current_observation']['own_farm']['tiles'])
        for j,t in enumerate(r) if isinstance(t,dict) and t.get('animal')}
def animal_identity(t):return (t.get('animal'),t.get('placed_day')) if t else None
def unit_state(h,u):
    return dict(position=h['farmer'] if u==0 else h['hands'][u-1],inventory=h['private']['inventories'][u])
def product_table(a,b):
    goods=sorted(set(a['revenue'])|set(b['revenue'])|{k.split(':')[1] for k in a['physical'] if k.startswith('produced:')})
    return {g:dict(v8=dict(collected=a['physical'].get('produced:'+g,0),sold=a['sold_units'].get(g,0),revenue=a['revenue'].get(g,0)),
        v12=dict(collected=b['physical'].get('produced:'+g,0),sold=b['sold_units'].get(g,0),revenue=b['revenue'].get(g,0)),
        delta=dict(collected=b['physical'].get('produced:'+g,0)-a['physical'].get('produced:'+g,0),
            sold=b['sold_units'].get(g,0)-a['sold_units'].get(g,0),revenue=b['revenue'].get(g,0)-a['revenue'].get(g,0))) for g in goods}

def main():
    paths=[STUDY/'runs'/v/'development/live/live-01.json' for v in VERSIONS]
    rows=[json.loads(p.read_text()) for p in paths]
    actions=[json.loads(p.with_suffix('.actions.json').read_text()) for p in paths]
    a,b=rows;seat=a['case']['seat'];assert a['case']==b['case']
    hourly=[{h['step']:h for h in row['early_window_audit']} for row in rows]
    repeat_pickups=[]
    for step in range(145,263):
        old,new=commands(actions[0][seat][step]),commands(actions[1][seat][step])
        prev=commands(actions[1][seat][step-1])
        for u,cmd in enumerate(new):
            if cmd[:2]!=['PICKUP','WHEAT'] or u>=len(prev) or prev[u][:2]!=['PICKUP','WHEAT'] or (u<len(old) and old[u]==cmd):continue
            h,n=hourly[1][step],hourly[1][step+1]
            if u>=len(h['private']['inventories']):continue
            repeat_pickups.append(dict(step=step,day=step//24,hour=step%24,unit=u,previous_action=prev[u],v8_action=old[u] if u<len(old) else None,
                v12_action=cmd,shed_wheat_before=h['private']['shed'].get('WHEAT',0),before=unit_state(h,u),after=unit_state(n,u),
                actual_wheat_received=n['private']['inventories'][u].get('WHEAT',0)-h['private']['inventories'][u].get('WHEAT',0)))
    phase=[]
    for day in (8,9,10,12,15,18,21,24,30):
        entry=dict(day=day)
        for key,s in (('own',seat),('rival',1-seat)):
            x,y=a['daily'][s][day],b['daily'][s][day]
            entry[key]=dict(cash_delta=y['money']-x['money'],physical_delta=delta(x['physical'],y['physical']),revenue_delta=delta(x['revenue'],y['revenue']),spend_delta=delta(x['spend'],y['spend']),sold_delta=delta(x['sold_units'],y['sold_units']))
        phase.append(entry)
    cohorts=[]
    for day in range(6,30):
        aa,bb=animals(a,day),animals(b,day)
        differences={str(t):dict(v8=aa.get(t),v12=bb.get(t)) for t in sorted(set(aa)|set(bb)) if aa.get(t)!=bb.get(t)}
        identity_differences={str(t):dict(v8=animal_identity(aa.get(t)),v12=animal_identity(bb.get(t))) for t in sorted(set(aa)|set(bb)) if animal_identity(aa.get(t))!=animal_identity(bb.get(t))}
        if differences:cohorts.append(dict(day=day,animal_state_differences=differences,cohort_identity_differences=identity_differences))
    byday=[]
    for day in range(6,30):
        physical_actions=[]
        for s in range(day*24,min((day+1)*24,719)):
            aa,bb=commands(actions[0][seat][s]),commands(actions[1][seat][s])
            for u in range(max(len(aa),len(bb))):
                x=aa[u] if u<len(aa) else None;y=bb[u] if u<len(bb) else None
                if x!=y:physical_actions.append(dict(step=s,unit=u,v8=x,v12=y))
        if physical_actions:byday.append(dict(day=day,changes=physical_actions))
    financial={}
    for role,s in (('own',seat),('rival',1-seat)):
        x,y=a['daily'][s][30],b['daily'][s][30]
        rev=sum(y['revenue'].values())-sum(x['revenue'].values());spend=sum(y['spend'].values())-sum(x['spend'].values())
        assert rev-spend==y['money']-x['money']
        financial[role]=dict(v8_cash=x['money'],v12_cash=y['money'],cash_delta=y['money']-x['money'],revenue_delta=rev,spend_delta=spend,
            products=product_table(x,y),spending=delta(x['spend'],y['spend']),physical_delta=delta(x['physical'],y['physical']))
    first_differences={}
    for role,s in (('own',seat),('rival',1-seat)):
        first_differences[role]=next((dict(step=i,day=i//24,hour=i%24,v8=x,v12=y) for i,(x,y) in enumerate(zip(actions[0][s],actions[1][s])) if x!=y),None)
    result=dict(scope='READ_ONLY_NATURAL_SHOP_DEVELOPMENT_TRACE',case=a['case'],
        sources={str(p):sha(p) for p in paths+ [p.with_suffix('.actions.json') for p in paths]},
        candidate_manifests=[r['candidate_manifest_sha256'] for r in rows],
        no_new_games=True,first_differences=first_differences,
        shop_sequences=dict(v8=a['shops'],v12=b['shops']),shop_changes=[dict(reveal_day=(i+1)*3,v8=x,v12=y) for i,(x,y) in enumerate(zip(a['shops'],b['shops'])) if x!=y],
        repeated_pickups_observed=repeat_pickups,
        retry_evidence_limit='Saved logs do not retain internal retry audit. Consecutive extra pickup action and observed inventory receipt identify the actual visible effect; no unlogged admission reason is inferred.',
        finances=financial,phase=phase,cohort_differences=cohorts,own_action_differences_by_day=byday,
        retirement_intents={v:[dict(day=x['day'],retirements=x.get('retirements',[])) for x in r['final_diagnostics'][str(seat)] if x.get('retirements')] for v,r in zip(VERSIONS,rows)},
        caution='Shared-RNG shop sequences differ from D15. Full-season outcome is not an isolated retry profit effect; collected units are successful harvest/collection inventory gains, not new biological production.')
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(output=str(OUT),sha256=sha(OUT),pickups=repeat_pickups,finances={k:{j:v for j,v in r.items() if j not in ('products','physical_delta')} for k,r in financial.items()},phase=[dict(day=p['day'],own=p['own']['cash_delta'],rival=p['rival']['cash_delta']) for p in phase]),indent=2))

if __name__=='__main__':main()

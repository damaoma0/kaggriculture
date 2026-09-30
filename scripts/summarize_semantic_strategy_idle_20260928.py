"""Summarize parity-controlled route stalls and optional one-day BUY continuations."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/'results/fresh/semantic_strategy_20260928'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with gzip.open(p,'rt',encoding='utf-8') as f:return json.load(f)
def counts(farm):
    return dict(Counter(t.get('crop',t.get('animal',t.get('kind'))) for row in farm['tiles']
                        for t in row if isinstance(t,dict)))

def stalls(snapshots):
    result=[]
    for s in snapshots:
        state=s.get('state') or {};ctx=state.get('current_context')
        if not ctx or state.get('sd_tier'):continue
        action=s.get('executed_action',s.get('recorded_action'))
        commands=[action['farmer']]+action['hands']
        positions=[s['positions']['farmer']]+s['positions']['hands']
        inventories=s['private']['inventories'];routes=state.get('lower_routes',{})
        for unit,(cmd,pos,inv) in enumerate(zip(commands,positions,inventories)):
            route=routes.get(str(unit),[])
            if cmd!=['PASS'] or not route or type(route[0]) is not int:continue
            tile=route[0];task=ctx['tasks'].get(str(tile))
            if tile!=pos[1]*10+pos[0] or not task or not any(op[0]=='FEED' for op in task[0]) or inv.get('WHEAT',0):continue
            result.append(dict(hour=s['hour'],unit=unit,tile=tile,ops=task[0],own_inventory=inv,
                shed_wheat=s['private']['shed'].get('WHEAT',0),carried_wheat=sum(i.get('WHEAT',0) for i in inventories),
                global_demand_wheat=ctx['demand'].get('WHEAT',0),cash=s['cash'],market=action['market']))
    return result

def main():
    rows=[]
    for case in ('live-01','live-02'):
        path=STUDY/'idle_shadows_v5'/f'{case}-d10-10.json.gz';raw=read(path)
        blocked=stalls(raw['snapshots'])
        units={str(u):dict(hours=[r['hour'] for r in blocked if r['unit']==u],
                          tiles=sorted(set(r['tile'] for r in blocked if r['unit']==u)))
               for u in sorted(set(r['unit'] for r in blocked))}
        row=dict(case=raw['case'],source_sha256=raw['source_sha256'],actions_sha256=raw['actions_sha256'],
                 candidate_manifest_sha256=raw['candidate_manifest_sha256'],control_path=path.relative_to(ROOT).as_posix(),
                 control_sha256=sha(path),replay_cash_equal=raw['replay_cash_equal'],replay_ledger_equal=raw['replay_ledger_equal'],
                 exact_shadow_calls=raw['shadow_calls'],shadow_mismatches=len(raw['shadow_mismatches']),
                 blocked_pass_count=len(blocked),blocked_units=units,blocked_events=blocked)
        p=path.with_name(f'{case}-d10-route-wheat.json.gz')
        if p.exists():
            r=read(p);remaining=stalls(r['snapshots'])
            row['continuation']=dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),
                exact_shadow_prefix_calls=r['exact_shadow_prefix_calls'],first_trigger=r['trigger'],events=r['events'],
                requested_wheat=sum(e['buy'] for e in r['events']),remaining_blocked_pass_count=len(remaining),
                remaining_blocked_events=remaining,own_ledger_delta=r['own_ledger_delta'],
                baseline_end_cash=r['baseline_end_cash'],continuation_end_cash=r['continuation_end_cash'],
                baseline_end_counts=counts(r['baseline_end_farm']),continuation_end_counts=counts(r['continuation_end_farm']),
                max_post_trigger_call_seconds=max(t['seconds'] for t in r['call_timings'] if t['step']>=r['trigger']['step']),
                post_trigger_calls_over_one_second=sum(t['seconds']>1 for t in r['call_timings'] if t['step']>=r['trigger']['step']),
                elapsed_seconds=r['elapsed_seconds'])
        rows.append(row)
    payload=dict(scope='READ_ONLY_PARITY_AUDIT_AND_BOUNDED_COMPONENT_CONTINUATIONS',script_sha256=sha(Path(__file__)),
        helper_sha256=sha(ROOT/'scripts/semantic_strategy_route_wheat_20260928.py'),rows=rows,
        limitation='Two selected development failures. No new opponent calls and no full-season or profitability claim for the repair.')
    out=STUDY/'idle_route_wheat_diagnostic_summary.json'
    out.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(case=r['case']['id'],blocked=r['blocked_pass_count'],units=r['blocked_units'],
        continuation={k:v for k,v in r.get('continuation',{}).items() if k not in ('remaining_blocked_events','events','first_trigger')}) for r in rows],indent=2))
    print(out)

if __name__=='__main__':main()

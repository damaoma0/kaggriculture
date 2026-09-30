"""Read-only V7/V8 ledger, cohort-delay and matched early pickup evidence."""
from collections import Counter,deque
import hashlib
import json
from pathlib import Path
import semantic_strategy_policy_20260928 as P

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_strategy_20260928'
ARMS={'v7':'strategy_v7_blocks100_readiness','v8':'strategy_v8_kb115lt2_readiness'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def animal_metrics(game,seat):
    ledger=game['daily'][seat];queue={s:deque() for s in P.ANIMALS};placements=[];expected=Counter()
    snapshots={r['day']:r['current_observation'] for r in game['diagnostics'][seat]}
    for d in range(6,30):
        _,animals,_,_=P._cohorts(snapshots[d]['own_farm'],d)
        expected.update(P.output_calendar([],animals,d)[d])
    for d in range(29):
        for s,r in P.ANIMALS.items():
            n=int((ledger[d+1]['spend'].get('BUY_ANIMAL:'+s,0)-ledger[d]['spend'].get('BUY_ANIMAL:'+s,0))/r['cost'])
            queue[s].extend([d]*n)
        for row in snapshots[d+1]['own_farm']['tiles']:
            for t in row:
                if isinstance(t,dict) and t.get('animal') and t['placed_day']==d:
                    s=t['animal'];assert queue[s],(d,s,'placement without owned purchase')
                    bought=queue[s].popleft();placements.append(dict(species=s,purchase_day=bought,placement_day=d,lag_days=d-bought))
    actual={p:ledger[30]['physical'].get('produced:'+p,0)-ledger[6]['physical'].get('produced:'+p,0) for p in ('MILK','WOOL','EGG')}
    early=[r for r in placements if 6<=r['purchase_day']<=10]
    return dict(actual_harvest_d6_29=actual,expected_calendar_d6_29={p:expected[p] for p in actual},
        ratio={p:actual[p]/expected[p] if expected[p] else None for p in actual},
        early_purchased_placed=len(early),early_placements_delayed=sum(r['lag_days']>0 for r in early),
        early_animal_unit_days_delayed=sum(r['lag_days'] for r in early),early_delay_by_species={s:sum(r['lag_days'] for r in early if r['species']==s) for s in P.ANIMALS},
        purchased_unplaced_at_d29={s:list(q) for s,q in queue.items() if q},placements=placements)


def compare_sales(own,rival):
    products={}
    for p in sorted(set(own['sold_units'])|set(rival['sold_units'])):
        a=own['sold_units'].get(p,0);b=rival['sold_units'].get(p,0);ra=own['revenue'].get(p,0);rb=rival['revenue'].get(p,0)
        pa=ra/a if a else None;pb=rb/b if b else None
        products[p]=dict(ours=a,rival=b,revenue_difference=ra-rb,our_average_price=pa,rival_average_price=pb,
            quantity_component_at_rival_price=(a-b)*pb if pb is not None else None,
            timing_price_component=a*(pa-pb) if pa is not None and pb is not None else None)
    return products


def commands(action):return [action.get('farmer',['PASS'])]+action.get('hands',[])


def main():
    service_path=BASE/'service_audit_v7_v8.json';service=json.loads(service_path.read_text())
    groups={};sources={str(service_path.relative_to(ROOT)):sha(service_path)}
    for label,arm in ARMS.items():
        folder=BASE/'runs'/arm/'development/live';sg=service['groups'][str(folder.relative_to(ROOT)).replace('\\','/')]
        bycase={g['case']['id']:g for g in sg['games']};cases=[]
        for path in sorted(folder.glob('live-??.json')):
            sources[str(path.relative_to(ROOT))]=sha(path);g=json.loads(path.read_text());seat=g['case']['seat']
            a=g['daily'][seat][30];b=g['daily'][1-seat][30];sw=bycase[g['case']['id']]
            rev=sum(a['revenue'].values())-sum(b['revenue'].values());spend=sum(a['spend'].values())-sum(b['spend'].values())
            assert rev-spend==g['margin']
            exits=[e for e in sw['execution']['animal_exits'] if e['classification']=='no_matching_recorded_retirement']
            cases.append(dict(case=g['case']['id'],margin=g['margin'],shops=g['shops'],full_revenue_difference=rev,full_spending_difference=spend,
                spending_delta={k:a['spend'].get(k,0)-b['spend'].get(k,0) for k in sorted(set(a['spend'])|set(b['spend']))},
                sales=compare_sales(a,b),own_animals=animal_metrics(g,seat),rival_animals=animal_metrics(g,1-seat),
                unintended_exits=exits,early_unintended_exits=[e for e in exits if e['exit_day']<=10],
                service_counts=dict(committed_unfed_production=sum(r['committed'] and not r['fed'] and r['production'] for r in sw['service']),
                    committed_banked_bonus_lost=sum(r['lost_banked_bonus'] for r in sw['service'] if r['committed']),
                    newborn_committed_unfed=sum(r['newborn'] and r['committed'] and not r['fed'] for r in sw['service']))))
        aggregate={}
        for side in ('own_animals','rival_animals'):
            actual=Counter();expected=Counter()
            for c in cases:actual.update(c[side]['actual_harvest_d6_29']);expected.update(c[side]['expected_calendar_d6_29'])
            aggregate[side]=dict(actual=dict(actual),expected=dict(expected),ratio={p:actual[p]/expected[p] if expected[p] else None for p in actual},
                early_purchased_placed=sum(c[side]['early_purchased_placed'] for c in cases),
                early_placements_delayed=sum(c[side]['early_placements_delayed'] for c in cases),
                early_animal_unit_days_delayed=sum(c[side]['early_animal_unit_days_delayed'] for c in cases))
        groups[label]=dict(cases=cases,service_summary={k:v for k,v in sg['summary'].items() if k not in ('execution','own','rival','post_unlock_issued_commands')},aggregate=aggregate)
    # Match previous independently logged partial-pickup states without replaying
    # an engine or inferring a new tier cursor from action order alone.
    first=BASE/'partial_pickup_first_event_diagnostic.json';events=json.loads(first.read_text())['events'];sources[str(first.relative_to(ROOT))]=sha(first)
    matches=[]
    for ev in events:
        case=ev['case'];d=ev['day'];h=ev['hour'];step=ev['event'][0];unit=ev['event'][1]
        oldp=BASE/'runs/strategy_v5_blocks100_finance/development/live'/f'{case}.json'
        newp=BASE/'runs'/ARMS['v8']/'development/live'/f'{case}.json'
        old=json.loads(oldp.read_text());new=json.loads(newp.read_text());seat=new['case']['seat']
        opa=oldp.with_name(oldp.stem+'.actions.json');npa=newp.with_name(newp.stem+'.actions.json')
        oa=json.loads(opa.read_text());na=json.loads(npa.read_text())
        for p in (oldp,newp,opa,npa):sources[str(p.relative_to(ROOT))]=sha(p)
        snap0={r['step']:r for r in old['early_window_audit']};snap1={r['step']:r for r in new['early_window_audit']}
        prefix=[oa[s][:step+1]==na[s][:step+1] for s in (0,1)]
        sw=next(c for c in groups['v8']['cases'] if c['case']==case)
        row=dict(case=case,day=d,hour=h,unit=unit,v6_original_shortage_log=ev['event'],both_action_prefixes_equal_through_pickup=prefix,
            current_private_snapshot_equal=snap0[step+1]==snap1[step+1],v8_pickup_command=commands(na[seat][step])[unit],
            v8_next_command=commands(na[seat][step+1])[unit],v8_current_shed=snap1[step+1]['private']['shed'].get('WHEAT',0),
            v8_unit_inventory=snap1[step+1]['private']['inventories'][unit],later_same_unit_care_of_unfed=[])
        service_game=next(g for g in service['groups'][str((BASE/'runs'/ARMS['v8']/'development/live').relative_to(ROOT)).replace('\\','/')]['games'] if g['case']['id']==case)
        unfed={r['tile']:r for r in service_game['service'] if r['day']==d and r['committed'] and not r['fed']}
        unfed.update({r['tile']:r for r in sw['unintended_exits'] if r['exit_day']==d})
        for st in range(step+1,(d+1)*24):
            snap=snap1[st];cmd=commands(na[seat][st])[unit]
            if cmd[:1]!=['CARE']:continue
            pos=snap['farmer'] if unit==0 else snap['hands'][unit-1];tile=pos[1]*10+pos[0]
            if tile in unfed:row['later_same_unit_care_of_unfed'].append(dict(hour=st%24,tile=tile,wheat=snap['private']['inventories'][unit].get('WHEAT',0),animal=unfed[tile].get('animal',unfed[tile].get('species'))))
        matches.append(row)
    result=dict(scope=__doc__,new_games=0,input_hashes=sources,groups=groups,first_partial_pickup_prefix_matches=matches,
        limitations=['Natural shops change in7/8 V7/V8 pairs; no isolated causal margin claim.',
            'FIFO purchase-to-placement lag is aggregate delay accounting; animal identities are not present while in shed/hands.',
            'Animal harvest/calendar ratios include care, held output, delivery and intentional retirement differences; not causal profit ratios.',
            'Quantity/average-price revenue split is an algebraic descriptive identity, not recoverable profit.',
            'V8 partial-pickup designation is inherited only from exact prior action/state prefixes; V8 internal tier logs were not saved.',
            'Same-unit CARE without feed links physical symptoms but does not prove that a local retry or broad rolling switch would improve final profit.'])
    dest=BASE/'v8_cost_service_diagnostic.json';dest.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(path=str(dest),sha256=sha(dest),aggregate={k:v['aggregate'] for k,v in groups.items()},prefix_matches=sum(all(r['both_action_prefixes_equal_through_pickup']) and r['current_private_snapshot_equal'] for r in matches))))


if __name__=='__main__':main()

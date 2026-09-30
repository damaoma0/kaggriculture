"""Aggregate audited production, staffing, costs and fixed-stream diagnostics."""
from collections import Counter
from statistics import mean
import json
from market_corpus import ROOT

OUT=ROOT/'results/fresh/leader_strategy'

def total_physical(rows):
    c=Counter()
    for r in rows:c.update(r)
    return c

def main():
    games=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(OUT.glob('audit-*.json'))]
    assert len(games)==11 and all('leader_vs_v45' in r for r in games)
    result={'games':11,'policies':{},'episodes':[]}
    for mode,label in [('replay','leader'),('v45_replace','our_v45')]:
        ledgers=[g[mode]['ledger'][g['seat']] for g in games]
        phys=[total_physical(g[mode]['physical'][g['seat']]) for g in games]
        summary=dict(cash=mean(g[mode]['cash'][g['seat']] for g in games),revenue=mean(sum(l['revenue'].values()) for l in ledgers),spend=mean(sum(l['spend'].values()) for l in ledgers),
            ledger={section:{k:mean(l[section].get(k,0) for l in ledgers) for k in sorted(set().union(*(l[section] for l in ledgers)))} for section in ('revenue','spend','sold_units')},
            physical={k:mean(p.get(k,0) for p in phys) for k in sorted(set().union(*phys))},snapshots=[])
        for day in (1,3,6,9,12,15,18,21,24,27):
            snaps=[g[mode]['snapshots'][g['seat']][day] for g in games]
            summary['snapshots'].append(dict(day=day,cash=mean(s['cash'] for s in snaps),land=mean(s['land'] for s in snaps),plots=mean(s['plots'] for s in snaps),
                crops={k:mean(s['crops'].get(k,0) for s in snaps) for k in ('WHEAT','MELON','STRAWBERRY','TOMATO','CARROT')},
                animals={k:mean(s['animals'].get(k,0) for s in snaps) for k in ('COW','SHEEP','GOOSE')},hire_cost=mean(s['ledger']['spend'].get('HIRE',0) for s in snaps)))
        result['policies'][label]=summary
    for g in games:
        s=g['seat'];a=g['replay'];b=g['v45_replace'];c=g['leader_vs_v45']
        result['episodes'].append(dict(episode=g['episode'],seat=s,opponent=g['teams'][1-s],shops=a['snapshots'][s][-1]['shops'],actual_margin=a['cash'][s]-a['cash'][1-s],
            leader_cash=a['cash'][s],replacement_cash=b['cash'][s],replacement_opponent_cash=b['cash'][1-s],replacement_margin=b['cash'][s]-b['cash'][1-s],
            leader_tape_margin=c['cash'][s]-c['cash'][1-s],leader_tape_missing_worker_commands=total_physical(c['physical'][s]).get('missing_worker_commands',0),
            leader_hire=a['ledger'][s]['spend'].get('HIRE',0),v45_hire=b['ledger'][s]['spend'].get('HIRE',0),leader_land=a['ledger'][s]['spend'].get('BUY_LAND',0),v45_land=b['ledger'][s]['spend'].get('BUY_LAND',0)))
    result['actual_wins']=sum(r['actual_margin']>0 for r in result['episodes']);result['actual_mean_margin']=mean(r['actual_margin'] for r in result['episodes'])
    result['fixed_leader_tape_wins']=sum(r['leader_tape_margin']>0 for r in result['episodes'])
    matched=[g for g in games if 'M & M & P & Q' in g['teams']]
    result['matched_challenger']={}
    for label in ('leader','challenger'):
        seats=[g['seat'] if label=='leader' else 1-g['seat'] for g in matched]
        ls=[g['replay']['ledger'][i] for g,i in zip(matched,seats)]
        ps=[total_physical(g['replay']['physical'][i]) for g,i in zip(matched,seats)]
        result['matched_challenger'][label]=dict(games=len(matched),cash=mean(g['replay']['cash'][i] for g,i in zip(matched,seats)),
            ledger={section:{k:mean(l[section].get(k,0) for l in ls) for k in sorted(set().union(*(l[section] for l in ls)))} for section in ('revenue','spend','sold_units')},
            physical={k:mean(p.get(k,0) for p in ps) for k in sorted(set().union(*ps))})
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

"""Report all failures and paired score/margin; bootstrap whole worlds."""
import argparse,json,random,statistics
from collections import defaultdict
from pathlib import Path


def ci(values,seed=24):
    if not values:return None
    rng=random.Random(seed);n=len(values)
    draws=sorted(statistics.mean(rng.choices(values,k=n)) for _ in range(2000))
    return [draws[50],draws[1949]]


def report(folder):
    rows=[json.loads(p.read_text(encoding='utf8')) for p in folder.glob('*.json') if p.name not in ('manifest.json','summary.json')]
    arms=defaultdict(list)
    for row in rows:
        if 'arm' in row:arms[row['arm']].append(row)
    result=dict(arms={},paired={},limitations=[
        'Recorded-opponent results are counterfactual diagnostics, not wins against responsive policies.',
        'Development cases are not independent qualification.',
        'Bootstrap clusters by world; small panels are not Elo estimates.'])
    for arm,group in arms.items():
        good=[r for r in group if r.get('completed')]
        revenue=defaultdict(float);spend=defaultdict(float)
        for r in good:
            for k,v in r['ledger'][r['seat']]['revenue'].items():revenue[k]+=v/len(good)
            for k,v in r['ledger'][r['seat']]['spend'].items():spend[k]+=v/len(good)
        animal_losses=[]
        for r in good:
            for before,after in zip(r['daily'],r['daily'][1:]):
                for species in ('COW','SHEEP','GOOSE'):
                    lost=before['seats'][r['seat']]['counts'].get(species,0)-after['seats'][r['seat']]['counts'].get(species,0)
                    if lost>0:animal_losses.append(dict(world=r.get('episode') or r['seed'],seat=r['seat'],
                        day=before['step']//24,species=species,lost=lost))
        result['arms'][arm]=dict(requested=len(group),completed=len(good),errors=[r.get('error') for r in group if r.get('error')],
            score=sum(r['score'] for r in good)/len(good) if good else None,
            mean_margin=statistics.mean(r['margin'] for r in good) if good else None,
            mean_cash=statistics.mean(r['cash'][r['seat']] for r in good) if good else None,
            mean_revenue_by_product=dict(revenue),mean_spend_by_category=dict(spend),
            worst_margin=min((r['margin'] for r in good),default=None),
            max_call=max((r['timing'][r['seat']]['max'] for r in good),default=None),
            max_total_agent_seconds=max((r['timing'][r['seat']]['total'] for r in good),default=None),
            all_cash_ledgers_verified=all(r.get('ledger_verified') for r in good),
            recovery_days=sum(r.get('stats',{}).get('recoveries',0) for r in good),
            animal_count_decreases=animal_losses,
            failed_orders=sum(sum(r['failed_orders'][r['seat']].values()) for r in good),
            unplanned_hours=sum(r.get('stats',{}).get('unplanned_hours',0) for r in good),
            state_repairs=sum(r.get('stats',{}).get('state_repairs',0) for r in good),
            physical_no_effect=sum(sum(n for op,n in r['no_effect'][r['seat']].items()
                if op not in ('DROP','PICKUP')) for r in good))
    ours={(r.get('episode') or r['seed'],r['seat']):r for r in arms.get('semantic',[]) if r.get('completed')}
    for arm,group in arms.items():
        if arm=='semantic':continue
        delta=defaultdict(list);score=defaultdict(list);invalid=[]
        for row in group:
            key=(row.get('episode') or row['seed'],row['seat'])
            if not row.get('completed') or key not in ours:continue
            candidate=ours[key]
            delta[key[0]].append(candidate['margin']-row['margin'])
            score[key[0]].append(candidate['score']-row['score'])
            if abs(sum(candidate['no_effect'][1-candidate['seat']].values())-
                   sum(row['no_effect'][1-row['seat']].values()))>40:invalid.append(key)
        values=[statistics.mean(v) for v in delta.values()]
        scores=[statistics.mean(v) for v in score.values()]
        flagged_worlds={key[0] for key in invalid}
        unflagged=[statistics.mean(v) for world,v in delta.items() if world not in flagged_worlds]
        result['paired'][arm]=dict(worlds=len(delta),games=sum(map(len,delta.values())),
            mean_margin_delta=statistics.mean(values) if values else None,margin_ci95=ci(values),
            mean_score_delta=statistics.mean(scores) if scores else None,score_ci95=ci(scores),
            rival_tape_noop_sensitivity_flags=invalid,
            unflagged_sensitivity=dict(worlds=len(unflagged),
                mean_margin_delta=statistics.mean(unflagged) if unflagged else None,
                margin_ci95=ci(unflagged)))
    (folder/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder');report(Path(parser.parse_args().folder))

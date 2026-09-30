"""Read-only development/training diagnosis. Does not run agents or games."""
from collections import Counter, defaultdict
from pathlib import Path
import gzip
import hashlib
import json
import statistics

import numpy as np
import semantic_strategy_policy_20260928 as P
import build_semantic_block_model_20260928 as B

ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / 'results/fresh/semantic_strategy_20260928'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rounded(a):
    return np.maximum(0, np.floor(a + .5))


def features_state(row):
    f = row['features']
    return dict(f, day=row['day'], owned_quadrants=P._land(f))


def annual_release(row, end):
    out = np.zeros(len(B.OUTPUTS))
    for c in row['features']['own_crop_cohorts']:
        if c['crop'] in ('WHEAT', 'CARROT') and c['birth'] + P.DEFAULT_CONFIG['release_age'][c['crop']] <= end:
            out[B.OUTPUTS.index(c['crop'])] += c['count']
    return out


def cross_validation(games):
    """Leave one whole source episode out. No qualification data is read."""
    results = {}
    for start in range(6, 30, 3):
        first = [g[start] for g in games]
        x = np.array([B.features(r) for r in first], float)
        y = np.array([np.array([B.quantities(g[d]) for d in range(start, start+3)]).sum(axis=0) for g in games], float)
        releases = np.array([annual_release(r, start+2) for r in first])
        reveal = np.array([[int(start<=24 and r['features']['shops_prefix'][-1]==shop) for shop in P.SHOPS] for r in first],float)
        pred = {k: [] for k in ('ridge', 'ridge_reveal', 'ridge_sheep_hurdle', 'nearest', 'median')}
        match = []
        for i in range(len(games)):
            keep = np.arange(len(games)) != i
            xx = x[keep]; yy = y[keep] - releases[keep]
            mean = xx.mean(axis=0); scale = np.maximum(xx.std(axis=0), 1.)
            design = np.column_stack([np.ones(len(xx)), (xx-mean)/scale])
            penalty = np.eye(design.shape[1])*3; penalty[0,0] = 0
            coef = np.linalg.solve(design.T@design+penalty, design.T@yy)
            estimate = np.r_[1., (x[i]-mean)/scale]@coef + releases[i]
            pred['ridge'].append(np.minimum(rounded(estimate), y[keep].max(axis=0)))
            xxx = np.column_stack([x,reveal]); xxt=xxx[keep]
            mm=xxt.mean(axis=0);sc=np.maximum(xxt.std(axis=0),1.)
            dd=np.column_stack([np.ones(len(xxt)),(xxt-mm)/sc]); pp=np.eye(dd.shape[1])*3;pp[0,0]=0
            cc=np.linalg.solve(dd.T@dd+pp,dd.T@yy)
            re=np.minimum(rounded(np.r_[1.,(xxx[i]-mm)/sc]@cc+releases[i]),y[keep].max(axis=0))
            pred['ridge_reveal'].append(re)
            hurdle=pred['ridge'][-1].copy()
            if start>=9 and (start>24 or first[i]['features']['shops_prefix'][-1]!='YARN_STORE'):
                hurdle[B.OUTPUTS.index('SHEEP')]=0
            pred['ridge_sheep_hurdle'].append(hurdle)
            state = features_state(first[i])
            candidates = [j for j in range(len(games)) if j != i]
            nearest = min(candidates, key=lambda j: (P.row_distance(state, first[j], P.DEFAULT_CONFIG), j))
            pred['nearest'].append(y[nearest])
            pred['median'].append(rounded(np.median(y[keep], axis=0)))
            match.append(P.demand(first[i]['features']['shops_prefix']) == P.demand(first[nearest]['features']['shops_prefix']))
        details = {}
        for mode, a in pred.items():
            a = np.array(a)
            details[mode] = {s: dict(mae=round(float(np.abs(a[:,j]-y[:,j]).mean()),3),
                actual_mean=round(float(y[:,j].mean()),3), predicted_mean=round(float(a[:,j].mean()),3),
                false_positive_cases=int(((a[:,j]>0)&(y[:,j]==0)).sum()),
                missed_positive_cases=int(((a[:,j]==0)&(y[:,j]>0)).sum()),
                source_zero_cases=int((y[:,j]==0).sum())) for j,s in enumerate(B.OUTPUTS)}
        results[str(start)] = dict(nearest_exact_demand_matches=sum(match), episodes=len(games), methods=details)
    return results


def main():
    source = MISSION / 'causal_daily_rows_modern100.json'
    model = json.loads(source.read_text()); groups = defaultdict(dict)
    for r in model['rows']:
        groups[int(r['meta']['episode'])][r['day']] = r
    games = [groups[e] for e in sorted(groups)]
    native_exit_ages = defaultdict(Counter)
    native_daily = {}; native_sheep_reveal = {}
    native_output = Counter(); native_forecast = Counter(); native_feeds = 0; native_animal_days = 0
    native_sources = {}
    for g in games:
        path = ROOT/g[6]['meta']['source']; native_sources[str(path.relative_to(ROOT))] = sha(path)
        sem = json.load(gzip.open(path, 'rt'))
        for day in range(6,29):
            f = g[day]['features']; now = {(c['crop'],c['birth']):c['count'] for c in f['own_crop_cohorts']}
            nxt = {(c['crop'],c['birth']):c['count'] for c in g[day+1]['features']['own_crop_cohorts']}
            for (sp,birth),count in now.items():
                if count > nxt.get((sp,birth),0):native_exit_ages[sp][day-birth] += count-nxt.get((sp,birth),0)
        for day in range(6,30):
            f = g[day]['features']; native_forecast.update(P.output_calendar([],f['own_animal_cohorts'],day)[day])
            native_output.update(sem['days'][day]['harvested']['units'])
            native_feeds += len(sem['days'][day]['maintenance'].get('FEED',[]))
            native_animal_days += sum(c['count'] for c in f['own_animal_cohorts'])
    for day in range(6,30):
        rows=[g[day] for g in games]
        native_daily[str(day)] = dict(
            mean_plant={sp:round(statistics.mean(r['target'].get('plant_counts',{}).get(sp,0) for r in rows),3) for sp in P.CROPS},
            mean_add={sp:round(statistics.mean(r['target'].get('animal_add_counts',{}).get(sp,0) for r in rows),3) for sp in P.ANIMALS},
            mean_animals={sp:round(statistics.mean(sum(c['count'] for c in r['features']['own_animal_cohorts'] if c['species']==sp) for r in rows),3) for sp in P.ANIMALS})
    for start in range(9,30,3):
        table=defaultdict(lambda:dict(cases=0,positive=0,units=0))
        for g in games:
            label=g[start]['features']['shops_prefix'][-1] if start<=24 else 'NO_NEW_REVEAL'
            n=sum(g[d]['target']['animal_add_counts'].get('SHEEP',0) for d in range(start,start+3))
            table[label]['cases']+=1; table[label]['positive']+=int(n>0); table[label]['units']+=n
        native_sheep_reveal[str(start)]=dict(table)
    cases=[]; raw_sources={}
    for path in sorted((MISSION/'runs/strategy_v5_blocks100_finance/development/live').glob('live-??.json')):
        x=json.loads(path.read_text()); raw_sources[str(path.relative_to(ROOT))]=sha(path); seat=x['case']['seat']
        own=x['daily'][seat][-1]; rival=x['daily'][1-seat][-1]
        deltas={field:{s:own[field].get(s,0)-rival[field].get(s,0) for s in set(own[field])|set(rival[field])} for field in ('revenue','spend','sold_units')}
        rows=[]; forecast=Counter(); actual=Counter(); age_calendar={}
        for day in range(6,30):
            obs=x['diagnostics'][seat][day]['current_observation']; crops,animals,_,_=P._cohorts(obs['own_farm'],day)
            diag=x['final_diagnostics'][str(seat)][day]; proposal=diag['proposal']; inv=Counter(obs['private'].get('shed',{}))
            for held in obs['private'].get('inventories',[]):inv.update(held)
            ap=Counter(proposal['animal_add_counts']); held={s:min(ap[s],inv[s]) for s in P.ANIMALS}
            committed={int(r['tile']) for r in diag.get('retirements',[])}
            active_unfed=Counter(); active=Counter()
            for yi,row in enumerate(obs['own_farm']['tiles']):
                for xi,tile in enumerate(row):
                    if isinstance(tile,dict) and tile.get('animal') in P.ANIMALS and yi*10+xi not in committed:
                        active[tile['animal']]+=1
                        if tile.get('consecutive_unfed',0)>0:active_unfed[tile['animal']]+=1
            # Causal diagnostic trigger only: no counterfactual game/profit claim.
            deferred={s:min(1,max(0,ap[s]-held[s])) for s in P.ANIMALS if active_unfed[s] and ap[s]>held[s] and day>=9}
            forecast.update(P.output_calendar([],animals,day)[day])
            for s in P.PRODUCTS:
                actual[s]+=x['daily'][seat][day+1]['physical'].get('produced:'+s,0)-x['daily'][seat][day]['physical'].get('produced:'+s,0)
            rows.append(dict(day=day,cash=obs['own_farm']['money'],prices=obs['market']['prices'],animals=dict(P.cohort_counts(animals,'species')),
                crops=dict(P.cohort_counts(crops,'crop')),plant=proposal['plant_counts'],animal_add=dict(ap),animal_held=held,
                unbought_add={s:max(0,ap[s]-held[s]) for s in P.ANIMALS},retire=proposal['animal_retire_counts'],
                active_unfed=dict(active_unfed),candidate_one_unit_defer=deferred,
                estimated_work=proposal['estimated_work_p95'],hands=proposal['hands'],
                old_model_values=diag['policy'].get('cohort_values',{})))
            rows[-1]['block_reveal']=x['shops'][day//3-1] if day<=26 else 'NO_NEW_REVEAL'
        for s in P.ANIMALS:
            par=P.ANIMALS[s]
            age_calendar[s]={str(d):dict(first_sale_day=d+par['first'], remaining_output_dates=sum(t>=d+par['first'] and (t-d-par['first'])%par['interval']==0 for t in range(d,30)),
                feed_nights=max(0,29-d)) for d in (6,9,12,15,18,21,24)}
        cases.append(dict(case=x['case']['id'],margin=x['margin'],shops=x['shops'],
            revenue_difference=sum(deltas['revenue'].values()),spend_difference=sum(deltas['spend'].values()),deltas=deltas,
            actual_harvest_d6_29=dict(actual),calendar_expected_d6_29=dict(forecast),daily=rows,animal_lifetime_calendar=age_calendar))
    out=dict(scope='Read-only old-executor V5 live development8 and authorized modern100 training; no qualification or games. New KB115LT2 requires new gameplay validation.',
        limitations=['Actual harvested units include delivery/stock timing; ratios to forecast are descriptive, not causal production/care efficiency.',
            'Zero-source count classification measures imitation, not optimal profitability.',
            'Candidate one-unit deferral is static activation only; it excludes held commitments but has no profit evidence.',
            'Native source market fields are shifted and are not used in the training physical comparison.'],
        sources={str(source.relative_to(ROOT)):sha(source),**raw_sources},native_sources=native_sources,
        native_daily=native_daily,native_sheep_reveal=native_sheep_reveal,
        native_crop_exit_ages={s:dict(sorted(v.items())) for s,v in native_exit_ages.items()},
        native_actual_harvest_d6_29=dict(native_output),native_calendar_expected_d6_29=dict(native_forecast),
        native_physical_feeds=native_feeds,native_morning_animal_days=native_animal_days,
        leave_episode_out=cross_validation(games),v5_cases=cases)
    dest=MISSION/'strategic_v5_what_when_diagnostic_v2.json'; dest.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(path=str(dest),sha256=sha(dest),cases=len(cases),training_episodes=len(games))))


if __name__=='__main__':main()

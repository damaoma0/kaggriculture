"""Leave-one-episode-out modern DSM block-label diagnostic, without games.

Three-day labels are training targets under one revealed shop prefix, never
actual future target-world observations. Counts are evaluated offline only.
"""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np

import semantic_strategy_policy_20260928 as P

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/semantic_strategy_20260928'
SPECIES=tuple(P.CROPS)+tuple(P.ANIMALS)
STARTS=tuple(range(6,30,3))


def q(row):
    t=row['target']
    return np.array([t.get('plant_counts' if s in P.CROPS else 'animal_add_counts',{}).get(s,0) for s in SPECIES],float)


def state(row):
    s=dict(row['features']);s['day']=row['day'];s['owned_quadrants']=P._land(s)
    return s


def predictors(row,own=True):
    f=row['features'];dem=P.demand(f['shops_prefix'])
    x=[dem.get(p,0) for p in ('MILK','WOOL','EGG','STRAWBERRY','TOMATO','CARROT','WHEAT')]
    if own:
        c=P.cohort_counts(f['own_crop_cohorts'],'crop')+P.cohort_counts(f['own_animal_cohorts'],'species')
        x += [c[s] for s in SPECIES]
    return np.array(x,float)


def annual_releases(row):
    out=np.zeros(len(SPECIES));start=row['day'];end=min(29,start+2)
    for c in row['features']['own_crop_cohorts']:
        crop=c['crop']
        if crop in ('WHEAT','CARROT') and c['birth']+P.DEFAULT_CONFIG['release_age'][crop]<=end:
            out[SPECIES.index(crop)]+=c['count']
    return out


def summary(records):
    out={}
    for method in sorted({r['method'] for r in records}):
        out[method]={}
        for start in ('all',*STARTS):
            rs=[r for r in records if r['method']==method and (start=='all' or r['day']==start)]
            a=np.array([r['actual'] for r in rs]);b=np.array([r['predicted'] for r in rs])
            out[method][str(start)]=dict(blocks=len(rs),per_species_block_mae=float(np.abs(a-b).mean()),
                by_species={s:dict(actual=float(a[:,i].sum()),predicted=float(b[:,i].sum()),
                                  mae=float(np.abs(a[:,i]-b[:,i]).mean())) for i,s in enumerate(SPECIES)})
    return out


def main():
    path=BASE/'causal_daily_rows_modern60.json';rows=json.loads(path.read_text())['rows']
    games=defaultdict(dict)
    for r in rows:games[int(r['meta']['episode'])][r['day']]=r
    ids=sorted(games);blocks={d:{} for d in STARTS};records=[]
    for start in STARTS:
        for ep,rr in games.items():
            chunk=[rr[d] for d in range(start,min(30,start+3))]
            assert all(r['features']['shops_prefix']==chunk[0]['features']['shops_prefix'] for r in chunk)
            blocks[start][ep]=dict(first=chunk[0],y=sum((q(r) for r in chunk),np.zeros(len(SPECIES))))
    for start in STARTS:
        for ep in ids:
            target=blocks[start][ep];others=[e for e in ids if e!=ep]
            st=state(target['first']);cfg=dict(P.DEFAULT_CONFIG)
            distances={e:P.row_distance(st,blocks[start][e]['first'],cfg) for e in others}
            rank=sorted(others,key=lambda e:(distances[e],ids.index(e)))
            demand_dist={e:P._l1(P.demand(st['shops_prefix']),P.demand(blocks[start][e]['first']['features']['shops_prefix']),P.WEIGHTS) for e in others}
            demand_rank=sorted(others,key=lambda e:(demand_dist[e],ids.index(e)))
            predicted={
                'calendar_median':np.median([blocks[start][e]['y'] for e in others],axis=0),
                'reveal_nearest_joint':blocks[start][rank[0]]['y'],
                'reveal_3_nearest_mean':np.mean([blocks[start][e]['y'] for e in rank[:3]],axis=0),
                'reveal_demand_nearest':blocks[start][demand_rank[0]]['y']}
            daily=np.zeros(len(SPECIES));donors=[]
            for day in range(start,min(30,start+3)):
                dst=state(games[ep][day])
                chosen=min(others,key=lambda e:(P.row_distance(dst,games[e][day],cfg),ids.index(e)))
                daily+=q(games[chosen][day]);donors.append(chosen)
            predicted['daily_nearest_joint']=daily
            for own in (False,True):
                # Fixed ridge regularization, declared before outcomes; the
                # target episode is excluded from every fit and normalization.
                xx=np.array([predictors(blocks[start][e]['first'],own) for e in others]);yy=np.array([blocks[start][e]['y'] for e in others])
                mean=xx.mean(axis=0);scale=np.maximum(xx.std(axis=0),1.)
                x=np.column_stack([np.ones(len(others)),(xx-mean)/scale]);xt=np.r_[1.,(predictors(target['first'],own)-mean)/scale]
                penalty=np.eye(x.shape[1])*3.;penalty[0,0]=0
                beta=np.linalg.solve(x.T@x+penalty,x.T@yy)
                predicted['ridge_demand_and_own' if own else 'ridge_demand']=np.maximum(0,xt@beta)
                if own:
                    net=yy-np.array([annual_releases(blocks[start][e]['first']) for e in others])
                    beta=np.linalg.solve(x.T@x+penalty,x.T@net)
                    predicted['ridge_own_netannual']=np.maximum(0,xt@beta+annual_releases(target['first']))
            for name,pred in predicted.items():
                records.append(dict(episode=ep,day=start,method=name,actual=target['y'].tolist(),
                                    predicted=pred.tolist(),daily_neighbor_switches=len(set(donors))-1))
    out=dict(purpose='Modern60 leave-one-episode-out block-label fidelity, not gameplay validation',
        schema=1,source=str(path.relative_to(ROOT)),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        cohort_features='Only current anonymous own cohorts and revealed shops at decision time',
        target='Successful additions during the current three-day reveal interval; one shop prefix verified throughout',
        limitations=['No market, rival board, or private-stock archive for these modern records.',
                    'Repeated block rows are dependent within episode; no inferential profit claims.',
                    'Budgets require causal completion accounting, capacity, financing and execution before use.'],
        summary=summary(records),rows=records)
    dst=BASE/'block_strategy_diagnostic.json';dst.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(path=str(dst),mae={k:round(v['all']['per_species_block_mae'],4) for k,v in out['summary'].items()},
                         d6={k:round(v['6']['per_species_block_mae'],4) for k,v in out['summary'].items()}),indent=2))


if __name__=='__main__':main()

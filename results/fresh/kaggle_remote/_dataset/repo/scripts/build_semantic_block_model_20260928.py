"""Offline causal block-policy fit; source IDs remain in a separate manifest."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np

import semantic_strategy_policy_20260928 as P

DEMAND=('MILK','WOOL','EGG','STRAWBERRY','TOMATO','CARROT','WHEAT')
SPECIES=tuple(P.CROPS)+tuple(P.ANIMALS)
OUTPUTS=SPECIES+tuple('RETIRE_'+s for s in P.ANIMALS)
ROOT=Path(__file__).resolve().parents[1]


def features(row):
    f=row['features'];d=P.demand(f['shops_prefix'])
    c=P.cohort_counts(f['own_crop_cohorts'],'crop')+P.cohort_counts(f['own_animal_cohorts'],'species')
    return [d.get(s,0) for s in DEMAND]+[c[s] for s in SPECIES]


def quantities(row):
    t=row['target']
    return [t.get('plant_counts' if s in P.CROPS else 'animal_add_counts',{}).get(s,0) for s in SPECIES]+[
        t.get('animal_retire_counts',{}).get(s,0) for s in P.ANIMALS]


def build(source):
    model=json.loads(source.read_text());games=defaultdict(dict)
    for row in model['rows']:games[(int(row['meta']['episode']),int(row['meta']['seat']))][row['day']]=row
    blocks={}
    for day in range(6,30,3):
        firsts=[];daily=[];net=[];hands=[];land=[];examples=[]
        for _,game in sorted(games.items()):
            chunk=[game[d] for d in range(day,min(30,day+3))]
            assert all(r['features']['shops_prefix']==chunk[0]['features']['shops_prefix'] for r in chunk)
            first=chunk[0];counts=np.array([quantities(r) for r in chunk],float)
            targets=counts.sum(axis=0)
            for c in first['features']['own_crop_cohorts']:
                if c['crop'] in ('WHEAT','CARROT') and c['birth']+P.DEFAULT_CONFIG['release_age'][c['crop']]<=min(29,day+2):
                    targets[SPECIES.index(c['crop'])]-=c['count']
            firsts.append(features(first));daily.append(counts);net.append(targets)
            hands.append([r['target']['hands'] for r in chunk])
            land.append([len(r['target']['owned_quadrants']) if isinstance(r['target']['owned_quadrants'],list)
                         else int(r['target']['owned_quadrants']) for r in chunk])
            if day==6:
                allowed=('shops_prefix','own_crop_cohorts','own_animal_cohorts','owned_quadrants','own_structures')
                examples.append(dict(features={k:first['features'][k] for k in allowed},
                    daily=counts.tolist(),hands=hands[-1],land=land[-1]))
        xx=np.array(firsts,float);yy=np.array(net,float);mean=xx.mean(axis=0);scale=np.maximum(xx.std(axis=0),1.)
        x=np.column_stack([np.ones(len(xx)),(xx-mean)/scale]);penalty=np.eye(x.shape[1])*3.;penalty[0,0]=0
        coef=np.linalg.solve(x.T@x+penalty,x.T@yy)
        totals=np.array(daily).sum(axis=1);schedule=np.mean(daily,axis=0)
        share=np.divide(schedule,schedule.sum(axis=0),out=np.full_like(schedule,1/len(schedule)),where=schedule.sum(axis=0)>0)
        blocks[str(day)]=dict(mean=mean.tolist(),scale=scale.tolist(),coef=coef.tolist(),shares=share.tolist(),
            max_counts=totals.max(axis=0).tolist(),hands=np.rint(np.median(hands,axis=0)).astype(int).tolist(),
            land=np.rint(np.median(land,axis=0)).astype(int).tolist(),opening_examples=examples)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    return dict(schema=1,demand_features=list(DEMAND),species=list(SPECIES),outputs=list(OUTPUTS),
                fit='ridge lambda3, intercept unpenalized; annual crop labels are net of existing cohort releases',
                source_sha256=digest,training_seats=len(games),blocks=blocks),dict(
                source=str(source.relative_to(ROOT)),source_sha256=digest,episodes=sorted({e for e,s in games}),
                seats=[dict(episode=e,seat=s) for e,s in sorted(games)],
                provenance='Authorized stage2 training; any stage1 DSM40 sources are no longer independent tests of this policy')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',default='results/fresh/semantic_strategy_20260928/causal_daily_rows_modern100.json')
    ap.add_argument('--out',default='results/fresh/semantic_strategy_20260928/block_model_modern100.json');args=ap.parse_args()
    source=ROOT/args.source;out=ROOT/args.out;model,manifest=build(source)
    out.write_text(json.dumps(model,separators=(',',':'))+'\n');mp=out.with_name(out.stem+'_training_manifest.json')
    mp.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(path=str(out),sha256=hashlib.sha256(out.read_bytes()).hexdigest(),training_seats=model['training_seats'])))


if __name__=='__main__':main()

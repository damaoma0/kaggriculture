"""Descriptive calendar analysis and episode-held-out production donor diagnostic.

This is a prediction/retrieval check, not executor feasibility or game performance.
All selectors use only information present at the handover; output labels end
before the next shop reveal. All seats of the test episode are excluded.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, pstdev
from analyze_umg_shop_output_changes import PRODUCTS, DAYS
from mgt_late_choice import DEMAND

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/production_continuation'
FARM=['WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','COW','SHEEP','GOOSE','EMPTY','WEED']
CROPS=FARM[:5]
FEATURES=['demand','board','ages','before']

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def summarize(rows):
    return {p:dict(median=median([r['delta'][p] for r in rows]),
                   mean=mean([r['delta'][p] for r in rows]),
                   positive=sum(r['delta'][p]>0 for r in rows),
                   negative=sum(r['delta'][p]<0 for r in rows),
                   zero=sum(r['delta'][p]==0 for r in rows)) for p in PRODUCTS}

def main():
    corpus=read(BASE/'leader_shop_matrices.json')
    events=corpus['events']
    grouped=defaultdict(list)
    for e in events:grouped[e['episode']].append(e)
    cache=BASE/'imitation_observed_features.json'
    if cache.exists():
        metadata=read(cache)
    else:
        metadata={}
        for eid, rows in grouped.items():
            replay=read(ROOT/f'data/leaders_20260917/episode-{eid}-replay.json')
            for e in rows:
                obs=replay['steps'][e['day']*24][e['seat']]['observation']
                # Kaggle omits the common step field from some seat-1 snapshots.
                assert replay['steps'][e['day']*24][0]['observation']['step']==e['day']*24
                assert obs['town']['unlocked_shops']==e['previous_shops']+[e['shop']]
                ages=Counter()
                for line in obs['farms'][e['seat']]['tiles']:
                    for tile in line:
                        if isinstance(tile,dict) and tile.get('crop'):
                            age=e['day']-tile['planted_day']
                            ages[tile['crop'],min(5,max(0,age//3))]+=1
                metadata[f"{eid}/{e['seat']}/{e['day']}"]={
                    'ages':[ages[c,a] for c in CROPS for a in range(6)]}
            print('features',eid,flush=True)
        cache.write_text(json.dumps(metadata),encoding='utf-8')
    for eid, rows in grouped.items():
        ledger=read(ROOT/f'results/fresh/leader_segments/segments-{eid}.json')
        for e in rows:
            state=ledger['seats'][e['seat']]['segments'][e['day']//3]
            assert state['shops_at_start']==e['previous_shops']+[e['shop']]
            e['demand']=[sum(DEMAND[s].get(p,0) for s in state['shops_at_start']) for p in PRODUCTS]
            e['board']=[state['board_start'].get(c,0) for c in FARM]
            e['ages']=metadata[f"{eid}/{e['seat']}/{e['day']}"]['ages']
            e['previous_output']=[e['before'][p] for p in PRODUCTS]
    descriptions={
        'calendar_median':'Same UMG version/day median output change, added to current prior output',
        'new_shop_median':'Same UMG version/day/new shop median change; calendar fallback if no examples',
        'umg_demand_donor':'Nearest UMG donor by current aggregate demand',
        'umg_state_donor':'Nearest UMG donor by board, crop age buckets and prior output',
        'umg_full_donor':'Nearest UMG donor by demand plus board, crop ages and prior output',
        'all_full_donor':'Nearest donor from all four submissions with the same full-state distance',
    }
    predictions=[]
    targets=[e for e in events if e['submission']==56266758]
    for target in targets:
        train=[e for e in events if e['day']==target['day'] and e['episode']!=target['episode']]
        own=[e for e in train if e['submission']==56266758]
        matching=[e for e in own if e['shop']==target['shop']]
        dims={'demand':'demand','board':'board','ages':'ages','before':'previous_output'}
        # Fit scales on training UMG only, shared by UMG/all-leader selectors.
        scales={f:[max(1,pstdev([r[key][i] for r in own])) for i in range(len(target[key]))] for f,key in dims.items()}
        def distance(candidate,features):
            return mean(mean(abs(a-b)/s for a,b,s in zip(target[dims[f]],candidate[dims[f]],scales[f])) for f in features)
        for model in descriptions:
            donor=None
            if model.endswith('_median'):
                rows=matching if model=='new_shop_median' and matching else own
                predicted={p:max(0,target['before'][p]+median([r['delta'][p] for r in rows])) for p in PRODUCTS}
            else:
                features=['demand'] if model=='umg_demand_donor' else ['board','ages','before'] if model=='umg_state_donor' else FEATURES
                choices=train if model=='all_full_donor' else own
                donor=min(choices,key=lambda r:(distance(r,features),r['episode'],r['seat']))
                predicted=donor['after']
            err={p:abs(predicted[p]-target['after'][p]) for p in PRODUCTS}
            predictions.append(dict(episode=target['episode'],day=target['day'],model=model,
                error=err,mae=mean(err.values()),donor_submission=donor['submission'] if donor else None,
                donor_episode=donor['episode'] if donor else None))
    metrics={m:dict(mae=mean(r['mae'] for r in predictions if r['model']==m),
        by_product={p:mean(r['error'][p] for r in predictions if r['model']==m) for p in PRODUCTS},
        by_day={str(d):mean(r['mae'] for r in predictions if r['model']==m and r['day']==d) for d in DAYS}) for m in descriptions}
    calendar={str(sub):{str(d):summarize([e for e in events if e['submission']==int(sub) and e['day']==d]) for d in DAYS} for sub in corpus['counts']}
    selection=Counter(r['donor_submission'] for r in predictions if r['model']=='all_full_donor')
    result=dict(description=descriptions,metrics=metrics,calendar=calendar,mixed_donor_counts=dict(selection),predictions=predictions,
        test_trajectories=30,test_periods=120,notes=[
            'All test-episode seats are excluded; same-date only; no future shops/final scores used to rank donors.',
            'Features and equal group weights fixed before seeing scores; scaling uses remaining UMG sample only.',
            'UMG 30-game imitation diagnostic only; not held-out shop histories, execution, profit or strength evaluation.',
            'Donor produces an actual next-period output vector; cross-farm reachability is untested.',
            'Whole-season donor suffixes would contain decisions conditioned on later reveals; only next three-day labels evaluated here.',
            'MAE weights each of nine products equally; it is not an economic value metric.',
            'Crop age groups are three-day buckets, animals only counts; spatial routing, prices, stock and care omitted.'])
    (BASE/'plan_imitation_analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'metrics':metrics,'mixed_donor_counts':dict(selection)},indent=2))

if __name__=='__main__':main()

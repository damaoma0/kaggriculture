"""Independent paired reporting of frozen forecast predictions; no model fitting."""
from collections import defaultdict
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    report=read(OUT/'forecast/forecast_results.json');products=report['products'];rng=np.random.default_rng(20260924)
    cells=[];errors=defaultdict(list);bootstrap=[]
    # Apply the same predeclared cumulative-max coherence rule to each baseline.
    grouped=defaultdict(list)
    for r in report['results']:
        if 'frozen_test' in r:grouped[r['checkpoint_day']].append(r)
    for rows in grouped.values():
        rows.sort(key=lambda r:999 if r['horizon']=='end' else r['horizon'])
        running={}
        for r in rows:
            for name,candidate in r['frozen_test']['all_frozen_candidates'].items():
                for x in candidate['rows']:
                    key=(name,x['episode'],x['seat']);p=np.array(x['prediction'])
                    running[key]=np.maximum(running.get(key,np.zeros(len(products))),p)
                    x['coherent_prediction']=running[key].tolist()
    for r in report['results']:
        if 'frozen_test' not in r:continue
        t=r['frozen_test'];selected=t['rows'];ids=[(x['episode'],x['seat']) for x in selected]
        actual=np.array([x['actual'] for x in selected]);pred=np.array([x.get('cumulative_max_prediction',x['prediction']) for x in selected])
        candidate={n:{(x['episode'],x['seat']):x for x in q['rows']} for n,q in t['all_frozen_candidates'].items()}
        mae=float(abs(pred-actual).mean());base={}
        for name,c in candidate.items():
            p=np.array([c[i]['coherent_prediction'] for i in ids]);base[name]=float(abs(p-actual).mean())
        widths=np.array([r['interval']['half_width_by_product'][p] for p in products])
        covered=abs(pred-actual)<=widths
        cell=dict(day=r['checkpoint_day'],horizon=r['horizon'],selected=r['selected_model'],mae=mae,
                  per_product_mae=dict(zip(products,abs(pred-actual).mean(0).tolist())),baseline_mae=base,
                  coverage=t.get('cumulative_max_mean_coverage',t['mean_coverage']),all_nine_coverage=float(covered.all(1).mean()))
        cells.append(cell)
        # The same episodes recur across days; average within each episode
        # before resampling, avoiding 450 pseudoreplicated observations.
        for j,eid in enumerate(ids):
            errors[eid].append(dict(day=r['checkpoint_day'],horizon=r['horizon'],selected=float(abs(pred[j]-actual[j]).mean()),
                **{n:float(abs(np.array(candidate[n][eid]['coherent_prediction'])-actual[j]).mean()) for n in candidate}))
    for horizon in [3,6,'end','all']:
        for baseline in ['count_timing_ridge','own_product_demand_ridge','nearest_state']:
            per=[]
            for rows in errors.values():
                keep=[x for x in rows if horizon=='all' or x['horizon']==horizon]
                per.append([np.mean([x['selected'] for x in keep]),np.mean([x[baseline] for x in keep])])
            per=np.asarray(per);draw=per[rng.integers(0,len(per),(5000,len(per)))].mean(1)
            improvement=100*(1-per[:,0].mean()/per[:,1].mean())
            ci=np.quantile(100*(1-draw[:,0]/draw[:,1]),[.025,.975]).tolist()
            bootstrap.append(dict(horizon=horizon,baseline=baseline,selected_mae=float(per[:,0].mean()),baseline_mae=float(per[:,1].mean()),
                                  error_reduction_percent=float(improvement),episode_bootstrap95_percent=ci))
    result=dict(cells=cells,paired_episode_bootstrap=bootstrap,n_episodes=len(errors),
                metric='Mean absolute error in harvested/collected units; all nine products equally weighted. Episode bootstrap resamples complete episode vectors across days; not a profit metric.')
    (OUT/'forecast/independent_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(bootstrap,indent=2))
    print('day12/end products',json.dumps(next(x for x in cells if x['day']==12 and x['horizon']=='end')['per_product_mae']))
if __name__=='__main__':main()

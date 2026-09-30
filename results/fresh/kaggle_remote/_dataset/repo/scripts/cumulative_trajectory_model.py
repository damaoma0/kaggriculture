"""Compact trained artifact and coherent multi-horizon prediction API."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import numpy as np
from cumulative_forecast_model import predict_checkpoint

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning/forecast'
def export(report_path,out_path):
    report=json.loads(Path(report_path).read_text(encoding='utf-8'))
    frozen=json.loads((OUT/'frozen_selection.json').read_text(encoding='utf-8'))
    models=[]
    for r in report['results']:
        a=dict(r['fitted_model']);a['empirical_residual_width']=r['interval']['half_width_by_product'];models.append(a)
    obj=dict(schema_version=1,products=report['products'],models=models,
        development_sha256=frozen['development_sha256'],freeze_sha256=sha256((OUT/'frozen_selection.json').read_bytes()).hexdigest(),
        scope='UMG56266758 policy-conditional forecast. Coefficients use75 development games only; this file contains no test labels or future shops.',
        uncertainty='Empirical marginal residual widths; no joint or distribution-free coverage guarantee.')
    Path(out_path).write_text(json.dumps(obj,separators=(',',':')),encoding='utf-8')
    return obj
def load(path=OUT/'trained_model.json'):
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    obj['lookup']={(m['checkpoint_day'],str(m['horizon'])):m for m in obj['models']}
    return obj
def predict_trajectory(model,checkpoint):
    day=int(checkpoint['day']);products=model['products'];rows=[];running=np.zeros(len(products))
    for horizon in [3,6,'end']:
        if horizon!='end' and day+horizon>30:continue
        result=predict_checkpoint(model['lookup'],day,horizon,checkpoint)
        raw=np.array(result['remaining_increment']);running=np.maximum(running,raw)
        a=model['lookup'][(day,str(horizon))]
        q=np.array([a['empirical_residual_width'][p] for p in products])
        rows.append(dict(horizon=horizon,end_day=30 if horizon=='end' else day+horizon,
            remaining=dict(zip(products,running.tolist())),
            cumulative={p:float(checkpoint['cumulative_output'].get(p,0)+running[i]) for i,p in enumerate(products)},
            marginal_lower=dict(zip(products,np.maximum(0,running-q).tolist())),
            marginal_upper=dict(zip(products,(running+q).tolist())),selected_model=a['model']))
    return dict(day=day,products=products,horizons=rows,uncertainty=model['uncertainty'])
def main():
    p=argparse.ArgumentParser();p.add_argument('--export',action='store_true');p.add_argument('--validate',action='store_true');a=p.parse_args()
    if a.export:
        dest=OUT/'trained_model.json';export(OUT/'forecast_results.json',dest);print('model bytes',dest.stat().st_size)
    if a.validate:
        model=load();data=json.loads((OUT.parent/'dataset_test.json').read_text(encoding='utf-8'))
        report=json.loads((OUT/'forecast_results.json').read_text(encoding='utf-8'));expected={}
        for r in report['results']:
            for x in r['frozen_test']['rows']:
                expected[(int(x['episode']),x['seat'],r['checkpoint_day'],str(r['horizon']))]=x.get('cumulative_max_prediction',x['prediction'])
        n=0;max_delta=0
        for game in data['games']:
            for day,checkpoint in game['checkpoints'].items():
                pred=predict_trajectory(model,checkpoint)
                for r in pred['horizons']:
                    wanted=expected[(game['episode'],game['seat'],int(day),str(r['horizon']))]
                    got=[r['remaining'][x] for x in model['products']]
                    delta=float(np.max(np.abs(np.array(got)-wanted)));max_delta=max(max_delta,delta)
                    assert delta<1e-6,(game['episode'],day,r['horizon'],delta)
                    n+=1
        result=dict(checked_forecast_vectors=n,checked_product_values=n*len(model['products']),maximum_absolute_delta=max_delta,passed=True)
        (OUT/'api_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()

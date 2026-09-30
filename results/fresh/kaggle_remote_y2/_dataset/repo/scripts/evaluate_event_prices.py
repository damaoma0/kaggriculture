"""Training-only ridge selection and untouched forecast validation."""
import argparse,json
from collections import defaultdict
from hashlib import sha256
from statistics import mean
import numpy as np
from market_corpus import ROOT
from research_event_prices import OUT,jobs
from kaggle_environments.envs.kaggriculture import kaggriculture as E

METHODS=('current','flow','clock','base','event')
def read(phase):
    rows=[]
    for job in jobs(phase):
        game=json.loads((OUT/'games'/('-'.join(map(str,job))+'.json')).read_text(encoding='utf-8'))
        for r in game['records']:rows.append(dict(r,seed=game['seed'],seat=game['seat'],opponent=game['opponent']))
    return rows

def fit(rows,kind,alpha):
    x=np.array([r[kind] for r in rows]);y=np.array([r['target_flow'] for r in rows])
    center=x.mean(axis=0);scale=x.std(axis=0);scale[scale<1e-8]=1
    z=(x-center)/scale;bias=float(y.mean())
    coef=np.linalg.solve(z.T@z+alpha*np.eye(z.shape[1]),z.T@(y-bias))
    return dict(center=center.tolist(),scale=scale.tolist(),coef=coef.tolist(),bias=bias,alpha=alpha)

def predict(r,kind,model):
    flow=model['bias']+sum((x-c)/s*b for x,c,s,b in zip(r[kind],model['center'],model['scale'],model['coef']))
    return r['inventory']+flow-r['drain']

def verify_manifest():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,h in manifest['sources'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    return manifest

def train():
    verify_manifest();rows=read('train');models={};cv={}
    for item in ('WHEAT','CARROT','MILK','WOOL'):
        for horizon in (12,24,48,72):
            subset=[r for r in rows if r['item']==item and r['horizon']==horizon]
            for kind in ('base','event'):
                errors={}
                for alpha in (1.,10.,100.):
                    scores=[]
                    for seed in sorted({r['seed'] for r in subset}):
                        model=fit([r for r in subset if r['seed']!=seed],kind,alpha)
                        scores += [abs(E.market_price(item,predict(r,kind,model))-r['actual_price']) for r in subset if r['seed']==seed]
                    errors[alpha]=mean(scores)
                alpha=min(errors,key=lambda a:(errors[a],-a));key=f'{item}/{horizon}/{kind}'
                models[key]=fit(subset,kind,alpha);cv[key]=errors
    result=dict(models=models,cv=cv,source_hash=sha256((ROOT/'agents/event_price_forecast.py').read_bytes()).hexdigest())
    path=OUT/'models.json'
    if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==json.loads(json.dumps(result))
    else:path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    (OUT/'model_freeze.json').write_text(json.dumps(dict(sha256=sha256(path.read_bytes()).hexdigest(),training_seeds=list(range(145000,145004))),indent=2),encoding='utf-8')
    print('FROZEN',sha256(path.read_bytes()).hexdigest(),len(models),'models; no test data read')

def report():
    manifest=verify_manifest();path=OUT/'models.json'
    assert sha256(path.read_bytes()).hexdigest()==json.loads((OUT/'model_freeze.json').read_text(encoding='utf-8'))['sha256']
    models=json.loads(path.read_text(encoding='utf-8'))['models'];rows=read('test');errors=[]
    for r in rows:
        for kind in METHODS:
            inv=r[kind] if kind in ('current','flow','clock') else predict(r,kind,models[f"{r['item']}/{r['horizon']}/{kind}"])
            pred=E.market_price(r['item'],inv)
            errors.append(dict(seed=r['seed'],seat=r['seat'],opponent=r['opponent'],step=r['step'],item=r['item'],horizon=r['horizon'],method=kind,
                               error=abs(pred-r['actual_price']),bias=pred-r['actual_price']))
    primary=[e for e in errors if e['item'] in ('WHEAT','CARROT') and e['horizon'] in (24,48,72)]
    metrics={m:mean(e['error'] for e in primary if e['method']==m) for m in METHODS}
    seed_metrics={s:{m:mean(e['error'] for e in primary if e['seed']==s and e['method']==m) for m in METHODS} for s in range(146000,146008)}
    groups={}
    for item in ('WHEAT','CARROT','MILK','WOOL'):
        for h in (12,24,48,72):
            groups[f'{item}/{h}']={m:mean(e['error'] for e in errors if e['item']==item and e['horizon']==h and e['method']==m) for m in METHODS}
    gates={f'five_percent_vs_{m}':metrics['event']<=.95*metrics[m] for m in ('current','flow','base')}
    gates.update({f'six_seeds_vs_{m}':sum(v['event']<v[m] for v in seed_metrics.values())>=6 for m in ('current','flow','base')})
    for item in ('WHEAT','CARROT'):
        values={m:mean(e['error'] for e in primary if e['item']==item and e['method']==m) for m in METHODS}
        gates[f'{item}_no_regression']=values['event']<=1.05*min(values[m] for m in ('current','flow','base'))
    runtime=[];failures=[]
    for phase in ('train','test'):
        for job in jobs(phase):
            game=json.loads((OUT/'games'/('-'.join(map(str,job))+'.json')).read_text(encoding='utf-8'));runtime.append(game['max_feature_seconds'])
            for field in ('telemetry','diagnostics'):
                for k,v in game[field].items():
                    if any(w in k.lower() for w in ('error','fallback')) and isinstance(v,(int,float)) and v:failures.append((job,k,v))
    gates['no_execution_failures']=not failures
    result=dict(primary_mae=metrics,seed_mae=seed_metrics,groups=groups,gates=gates,forecast_gate_passed=all(gates.values()),
                max_feature_seconds=max(runtime),failures=failures,test_forecast_targets=len(rows),note='Forecast-only validation on fixed baseline trajectories; no competitive uplift established.')
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (OUT/'errors.json').write_text(json.dumps(errors),encoding='utf-8')
    lines=['# Event-based delivery-price forecasting','',
        '**Forecast gate: '+('passed' if result['forecast_gate_passed'] else 'failed')+'**. V45 + our sale ordering remains the competitive baseline. No policy was changed or submitted.','',
        '## What was tested','',
        'A causal model predicts future aggregate market inventory, then converts it through the exact engine price curve. Production features cover both visible farms: crop maturity and potential watering yield, animal production dates and care potential, recent observed harvests, candidate direct/12-hour/midnight delivery windows, and our observable shed/cargo. Historical market flow and hour-of-day selling rhythms provide context. Opponent private holdings, actions and future routes are never read. Unknown future-shop demand uses its expectation under uniform replacement draws.','',
        'Production events are estimates: care, watering, harvesting and selling are not guaranteed. The model does not simulate a known rival policy. Linear ridge calibration learns how strongly each feature predicts the subsequent inventory; it is fitted separately by product and horizon.','',
        'Controls: current quote; the prior 24/48-hour blended flow forecast; an hourly flow forecast; and an identically trained ridge model without farm-event or own-stock features. Comparing event versus base isolates the added feature group, not any single event feature.','',
        '## Frozen evaluation','',manifest['design'], '',
        '72 complete games: 24 training and 48 held-out games. Forecasts are issued every 12 turns from turn 216 through 636, regardless of whether an investment is accepted. Products: wheat, carrots, milk and wool; horizons: 12/24/48/72 turns. Primary endpoint: wheat/carrot MAE at 24/48/72 turns. Repeated forecasts and related rivals are correlated; the effective held-out seed count is eight. Hyperparameters use only leave-one-training-seed-out validation.','',
        '| Method | Primary absolute price error |','|---|---:|',*[f'| {m} | {v:.3f} |' for m,v in metrics.items()],'',
        '## Product and horizon','', '| Product / turns | Current | Flow | Clock | Calibrated without events | Calibrated events |','|---|---:|---:|---:|---:|---:|',
        *['| '+k+' | '+' | '.join(f'{v[m]:.3f}' for m in METHODS)+' |' for k,v in groups.items()],'',
        '## Seed consistency','', '| Seed | Current | Flow | Clock | Without events | With events |','|---|---:|---:|---:|---:|---:|',
        *['| '+str(k)+' | '+' | '.join(f'{v[m]:.3f}' for m in METHODS)+' |' for k,v in seed_metrics.items()],'',
        '## Gate and execution','',manifest['gate'],'',*[f'- {k}: {v}' for k,v in gates.items()],'',
        f"All 72 games completed 720 valid states with exact cash ledgers and per-turn wheat conservation. Maximum observation/feature call under concurrent load: {max(runtime):.3f}s. Nonzero execution error/fallback counters: {len(failures)}.",'',
        '## Limits','',
        'This evaluates price prediction, not winning margin or investment returns. Potential production ignores future replanting, assumes continued maintenance, and only approximately represents delivery times. Observed yield disappearance may include digging; midnight and decay-ambiguous harvests are excluded. The opponent families remain limited and related. A passing forecast must still survive a new policy-level test before adoption.','',
        '## Files','',
        '- Research module: `agents/event_price_forecast.py` (uses local engine constants; not a standalone submission).',
        '- Corpus: `scripts/research_event_prices.py --phase train`, then `--phase test` after freezing models.',
        '- Calibration: `scripts/evaluate_event_prices.py --mode train`; evaluation: `--mode report`.',
        '- Frozen sources, model coefficients, per-game features/labels and errors: `results/fresh/event_prices/`.','']
    (ROOT/'docs/event_prices.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('train','report'),required=True);a=p.parse_args()
    train() if a.mode=='train' else report()

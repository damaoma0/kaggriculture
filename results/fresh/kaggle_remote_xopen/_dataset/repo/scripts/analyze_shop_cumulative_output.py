"""Do unordered shop counts predict actual cumulative output for each version?

Separate per-submission nested leave-one-shop-composition-out validation.
Targets are actual harvested/collected quantities, never sales or purchases.
Models only use shops revealed by the checkpoint; no farm state or future shops.
"""
import json
from collections import Counter
from pathlib import Path
import numpy as np
from analyze_leader_shop_matrices import LEADERS, NAMES, PRODUCTS, SHOP_PRODUCTS
from mgt_late_choice import DEMAND

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/fresh/production_continuation'
SOURCE=ROOT/'results/fresh/leader_segments'
SHOPS=list(SHOP_PRODUCTS)
ALPHAS=[1.,10.,100.,1000.,None]
DAYS=[12,15,18,21,24]

def read(p):return json.loads(p.read_text(encoding='utf-8'))

def predict(x,y,z,alpha):
    center=y.mean(axis=0)
    if alpha is None:return np.maximum(0,np.tile(center,(len(z),1)))
    xm=x.mean(axis=0); xs=np.maximum(1e-6,x.std(axis=0))
    a=(x-xm)/xs; b=(z-xm)/xs
    beta=np.linalg.solve(a.T@a+alpha*np.eye(a.shape[1]),a.T@(y-center))
    return np.maximum(0,center+b@beta)

def evaluate(x,y,groups,episodes,product_names=PRODUCTS):
    predicted=np.zeros_like(y); baseline=np.zeros_like(y); selected=[]
    for group in sorted(set(groups)):
        held=np.array([g==group for g in groups]); keep=~held
        train_groups=np.array(groups)[keep]
        losses=np.zeros((len(ALPHAS),y.shape[1]))
        for inner in sorted(set(train_groups)):
            iv=train_groups==inner; it=~iv
            for j,alpha in enumerate(ALPHAS):
                p=predict(x[keep][it],y[keep][it],x[keep][iv],alpha)
                losses[j]+=((p-y[keep][iv])**2).sum(axis=0)
        best=np.argmin(losses,axis=0)
        candidates=np.array([predict(x[keep],y[keep],x[held],a) for a in ALPHAS])
        predicted[held]=np.stack([candidates[best[p],:,p] for p in range(y.shape[1])],axis=1)
        baseline[held]=y[keep].mean(axis=0)
        selected.append(dict(episodes=[episodes[i] for i in np.where(held)[0]],alphas=[ALPHAS[j] for j in best]))
    products={}
    for i,p in enumerate(product_names):
        err=predicted[:,i]-y[:,i]; base=baseline[:,i]-y[:,i]
        denom=float((base**2).sum())
        products[p]=dict(mean=float(y[:,i].mean()),min=float(y[:,i].min()),max=float(y[:,i].max()),
            mae=float(np.abs(err).mean()),baseline_mae=float(np.abs(base).mean()),
            mse_skill=1-float((err**2).sum())/denom if denom>1e-8 else None,
            baseline_sse=denom,model_sse=float((err**2).sum()))
    return dict(n=len(y),distinct_combinations=len(set(groups)),products=products,
        actual=y.tolist(),predicted=predicted.tolist(),baseline=baseline.tolist(),episodes=episodes,
        selected_regularization=selected)

def main():
    identities={e['id']:e['agents'] for e in read(SOURCE/'sample.json')['sample']}
    games=[]
    for path in sorted(SOURCE.glob('segments-*.json')):
        g=read(path);eid=g['episode']
        for seat in g['seats']:
            sub=identities[eid][seat['seat']]['sub']
            if sub not in LEADERS:continue
            assert seat['team']==NAMES[sub]
            yields=np.array([[s['physical'].get('produced:'+p,0) for p in PRODUCTS] for s in seat['segments']],dtype=float)
            assert yields.shape==(10,9) and (yields>=0).all()
            games.append(dict(episode=eid,submission=sub,shops=g['shops_by_segment']['8'],output=yields))
    assert Counter(g['submission'] for g in games)==Counter({56266758:30,56216119:30,56156662:8,56254996:8})
    results=[]
    for sub in LEADERS:
        rows=[g for g in games if g['submission']==sub]
        for day in DAYS:
            k=day//3
            counts=np.array([[g['shops'][:k].count(s) for s in SHOPS] for g in rows],dtype=float)
            exposure=np.array([[sum(day-3*(i+1) for i,s in enumerate(g['shops'][:k]) if s==shop) for shop in SHOPS] for g in rows],dtype=float)
            groups=[','.join(str(int(q)) for q in row) for row in counts]
            # Do not score one constant cumulative checkpoint against another day.
            for target in ['season_total','remaining','already_produced']:
                y=np.array([g['output'].sum(axis=0) if target=='season_total' else
                            g['output'][k:].sum(axis=0) if target=='remaining' else
                            g['output'][:k].sum(axis=0) for g in rows])
                for model,x in [('counts',counts),('counts_and_timing',np.concatenate([counts,exposure],axis=1))]:
                    score=evaluate(x,y,groups,[g['episode'] for g in rows])
                    results.append(dict(submission=sub,leader=LEADERS[sub],day=day,target=target,model=model,**score))
                if (day==12 and target=='remaining') or (day==24 and target=='season_total'):
                    # Sparse-sample check: each product uses only its own demand.
                    # It is reported separately, never selected using outer scores.
                    individual={}
                    for j,p in enumerate(PRODUCTS):
                        x=(counts@np.array([DEMAND[s].get(p,0) for s in SHOPS],dtype=float)).reshape(-1,1)
                        individual[p]=evaluate(x,y[:,j:j+1],groups,[g['episode'] for g in rows],product_names=[p])
                    results.append(dict(submission=sub,leader=LEADERS[sub],day=day,target=target,model='own_product_demand',
                        n=len(rows),distinct_combinations=len(set(groups)),products={p:r['products'][p] for p,r in individual.items()},
                        per_product_validation=individual))
            print('completed',sub,day,flush=True)
    result=dict(products=PRODUCTS,shops=SHOPS,source_snapshot='2026-09-17',results=results,
        method='Per-submission nested leave-one-shop-composition-out ridge regression; regularization selected separately per product by inner grouped validation; baseline-only option included.',
        interpretation='mse_skill is 1 - held-out model squared error / held-out training-mean squared error; negative means worse than baseline. This is predictive association, not causation.',
        limitations=['Historical versions only; n=30,30,8,8; sparse combinations.',
                     'No future shop input, but season_total includes past harvest. already_produced is descriptive only: its inputs include the checkpoint-day shop revealed after that harvest window ended.',
                     'Remaining output is the forward-looking test; it is not feasibility, value or win-rate.',
                     'Timing uses counts plus shop-days since reveal, a summary of order rather than full ordered history.',
                     'Model class is a simple regularized linear model; poor predictions do not prove absence of nonlinear information. Own-product-demand is a separately reported exploratory low-dimensional check, not a winner selected on test scores.',
                     'No uncertainty intervals or multiple-comparison significance claims; no architecture or exact rule recovered.'])
    (BASE/'shop_cumulative_output.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# Can shop combinations predict cumulative production?', '',
        'Historical September 17 leader versions, fitted separately. Output is actual harvested/collected units, excluding purchases and sales. Fertilizer means collected fertilizer.', '',
        '`counts` uses all eight shop-type counts. `counts_and_timing` adds shop-days since each reveal. `own_product_demand` is a separately reported simpler check using only each product\'s revealed shop demand (Pet Cafe/Yarn Store count double). Models are not selected using outer test scores. `remaining` is forward-looking from the checkpoint; `already_produced` is descriptive only and includes a newly revealed shop as input after its harvest window has ended.', '',
        'Each test holds out **every game with the same unordered shop combination**. A regularized linear model is trained on the other combinations. Its regularization (or a constant predictor) is chosen using inner validation, without the test games. The reference predicts each product using that leader version’s training mean at that date.', '',
        '**Score = percentage reduction in held-out squared prediction error versus the reference.** 100% is perfect; 0% matches the reference; a negative value is worse. A dash means the target is constant. These are predictive diagnostics, not causal effects or profit.', '',
        '## Season-total production from the eight shops known at day 24', '',
        '| Leader/version | n / combinations | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    def score(v):return '—' if v is None else f'{100*v:.0f}%'
    for sub in LEADERS:
        r=next(r for r in results if r['submission']==sub and r['day']==24 and r['target']=='season_total' and r['model']=='counts')
        lines.append(f"| {LEADERS[sub]} {sub} | {r['n']} / {r['distinct_combinations']} | "+' | '.join(score(r['products'][p]['mse_skill']) for p in PRODUCTS)+' |')
    lines += ['', 'The final eight-shop combination includes reveals occurring after much of the production commitment. This measures an association with the whole-season total, not what an agent could forecast at day 12.', '']
    for sub in LEADERS:
        lines += [f'## {LEADERS[sub]} — {sub}', '',
            '| Known by day | Target | Model | Wheat | Carrot | Tomato | Strawberry | Melon | Egg | Milk | Wool | Fertilizer |',
            '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for r in results:
            if r['submission']!=sub:continue
            lines.append(f"| {r['day']} | {r['target']} | {r['model']} | "+' | '.join(score(r['products'][p]['mse_skill']) for p in PRODUCTS)+' |')
        lines.append('')
    lines += ['## Limits and reproducibility','']+['- '+x for x in result['limitations']]+['',
        'Source: `results/fresh/leader_segments/segments-*.json`, previously exact-replayed and identity-checked. All fold predictions, actual quantities, mean absolute errors and chosen model penalties are in `results/fresh/production_continuation/shop_cumulative_output.json`. Reproduce with `scripts/analyze_shop_cumulative_output.py`.']
    (ROOT/'docs/shop_cumulative_output.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for r in results:
        if (r['day']==24 and r['target']=='season_total') or (r['day']==12 and r['target']=='remaining'):
            print(json.dumps({k:r[k] for k in ['submission','day','target','model','n','distinct_combinations']}),
                  json.dumps({p:round(r['products'][p]['mse_skill'],3) if r['products'][p]['mse_skill'] is not None else None for p in PRODUCTS}))

if __name__=='__main__':main()

"""Standalone scientific figures for the cumulative production research."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    s=read(OUT/'forecast/independent_summary.json');r=read(OUT/'forecast/forecast_results.json')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,3,figsize=(14,4.5),layout='constrained')
    days=[12,15,18,21,24]
    colors=['#17635c','#d68f24','#63748e']
    for ax,h,title in zip(axes,[3,6,'end'],['Next 3 days','Next 6 days','Rest of season']):
        cells=[next(x for x in s['cells'] if x['day']==d and x['horizon']==h) for d in days]
        for label,key,color in [('Frozen selected model',None,colors[0]),('Shop counts + timing','count_timing_ridge',colors[1]),('Nearest state donor','nearest_state',colors[2])]:
            vals=[x['mae'] if key is None else x['baseline_mae'][key] for x in cells]
            ax.plot(days,vals,marker='o',lw=2,label=label,color=color)
        ax.set(title=title,xlabel='Forecast checkpoint day',xticks=days);ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Mean absolute error (units / product)');axes[1].legend(loc='upper right',fontsize=8)
    fig.suptitle('UMG production forecasts: 30 unseen early shop combinations',fontsize=15)
    fig.savefig(OUT/'forecast/forecast_comparison.png',dpi=180)
    plt.close(fig)
    # Transfer error remains a separate experiment, not a strategy comparison.
    domain=r.get('domain_transfer',{}).get('results',[])
    if domain:
        fig,ax=plt.subplots(figsize=(8,4),layout='constrained')
        own=[next(x for x in s['cells'] if x['day']==d and x['horizon']=='end')['mae'] for d in days]
        transfer=[]
        for d in days:
            x=next(x for x in domain if x['checkpoint_day']==d and x['horizon']=='end')
            transfer.append(x['metrics']['mae'])
        x=np.arange(len(days));ax.bar(x-.17,own,.34,label='UMG holdout (30 games)',color='#17635c')
        ax.bar(x+.17,transfer,.34,label='Our v10 transfer (16 games)',color='#d68f24')
        ax.set(xticks=x,xticklabels=days,xlabel='Forecast checkpoint day',ylabel='Remaining-season MAE (units / product)',title='A model of UMG is less accurate on our v10 farms')
        ax.legend();ax.grid(axis='y',alpha=.2);fig.savefig(OUT/'forecast/domain_transfer.png',dpi=180);plt.close(fig)
    example=OUT/'plans/example_plan_guarded.json'
    if example.exists():
        case=read(example);plan=case['modes']['forecast_timed'];days=list(range(case['day'],30))
        assets=['WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','GOOSE','COW','SHEEP']
        a=np.array([[plan['daily'][str(d)]['plant'].get(p,0)+plan['daily'][str(d)]['buy_animal'].get(p,0) for d in days] for p in assets])
        products=r['products'];b=np.array([[s['output'].get(p,0) for s in plan['three_day_output']] for p in products])
        fig,axes=plt.subplots(2,1,figsize=(13,8.5),layout='constrained',gridspec_kw={'height_ratios':[1,1.2]})
        for ax,matrix,labels,xlabels,title in [(axes[0],a,assets,days,'New cohorts: plants established / animals added'),
                (axes[1],b,products,[f"{s['days'][0]}–{s['days'][1]-1}" for s in plan['three_day_output']],'Planned harvest and collection by three-day period')]:
            ax.imshow(np.log1p(matrix),cmap='YlGnBu',aspect='auto')
            ax.set(xticks=range(len(xlabels)),xticklabels=xlabels,yticks=range(len(labels)),yticklabels=[x.title() for x in labels],title=title)
            for y in range(len(labels)):
                for x in range(len(xlabels)):
                    if matrix[y,x]:ax.text(x,y,str(matrix[y,x]),ha='center',va='center',fontsize=8,color='white' if np.log1p(matrix[y,x])>np.log1p(matrix.max())*.6 else '#16324f')
        fig.suptitle(f"Generated whole-farm continuation • episode {case['episode']} • day {case['day']}\nExact tile mechanics and aggregate budgets; worker routes remain untested",fontsize=14)
        axes[1].set_xlabel('Game days (numbers are units; color uses log scale)')
        fig.savefig(OUT/'plans/example_production_plan.png',dpi=180);plt.close(fig)
    print('figures saved')
if __name__=='__main__':main()

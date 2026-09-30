"""Train-only model selection, held-out forecasts and fixed-flow DP diagnostic."""
import itertools,json,random,sys
from collections import defaultdict
from statistics import mean
from market_corpus import OUT,ROOT,load
F=load('forecast_eval',ROOT/'agents/market_forecast.py')
METHODS=('current','trend','flow','visible')
HORIZONS=(6,24,72,168)

def verify():
    rng=random.Random(184)
    for _ in range(30):
        item=rng.choice(F.E.PRODUCTS);path=[rng.randint(9800,10300) for _ in range(3)];q=rng.randint(1,4)
        best=-1
        for a in range(q+1):
            for b in range(q-a+1):
                added=0;total=0
                for inv,n in zip(path,(a,b,q-a-b)):
                    v,inc=F.sell_value(item,inv+added,n);total+=v;added+=inc
                best=max(best,total)
        assert F.sale_dp(item,path,q)[0]==best

def main():
    verify();records=[];diagnostics=[]
    corpus=[json.loads(p.read_text()) for p in sorted((OUT/'corpus').glob('*.json'))];assert len(corpus)==32
    for game in corpus:
        group='train' if game['opponent']=='sixday' and game['seed']<97004 else 'test_same' if game['opponent']=='sixday' else 'test_family' if game['seed']>=97004 else 'unused_family'
        if group=='unused_family':continue
        for st,obs in game['checkpoints'].items():
            t=int(st);h=min(168,719-t)
            predictions={m:F.forecast(obs,game['market'],h,m) for m in METHODS}
            # Changing unavailable future records cannot affect a forecast.
            if t==216:
                changed=game['market'][:t]+[{'inventory':{},'shops':[]} for _ in range(720-t)]
                assert predictions['flow']==F.forecast(obs,changed,h,'flow')
            for horizon in HORIZONS:
                if horizon>h:continue
                for method in METHODS:
                    errs=[];scaled=[]
                    for item in F.E.PRODUCTS:
                        price=F.E.market_price(item,predictions[method][item][horizon])
                        err=abs(price-game['market'][t+horizon]['prices'][item]);errs.append(err)
                        scaled.append(err/F.E.MARKET_PARAMS[item]['base'])
                    records.append({'group':group,'seed':game['seed'],'seat':game['seat'],'opponent':game['opponent'],'step':t,
                                    'horizon':horizon,'method':method,'mae':mean(errs),'normalized_mae':mean(scaled)})
            if h>=24 and t%48==0:
                for item in ('CARROT','TOMATO','STRAWBERRY','MELON'):
                    actual=[game['market'][t+k]['inventory'][item] for k in range(0,25,4)]
                    immediate=F.sell_value(item,actual[0],10)[0]
                    oracle=F.sale_dp(item,actual,10)[0]
                    for method in METHODS:
                        path=predictions[method][item][::4][:7]
                        _,plan=F.sale_dp(item,path,10,plan=True)
                        total=0;added=0
                        for inv,n in zip(actual,plan):
                            revenue,inc=F.sell_value(item,inv+added,n);total+=revenue;added+=inc
                        diagnostics.append({'group':group,'seed':game['seed'],'seat':game['seat'],'opponent':game['opponent'],
                                            'step':t,'item':item,'method':method,'revenue':total,'immediate':immediate,'oracle':oracle})
    metrics=[]
    for group in ('train','test_same','test_family'):
        for h in HORIZONS:
            for m in METHODS:
                rows=[r for r in records if r['group']==group and r['horizon']==h and r['method']==m]
                metrics.append({'group':group,'horizon':h,'method':m,'mae':mean(r['mae'] for r in rows),'normalized_mae':mean(r['normalized_mae'] for r in rows)})
    selected=min([r for r in metrics if r['group']=='train' and r['horizon']==24],key=lambda r:r['normalized_mae'])['method']
    (OUT/'forecast_metrics.json').write_text(json.dumps(metrics,indent=2))
    (OUT/'forecast_errors.json').write_text(json.dumps(records))
    (OUT/'dp_diagnostic.json').write_text(json.dumps(diagnostics))
    (OUT/'forecast_selection.json').write_text(json.dumps({'method':selected,'criterion':'Lowest normalized 24-turn MAE, training seeds and sixday opponent only','dp_horizon':24,'lot_size':10},indent=2))
    print('SELECTED',selected)
    for r in metrics:
        if r['horizon']==24:print(r)
    for group in ('test_same','test_family'):
        rows=[r for r in diagnostics if r['group']==group and r['method']==selected]
        print(group,'lot uplift',mean(r['revenue']-r['immediate'] for r in rows),'oracle uplift',mean(r['oracle']-r['immediate'] for r in rows))

if __name__=='__main__':main()

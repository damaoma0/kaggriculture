"""Compare rival-volume predictions on twenty excluded modern episodes."""
from collections import Counter
import gzip
import json
import statistics
import time

import rival_trajectory_model as M2
import rival_trajectory_model_v3 as M3
import value_tape_search as V


def main():
    started=time.perf_counter();rows=[];day=15
    manifest=json.loads((M3.MODERN/'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['games']:
        if item['split']!='test':continue
        with gzip.open(M3.MODERN/f"{item['episode']}.json.gz",'rt',encoding='utf-8') as f:target=json.load(f)
        obs=dict(day=day,step=24*day,player=0,farms=[{},target['farms'][day]],town={'unlocked_shops':target['shops'][day]})
        old=V.rival_schedule(obs,1.0);v2=[M2.world(obs,i) for i in range(8)];v3=[M3.world(obs,i) for i in range(8)]
        for horizon in (3,6,15):
            stop=day+horizon;actual=Counter()
            for t,op,p in target['trades']:
                if day*24<=t<stop*24:actual[p]+=1 if op=='SELL' else -1
            for p in M2.PRODUCTS:
                row=dict(episode=item['episode'],horizon=horizon,product=p,actual=actual[p],
                    v1=sum(old.get(d,{}).get(p,0) for d in range(day,stop)))
                for name,worlds in (('v2',v2),('v3',v3)):
                    row[name]=statistics.mean(sum(c.get(p,0) for t,c in w['hourly'].items() if t<stop*24) for w in worlds)
                rows.append(row)
    summaries=[]
    for horizon in (3,6,15):
        sub=[r for r in rows if r['horizon']==horizon]
        summaries.append(dict(horizon=horizon,mae={m:statistics.mean(abs(r[m]-r['actual']) for r in sub) for m in ('v1','v2','v3')},
            by_product={p:{m:statistics.mean(abs(r[m]-r['actual']) for r in sub if r['product']==p) for m in ('v1','v2','v3')} for p in M2.PRODUCTS}))
    result=dict(train_modern=40,test_modern=20,rows=rows,summary=summaries,model_sha256=M3.MODEL_SHA256,seconds=time.perf_counter()-started)
    (M3.MODERN.parent/'modern_forecast_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(summaries,indent=2),flush=True)


if __name__=='__main__':main()

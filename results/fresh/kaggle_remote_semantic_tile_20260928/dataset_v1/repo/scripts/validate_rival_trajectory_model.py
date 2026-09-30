"""Held-out sale forecast audit on the pre-existing 30 unseen shop prefixes."""
from collections import Counter
from hashlib import sha256
import gzip
import json
import statistics
import time

import rival_trajectory_model as M
import value_tape_search as V


def main():
    started=time.perf_counter();day=15;rows=[]
    manifest=json.loads((M.LIBRARY/'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['games']:
        if item['split']!='test':continue
        with gzip.open(M.LIBRARY/f"{item['episode']}.json.gz",'rt',encoding='utf-8') as f:target=json.load(f)
        obs=dict(day=day,step=day*24,player=0,farms=[{},target['farms'][day]],town={'unlocked_shops':target['shops'][day]})
        original=V.rival_schedule(obs,1.0)
        worlds=[M.world(obs,i) for i in range(8)]
        for horizon in (3,6,15):
            stop=min(30,day+horizon)
            actual=Counter()
            for t,op,p in target['trades']:
                if day*24<=t<stop*24:actual[p]+=1 if op=='SELL' else -1
            for p in M.PRODUCTS:
                old=sum(original.get(d,{}).get(p,0) for d in range(day,stop))
                new=statistics.mean(sum(c.get(p,0) for t,c in w['hourly'].items() if t<stop*24) for w in worlds)
                rows.append(dict(episode=item['episode'],horizon=horizon,product=p,actual=actual[p],v1=old,v2=new))
        print(json.dumps(dict(episode=item['episode'],complete=True,seconds=round(time.perf_counter()-started,1))),flush=True)
    summaries=[]
    for horizon in (3,6,15):
        subset=[r for r in rows if r['horizon']==horizon]
        summaries.append(dict(horizon=horizon,n=len(subset),
            v1_mae=statistics.mean(abs(r['v1']-r['actual']) for r in subset),
            v2_mae=statistics.mean(abs(r['v2']-r['actual']) for r in subset),
            by_product={p:{model:statistics.mean(abs(r[model]-r['actual']) for r in subset if r['product']==p) for model in ('v1','v2')} for p in M.PRODUCTS}))
    result=dict(completed=True,train_games=75,test_games=30,origin_day=day,summary=summaries,rows=rows,
        model_sha256=M.MODEL_SHA256,seconds=time.perf_counter()-started,
        limitation='Unseen older UMG games. Forecast accuracy is separate from policy profit and modern opponent generalization.')
    path=M.LIBRARY.parent/'rival_forecast_validation.json'
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(summaries,indent=2),flush=True)


if __name__=='__main__':main()

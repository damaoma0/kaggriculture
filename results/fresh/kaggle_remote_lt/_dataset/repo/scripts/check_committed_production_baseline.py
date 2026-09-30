"""Post-analysis diagnostic: service existing assets, establish no new cohorts."""
from collections import Counter
import json
from pathlib import Path
import numpy as np
from cumulative_engine_profiles import engine_profile,PRODUCTS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    games=read(OUT/'dataset_test.json')['games'];rows=[]
    for day in [12,15,18,21,24]:
        pred={3:[],6:[],'end':[]};actual={3:[],6:[],'end':[]}
        for game in games:
            checkpoint=game['checkpoints'][str(day)];obs=checkpoint['observation'];daily={d:Counter() for d in range(day,30)}
            for line in obs['farms'][game['seat']]['tiles']:
                for tile in line:
                    if not isinstance(tile,dict) or not(tile.get('crop') or tile.get('animal')):continue
                    outputs,_,_,_=engine_profile(tile,day,30)
                    for p,values in outputs.items():
                        for d,q in values.items():daily[d][p]+=q
            for h in [3,6,'end']:
                endpoint=30 if h=='end' else day+h
                pred[h].append([sum(daily[d][p] for d in range(day,endpoint)) for p in PRODUCTS])
                actual[h].append([sum(s['output'][p] for s in game['segments'] if day<=s['days'][0]<endpoint) for p in PRODUCTS])
        for h in [3,6,'end']:
            p=np.array(pred[h]);a=np.array(actual[h]);rows.append(dict(day=day,horizon=h,mae=float(abs(p-a).mean()),
                product_mae=dict(zip(PRODUCTS,abs(p-a).mean(0).tolist()))))
    result=dict(scope='Post-analysis diagnostic, not used in frozen model selection. Service all current assets with default exact engine profiles, no new planting or new animals, no extra fertilizer applications. Assumes resources/labor available; not a route.',rows=rows)
    (OUT/'forecast/committed_asset_baseline.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()

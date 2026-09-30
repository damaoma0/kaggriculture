"""V3 with a corrected screening boundary: finish balanced worlds before veto.

The first four worlds are only a coarse margin ranking. Own-cash admission is
applied after all eight futures, not to a partial, unbalanced shop sample.
Optional cached forecasts are independently reproducible public-only outputs;
their input and model hashes must match. No observed evaluation result is read.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import statistics
import time

import rival_trajectory_model_v3 as M
import value_tape_search as V
import value_tape_search_v2 as V2
from value_tape_search_v3 import assess

PLANNER_SHA256=sha256(Path(__file__).read_bytes()).hexdigest()


def choose(obs,memory,*,count=7,forecast_cache=None):
    started=time.perf_counter();candidates=V.shortlist(obs,memory,count)
    input_hash=sha256(json.dumps(V.canonical([obs,memory]),sort_keys=True,default=str).encode()).hexdigest()
    existing=V.asset_keys(obs['farms'][int(obs['player'])]);worlds=[M.world(obs,i) for i in range(8)]
    predictions={}
    if forecast_cache is not None:
        assert forecast_cache['input_sha256']==input_hash
        assert forecast_cache['model_sha256']==M.MODEL_SHA256 and forecast_cache['source_sha256']==V.SOURCE_SHA256
        predictions={r['route']:deepcopy(r['predictions']) for r in forecast_cache['candidates']}
    for candidate in candidates:
        route=candidate['route'];pred=predictions.setdefault(route,[])
        pred.extend(V2.rollout(obs,memory,route,w) for w in worlds[len(pred):4])
    base=predictions[None][:4]
    screen=[assess(c,predictions[c['route']][:4],base,existing) for c in candidates]
    finalists=sorted((r for r in screen if r['route'] is not None and not r['protection_failures']
        and r['risk_score']>0),key=lambda r:r['risk_score'],reverse=True)[:2]
    active={None,*[r['route'] for r in finalists]}
    if finalists:
        for route in active:
            pred=predictions[route];pred.extend(V2.rollout(obs,memory,route,w) for w in worlds[len(pred):8])
    rows=[]
    for c in candidates:
        route=c['route'];pred=predictions[route]
        # Cache contents must not silently add finalists to the current policy.
        if route not in active:pred=pred[:4]
        row=assess(c,pred,predictions[None][:len(pred)],existing)
        row['fully_evaluated']=len(pred)==8
        row['admitted']=row['admitted'] and row['fully_evaluated']
        row['strict_admitted']=row['strict_admitted'] and row['fully_evaluated']
        rows.append(row)
    allowed=[r for r in rows if r['admitted']];strict=[r for r in rows if r['strict_admitted']]
    chosen=max(allowed,key=lambda r:r['risk_score']) if allowed else rows[0]
    strict_chosen=max(strict,key=lambda r:r['risk_score']) if strict else rows[0]
    decision=dict(day=int(obs['day']),selected=chosen['route'],selected_episode=chosen['episode'],strict_selected=strict_chosen['route'],
        candidates=rows,worlds=[dict(index=w['index'],shops=w['shops'][29],donor=w['donor']) for w in worlds],
        seconds=time.perf_counter()-started,until=min(719,(int(obs['day'])+3)*24),
        source_sha256=V.SOURCE_SHA256,planner_sha256=PLANNER_SHA256,model_sha256=M.MODEL_SHA256,
        input_sha256=input_hash,forecast_cache_used=forecast_cache is not None,
        protocol='Public-only V3 economics; margin-only screening, full eight-world own-cash admission. 115 training trajectories; cohort protection; loss budget max(500,25% of mean margin gain); three-day commitment.')
    return chosen['route'],decision

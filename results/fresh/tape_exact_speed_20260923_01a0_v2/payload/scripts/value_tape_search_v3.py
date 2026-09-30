"""Public-only tape value search with rival-family matching and scaled risk.

Forecast downside is capped at the larger of 500 or one quarter of expected
margin gain. This declared research risk budget avoids treating a 1,000 risk
identically for a 1,500 and a 15,000 opportunity. It is not a loss guarantee.
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

PLANNER_SHA256=sha256(Path(__file__).read_bytes()).hexdigest()


def assess(candidate,predictions,base,existing):
    row=V2.assess(candidate,predictions,base,existing)
    row['strict_admitted']=row['admitted']
    row['loss_budget']=max(500,.25*max(0,row['mean_margin']))
    row['admitted']=(not row['protection_failures'] and row['minimum_margin']>=-row['loss_budget']
        and statistics.mean(row['cash_deltas'])>0 and row['risk_score']>350)
    return row


def choose(obs,memory,*,count=7):
    started=time.perf_counter();candidates=V.shortlist(obs,memory,count)
    existing=V.asset_keys(obs['farms'][int(obs['player'])]);worlds=[M.world(obs,i) for i in range(8)]
    predictions={}
    for candidate in candidates:
        route=candidate['route'];predictions[route]=[V2.rollout(obs,memory,route,w) for w in worlds[:4]]
    base=predictions[None];screen=[assess(c,predictions[c['route']],base,existing) for c in candidates]
    finalists=sorted((r for r in screen if r['route'] is not None and not r['protection_failures']
        and r['risk_score']>0 and statistics.mean(r['cash_deltas'])>0),key=lambda r:r['risk_score'],reverse=True)[:2]
    active={None,*[r['route'] for r in finalists]}
    if finalists:
        for route in active:predictions[route].extend(V2.rollout(obs,memory,route,w) for w in worlds[4:])
    rows=[]
    for c in candidates:
        pred=predictions[c['route']];row=assess(c,pred,predictions[None][:len(pred)],existing)
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
        input_sha256=sha256(json.dumps(V.canonical([obs,memory]),sort_keys=True,default=str).encode()).hexdigest(),
        protocol='Public observation and our memory only. 115 older/modern training trajectories; eight stratified future shop worlds; paired official own-farm rollouts. Preserve cohorts, discount dispersion, cap projected loss at max(500,25% of mean gain); commit until next reveal.')
    return chosen['route'],decision

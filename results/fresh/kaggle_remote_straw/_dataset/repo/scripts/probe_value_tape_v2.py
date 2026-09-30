"""Development regression checks, then frozen historical/live V2 panels."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import argparse
import json
import os
import time
import traceback

import audit_value_forecast_components as A
import rival_trajectory_model as M
import value_tape_search as V
import value_tape_search_v2 as V2

OUT=A.OUT


def audit(name):
    target=OUT/f'{name}-v2-audit.json'
    started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            ctx=A.context(name);obs,memory=ctx['observation'],ctx['memory']
            base=[];pred=[];worlds=[]
            for i in range(8):
                world=M.world(obs,i)
                base.append(V2.rollout(obs,memory,None,world))
                pred.append(V2.rollout(obs,memory,ctx['spec']['route'],world))
                net={p:sum(f.get(p,0) for f in world['hourly'].values()) for p in M.PRODUCTS}
                actual={p:sum(f.get(p,0) for f in ctx['daily'].values()) for p in M.PRODUCTS}
                worlds.append(dict(index=i,donor=world['donor'],shops=world['shops'][29],projected=net,actual=actual))
            row=V2.assess(dict(route=ctx['spec']['route']),pred,base,V.asset_keys(obs['farms'][int(obs['player'])]))
            row.update(name=name,completed=True,seconds=time.perf_counter()-started,base=base,worlds=worlds,
                planner_sha256=V2.PLANNER_SHA256,model_sha256=M.MODEL_SHA256)
        except Exception:row=dict(name=name,completed=False,error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    target.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return {k:row.get(k) for k in ('name','completed','route','margin_deltas','cash_deltas','risk_score','minimum_margin','admitted','protection_failures','seconds','error')}


def main():
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(audit,name) for name in A.CASES]):print(json.dumps(future.result()),flush=True)


if __name__=='__main__':main()

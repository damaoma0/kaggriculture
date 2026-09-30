"""Development-only diagnostic of plausible opponent-model disagreement."""
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
import os
import time
import traceback

import audit_value_forecast_components as A
import rival_cohort_scenarios as C
import value_tape_search as V
import value_tape_search_v2 as V2


def worker(name):
    target=A.OUT/f'{name}-model-disagreement.json';started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            ctx=A.context(name);obs,memory=ctx['observation'],ctx['memory']
            base=[];changed=[]
            for i in range(8):
                world=C.world(obs,i,delay=0 if i%2==0 else 12)
                base.append(V2.rollout(obs,memory,None,world))
                changed.append(V2.rollout(obs,memory,ctx['spec']['route'],world))
            row=V2.assess(dict(route=ctx['spec']['route']),changed,base,V.asset_keys(obs['farms'][int(obs['player'])]))
            row.update(name=name,completed=True,seconds=time.perf_counter()-started,base=base,model_sha256=C.MODEL_SHA256)
        except Exception:row=dict(name=name,completed=False,error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    target.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return {k:row.get(k) for k in ('name','completed','margin_deltas','cash_deltas','risk_score','minimum_margin','admitted','seconds','error')}


if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker,name) for name in A.CASES]):print(json.dumps(future.result()),flush=True)

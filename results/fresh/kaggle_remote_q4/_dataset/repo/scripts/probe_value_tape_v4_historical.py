"""Fresh forecasts audit the corrected V4 screening boundary.

Native memory contains runtime object identities. Cross-process cache hashes
correctly failed equality, so this audit recomputes rather than bypassing it.
"""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import json
import os
import time
import traceback

import probe_value_tape_search as P
import value_tape_search_v4 as V4

OUT=P.ROOT/'results/fresh/value_tape_followup_20260923'


def worker(case):
    ep,day=case;target=OUT/'v4_historical'/f'{ep}-{day}.json';started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            game,pair=P.load(ep);state,memory=P.checkpoint(game,pair,day)
            if target.exists():
                prior=json.loads(target.read_text(encoding='utf-8'))
                if not prior.get('completed'):target.with_suffix('.cache_mismatch.json').write_text(json.dumps(prior,indent=2),encoding='utf-8')
            selected,decision=V4.choose(deepcopy(state[game['seat']].observation),memory)
            target.with_suffix('.decision.json').write_text(json.dumps(dict(episode=ep,day=day,decision=decision),indent=2,default=str),encoding='utf-8')
            base=P.evaluate(game,pair,state,memory,None,day)
            assert [base['cash'],base['rival_cash']]==[game['rewards'][game['seat']],game['rewards'][1-game['seat']]]
            changed=P.evaluate(game,pair,state,memory,selected,day) if selected is not None else base
            row=dict(episode=ep,day=day,completed=True,selected=selected,decision=decision,baseline=base,candidate=changed,
                margin_delta=changed['margin']-base['margin'],cash_delta=changed['cash']-base['cash'])
        except Exception:row=dict(episode=ep,day=day,completed=False,error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    row['seconds']=time.perf_counter()-started;target.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return {k:row.get(k) for k in ('episode','day','completed','selected','margin_delta','cash_delta','seconds','error')}


if __name__=='__main__':
    (OUT/'v4_historical').mkdir(exist_ok=True)
    cases=[(111262874,12),(111287532,12),(111269605,15)]
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(worker,c) for c in cases]):print(json.dumps(f.result()),flush=True)

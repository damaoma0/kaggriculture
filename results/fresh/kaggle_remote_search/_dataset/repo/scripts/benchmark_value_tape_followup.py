"""Frozen follow-up decisions and controlled paired evaluations."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import time
import traceback

import probe_value_tape_search as P
import rival_trajectory_model as M
import value_tape_search as V
import value_tape_search_v2 as V2

OUT=V.ROOT/'results/fresh/value_tape_followup_20260923'


def historical(job):
    episode,day,folder=job
    target=Path(folder)/f'{episode}-{day}.json'
    if target.exists():
        row=json.loads(target.read_text(encoding='utf-8'))
        return {k:row.get(k) for k in ('episode','day','completed','selected','margin_delta','seconds','error')}
    started=time.perf_counter()
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            game,pair=P.load(episode);state,memory=P.checkpoint(game,pair,day)
            obs=deepcopy(state[game['seat']].observation)
            selected,decision=V2.choose(obs,memory)
            row=dict(episode=episode,day=day,completed=False,selected=selected,decision=decision,seat=game['seat'])
            target.with_suffix('.decision.json').write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
            base=P.evaluate(game,pair,state,memory,None,day)
            assert [base['cash'],base['rival_cash']]==[game['rewards'][game['seat']],game['rewards'][1-game['seat']]]
            changed=P.evaluate(game,pair,state,memory,selected,day) if selected is not None else base
            row.update(completed=True,baseline=base,candidate=changed,
                baseline_margin=base['margin'],margin=changed['margin'],
                margin_delta=changed['margin']-base['margin'],cash_delta=changed['cash']-base['cash'])
        except Exception:row=dict(episode=episode,day=day,completed=False,error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    row['seconds']=time.perf_counter()-started
    target.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return {k:row.get(k) for k in ('episode','day','completed','selected','margin_delta','seconds','error')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--panel',choices=['diagnostic','prior_sample'],default='diagnostic')
    args=parser.parse_args();folder=OUT/f'v2_{args.panel}';folder.mkdir(parents=True,exist_ok=True)
    cases=P.CASES if args.panel=='diagnostic' else json.loads((P.OUT/'holdout_design.json').read_text(encoding='utf-8'))['cases']
    design=dict(cases=cases,planner_sha256=V2.PLANNER_SHA256,model_sha256=M.MODEL_SHA256,
        source_sha256=V.SOURCE_SHA256,role='Development re-use of prior historical cases; not independent confirmation.')
    path=folder/'design.json'
    if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==json.loads(json.dumps(design))
    else:path.write_text(json.dumps(design,indent=2),encoding='utf-8')
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(historical,(ep,day,str(folder))) for ep,day in cases]):
            row=future.result();rows.append(row);print(json.dumps(row),flush=True)
    (folder/'summary.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')


if __name__=='__main__':main()

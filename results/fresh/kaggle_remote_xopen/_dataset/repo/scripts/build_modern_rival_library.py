"""Outcome-blind modern rival sample, excluding every previous target case."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
import random
import traceback

import research_labour_profit as R
import probe_value_tape_search as P

OUT=P.ROOT/'results/fresh/value_tape_followup_20260923/modern_rival_library'


def worker(item):
    target=OUT/f"{item['episode']}.json.gz"
    if target.exists():return dict(episode=item['episode'],cached=True)
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            game,pair=P.load(item['episode']);seat=1-game['seat'];farms=[];E=R.engine()
            with R.Simulator(game) as sim:
                old=E.interpreter
                def capture(state,env):
                    if sim.t%24==0:farms.append(deepcopy(state[0].observation.farms[seat]))
                    return old(state,env)
                E.interpreter=capture
                try:result=sim.run(sim.initial,0,719,pair)
                finally:E.interpreter=old
            assert result['money']==game['rewards'] and len(farms)==30
            econ=R.economic(result['events'],seat)
            assert 3000+sum(econ['revenue'].values())-sum(econ['spend'].values())==result['money'][seat]
            trades=[(t,op,p) for t,s,op,p,_ in result['events'] if s==seat and op in ('SELL','BUY_PRODUCT')]
            source=P.ROOT/f"data/ladder_panel/56395605/{item['episode']}.json.gz"
            row=dict(item,seat=seat,shops=game['shops'],farms=farms,trades=trades,verified=True,replay_sha256=sha256(source.read_bytes()).hexdigest())
            with gzip.open(target,'wt',encoding='utf-8') as f:json.dump(row,f,separators=(',',':'))
            return dict(episode=item['episode'],verified=True)
        except Exception:return dict(episode=item['episode'],error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)


def main():
    OUT.mkdir(parents=True,exist_ok=True);path=OUT/'manifest.json'
    if path.exists():design=json.loads(path.read_text(encoding='utf-8'))
    else:
        excluded={e for e,d in P.CASES}
        excluded.update(e for e,d in json.loads((P.OUT/'holdout_design.json').read_text(encoding='utf-8'))['cases'])
        ids=sorted(int(p.name.split('.')[0]) for p in (P.ROOT/'data/ladder_panel/56395605').glob('*.json.gz'))
        selected=random.Random(93703125).sample([e for e in ids if e not in excluded],60)
        design=dict(games=[dict(episode=e,split='train' if i<40 else 'test') for i,e in enumerate(selected)],
            excluded=sorted(excluded),seed=93703125,
            protocol='Random sample of complete modern historical population, without score filtering. Forty train / twenty test. All nineteen previous target cases excluded. Retrospective development; future live tests are independent.')
        path.write_text(json.dumps(design,indent=2),encoding='utf-8')
    rows=[]
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(worker,item) for item in design['games']]):
            row=f.result();rows.append(row)
            if len(rows)%10==0 or 'error' in row:print(json.dumps(dict(done=len(rows),latest=row)),flush=True)
    assert all('error' not in r for r in rows)
    print(json.dumps(dict(complete=len(rows),train=40,test=20)),flush=True)


if __name__=='__main__':main()

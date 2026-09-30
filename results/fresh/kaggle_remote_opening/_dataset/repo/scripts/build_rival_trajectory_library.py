"""Build a public-board / successful-trade library from the older frozen corpus.

Training and test episodes retain the pre-existing 75/30 split. Target games
from the value-tape experiments are not included. Private replay fields never
enter the exported predictors; official successful trades are training labels.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
import time
import traceback

import research_labour_profit as R

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/value_tape_followup_20260923/rival_library'
MANIFEST=ROOT/'results/fresh/cumulative_planning/data_manifest.json'


def worker(g):
    path=OUT/f"{g['episode']}.json.gz"
    if path.exists():return dict(episode=g['episode'],cached=True)
    with path.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            blob=Path(g['raw_path']).read_bytes()
            raw=json.loads(blob)
            ledger=json.loads(Path(g['ledger_path']).read_text(encoding='utf-8'))
            assert sha256(blob).hexdigest()==ledger['replay_sha256']
            seat=g['seat']
            shops=[list(raw['steps'][min(d*24,719)][0]['observation']['town']['unlocked_shops']) for d in range(31)]
            game=dict(episode=g['episode'],seed=ledger['seed'],seat=seat,shops=shops)
            actions=[[step[s]['action'] for step in raw['steps'][1:]] for s in range(2)]
            with R.Simulator(game) as sim:
                result=sim.run(sim.initial,0,719,actions)
            assert result['money']==ledger['rewards'],(result['money'],ledger['rewards'])
            econ=R.economic(result['events'],seat)
            assert 3000+sum(econ['revenue'].values())-sum(econ['spend'].values())==result['money'][seat]
            trades=[(t,op,p) for t,s,op,p,price in result['events'] if s==seat and op in ('SELL','BUY_PRODUCT')]
            # Public farm state, with no donor private storage or worker bags.
            farms=[deepcopy(raw['steps'][d*24][0]['observation']['farms'][seat]) for d in range(30)]
            row=dict(episode=g['episode'],seat=seat,split=g['split'],submission=g['submission'],
                shops=shops,farms=farms,trades=trades,verified=True,replay_sha256=sha256(blob).hexdigest())
            with gzip.open(path,'wt',encoding='utf-8') as f:json.dump(row,f,separators=(',',':'))
            return dict(episode=g['episode'],verified=True,transactions=len(trades))
        except Exception:return dict(episode=g['episode'],error=traceback.format_exc())
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    games=[g for g in json.loads(MANIFEST.read_text(encoding='utf-8'))['games'] if g['split'] in ('train','test')]
    assert sum(g['split']=='train' for g in games)==75 and sum(g['split']=='test' for g in games)==30
    results=[]
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker,g) for g in games]):
            row=future.result();results.append(row)
            if 'error' in row or len(results)%15==0:print(json.dumps(dict(done=len(results),latest=row)),flush=True)
    assert all('error' not in r for r in results)
    manifest=dict(games=[{k:g[k] for k in ('episode','seat','split','submission')} for g in games],
        source_manifest_sha256=sha256(MANIFEST.read_bytes()).hexdigest(),
        builder_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        protocol='Older 75 training / 30 test UMG episodes. Public daily farms and shops; successful official-engine transactions as labels. No target experiment suffixes.')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(completed=len(results),train=75,test=30)),flush=True)


if __name__=='__main__':main()

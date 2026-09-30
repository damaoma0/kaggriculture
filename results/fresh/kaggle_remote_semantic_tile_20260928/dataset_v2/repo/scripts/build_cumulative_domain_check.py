"""Outcome-independent v10 sample and exact replay labels for domain-shift checks."""
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning/domain'
PRODUCTS=['WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER']
DAYS=[12,15,18,21,24]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,o):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,indent=1),encoding='utf-8')
def verify(g):
    import analyze_leader_segments as a
    a.OUT=OUT/'ledgers'
    for p in [a.OUT,a.OUT/'actions',a.OUT/'digests']:p.mkdir(parents=True,exist_ok=True)
    return a.run(Path(g['raw_path']))
def fetch(g):
    p=Path(g['raw_path'])
    if not p.exists():
        p.parent.mkdir(parents=True,exist_ok=True)
        r=subprocess.run([str(ROOT/'.venv/Scripts/kaggle.exe'),'competitions','replay',str(g['episode']),'-p',str(p.parent),'-q'],capture_output=True,timeout=240)
        if r.returncode or not p.exists():raise RuntimeError((g['episode'],r.stderr.decode(errors='replace')[-500:]))
    return g['episode']
def main():
    manifest=OUT/'manifest.json'
    if not manifest.exists():
        paths=sorted((ROOT/'data/ladder_panel/56368334').glob('*.json.gz'))
        random.Random(20260923).shuffle(paths)
        games=[]
        for p in paths[:16]:
            with gzip.open(p,'rt',encoding='utf-8') as f:t=json.load(f)
            raw=ROOT/f"data/ladder_t10/episode-{t['episode']}-replay.json"
            if not raw.exists():raw=OUT/f"raw/episode-{t['episode']}-replay.json"
            games.append(dict(episode=t['episode'],seat=t['seat'],seed=t['seed'],raw_path=str(raw),compact_path=str(p)))
        save(manifest,dict(seed=20260923,population=len(paths),n=len(games),created_at=time.strftime('%Y-%m-%d %H:%M:%S'),
            design='Random sample of archived v10 ladder episodes selected by shuffled filenames; no outcome filtering. Frozen UMG model only; this set is a domain diagnostic, not a strategy benchmark.',games=games))
    games=read(manifest)['games']
    with ThreadPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(fetch,g) for g in games]):print('downloaded',f.result(),flush=True)
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        todo=[g for g in games if not (OUT/f"ledgers/segments-{g['episode']}.json").exists()]
        for f in as_completed([pool.submit(verify,g) for g in todo]):print('verified',f.result(),flush=True)
    rows=[]
    for g in games:
        raw=read(Path(g['raw_path']));ledger=read(OUT/f"ledgers/segments-{g['episode']}.json");seat=g['seat']
        assert raw['info']['seed']==g['seed']
        with gzip.open(g['compact_path'],'rt',encoding='utf-8') as f:compact=json.load(f)
        assert compact['rewards']==raw['rewards'] and compact['names']==raw['info']['TeamNames']
        assert compact['our_actions']==[s[seat]['action'] for s in raw['steps'][1:]]
        segments=[]
        for s in ledger['seats'][seat]['segments']:
            segments.append(dict(segment=s['segment'],days=s['days'],output={p:s['physical'].get('produced:'+p,0) for p in PRODUCTS},
                planted={p:s['physical'].get('planted:'+p,0) for p in PRODUCTS[:5]},physical=s['physical'],
                board_start=s['board_start'],board_end=s['board_end'],ledger=s['ledger']))
        checkpoints={}
        for day in DAYS:
            obs=deepcopy(raw['steps'][24*day][seat]['observation']);common=raw['steps'][24*day][0]['observation']
            for k in ['farms','market','town']:
                if k not in obs:obs[k]=deepcopy(common[k])
            obs.update(step=day*24,day=day,player=seat)
            checkpoints[str(day)]=dict(day=day,observation=obs,prior_output=segments[day//3-1]['output'],
                cumulative_output={p:sum(s['output'][p] for s in segments[:day//3]) for p in PRODUCTS})
        rows.append(dict(episode=g['episode'],seat=seat,submission=56368334,leader='our v10',split='domain',
            checkpoints=checkpoints,segments=segments,seed=g['seed'],replay_sha256=ledger['replay_sha256'],
            configuration=raw['configuration'],validation='All720 states exactly matched for both seats; compact action/identity verified.'))
    save(OUT/'dataset.json',dict(schema_version=1,products=PRODUCTS,days=DAYS,games=rows,manifest_sha256=sha256(manifest.read_bytes()).hexdigest()))
    print('domain dataset',len(rows),flush=True)
if __name__=='__main__':main()

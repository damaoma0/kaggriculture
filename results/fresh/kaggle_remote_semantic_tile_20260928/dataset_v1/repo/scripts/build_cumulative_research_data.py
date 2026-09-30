"""Frozen expansion and verified rich dataset for cumulative prediction/planning."""
import argparse
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path
import random
import subprocess
import time
from analyze_leader_shop_matrices import LEADERS, PRODUCTS, SHOP_PRODUCTS

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/cumulative_planning'
RAW=OUT/'raw_replays'
LEDGER=OUT/'verified_ledgers'
OLD=ROOT/'results/fresh/leader_segments'
MANIFEST=OUT/'data_manifest.json'
DAYS=[12,15,18,21,24]

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=1),encoding='utf-8')
def key(shops):return tuple(shops[:4].count(s) for s in SHOP_PRODUCTS)

def select():
    if MANIFEST.exists():
        print('Frozen manifest already exists');return
    sample=read(OLD/'sample.json')['sample']
    games=[]
    for e in sample:
        if not (OLD/f"segments-{e['id']}.json").exists():continue
        ledger=read(OLD/f"segments-{e['id']}.json")
        for seat,a in enumerate(e['agents']):
            if a['sub'] not in LEADERS:continue
            games.append(dict(episode=e['id'],submission=a['sub'],leader=LEADERS[a['sub']],seat=seat,
                split='train' if a['sub']==56266758 else 'reference',
                raw_path=str(ROOT/f"data/leaders_20260917/episode-{e['id']}-replay.json"),
                ledger_path=str(OLD/f"segments-{e['id']}.json"),
                count_key=key(ledger['shops_by_segment']['8'])))
    existing=[g for g in games if g['submission']==56266758]
    assert len(existing)==30
    used={g['episode'] for g in games};used_keys={tuple(g['count_key']) for g in existing}
    candidates=[]
    for p in sorted((ROOT/'data/mg_tapes/56266758').glob('*.json.gz')):
        with gzip.open(p,'rt',encoding='utf-8') as f:t=json.load(f)
        if t['episode'] in used:continue
        candidates.append(dict(episode=t['episode'],seat=t['seat'],count_key=key(t['shops'][30])))
    rng=random.Random(20260922);rng.shuffle(candidates)
    test=[];test_keys=set()
    for c in candidates:
        k=tuple(c['count_key'])
        if k in used_keys or k in test_keys:continue
        test.append(c);test_keys.add(k)
        if len(test)==30:break
    assert len(test)==30
    train=[c for c in candidates if tuple(c['count_key']) not in test_keys][:45]
    assert len(train)==45
    for split,rows in [('train',train),('test',test)]:
        for c in rows:
            games.append(dict(**c,submission=56266758,leader='UMG',split=split,
                raw_path=str(RAW/f"episode-{c['episode']}-replay.json"),
                ledger_path=str(LEDGER/f"segments-{c['episode']}.json")))
    assert not ({tuple(g['count_key']) for g in games if g['split']=='train'} & test_keys)
    save(MANIFEST,dict(schema_version=1,seed=20260922,created_at=time.strftime('%Y-%m-%d %H:%M:%S'),
        design='30 existing UMG plus45 added training episodes;30 new test episodes, each from a distinct first-four unordered shop composition absent from all training episodes. Selection uses episode identities and first-four shops, never yields or scores. Other recorded leader versions kept as references.',
        games=games,products=PRODUCTS,shops=list(SHOP_PRODUCTS),days=DAYS))
    print('selected',len(games),'UMG train75 test30 reference46; new downloads75')

def fetch_one(g):
    p=Path(g['raw_path'])
    if p.exists():return g['episode'],'cached'
    p.parent.mkdir(parents=True,exist_ok=True)
    proc=subprocess.run([str(ROOT/'.venv/Scripts/kaggle.exe'),'competitions','replay',str(g['episode']),'-p',str(p.parent),'-q'],capture_output=True,timeout=240)
    if proc.returncode or not p.exists():
        raise RuntimeError(f"Replay {g['episode']} download failed, status {proc.returncode}: "+proc.stderr.decode(errors='replace')[-500:])
    return g['episode'],'downloaded'

def fetch():
    m=read(MANIFEST); jobs={g['episode']:g for g in m['games'] if not Path(g['raw_path']).exists()}
    print('downloads',len(jobs),flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(fetch_one,g) for g in jobs.values()]):print(*f.result(),flush=True)

def process_one(g):
    import analyze_leader_segments as audit
    audit.OUT=LEDGER
    for folder in [LEDGER,LEDGER/'actions',LEDGER/'digests']:folder.mkdir(parents=True,exist_ok=True)
    return audit.run(Path(g['raw_path']))

def process():
    jobs={g['episode']:g for g in read(MANIFEST)['games'] if not Path(g['ledger_path']).exists()}
    print('new exact replays',len(jobs),flush=True)
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(process_one,g) for g in jobs.values()]):print('verified',f.result(),flush=True)

def build():
    manifest=read(MANIFEST);grouped={}
    for g in manifest['games']:grouped.setdefault(g['episode'],[]).append(g)
    games=[]
    for eid,rows in grouped.items():
        p=Path(rows[0]['raw_path']);blob=p.read_bytes();raw=json.loads(blob);ledger=read(Path(rows[0]['ledger_path']))
        assert sha256(blob).hexdigest()==ledger['replay_sha256']
        assert raw['info']['EpisodeId']==eid
        for g in rows:
            seat=g['seat'];sr=ledger['seats'][seat];segments=[]
            assert ('Mother' in sr['team']) if g['submission']==56266758 else True
            for s in sr['segments']:
                segments.append(dict(segment=s['segment'],days=s['days'],output={p:s['physical'].get('produced:'+p,0) for p in PRODUCTS},
                    planted={p:s['physical'].get('planted:'+p,0) for p in PRODUCTS[:5]},physical=s['physical'],
                    board_start=s['board_start'],board_end=s['board_end'],ledger=s['ledger']))
            checkpoints={}
            for day in DAYS:
                idx=day//3;t=day*24
                obs=deepcopy(raw['steps'][t][seat]['observation'])
                common=raw['steps'][t][0]['observation']
                for f in ('farms','market','town'):
                    if f not in obs:obs[f]=deepcopy(common[f])
                obs.update(step=t,day=day,player=seat)
                assert len(obs['town']['unlocked_shops'])==min(8,idx)
                checkpoints[str(day)]=dict(day=day,observation=obs,
                    prior_output=segments[idx-1]['output'],
                    cumulative_output={p:sum(s['output'][p] for s in segments[:idx]) for p in PRODUCTS})
            games.append(dict(episode=eid,seat=seat,submission=g['submission'],leader=g['leader'],split=g['split'],
                checkpoints=checkpoints,segments=segments,replay_sha256=ledger['replay_sha256'],
                validation='Both seats: all720states and farms/private/market/town exactly matched in official replay; cash ledger reconciled. Output counts actual inventory gains inside successful unit actions.',
                source_raw=str(p),configuration=raw['configuration']))
        print('extracted',eid,flush=True)
    header=dict(schema_version=1,products=PRODUCTS,shops=list(SHOP_PRODUCTS),manifest_sha256=sha256(MANIFEST.read_bytes()).hexdigest(),days=DAYS)
    for name,splits in [('train',{'train','reference'}),('test',{'test'})]:
        save(OUT/f'dataset_{name}.json',dict(**header,games=[g for g in games if g['split'] in splits]))
    save(OUT/'dataset.json',dict(**header,games=games))
    print('dataset games',len(games),'bytes',(OUT/'dataset.json').stat().st_size,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['select','fetch','process','build','all'])
    arg=parser.parse_args().stage
    for name,fn in [('select',select),('fetch',fetch),('process',process),('build',build)]:
        if arg in (name,'all'):fn()

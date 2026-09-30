"""Read-only Kaggle refresh and exact animal extraction; bounded temporary replays."""
import json, gzip, sys, subprocess, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/all_umg_m1'
RAW = ROOT / 'data/all_umg_m1_raw'

def api():
    from kaggle.api.kaggle_api_extended import KaggleApi
    a = KaggleApi(); a.authenticate(); return a

def inventory():
    eps = api().competition_list_episodes(56395605)
    rows = [dict(id=e.id, created=str(e.create_time), state=str(e.state),
        agents=[dict(submission=a.submission_id,index=a.index,reward=a.reward,team=a.team_name,team_id=a.team_id) for a in e.agents]) for e in eps]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'m1_inventory.json').write_text(json.dumps(dict(fetched=datetime.now(timezone.utc).isoformat(),episodes=rows)),encoding='utf8')
    print('m1 inventory', len(rows), flush=True)

def ratings():
    import requests
    response=requests.post('https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes',json={'submissionId':56395605},timeout=45)
    print('ratings response',response.status_code,flush=True)
    response.raise_for_status()
    data=response.json(); (OUT/'m1_ratings.json').write_text(json.dumps(data),encoding='utf8')
    print('ratings keys',list(data),flush=True)

def probe():
    try: api().competition_episode_replay(111783885,str(RAW),quiet=True)
    except Exception as e:
        response=getattr(e,'response',None)
        print(type(e).__name__, 'retry-after',response.headers.get('Retry-After') if response is not None else None,flush=True)

def collect(mode):
    OUT.mkdir(parents=True, exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
    local = {p.name:p for base in ('data','results') for p in (ROOT/base).rglob('episode-*-replay.json') if RAW not in p.parents}
    if mode == 'umg':
        jobs=[]
        for p in (ROOT/'data/mg_tapes').glob('*/*.json.gz'):
            with gzip.open(p,'rt',encoding='utf8') as f: g=json.load(f)
            jobs.append((g['episode'],g['seat'],g))
    else:
        eps=json.loads((OUT/'m1_inventory.json').read_text(encoding='utf8'))['episodes']
        jobs=[]
        for e in eps:
            own=[a for a in e['agents'] if a['submission']==56395605]
            if len(own)!=1 or len(e['agents'])!=2 or 'COMPLETED' not in e['state']: continue
            if own[0]['reward']>=next(a['reward'] for a in e['agents'] if a['index']!=own[0]['index']): continue
            p=ROOT/f'data/ladder_panel/56395605/{e["id"]}.json.gz'
            if not p.exists(): jobs.append((e['id'],own[0]['index'],e))
    def handle(job):
        eid,seat,meta=job
        target=OUT/f'animals/{eid}.json'
        if mode=='umg' and target.exists(): return 'cached'
        name=f'episode-{eid}-replay.json'; p=local.get(name,RAW/name)
        download=p.parent==RAW
        for attempt in range(3):
            try:
                if not p.exists():
                    api().competition_episode_replay(eid,str(RAW),quiet=True)
                    time.sleep(1)
                if mode=='umg':
                    subprocess.run(['node',str(ROOT/'scripts/extract_all_umg_animals.mjs'),str(p),str(seat),str(meta['submission'])],check=True,capture_output=True,timeout=60)
                else:
                    r=json.loads(p.read_text(encoding='utf8')); steps=r['steps']; assert len(steps)==720
                    g=dict(episode=eid,created=meta['created'],submission=56395605,seat=seat,seed=r['info']['seed'],names=r['info']['TeamNames'],rewards=r['rewards'],
                        opponent=next(a for a in meta['agents'] if a['index']!=seat),
                        shops=[steps[min(719,d*24)][0]['observation']['town']['unlocked_shops'] for d in range(31)],
                        our_actions=[steps[t+1][seat].get('action') or {} for t in range(719)],opp_actions=[steps[t+1][1-seat].get('action') or {} for t in range(719)])
                    target=ROOT/f'data/ladder_panel/56395605/{eid}.json.gz'; target.parent.mkdir(parents=True,exist_ok=True)
                    with gzip.open(target,'wt',encoding='utf8') as f: json.dump(g,f,separators=(',',':'))
                if download:
                    assert p.resolve().parent==RAW.resolve()
                    p.unlink()
                return 'ok'
            except Exception as ex:
                if attempt==2: return f'FAILED {eid}: {type(ex).__name__} {str(ex)[:180]}'
                if '429' in str(ex):
                    print(mode,'rate limited; cooling down 90 seconds',flush=True)
                    time.sleep(90)
                else: time.sleep(5)
    counts={}
    with ThreadPoolExecutor(max_workers=1) as pool:
        for n,f in enumerate(as_completed([pool.submit(handle,j) for j in jobs]),1):
            status=f.result(); counts[status]=counts.get(status,0)+1
            if n%20==0 or status.startswith('FAILED'): print(mode,n,len(jobs),'ok',counts.get('ok',0),'cached',counts.get('cached',0),'failed',sum(v for k,v in counts.items() if k.startswith('FAILED')),flush=True)
    (OUT/f'{mode}_fetch_status.json').write_text(json.dumps(counts,indent=2),encoding='utf8')
    print(mode,'done',counts,flush=True)

if __name__=='__main__':
    if sys.argv[1]=='inventory': inventory()
    elif sys.argv[1]=='ratings': ratings()
    elif sys.argv[1]=='probe': probe()
    else: collect(sys.argv[1])

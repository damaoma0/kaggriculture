"""Freeze and run R4 development and independent qualification locally."""
from hashlib import sha256
from pathlib import Path
import argparse
import json
import random
import secrets
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_margin_20260924_01a0'
PREVIOUS=ROOT/'results/fresh/tape_repair_20260924_01a0'
FROZEN=PREVIOUS/'r3holdout24'
OLD=ROOT/'results/fresh/value_tape_wide_20260923_01a0'

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(v,indent=2),encoding='utf-8');q.replace(p)
def digest(x):return sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def freeze():
    assert not OUT.exists(), 'Never overwrite a frozen study'
    manifest=read(FROZEN/'source_manifest.json')
    for rel,h in manifest['sha256'].items():
        src=FROZEN/'payload'/rel;assert sha256(src.read_bytes()).hexdigest()==h
        dst=OUT/'payload'/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    rel='scripts/value_tape_margin_r4.py'
    shutil.copyfile(ROOT/rel,OUT/'payload'/rel)
    manifest['sha256'][rel]=sha256((OUT/'payload'/rel).read_bytes()).hexdigest()
    write(OUT/'source_manifest.json',manifest)
    base=(FROZEN/'run_panel.py').read_text()
    base=base[:base.index('\ndef main():')]
    def replace(a,b):
        nonlocal base
        assert base.count(a)==1,a
        base=base.replace(a,b)
    replace("PAYLOAD = OUT / 'payload'","PAYLOAD = OUT.parent / 'payload'")
    replace("(OUT / 'source_manifest.json')","(OUT.parent / 'source_manifest.json')")
    replace("N = importlib.import_module('value_tape_repair_r3' if arm=='candidate' else 'value_tape_search_v9')",
            "N = importlib.import_module('value_tape_margin_r4' if arm=='candidate' else ('value_tape_repair_r3' if arm=='r3' else 'value_tape_search_v9'))")
    assert base.count("if arm=='candidate':")==3
    base=base.replace("if arm=='candidate':","if arm in ('candidate','r3'):")
    replace("arm in ('candidate','v9')","arm in ('candidate','v9','r3')")
    base+='''
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--arm',required=True)
    args=ap.parse_args();spec=next(s for s in specs() if s['id']==args.case)
    started=time.perf_counter()
    try:result=run_game(spec,args.arm)
    except Exception:result=dict(spec=spec,arm=args.arm,completed=False,error=traceback.format_exc())
    result['seconds']=time.perf_counter()-started
    write(OUT/'arms'/f'{args.case}-{args.arm}.json',result)
    print(json.dumps({k:result.get(k) for k in ('spec','arm','completed','margin','seconds','error')}),flush=True)
    raise SystemExit(0 if result['completed'] else 1)
'''
    compile(base,'margin_study_harness','exec')
    devspecs=read(FROZEN/'design.json')['specs']
    devspecs += [s for s in read((PREVIOUS/'r3dev/design.json'))['specs'] if s['id'] in ('random-06-v56','random-11-v56')]
    assert len(devspecs)==50
    seed=secrets.randbits(128);rng=random.Random(seed)
    used={s['seed'] for s in devspecs}
    used.update(s['seed'] for s in read(OLD/'random_design.json').get('specs',[]) if 'seed' in s) if isinstance(read(OLD/'random_design.json'),dict) else None
    # Exclude every known live seed in the earlier broad panel as well.
    for p in (OLD/'pairs').glob('*.json'):
        s=read(p)['spec']
        if 'seed' in s:used.add(s['seed'])
    shops=sorted(['BAKERY','PIZZA_SHOP','BRUNCH_SPOT','YARN_STORE','ICE_CREAM_SHOP','PET_CAFE','SMOOTHIE_SHOP','FARMERS_MARKET'])
    fresh=[]
    for world in range(24):
        while True:
            game_seed=rng.randrange(2**32)
            if game_seed not in used and not 93021000<=game_seed<=93023999:break
        used.add(game_seed);draw=[rng.choice(shops) for _ in range(8)]
        for rival in ('v56','original_m1'):
            fresh.append(dict(id=f'qual-{world:02d}-{rival}',world=world,seed=game_seed,seat=world%2,
                              shops=draw,kind='live',opponent=rival))
    for name,specs,arms in [('development',devspecs,['candidate']),('qualification',fresh,['baseline','r3','candidate'])]:
        folder=OUT/name;folder.mkdir()
        (folder/'run_panel.py').write_text(base,encoding='utf-8')
        write(folder/'design.json',dict(specs=specs,arms=arms,master_seed=seed if name=='qualification' else None,
            protocol=('Exposed development: 24 earlier worlds crossed with both live opponents, plus two repair controls.' if name=='development' else
                      'Independent qualification: 24 IID uniform eight-shop worlds crossed with live V56 and original m1, alternating seat, three full-game arms. Freeze before new outcomes; no outcome-based exclusions or policy tuning. Report world-clustered uncertainty.'),
            policy_sha256=manifest['sha256'][rel],harness_sha256=sha256((folder/'run_panel.py').read_bytes()).hexdigest(),
            promotion='Report all regressions and win conversions. Do not promote if evidence is insufficient or important regressions remain. No submission.',
            schedule=[12,15,18],max_workers=2,minimum_available_gib=2.6))
    provenance={}
    for s in devspecs:
        case=s['id'];recent=case.startswith('fresh')
        sources={'r3':(FROZEN if recent else PREVIOUS/'r3dev','candidate'),
                 'baseline':(FROZEN if recent else OLD,'baseline'),
                 'v9':(FROZEN if recent else OLD,'v9' if recent else 'candidate')}
        for arm,(folder,oldarm) in sources.items():
            for category in ('arms','actions'):
                src=folder/category/f'{case}-{oldarm}.json';dst=OUT/'development'/category/f'{case}-{arm}.json'
                dst.parent.mkdir(exist_ok=True);shutil.copyfile(src,dst)
                provenance[str(dst.relative_to(OUT))]=dict(source=str(src),sha256=sha256(src.read_bytes()).hexdigest())
    write(OUT/'reference_manifest.json',provenance)
    print(json.dumps(dict(development=50,new_worlds=24,qualification_games=144,policy_sha256=manifest['sha256'][rel])))

def run(panel):
    import psutil
    folder=OUT/panel;design=read(folder/'design.json')
    jobs=[(s['id'],arm) for s in design['specs'] for arm in design['arms']]
    active=[];pending=list(jobs);done=0
    while pending or active:
        for item in active[:]:
            process,log,job=item
            if process.poll() is not None:
                log.close();active.remove(item)
                assert process.returncode==0,job
                done+=1;print(f'DONE {done}/{len(jobs)} {job}',flush=True)
        if pending and len(active)<2 and psutil.virtual_memory().available>2.6*2**30:
            case,arm=pending.pop(0);target=folder/'arms'/f'{case}-{arm}.json'
            if target.exists() and read(target).get('completed'):done+=1;continue
            (folder/'logs').mkdir(exist_ok=True)
            log=(folder/'logs'/f'{case}-{arm}.log').open('w',encoding='utf-8')
            p=subprocess.Popen([sys.executable,str(folder/'run_panel.py'),'--case',case,'--arm',arm],stdout=log,stderr=subprocess.STDOUT)
            active.append((p,log,(case,arm)))
        time.sleep(1)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['freeze','development','qualification'])
    args=ap.parse_args()
    if args.mode=='freeze':freeze()
    else:run(args.mode)

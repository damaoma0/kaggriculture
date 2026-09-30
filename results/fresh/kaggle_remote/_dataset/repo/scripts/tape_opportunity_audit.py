"""Frozen development counterfactual audit. Native policies are never edited."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_opportunity_20260924_01a0'
BASE=ROOT/'results/fresh/tape_repair_20260924_01a0'
FROZEN=BASE/'r3holdout24'
OLD=ROOT/'results/fresh/value_tape_wide_20260923_01a0'
CASES=[('random-24-v56',15),('random-02-v56',15),('random-00-v56',15),
       ('fresh-22-v56',15),('random-06-v56',15),('fresh-12-v56',12),
       ('random-11-v56',12),('fresh-11-original_m1',18)]

def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(v,indent=2),encoding='utf-8');q.replace(p)
def digest(v): return sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def key(v): return json.dumps(v,sort_keys=True)

def freeze():
    assert not OUT.exists(), 'Never overwrite a frozen audit'
    OUT.mkdir(parents=True)
    source=(FROZEN/'run_panel.py').read_text()
    source=source[:source.index('\ndef main():')]
    def replace(a,b):
        nonlocal source
        assert source.count(a)==1,a
        source=source.replace(a,b)
    replace("OUT = Path(__file__).resolve().parent",f"OUT = Path({str(OUT)!r})")
    replace("PAYLOAD = OUT / 'payload'",f"PAYLOAD = Path({str(FROZEN/'payload')!r})")
    replace("(OUT / 'source_manifest.json')",f"(Path({str(FROZEN)!r}) / 'source_manifest.json')")
    replace("searched=arm in ('candidate','v9') and t in (288,360,432)",
        "searched=(t==spec['checkpoint'] or (spec.get('continuation')=='r3' and t>spec['checkpoint'] and t in (288,360,432)))\n                if t==spec['checkpoint'] and spec.get('collect'):\n                    collect_candidates(N, ours, deepcopy(state[seat].observation), spec)\n                    raise CheckpointComplete()")
    replace("selected,decision=N.choose(obs,mem)",
        "if t==spec['checkpoint']:\n                        selected=spec['forced']\n                        decision=dict(selected=selected,until=t+72,day=t//24,forced_diagnostic=True)\n                    else:\n                        selected,decision=N.choose(obs,mem,budget_seconds=None)")
    replace("if t<288:prefix.append(deepcopy(pair))","if t<spec['checkpoint']:prefix.append(deepcopy(pair))")
    replace("physical_daily.append([dict(p) for p in physical])",
        "daily[-1]['assets']=[sorted(V.asset_keys(f)) for f in state[0].observation.farms]\n                    daily[-1]['inventories']=[deepcopy(s.observation.private) for s in state]\n                    physical_daily.append([dict(p) for p in physical])")
    compile(source,'frozen_opportunity_harness','exec')
    (OUT/'harness.py').write_text(source,encoding='utf-8')
    specs=[]
    for case,day in CASES:
        panel=FROZEN if case.startswith('fresh') else BASE/'r1dev'
        spec=next(s for s in read(panel/'design.json')['specs'] if s['id']==case)
        reference=FROZEN if case.startswith('fresh') else OLD
        decision_panel=(BASE/'r3dev' if case in ('random-06-v56','random-11-v56') else panel)
        dp=decision_panel/'decisions'/f'{case}-candidate-d{day}.json'
        specs.append(dict(spec,checkpoint=day*24,reference=str(reference),saved_decision=str(dp)))
    write(OUT/'design.json',dict(specs=specs,created=time.time(),
        protocol='Eight exposed development worlds. One fixed reveal each. Native prefix and native continuation after a three-day forced decision. Original shortlist plus existing repairs; six diverse extra donors (two each at board Hamming caps 8,14,24), each optionally repaired with at most six cohorts and three closure attempts. No more than 25 candidates per checkpoint. All choices use only checkpoint observation/memory and public forecast scenarios. Actual future shops/live opponents are label inputs only. Then confirm native, current R3 selection, and two highest-margin feasible branches per world using R3 at subsequent D12/15/18 reveals. Report all failures. No outcome-based exclusions or new holdout claim.',
        excluded_scope='This stage audits donor retrieval, valuation, and cohort repair. New planting/retirement operators require a separate executable adapter and are not claimed tested.',
        source_sha256=read(FROZEN/'source_manifest.json')['sha256'],
        harness_sha256=sha256((OUT/'harness.py').read_bytes()).hexdigest(),
        driver_sha256=sha256(Path(__file__).read_bytes()).hexdigest()))

class CheckpointComplete(Exception): pass

def collect_candidates(N,entry,obs,spec):
    V=N.V
    memory=V.memory_of(entry)
    original=read(Path(spec['saved_decision']))
    before=digest(V.canonical([obs,memory]))
    runner=N.R.runtime()  # R1 runtime, including repair adapter
    runner.prepare(obs)
    world=runner.world_batch.world(obs,0)
    until=spec['checkpoint']+72
    base=runner.rollout(obs,memory,None,world,until)
    existing=V.asset_keys(obs['farms'][spec['seat']])
    protected=existing & set(map(tuple,base['survives']))
    rows=[]
    def add(route,group,metadata,forecast=None):
        if any(key(c['route'])==key(route) for c in rows): return
        rows.append(dict(id=f'c{len(rows):02}',route=route,group=group,metadata=metadata,
                         forecast=forecast,selected=key(route)==key(original['selected'])))
    for c in original['candidates']:
        add(c['route'],'repair' if c.get('repair_assets') else 'original',c)
    assert rows[0]['route'] is None
    # Use all donor metadata from the exact same private native clone.
    ns=entry.__globals__;day=obs['day'];seat=spec['seat']
    board=ns['_mgt_labels'](ns['_mgt_board'](obs['farms'][seat]))
    ignored=memory['_MGT_IGNORE'].get(seat) or ()
    shops=list(obs['town']['unlocked_shops'])
    vectors=[ns['_mgt_vec'](shops,j) for j in range(9)]
    pool=[]
    used={c['route'] for c in rows if isinstance(c['route'],int)}
    for i,tape in enumerate(ns['_MGT_TAPES']):
        h=sum(a!=b for j,(a,b) in enumerate(zip(board,tape['lab'][day])) if j not in ignored)
        pool.append(dict(route=i,episode=tape['ep'],hamming=h,
                         distance=ns['_mgt_distance'](vectors,shops,tape,len(shops))))
    for cap in (8,14,24):
        candidates=sorted((p for p in pool if p['hamming']<=cap and p['route'] not in used),
                          key=lambda p:(p['distance'],p['hamming'],p['route']))[:2]
        for c in candidates:
            route=c['route'];used.add(route)
            prediction=runner.rollout(obs,memory,route,world,until)
            assessment=N.R.assess(c,[prediction],[base],existing)
            add(route,'expanded',assessment,prediction)
            missing=protected-set(map(tuple,prediction['survives']))
            if not missing or len(missing)>6: continue
            for attempt in range(3):
                repaired=(route,tuple(sorted(missing)))
                prediction=runner.rollout(obs,memory,repaired,world,until)
                still=protected-set(map(tuple,prediction['survives']))
                enlarged=missing|still
                if not still or enlarged==missing or len(enlarged)>6 or attempt==2: break
                missing=enlarged
            assessment=N.R.assess(dict(c,route=repaired),[prediction],[base],existing)
            add(repaired,'expanded_repair',assessment,prediction)
    assert len(rows)<=25
    assert digest(V.canonical([obs,memory]))==before
    # Prefix reconstruction must match the native baseline at this checkpoint.
    native=read(Path(spec['reference'])/'arms'/f"{spec['id']}-baseline.json")
    H=load_harness()
    assert H.physical_key(obs['farms'][seat])==native['board_keys'][seat][spec['checkpoint']]
    assert H.digest(obs['private'])==native['private_keys'][seat][spec['checkpoint']]
    write(OUT/'candidates'/f"{spec['id']}.json",dict(case=spec['id'],day=day,
        checkpoint_sha256=before,baseline_prediction=base,protected=sorted(protected),
        original_selected=original['selected'],rows=V.canonical(rows)))

def load_harness():
    module_spec=importlib.util.spec_from_file_location('opportunity_harness',OUT/'harness.py')
    H=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(H)
    H.collect_candidates=collect_candidates;H.CheckpointComplete=CheckpointComplete
    return H

def worker(case,branch,continuation):
    design=read(OUT/'design.json')
    assert sha256((OUT/'harness.py').read_bytes()).hexdigest()==design['harness_sha256']
    spec=next(s for s in design['specs'] if s['id']==case)
    H=load_harness();started=time.perf_counter()
    if branch=='collect':
        try: H.run_game(dict(spec,collect=True),'candidate')
        except CheckpointComplete: return
        raise AssertionError('Checkpoint not reached')
    candidate=next(c for c in read(OUT/'candidates'/f'{case}.json')['rows'] if c['id']==branch)
    run_id=f'{case}-{branch}-{continuation}'
    try:
        result=H.run_game(dict(spec,id=run_id,forced=candidate['route'],continuation=continuation),'candidate')
        reference=read(Path(spec['reference'])/'actions'/f'{case}-baseline.json')
        expected=H.digest([[reference[s][t] for s in range(2)] for t in range(spec['checkpoint'])])
        assert result['prefix_sha256']==expected,'Prefix changed before intervention'
        result.update(candidate=candidate,case=case,continuation=continuation,prefix_verified=True)
    except Exception: result=dict(completed=False,error=traceback.format_exc(),case=case,branch=branch)
    result['seconds']=time.perf_counter()-started
    write(OUT/'arms'/f'{run_id}.json',result)
    print(json.dumps({k:result.get(k) for k in ('case','completed','margin','seconds','error')}),flush=True)
    if not result['completed']: raise SystemExit(1)

def coordinate(stage):
    import psutil
    design=read(OUT/'design.json');jobs=[]
    for spec in design['specs']:
        case=spec['id']
        if stage=='collect': jobs.append((case,'collect','native'));continue
        rows=read(OUT/'candidates'/f'{case}.json')['rows']
        if stage=='r3':
            baseline=read(OUT/'arms'/f'{case}-c00-native.json')
            seat=spec['seat'];boundary=spec['checkpoint']//24+3
            keep=set(map(tuple,next(d for d in baseline['daily'] if d['day']==boundary)['assets'][seat]))
            start=set(map(tuple,next(d for d in baseline['daily'] if d['day']==spec['checkpoint']//24)['assets'][seat]))
            eligible=[]
            for c in rows:
                arm=read(OUT/'arms'/f"{case}-{c['id']}-native.json")
                survivors=set(map(tuple,next(d for d in arm['daily'] if d['day']==boundary)['assets'][seat]))
                if (start & keep)<=survivors: eligible.append((arm['margin'],c['id']))
            ids={'c00',*[c['id'] for c in rows if c['selected']],*[i for m,i in sorted(eligible,reverse=True)[:2]]}
            rows=[c for c in rows if c['id'] in ids]
        jobs.extend((case,c['id'],stage) for c in rows)
    if stage=='r3': write(OUT/'confirmation_design.json',dict(jobs=jobs,selection='Predeclared top two realized feasible branches plus native and original selected. Same exposed worlds, diagnostic only.'))
    running=[];pending=list(jobs);done=0
    while pending or running:
        for item in running[:]:
            p,log,job=item
            if p.poll() is not None:
                log.close();running.remove(item)
                assert p.returncode==0,job
                done+=1;print(f'DONE {done}/{len(jobs)} {job}',flush=True)
        if pending and len(running)<(1 if stage=='collect' else 2) and psutil.virtual_memory().available>2.6*2**30:
            job=pending.pop(0);case,branch,cont=job
            output=OUT/'candidates'/f'{case}.json' if stage=='collect' else OUT/'arms'/f'{case}-{branch}-{cont}.json'
            if output.exists() and (stage=='collect' or read(output).get('completed')):
                done+=1;continue
            (OUT/'logs').mkdir(exist_ok=True)
            log=(OUT/'logs'/f'{case}-{branch}-{cont}.log').open('w',encoding='utf-8')
            p=subprocess.Popen([sys.executable,str(Path(__file__)), 'worker','--case',case,'--branch',branch,'--continuation',cont],stdout=log,stderr=subprocess.STDOUT)
            running.append((p,log,job))
        time.sleep(1)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['freeze','collect','native','r3','worker'])
    ap.add_argument('--case');ap.add_argument('--branch');ap.add_argument('--continuation',default='native')
    a=ap.parse_args()
    if a.mode=='freeze': freeze()
    elif a.mode=='worker': worker(a.case,a.branch,a.continuation)
    else: coordinate(a.mode)

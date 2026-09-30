"""Frozen release test: exact archive, fresh IID worlds, serial fresh processes.

Own-call timing includes initial file loading and enforces the one-second call
allowance plus60-second overage. Actual framework/isolated archive checks are
separate. Hidden shop schedules exist only in this evaluation driver.
"""
from copy import deepcopy
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/coherent_switch_20260924_01a0/release_qualification'
PACKAGE=ROOT/'submissions/2026-09-24-mgt_v9y3'
ARMS=('baseline','y3','v9y3')
OPPONENTS={'mgt_m1':ROOT/'agents/mgt_m1.py','v56':ROOT/'data/router_refresh_20260922/v56/main.py'}


def digest(path):return sha256(path.read_bytes()).hexdigest()


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((PACKAGE/'MANIFEST.json').read_text())
    assert digest(PACKAGE/'submission.tar.gz')==manifest['archive_sha256']
    for name,wanted in manifest['files'].items():assert digest(PACKAGE/'pkg'/name)==wanted,name
    frozen=OUT/'package'
    if not frozen.exists():shutil.copytree(PACKAGE/'pkg',frozen)
    for name,wanted in manifest['files'].items():assert digest(frozen/name)==wanted,name
    archive=OUT/'submission.tar.gz'
    if not archive.exists():shutil.copyfile(PACKAGE/'submission.tar.gz',archive)
    assert digest(archive)==manifest['archive_sha256']
    hashes={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__).resolve(),ROOT/'scripts/run_coherent_opening_study.py',
        ROOT/'scripts/research_labour_profit.py',*OPPONENTS.values()]}
    frozen_manifest=dict(archive_sha256=manifest['archive_sha256'],package_files=manifest['files'],driver_hashes=hashes)
    target=OUT/'manifest.json'
    if target.exists():assert json.loads(target.read_text())==frozen_manifest
    else:target.write_text(json.dumps(frozen_manifest,indent=2))
    target=OUT/'design.json'
    if target.exists():return json.loads(target.read_text())
    names=['BAKERY','BRUNCH_SPOT','FARMERS_MARKET','ICE_CREAM_SHOP','PET_CAFE','PIZZA_SHOP','SMOOTHIE_SHOP','YARN_STORE']
    excluded=set()
    for phase in ('development','qualification'):
        prior=json.loads((ROOT/'results/fresh/coherent_opening_20260924_01a0'/phase/'design.json').read_text())
        excluded.update(w['seed'] for w in prior['worlds'])
    master=secrets.randbits(128);rng=random.Random(master);worlds=[];specs=[]
    for i in range(32):
        seed=rng.randrange(1_000_000_000,4_000_000_000)
        while seed in excluded:seed=rng.randrange(1_000_000_000,4_000_000_000)
        excluded.add(seed);shops=[rng.choice(names) for _ in range(8)]
        world=dict(id=f'r{i:02}',seed=seed,shops=shops,first_shop=shops[0])
        worlds.append(world)
        for opponent in OPPONENTS:specs.append(dict(id=f'r{i:02}-{opponent}',world=world,opponent=opponent,seat=i%2))
    design=dict(worlds=worlds,specs=specs,arms=ARMS,master_seed=master,
        protocol='32 untouched IID shop worlds, two live opponents, balanced seats; all3arms in fresh processes; serial; no tuning on outcomes.',
        primary='v9y3 versus original m1: paired final competitive margin; world-clustered bootstrap. y3 is the component control.',
        release_gates=['all192games complete; allledgers reconcile; no runtime exhaustion or candidate search errors',
                      'positive mean competitive-margin improvement over m1, with world-bootstrap95% lower bound above0',
                      'no material mean degradation versus y3; inspect new large regressions before release',
                      'exact archive passes isolated official file-loader checks; unchanged frozen hashes'])
    target.write_text(json.dumps(design,indent=2));return design


def worker(case,arm):
    import run_coherent_opening_study as H
    R=H.R;E=R.engine()
    from kaggle_environments.agent import get_last_callable
    design=json.loads((OUT/'design.json').read_text());spec=next(s for s in design['specs'] if s['id']==case)
    seat=spec['seat'];shops=spec['world']['shops'];pkg=OUT/'package'
    source={'baseline':pkg/'agents/mgt_m1.py','y3':pkg/'agents/mgt_y3.py','v9y3':pkg/'main.py'}[arm]
    # Match the official file loader's package-root discovery. The V9 modules
    # are imported from this frozen archive, never the mutable working scripts.
    sys.path.append(str(pkg))
    started=time.perf_counter();entry=get_last_callable(source.read_text(encoding='utf-8'),path=str(source));load_seconds=time.perf_counter()-started
    rival=H.load_callable(OPPONENTS[spec['opponent']],spec['opponent'])
    sim=R.Simulator(dict(seed=spec['world']['seed'],seat=seat,episode=0,
        shops=[shops[:min(8,d//3)] for d in range(31)]))
    bank=60.;timings=[];actions=sha256();prefix=sha256();daily=[];failures=[]
    with sim:
        old_hire=E._do_hire
        def hire(farm,*args,**kwargs):
            before=farm['hires_today'];result=old_hire(farm,*args,**kwargs)
            if before==farm['hires_today']:failures.append([sim.t,sim.seats.get(id(farm))])
            return result
        E._do_hire=hire
        state=deepcopy(sim.initial)
        for t in range(719):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            expected=shops[:min(8,(t//24)//3)]
            assert list(state[seat].observation.town.unlocked_shops)==expected
            if t%24==0:
                daily.append(dict(step=t,cash=[f['money'] for f in state[0].observation.farms],
                    own_assets=H.asset_counts(state[0].observation.farms[seat]) if hasattr(H,'asset_counts') else None))
            obs=deepcopy(state[seat].observation);obs['remainingOverageTime']=bank
            start=time.perf_counter();action=entry(obs);elapsed=time.perf_counter()-start+(load_seconds if t==0 else 0)
            timings.append(elapsed);bank-=max(0.,elapsed-1.)
            if bank<0:raise RuntimeError(f'own time bank exhausted atstep{t}: {bank}')
            assert isinstance(action,dict),('invalid action',t,action)
            state[seat].action=action
            state[1-seat].action=rival(deepcopy(state[1-seat].observation))
            encoded=json.dumps(H.public(action),sort_keys=True).encode();actions.update(encoded)
            if t<288:prefix.update(encoded)
            E.interpreter(state,sim.env)
            if (t+1)%24==0:state[0].observation.town.unlocked_shops[:]=shops[:min(8,((t+1)//24)//3)]
        assert all(s.status=='DONE' for s in state)
        cash=[int(state[0].observation.farms[s]['money']) for s in range(2)]
        ledger=H.ledgers_from_events(sim.events)
        for s in range(2):assert 3000+sum(ledger[s]['revenue'].values())-sum(ledger[s]['spend'].values())==cash[s]
    report=entry.__globals__.get('_V9_REPORT',{})
    assert not report.get('errors',0),report
    return dict(completed=True,spec=spec,arm=arm,cash=cash,ledgers=ledger,ledger_verified=[True,True],
        seconds=sum(timings),load_seconds=load_seconds,bank_remaining=bank,max_action_seconds=max(timings),
        timings=timings,failed_hires=failures,action_sha256=actions.hexdigest(),prefix_sha256=prefix.hexdigest(),daily=daily,
        report=H.public(report),package_root=str(entry.__globals__.get('_V9_ROOT','')))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case');ap.add_argument('--arm');ap.add_argument('--prepare-only',action='store_true');ap.add_argument('--limit',type=int)
    args=ap.parse_args();(OUT/'games').mkdir(parents=True,exist_ok=True)
    if args.case:
        try:row=worker(args.case,args.arm)
        except Exception:row=dict(completed=False,case=args.case,arm=args.arm,error=traceback.format_exc())
        (OUT/'games'/f'{args.case}-{args.arm}.json').write_text(json.dumps(row,indent=2))
        print(json.dumps({k:row[k] for k in ('completed','arm','cash','bank_remaining','error') if k in row}),flush=True)
        return
    design=prepare()
    if args.prepare_only:return
    specs=design['specs'][:args.limit] if args.limit else design['specs']
    for spec in specs:
        for arm in ARMS:
            target=OUT/'games'/f"{spec['id']}-{arm}.json"
            if target.exists():
                assert json.loads(target.read_text())['completed'],str(target)
                continue
            import psutil
            while psutil.virtual_memory().available<2_600_000_000:
                print(json.dumps(dict(waiting_for_memory=True)),flush=True);time.sleep(20)
            proc=subprocess.run([sys.executable,__file__,'--case',spec['id'],'--arm',arm],capture_output=True,text=True)
            if proc.returncode or not target.exists():raise RuntimeError(proc.stderr[-3000:]+proc.stdout[-3000:])
            row=json.loads(target.read_text());print(json.dumps(dict(id=spec['id'],arm=arm,completed=row['completed'],
                seconds=row.get('seconds'),bank=row.get('bank_remaining'),error=row.get('error'))),flush=True)
            if not row['completed']:raise RuntimeError(row['error'])
    prepare()


if __name__=='__main__':main()

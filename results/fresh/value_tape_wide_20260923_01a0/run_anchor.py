"""Use the frozen harness; gate every additional pair on exact native control."""
from pathlib import Path
from hashlib import sha256
from types import FunctionType
import argparse
import gzip
import json
import subprocess
import sys
import time
import traceback
import run_panel as P

OUT=Path(__file__).resolve().parent

def specs():
    design=json.loads((OUT/'anchor_design.json').read_text())
    return [dict(id=f'anchor-{r["episode"]["id"]}',world=r['episode']['id'],kind='replay',
        anchored=True,episode=r['episode']['id'],seat=1-r['opponent']['seat'],
        opponent=r['opponent']['team'],submission=r['opponent']['submission'],rating=r['rating'])
        for r in design['selected']]

P.specs=specs
launch=FunctionType(P.launch.__code__,dict(P.launch.__globals__,__file__=__file__),
                    'launch_anchor',P.launch.__defaults__)

def worker(case,arm):
    spec=next(s for s in specs() if s['id']==case);started=time.perf_counter()
    result={}
    try:
        if arm=='candidate':
            b=json.loads((OUT/'arms'/f'{case}-baseline.json').read_text())
            assert b['completed'] and b['control_exact']
        result=P.run_game(spec,arm)
        if arm=='baseline':
            ref=json.loads((OUT/'arms'/f'{case}-recording.json').read_text())
            checks={k:result[k]==ref[k] for k in ('cash_by_seat','board_keys','private_keys')}
            result['control_equality_checks']=checks
            result['control_exact']=all(checks.values())
            assert result['control_exact'],checks
    except Exception:
        result.update(spec=spec,arm=arm,completed=False,error=traceback.format_exc())
    result['seconds']=time.perf_counter()-started
    P.write(OUT/'arms'/f'{case}-{arm}.json',result)
    print('ANCHOR_ARM '+json.dumps({k:result.get(k) for k in ('spec','arm','completed','control_exact','cash',
        'rival_cash','selected','seconds','error')}),flush=True)
    return 0 if result['completed'] else 1

def freeze():
    path=OUT/'anchor_manifest.json'
    if path.exists():
        data=json.loads(path.read_text())
        for name,expected in data['sha256'].items():
            assert sha256((OUT/name).read_bytes()).hexdigest()==expected,name
        return
    paths=[OUT/'anchor_design.json',OUT/'prepare_anchor.py',Path(__file__)]
    paths += [OUT/'recordings'/f'{s["episode"]}.json.gz' for s in specs()]
    P.write(path,dict(sha256={p.relative_to(OUT).as_posix():sha256(p.read_bytes()).hexdigest() for p in paths},
        base_panel_manifest_sha256=sha256((OUT/'panel_manifest.json').read_bytes()).hexdigest(),
        protocol='Additional diagnostic control-exact panel after frozen-playback failures; V9 remains unchanged.'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--case');p.add_argument('--arm',choices=['recording','baseline','candidate'])
    args=p.parse_args()
    freeze()
    if args.case and args.arm:return worker(args.case,args.arm)
    for spec in specs():
        target=OUT/'pairs'/f'{spec["id"]}.json'
        if target.exists():continue
        success=True
        for arm in ('recording','baseline','candidate'):
            ok=launch(spec,arm)
            if ok is None:return 2
            if not ok:success=False;break
        if success:
            row=P.pair(spec)
            row['control_exact']=True
            P.write(target,row)
        else:
            P.write(target,dict(spec=spec,completed=False,error='One arm failed; see per-arm evidence.'))
    return 0

if __name__=='__main__':sys.exit(main())

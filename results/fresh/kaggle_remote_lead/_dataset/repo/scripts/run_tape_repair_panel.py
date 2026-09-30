"""Run a frozen repair panel serially, leaving memory for other local agents."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--version',default='r1')
    ap.add_argument('--arms',nargs='+',default=['candidate'])
    ap.add_argument('--case')
    args=ap.parse_args()
    out=ROOT/'results/fresh/tape_repair_20260924_01a0'/args.version
    specs=json.loads((out/'design.json').read_text())['specs']
    for spec in specs:
        if args.case and args.case!=spec['id']:continue
        for arm in args.arms:
            target=out/'arms'/f'{spec["id"]}-{arm}.json'
            if target.exists() and json.loads(target.read_text()).get('completed'):continue
            while psutil.virtual_memory().available/2**30<2.6:
                print('MEMORY_WAIT',round(psutil.virtual_memory().available/2**30,2),flush=True)
                time.sleep(10)
            log=out/'logs'/f'{spec["id"]}-{arm}.log'
            log.parent.mkdir(exist_ok=True)
            print('START',spec['id'],arm,flush=True)
            with log.open('w',encoding='utf-8') as handle:
                result=subprocess.run([sys.executable,str(out/'run_panel.py'),'--case',spec['id'],'--arm',arm],
                                      stdout=handle,stderr=subprocess.STDOUT)
            if result.returncode:
                print(log.read_text()[-7000:],flush=True)
                raise SystemExit(result.returncode)
            row=json.loads(target.read_text())
            print('DONE',json.dumps({k:row.get(k) for k in ('spec','margin','selected','seconds','remaining_overage_seconds')}),flush=True)


if __name__=='__main__':main()

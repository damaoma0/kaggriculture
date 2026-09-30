"""Separate output namespace; previous qualification worlds are development now."""
from pathlib import Path
import argparse
import json
import time
import traceback
import run_coherent_opening_v5 as B
from coherent_switch_v6 import make_policy

H = B.H
OUT = H.ROOT/'results/fresh/coherent_switch_20260924_01a0'
H.OWNED_SOURCES.extend([Path(__file__).resolve(), Path(__file__).with_name('coherent_switch_v6.py')])
H.fresh_policy = make_policy


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',default='w26-v56,w08-mgt_m1,w06-v56,w14-mgt_m1')
    ap.add_argument('--arms',default='contracts,guarded')
    ap.add_argument('--revision',default='v6')
    args=ap.parse_args()
    design=json.loads((H.OUT/'qualification/design.json').read_text())
    ids=args.cases.split(',')
    specs=[s for s in design['specs'] if args.cases=='all' or s['id'] in ids]
    dest=OUT/args.revision;dest.mkdir(parents=True,exist_ok=True)
    source=H.source_hashes()
    manifest=dest/'source_manifest.json'
    if manifest.exists():assert json.loads(manifest.read_text())==source
    else:manifest.write_text(json.dumps(source,indent=2))
    for spec in specs:
        for arm in args.arms.split(','):
            target=dest/f"{spec['id']}-{arm}.json"
            if target.exists():continue
            start=time.perf_counter()
            try:row=H.play(spec,arm)
            except Exception:row=dict(spec=spec,arm=arm,completed=False,error=traceback.format_exc())
            row['seconds']=time.perf_counter()-start
            target.write_text(json.dumps(row,indent=2))
            print(json.dumps(dict(id=spec['id'],arm=arm,completed=row['completed'],seconds=row['seconds'],
                                  error=row.get('error'),cash=row.get('cash'))),flush=True)
    assert source==H.source_hashes(), 'frozen inputs changed'


if __name__=='__main__':main()

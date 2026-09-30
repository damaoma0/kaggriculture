"""Check the frozen selected micro change on every locally available m1 game."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'results/fresh/m1_minimal_20260922'
OUT=PARENT/'ladder_full'


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def run(job):
    import experiment_m1_micro as micro
    micro.OUT=OUT
    return micro.historical_job(job)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=1)
    args=parser.parse_args()
    design=read(PARENT/'design.json')
    selection=read(PARENT/'selection.json')
    arm=selection['candidate']
    assert arm
    summary=read(ROOT/'results/fresh/all_umg_m1/summary.json')
    episodes=[e for e in summary['episodes'] if (ROOT/f'data/ladder_panel/56395605/{e["episode"]}.json.gz').exists()]
    assert sum(e['margin']<0 for e in episodes)==89
    (OUT/'sources').mkdir(parents=True,exist_ok=True)
    source=PARENT/'sources'/f'{arm}.py'
    assert sha256(source.read_bytes()).hexdigest()==design['source_hashes'][arm]
    shutil.copyfile(source,OUT/'sources'/source.name)
    meta=dict(created_utc=datetime.now(timezone.utc).isoformat(),candidate=arm,
        source_hash=design['source_hashes'][arm],episodes=episodes,
        baseline='Original recorded mgt_m1 rewards. Same archived source reproduced all 89 loss action streams in the audit; six diagnostic controls also reproduce both cash values and every action.',
        purpose='Historical regression check including all locally available wins and losses. Fixed opponent actions and shop schedules; not an independent live-opponent qualification.')
    (OUT/'design.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
    # Reuse already executed diagnostic candidate rows, with explicit provenance.
    (OUT/'historical').mkdir(exist_ok=True)
    for e in episodes:
        name=f'{arm}-{e["episode"]}.json'
        old=PARENT/'historical'/name
        target=OUT/'historical'/name
        if old.exists() and not target.exists():
            row=read(old)
            assert row['source_sha256']==design['source_hashes'][arm]
            row['reused_from']=str(old.relative_to(ROOT))
            target.write_text(json.dumps(row,indent=2),encoding='utf8')
    jobs=[(arm,e['episode'],design) for e in episodes]
    print(json.dumps(dict(expected=len(jobs),wins=sum(e['margin']>0 for e in episodes),losses=sum(e['margin']<0 for e in episodes))),flush=True)
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(run,j) for j in jobs]):
            print(json.dumps(future.result()),flush=True)

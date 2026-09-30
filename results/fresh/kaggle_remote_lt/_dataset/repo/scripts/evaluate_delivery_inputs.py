"""Frozen multi-seed test of delivery-valued input decisions.

Reuse audited game execution; common hidden shops remove policy-dependent shop
draw changes. Additional native-RNG integration checks are run separately.
"""
import argparse,json
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor,as_completed
import evaluate_modern_router as runner
from market_corpus import ROOT

OUT=ROOT/'results/fresh/delivery_inputs'
PATHS={**runner.PUBLIC,'baseline':ROOT/'agents/v45_our_selected.py',
       'public':ROOT/'agents/modern_router_baseline.py',
       'candidate':ROOT/'agents/v45_delivery_candidate.py'}

def jobs(phase):
    if phase=='smoke':return [('smoke',142999,0,'candidate','v44')]
    seeds=range(142000,142002) if phase=='development' else range(143000,143008)
    return [(phase,s,i,p,o) for s in seeds for i in (0,1)
            for p in ('public','baseline','candidate') for o in ('v44','v45','twocoins')]

def run(job):
    runner.OUT=OUT;runner.PATHS=PATHS
    return runner.run(job)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('smoke','development','confirmation'),required=True)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    paths=set(PATHS.values())|set(PATHS['twocoins'].parent.glob('*.py'))|{PATHS['twocoins'].parent/'actions.json',PATHS['twocoins'].parent/'settings.json'}
    paths|={ROOT/'scripts/evaluate_delivery_inputs.py',ROOT/'scripts/evaluate_modern_router.py',ROOT/'scripts/build_delivery_inputs.py',ROOT/'agents/delivery_input_overlay.py',ROOT/'agents/modern_input_overlay.py'}
    manifest=dict(sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
        jobs=jobs('development')+jobs('confirmation'),
        gate='Versus selected hybrid: positive confirmation margin; nonnegative against each rival; positive on >=6/8 seed averages; no fewer wins; cash delta >=-500; no errors/fallbacks; max call <1s. Also positive overall margin gain against public V45. No tuning between panels. No submission.',
        design='8 shop scenarios, 24/48-turn public net-flow extrapolation, 75% mean +25% lower-quartile proceeds; harvest-midnight delivery and next native sale; native plus bounded joint tours and no-investment option. Not a full farm optimizer.')
    path=OUT/'manifest.json'
    if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
    else:path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs(args.phase) if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()

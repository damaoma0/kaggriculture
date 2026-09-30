"""Freeze fresh random seeds before outcomes, then dispatch a complete panel."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
from hashlib import sha256
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/fresh/rotation_experiments'
ARMS = ['mgt_m1', 'mgt_exp_dsm', 'mgt_exp_cohort', 'mgt_exp_rotate', 'mgt_exp_hold']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['freeze', 'smoke', 'development', 'select', 'validation', 'direct'])
    p.add_argument('--candidate')
    p.add_argument('--workers', type=int, default=4)
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT/'design.json'
    if not path.exists():
        # These are far outside the reserved qualification block. Sampling from
        # 900 million integers also makes accidental previous overlap negligible.
        seeds = set()
        while len(seeds) < 46:
            seeds.add(900_000_000 + secrets.randbelow(900_000_000))
        seeds = list(seeds)
        secrets.SystemRandom().shuffle(seeds)
        design = {'created_utc': datetime.now(timezone.utc).isoformat(),
                  'smoke': seeds[:2], 'development': seeds[2:14], 'validation': seeds[14:],
                  'arms': ARMS, 'seats': [0, 1], 'opponent': 'v56',
                  'selection': 'Largest development mean paired margin improvement versus unchanged mgt_m1 against V56, among completed error-free variants within the 1-second action limit. Validate that one unchanged candidate on all 32 held-out seeds, both seats, against V56 and directly against mgt_m1. A discovery requires positive held-out paired mean margin with a seed-cluster bootstrap 95% interval above zero, positive cash delta, and positive direct head-to-head mean margin. If no development arm improves, stop and report no improvement found.',
                  'comparisons': 'Natural engine RNG: same initial seed and seat, but shops can diverge after policy-dependent weed draws. Baseline and candidates may also affect the opponent through the shared market.',
                  'build': json.loads((OUT/'build.json').read_text())}
        path.write_text(json.dumps(design, indent=2))
    design = json.loads(path.read_text())
    if args.stage == 'freeze':
        print(json.dumps(design, indent=2)); return
    if args.stage == 'select':
        from summarize_rotation_experiments import summarize
        results=summarize('development')
        assert results['present']==results['completed']==results['expected']
        eligible=[(v.get('mean_paired_margin_delta',0),name) for name,v in results['arms'].items()
                  if name!='mgt_m1' and v['completed']==24 and not v['runtime_errors'] and not v['actions_over_1s']]
        best=max(eligible,default=(0,None))
        selected=best[1] if best[0]>0 else None
        selection={'candidate':selected,'development_mean_paired_margin_delta':best[0],
                   'selected_utc':datetime.now(timezone.utc).isoformat(),
                   'rule':design['selection']}
        (OUT/'selection.json').write_text(json.dumps(selection,indent=2))
        print(json.dumps(selection));return
    if args.stage in ('smoke', 'development'):
        arms = ARMS
        seeds = design[args.stage]
        opponents = ['v56']
    else:
        if not args.candidate or args.candidate not in ARMS[1:]:
            p.error('validation requires --candidate from the frozen arms')
        arms = [args.candidate] if args.stage == 'direct' else ['mgt_m1', args.candidate]
        opponents = ['mgt_m1'] if args.stage == 'direct' else ['v56']
        seeds = design['validation']
        choice=json.loads((OUT/'selection.json').read_text())
        assert choice['candidate']==args.candidate
    for name in arms:
        expected=design['build']['baseline_sha256'] if name=='mgt_m1' else design['build']['variants'][name]['sha256']
        assert sha256((ROOT/'agents'/f'{name}.py').read_bytes()).hexdigest()==expected, f'Source changed: {name}'
    command = [sys.executable, str(ROOT/'scripts/benchmark_segment_stitch.py'),
               '--agents', ','.join(arms), '--opponents', ','.join(opponents),
               '--seeds', ','.join(map(str, seeds)), '--workers', str(args.workers),
               '--out', str(OUT/args.stage)]
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()

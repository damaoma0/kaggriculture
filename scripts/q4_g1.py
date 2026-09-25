"""G1 (the 12 leader worlds) for deploy variants, without editing scripts/lead_ablation.py (E1's): runs its cell E2
(the full deploy through _DeployAdapter) with LEAD_DEPLOY_PATH pointing at each variant file and ABL_SUFFIX
separating the result directories (results/fresh/lead_agent_20260924/abl_E2_<name>/).

usage: q4_g1.py <name>[,<name>...] [--workers N]     (name -> agents/mgt_lpv_<name>.py)
Runs the variants one after the other; prints lead_ablation's per-game lines and G1 means per variant.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = sys.argv[1].split(',')
    workers = sys.argv[sys.argv.index('--workers') + 1] if '--workers' in sys.argv else '2'
    for nm in names:
        env = dict(os.environ, ABL_SUFFIX=f'_{nm}', LEAD_DEPLOY_PATH=str(ROOT / f'agents/mgt_lpv_{nm}.py'))
        p = subprocess.run([sys.executable, str(ROOT / 'scripts/lead_ablation.py'), 'run', 'E2', '--workers', workers],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        print(f'== {nm}: rc {p.returncode}')
        print('\n'.join(l for l in p.stdout.splitlines() if l.startswith('E2 ') or 'wall' in l))
        if p.returncode:
            print(p.stderr[-2000:])
        d = ROOT / f'results/fresh/lead_agent_20260924/abl_E2_{nm}'
        rows = [json.load(open(f)) for f in sorted(d.glob('1*.json'))]
        r12 = [r['ratio'] for r in rows]
        r11 = [r['ratio'] for r in rows if r['episode'] != 112708229]
        if r12:
            print(f'   G1 mean12 {sum(r12) / len(r12):.3f}, mean11 {sum(r11) / max(1, len(r11)):.3f} ({len(r12)} games)')


if __name__ == '__main__':
    main()

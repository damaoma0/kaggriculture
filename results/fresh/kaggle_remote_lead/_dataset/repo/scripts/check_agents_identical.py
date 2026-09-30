"""Check that two agent builds under results/fresh/ladder_panel/<agent>/ produced byte-for-behaviour
identical outcomes (final cash, rival cash, dollar-exact) on every episode they share -- used to confirm
a fragment change is behaviourally inert for a build whose config never sets the new keys (CLAUDE.md
task A, 2026-09-23: mgt_m1_rebuild2, built from the patched scripts/fragments/mgt_sheep.py with the
SAME config as mgt_m1, must reproduce cached mgt_m1 results to the dollar).

Usage: .venv/Scripts/python.exe scripts/check_agents_identical.py <a> <b> [min_common=20]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'results/fresh/ladder_panel'


def main():
    a, b = sys.argv[1], sys.argv[2]
    min_common = int(sys.argv[3]) if len(sys.argv) > 3 else 20
    A = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (PANEL / a).glob('*.json')}
    B = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (PANEL / b).glob('*.json')}
    common = sorted(set(A) & set(B))
    diffs = []
    for e in common:
        ra, rb = A[e], B[e]
        if round(ra['final']) != round(rb['final']) or round(rb['rival']) != round(ra['rival']):
            diffs.append((e, ra['final'] - rb['final'], ra['rival'] - rb['rival']))
    print(f'{a} vs {b}: {len(common)} common episodes ({len(A)} in {a}, {len(B)} in {b})')
    print(f'identical to the dollar: {len(common) - len(diffs)}/{len(common)}')
    if diffs:
        print(f'DIFFERENCES ({len(diffs)}):')
        for e, df, dr in diffs[:20]:
            print(f'  {e}: final diff {df:+.0f}, rival diff {dr:+.0f}')
    status = 'PASS' if len(common) >= min_common and not diffs else 'FAIL'
    print(f'\n{status}: {"byte-for-behaviour identical" if not diffs else "MISMATCHES FOUND"} on '
          f'{len(common)} common episodes (>= {min_common} required)')
    sys.exit(0 if status == 'PASS' else 1)


if __name__ == '__main__':
    main()

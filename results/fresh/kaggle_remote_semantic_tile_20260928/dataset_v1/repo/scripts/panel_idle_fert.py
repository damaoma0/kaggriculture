"""Idle hands' own-route fertilize opportunities (arm, tier_days log): for every route planned to end before 24 (the
idle fragments), the free hours and, on its OWN stops, the unplaced FERTILIZE extras (the log's unplanned list) and the
unplaced COLLECT_FERTILIZER extras; classed as: collect before the fertilize on the route (insert both, no walking), collect
only after it (a reorder needed), no collect on the route (no supply on the path), no fertilize left on the route.
usage: panel_idle_fert.py ARM ep[,ep...]"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    arm, eps = sys.argv[1], sys.argv[2].split(',')
    c = Counter()
    hrs = Counter()
    nf = Counter()
    for ep in eps:
        T = json.load(open(ROOT / f'results/fresh/sector_20260925/multi/{arm}/{ep}.json'))['tier_days']
        for d, td in T.items():
            if int(d) >= 29:
                continue
            uf = {t for t, ops, v in td.get('unplanned') or [] if 'FERTILIZE' in ops}
            uc = {t for t, ops, v in td.get('unplanned') or [] if 'COLLECT_FERTILIZER' in ops}
            for u in td.get('units') or []:
                if u.get('kind') != 'out' or int(u.get('end', 24)) >= 24:
                    continue
                stops = [s[0] for s in u.get('stops') or []]
                carried = 0
                for tile, ops in u.get('stops') or []:
                    carried += ops.count('COLLECT_FERTILIZER') - ops.count('FERTILIZE')
                fi = [k for k, t in enumerate(stops) if t in uf]
                ci = [k for k, t in enumerate(stops) if t in uc]
                if not fi:
                    key = 'no unplaced fertilize on its own route' + (' (a collect is left on it)' if ci else '')
                elif carried > 0:
                    key = 'fertilize on route AND a spare fertilizer already in hand'
                elif ci and min(ci) < max(fi):
                    key = 'fertilize on route, a collect before it (insert both, no walk)'
                elif ci:
                    key = 'fertilize on route, collects only after it (reorder needed)'
                else:
                    key = 'fertilize on route, no collect on the route (no supply)'
                c[key] += 1
                hrs[key] += 24 - int(u['end'])
                nf[key] += len(fi)
    n = len(eps)
    tot = sum(c.values())
    print(f'{arm}: outbound routes planned to end before 24: {tot / n:.1f} hand-days a world, {sum(hrs.values()) / n:.0f} free hours')
    for k, v in c.most_common():
        print(f'   {v / n:5.1f} hand-days  {hrs[k] / n:5.1f} h  unplaced fertilizes on route {nf[k] / n:4.1f}  | {k}')


if __name__ == '__main__':
    main()

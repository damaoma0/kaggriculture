"""Compact animal comparison over panel13 from animal_diag JSONs: per arm (and the leader) per-world means of units
produced / sold / revenue, fed / cared animal-days, unfed production nights, harvests per species, and the rival's revenue
for the same product. usage: animal_compare.py k5b,ka1,..."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from animal_diag import summarize  # noqa: E402
from run_arms import PANEL13  # noqa: E402

DIAG = ROOT / 'results/fresh/threads_20260928/animal/diag'
arms = sys.argv[1].split(',')
rows = {}
for arm in arms:
    tot, n = {}, 0
    ld = {}
    for g in PANEL13:
        ep = g.split(':')[1]
        f = DIAG / f'{ep}_{arm}.json'
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        n += 1
        for who in (['leader'] if 'leader' not in rows else []) + [arm]:
            s = summarize(r[who])
            dst = ld if who == 'leader' else tot
            for sp, v in s.items():
                for k, x in v.items():
                    dst[(sp, k)] = dst.get((sp, k), 0) + x
    if ld:
        rows['leader'] = ({k: v / n for k, v in ld.items()}, n)
    rows[arm] = ({k: v / n for k, v in tot.items()}, n)
K = ['animal_days', 'fed', 'cared', 'prod_unfed', 'wipe', 'units', 'harvested', 'sold', 'revenue', 'opp_rev', 'deleted', 'escaped']
for sp in ('GOOSE', 'COW', 'SHEEP'):
    print(sp, ' '.join('%11s' % k for k in K))
    for who, (v, n) in rows.items():
        print('  %-9s' % who[:9], ' '.join('%11.1f' % v.get((sp, k), 0) for k in K), f'(n={n})')

"""Per-product table for arms of one world (dawn thread), from case_world.py logs (run it first:
case_world.py <team:ep> <ARM> results/fresh/threads_20260928/dawn/case_<ARM>.json --prods <all products>):
our units sold / revenue, rival revenue, margin contribution vs the first arm; midnight deletions; upkeep ops.
usage: dawn_products.py <REF> <ARM>[,<ARM>...] [--dir results/fresh/threads_20260928/dawn]"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = Path(sys.argv[sys.argv.index('--dir') + 1]) if '--dir' in sys.argv else ROOT / 'results/fresh/threads_20260928/dawn'
ref, arms = sys.argv[1], sys.argv[2].split(',')
PRODS = ('STRAWBERRY', 'WOOL', 'MILK', 'EGG', 'WHEAT', 'CARROT', 'TOMATO', 'MELON', 'FERTILIZER')


def load(a):
    d = json.load(open(DIR / f'case_{a}.json'))
    g = d[a]
    rev, n, rrev = Counter(), Counter(), Counter()
    for s in g['sales']:
        if s[2] != 'SELL' or s[0] < 264:
            continue
        if s[1] == 'us':
            rev[s[3]] += s[4]
            n[s[3]] += 1
        else:
            rrev[s[3]] += s[4]
    lost = Counter()
    for dd, v in (g.get('lost') or {}).items():
        lost.update(v)
    ops = Counter()
    for dd, v in (g.get('ops') or {}).items():
        ops.update(v)
    return rev, n, rrev, lost, ops


R = {a: load(a) for a in [ref] + arms}
r0 = R[ref]
print('margin contribution vs %s by product (our revenue change - rival revenue change); units sold in ()' % ref)
print('%-10s' % 'arm' + ''.join('%14s' % p[:10] for p in PRODS) + '%10s %8s' % ('total', 'deleted'))
for a in [ref] + arms:
    rev, n, rrev, lost, ops = R[a]
    cells, tot = [], 0.0
    for p in PRODS:
        m = (rev[p] - r0[0][p]) - (rrev[p] - r0[2][p])
        tot += m
        cells.append('%8.0f(%3d)' % (m, n[p]))
    print('%-10s' % a + ''.join('%14s' % c for c in cells) + '%10.0f %8d' % (tot, sum(lost.values())))
print('upkeep ops (FEED / CARE by animal, COLLECT, WATER, FERTILIZE)')
for a in [ref] + arms:
    ops = R[a][4]
    f = lambda k: ops.get(k, 0)
    print('%-10s cow F/C %3d/%3d sheep F/C %3d/%3d goose F/C %3d/%3d collect %3d water %3d fertilize %3d harvest cow/sheep %d/%d' % (
        a, f('FEED|COW'), f('CARE|COW'), f('FEED|SHEEP'), f('CARE|SHEEP'), f('FEED|GOOSE'), f('CARE|GOOSE'),
        sum(v for k, v in ops.items() if k.startswith('COLLECT')), sum(v for k, v in ops.items() if k.startswith('WATER')),
        sum(v for k, v in ops.items() if k.startswith('FERTILIZE')), f('HARVEST|COW'), f('HARVEST|SHEEP')))

"""Skeptic re-check (4/4): smaller claims of the sem4 gap analysis (units / prices table, failed buys, implied wheat
product price, per-world spot checks, the opponent-gain world 112420551). Raw JSONs only; one process, no games.
"""
import json
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
ARMS = ['LEADER', 'T0', 'T', 'S', 'S0', 'D', 'Dp']
PRODUCTS = ['WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'EGG', 'MILK', 'WOOL', 'FERTILIZER']
W = json.loads((OUT / 'worlds.json').read_text(encoding='utf-8'))
worlds = {w['episode']: w for w in W['worlds']}
R = {a: {} for a in ARMS}
for a in ARMS:
    for f in sorted((OUT / a).glob('*.json')):
        r = json.loads(f.read_text(encoding='utf-8'))
        R[a][r['episode']] = r
E = sorted(worlds)

print('units harvested / sold @ price (pooled rev/units | mean of per-game avg)')
for p in ('WHEAT', 'STRAWBERRY', 'MILK', 'EGG'):
    row = []
    for a in ARMS:
        t = [R[a][e]['totals'] for e in E]
        h = np.mean([x['harvested'].get(p, 0) for x in t])
        s = np.mean([x['sold'].get(p, 0) for x in t])
        pooled = sum(x['rev'].get(p, 0) for x in t) / max(1, sum(x['sold'].get(p, 0) for x in t))
        per = np.mean([x['rev'][p] / x['sold'][p] for x in t if x['sold'].get(p)])
        row.append(f'{a} {h:.0f}/{s:.0f}@{pooled:.0f}|{per:.0f}')
    print(f'  {p:10s}', '  '.join(row))

print('\nfailed purchases per game:')
for a in ARMS:
    agg = {}
    for e in E:
        for k, v in R[a][e]['totals'].get('failed', {}).items():
            agg[k] = agg.get(k, 0) + v
    print(f'  {a:6s}', {k: round(v / len(E), 2) for k, v in sorted(agg.items())})

print('\nimplied price of wheat bought as product = (wheat spend - 10 x wheat planted) / (bought - planted):')
for a in ARMS:
    ps = []
    for e in E:
        t = R[a][e]['totals']
        b, pl = t['bought'].get('WHEAT', 0), t['plant'].get('WHEAT', 0)
        if b > pl:
            ps.append((t['spend'].get('WHEAT', 0) - 10 * pl) / (b - pl))
    print(f'  {a:6s} n={len(ps)} min {min(ps):.1f} median {np.median(ps):.1f} max {max(ps):.1f}')

print('\nper-world spot checks (final):')
for e, a in ((112649864, 'T0'), (112910261, 'S'), (112750983, 'Dp'), (112832436, 'T'), (112661570, 'T'), (112426437, 'S')):
    print(f'  {e} {a}: {R[a][e]["final"]:,.0f}  leader {R["LEADER"][e]["final"]:,.0f}')

e = 112420551
print(f'\nworld {e}: opponent final LEADER {R["LEADER"][e]["opp_final"]:,.0f}, T {R["T"][e]["opp_final"]:,.0f}; units sold leader vs T:')
print('  ', {p: (R['LEADER'][e]['totals']['sold'].get(p, 0), R['T'][e]['totals']['sold'].get(p, 0)) for p in PRODUCTS})
tot = {a: np.mean([sum(R[a][ee]['totals']['sold'].values()) - R[a][ee]['totals']['sold'].get('FERTILIZER', 0) for ee in E]) for a in ARMS}
print('mean units sold per game excl. fertilizer:', {a: round(v) for a, v in tot.items()})

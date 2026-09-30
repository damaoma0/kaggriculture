"""Vital statistics per world (40-world panel): the leader (DSM) and arms, from season_gap.py replays and the season files.
usage: vital_stats.py ARM1,ARM2,...  (reads results/fresh/threads_20260928/gap_<arm>_40.json)"""
import json
import sys
from collections import Counter
from pathlib import Path

R = Path('results/fresh/threads_20260928')
M = Path('results/fresh/sector_20260925/multi')
arms = sys.argv[1].split(',')
eps = [g.split(':')[1] for g in (R / 'panel_dsm40b.txt').read_text().replace(',', ' ').split()]
G = {a: json.load(open(R / f'gap_{a.lower()}_40.json')) for a in arms}
cols = ['DSM'] + arms
C = {c: Counter() for c in cols}
for a in arms:
    for ep, r in G[a].items():
        C[a].update(r[a])
        if a == arms[0]:
            C['DSM'].update(r['leader'])
S = {c: Counter() for c in cols}
for c in cols:
    folder = 'LEADER' if c == 'DSM' else c
    for ep in eps:
        f = M / folder / f'{ep}.json'
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        o, r = d['money']['30']
        S[c]['wins'] += o > r
        for dd in (d.get('died') or {}).values():
            for k, v in (dd or {}).items():
                S[c]['d_plant' if k.startswith('plant_') else 'd_' + k[7:].lower()] += v
        for day, t in (d.get('tier_days') or {}).items():
            S[c]['days'] += 1
            S[c]['mid_units'] += t['cnt'].get('turn_units', 0) + t['cnt'].get('access_drop_units', 0)
            S[c]['unf_w'] += sum(1 for u, items in (t.get('unfinished') or {}).items() for it in items
                                 for o_ in (it[1] if isinstance(it[1], list) else []) if (o_[0] if isinstance(o_, list) else o_) == 'WATER')
n = len(eps)
f = lambda c, k: C[c].get(k, 0) / n
rows = []
def row(label, fn, fmt='%.0f'):
    rows.append((label, [fn(c) for c in cols], fmt))
row('own cash (end)', lambda c: f(c, 'money|us'))
row('rival cash (end)', lambda c: f(c, 'money|opp'))
row('margin', lambda c: f(c, 'money|us') - f(c, 'money|opp'))
row('wins / 40', lambda c: S[c]['wins'])
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
for p in PROD:
    row(f'{p.lower()}: made', lambda c, p=p: f(c, f'got|{p}'))
    row(f'{p.lower()}: sold @ price', lambda c, p=p: (f(c, f'us|SELL|{p}|n'), f(c, f'us|SELL|{p}|$') / max(1e-9, f(c, f'us|SELL|{p}|n'))), '%.0f @ %.1f')
row('revenue (all sales)', lambda c: sum(f(c, f'us|SELL|{p}|$') for p in PROD))
row('rival revenue (all sales)', lambda c: sum(f(c, f'opp|SELL|{p}|$') for p in PROD))
row('deleted at midnight (units)', lambda c: sum(f(c, f'lost|{p}') for p in PROD), '%.1f')
row('delivered during the day (units/day)', lambda c: S[c]['mid_units'] / max(1, S[c]['days']) if c != 'DSM' else float('nan'), '%.1f')
row('hire cost', lambda c: f(c, 'us|HIRE|$'))
row('hand-days hired', lambda c: f(c, 'us|HIRE|n'))
for op in ('WATER', 'FERTILIZE', 'HARVEST', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'PLANT'):
    row(f'ops: {op.lower()}', lambda c, op=op: sum(v for k, v in C[c].items() if k.startswith(f'ok|{op}|')) / n)
row('wheat bought (units)', lambda c: f(c, 'us|BUY_PRODUCT|WHEAT|n'))
row('animals bought (cost)', lambda c: sum(f(c, k) for k in C[c] if k.startswith('us|BUY_ANIMAL|') and k.endswith('|$')))
row('plant deaths', lambda c: S[c]['d_plant'] / n, '%.1f')
row('cow / sheep / goose escapes', lambda c: (S[c]['d_cow'] / n, S[c]['d_sheep'] / n, S[c]['d_goose'] / n), '%.1f / %.1f / %.1f')
row('unfinished planned waterings', lambda c: S[c]['unf_w'] / n if c != 'DSM' else float('nan'), '%.1f')
w = 36
print('%-*s' % (w, 'per world, 40 worlds') + ''.join('%22s' % c for c in cols))
for label, vals, fmt in rows:
    cells = []
    for v in vals:
        try:
            cells.append('%22s' % ((fmt % v) if not (isinstance(v, float) and v != v) else '-'))
        except TypeError:
            cells.append('%22s' % (fmt % tuple(v)))
    print('%-*s' % (w, label) + ''.join(cells))

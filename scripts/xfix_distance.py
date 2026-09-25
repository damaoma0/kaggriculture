"""xfix: STATE DISTANCE to the leader at the day-12 morning after each arm plays day 11 from the leader's exact morning
state (results/fresh/xfix_20260925/state11/<arm>/<ep>.json, scripts/xfix_run.py state11). Components, mean per world:
tiles of another kind / other planting-placement day / unit difference on the same asset / fertilized-until / plant
dryness (consecutive unwatered) / animal care bank / fertilizer available; seeds, shed stock (fertilizer shown
separately), cash. usage: xfix_distance.py [arm,...] -> results/fresh/xfix_20260925/distance_report.txt"""
import glob, json, sys
from collections import Counter
from pathlib import Path
OUT = Path('results/fresh/xfix_20260925')


def parse(sig):
    if '@' not in sig:
        return {'kind': sig}
    k, rest = sig.split('@', 1)
    parts = rest.split()
    r = {'kind': k, 'day': int(parts[0])}
    for p in parts[1:]:
        for pre, key in (('y', 'y'), ('c', 'c'), ('f', 'f'), ('b', 'b'), ('u', 'u')):
            if p.startswith(pre) and (p[1:].lstrip('-').isdigit()):
                r[key] = int(p[1:])
        if p.startswith('fa'):
            r['fa'] = int(p[2:])
    return r


def dist(A, L):
    d = Counter()
    ta, tl = A['state']['tiles'], L['state']['tiles']
    for a, b in zip(ta, tl):
        pa, pb = parse(a), parse(b)
        if pa['kind'] != pb['kind']:
            d['tiles_kind'] += 1
            continue
        if pa.get('day') != pb.get('day'):
            d['tiles_day'] += 1
            continue
        if pa.get('y') != pb.get('y'):
            d['units_abs'] += abs((pa.get('y') or 0) - (pb.get('y') or 0))
            d['tiles_units'] += 1
        if pa.get('f') != pb.get('f'):
            d['tiles_fert'] += 1
        if pa.get('c') != pb.get('c'):
            d['tiles_dry'] += 1
        if pa.get('b') != pb.get('b'):
            d['animal_bank'] += abs((pa.get('b') or 0) - (pb.get('b') or 0))
        if pa.get('fa') != pb.get('fa'):
            d['animal_fa'] += 1
    for key in ('seeds', 'shed'):
        a, b = Counter(A['state'].get(key) or {}), Counter(L['state'].get(key) or {})
        for k in set(a) | set(b):
            dd = abs(a.get(k, 0) - b.get(k, 0))
            if key == 'shed' and k == 'FERTILIZER':
                d['shed_fertilizer'] += dd
            else:
                d[key] += dd
    d['cash'] = A['cash_next_morning'] - L['cash_next_morning']
    return d


arms = sys.argv[1].split(',') if len(sys.argv) > 1 else sorted(p.name for p in (OUT / 'state11').iterdir() if p.is_dir() and p.name != 'LEADER')
L = {json.load(open(f))['episode']: json.load(open(f)) for f in glob.glob(str(OUT / 'state11/LEADER/*.json'))}
keys = ['tiles_kind', 'tiles_day', 'tiles_units', 'units_abs', 'tiles_fert', 'tiles_dry', 'animal_bank', 'animal_fa', 'seeds', 'shed',
        'shed_fertilizer', 'cash']
lines = [f'day-12 morning state distance to the leader ({len(L)} worlds), mean per world', '| arm | ' + ' | '.join(keys) + ' |',
         '|---|' + '---:|' * len(keys)]
for a in arms:
    A = {json.load(open(f))['episode']: json.load(open(f)) for f in glob.glob(str(OUT / f'state11/{a}/*.json'))}
    es = [e for e in A if e in L]
    if not es:
        continue
    tot = Counter()
    for e in es:
        tot.update(dist(A[e], L[e]))
    lines.append(f'| {a} | ' + ' | '.join((f'{tot[k] / len(es):+,.0f}' if k == 'cash' else f'{tot[k] / len(es):.1f}') for k in keys) + ' |')
print('\n'.join(lines))
(OUT / 'distance_report.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')

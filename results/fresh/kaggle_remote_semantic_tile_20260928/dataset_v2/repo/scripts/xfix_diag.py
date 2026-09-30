"""xfix: mechanism diagnosis of the parked fixes from stored full-game ledgers (no games). For arm A vs base B, per game
over the common worlds: own cash, rival cash, revenue delta by product, harvested units by product, plantings, effective
ops by kind (FERTILIZE / WATER / HARVEST / FEED / CARE / COLLECT / PLANT / PASS), fertilizer sold / held, wages, trades."""
import glob, json, sys
from collections import Counter


def load(d):
    return {json.load(open(f))['episode']: json.load(open(f)) for f in glob.glob(d + '/*.json')}


def tot(r, key):
    c = Counter()
    for d in r['days']:
        v = d.get(key)
        if isinstance(v, dict):
            c.update(v)
        elif isinstance(v, (int, float)):
            c['_'] += v
    return c


X = 'results/fresh/xfix_20260925/full'
BASES = {'T': 'results/fresh/xopen_20260925/g1/T'}
pairs = [p.split(':') for p in sys.argv[1].split(',')]
for a, b in pairs:
    A = load(X + '/' + a)
    B = load(BASES.get(b, X + '/' + b))
    es = [e for e in A if e in B]
    n = len(es)
    if not n:
        print(a, b, 'no data'); continue
    f = lambda R, key: sum((tot(R[e], key) for e in es), Counter())
    own = sum(A[e]['final'] - B[e]['final'] for e in es) / n
    riv = sum(A[e]['opp_final'] - B[e]['opp_final'] for e in es) / n
    out = [f'== {a} vs {b} (n={n}): own {own:+,.0f}, rival {riv:+,.0f}']
    for key, lab, thr in (('rev', 'revenue', 150), ('harv', 'harvested', 3), ('eff', 'ops', 3), ('plant', 'plantings', 1),
                          ('spend', 'trade spend', 100), ('sold', 'sold', 3)):
        ca, cb = f(A, key), f(B, key)
        items = sorted(((k, (ca.get(k, 0) - cb.get(k, 0)) / n) for k in set(ca) | set(cb)), key=lambda kv: -abs(kv[1]))
        items = [(k, v) for k, v in items if abs(v) >= thr][:9]
        if items:
            out.append(f'   {lab}: ' + ', '.join(f'{k} {v:+,.0f}' for k, v in items))
    pa = sum(sum(d['passes'] for d in A[e]['days']) for e in es) / n
    pb = sum(sum(d['passes'] for d in B[e]['days']) for e in es) / n
    wa = sum(sum(d.get('wages', 0) for d in A[e]['days']) for e in es) / n
    wb = sum(sum(d.get('wages', 0) for d in B[e]['days']) for e in es) / n
    fa = sum(sum((d.get('carried_mid') or {}).get('FERTILIZER', 0) + (d.get('shed_after') or {}).get('FERTILIZER', 0) for d in A[e]['days'][:29]) for e in es) / n / 29
    fb = sum(sum((d.get('carried_mid') or {}).get('FERTILIZER', 0) + (d.get('shed_after') or {}).get('FERTILIZER', 0) for d in B[e]['days'][:29]) for e in es) / n / 29
    out.append(f'   PASS {pa - pb:+.0f}; wages {wa - wb:+.0f}; fertilizer held at midnight (mean/day) {fa:.1f} vs {fb:.1f}')
    print('\n'.join(out))

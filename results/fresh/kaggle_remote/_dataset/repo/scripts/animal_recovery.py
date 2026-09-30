"""How much of the leader's animal-production lead over a base arm each arm recovers (season_animals.py outputs, same
worlds). usage: animal_recovery.py <base json> <base arm> <arm json:arm> ..."""
import json
import sys
from collections import Counter

PRICE = {'GOOSE': 48.0, 'COW': 113.0, 'SHEEP': 163.0}      # our average sale prices, 40 DSM worlds (K5b)


def load(path, arm):
    d = json.load(open(path))
    L, A = Counter(), Counter()
    for r in d.values():
        L.update(r['leader'])
        A.update(r[arm])
    n = len(d)
    return {k: v / n for k, v in L.items()}, {k: v / n for k, v in A.items()}, n


Lb, B, n = load(sys.argv[1], sys.argv[2])
rows = [('leader', Lb), (sys.argv[2], B)]
for spec in sys.argv[3:]:
    p, a = spec.rsplit(':', 1)
    _, A, _ = load(p, a)
    rows.append((a, A))
keys = [('made', 'units made'), ('bank_lost', 'bank wiped'), ('harvests', 'harvests')]
print(f'{n} worlds, per world')
for an in ('GOOSE', 'COW', 'SHEEP'):
    print(f'\n{an}')
    for name, C in rows:
        g = lambda k: C.get(f'{an}|{k}', 0)
        d = max(1e-9, g('days'))
        pd = max(1e-9, g('prod_days'))
        rec = ''
        if name not in ('leader', sys.argv[2]):
            gap = Lb.get(f'{an}|made', 0) - B.get(f'{an}|made', 0)
            rec = '  recovered %+.0f of %.0f units (%.0f%%)' % (g('made') - B.get(f'{an}|made', 0), gap, 100 * (g('made') - B.get(f'{an}|made', 0)) / gap if gap else 0)
        print('  %-10s made %6.1f | fed %3.0f%% cared %3.0f%% prod nights fed %3.0f%% | bank wiped %5.1f | harvests %5.1f (%.2f each)%s' % (
            name, g('made'), 100 * g('fed') / d, 100 * g('cared') / d, 100 * g('prod_days_fed') / pd, g('bank_lost'),
            g('harvests'), g('harvest_units') / max(1e-9, g('harvests')), rec))
print('\nALL ANIMALS, coins at our average prices (egg 48, milk 113, wool 163)')
val = lambda C: sum(C.get(f'{an}|made', 0) * PRICE[an] for an in PRICE)
gap = val(Lb) - val(B)
for name, C in rows:
    extra = '' if name in ('leader', sys.argv[2]) else '  recovered %+.0f of %.0f (%.0f%%)' % (val(C) - val(B), gap, 100 * (val(C) - val(B)) / gap)
    print('  %-10s %7.0f%s' % (name, val(C), extra))

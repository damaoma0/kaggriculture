"""Hour-0 vs hour-1 sales: per product, our units / avg price at hour 0, hour 1 and hours 2-23 in two arms' games
(season_timing.py outputs), and the rival's hour-0 / hour-1 prices in each. usage: h0_sale_compare.py <jsonA:armA> <jsonB:armB>"""
import json
import sys
from collections import Counter

PROD = ('WOOL', 'MILK', 'STRAWBERRY', 'EGG', 'CARROT', 'TOMATO', 'FERTILIZER', 'WHEAT')


def load(spec):
    p, arm = spec.rsplit(':', 1)
    d = json.load(open(p))
    C = Counter()
    for r in d.values():
        C.update(r[arm]['C'])
    return C, len(d), arm, {ep: r[arm]['money'] for ep, r in d.items()}


def block(C, side, p, hours):
    u = sum(v for k, v in C.items() if k.startswith(f'{side}|{p}|') and k.endswith('|n') and int(k.split('|')[3]) in hours)
    r = sum(v for k, v in C.items() if k.startswith(f'{side}|{p}|') and k.endswith('|$') and int(k.split('|')[3]) in hours)
    return u, r


(A, n, a, mA), (B, _, b, mB) = load(sys.argv[1]), load(sys.argv[2])
print(f'{n} worlds, per world: units @ avg price')
print('%-10s | %-38s | %-38s | rival h0 / h1 price' % ('', f'{a}: h0 / h1 / h2-23', f'{b}: h0 / h1 / h2-23'))
tot = Counter()
for p in PROD:
    cells = []
    for C, tag in ((A, a), (B, b)):
        parts = []
        for hs in ((0,), (1,), tuple(range(2, 24))):
            u, r = block(C, 'us', p, hs)
            parts.append('%5.1f@%5.1f' % (u / n, r / u if u else 0))
            tot[(tag, hs[0])] += r / n
        cells.append(' '.join(parts))
    rv = []
    for C in (A, B):
        u0, r0 = block(C, 'opp', p, (0,))
        u1, r1 = block(C, 'opp', p, (1,))
        rv.append('%.0f/%.0f' % (r0 / u0 if u0 else 0, r1 / u1 if u1 else 0))
    print('%-10s | %-38s | %-38s | %s' % (p, cells[0], cells[1], ' vs '.join(rv)))
own = sum(mA[e][0] - mB[e][0] for e in mA) / n
mar = sum((mA[e][0] - mA[e][1]) - (mB[e][0] - mB[e][1]) for e in mA) / n
print('\nrevenue by block (all products): ' + ', '.join('%s h%s %.0f' % (k[0], k[1], v) for k, v in sorted(tot.items())))
print(f'{a} - {b}: own {own:+.0f}, margin {mar:+.0f} (replay, step 718)')

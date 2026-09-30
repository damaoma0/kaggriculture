"""Own-cash gap vs the leader by CAUSE: each product's sales gap split into units made, deleted at midnight, left unsold
at the end, used (feed wheat / applied fertilizer), bought, and price; plus purchases and hires.
Units valued at the leader's average sale price; the price term is our units x (our price - leader price).
usage: season_gap_causes.py <season_gap json> <arm>"""
import json
import sys
from collections import Counter

d = json.load(open(sys.argv[1]))
arm = sys.argv[2]
n = len(d)
L, A = Counter(), Counter()
for r in d.values():
    L.update(r['leader'])
    A.update(r[arm])
f = lambda C, k: C.get(k, 0) / n
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')


def used(C, p):
    if p == 'WHEAT':
        return sum(v for k, v in C.items() if k.startswith('ok|FEED|')) / n
    if p == 'FERTILIZER':
        return sum(v for k, v in C.items() if k.startswith('ok|FERTILIZE|')) / n
    return 0.0


cause = Counter()
print(f'{n} worlds, per world; units valued at the leader price\n')
print('%-10s %8s | %7s %7s %7s %7s %7s | %7s | %8s' % ('product', 'sales gap', 'made', 'deleted', 'unsold', 'used', 'bought', 'price', 'check'))
for p in PROD:
    ns_l, ns_a = f(L, f'us|SELL|{p}|n'), f(A, f'us|SELL|{p}|n')
    pl = f(L, f'us|SELL|{p}|$') / max(1e-9, ns_l)
    pa = f(A, f'us|SELL|{p}|$') / max(1e-9, ns_a)
    gap = f(A, f'us|SELL|{p}|$') - f(L, f'us|SELL|{p}|$')
    parts = {
        'made': (f(A, f'got|{p}') - f(L, f'got|{p}')) * pl,
        'deleted': -(f(A, f'lost|{p}') - f(L, f'lost|{p}')) * pl,
        'unsold': -(f(A, f'end|{p}') - f(L, f'end|{p}')) * pl,
        'used': -(used(A, p) - used(L, p)) * pl,
        'bought': (f(A, f'us|BUY_PRODUCT|{p}|n') - f(L, f'us|BUY_PRODUCT|{p}|n')) * pl,
        'price': ns_a * (pa - pl),
    }
    for k, v in parts.items():
        cause[k] += v
    rest = gap - sum(parts.values())
    print('%-10s %+8.0f | %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f | %+7.0f | %+8.0f' % (
        p, gap, parts['made'], parts['deleted'], parts['unsold'], parts['used'], parts['bought'], parts['price'], rest))
spend = {
    'wheat / product purchases': -sum(f(A, f'us|BUY_PRODUCT|{p}|$') - f(L, f'us|BUY_PRODUCT|{p}|$') for p in PROD),
    'seeds': -sum(f(A, k) - f(L, k) for k in set(A) | set(L) if k.startswith('us|BUY_SEED|') and k.endswith('|$')),
    'animals': -sum(f(A, k) - f(L, k) for k in set(A) | set(L) if k.startswith('us|BUY_ANIMAL|') and k.endswith('|$')),
    'hires': -(f(A, 'us|HIRE|$') - f(L, 'us|HIRE|$')),
}
print('\nBY CAUSE (sales gap parts + spending)')
tot = 0
for k, v in sorted(list(cause.items()) + [('spend: ' + k, v) for k, v in spend.items()], key=lambda x: x[1]):
    tot += v
    print('  %-30s %+8.0f' % (k, v))
print('  %-30s %+8.0f   (money gap %+.0f; the rest is start-of-window stock and rounding)' % ('SUM', tot, f(A, 'money|us') - f(L, 'money|us')))

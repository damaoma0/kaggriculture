"""Margin gap vs the leader (our cash - rival cash, compared with the leader's game) by product and cause.
Our side: each product's sales gap split into units made / deleted at midnight / unsold at the end / used (feed wheat,
applied fertilizer) / bought / price, valued at the leader's average price; plus seeds, animals, hires. Rival side: its
sales and purchases by product (its orders are the recorded ones, so only prices, and occasionally cash-failed orders,
move). margin gap = our cash gap - rival cash gap.
usage: season_margin.py <season_gap json> <arm>"""
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
    pre = {'WHEAT': 'ok|FEED|', 'FERTILIZER': 'ok|FERTILIZE|'}.get(p)
    return sum(v for k, v in C.items() if k.startswith(pre)) / n if pre else 0.0


og, rg = f(A, 'money|us') - f(L, 'money|us'), f(A, 'money|opp') - f(L, 'money|opp')
print(f'{n} worlds, per world. own gap {og:+.0f}, rival gap {rg:+.0f}, MARGIN GAP {og - rg:+.0f}\n')
print('%-10s | %7s %7s %7s %7s %7s %7s | %8s | %8s %8s | %8s' % (
    'product', 'made', 'deleted', 'unsold', 'used', 'bought', 'price', 'our sales', 'rival $', 'rival px', 'MARGIN'))
tot = Counter()
for p in PROD:
    ns_l, ns_a = f(L, f'us|SELL|{p}|n'), f(A, f'us|SELL|{p}|n')
    pl = f(L, f'us|SELL|{p}|$') / max(1e-9, ns_l)
    pa = f(A, f'us|SELL|{p}|$') / max(1e-9, ns_a)
    parts = {
        'made': (f(A, f'got|{p}') - f(L, f'got|{p}')) * pl,
        'deleted': -(f(A, f'lost|{p}') - f(L, f'lost|{p}')) * pl,
        'unsold': -(f(A, f'end|{p}') - f(L, f'end|{p}')) * pl,
        'used': -(used(A, p) - used(L, p)) * pl,
        'bought': (f(A, f'us|BUY_PRODUCT|{p}|n') - f(L, f'us|BUY_PRODUCT|{p}|n')) * pl
                  - (f(A, f'us|BUY_PRODUCT|{p}|$') - f(L, f'us|BUY_PRODUCT|{p}|$')),   # units gained minus their cost
        'price': ns_a * (pa - pl),
    }
    ours = (f(A, f'us|SELL|{p}|$') - f(L, f'us|SELL|{p}|$')) - (f(A, f'us|BUY_PRODUCT|{p}|$') - f(L, f'us|BUY_PRODUCT|{p}|$'))
    riv = (f(A, f'opp|SELL|{p}|$') - f(L, f'opp|SELL|{p}|$')) - (f(A, f'opp|BUY_PRODUCT|{p}|$') - f(L, f'opp|BUY_PRODUCT|{p}|$'))
    rpl = f(L, f'opp|SELL|{p}|$') / max(1e-9, f(L, f'opp|SELL|{p}|n'))
    rpa = f(A, f'opp|SELL|{p}|$') / max(1e-9, f(A, f'opp|SELL|{p}|n'))
    for k, v in parts.items():
        tot[k] += v
    tot['ours'] += ours
    tot['rival'] += riv
    print('%-10s | %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f | %+8.0f | %+8.0f %8s | %+8.0f' % (
        p, parts['made'], parts['deleted'], parts['unsold'], parts['used'], parts['bought'], parts['price'], ours, riv,
        '%.0f->%.0f' % (rpl, rpa), ours - riv))
spend = -sum(f(A, k) - f(L, k) for k in set(A) | set(L)
             if (k.startswith('us|BUY_SEED|') or k.startswith('us|BUY_ANIMAL|')) and k.endswith('|$')) - (f(A, 'us|HIRE|$') - f(L, 'us|HIRE|$'))
print('%-10s | %55s | %+8.0f | %8s %8s | %+8.0f' % ('seeds/animals/hires', '', spend, '', '', spend))
print('%-10s | %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f | %+8.0f | %+8.0f %8s | %+8.0f' % (
    'TOTAL', tot['made'], tot['deleted'], tot['unsold'], tot['used'], tot['bought'], tot['price'], tot['ours'] + spend,
    tot['rival'], '', tot['ours'] + spend - tot['rival']))
print('\n(check: own flows %+.0f vs own gap %+.0f; rival flows %+.0f vs rival gap %+.0f; the rest is start stock / cash-failed orders)' % (
    tot['ours'] + spend, og, tot['rival'], rg))

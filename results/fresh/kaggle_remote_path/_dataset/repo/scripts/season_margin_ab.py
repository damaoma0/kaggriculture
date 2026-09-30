"""Arm A vs arm B, same worlds (season_gap.py outputs): margin difference by product and cause (units valued at B's
average price), plus spending and the rival side. usage: season_margin_ab.py <gapA.json:armA> <gapB.json:armB>"""
import json
import sys
from collections import Counter

PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')


def load(spec):
    p, arm = spec.rsplit(':', 1)
    d = json.load(open(p))
    C = Counter()
    for r in d.values():
        C.update(r[arm])
    return C, len(d), arm


(A, n, a), (B, _, b) = load(sys.argv[1]), load(sys.argv[2])
f = lambda C, k: C.get(k, 0) / n


def used(C, p):
    pre = {'WHEAT': 'ok|FEED|', 'FERTILIZER': 'ok|FERTILIZE|'}.get(p)
    return sum(v for k, v in C.items() if k.startswith(pre)) / n if pre else 0.0


og, rg = f(A, 'money|us') - f(B, 'money|us'), f(A, 'money|opp') - f(B, 'money|opp')
print(f'{n} worlds, per world, {a} - {b}: own {og:+.0f}, rival {rg:+.0f}, MARGIN {og - rg:+.0f}\n')
print('%-10s | %7s %7s %7s %7s %7s %7s | %8s | %8s %9s | %8s' % ('product', 'made', 'deleted', 'unsold', 'used', 'bought', 'price', 'our sales', 'rival $', 'rival px', 'MARGIN'))
tot = Counter()
for p in PROD:
    nb, na = f(B, f'us|SELL|{p}|n'), f(A, f'us|SELL|{p}|n')
    pb = f(B, f'us|SELL|{p}|$') / max(1e-9, nb)
    pa = f(A, f'us|SELL|{p}|$') / max(1e-9, na)
    parts = {'made': (f(A, f'got|{p}') - f(B, f'got|{p}')) * pb, 'deleted': -(f(A, f'lost|{p}') - f(B, f'lost|{p}')) * pb,
             'unsold': -(f(A, f'end|{p}') - f(B, f'end|{p}')) * pb, 'used': -(used(A, p) - used(B, p)) * pb,
             'bought': (f(A, f'us|BUY_PRODUCT|{p}|n') - f(B, f'us|BUY_PRODUCT|{p}|n')) * pb
                       - (f(A, f'us|BUY_PRODUCT|{p}|$') - f(B, f'us|BUY_PRODUCT|{p}|$')),
             'price': na * (pa - pb)}
    ours = (f(A, f'us|SELL|{p}|$') - f(B, f'us|SELL|{p}|$')) - (f(A, f'us|BUY_PRODUCT|{p}|$') - f(B, f'us|BUY_PRODUCT|{p}|$'))
    riv = (f(A, f'opp|SELL|{p}|$') - f(B, f'opp|SELL|{p}|$')) - (f(A, f'opp|BUY_PRODUCT|{p}|$') - f(B, f'opp|BUY_PRODUCT|{p}|$'))
    rb = f(B, f'opp|SELL|{p}|$') / max(1e-9, f(B, f'opp|SELL|{p}|n'))
    ra = f(A, f'opp|SELL|{p}|$') / max(1e-9, f(A, f'opp|SELL|{p}|n'))
    for k, v in parts.items():
        tot[k] += v
    tot['ours'] += ours
    tot['rival'] += riv
    print('%-10s | %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f | %+8.0f | %+8.0f %9s | %+8.0f' % (
        p, parts['made'], parts['deleted'], parts['unsold'], parts['used'], parts['bought'], parts['price'], ours, riv,
        '%.1f->%.1f' % (rb, ra), ours - riv))
sp = {'seeds': sum(f(A, k) - f(B, k) for k in set(A) | set(B) if k.startswith('us|BUY_SEED|') and k.endswith('|$')),
      'animals': sum(f(A, k) - f(B, k) for k in set(A) | set(B) if k.startswith('us|BUY_ANIMAL|') and k.endswith('|$')),
      'hires': f(A, 'us|HIRE|$') - f(B, 'us|HIRE|$')}
for k, v in sp.items():
    print('%-10s | spend %+.0f' % (k, v))
spend = -sum(sp.values())
print('%-10s | %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f %+7.0f | %+8.0f | %+8.0f %9s | %+8.0f' % (
    'TOTAL', tot['made'], tot['deleted'], tot['unsold'], tot['used'], tot['bought'], tot['price'], tot['ours'] + spend,
    tot['rival'], '', tot['ours'] + spend - tot['rival']))
print('\nunits: made / deleted / sold / avg price, %s -> %s' % (b, a))
for p in PROD:
    print('  %-10s made %6.1f -> %6.1f | deleted %5.1f -> %5.1f | sold %6.1f -> %6.1f | price %6.1f -> %6.1f' % (
        p, f(B, f'got|{p}'), f(A, f'got|{p}'), f(B, f'lost|{p}'), f(A, f'lost|{p}'), f(B, f'us|SELL|{p}|n'), f(A, f'us|SELL|{p}|n'),
        f(B, f'us|SELL|{p}|$') / max(1e-9, f(B, f'us|SELL|{p}|n')), f(A, f'us|SELL|{p}|$') / max(1e-9, f(A, f'us|SELL|{p}|n'))))

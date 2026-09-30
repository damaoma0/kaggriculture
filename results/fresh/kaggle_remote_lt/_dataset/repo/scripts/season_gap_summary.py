import json, sys
from collections import Counter
d = json.load(open(sys.argv[1])); arm = sys.argv[2]
n = len(d)
L, A = Counter(), Counter()
for ep, r in d.items():
    L.update(r['leader']); A.update(r[arm])
f = lambda C, k: C.get(k, 0) / n
print(f'{n} worlds, per world means (leader | {arm} | gap)')
print('final money us   %9.0f | %9.0f | %+8.0f' % (f(L, 'money|us'), f(A, 'money|us'), f(A, 'money|us') - f(L, 'money|us')))
print('final money opp  %9.0f | %9.0f | %+8.0f' % (f(L, 'money|opp'), f(A, 'money|opp'), f(A, 'money|opp') - f(L, 'money|opp')))
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
print('\nOWN CASH GAP BY FLOW (days 11-29)')
tot = 0
rows = []
for p in PROD:
    k = f'us|SELL|{p}|$'
    rows.append((f'sales {p}', f(A, k) - f(L, k), f'units {f(L, f"us|SELL|{p}|n"):.0f} -> {f(A, f"us|SELL|{p}|n"):.0f}, price {f(L,k)/max(1e-9,f(L,f"us|SELL|{p}|n")):.1f} -> {f(A,k)/max(1e-9,f(A,f"us|SELL|{p}|n")):.1f}'))
for p in PROD:
    k = f'us|BUY_PRODUCT|{p}|$'
    if f(L, k) or f(A, k):
        rows.append((f'buy {p}', -(f(A, k) - f(L, k)), f'units {f(L, f"us|BUY_PRODUCT|{p}|n"):.0f} -> {f(A, f"us|BUY_PRODUCT|{p}|n"):.0f}'))
seeds = [k.split('|')[2] for k in set(L) | set(A) if k.startswith('us|BUY_SEED|') and k.endswith('|$')]
rows.append(('seeds', -sum(f(A, f'us|BUY_SEED|{c}|$') - f(L, f'us|BUY_SEED|{c}|$') for c in seeds),
             ', '.join('%s %.0f->%.0f' % (c, f(L, f'us|BUY_SEED|{c}|n'), f(A, f'us|BUY_SEED|{c}|n')) for c in sorted(seeds))))
an = [k.split('|')[2] for k in set(L) | set(A) if k.startswith('us|BUY_ANIMAL|') and k.endswith('|$')]
rows.append(('animals bought', -sum(f(A, f'us|BUY_ANIMAL|{c}|$') - f(L, f'us|BUY_ANIMAL|{c}|$') for c in an),
             ', '.join('%s %.1f->%.1f' % (c, f(L, f'us|BUY_ANIMAL|{c}|n'), f(A, f'us|BUY_ANIMAL|{c}|n')) for c in sorted(an))))
rows.append(('hires', -(f(A, 'us|HIRE|$') - f(L, 'us|HIRE|$')), 'hand-days %.0f -> %.0f' % (f(L, 'us|HIRE|n'), f(A, 'us|HIRE|n'))))
rows.append(('land', -(f(A, 'us|LAND|$') - f(L, 'us|LAND|$')), ''))
for name, v, note in sorted(rows, key=lambda r: r[1]):
    tot += v
    print('  %-18s %+7.0f   %s' % (name, v, note))
print('  %-18s %+7.0f   (money gap %+.0f)' % ('SUM', tot, f(A, 'money|us') - f(L, 'money|us')))
print('\nPRODUCTION (units harvested / collected) and what happened to them')
for p in PROD:
    print('  %-10s got %6.0f -> %6.0f (%+5.0f) | deleted %5.1f -> %5.1f | end stock %5.1f -> %5.1f' % (
        p, f(L, f'got|{p}'), f(A, f'got|{p}'), f(A, f'got|{p}') - f(L, f'got|{p}'), f(L, f'lost|{p}'), f(A, f'lost|{p}'), f(L, f'end|{p}'), f(A, f'end|{p}')))
print('\nWORK (successful actions) and board (tile-days / 19 = mean count)')
labs = sorted({k.split('|', 1)[1] for k in set(L) | set(A) if k.startswith('ok|')})
for lab in labs:
    k = 'ok|' + lab
    if max(f(L, k), f(A, k)) >= 3:
        print('  %-28s %6.0f -> %6.0f (%+5.0f)' % (lab, f(L, k), f(A, k), f(A, k) - f(L, k)))
print('  harvest units per harvest:')
for c in ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY', 'MELON', 'COW', 'CHICKEN', 'GOOSE', 'SHEEP'):
    hl, ha = f(L, f'ok|HARVEST|{c}'), f(A, f'ok|HARVEST|{c}')
    if hl or ha:
        print('    %-11s %.2f (%.0f) -> %.2f (%.0f)' % (c, f(L, f'hv_units|{c}') / max(1e-9, hl), hl, f(A, f'hv_units|{c}') / max(1e-9, ha), ha))
for k in sorted(k for k in set(L) | set(A) if k.startswith('count|')):
    print('  board %-18s %6.1f -> %6.1f' % (k[6:], f(L, k) / 19, f(A, k) / 19))
print('\nRIVAL SALES (windfall)')
rt = 0
for p in PROD:
    k = f'opp|SELL|{p}|$'
    dv = f(A, k) - f(L, k); rt += dv
    if abs(dv) > 50:
        print('  %-10s %+7.0f (price %.1f -> %.1f)' % (p, dv, f(L, k) / max(1e-9, f(L, f'opp|SELL|{p}|n')), f(A, k) / max(1e-9, f(A, f'opp|SELL|{p}|n'))))
print('  total %+.0f' % rt)

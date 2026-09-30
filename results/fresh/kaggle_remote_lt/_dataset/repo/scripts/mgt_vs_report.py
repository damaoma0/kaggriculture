"""Head-to-head report: Mother-Goose's recorded moves (her own world) against a live tape-router build whose
library does not contain that world (scripts/mgt_loo.py <x> <rival> 40 mg_vs).

usage: mgt_vs_report.py <rival>
All numbers are from HER side; the reference columns are the same worlds against live V50 (native_raw arm).
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results' / 'fresh' / 'mg_tape' / 'loo'


def load(pattern):
    out = {}
    for p in LOO.glob(pattern):
        d = json.loads(p.read_text())
        if d.get('final') is not None:
            out[int(d['episode'])] = d
    return out


def ci(xs, n=4000, seed=11):
    rng = random.Random(seed)
    m = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return m[int(0.025 * n)], m[int(0.975 * n)]


def main():
    rival = sys.argv[1]
    a = load(f'mgtape_vs_{rival}-mg_vs-*.json')
    v50 = load('any-native_raw-*.json')
    ours_v50 = load(f'{rival}-loo-*.json')
    eps = sorted(a)
    n = len(eps)
    m = [a[e]['margin'] for e in eps]
    lo, hi = ci(m)
    print(f'Her recorded tape vs live {rival} (world excluded from its library): {n} worlds')
    print(f'  HER W-L {sum(x > 0 for x in m)}-{sum(x <= 0 for x in m)}, her mean margin {sum(m) / n:+,.0f} ({lo:+,.0f}..{hi:+,.0f}), median {sorted(m)[n // 2]:+,.0f}')
    print(f'  her cash {sum(a[e]["final"] for e in eps) / n:,.0f}   {rival} cash {sum(a[e]["rival_final"] for e in eps) / n:,.0f}')
    both = [e for e in eps if e in v50]
    if both:
        print(f'  same worlds vs live V50: her cash {sum(v50[e]["final"] for e in both) / len(both):,.0f}, margin {sum(v50[e]["margin"] for e in both) / len(both):+,.0f}, '
              f'W-L {sum(v50[e]["margin"] > 0 for e in both)}-{sum(v50[e]["margin"] <= 0 for e in both)}')
        print(f'  her cash against {rival} minus her cash against V50: {sum(a[e]["final"] - v50[e]["final"] for e in both) / len(both):+,.0f}')
    both = [e for e in eps if e in ours_v50]
    if both:
        print(f'  {rival} cash against her minus its cash against V50 (same worlds): '
              f'{sum(a[e]["rival_final"] - ours_v50[e]["final"] for e in both) / len(both):+,.0f}')
    prods = sorted({k for e in eps for k in list(a[e]['revenue']) + list(a[e]['rival_revenue'])})
    print('  revenue per game  her / ' + rival)
    for k in prods:
        h = sum(a[e]['revenue'].get(k, 0) for e in eps) / n
        r = sum(a[e]['rival_revenue'].get(k, 0) for e in eps) / n
        if max(h, r) >= 300:
            print(f'    {k:<11} {h:>8,.0f} / {r:>8,.0f}   {h - r:>+8,.0f}')
    print('  by Yarn Stores in the world (her margin):')
    for lab, f in (('0', lambda y: y == 0), ('1', lambda y: y == 1), ('2+', lambda y: y >= 2)):
        xs = [a[e]['margin'] for e in eps if f(sum(1 for s in a[e]['shops'][:8] if s == 'YARN_STORE'))]
        if xs:
            print(f'    yarn {lab:<2} n={len(xs):>2}  W-L {sum(x > 0 for x in xs)}-{sum(x <= 0 for x in xs)}  mean {sum(xs) / len(xs):+,.0f}')
    worst = sorted(eps, key=lambda e: a[e]['margin'])
    print('  our best worlds (her margin):', [(e, round(a[e]['margin'])) for e in worst[:5]])
    print('  our worst worlds (her margin):', [(e, round(a[e]['margin'])) for e in worst[-5:]])
    print('  dead commands in her tape:', sum(a[e].get('no_effect', 0) for e in eps) / n)


if __name__ == '__main__':
    main()

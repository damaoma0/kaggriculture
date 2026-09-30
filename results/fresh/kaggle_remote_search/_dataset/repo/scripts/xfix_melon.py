"""xfix: melon units harvested by day (10 / 11 / 12+), melon revenue, per arm (full games, stored ledgers)."""
import glob, json, sys
def load(d):
    return {json.load(open(f))['episode']: json.load(open(f)) for f in glob.glob(d + '/*.json')}
L = load('results/fresh/xopen_20260925/g1/LEADER')
T = load('results/fresh/xopen_20260925/g1/T')
arms = [('leader', L), ('T', T)] + [(a, load(f'results/fresh/xfix_20260925/full/{a}')) for a in sys.argv[1].split(',')]
for sel_name, sel in (('12 G1', lambda e: e in {112655730, 112661570, 112667461, 112673479, 112708229, 112714050, 112715010,
                                                  112721923, 112444381, 112445586, 112447950, 112449129}), ('52', lambda e: True)):
    print('==', sel_name)
    for nm, G in arms:
        es = [e for e in G if sel(e) and e in T]
        if not es:
            continue
        h = lambda r, a, b: sum(r['days'][d].get('harv', {}).get('MELON', 0) for d in range(a, b + 1))
        n = len(es)
        print(f"  {nm:7s} n={n:2d} melon units harvested d<=9 {sum(h(G[e], 0, 9) for e in es) / n:5.1f}  d10 {sum(h(G[e], 10, 10) for e in es) / n:5.1f}"
              f"  d11 {sum(h(G[e], 11, 11) for e in es) / n:5.1f}  d12+ {sum(h(G[e], 12, 29) for e in es) / n:5.1f}  total {sum(h(G[e], 0, 29) for e in es) / n:5.1f};"
              f"  melon revenue {sum(sum(d.get('rev', {}).get('MELON', 0) for d in G[e]['days']) for e in es) / n:7,.0f};"
              f"  WATER:MELON d6-9 {sum(sum(G[e]['days'][d].get('opk', {}).get('WATER:MELON', 0) for d in range(6, 10)) for e in es) / n:5.1f}")

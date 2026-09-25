"""Extra step-1 cuts (thread upkeep): realized coins lost on skip asset-days; animal skips = retirement vs intermittent."""
import gzip, json, glob, statistics as st
from collections import Counter, defaultdict
PROD = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
coins = defaultdict(lambda: [0, 0.0, 0.0, 0.0])      # grp -> [asset-days with skip, L0 coins, LF coins, module coins]
anim = Counter()
files = sorted(glob.glob('results/fresh/upkeep_20260925/skips/*.json.gz'))
G = 0
for f in files:
    r = json.load(gzip.open(f, 'rt'))
    G += 1
    fed = defaultdict(set)
    for a in r['assets']:
        if a['k'] in PROD and any(o[0] == 'FEED' for o in a['ops']):
            fed[(a['i'], a['k'], a['s'])].add(a['d'])
    for a in r['assets']:
        d = a['d']
        if not (12 <= d <= 28) or 'V0_1' not in a:
            continue
        ops = {o[0] for o in a['ops']}
        sk = [j for j in a['mj'] if not j[5] and j[0] != 'COLLECT_FERTILIZER' and j[2] > 0 and j[0] not in ops]
        if not sk:
            continue
        grp = a['k'] if a['k'] in PROD else 'crop:' + a['k']
        p = float(a['p'] or 0)
        c = coins[grp]
        c[0] += 1
        c[1] += (a['V0'] - a['hv'] - a['V0_1']) * p
        c[2] += (a['VF'] - a['hv'] - a['VF_1']) * p
        c[3] += sum(max(0.0, j[1]) for j in sk)
        if a['k'] in PROD and any(j[0] in ('FEED', 'CARE') for j in sk):
            key = (a['i'], a['k'], a['s'])
            later = [x for x in fed[key] if x > d]
            if not later:
                cls = 'never fed again (retired)'
            elif min(later) <= d + 2:
                cls = 'fed again within 2 days (intermittent)'
            else:
                cls = 'fed again later'
            anim[(a['k'], cls)] += 1
print(f'{G} games, days 12-28, asset-days with >= 1 skipped production-affecting job')
print('| asset | skip asset-days / game | realized L0 coins / game | realized LF coins / game | module coins / game |')
print('|---|---|---|---|---|')
tot = [0, 0.0, 0.0, 0.0]
for grp, c in sorted(coins.items(), key=lambda kv: -kv[1][2]):
    for i in range(4):
        tot[i] += c[i]
    print(f'| {grp} | {c[0] / G:.1f} | {c[1] / G:,.0f} | {c[2] / G:,.0f} | {c[3] / G:,.0f} |')
print(f'| all | {tot[0] / G:.1f} | {tot[1] / G:,.0f} | {tot[2] / G:,.0f} | {tot[3] / G:,.0f} |')
print()
print('Animal asset-days with a skipped FEED/CARE (per game):')
for sp in ('COW', 'SHEEP', 'GOOSE'):
    t = sum(v for (k, c), v in anim.items() if k == sp)
    print(f'  {sp}: {t / G:.1f}: ' + ', '.join(f'{c} {v / t:.0%}' for (k, c), v in sorted(anim.items()) if k == sp))

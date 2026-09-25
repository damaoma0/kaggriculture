"""Leader skip rate by the module's job value (coins net of inputs), per job class, days 12-28 (thread upkeep)."""
import gzip, json, glob
from collections import defaultdict
PROD = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}
EDGES = [0, 10, 20, 30, 50, 80, 120, 200, 400, 1e9]
tab = defaultdict(lambda: [[0, 0] for _ in EDGES[:-1]])
G = 0
for f in sorted(glob.glob('results/fresh/upkeep_20260925/skips/*.json.gz')):
    r = json.load(gzip.open(f, 'rt'))
    G += 1
    for a in r['assets']:
        if not (12 <= a['d'] <= 28):
            continue
        ops = {o[0] for o in a['ops']}
        grp = 'animal' if a['k'] in PROD else 'crop'
        for cmd, val, u, jk, dl, opt, held in a['mj']:
            if opt or cmd == 'COLLECT_FERTILIZER' or u <= 0:
                continue
            b = next(i for i in range(len(EDGES) - 1) if val < EDGES[i + 1])
            for key in ((grp, cmd), ('all', '*')):
                tab[key][b][0] += 1
                tab[key][b][1] += int(cmd not in ops)
print(f'{G} games; leader skip rate of production-affecting module jobs by module value (coins); n per game in brackets')
hdr = ' | '.join(f'{EDGES[i]:.0f}-{EDGES[i + 1]:.0f}' if EDGES[i + 1] < 1e8 else f'{EDGES[i]:.0f}+' for i in range(len(EDGES) - 1))
print('| class | ' + hdr + ' |')
print('|---|' + '---|' * (len(EDGES) - 1))
for key in sorted(tab, key=lambda k: (k[0] != 'all', k)):
    row = tab[key]
    if sum(c[0] for c in row) < 5 * G:
        continue
    print(f'| {key[0]}:{key[1]} | ' + ' | '.join((f'{c[1] / c[0]:.0%} ({c[0] / G:.1f})' if c[0] >= G / 2 else '-') for c in row) + ' |')

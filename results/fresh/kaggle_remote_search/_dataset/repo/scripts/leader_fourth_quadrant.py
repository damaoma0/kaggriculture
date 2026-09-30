"""Do the 3000+ leaders buy the FOURTH quadrant (SE, $4,000)? Per team, from day-start boards: the day each quadrant
first shows no locked tile; outcomes of games with and without SE. usage: leader_fourth_quadrant.py"""
import gzip, json, glob, collections, statistics as st
from pathlib import Path

NAMES = {'16915014': 'Boey', '16623559': 'DECEM', '16681125': 'MMPQ', '16730612': 'MG', '16770421': 'Vadim', '16732748': 'DSM'}


def lab(b):
    if isinstance(b, list) and b and len(b[0]) == 2:
        return b
    s = ''.join(b)
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def unlock_days(g):
    out = {}
    for d, day in enumerate(g['days']):
        L = lab(day['board'])
        for q, (xs, ys) in {'NE': (range(5, 10), range(0, 5)), 'SW': (range(0, 5), range(5, 10)), 'SE': (range(5, 10), range(5, 10))}.items():
            if q not in out and all(L[y * 10 + x] != ' L' for x in xs for y in ys):
                out[q] = d
    return out


rows = collections.defaultdict(list)
for f in glob.glob('data/leader_semantics/*/*.json.gz'):
    g = json.load(gzip.open(f, 'rt'))
    s = g['meta']['seat']; r = g['meta']['rewards']
    rows[Path(f).parent.name].append((unlock_days(g), r[s] - r[1 - s], r[s]))
tot = [0, 0]
for t, rs in sorted(rows.items(), key=lambda kv: NAMES[kv[0]]):
    se = [x for x in rs if 'SE' in x[0]]; no = [x for x in rs if 'SE' not in x[0]]
    tot[0] += len(se); tot[1] += len(rs)
    sed = [x[0]['SE'] for x in se]
    fmt = lambda xs: f"win {sum(1 for x in xs if x[1] > 0)}/{len(xs)} margin {st.median([x[1] for x in xs]):+.0f} cash {st.median([x[2] for x in xs]):.0f}" if xs else '-'
    print(f"{NAMES[t]:6s} SE bought in {len(se):3d}/{len(rs)} games" + (f" (day median {st.median(sed):.0f}, range {min(sed)}-{max(sed)})" if sed else '') +
          f" | with SE: {fmt(se)} | without: {fmt(no)}")
print('all teams:', tot[0], 'of', tot[1], 'games buy SE')

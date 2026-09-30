"""How often does a router switch abandon a live crop? Offline, from recorded panel results and tape boards (no games).

For each switch day d from tape A (the route followed) to tape B: tiles where A has strawberry / melon / tomato on
day d and still on day d+2 (a live crop with a future in A), but B has a different label on day d and on day d+2
(nobody in B tends it). Our real board is within 8 tiles of B and followed A, so A's board stands in for ours.
usage: crop_strand_at_switches.py <results_glob> [...]
"""
import glob, gzip, json, sys, collections
from pathlib import Path

CROPS = ('ST', 'ME', 'TO')
TAPES = {}
for f in glob.glob('data/mg_tapes/*/*.json.gz'):
    TAPES[int(Path(f).name.split('.')[0])] = f
_cache = {}


def lab(ep):
    if ep not in _cache:
        t = json.load(gzip.open(TAPES[ep], 'rt'))
        _cache[ep] = [[row[i:i + 2] for row in b for i in range(0, len(row), 2)] for b in t['boards']]
    return _cache[ep]


def main():
    rows = []
    for pat in sys.argv[1:]:
        for f in glob.glob(pat, recursive=True):
            r = json.loads(Path(f).read_text(encoding='utf-8'))
            sw = r.get('router', {}) and r.get('switches') or []
            prev = None
            for day, ep, *_ in sw:
                ep = int(ep)
                if prev is not None and ep != prev and ep in TAPES and prev in TAPES:
                    A, B = lab(prev), lab(ep)
                    d2 = min(29, day + 2)
                    lost = collections.Counter()
                    for j, x in enumerate(A[day]):
                        if x in CROPS and A[d2][j] == x and B[day][j] != x and B[d2][j] != x:
                            lost[x] += 1
                    rows.append(dict(ep=r['episode'], day=day, lost=dict(lost), n=sum(lost.values())))
                prev = ep
    n = len(rows)
    games = len({x['ep'] for x in rows})
    tot = collections.Counter()
    for x in rows:
        tot.update(x['lost'])
    by_day = collections.defaultdict(list)
    for x in rows:
        by_day[x['day']].append(x['n'])
    print(f'{n} switches in {games} games; switches stranding >=1 crop tile: {sum(1 for x in rows if x["n"])} '
          f'({sum(x["n"] for x in rows)} tiles: {dict(tot)})')
    for d in sorted(by_day):
        v = by_day[d]
        print(f'  day {d:2d}: {len(v):3d} switches, {sum(1 for a in v if a):3d} stranding, {sum(v):4d} tiles')
    return rows


if __name__ == '__main__':
    main()

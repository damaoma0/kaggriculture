"""Type-exact board comparison, the leader vs arms, each morning of days 12-29 (from a labor viewer json,
results/fresh/labor_viz/<ep>.json). A tile's type: empty / weed / the crop / COOP or PASTURE with its animal (or
empty). Same-type tiles count as exact whatever the planting day (user, 2026-09-27: type exact; same-type replant
timing is ours). Prints mismatched tiles per morning, the mismatch pairs (leader type -> ours) in tile-days, and each
mismatch run (tile, first / last morning, types).
usage: tile_type_diverge.py <labor_viz json> <arm>[,<arm>...]"""
import json
import sys
from collections import Counter


def ttype(t):
    if t is None:
        return '.'
    k = t.get('kind')
    if k == 'PLANT':
        return t.get('crop')
    if k == 'WEED':
        return 'weed'
    if k in ('COOP', 'PASTURE'):
        return k + ('+' + t['animal'] if t.get('animal') else '')
    if 'animal' in t:
        return 'PEN+' + t['animal']
    return str(k)


def mornings(frames, table):
    out = {}
    for f in frames:
        s = f['step']
        if s % 24 == 0 and 12 * 24 <= s <= 29 * 24:
            out[s // 24] = [ttype(table[i]) if i is not None and i >= 0 else '.' for i in f['board']]
    return out


def main():
    r = json.load(open(sys.argv[1], encoding='utf-8'))[0]
    table = r['tiles']
    lead = mornings(r['leader']['frames'], table)
    for arm in sys.argv[2].lower().split(','):
        a = r.get(arm)
        if not a or not a.get('frames'):
            print(arm, 'not in file')
            continue
        ours = mornings(a['frames'], table)
        pairs = Counter()
        per_day = []
        runs = {}
        for d in sorted(set(lead) & set(ours)):
            n = 0
            for i in range(100):
                x, y = lead[d][i], ours[d][i]
                if x == 'LOCKED' or x == y:
                    continue
                n += 1
                pairs[(x, y)] += 1
                runs.setdefault((i, x, y), []).append(d)
            per_day.append((d, n))
        print(f'== {arm}: mismatched tiles each morning:', ' '.join(f'd{d}:{n}' for d, n in per_day),
              f'| tile-days {sum(n for _, n in per_day)}')
        print('   pairs (leader -> ours, tile-days):')
        for (x, y), n in pairs.most_common(14):
            print(f'     {x:>16s} -> {y:<16s} {n}')
        print('   runs (tile: leader -> ours, mornings):')
        for (i, x, y), ds in sorted(runs.items(), key=lambda kv: kv[1][0]):
            if len(ds) >= 2:
                print(f'     ({i % 10},{i // 10}) {x} -> {y}: d{ds[0]}-d{ds[-1]} ({len(ds)})')


if __name__ == '__main__':
    main()

"""How much of a Mother-Goose tape is production PLAN and how much is EXECUTION? (offline, tape calendar)

Plan      = what happens to which tile on which day (PLANT crop, BUILD, WATER, FERTILIZE, FEED, CARE, HARVEST, DIG,
            COLLECT_FERTILIZER) and the market orders (HIRE, BUY_*, SELL with quantity and step).
Execution = which unit does it, in what order, the moves between tiles, and the shed logistics that the tasks imply
            (PICKUP seeds / wheat / fertilizer, PLACE / DROP of cargo).

Also: how tight her routing is. Each hand-day is cut into legs at its shed-logistic commands; within a leg the same
tiles are re-ordered optimally (exact bitmask DP up to 11 tiles, fixed start, fixed end when the leg ends at the shed).
Her moves minus the optimum = within-hand routing waste. Order constraints inside a leg (harvest wheat, then feed it)
are ignored, so the waste is over- not under-stated.

Output: results/fresh/mg_tape/plan_split.json
"""
import glob
import gzip
import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ns = {}
exec(compile((ROOT / 'scripts/fragments/tape_calendar.py').read_text(encoding='utf-8'), 'tape_calendar', 'exec'), ns)
simulate = ns['_tc_simulate']
MV = ns['_TC_MOVES']
LOGISTIC = {'PICKUP', 'PLACE', 'DROP'}


def best_path(start, tiles, end):
    """Shortest walk from start through all tiles (any order), finishing at end if given. Exact DP."""
    n = len(tiles)
    if n == 0:
        return (abs(start[0] - end[0]) + abs(start[1] - end[1])) if end else 0
    d = lambda a, b: abs(a[0] - b[0]) + abs(a[1] - b[1])
    if n > 11:                                   # rare: nearest neighbour (upper bound on the optimum)
        pos, left, tot = start, list(tiles), 0
        while left:
            k = min(left, key=lambda p: d(pos, p))
            tot += d(pos, k)
            pos = k
            left.remove(k)
        return tot + (d(pos, end) if end else 0)
    INF = 10 ** 9
    best = [[INF] * n for _ in range(1 << n)]
    for i in range(n):
        best[1 << i][i] = d(start, tiles[i])
    for mask in range(1 << n):
        row = best[mask]
        for i in range(n):
            c = row[i]
            if c >= INF:
                continue
            for j in range(n):
                if not mask & (1 << j):
                    m2 = mask | (1 << j)
                    v = c + d(tiles[i], tiles[j])
                    if v < best[m2][j]:
                        best[m2][j] = v
    full = (1 << n) - 1
    return min(best[full][i] + (d(tiles[i], end) if end else 0) for i in range(n))


def main():
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))
    ops = Counter()
    market = Counter()
    steps = Counter()
    tile_days = []
    hers = opt = 0
    legs = Counter()
    waste_by_hand = []
    for gi, p in enumerate(paths[::4]):
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        for a in acts:
            for o in a.get('market') or []:
                if o:
                    market[o[0]] += 1
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        td = set()
        route = gi % 5 == 0                      # routing tightness on every 5th sampled tape (30 tapes)
        for day in range(30):
            seq = {}
            for s in range(day * 24, min(719, day * 24 + 24)):
                for u, (x, y, c) in enumerate(sim.get(s, [])):
                    op = c[0] if c else 'PASS'
                    seq.setdefault(u, []).append((x, y, op))
                    steps['all'] += 1
                    if op == 'PASS':
                        steps['idle'] += 1
                    elif op in MV:
                        steps['travel'] += 1
                    elif op in LOGISTIC:
                        steps['logistics'] += 1
                        ops[op] += 1
                    else:
                        steps['tile work'] += 1
                        ops[op] += 1
                        td.add((day, x, y))
            if not route:
                continue
            for u, v in seq.items():
                start = (v[0][0], v[0][1])
                tiles, moved, h_hand, o_hand = [], 0, 0, 0
                for x, y, op in v:
                    if op in MV:
                        moved += 1
                    elif op in LOGISTIC:
                        uniq = list(dict.fromkeys(tiles))
                        best = best_path(start, uniq, (x, y))
                        h_hand += moved
                        o_hand += min(best, moved)
                        legs['n'] += 1
                        start, tiles, moved = (x, y), [], 0
                    elif op != 'PASS':
                        tiles.append((x, y))
                if tiles:
                    uniq = list(dict.fromkeys(tiles))
                    best = best_path(start, uniq, None)
                    # her moves after the last work command are not part of the route to it; count up to it
                    last = max(k for k, (_, _, op) in enumerate(v) if op not in MV and op != 'PASS' and op not in LOGISTIC)
                    k0 = max([k for k, (_, _, op) in enumerate(v) if op in LOGISTIC and k < last], default=-1)
                    m = sum(1 for k in range(k0 + 1, last) if v[k][2] in MV)
                    h_hand += m
                    o_hand += min(best, m)
                    legs['n'] += 1
                hers += h_hand
                opt += o_hand
                if u > 0 and h_hand:
                    waste_by_hand.append(h_hand - o_hand)
        tile_days.append(len(td))
    n = len(paths[::4])
    print(f'{n} tapes. Unit-steps per game {steps["all"] / n:,.0f}: ' + ', '.join(f'{k} {steps[k] / n:,.0f} ({steps[k] / steps["all"]:.0%})' for k in ('tile work', 'logistics', 'travel', 'idle')))
    print('tile and shed commands per game:', {k: round(v / n) for k, v in ops.most_common()})
    print('market orders per game:', {k: round(v / n, 1) for k, v in market.most_common()})
    print(f'distinct (day, tile) pairs worked per game: {st.mean(tile_days):,.0f}  (= {st.mean(tile_days) / 30:.0f} tiles a day)')
    print(f'routing tightness (30 tapes, {legs["n"]:,} legs): her moves on the way to work {hers / 30:,.0f} a game, optimal order of the same tiles within each leg '
          f'{opt / 30:,.0f} -> waste {(hers - opt) / 30:,.0f} steps a game ({(hers - opt) / max(1, hers):.1%}); per hand-day mean {st.mean(waste_by_hand):.2f}, '
          f'share of hand-days with zero waste {sum(1 for w in waste_by_hand if w == 0) / len(waste_by_hand):.0%}')
    (ROOT / 'results/fresh/mg_tape/plan_split.json').write_text(json.dumps(dict(steps=dict(steps), ops=dict(ops), market=dict(market), tile_days=st.mean(tile_days),
                                                                               hers=hers / 30, opt=opt / 30)), encoding='utf-8')


if __name__ == '__main__':
    main()

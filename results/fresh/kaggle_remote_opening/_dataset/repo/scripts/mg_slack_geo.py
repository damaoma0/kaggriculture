"""Where her crew's steps go geographically (offline, tape calendar): how far from the shed the work is, how many
hand-days reach the far corners, an upper bound on the travel a near-shed SE quadrant could save, what the last-hired
hand of the day actually does, and whether day 10 (melon day) has any idle steps in the morning.

Output: results/fresh/mg_tape/slack_geo.json
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
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
MOVES = {'NORTH', 'SOUTH', 'EAST', 'WEST'}
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]


def dist(x, y):
    return min(abs(x - sx) + abs(y - sy) for sx, sy in SHED)


def main():
    paths = sorted(glob.glob(str(ROOT / 'data/mg_tapes/*/*.json.gz')))[::4]          # 146 tapes
    ring = Counter()
    reach = Counter()
    save_bound = []
    last_ops = Counter()
    other_ops = Counter()
    d10 = Counter()
    d10_tot = Counter()
    for p in paths:
        t = json.load(gzip.open(p, 'rt', encoding='utf-8'))
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        game_save = 0
        for day in range(30):
            far = {}
            n_units = max((len(sim.get(s, [])) for s in range(day * 24, day * 24 + 24)), default=0)
            for s in range(day * 24, min(719, day * 24 + 24)):
                for u, (x, y, c) in enumerate(sim.get(s, [])):
                    op = c[0] if c else 'PASS'
                    d = dist(x, y)
                    far[u] = max(far.get(u, 0), d)
                    if op not in MOVES and op != 'PASS':
                        ring[d] += 1
                        (last_ops if (u == n_units - 1 and u > 0) else other_ops)[op] += 1
                    if day == 10:
                        d10_tot[s % 24] += 1
                        d10[s % 24] += op == 'PASS'
            for u, m in far.items():
                if u > 0:
                    reach[m] += 1
                    game_save += 2 * max(0, m - 4)
        save_bound.append(game_save)
    n = len(paths)
    tot = sum(ring.values())
    print(f'{n} tapes. Work commands by distance of the tile from the nearest shed tile:')
    print('   ' + '  '.join(f'd{d}: {ring[d] / tot:.0%}' for d in sorted(ring)), f'| mean distance {sum(d * v for d, v in ring.items()) / tot:.2f}')
    tr = sum(reach.values())
    print('hand-days by the farthest distance they reach: ' + '  '.join(f'd{d}: {reach[d] / tr:.0%}' for d in sorted(reach)))
    print(f'UPPER BOUND on travel saved per game if every hand-day that goes beyond distance 4 stopped at 4 instead: {st.mean(save_bound):,.0f} steps '
          f'(= {st.mean(save_bound) / 22:.0f} hand-days, {st.mean(save_bound) / 22 / 25:.1f} hands a day over 25 days)')
    lt, ot = sum(last_ops.values()), sum(other_ops.values())
    print('what the LAST-hired hand does (share of its work commands) vs all other units:')
    for op in sorted(set(last_ops) | set(other_ops), key=lambda o: -last_ops[o]):
        print(f'   {op:<20} {last_ops[op] / lt:6.1%}   {other_ops[op] / ot:6.1%}')
    print(f'   work commands per day: last hand {lt / n / 25:.1f}, other units {ot / n / 25 / 10:.1f} each (approx.)')
    print('day 10 (melon day), idle share by hour:', ' '.join(f'{h}:{d10[h] / max(1, d10_tot[h]):.0%}' for h in range(24)))
    (ROOT / 'results/fresh/mg_tape/slack_geo.json').write_text(json.dumps(dict(ring=dict(ring), reach=dict(reach), save_bound=st.mean(save_bound))), encoding='utf-8')


if __name__ == '__main__':
    main()

"""Tiles walked vs worked per hand-day, and tiles worked by two or more hands on the same day, the leader vs arms over
the 40-world panel (days 11-28). Per hand-day (hands; the farmer apart): steps walked, distinct tiles walked over without
working there, distinct tiles worked, work ops, ops per worked tile; the spread over hands (quartiles). Per farm-day:
distinct tiles worked, how many were worked by 1 / 2 / 3+ hands, what those shared tiles are and how their ops split.
usage: panel_tile_coverage.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST')


def dsh(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    hd = defaultdict(lambda: {'moves': 0, 'walked': set(), 'worked': Counter(), 'ops': 0})
    day_tiles = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))   # day -> tile -> unit -> [ops]
    kind_of = {}
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                r = hd[(dd, u)]
                if op in MOVES:
                    r['moves'] += 1
                    r['walked'].add(p)
                elif op in ('PASS', 'DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE')):
                    pass
                else:
                    r['worked'][p] += 1
                    r['ops'] += 1
                    tl = farm['tiles'][p[1]][p[0]]
                    kind_of[(dd, p)] = (tl.get('animal') or tl.get('crop') or tl.get('kind')) if isinstance(tl, dict) else 'EMPTY'
                    day_tiles[dd][p][u].append(op)
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    rows = []
    for (dd, u), r in hd.items():
        if not r['ops']:
            continue
        rows.append((u, r['moves'], len(r['walked'] - set(r['worked'])), len(r['worked']), r['ops']))
    c = Counter()
    for dd, tiles in day_tiles.items():
        c['farm_days'] += 1
        for p, byu in tiles.items():
            k = len(byu)
            c['tiles'] += 1
            c['by_%s' % min(k, 3)] += 1
            if k >= 2:
                kd = kind_of[(dd, p)]
                c['shared|' + kd] += 1
                split = ' / '.join(sorted('+'.join(sorted(set(v))) for v in byu.values()))
                c['split|' + ('pen: ' if kd in ('COW', 'SHEEP', 'GOOSE') else 'crop: ') + split] += 1
                c['shared_ops'] += sum(len(v) for v in byu.values())
                c['shared_visits'] += k
        for p, byu in tiles.items():                    # per hand-visit (one hand on one tile in a day): ops by tile kind
            kd = kind_of[(dd, p)]
            kd = kd if kd in ('COW', 'SHEEP', 'GOOSE', 'STRAWBERRY', 'WHEAT', 'TOMATO', 'CARROT', 'MELON') else 'other'
            for v in byu.values():
                c['hv|' + kd] += 1
                c['hvops|' + kd] += len(v)
                c['combo|' + kd + '|' + '+'.join(sorted(v))] += 1
    return arm, rows, dict(c)


def q(xs, f):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(f * len(xs)))] if xs else 0


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (__import__('os').environ.get('PANEL_GAMES') or (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text()).replace(',', ' ').split()
    R = defaultdict(list)
    C = defaultdict(Counter)
    with Pool(nw) as pool:
        for arm, rows, c in pool.imap_unordered(job, [(g, a) for a in arms for g in games]):
            R[arm] += rows
            C[arm].update(c)
    n = len(games)
    for a in arms:
        for who, X in (('hands', [r for r in R[a] if r[0] > 0]), ('farmer', [r for r in R[a] if r[0] == 0])):
            m = max(1, len(X))
            mv, wk, wt, op = ([r[i] for r in X] for i in (1, 2, 3, 4))
            print(f'{a} {who}: {len(X) / n:.0f} working unit-days a world | steps walked {sum(mv) / m:.1f} (quartiles {q(mv, .25)}/{q(mv, .5)}/{q(mv, .75)}), '
                  f'tiles walked over (not worked) {sum(wk) / m:.1f} | tiles worked {sum(wt) / m:.1f} (quartiles {q(wt, .25)}/{q(wt, .5)}/{q(wt, .75)}), '
                  f'ops {sum(op) / m:.1f}, ops per worked tile {sum(op) / max(1, sum(wt)):.2f}, steps per worked tile {sum(mv) / max(1, sum(wt)):.2f}')
        c = C[a]
        fd = max(1, c['farm_days'])
        print(f'{a} farm-day: {c["tiles"] / fd:.1f} distinct tiles worked; by 1 hand {c["by_1"] / fd:.1f}, by 2 {c["by_2"] / fd:.1f}, by 3+ {c["by_3"] / fd:.1f} '
              f'(shared tiles take {c["shared_visits"] / fd:.1f} visits, {c["shared_ops"] / fd:.1f} ops a day)')
        print('   shared tiles by kind (a day): ' + ', '.join(f'{k[7:]} {v / fd:.2f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('shared|')))
        kinds = [k[3:] for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('hv|')]
        print('   hand-visits a day / ops per hand-visit: ' + ', '.join(f'{k} {c["hv|" + k] / fd:.1f} / {c["hvops|" + k] / max(1, c["hv|" + k]):.2f}' for k in kinds))
        for k in kinds[:7]:
            print(f'      {k:10s} top combos (a day): ' + ', '.join(f'{x.split("|")[2]} {v / fd:.1f}' for x, v in sorted(c.items(), key=lambda kv: -kv[1])
                                                               if x.startswith('combo|' + k + '|'))[:260])
        print('   most common splits (a day): ' + '; '.join(f'{k[6:]} {v / fd:.2f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('split|'))[:900])
        print()

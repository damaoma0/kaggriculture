"""DSM's early-morning trips per day from a recorded game (the leader's tape, or an arm's stream for comparison).
A trip: a unit that starts its day on a shed tile (farmer at hour 0, a hand at its first acting hour) and, before any
PICKUP, does ops on one or more tiles and is back on a shed tile with a PLACE / DROP of harvested goods by hour
--by (default 8). Recorded per trip: unit, first acting hour, start tile, the tiles visited with their ops in order
(tile content: animal / crop and yield before the op), the drop hour / tile / goods, and what the unit does right after
(PICKUP item and hour, or leaves). Units whose first action is a PICKUP are counted as "pickup first".
usage: dsm_dawn_shape.py <team:ep> [--arm ARM] [--by 8] [--json out.json] [--days 11-29]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
PRODS = ('WOOL', 'MILK', 'EGG', 'STRAWBERRY', 'TOMATO', 'CARROT', 'WHEAT', 'MELON')


def trace(tape, stream):
    """per day: per unit, the list of (hour, pos before, action, inventory after, tile content before) for hours 0..23."""
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    days = defaultdict(lambda: defaultdict(list))
    while w.t < 719:
        t = w.t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        rec = t >= 264
        if rec:
            f = w.farms[seat]
            pos = [tuple(f['farmer'])] + [tuple(p) for p in f['hands']]
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            tl = [f['tiles'][p[1]][p[0]] for p in pos]
            tl = [dict(animal=x.get('animal'), crop=x.get('crop'), y=int(x.get('yield_units', 0) or 0)) if isinstance(x, dict) else None for x in tl]
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
        if not rec:
            continue
        inv = w.private(seat)['inventories']
        for i, p in enumerate(pos):
            a = acts[i] if i < len(acts) and isinstance(acts[i], list) and acts[i] else ['PASS']
            days[t // 24][i].append((t % 24, p, a, {k: int(v) for k, v in (inv[i] if i < len(inv) else {}).items() if v}, tl[i]))
    return days


def trips_of(days, by):
    out = {}
    for d in sorted(days):
        rows = []
        pick_first = 0
        for u, seq in sorted(days[d].items()):
            if not seq:
                continue
            h_a = seq[0][0]
            # first acting hour: the farmer acts from hour 0, a hand from the first hour it is listed
            start = seq[0][1]
            if start not in SHED:
                continue
            k = 0
            while k < len(seq) and seq[k][2][0] == 'PASS':
                k += 1
            if k >= len(seq):
                continue
            if seq[k][2][0] == 'PICKUP':
                pick_first += 1
                continue
            tiles, drop = [], None
            for j in range(k, len(seq)):
                h, p, a, inv, tl = seq[j]
                op = a[0]
                if h > by:
                    break
                if op == 'PICKUP':
                    break
                if op in ('PLACE', 'DROP') and p in SHED:
                    goods = {}
                    prev = seq[j - 1][3] if j > 0 else {}
                    for kk in PRODS:
                        n = prev.get(kk, 0) - inv.get(kk, 0)
                        if n > 0:
                            goods[kk] = n
                    if goods:
                        drop = (h, list(p), goods, j)
                        break
                    continue
                if op in ('NORTH', 'SOUTH', 'EAST', 'WEST', 'PASS'):
                    continue
                if tiles and tiles[-1][0] == list(p):
                    tiles[-1][1].append(op)
                else:
                    what = (tl or {}).get('animal') or (tl or {}).get('crop')
                    tiles.append([list(p), [op], what, (tl or {}).get('y'), h])
            if drop is None or not any('HARVEST' in x[1] for x in tiles):
                continue
            after = None
            j = drop[3] + 1
            if j < len(seq):
                h, p, a, inv, tl = seq[j]
                after = [h, a[0], a[1] if len(a) > 1 else None]
            rows.append({'u': u, 'act_h': h_a, 'leave': seq[k][0], 'start': list(start), 'tiles': tiles, 'drop_h': drop[0],
                         'drop_tile': drop[1], 'goods': drop[2], 'after': after})
        out[d] = {'trips': rows, 'pickup_first': pick_first, 'units': len(days[d])}
    return out


def show(name, T, lo, hi):
    print(f'=== {name}: early trips (start on a shed tile, ops before any PICKUP, back with goods by the cut-off)')
    tot = Counter()
    for d in range(lo, hi + 1):
        r = T.get(d)
        if not r:
            continue
        tr = r['trips']
        tot['trips'] += len(tr)
        tot['tiles'] += sum(len(x['tiles']) for x in tr)
        for x in tr:
            for k, v in x['goods'].items():
                tot[k] += v
        desc = []
        for x in tr:
            tl = '+'.join('%d%d:%s%s(%s)' % (t[0][0], t[0][1], (t[2] or '?')[:2], t[3], '/'.join(o[:4] for o in t[1])) for t in x['tiles'])
            aft = ('%s@h%d' % (x['after'][2] or x['after'][1], x['after'][0])) if x['after'] else '-'
            desc.append('u%d h%d-%d %s -> %d%d %s | %s' % (x['u'], x['leave'], x['drop_h'], tl, x['drop_tile'][0], x['drop_tile'][1],
                                                        ','.join('%s%d' % (k[:1], v) for k, v in x['goods'].items()), aft))
        print(f'd{d}: {len(tr)} hands ({r["pickup_first"]} pickup-first of {r["units"]} units)')
        for s in desc:
            print('     ' + s)
    print(f'  total: {tot["trips"]} trips, {tot["tiles"]} tiles, goods ' + ', '.join(f'{k} {v}' for k, v in tot.items() if k not in ('trips', 'tiles')))


if __name__ == '__main__':
    g = sys.argv[1]
    by = int(sys.argv[sys.argv.index('--by') + 1]) if '--by' in sys.argv else 8
    lo, hi = (11, 29)
    if '--days' in sys.argv:
        lo, hi = (int(x) for x in sys.argv[sys.argv.index('--days') + 1].split('-'))
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    T = trips_of(trace(tape, None), by)
    show('DSM', T, lo, hi)
    out = {'game': g, 'by': by, 'leader': T}
    if '--arm' in sys.argv:
        for arm in sys.argv[sys.argv.index('--arm') + 1].split(','):
            s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
            TA = trips_of(trace(tape, s['actions']), by)
            show(arm, TA, lo, hi)
            out[arm] = TA
    if '--json' in sys.argv:
        json.dump(out, open(sys.argv[sys.argv.index('--json') + 1], 'w'), default=list)

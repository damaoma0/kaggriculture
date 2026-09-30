"""One world, the leader's game vs an arm's game: every unit of the chosen products from harvest to the shed.
Each hand's inventory is a FIFO of (product, harvest step, tile); a unit leaves it by a daytime DROP / PLACE on a shed
tile (sellable at that step's market: unit actions come before the market) or by the midnight dump (sellable from the
next hour 0; overflow deleted). Logs every delivery event (unit, step, units by product, where they were harvested)
and every unit's path, plus the market sales of both games, so the report can say which units arrive late and how
the leader's arrive early.
usage: case_delivery.py <team:ep> <arm> <out.json> [--prods STRAWBERRY,WOOL,MILK]"""
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODS = tuple(sys.argv[sys.argv.index('--prods') + 1].split(',')) if '--prods' in sys.argv else ('STRAWBERRY', 'WOOL', 'MILK')
ACCESS = {tuple(p) for p in E._shed_access_tiles(10)}
R = {'w': None, 'seat': 0, 't': 0, 'L': None}
_commit, _drop = E._commit_unit, E._drop_inventories_to_shed


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and R['t'] >= 264 and item in PRODS and op == 'SELL':
        R['L']['sales'].append([R['t'], 'us' if farm is w.farms[R['seat']] else 'opp', item, float(price)])
    return r


def drop(private, cap):
    w = R['w']
    if w is not None and R['t'] >= 264 and private is w.private(R['seat']):
        L = R['L']
        before = dict(private['shed'])
        _drop(private, cap)
        for i, q in L['fifo'].items():
            for u in q:
                if u[0] in PRODS:
                    L['units'].append({'p': u[0], 'h': u[1], 'tile': u[2], 'unit': i, 'd': R['t'] + 1, 'how': 'midnight'})
            q.clear()
        for p in PRODS:
            got = private['shed'].get(p, 0) - before.get(p, 0)
            L['dump'].append([R['t'], p, got])
        return
    return _drop(private, cap)


E._commit_unit, E._drop_inventories_to_shed = commit, drop


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    L = {'units': [], 'events': [], 'sales': [], 'dump': [], 'fifo': {}, 'pos': {}}
    R.update(w=w, seat=seat, L=L)
    while w.t < 719:
        t = w.t
        R['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        track = t >= 264
        if track:
            f, pv = w.farms[seat], w.private(seat)
            pos = [tuple(f['farmer'])] + [tuple(p) for p in f['hands']]
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            inv0 = [dict(pv['inventories'][i]) if i < len(pv['inventories']) else {} for i in range(len(pos))]
            L['pos'][t] = [list(p) for p in pos]
            if t == 264:
                for i, inv in enumerate(inv0):
                    for k, v in inv.items():
                        if k in PRODS:
                            L['fifo'].setdefault(i, deque()).extend([(k, 264, None)] * v)
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
        if not track or t % 24 == 23 and False:
            continue
        pv = w.private(seat)
        for i, p in enumerate(pos):
            a = acts[i] if i < len(acts) else None
            op = a[0] if isinstance(a, list) and a else 'PASS'
            inv1 = pv['inventories'][i] if i < len(pv['inventories']) else {}
            q = L['fifo'].setdefault(i, deque())
            for k in PRODS:
                d = int(inv1.get(k, 0) or 0) - int(inv0[i].get(k, 0) or 0)
                if d > 0:                                        # harvested (or picked up)
                    q.extend([(k, t, list(p))] * d)
                elif d < 0:                                      # left the hand
                    n = -d
                    kept = deque()
                    moved = []
                    while q and n:
                        u = q.popleft()
                        if u[0] == k:
                            moved.append(u)
                            n -= 1
                        else:
                            kept.append(u)
                    kept.extend(q)
                    q.clear()
                    q.extend(kept)
                    how = 'day' if tuple(p) in ACCESS else 'elsewhere'
                    for u in moved:
                        L['units'].append({'p': k, 'h': u[1], 'tile': u[2], 'unit': i, 'd': t, 'how': how, 'op': op})
                    L['events'].append({'t': t, 'unit': i, 'p': k, 'n': len(moved), 'op': op, 'at': list(p),
                                        'tiles': [u[2] for u in moved], 'hts': [u[1] for u in moved]})
    L.pop('fifo')
    R['w'] = None
    return L


if __name__ == '__main__':
    g, arm, out = sys.argv[1], sys.argv[2], sys.argv[3]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    res = {'game': g, 'arm': arm, 'prods': PRODS, 'leader': run(tape, None), arm: run(tape, s['actions'])}
    json.dump(res, open(out, 'w'), default=list)
    print('written', out)

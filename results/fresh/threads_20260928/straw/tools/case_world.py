"""One-world case log, the leader's recorded game vs an arm's game (days 11-29), for chosen products: every sale of
both players with the market stock it sold into, the market stock at the start of every step, units produced (tile
yield growth + harvests), harvested, delivered to the shed (by step; the midnight dump flagged), deleted at midnight,
held on tiles / in hands / in the shed at every step, and successful upkeep ops per day (FEED / CARE / HARVEST /
WATER / FERTILIZE by animal or crop). Writes one JSON with both games.
usage: case_world.py <team:ep> <arm> <out.json> [--prods STRAWBERRY,WOOL,MILK]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r'C:/Users/xyygl/Documents/kaggriculture')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODS = tuple(sys.argv[sys.argv.index('--prods') + 1].split(',')) if '--prods' in sys.argv else ('STRAWBERRY', 'WOOL', 'MILK')
SRC = {'STRAWBERRY': 'STRAWBERRY', 'WOOL': 'SHEEP', 'MILK': 'COW', 'EGG': 'GOOSE', 'TOMATO': 'TOMATO', 'CARROT': 'CARROT',
       'WHEAT': 'WHEAT', 'MELON': 'MELON'}
OPS = ('HARVEST', 'FEED', 'CARE', 'WATER', 'FERTILIZE', 'PLANT', 'COLLECT_FERTILIZER')
REC = {'w': None, 'seat': 0, 't': 0, 'L': None}
_commit, _ua, _drop = E._commit_unit, E._apply_unit_action, E._drop_inventories_to_shed


def commit(op, item, price, farm, private, market, shed_capacity=100):
    inv = market['inventory'].get(item)
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = REC['w']
    if r and w is not None and REC['t'] >= 264 and item in PRODS and op in ('SELL', 'BUY_PRODUCT'):
        side = 'us' if farm is w.farms[REC['seat']] else 'opp'
        REC['L']['sales'].append([REC['t'], side, op, item, float(price), inv])
    return r


def ua(farm, private, idx, action, *a, **k):
    w = REC['w']
    if w is None or REC['t'] < 264 or farm is not w.farms[REC['seat']] or not (isinstance(action, list) and action and action[0] in OPS):
        return _ua(farm, private, idx, action, *a, **k)
    pos = E._farmer_position(farm, idx)
    if pos is None:
        return _ua(farm, private, idx, action, *a, **k)
    t0 = farm['tiles'][pos[1]][pos[0]]
    lab = (t0.get('crop') or t0.get('animal') or t0.get('kind')) if isinstance(t0, dict) else 'EMPTY'
    tb = json.dumps(t0, sort_keys=True, default=str)
    ib = dict(E._farmer_inventory(private, idx))
    r = _ua(farm, private, idx, action, *a, **k)
    t1 = farm['tiles'][pos[1]][pos[0]]
    ia = E._farmer_inventory(private, idx)
    if json.dumps(t1, sort_keys=True, default=str) != tb or ia != ib:
        L = REC['L']
        d = REC['t'] // 24
        L['ops'][d][f'{action[0]}|{lab}'] += 1
        if action[0] == 'HARVEST':
            for kk, v in ia.items():
                if kk in PRODS and v - ib.get(kk, 0) > 0:
                    L['harv'].append([REC['t'], idx, list(pos), kk, v - ib.get(kk, 0)])
    return r


def drop(private, cap):
    w = REC['w']
    if w is not None and REC['t'] >= 264 and private is w.private(REC['seat']):
        car = Counter()
        for inv in private['inventories']:
            for kk, v in inv.items():
                if v > 0:
                    car[kk] += v
        before = dict(private['shed'])
        _drop(private, cap)
        for kk, v in car.items():
            lost = v - (private['shed'].get(kk, 0) - before.get(kk, 0))
            if kk in PRODS and lost > 0:
                REC['L']['lost'][REC['t'] // 24][kk] += lost
        return
    return _drop(private, cap)


E._commit_unit, E._apply_unit_action, E._drop_inventories_to_shed = commit, ua, drop


def held(w, seat):
    f, pv = w.farms[seat], w.private(seat)
    tiles, herd = Counter(), Counter()
    for row in f['tiles']:
        for x in row:
            if not isinstance(x, dict):
                continue
            src = x.get('animal') or x.get('crop')
            for p in PRODS:
                if src == SRC.get(p):
                    tiles[p] += int(x.get('yield_units', 0) or 0)
                    herd[p] += 1
    carried = Counter()
    for inv in pv['inventories']:
        for kk, v in inv.items():
            if kk in PRODS:
                carried[kk] += v
    return ({p: tiles[p] for p in PRODS}, {p: carried[p] for p in PRODS},
            {p: int(pv['shed'].get(p, 0) or 0) for p in PRODS}, {p: herd[p] for p in PRODS})


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    L = {'sales': [], 'harv': [], 'ops': defaultdict(Counter), 'lost': defaultdict(Counter), 'stock': {p: {} for p in PRODS},
         'tiles': {p: {} for p in PRODS}, 'carried': {p: {} for p in PRODS}, 'shed': {p: {} for p in PRODS},
         'herd': {p: {} for p in PRODS}, 'arrive': {p: {} for p in PRODS}}
    REC.update(w=w, seat=seat, L=L)
    while w.t < 719:
        t = w.t
        REC['t'] = t
        if t >= 264:
            ti, ca, sh, hd = held(w, seat)
            for p in PRODS:
                L['stock'][p][t] = w.market['inventory'][p]
                L['tiles'][p][t], L['carried'][p][t], L['shed'][p][t] = ti[p], ca[p], sh[p]
                if t % 24 == 0:
                    L['herd'][p][t // 24] = hd[p]
            n_ev = len(L['sales'])
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
        if t >= 264:
            sh1 = w.private(seat)['shed']
            for p in PRODS:
                ev = [e for e in L['sales'][n_ev:] if e[1] == 'us' and e[3] == p]
                sold = sum(1 for e in ev if e[2] == 'SELL')
                bought = sum(1 for e in ev if e[2] == 'BUY_PRODUCT')
                arr = int(sh1.get(p, 0) or 0) - L['shed'][p][t] + sold - bought
                if arr:
                    L['arrive'][p][t] = arr
    ti, ca, sh, hd = held(w, seat)
    for p in PRODS:
        L['tiles'][p][719], L['carried'][p][719], L['shed'][p][719] = ti[p], ca[p], sh[p]
    L['money'] = {'us': w.farms[seat]['money'], 'opp': w.farms[1 - seat]['money']}
    L['params'] = w.market.get('params')
    L['ops'] = {d: dict(c) for d, c in L['ops'].items()}
    L['lost'] = {d: dict(c) for d, c in L['lost'].items()}
    REC['w'] = None
    return L


if __name__ == '__main__':
    g, arm, out = sys.argv[1], sys.argv[2], sys.argv[3]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    res = {'game': g, 'arm': arm, 'prods': PRODS, 'leader': run(tape, None), arm: run(tape, s['actions'])}
    json.dump(res, open(out, 'w'), default=lambda o: o if not isinstance(o, dict) else dict(o))
    print('written', out)

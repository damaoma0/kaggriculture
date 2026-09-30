"""WHEAT and EGG unit flows, the leader's recorded game vs an arm's season stream, one world, days 11-29 (thread KWE).

Hooks on the real engine (scripts/upkeep_engine.py; the pre-state of every unit action is copied with json before the
action, since WATER / CARE / FEED mutate the tile in place):
  wheat  planted, waterings (in the growth window ages 2-4 = +yield, or survival-only), fertilized, harvests (units,
         age), decay losses (units lost after age 4), plant deaths (weed), FEED (wheat consumed, by animal), bought,
         sold (by hour), midnight deletions, held (tiles / hands / shed) at hour 0
  eggs   per goose-day at the day-end refresh: fed, cared, bank before, eggs added, eggs swallowed by the held cap
         (max_held 4), bank wiped by an unfed production, care missed on a fed day (no +1 banked); harvests (units),
         midnight deletions, sold (by hour), held
  labor  every unit-step classified: a successful op by (op, target), a MOVE charged to that unit's next op of the
         day, shed work (PICKUP / DROP / PLACE*), failed ops, idle (PASS / no action)
usage: wheategg_diag.py <team:ep> <arm> <out.json>"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
T0 = 264
OPS = ('HARVEST', 'FEED', 'CARE', 'WATER', 'FERTILIZE', 'PLANT', 'COLLECT_FERTILIZER', 'DIG', 'BUILD_COOP', 'BUILD_PASTURE')
MOVES = set(E.FARMER_MOVES)
R = {'w': None, 'seat': 0, 't': 0, 'L': None, 'steps': None}
_commit, _ua, _drop, _ra, _decay, _rp = (E._commit_unit, E._apply_unit_action, E._drop_inventories_to_shed,
                                          E._daily_refresh_animals, E._decay_plants, E._daily_refresh_plants)


def ours(farm):
    w = R['w']
    return w is not None and R['t'] >= T0 and farm is w.farms[R['seat']]


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and R['t'] >= T0 and item in ('WHEAT', 'EGG') and op in ('SELL', 'BUY_PRODUCT'):
        side = 'us' if farm is w.farms[R['seat']] else 'opp'
        R['L']['sales'].append([R['t'], side, op, item, float(price)])
    return r


def lab_of(t0):
    return (t0.get('crop') or t0.get('animal') or t0.get('kind')) if isinstance(t0, dict) else 'EMPTY'


def ua(farm, private, idx, action, *a, **k):
    if not ours(farm):
        return _ua(farm, private, idx, action, *a, **k)
    op = action[0] if isinstance(action, list) and action else 'PASS'
    pos = E._farmer_position(farm, idx)
    t0 = farm['tiles'][pos[1]][pos[0]] if pos is not None else None
    tb = json.dumps(t0, sort_keys=True, default=str)
    pre = json.loads(tb)
    ib = dict(E._farmer_inventory(private, idx))
    sb = dict(private['seeds'])
    shb = dict(private['shed'])
    r = _ua(farm, private, idx, action, *a, **k)
    t1 = farm['tiles'][pos[1]][pos[0]] if pos is not None else None
    ia = dict(E._farmer_inventory(private, idx))
    fp1 = E._farmer_position(farm, idx)
    ok = (json.dumps(t1, sort_keys=True, default=str) != tb or ia != ib or private['seeds'] != sb
          or dict(private['shed']) != shb or (op in MOVES and fp1 != pos))
    lab = lab_of(pre)
    if op == 'PLANT' and ok:
        lab = action[1] if len(action) > 1 else lab
    L = R['L']
    d = R['t'] // 24
    R['steps'].append([R['t'], idx, op, lab, bool(ok)])
    if lab == 'GOOSE' and op in OPS and pos is not None:
        L['goose_steps'].append([R['t'], idx, op, bool(ok), pos[1] * 10 + pos[0]])
    if ok and op in OPS:
        L['ops'][d][f'{op}|{lab}'] += 1
        if op == 'WATER' and lab == 'WHEAT':
            age = d - pre['planted_day']
            gain = (t1.get('yield_units', 0) if isinstance(t1, dict) else 0) - pre.get('yield_units', 0)
            L['wheat'][d]['water_grow' if gain > 0 else 'water_surv'] += 1
            L['wheat'][d]['water_gain'] += gain
            L['wheat_water_age'][age] += 1
        if op == 'FERTILIZE' and lab == 'WHEAT':
            L['wheat'][d]['fert'] += 1
        if op == 'PLANT' and lab == 'WHEAT':
            L['wheat'][d]['planted'] += 1
        if op == 'HARVEST':
            for kk, v in ia.items():
                g = v - ib.get(kk, 0)
                if g > 0 and kk == 'WHEAT':
                    L['wheat'][d]['harv_n'] += 1
                    L['wheat'][d]['harv_u'] += g
                    L['wheat_harv_age'][f'{d - pre["planted_day"]}|{g}'] += 1
                if g > 0 and kk == 'EGG':
                    L['egg'][d]['harv_n'] += 1
                    L['egg'][d]['harv_u'] += g
                    L['egg_harv_units'][g] += 1
        if op == 'FEED':
            L['wheat'][d][f'fed_{lab}'] += 1
            if lab == 'GOOSE':
                L['egg'][d]['feed'] += 1
        if op == 'CARE' and lab == 'GOOSE':
            L['egg'][d]['care'] += 1
    return r


def drop(private, cap):
    w = R['w']
    if w is not None and R['t'] >= T0 and private is w.private(R['seat']):
        car = Counter()
        for inv in private['inventories']:
            for kk, v in inv.items():
                if v > 0:
                    car[kk] += v
        before = dict(private['shed'])
        _drop(private, cap)
        d = R['t'] // 24
        for kk, v in car.items():
            lost = v - (private['shed'].get(kk, 0) - before.get(kk, 0))
            if lost > 0:
                R['L']['lost'][d][kk] += lost
            if kk in ('WHEAT', 'EGG'):
                R['L']['wheat' if kk == 'WHEAT' else 'egg'][d]['dump_in'] += v
        R['L']['dump_total'][d] = sum(car.values())
        return
    return _drop(private, cap)


def refresh_animals(farm, day):
    if not ours(farm):
        return _ra(farm, day)
    pre = {}
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get('animal') == 'GOOSE':
                pre[(x, y)] = json.loads(json.dumps(tile))
    _ra(farm, day)
    L = R['L']
    for (x, y), p in pre.items():
        t1 = farm['tiles'][y][x]
        e = L['egg'][day]
        e['goose_days'] += 1
        bank = p.get('pending_care_bonus', 0) or 0
        if not (isinstance(t1, dict) and t1.get('animal') == 'GOOSE'):
            e['escaped'] += 1
            continue
        a = E.ANIMALS['GOOSE']
        dsf = day + 1 - p['placed_day'] - a['first_yield_day']
        prod = dsf >= 0 and dsf % a['interval'] == 0
        if not prod:
            continue
        due = 1 + (bank if p['fed_today'] else 0)
        added = t1['yield_units'] - p['yield_units']
        e['produced'] += added
        e['swallowed'] += due - added
        e['bonus_paid'] += (bank if p['fed_today'] else 0)
        if not p['fed_today']:
            e['unfed'] += 1
            e['bank_wiped'] += bank
        elif not p['cared_today']:
            e['fed_not_cared'] += 1
        e['held_before'] += p['yield_units']
        L['goose_log'].append([day, x, y, int(p['fed_today']), int(p['cared_today']), bank, p['yield_units'], added])


def decay(farm, step):
    if not ours(farm):
        return _decay(farm, step)
    pre = {}
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get('kind') == 'PLANT' and tile.get('crop') == 'WHEAT':
                pre[(x, y)] = tile.get('yield_units', 0)
    _decay(farm, step)
    for (x, y), u in pre.items():
        t1 = farm['tiles'][y][x]
        u1 = t1.get('yield_units', 0) if isinstance(t1, dict) and t1.get('kind') == 'PLANT' else 0
        if u1 < u:
            R['L']['wheat'][step // 24]['decayed'] += u - u1
            if not (isinstance(t1, dict) and t1.get('kind') == 'PLANT'):
                R['L']['wheat'][step // 24]['decay_dead'] += 1


def refresh_plants(farm, day, tpd):
    if not ours(farm):
        return _rp(farm, day, tpd)
    pre = {}
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get('kind') == 'PLANT' and tile.get('crop') == 'WHEAT':
                pre[(x, y)] = tile.get('yield_units', 0)
    _rp(farm, day, tpd)
    for (x, y), u in pre.items():
        t1 = farm['tiles'][y][x]
        if not (isinstance(t1, dict) and t1.get('kind') == 'PLANT'):
            R['L']['wheat'][day]['died_unwatered'] += 1
            R['L']['wheat'][day]['died_units'] += u


E._commit_unit, E._apply_unit_action, E._drop_inventories_to_shed = commit, ua, drop
E._daily_refresh_animals, E._decay_plants, E._daily_refresh_plants = refresh_animals, decay, refresh_plants


def held(w, seat):
    f, pv = w.farms[seat], w.private(seat)
    out = {}
    for p, src in (('WHEAT', 'WHEAT'), ('EGG', 'GOOSE')):
        tiles = sum(int(x.get('yield_units', 0) or 0) for row in f['tiles'] for x in row
                    if isinstance(x, dict) and (x.get('animal') == src or x.get('crop') == src))
        n = sum(1 for row in f['tiles'] for x in row if isinstance(x, dict) and (x.get('animal') == src or x.get('crop') == src))
        car = sum(inv.get(p, 0) for inv in pv['inventories'])
        out[p] = [n, tiles, car, int(pv['shed'].get(p, 0) or 0)]
    return out


def labor(steps):
    """unit-steps by category; a MOVE is charged to the unit's next op of that day (or 'move_end' if none)."""
    by = defaultdict(list)
    for t, idx, op, lab, ok in steps:
        by[(t // 24, idx)].append((t, op, lab, ok))
    C = defaultdict(Counter)
    for (d, idx), seq in by.items():
        seq.sort()
        pend = 0
        for t, op, lab, ok in seq:
            if op in MOVES and ok:
                pend += 1
                continue
            if op in MOVES:
                C[d]['move_blocked'] += 1
                continue
            if op in OPS and ok:
                key = f'{op}|{lab}'
            elif op in OPS:
                key = 'failed'
            elif op in ('PICKUP', 'DROP', 'PLACE_HARVEST', 'PLACE', 'PLACE_ANIMAL') and ok:
                key = 'shed'
            elif op == 'PASS' or not ok:
                key = 'idle'
            else:
                key = op
            C[d][key] += 1
            if pend:
                C[d][key + '~move'] += pend
                pend = 0
        if pend:
            C[d]['move_end'] += pend
    return {d: dict(c) for d, c in C.items()}


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    L = {'sales': [], 'ops': defaultdict(Counter), 'lost': defaultdict(Counter), 'wheat': defaultdict(Counter),
         'egg': defaultdict(Counter), 'wheat_harv_age': Counter(), 'wheat_water_age': Counter(),
         'egg_harv_units': Counter(), 'goose_log': [], 'goose_steps': [], 'held': {}, 'dump_total': {}, 'price': {}, 'hands': {}}
    steps = []
    R.update(w=w, seat=seat, L=L, steps=steps)
    while w.t < 719:
        t = w.t
        R['t'] = t
        if t >= T0:
            L['held'][t] = held(w, seat)
            L['price'][t] = {p: w.market['prices'].get(p) for p in ('WHEAT', 'EGG')}
        if stream is None or t < T0:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        if t >= T0:
            L['hands'][t] = len(w.farms[seat]['hands'])
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    L['held'][719] = held(w, seat)
    L['money'] = {'us': w.farms[seat]['money'], 'opp': w.farms[1 - seat]['money']}
    L['labor'] = labor(steps)
    for k in ('ops', 'lost', 'wheat', 'egg'):
        L[k] = {d: dict(c) for d, c in L[k].items()}
    for k in ('wheat_harv_age', 'wheat_water_age', 'egg_harv_units'):
        L[k] = dict(L[k])
    R['w'] = None
    return L


if __name__ == '__main__':
    g, arm, out = sys.argv[1], sys.argv[2], sys.argv[3]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    res = {'game': g, 'arm': arm, 'leader': run(tape, None), arm: run(tape, s['actions'])}
    json.dump(res, open(out, 'w'), default=str)
    for who in ('leader', arm):
        print(who, res[who]['money'])
    print('written', out)

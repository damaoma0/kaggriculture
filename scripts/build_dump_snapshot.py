"""One day, leader vs an arm in the same world: board at hour 0, every unit's position / action / load each hour, shed
contents and sales each hour, midday drops at the shed, and the midnight dump (carried per unit, shed before, deleted by
product). Writes a self-contained viewer.  usage: build_dump_snapshot.py <team:ep> <day> <arm> [out.html]"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
R = {'w': None, 'seat': 0, 't': 0, 'sales': None, 'night': None, 'day': 0}
_commit, _drop = E._commit_unit, E._drop_inventories_to_shed


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and op == 'SELL' and R['t'] // 24 == R['day']:
        side = 'us' if farm is w.farms[R['seat']] else 'opp'
        R['sales'][R['t'] % 24][side][item] = R['sales'][R['t'] % 24][side].get(item, 0) + 1
    return r


def drop(private, cap):
    w = R['w']
    if w is not None and R['t'] // 24 == R['day'] and private is w.private(R['seat']):
        per = [{k: v for k, v in inv.items() if v > 0 and k in PROD} for inv in private['inventories']]
        before = {k: v for k, v in private['shed'].items() if v > 0}
        car = Counter()
        for p in per:
            car.update(p)
        _drop(private, cap)
        lost = {k: v - (private['shed'].get(k, 0) - before.get(k, 0)) for k, v in car.items()}
        R['night'] = {'per_unit': per, 'shed23': before, 'lost': {k: v for k, v in lost.items() if v > 0},
                      'shed_after': {k: v for k, v in private['shed'].items() if v > 0}}
        return
    return _drop(private, cap)


E._commit_unit, E._drop_inventories_to_shed = commit, drop


def tile_view(t):
    if t is None:
        return None
    if isinstance(t, str):
        return {'k': t}
    if t.get('kind') == 'PLANT':
        return {'k': 'PLANT', 'c': t.get('crop'), 'y': t.get('yield_units', 0), 'age': R['day'] - t.get('planted_day', 0)}
    if 'animal' in t:
        return {'k': 'ANIMAL', 'c': t.get('animal'), 'y': t.get('yield_units', 0), 'bank': t.get('pending_care_bonus', 0)}
    return {'k': t.get('kind')}


def run(tape, stream, day):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, day=day, sales=[{'us': {}, 'opp': {}} for _ in range(24)], night=None)
    hours = []
    board = None
    while w.t < (day + 1) * 24:
        t = w.t
        R['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        if t // 24 == day:
            f = w.farms[seat]
            pv = w.private(seat)
            if board is None:
                board = [[tile_view(x) for x in row] for row in f['tiles']]
            units = [f['farmer']] + list(f['hands'])
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            hours.append({
                'pos': [list(p) for p in units],
                'act': [acts[i] if i < len(acts) else None for i in range(len(units))],
                'inv': [{k: v for k, v in (pv['inventories'][i] if i < len(pv['inventories']) else {}).items() if v > 0 and k in PROD}
                        for i in range(len(units))],
                'shed': {k: v for k, v in pv['shed'].items() if v > 0},
                'orders': [o for o in (own.get('market') or []) if o],
                'money': [w.farms[seat]['money'], w.farms[1 - seat]['money']],
            })
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
    out = {'board': board, 'hours': hours, 'sales': R['sales'], 'night': R['night'],
           'money_end': [w.farms[seat]['money'], w.farms[1 - seat]['money']]}
    R['w'] = None
    return out


if __name__ == '__main__':
    g, day, arms = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(',')
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    sides = {'DSM (leader)': run(tape, None, day)}
    for arm in arms:
        s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
        sides[arm] = run(tape, s, day)
    data = {'ep': ep, 'team': team, 'day': day, 'arm': ','.join(arms), 'sides': sides}
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / 'viz' / f'dump_snapshot_{ep}_d{day}_{"_".join(a.lower() for a in arms)}.html'
    tpl = (ROOT / 'viz' / 'dump_snapshot_template.html').read_text(encoding='utf-8')
    out.write_text(tpl.replace('/*DATA*/null', json.dumps(data, separators=(',', ':'))), encoding='utf-8')
    print('wrote', out)

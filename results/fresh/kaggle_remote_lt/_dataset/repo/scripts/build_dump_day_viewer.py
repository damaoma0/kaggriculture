"""One day, leader vs an arm in the same world, for diagnosing midnight deletions (extends build_dump_snapshot.py).

Per side: the board at the start of every hour (crop / animal units held, fed / cared / watered flags), every unit's
position, action and load each hour, the shed each hour, our sales by hour, every harvest with its fate (delivered
to the shed at hour h / used / carried to midnight / deleted at the dump), the animal pens (held at dawn, harvested,
held at the end of the day, tonight's production), mid-day drops, and the midnight dump attributed to units in the
engine's order (farmer first, then hands by index; everything past 100 is deleted). The arm side also carries its
planned route per hand and hour (the stream's plan log).
usage: build_dump_day_viewer.py <team:ep> <day> <arm> [out.html]  -> viz/dump_day_<ep>_d<day>.html
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
import leader_shed_flow as L  # noqa: E402  (installs the shed-flow hooks on the engine)

E = L.E
PROD = L.PROD
SNAP = {'w': None, 'seat': 0, 'day': None, 'end': None}
_refresh_plants0 = E._daily_refresh_plants


def tile_view(t, day):
    if t is None or isinstance(t, str):
        return [t or '', 0]
    if t.get('kind') == 'PLANT':
        return ['P:' + t.get('crop', '?'), t.get('yield_units', 0), day - t.get('planted_day', day),
                int(bool(t.get('watered_today'))), int(t.get('fertilized_until_day', -1) >= day)]
    if 'animal' in t:
        return ['A:' + t['animal'], t.get('yield_units', 0), int(bool(t.get('fed_today'))),
                int(bool(t.get('cared_today'))), t.get('pending_care_bonus', 0)]
    return [t.get('kind', ''), 0]


def board(farm, day):
    return [tile_view(x, day) for row in farm['tiles'] for x in row]


def refresh_plants(farm, current_day, tpd):
    w = SNAP['w']
    if w is not None and farm is w.farms[SNAP['seat']] and current_day == SNAP['day']:
        SNAP['end'] = board(farm, current_day)          # after hour 23, before tonight's refresh
    return _refresh_plants0(farm, current_day, tpd)


E._daily_refresh_plants = refresh_plants


def attribute(shed23, per_unit_inv, cap=100):
    """The engine's dump (_drop_inventories_to_shed): units in order, items in inventory order, room = cap - shed."""
    cur = sum(shed23.values())
    out = []
    for inv in per_unit_inv:
        d = {}
        for k, n in inv.items():
            take = min(n, max(0, cap - cur))
            cur += take
            if n > take:
                d[k] = n - take
        out.append(d)
    return out


def run(tape, stream, day):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    L.R.update(w=w, seat=seat, mk=defaultdict(lambda: [0, 0.0]), trace=defaultdict(list), night=None)
    SNAP.update(w=w, seat=seat, day=day, end=None)
    hours, res = [], {}
    pi = {p: i for i, p in enumerate(PROD)}
    while True:
        t = w.t
        if t == (day + 1) * 24:
            res['morning'] = board(w.farms[seat], day + 1)
            break
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        if t // 24 == day:
            f, pv, mkt = w.farms[seat], w.private(seat), w.market
            units = [f['farmer']] + list(f['hands'])
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            hours.append({
                'tiles': board(f, day),
                'pos': [list(p) for p in units],
                'act': [acts[i] if i < len(acts) else None for i in range(len(units))],
                'inv': [{k: v for k, v in (pv['inventories'][i] if i < len(pv['inventories']) else {}).items() if v > 0}
                        for i in range(len(units))],
                'shed': {k: v for k, v in pv['shed'].items() if v > 0},
                'orders': [o for o in (own.get('market') or []) if o],
                'money': [f['money'], w.farms[1 - seat]['money']],
                'quote': {p: round(E.market_price(p, mkt['inventory'][p], mkt.get('params')), 1) for p in PROD},
            })
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
        if t % 24 == 23:
            d, u, hv = L._day_units(L.R['trace'], t // 24, L.R['mk'])
            if t // 24 == day:
                res.update(drops=d, units=u, harv=hv, night=L.R['night'])
            L.R['trace'], L.R['night'] = defaultdict(list), None
    sales = [{} for _ in range(24)]
    for (t, op, item), (n, rev) in L.R['mk'].items():
        if op == 'SELL' and t // 24 == day:
            sales[t % 24][item] = [n, round(rev, 1)]
    night = res['night']
    dele = attribute(night['shed23'], night['per_unit_inv'])
    assert sum(sum(x.values()) for x in dele) == sum(night['lost'].values()), (dele, night['lost'])
    # harvest fates: delivered hour / used / carried / deleted (a unit's deleted units of a product = its latest harvests)
    left = [dict(x) for x in dele]
    harv = []
    for (_, idx, k, h, m, fate, pos) in sorted(res['harv'], key=lambda x: (x[1], -x[3])):
        dl = min(m, left[idx].get(k, 0)) if fate == 24 and idx < len(left) else 0
        if dl:
            left[idx][k] -= dl
            harv.append([h, idx, k, dl, list(pos), 'deleted'])
        if m - dl:
            harv.append([h, idx, k, m - dl, list(pos), 'used' if fate == -1 else ('carried' if fate == 24 else fate)])
    harv.sort(key=lambda x: (x[0], x[1]))
    R_ = {'hours': hours, 'end': SNAP['end'], 'morning': res['morning'], 'sales': sales, 'harv': harv,
          'drops': [{k: x[k] for k in ('h', 'unit', 'produce', 'putback', 'sold_same_h', 'visit', 'inv_before', 'at')}
                    for x in res['drops']],
          'night': {'shed23': night['shed23'], 'per_unit': night['per_unit_inv'], 'lost': night['lost'], 'deleted': dele},
          'units': [{k: x[k] for k in ('unit', 'first_h', 'harvested', 'drops', 'trips')} for x in res['units']],
          'money_end': [w.farms[seat]['money'], w.farms[1 - seat]['money']]}
    L.R['w'] = SNAP['w'] = None
    return R_


def main():
    g, day, arm = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    arm_side = run(tape, s['actions'], day)
    plan = s.get('plan') or {}
    arm_side['plan'] = {str(h): plan.get(str(day * 24 + h)) for h in range(24) if plan.get(str(day * 24 + h))}
    leader = run(tape, None, day)
    name = (tape.get('names') or ['', ''])[tape['seat']] or 'leader'
    data = {'ep': ep, 'team': team, 'day': day, 'arm': arm, 'arm_label': s.get('arm', arm),
            'sides': {f'{name} (leader)': leader, arm: arm_side}}
    out = Path(sys.argv[4]) if len(sys.argv) > 4 else ROOT / 'viz' / f'dump_day_{ep}_d{day}.html'
    tpl = (ROOT / 'viz' / 'dump_day_template.html').read_text(encoding='utf-8')
    out.write_text(tpl.replace('/*DATA*/null', json.dumps(data, separators=(',', ':'))), encoding='utf-8')
    for k, v in data['sides'].items():
        n = v['night']
        print(k, 'carried', sum(sum(x.values()) for x in n['per_unit']), 'shed23', sum(n['shed23'].values()),
              'deleted', sum(n['lost'].values()), n['lost'])
    print('wrote', out)


if __name__ == '__main__':
    main()

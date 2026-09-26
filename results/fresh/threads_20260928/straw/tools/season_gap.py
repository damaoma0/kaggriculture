"""Season gap decomposition, leader (recorded episode) vs an arm's season stream, days 11-29, same world:
money flows (sales by product, wheat / seed / animal purchases, hire costs, land), production (units harvested or
collected by product), upkeep work (successful FEED / CARE / WATER / FERTILIZE / PLANT / HARVEST by crop or animal),
midnight deletions by product, end stock, herd and plant counts, and the rival's sales by product.
usage: season_gap.py <arm> <panel file | team:ep,...> <out.json> [--workers 3]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(r'C:/Users/xyygl/Documents/kaggriculture')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
OPS = ('HARVEST', 'FEED', 'CARE', 'WATER', 'FERTILIZE', 'PLANT', 'COLLECT_FERTILIZER')
REC = {'w': None, 'seat': 0, 'on': False, 'C': None}
_commit, _hire, _land, _ua, _drop = E._commit_unit, E._do_hire, E._do_buy_land, E._apply_unit_action, E._drop_inventories_to_shed


def _side(farm):
    w = REC['w']
    if w is None or not REC['on']:
        return None
    return 'us' if farm is w.farms[REC['seat']] else 'opp'


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    s = _side(farm)
    if r and s:
        C = REC['C']
        C[f'{s}|{op}|{item}|n'] += 1
        C[f'{s}|{op}|{item}|$'] += float(price)
    return r


def hire(farm, private, board_size, *a, **k):
    m0 = farm['money']
    r = _hire(farm, private, board_size, *a, **k)
    s = _side(farm)
    if s == 'us' and farm['money'] < m0:
        REC['C']['us|HIRE|n'] += 1
        REC['C']['us|HIRE|$'] += m0 - farm['money']
    return r


def land(farm, board_size, *a, **k):
    m0 = farm['money']
    r = _land(farm, board_size, *a, **k)
    if _side(farm) == 'us' and farm['money'] < m0:
        REC['C']['us|LAND|$'] += m0 - farm['money']
    return r


def ua(farm, private, idx, action, *a, **k):
    if not (isinstance(action, list) and action and action[0] in OPS) or _side(farm) != 'us':
        return _ua(farm, private, idx, action, *a, **k)
    pos = E._farmer_position(farm, idx)
    if pos is None:
        return _ua(farm, private, idx, action, *a, **k)
    t0 = farm['tiles'][pos[1]][pos[0]]
    lab = (t0.get('crop') or t0.get('animal') or t0.get('kind')) if isinstance(t0, dict) else 'EMPTY'
    tb = json.dumps(t0, sort_keys=True, default=str)
    inv = E._farmer_inventory(private, idx)
    ib = dict(inv)
    sb = dict(private['seeds'])
    r = _ua(farm, private, idx, action, *a, **k)
    t1 = farm['tiles'][pos[1]][pos[0]]
    ia = E._farmer_inventory(private, idx)
    if json.dumps(t1, sort_keys=True, default=str) != tb or ia != ib or private['seeds'] != sb:
        C = REC['C']
        op = action[0]
        if op == 'PLANT':
            lab = action[1] if len(action) > 1 else lab
        C[f'ok|{op}|{lab}'] += 1
        if op in ('HARVEST', 'COLLECT_FERTILIZER'):
            for kk, v in ia.items():
                d = v - ib.get(kk, 0)
                if d > 0:
                    C[f'got|{kk}'] += d
                    if op == 'HARVEST':
                        C[f'hv_units|{lab}'] += d
    return r


def drop(private, cap):
    w = REC['w']
    if w is not None and REC['on'] and private is w.private(REC['seat']):
        car = Counter()
        for inv in private['inventories']:
            for kk, v in inv.items():
                if v > 0:
                    car[kk] += v
        before = dict(private['shed'])
        _drop(private, cap)
        for kk, v in car.items():
            lost = v - (private['shed'].get(kk, 0) - before.get(kk, 0))
            if lost > 0:
                REC['C'][f'lost|{kk}'] += lost
        return
    return _drop(private, cap)


E._commit_unit, E._do_hire, E._do_buy_land, E._apply_unit_action, E._drop_inventories_to_shed = commit, hire, land, ua, drop


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    C = Counter()
    REC.update(w=w, seat=seat, C=C, on=False)
    while w.t < 720:
        t = w.t
        REC['on'] = t >= 264
        if t >= 264 and t % 24 == 0:
            for row in w.farms[seat]['tiles']:
                for x in row:
                    if isinstance(x, dict):
                        C[f'count|{x.get("crop") or x.get("animal") or x.get("kind")}'] += 1
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    pv = w.private(seat)
    for kk, v in pv['shed'].items():
        C[f'end|{kk}'] += v
    for inv in pv['inventories']:
        for kk, v in inv.items():
            C[f'end|{kk}'] += v
    C['money|us'] = w.farms[seat]['money']
    C['money|opp'] = w.farms[1 - seat]['money']
    REC['w'] = None
    return dict(C)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    return ep, {'leader': run(tape, None), arm: run(tape, s['actions'])}


if __name__ == '__main__':
    arm, games, out = sys.argv[1], sys.argv[2], sys.argv[3]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    p = Path(games)
    games = p.read_text().replace(',', ' ').split() if p.exists() else games.split(',')
    res = {}
    with Pool(nw) as pool:
        for ep, r in pool.imap_unordered(job, [(g, arm) for g in games]):
            res[ep] = r
            print('done', ep, len(res), flush=True)
    json.dump(res, open(out, 'w'))

"""Sale timing, leader game vs an arm's game (same world, days 11-29): every successful SELL of both players by
(product, day, hour) with revenue, our harvests by (product, day, hour), and every midnight dump (carried in, shed
before, deleted by product). usage: season_timing.py <arm> <panel file | team:ep,...> <out.json> [--workers 2]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
R = {'w': None, 'seat': 0, 't': 0, 'C': None, 'N': None}
_commit, _ua, _drop = E._commit_unit, E._apply_unit_action, E._drop_inventories_to_shed


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and op == 'SELL' and R['t'] >= 264:
        side = 'us' if farm is w.farms[R['seat']] else 'opp'
        d, h = divmod(R['t'], 24)
        R['C'][f'{side}|{item}|{d}|{h}|n'] += 1
        R['C'][f'{side}|{item}|{d}|{h}|$'] += float(price)
    return r


def ua(farm, private, idx, action, *a, **k):
    w = R['w']
    if not (w is not None and R['t'] >= 264 and isinstance(action, list) and action and action[0] == 'HARVEST'
            and farm is w.farms[R['seat']]):
        return _ua(farm, private, idx, action, *a, **k)
    inv = E._farmer_inventory(private, idx)
    b = dict(inv) if inv is not None else {}
    r = _ua(farm, private, idx, action, *a, **k)
    inv = E._farmer_inventory(private, idx) or {}
    d, h = divmod(R['t'], 24)
    for kk, v in inv.items():
        if v - b.get(kk, 0) > 0:
            R['C'][f'hv|{kk}|{d}|{h}'] += v - b.get(kk, 0)
    return r


def drop(private, cap):
    w = R['w']
    if w is not None and R['t'] >= 264 and private is w.private(R['seat']):
        car = Counter()
        for inv in private['inventories']:
            for kk, v in inv.items():
                if v > 0:
                    car[kk] += v
        before = dict(private['shed'])
        _drop(private, cap)
        lost = {kk: v - (private['shed'].get(kk, 0) - before.get(kk, 0)) for kk, v in car.items()}
        R['N'][R['t'] // 24] = {'shed23': sum(v for v in before.values() if v > 0), 'carried': sum(car.values()),
                               'lost': {kk: v for kk, v in lost.items() if v > 0}}
        return
    return _drop(private, cap)


E._commit_unit, E._apply_unit_action, E._drop_inventories_to_shed = commit, ua, drop


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, C=Counter(), N={})
    while w.t < 719:                              # step 718 is the last one the real interpreter executes
        t = w.t
        R['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    out = {'C': dict(R['C']), 'N': R['N'], 'money': [w.farms[seat]['money'], w.farms[1 - seat]['money']]}
    R['w'] = None
    return out


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

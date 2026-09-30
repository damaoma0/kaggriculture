"""Hands returning to the shed and the flow of goods, leader game vs an arm's game (days 11-28, same world).
Per unit-step: a RETURN is a unit reaching a shed-access tile after being away; a DELIVERY is a DROP / PLACE at an
access tile that moves produce into the shed (units by product). Also: harvests by product and hour, midnight carry by
product, sales by product and hour, hands employed per day.
usage: season_returns.py <arm> <panel file | team:ep,...> <out.json> [--workers 2]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PROD = ('WHEAT', 'CARROT', 'TOMATO', 'MELON', 'STRAWBERRY', 'MILK', 'EGG', 'WOOL', 'FERTILIZER')
ACCESS = {tuple(p) for p in E._shed_access_tiles(10)}
R = {'w': None, 'seat': 0, 't': 0, 'C': None}
_commit, _drop = E._commit_unit, E._drop_inventories_to_shed


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and op == 'SELL' and 264 <= R['t'] < 696 and farm is w.farms[R['seat']]:
        R['C'][f'sell|{item}|{R["t"] % 24}'] += 1
    return r


def drop(private, cap):
    w = R['w']
    if w is not None and 264 <= R['t'] < 696 and private is w.private(R['seat']):
        for i, inv in enumerate(private['inventories']):
            n = sum(v for k, v in inv.items() if k in PROD and v > 0)
            if i > 0:
                R['C']['night_hand_loads'] += 1
                R['C'][f'night_load_{min(n // 5 * 5, 30)}'] += 1
            for k, v in inv.items():
                if k in PROD and v > 0:
                    R['C'][f'carried|{k}'] += v
    return _drop(private, cap)


E._commit_unit, E._drop_inventories_to_shed = commit, drop


def run(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    C = Counter()
    R.update(w=w, seat=seat, C=C)
    away = {}
    while w.t < 696:                                # days 11-28
        t = w.t
        R['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        track = t >= 264
        if track:
            f = w.farms[seat]
            pv = w.private(seat)
            pos = [tuple(f['farmer'])] + [tuple(p) for p in f['hands']]
            acts = [own.get('farmer')] + list(own.get('hands') or [])
            inv0 = [dict(pv['inventories'][i]) if i < len(pv['inventories']) else {} for i in range(len(pos))]
            h = t % 24
            if h == 0:
                away = {}
                C['hand_days'] += len(pos) - 1
            for i, p in enumerate(pos):
                if p in ACCESS:
                    if away.get(i):
                        C[f'return|{"farmer" if i == 0 else "hand"}|{h}'] += 1
                        C[f'returned_{"farmer" if i == 0 else "hand"}|{t // 24}|{i}'] = 1
                    away[i] = False
                elif i not in away or away[i] is False:
                    away[i] = True
        acts2 = [None, None]
        acts2[seat], acts2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts2)
        if track:
            pv = w.private(seat)
            for i, p in enumerate(pos):
                a = acts[i] if i < len(acts) else None
                if not (isinstance(a, list) and a and a[0] in ('DROP', 'PLACE') and p in ACCESS):
                    continue
                if a[0] == 'PLACE' and len(a) > 1 and a[1] in ('COW', 'SHEEP', 'GOOSE'):
                    continue
                inv1 = pv['inventories'][i] if i < len(pv['inventories']) else {}
                moved = {k: v - inv1.get(k, 0) for k, v in inv0[i].items() if k in PROD and v - inv1.get(k, 0) > 0}
                if not moved:
                    continue
                who = 'farmer' if i == 0 else 'hand'
                C[f'deliv|{who}|{h}'] += 1
                C[f'deliv_units|{who}|{h}'] += sum(moved.values())
                C[f'delivered_{who}|{t // 24}|{i}'] = 1
                for k, v in moved.items():
                    C[f'dunits|{k}|{h}'] += v
    out = {k: v for k, v in C.items() if not k.startswith(('returned_', 'delivered_'))}
    out['hands_returning'] = sum(1 for k in C if k.startswith('returned_hand|'))
    out['hands_delivering'] = sum(1 for k in C if k.startswith('delivered_hand|'))
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

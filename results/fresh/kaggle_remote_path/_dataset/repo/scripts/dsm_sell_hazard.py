"""The leader's selling as a function of what it can observe (40 recorded games): per product and hour of day (and season
phase), the share of the units in its shed at the step start that it sells in that step (the selling "hazard"), plus the
lot sizes and the market price it accepts. The basis of a DSM-free seller: sell hazard[p][phase][h] x our shed stock.
usage: dsm_sell_hazard.py <out.json> [--workers 2]"""
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODS = ('STRAWBERRY', 'WOOL', 'MILK', 'EGG', 'WHEAT', 'CARROT', 'TOMATO', 'FERTILIZER', 'MELON')
R = {'w': None, 'seat': 0, 't': 0, 'sold': None}
_commit = E._commit_unit


def commit(op, item, price, farm, private, market, shed_capacity=100):
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and op == 'SELL' and farm is w.farms[R['seat']] and R['t'] >= 264:
        R['sold'][item].append(price)
    return r


E._commit_unit = commit


def phase(d):
    return 'early' if d <= 17 else ('mid' if d <= 23 else 'late')


def job(g):
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    A = defaultdict(float)          # (p, phase, h) -> units available at the step start
    S = defaultdict(float)          # (p, phase, h) -> units sold
    lots = defaultdict(list)
    while w.t < 719:
        t = w.t
        R.update(w=w, seat=seat, t=t, sold=defaultdict(list))
        sh = dict(w.private(seat)['shed']) if t >= 264 else {}
        acts = [None, None]
        acts[seat], acts[1 - seat] = UE.tape_action(tape['actions'], t), UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
        if t >= 264 and t < 718:
            d, h = t // 24, t % 24
            for p in PRODS:
                a = int(sh.get(p, 0) or 0)
                n = len(R['sold'][p])
                # units dropped this step and sold at once count as available too (unit actions come before the market)
                a = max(a, n)
                if a:
                    A[f'{p}|{phase(d)}|{h}'] += a
                    S[f'{p}|{phase(d)}|{h}'] += n
                if n:
                    lots[p].append(n)
    R['w'] = None
    return {'A': dict(A), 'S': dict(S), 'lots': {p: v for p, v in lots.items()}}


if __name__ == '__main__':
    out = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    A, S, lots = defaultdict(float), defaultdict(float), defaultdict(list)
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, games):
            for k, v in r['A'].items():
                A[k] += v
            for k, v in r['S'].items():
                S[k] += v
            for p, v in r['lots'].items():
                lots[p] += v
    haz = {k: S[k] / A[k] for k in A if A[k] > 0}
    json.dump({'hazard': haz, 'avail': dict(A), 'sold': dict(S),
               'lot_p90': {p: sorted(v)[int(0.9 * (len(v) - 1))] for p, v in lots.items()}}, open(out, 'w'))
    for p in ('STRAWBERRY', 'WOOL', 'MILK'):
        for ph in ('early', 'mid', 'late'):
            print(f'{p:10s} {ph:5s} ' + ' '.join(f'{haz.get(f"{p}|{ph}|{h}", 0):.2f}' for h in range(24)))

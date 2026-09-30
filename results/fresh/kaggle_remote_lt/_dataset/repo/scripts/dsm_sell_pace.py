"""The leader's selling PACE (40 recorded games, days 11-29): at each step, the share of the day's goods it has sold so
far, where the day's goods = shed stock at the start of the step + what it already sold today (dawn stock + arrivals).
pace = (sold today before the step + sold this step) / (shed at the start of the step + sold today before it), as a
ratio of sums by product, season phase, hour and the rival's habit (its mean units of that product at this hour 'now'
>= 1, and in the next 4 hours 'soon' >= 2, over the previous 3 days - the signals a deployed agent forms from the market,
same as dsm_sell_hazard2.py). A deployed seller sells up to pace x (our shed + our sales today) - our sales today.
Output: {"p2": {p|phase|h|now|soon: pace}, "p1": {p|phase|h: pace}, "n": {key: goods-steps}}.
usage: dsm_sell_pace.py <out.json> [--exclude ep,ep,...]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402
from dsm_sell_hazard2 import phase, rival_signal, PRODS  # noqa: E402

E = UE.engine()


def job(g):
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    T = [0]
    us, riv = defaultdict(int), defaultdict(int)
    orig = E._commit_unit

    def commit(op, item, price, farm, private, market, cap=100):
        r = orig(op, item, price, farm, private, market, cap)
        if r and op == 'SELL' and T[0] >= 264:
            (us if farm is w.farms[seat] else riv)[(T[0], item)] += 1
        return r
    E._commit_unit = commit
    shed = {}
    while w.t < 719:
        t = w.t
        T[0] = t
        if t >= 264:
            shed[t] = dict(w.private(seat)['shed'])
        a2 = [None, None]
        a2[seat], a2[1 - seat] = UE.tape_action(tape['actions'], t), UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    E._commit_unit = orig
    A2, S2, A1, S1 = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    for p in PRODS:
        sold_today = 0
        for t in range(264, 718):
            if t % 24 == 0:
                sold_today = 0
            have = int(shed[t].get(p, 0) or 0)
            goods = have + sold_today
            s_t = us[(t, p)]
            if goods + s_t > 0:
                now, soon = rival_signal(riv, p, t)
                ph = phase(t // 24)
                k1 = f'{p}|{ph}|{t % 24}'
                k2 = f'{k1}|{now}|{soon}'
                num = min(sold_today + s_t, max(goods, sold_today + s_t))
                den = max(goods, sold_today + s_t)
                A2[k2] += den
                S2[k2] += num
                A1[k1] += den
                S1[k1] += num
            sold_today += s_t
    return A2, S2, A1, S1


if __name__ == '__main__':
    out = sys.argv[1]
    excl = set(sys.argv[sys.argv.index('--exclude') + 1].split(',')) if '--exclude' in sys.argv else set()
    games = [g for g in (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
             if g.split(':')[1].strip() not in excl]
    A2, S2, A1, S1 = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    for g in games:
        a2, s2, a1, s1 = job(g.strip())
        for D, X in ((A2, a2), (S2, s2), (A1, a1), (S1, s1)):
            for k, v in X.items():
                D[k] += v
    json.dump({'p2': {k: S2[k] / A2[k] for k in A2 if A2[k] >= 20}, 'p1': {k: S1[k] / A1[k] for k in A1 if A1[k] >= 20},
               'n': dict(A1), 'games': len(games)}, open(out, 'w'))
    for p in ('STRAWBERRY', 'WOOL', 'MILK', 'EGG', 'TOMATO', 'FERTILIZER'):
        for ph in ('early', 'mid', 'late'):
            row = [(h, S1.get(f'{p}|{ph}|{h}', 0) / A1[f'{p}|{ph}|{h}']) for h in range(24) if A1.get(f'{p}|{ph}|{h}', 0) >= 20]
            print(f'{p:10s} {ph:5s} ' + ' '.join(f'{h}:{v:.2f}' for h, v in row if h in (0, 1, 5, 9, 13, 17, 21, 23)))

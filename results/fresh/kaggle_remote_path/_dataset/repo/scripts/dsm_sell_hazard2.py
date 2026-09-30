"""The leader's selling hazard conditioned on the rival (40 recorded games): share of the shed stock sold, by product, season
phase, hour, and the rival's selling predicted from the previous 3 days (mean rival units of that product at this hour:
'now' >= 1, and in the next 4 hours of the day: 'soon' >= 2) - the signals a deployed agent can form from the market
(rival sales = stock change - own sales + shop consumption). Output: hazard2[p|phase|h|now|soon].
usage: dsm_sell_hazard2.py <out.json>"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODS = ('STRAWBERRY', 'WOOL', 'MILK', 'EGG', 'WHEAT', 'CARROT', 'TOMATO', 'FERTILIZER')


def phase(d):
    return 'early' if d <= 17 else ('mid' if d <= 23 else 'late')


def rival_signal(riv, p, t, lookback=3):
    """predicted rival units of p now and in the next 4 hours of the day, from the same hours of the previous days"""
    d, h = t // 24, t % 24
    days = [d - k for k in range(1, lookback + 1) if d - k >= 11]
    if not days:
        return 0, 0
    now = sum(riv.get((dd * 24 + h, p), 0) for dd in days) / len(days)
    soon = sum(riv.get((dd * 24 + hh, p), 0) for dd in days for hh in range(h + 1, min(24, h + 5))) / len(days)
    return int(now >= 1), int(soon >= 2)


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
    avail = {}
    while w.t < 719:
        t = w.t
        T[0] = t
        if t >= 264:
            avail[t] = dict(w.private(seat)['shed'])
        a2 = [None, None]
        a2[seat], a2[1 - seat] = UE.tape_action(tape['actions'], t), UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    E._commit_unit = orig
    A, S = defaultdict(float), defaultdict(float)
    for t in range(264, 718):
        for p in PRODS:
            a = max(int(avail[t].get(p, 0) or 0), us[(t, p)])
            if not a:
                continue
            now, soon = rival_signal(riv, p, t)
            k = f'{p}|{phase(t // 24)}|{t % 24}|{now}|{soon}'
            A[k] += a
            S[k] += us[(t, p)]
    return dict(A), dict(S)


if __name__ == '__main__':
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    A, S = defaultdict(float), defaultdict(float)
    for g in games:
        a, s = job(g)
        for k, v in a.items():
            A[k] += v
        for k, v in s.items():
            S[k] += v
    json.dump({'hazard2': {k: S[k] / A[k] for k in A if A[k] >= 20}, 'avail': dict(A)}, open(sys.argv[1], 'w'))
    for p in ('STRAWBERRY', 'WOOL', 'MILK'):
        for sig in ('0|0', '0|1', '1|0', '1|1'):
            ks = [k for k in A if k.startswith(p + '|') and k.endswith('|' + sig)]
            a = sum(A[k] for k in ks)
            print(f'{p:10s} rival now|soon {sig}: DSM hazard {sum(S[k] for k in ks) / max(1, a):.3f} over {a:.0f} unit-steps')

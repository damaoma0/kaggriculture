"""How much of the leader's sale timing we can reach with our logistics.

Replays our game and logs, per product: when each unit becomes sellable in our shed (drops during the day: that
step; the midnight dump at the end of hour 23: the next step), our sales, the rival's sales with the market stock each
sold into, and the market stock at the start of every step. Shop consumption is a fixed schedule, so moving our sales
shifts the stock by delta(t) = (our units sold by t in the counterfactual) - (actual) and prices follow exactly.
Counterfactual A: our k-th unit at the leader's k-th sale time (no stock constraint; earlier result +13.8k).
Counterfactual B: our k-th unit at max(the leader's k-th sale time, the time our k-th unit became sellable), FIFO:
the part a market policy alone (holding / releasing stock) can reach with our current deliveries.
usage: sale_pattern_cf.py <arm> <timing json of that arm> <out.json> [--workers 2]"""
import bisect
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODS = ('WOOL', 'MILK', 'STRAWBERRY', 'EGG', 'WHEAT', 'CARROT', 'TOMATO', 'FERTILIZER')
R = {'w': None, 'seat': 0, 't': 0, 'ev': None}
DUMP_H1 = 1 if '--dump-h1' in sys.argv else 0   # the night's dump sellable from hour 1 (our hour-0 slots go to hires)
_commit = E._commit_unit


def commit(op, item, price, farm, private, market, shed_capacity=100):
    inv = market['inventory'].get(item)
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and item in PRODS and R['t'] >= 264 and op in ('SELL', 'BUY_PRODUCT'):
        side = 'us' if farm is w.farms[R['seat']] else 'opp'
        R['ev'].append((R['t'], side, op, item, float(price), inv))
    return r


E._commit_unit = commit


def run(args):
    g, arm, leader_times = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, ev=[])
    stock = {p: {} for p in PRODS}
    avail = {p: [] for p in PRODS}
    while w.t < 719:
        t = w.t
        R['t'] = t
        if t >= 264:
            sh0 = dict(w.private(seat)['shed'])
            n_ev = len(R['ev'])
            for p in PRODS:
                stock[p][t] = w.market['inventory'][p]
            if t == 264:
                for p in PRODS:
                    avail[p] += [264] * int(sh0.get(p, 0) or 0)
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if t < len(s) and isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
        if t >= 264:
            sh1 = w.private(seat)['shed']
            for p in PRODS:
                sold = sum(1 for e in R['ev'][n_ev:] if e[1] == 'us' and e[3] == p and e[2] == 'SELL')
                bought = sum(1 for e in R['ev'][n_ev:] if e[1] == 'us' and e[3] == p and e[2] == 'BUY_PRODUCT')
                arr = int(sh1.get(p, 0) or 0) - int(sh0.get(p, 0) or 0) + sold - bought
                if arr > 0:
                    avail[p] += [(t + 1 + DUMP_H1) if t % 24 == 23 else t] * arr
    params = w.market.get('params')
    out = {}
    for p in PRODS:
        ev = [e for e in R['ev'] if e[3] == p]
        ours = [e for e in ev if e[1] == 'us' and e[2] == 'SELL']
        riv = [e for e in ev if e[1] == 'opp' and e[2] == 'SELL']
        a_times = sorted(e[0] for e in ours)
        l_times = sorted(leader_times.get(p, []))
        av = sorted(avail[p])
        m = min(len(a_times), len(l_times))
        res = {'units': len(ours), 'leader_units': len(l_times), 'rival_act': sum(e[4] for e in riv),
               'our_act': sum(e[4] for e in ours)}
        for tag in ('A', 'B'):
            if tag == 'A':
                cf = sorted(l_times[:m] + a_times[m:])
            else:
                cf = []
                for k in range(len(a_times)):
                    if k < m:
                        a_k = av[k] if k < len(av) else a_times[k]
                        cf.append(max(l_times[k], a_k))
                    else:
                        cf.append(a_times[k])
                cf.sort()

            def delta(t, cf=cf):
                return bisect.bisect_left(cf, t) - bisect.bisect_left(a_times, t)

            res[f'rival_{tag}'] = sum(E.market_price(p, e[5] + delta(e[0]), params) for e in riv)
            our = 0.0
            same_t = defaultdict(int)
            for t in cf:
                base = stock[p].get(min(t, 718), 0)
                our += E.market_price(p, base + delta(t) + same_t[t], params)
                same_t[t] += 1
            res[f'our_{tag}'] = our
        out[p] = res
    R['w'] = None
    return ep, out


if __name__ == '__main__':
    arm, tfile, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    T = json.load(open(tfile))
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    jobs = []
    for g in games:
        ep = g.split(':')[1]
        lt = defaultdict(list)
        for k, v in T[ep]['leader']['C'].items():
            parts = k.split('|')
            if len(parts) == 5 and parts[0] == 'us' and parts[4] == 'n':
                lt[parts[1]] += [int(parts[2]) * 24 + int(parts[3])] * v
        jobs.append((g, arm, dict(lt)))
    res = {}
    with Pool(nw) as pool:
        for ep, r in pool.imap_unordered(run, jobs):
            res[ep] = r
    json.dump(res, open(outp, 'w'))
    n = len(res)
    print(f'{n} worlds, per world. A = our units at the leader\'s sale times (no stock constraint); '
          f'B = the same but never before the unit is in our shed (market policy only)')
    tot = defaultdict(float)
    for p in PRODS:
        g_ = lambda k: sum(r[p][k] for r in res.values()) / n
        ra, oa = g_('rival_act'), g_('our_act')
        line = '  %-10s' % p
        for tag in ('A', 'B'):
            dr, do = g_(f'rival_{tag}') - ra, g_(f'our_{tag}') - oa
            tot[tag + 'r'] += dr
            tot[tag + 'o'] += do
            line += ' | %s: rival %+6.0f, ours %+6.0f, margin %+6.0f' % (tag, dr, do, do - dr)
        print(line)
    for tag in ('A', 'B'):
        print('  TOTAL %s: rival %+.0f, ours %+.0f, margin %+.0f' % (tag, tot[tag + 'r'], tot[tag + 'o'], tot[tag + 'o'] - tot[tag + 'r']))

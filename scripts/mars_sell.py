"""Selling strategy in isolation ("goods from Mars"): the farm plays exactly as the arm's game (same actions, same units
produced and sold); only the times at which our units of a product are sold change. Shop consumption is a fixed
schedule and the rival's orders are recorded, so the market stock at any moment = the actual stock + (our units sold
by then under the strategy - actually sold by then), and every price (ours and the rival's) follows exactly from
market_price(stock). No planner, no hands, no cash feedback: nothing but the sale times moves.
Approximation: within one step the rival's units go first (our sells sit behind the hires), then ours in order; the
rival's are priced at its recorded stock + the shift. 'calib' prices the ACTUAL
schedule the same way (checks the approximation against the real revenue).
Strategies (our units only; units beyond the leader's count keep their actual times):
  day     the current rule (KS1): at hour 1 of day d sell up to the leader's cumulative sales through day d
  hourly  the KQ rule: at hour h of day d sell up to leader cum[d-1] + share[h] x (cum[d] - cum[d-1]) (DSM profile)
  books   our k-th unit at the leader's k-th sale time (DSM's exact books)
each three times: 'mars' = any unit available whenever the rule wants it; 'harv' = never before that unit was harvested
(as if teleported to the shed at harvest: the bound for delivery changes alone); 'deliv' = never before that unit reached
our shed (FIFO, midnight dump sellable from the next hour 0).
usage: mars_sell.py <arm> <out.json> [--workers 2] [--prods STRAWBERRY,WOOL,MILK]"""
import bisect
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODS = tuple(sys.argv[sys.argv.index('--prods') + 1].split(',')) if '--prods' in sys.argv else ('STRAWBERRY', 'WOOL', 'MILK')
PROF = json.load(open(ROOT / 'results/fresh/threads_20260928/dsm_hourly_profile.json'))
R = {'w': None, 'seat': 0, 't': 0, 'ev': None, 'hv': None}
_commit = E._commit_unit


def commit(op, item, price, farm, private, market, shed_capacity=100):
    inv = market['inventory'].get(item)
    r = _commit(op, item, price, farm, private, market, shed_capacity)
    w = R['w']
    if r and w is not None and item in PRODS and R['t'] >= 264 and op == 'SELL':
        R['ev'].append((R['t'], 'us' if farm is w.farms[R['seat']] else 'opp', item, float(price), inv))
    return r


_ua = E._apply_unit_action


def ua(farm, private, idx, action, *a, **k):
    w = R['w']
    if w is None or R['t'] < 264 or farm is not w.farms[R['seat']] or not (isinstance(action, list) and action and action[0] == 'HARVEST'):
        return _ua(farm, private, idx, action, *a, **k)
    ib = dict(E._farmer_inventory(private, idx))
    r = _ua(farm, private, idx, action, *a, **k)
    for kk, v in E._farmer_inventory(private, idx).items():
        if kk in PRODS and v - ib.get(kk, 0) > 0:
            R['hv'][kk] += [R['t']] * (v - ib.get(kk, 0))
    return r


E._commit_unit, E._apply_unit_action = commit, ua


def replay(tape, stream):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, ev=[], hv={p: [] for p in PRODS})
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
                    avail[p] += [264] * int(sh0.get(p, 0) or 0)
                    R['hv'][p] += [264] * (int(sh0.get(p, 0) or 0) + sum(int(inv.get(p, 0) or 0) for inv in w.private(seat)['inventories']))
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = a if isinstance(a, dict) and a else dict(UE.PASS)
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
        if t >= 264:
            sh1 = w.private(seat)['shed']
            for p in PRODS:
                sold = sum(1 for e in R['ev'][n_ev:] if e[1] == 'us' and e[2] == p)
                arr = int(sh1.get(p, 0) or 0) - int(sh0.get(p, 0) or 0) + sold
                if arr > 0:
                    avail[p] += [(t + 1) if t % 24 == 23 else t] * arr
    out = {'ev': list(R['ev']), 'stock': stock, 'avail': avail, 'hv': {p: sorted(v) for p, v in R['hv'].items()}, 'params': w.market.get('params'),
           'money': (w.farms[seat]['money'], w.farms[1 - seat]['money'])}
    R['w'] = None
    return out


def rule_times(p, lt, n):
    """sale time of our k-th unit (k < n) under the day / hourly rules, from the leader's sale times lt."""
    cum = Counter(t // 24 for t in lt)
    c = [0] * 31
    run = 0
    for d in range(31):
        run += cum.get(d, 0)
        c[d] = run
    day, hourly = [], []
    for k in range(n):
        need = k + 1
        d = next((d for d in range(11, 30) if c[d] >= need), None)
        day.append(d * 24 + 1 if d is not None else None)
        th = None
        for d in range(11, 30):
            if c[d] < need:
                continue
            prev = c[d - 1]
            for h in range(24):
                if int(prev + PROF[p][h] * (c[d] - prev)) >= need:
                    th = d * 24 + h
                    break
            if th is not None:
                break
        hourly.append(th)
    return day, hourly


def price_schedule(p, cf, at, ev_opp, stock, params):
    def delta(t):
        return bisect.bisect_left(cf, t) - bisect.bisect_left(at, t)
    riv = sum(E.market_price(p, e[4] + delta(e[0]), params) for e in ev_opp)
    ropp = Counter(e[0] for e in ev_opp)          # the rival's units of a step go first (our sells sit behind the hires)
    ours, same = 0.0, Counter()
    for t in cf:
        ours += E.market_price(p, stock.get(min(t, 718), 0) + delta(t) + ropp[t] + same[t], params)
        same[t] += 1
    return ours, riv


def job(args):
    g, arm = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    L = replay(tape, None)
    A = replay(tape, s['actions'])
    res = {'money': {'leader': L['money'], arm: A['money']}}
    for p in PRODS:
        lt = sorted(e[0] for e in L['ev'] if e[1] == 'us' and e[2] == p)
        ours = [e for e in A['ev'] if e[1] == 'us' and e[2] == p]
        riv = [e for e in A['ev'] if e[1] == 'opp' and e[2] == p]
        at = sorted(e[0] for e in ours)
        n, m = len(at), min(len(at), len(lt))
        stock = A['stock'][p]
        av = sorted(A['avail'][p])
        hv = A['hv'][p]
        r = {'our_act': sum(e[3] for e in ours), 'riv_act': sum(e[3] for e in riv), 'n': n, 'n_leader': len(lt),
             'leader_rev': sum(e[3] for e in L['ev'] if e[1] == 'us' and e[2] == p),
             'leader_riv': sum(e[3] for e in L['ev'] if e[1] == 'opp' and e[2] == p)}
        o, rv = price_schedule(p, at, at, riv, stock, A['params'])
        r['calib'] = (o, rv)
        dayr, hourr = rule_times(p, lt, m)
        rules = {'day': dayr, 'hourly': hourr, 'books': lt[:m]}
        for name, tt in rules.items():
            for mode in ('mars', 'harv', 'deliv'):
                cf = []
                for k in range(n):
                    if k < m and tt[k] is not None:
                        x = tt[k]
                        if mode == 'deliv':
                            x = max(x, av[k] if k < len(av) else at[k])
                        elif mode == 'harv':
                            x = max(x, hv[k] if k < len(hv) else at[k])
                        cf.append(min(x, 718))
                    else:
                        cf.append(at[k])
                cf.sort()
                r[f'{name}_{mode}'] = price_schedule(p, cf, at, riv, stock, A['params'])
        res[p] = r
    return ep, res


if __name__ == '__main__':
    arm, outp = sys.argv[1], sys.argv[2]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    res = {}
    with Pool(nw) as pool:
        for ep, r in pool.imap_unordered(job, [(g, arm) for g in games]):
            res[ep] = r
    json.dump(res, open(outp, 'w'))
    n = len(res)
    print(f'{n} worlds, {arm}, per world. Margin gap vs DSM on each product = (our revenue - DSM\'s) - (rival revenue in our '
          f'game - in DSM\'s game). Strategy rows: change vs our actual sales (ours, rival, MARGIN); nothing but sale times moves.')
    T = defaultdict(float)
    for p in PRODS:
        g_ = lambda f: sum(f(r[p]) for r in res.values()) / n
        gap = g_(lambda r: (r['our_act'] - r['leader_rev']) - (r['riv_act'] - r['leader_riv']))
        oa, ra = g_(lambda r: r['our_act']), g_(lambda r: r['riv_act'])
        co, cr = g_(lambda r: r['calib'][0]), g_(lambda r: r['calib'][1])
        T['gap'] += gap
        print(f'\n{p}: margin gap vs DSM {gap:+.0f} (our units {g_(lambda r: r["n"]):.0f} vs DSM {g_(lambda r: r["n_leader"]):.0f}); '
              f'calibration: actual schedule priced by the model ours {co - oa:+.0f}, rival {cr - ra:+.0f}')
        for name in ('day', 'hourly', 'books'):
            for mode in ('mars', 'harv', 'deliv'):
                k = f'{name}_{mode}'
                do = g_(lambda r: r[k][0]) - co
                dr = g_(lambda r: r[k][1]) - cr
                T[k] += do - dr
                print(f'  {name:6s} {mode:5s}  ours {do:+7.0f}  rival {dr:+7.0f}  MARGIN {do - dr:+7.0f}  ({(do - dr) / -gap * 100 if gap < 0 else 0:5.1f}% of the gap)')
    print(f'\nTOTAL gap {T["gap"]:+.0f}; recovered: ' + ', '.join(f'{k} {v:+.0f}' for k, v in T.items() if k != 'gap'))

"""Market timing counterfactual: keep our units, move them onto the leader's sale times, recompute prices.

Shop consumption is a fixed schedule (engine _town_consume), so the market stock of a product at any moment is the
start stock + all units sold so far by both players - units bought - the fixed consumption, and the price is a fixed
function of that stock (market_price). Replaying our game gives the actual stock path; moving our k-th sold unit to
the leader's k-th sale time shifts the stock by delta(t) = (our units sold by t under the leader's timing) - (actual
ones), for every later moment. Rival revenue and ours are recomputed from the shifted stock (per unit, at the stock it
sold into, within-hour order kept as in the actual game).
usage: timing_counterfactual.py <arm> <timing json of that arm (season_timing.py)> <out.json> [--workers 2]"""
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
    stock = {p: {} for p in PRODS}                    # market stock at the start of every step (before its market)
    while w.t < 719:
        t = w.t
        R['t'] = t
        if t >= 264:
            for p in PRODS:
                stock[p][t] = w.market['inventory'][p]
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if t < len(s) and isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    params = w.market.get('params')
    out = {}
    for p in PRODS:
        ev = [e for e in R['ev'] if e[3] == p]
        ours = [e for e in ev if e[1] == 'us' and e[2] == 'SELL']
        riv = [e for e in ev if e[1] == 'opp' and e[2] == 'SELL']
        a_times = sorted(e[0] for e in ours)
        l_times = sorted(leader_times.get(p, []))
        m = min(len(a_times), len(l_times))
        cf_times = sorted(l_times[:m] + a_times[m:])     # our units beyond the leader's count keep their times

        def delta(t):                                    # stock shift at the start of step t (sales before t)
            return bisect.bisect_left(cf_times, t) - bisect.bisect_left(a_times, t)

        rv_act = sum(e[4] for e in riv)
        rv_cf = sum(E.market_price(p, e[5] + delta(e[0]), params) for e in riv)
        our_act = sum(e[4] for e in ours)
        # our cf units: sold at the leader's times into the shifted stock; the stock just before our unit at time t
        # in the cf world ~ the actual stock at the start of t (last event before t) + delta(t) + our earlier cf units
        # at the same t
        our_cf = 0.0
        same_t = defaultdict(int)
        for t in cf_times:                               # the actual stock at the start of step t, shifted
            base = stock[p].get(t, stock[p].get(718, 0))
            our_cf += E.market_price(p, base + delta(t) + same_t[t], params)
            same_t[t] += 1
        out[p] = {'units': len(ours), 'leader_units': len(l_times), 'riv_units': len(riv),
                  'rival_act': rv_act, 'rival_cf': rv_cf, 'our_act': our_act, 'our_cf': our_cf,
                  'lags': [a - b for a, b in zip(a_times[:m], l_times[:m])]}
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
        C = T[ep]['leader']['C']
        lt = defaultdict(list)
        for k, v in C.items():
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
    print(f'{n} worlds, per world: our units moved onto the leader\'s sale times (same units), prices from the shifted stock')
    tot = defaultdict(float)
    for p in PRODS:
        ra = sum(r[p]['rival_act'] for r in res.values()) / n
        rc = sum(r[p]['rival_cf'] for r in res.values()) / n
        oa = sum(r[p]['our_act'] for r in res.values()) / n
        oc = sum(r[p]['our_cf'] for r in res.values()) / n
        lags = sorted(x for r in res.values() for x in r[p]['lags'])
        lag = lags[len(lags) // 2] if lags else 0
        tot['r'] += rc - ra
        tot['o'] += oc - oa
        print('  %-10s median lag %+4d h | rival revenue %8.0f -> %8.0f (%+6.0f) | our revenue %8.0f -> %8.0f (%+6.0f) | margin %+6.0f' % (
            p, lag, ra, rc, rc - ra, oa, oc, oc - oa, (oc - oa) - (rc - ra)))
    print('  TOTAL rival %+.0f, ours %+.0f, margin %+.0f' % (tot['r'], tot['o'], tot['o'] - tot['r']))

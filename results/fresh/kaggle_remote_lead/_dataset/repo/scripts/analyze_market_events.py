"""Market-mechanism analysis over event logs from scripts/extract_market_events.py (2026-09-24).

Pairs each world's LEADER log with an agent log (our agent in the leader's seat; the rival replays its recorded
actions in both). The market of one product is fully determined by the units sold / bought and by town consumption,
which is fixed by the (forced) shops, so every unit's price can be recomputed exactly from the event positions
(step, order index, lockstep iteration). `simulate` does that and is validated against the logged prices; the
cross-world swaps and counterfactual sale schedules below use it.

usage: analyze_market_events.py [agent_dir=results/fresh/market_events_20260924/mgt_y3]
                                [leader_dir=results/fresh/market_events_20260924/LEADER] [collapse=0.8]
"""
import gzip
import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from kaggle_environments.envs.kaggriculture.kaggriculture import market_price, PRODUCTS  # noqa: E402

ITEMS = ['STRAWBERRY', 'MILK', 'WOOL', 'MELON']
ALL_ITEMS = [p for p in PRODUCTS]
PIDX = {p: i for i, p in enumerate(PRODUCTS)}
I0 = 10000


def load(path):
    return json.load(gzip.open(path, 'rt', encoding='utf-8'))


def pairs(agent_dir, leader_dir, collapse=0.8):
    out, dropped = [], []
    for f in sorted(Path(agent_dir).glob('*.json.gz')):
        lf = Path(leader_dir) / f.name
        if not lf.exists():
            continue
        a, l = load(f), load(lf)
        s = l['meta']['seat']
        if not l['meta']['cash_match']:
            dropped.append((f.name, 'leader replay cash mismatch'))
            continue
        ra, rl = a['meta']['final_cash'][1 - s], l['meta']['final_cash'][1 - s]
        if ra < collapse * rl:
            dropped.append((f.name, f'rival collapsed {ra:.0f} vs {rl:.0f}'))
            continue
        out.append((f.name.split('.')[0], l, a))
    return out, dropped


# ---------------------------------------------------------------- market reconstruction
def consumption(g, item):
    """Town consumption of `item` per step: inv_pre + net market change - inv_post."""
    k = PIDX[item]
    n = len(g['steps'])
    net = [0] * n
    for t, oi, it, p, op, itm, price, invb in g['tx']:
        if itm != item:
            continue
        if op == 'SELL' and price > 1:
            net[t] += 1
        elif op == 'BUY_PRODUCT':
            net[t] -= 1
    return [g['steps'][t]['inv_pre'][k] + net[t] - g['steps'][t]['inv_post'][k] for t in range(n)]


def sell_events(g, item, player):
    """[(step, oi, k)] of the player's successful SELL units of item, in execution order."""
    return [(t, oi, it) for t, oi, it, p, op, itm, price, invb in g['tx'] if p == player and op == 'SELL' and itm == item]


def buy_events(g, item, player):
    return [(t, oi, it) for t, oi, it, p, op, itm, price, invb in g['tx'] if p == player and op == 'BUY_PRODUCT' and itm == item]


def simulate(item, ev0, ev1, cons, buys=()):
    """Exact re-pricing of one product. ev0/ev1: [(step, oi, k)] SELL units of player 0/1; buys: [(step, oi, k, player)]
    BUY_PRODUCT units (wheat/fertilizer). Units with the same (step, oi, k) are quoted from the same inventory
    (engine lockstep), player 0 commits first. Town consumption is applied after each step's market phase.
    Returns (prices0, prices1) aligned with ev0/ev1."""
    by_step = defaultdict(list)
    for j, (t, oi, k) in enumerate(ev0):
        by_step[t].append((oi, k, 0, j, 'S'))
    for j, (t, oi, k) in enumerate(ev1):
        by_step[t].append((oi, k, 1, j, 'S'))
    for j, (t, oi, k, p) in enumerate(buys):
        by_step[t].append((oi, k, p, j, 'B'))
    prices = [[None] * len(ev0), [None] * len(ev1)]
    inv = I0
    for t in range(len(cons)):
        evs = sorted(by_step.get(t, ()))
        i = 0
        while i < len(evs):
            oi, k = evs[i][0], evs[i][1]
            grp = []
            while i < len(evs) and evs[i][0] == oi and evs[i][1] == k:
                grp.append(evs[i]); i += 1
            q_sell = market_price(item, inv)
            q_buy = market_price(item, inv - 1)
            for _, _, p, j, kind in grp:
                if kind == 'S':
                    prices[p][j] = q_sell
                    if q_sell > 1:
                        inv += 1
                else:
                    inv -= 1
        inv -= cons[t]
    return prices


def logged_prices(g, item, player):
    return [price for t, oi, it, p, op, itm, price, invb in g['tx'] if p == player and op == 'SELL' and itm == item]


def validate(g, item):
    cons = consumption(g, item)
    ev = [sell_events(g, item, 0), sell_events(g, item, 1)]
    buys = [(t, oi, k, p) for p in (0, 1) for (t, oi, k) in buy_events(g, item, p)]
    pr = simulate(item, ev[0], ev[1], cons, buys)
    return pr[0] == logged_prices(g, item, 0) and pr[1] == logged_prices(g, item, 1)


# ---------------------------------------------------------------- per-world helpers
def arrivals(g, item, player):
    """Units entering the player's shed per step (between the previous market phase and this one)."""
    k = PIDX[item]
    n = len(g['steps'])
    sold = Counter(t for t, oi, it, p, op, itm, price, invb in g['tx'] if p == player and op == 'SELL' and itm == item)
    arr = [0] * n
    prev = 0
    for t in range(n):
        cur = g['steps'][t]['shed'][player][k]
        arr[t] = max(0, cur - prev)
        prev = cur - sold.get(t, 0)
    return arr


def asap_schedule(g, item, player, oi=0):
    """Sell every unit at the first market phase after it enters the shed (order index oi)."""
    arr = arrivals(g, item, player)
    ev = []
    for t, a in enumerate(arr):
        for k in range(a):
            ev.append((t, oi, k))
    return ev


WINDOWS = [('same step', 0, 0), ('1-3 steps before', 1, 3), ('4-23 steps before', 4, 23), ('1-2 days before', 24, 71),
           ('>=3 days before', 72, 10 ** 6)]


def before_counts(riv_ev, own_ev):
    """For each rival unit, how many of our units executed before it, split by window (steps back).
    Same step: our units with (oi, k) < rival's (oi, k), or equal (oi, k) and our seat is 0 (commits first but was
    quoted from the same inventory -> does NOT affect this rival unit's price). So same-step counts only units with a
    strictly earlier (oi, k)."""
    own_by_step = defaultdict(list)
    for t, oi, k in own_ev:
        own_by_step[t].append((oi, k))
    steps_sorted = sorted(own_by_step)
    cum = {}
    c = 0
    for t in steps_sorted:
        c += len(own_by_step[t])
        cum[t] = c
    import bisect

    def cum_upto(t):              # our units in steps <= t
        i = bisect.bisect_right(steps_sorted, t)
        return cum[steps_sorted[i - 1]] if i else 0

    out = []
    for t, oi, k in riv_ev:
        row = []
        same = sum(1 for (o2, k2) in own_by_step.get(t, ()) if (o2, k2) < (oi, k))
        for name, lo, hi in WINDOWS:
            if lo == 0:
                row.append(same)
            else:
                row.append(cum_upto(t - lo) - cum_upto(t - hi - 1))
        out.append(row)
    return out


def rev(prices):
    return sum(prices)


def simulate_inv(item, ev0, ev1, cons):
    """Like simulate (sells only) but returns, per player, (price, inventory_before) per unit."""
    by_step = defaultdict(list)
    for j, (t, oi, k) in enumerate(ev0):
        by_step[t].append((oi, k, 0, j))
    for j, (t, oi, k) in enumerate(ev1):
        by_step[t].append((oi, k, 1, j))
    out = [[None] * len(ev0), [None] * len(ev1)]
    inv = I0
    for t in range(len(cons)):
        evs = sorted(by_step.get(t, ()))
        i = 0
        while i < len(evs):
            oi, k = evs[i][0], evs[i][1]
            grp = []
            while i < len(evs) and evs[i][0] == oi and evs[i][1] == k:
                grp.append(evs[i]); i += 1
            q = market_price(item, inv)
            inv0 = inv
            for _, _, p, j in grp:
                out[p][j] = (q, inv0)
                if q > 1:
                    inv += 1
        inv -= cons[t]
    return out


def two(riv, own, r):
    ev = [None, None]
    ev[r], ev[1 - r] = riv, own
    return ev


def cum_curve(ev_steps, n=719):
    c = [0] * (n + 1)
    for t in ev_steps:
        c[t + 1] += 1
    for t in range(n):
        c[t + 1] += c[t]
    return c          # c[t] = units strictly before step t


def world_item(L, Y, item):
    """Everything for one world x product. Leader seat s, rival r."""
    s = L['meta']['seat']; r = 1 - s
    cons = consumption(L, item)
    assert cons == consumption(Y, item), 'consumption differs between worlds'
    rl, ry = sell_events(L, item, r), sell_events(Y, item, r)
    ol, oy = sell_events(L, item, s), sell_events(Y, item, s)
    base = simulate_inv(item, *two(rl, ol, r), cons)            # = logged L world
    swap = simulate_inv(item, *two(rl, oy, r), cons)            # rival's L schedule, our Y schedule
    yw = simulate_inv(item, *two(ry, oy, r), cons)              # = logged Y world
    asap = asap_schedule(Y, item, s, oi=0)
    swap_asap = simulate_inv(item, *two(rl, asap, r), cons)
    res = dict(
        riv_units=(len(rl), len(ry)), own_units=(len(ol), len(oy)),
        riv_rev_L=sum(p for p, _ in base[r]), riv_rev_Y=sum(p for p, _ in yw[r]), riv_rev_swap=sum(p for p, _ in swap[r]),
        own_rev_L=sum(p for p, _ in base[s]), own_rev_Y=sum(p for p, _ in yw[s]),
    )
    # decomposition of the our-schedule effect (rival's L schedule fixed). For each rival unit u the inventory it is
    # priced from differs between the two simulations by  d_inv(u) = dA - dH - dF + dRf, where (counts of OUR units
    # before u) A = arrived in our shed, H = arrived but still held, F = sold at the $1 floor (a floor sale does not
    # add to inventory), and dRf = change in the rival's OWN floor units before u. The price change dp(u) is allocated
    # to these parts in proportion (exact, one secant per unit). Windows use only our inventory-moving units.
    eff_L = [ev for ev, (pr, _) in zip(ol, base[s]) if pr > 1]
    eff_S = [ev for ev, (pr, _) in zip(oy, swap[s]) if pr > 1]
    flo_L = [ev for ev, (pr, _) in zip(ol, base[s]) if pr <= 1]
    flo_S = [ev for ev, (pr, _) in zip(oy, swap[s]) if pr <= 1]
    rfl_L = [ev for ev, (pr, _) in zip(rl, base[r]) if pr <= 1]
    rfl_S = [ev for ev, (pr, _) in zip(rl, swap[r]) if pr <= 1]
    bl, by = before_counts(rl, eff_L), before_counts(rl, eff_S)
    tot_L, tot_S = before_counts(rl, ol), before_counts(rl, oy)
    fL, fS = before_counts(rl, flo_L), before_counts(rl, flo_S)
    rfL, rfS = before_counts(rl, rfl_L), before_counts(rl, rfl_S)
    arrL, arrY = arrivals(L, item, s), arrivals(Y, item, s)
    cumA_L = cum_curve([t for t, a in enumerate(arrL) for _ in range(a)])
    cumA_Y = cum_curve([t for t, a in enumerate(arrY) for _ in range(a)])
    win = [0.0] * len(WINDOWS)
    parts = defaultdict(float)
    resid = 0.0
    dO_sum = 0
    for j, (t, oi, k) in enumerate(rl):
        pL, invL = base[r][j]; pS, invS = swap[r][j]
        dp = pS - pL
        dinv = invS - invL
        dOe = [by[j][w] - bl[j][w] for w in range(len(WINDOWS))]
        dO_sum += sum(tot_S[j]) - sum(tot_L[j])
        # our units sold before u (all prices) and arrivals up to and including step t
        dA = cumA_Y[t + 1] - cumA_L[t + 1]
        dH = dA - (sum(tot_S[j]) - sum(tot_L[j]))
        dF = sum(fS[j]) - sum(fL[j])
        dRf = -(sum(rfS[j]) - sum(rfL[j]))          # rival floor units do not add either
        comp = {'production': dA, 'holding': -dH, 'floor': -dF, 'rival_floor': dRf}
        tot = sum(comp.values())
        if dinv != tot and dp != 0:
            parts['unexplained'] += dp               # should not happen (checked)
            continue
        if tot == 0:
            resid += dp
            continue
        for c, v in comp.items():
            parts[c] += dp * v / tot
        se = sum(dOe)
        if se:
            for w in range(len(WINDOWS)):
                win[w] += dp * (dOe[w] / se) * ((tot - dRf) / tot)
    prod_part, hold_part = parts['production'], parts['holding']
    def stock_stats(sim, who):
        inv = [iv - I0 for _, iv in sim[who]]
        slope = [market_price(item, iv) - market_price(item, iv + 1) for _, iv in sim[who]]
        m = max(1, len(inv))
        return sum(inv) / m, sum(slope) / m
    res['stock_riv_L'], res['slope_riv_L'] = stock_stats(base, r)
    res['stock_riv_Y'], res['slope_riv_Y'] = stock_stats(yw, r)
    res['stock_own_L'], res['slope_own_L'] = stock_stats(base, s)
    res['stock_own_Y'], res['slope_own_Y'] = stock_stats(yw, s)
    res['cons_per_day_late'] = sum(cons[480:719]) / 10.0      # days 20-29
    res.update(floor_part=parts['floor'], rival_floor_part=parts['rival_floor'], unexplained=parts['unexplained'],
               floor_units_L=len(flo_L), floor_units_S=len(flo_S))
    res.update(win=win, resid=resid, prod_part=prod_part, hold_part=hold_part,
               mean_dO=dO_sum / max(1, len(rl)),
               riv_rev_swap_asap=sum(p for p, _ in swap_asap[r]), own_rev_swap_asap=sum(p for p, _ in swap_asap[s]),
               own_rev_swap=sum(p for p, _ in swap[s]))
    # timing descriptors
    def desc(g, ev, riv_ev, p):
        arr = arrivals(g, item, p)
        # FIFO holding time (steps from shed arrival to sale)
        q = []
        for t, a in enumerate(arr):
            q += [t] * a
        hold = [ev[i][0] - q[i] for i in range(min(len(ev), len(q)))]
        riv_steps = Counter(t for t, _, _ in riv_ev)
        riv_days = set(t // 24 for t, _, _ in riv_ev)
        sell_steps = Counter(t for t, _, _ in ev)
        same_step = sum(n for t, n in sell_steps.items() if t in riv_steps)
        same_day = sum(n for t, n in sell_steps.items() if t // 24 in riv_days)
        first_arr = next((t for t, a in enumerate(arr) if a), None)
        # within-step order in collision steps: our units ahead of (strictly lower order index), interleaved with
        # (same index) or behind every rival unit of the product in that step
        riv_oi = defaultdict(list)
        for t, oi, k in riv_ev:
            riv_oi[t].append(oi)
        ahead = inter = behind = 0
        for t, oi, k in ev:
            if t in riv_oi:
                lo, hi = min(riv_oi[t]), max(riv_oi[t])
                if oi < lo:
                    ahead += 1
                elif oi > hi:
                    behind += 1
                else:
                    inter += 1
        coll = max(1, ahead + inter + behind)
        return dict(ahead=ahead / coll, inter=inter / coll, behind=behind / coll, units=len(ev), hold_mean=(sum(hold) / len(hold)) if hold else 0.0,
                    hold_le1=sum(1 for h in hold if h <= 1) / max(1, len(hold)),
                    lot=len(ev) / max(1, len(sell_steps)), same_step=same_step / max(1, len(ev)),
                    same_day=same_day / max(1, len(ev)), first_arrival_day=None if first_arr is None else first_arr // 24,
                    mean_sale_step=sum(t for t, _, _ in ev) / max(1, len(ev)),
                    hours=Counter(t % 24 for t, _, _ in ev))
    res['desc_L'] = desc(L, ol, rl, s)
    res['desc_Y'] = desc(Y, oy, ry, s)
    res['desc_R'] = desc(L, rl, ol, r)
    return res


# ---------------------------------------------------------------- counterfactual sale schedules for OUR agent
def sched_from_arrivals(arr, pick, oi=0):
    """pick(t_arrival) -> sale step (>= arrival). Returns [(step, oi, k)] with k numbered per step."""
    per = Counter()
    for t, a in enumerate(arr):
        if a:
            per[min(718, pick(t))] += a
    ev = []
    for t in sorted(per):
        for k in range(per[t]):
            ev.append((t, oi, k))
    return ev


def rules_for(Y, item):
    s = Y['meta']['seat']; r = 1 - s
    arr = arrivals(Y, item, s)
    riv = sell_events(Y, item, r)
    riv_steps = sorted(set(t for t, _, _ in riv))
    import bisect

    def next_riv(t, horizon):
        i = bisect.bisect_left(riv_steps, t)
        if i < len(riv_steps) and riv_steps[i] - t <= horizon:
            return riv_steps[i]
        return t

    def riv_oi(t):
        ois = [oi for tt, oi, k in riv if tt == t]
        return min(ois) if ois else 0

    rules = {
        'asap_first': sched_from_arrivals(arr, lambda t: t, oi=0),
        'asap_last': sched_from_arrivals(arr, lambda t: t, oi=10),
        'tick_aligned': sched_from_arrivals(arr, lambda t: t + ((1 - t) % 4), oi=0),
        'daily_h1': sched_from_arrivals(arr, lambda t: (t // 24) * 24 + 1 if t % 24 <= 1 else (t // 24 + 1) * 24 + 1, oi=0),
        'oracle_front_run_24h': sched_from_arrivals(arr, lambda t: next_riv(t, 24), oi=0),
        'hold_1day': sched_from_arrivals(arr, lambda t: t + 24, oi=0),
    }
    return rules


def eval_rules(Y, item):
    s = Y['meta']['seat']; r = 1 - s
    cons = consumption(Y, item)
    riv = sell_events(Y, item, r)
    own = sell_events(Y, item, s)
    base = simulate_inv(item, *two(riv, own, r), cons)
    b_own, b_riv = sum(p for p, _ in base[s]), sum(p for p, _ in base[r])
    out = {}
    for name, ev in rules_for(Y, item).items():
        # the rival's order indices are kept; ours use `oi` (0 = ahead of any rival order in the step, 10 = behind)
        x = simulate_inv(item, *two(riv, ev, r), cons)
        o, rv = sum(p for p, _ in x[s]), sum(p for p, _ in x[r])
        out[name] = (o - b_own, rv - b_riv, len(ev) - len(own))
    return out


def shift_calendar(Y, L, item, days):
    """Production-calendar counterfactual: y3's own sale schedule moved `days` earlier (same units, same hours),
    rival's Y schedule fixed. Returns (d_own, d_riv)."""
    s = Y['meta']['seat']; r = 1 - s
    cons = consumption(Y, item)
    riv = sell_events(Y, item, r)
    own = sell_events(Y, item, s)
    base = simulate_inv(item, *two(riv, own, r), cons)
    moved = sorted((max(0, t - 24 * days), oi, k) for t, oi, k in own)
    x = simulate_inv(item, *two(riv, moved, r), cons)
    return (sum(p for p, _ in x[s]) - sum(p for p, _ in base[s]), sum(p for p, _ in x[r]) - sum(p for p, _ in base[r]))


def leader_calendar(Y, L, item):
    """Our (y3) units re-timed onto the LEADER's sale calendar by quantile (unit i of n_y takes the step of the
    leader's unit floor(i*n_l/n_y)), rival's Y schedule fixed. Market-only value of the leader's calendar at y3's volume."""
    s = Y['meta']['seat']; r = 1 - s
    cons = consumption(Y, item)
    riv = sell_events(Y, item, r)
    own = sell_events(Y, item, s)
    lead = sell_events(L, item, s)
    base = simulate_inv(item, *two(riv, own, r), cons)
    if not lead or not own:
        return (0, 0)
    steps = sorted(lead[int(i * len(lead) / len(own))][0] for i in range(len(own)))
    per = Counter(steps)
    ev = [(t, 0, k) for t in sorted(per) for k in range(per[t])]
    x = simulate_inv(item, *two(riv, ev, r), cons)
    return (sum(p for p, _ in x[s]) - sum(p for p, _ in base[s]), sum(p for p, _ in x[r]) - sum(p for p, _ in base[r]))


def main():
    agent_dir = sys.argv[1] if len(sys.argv) > 1 else 'results/fresh/market_events_20260924/mgt_y3'
    leader_dir = sys.argv[2] if len(sys.argv) > 2 else 'results/fresh/market_events_20260924/LEADER'
    collapse = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
    items = ITEMS + ['EGG', 'TOMATO', 'CARROT', 'WHEAT']
    ps, dropped = pairs(agent_dir, leader_dir, collapse)
    print(f'{len(ps)} intact worlds; dropped {dropped}')
    bad = [(ep, it) for ep, L, Y in ps for it in ALL_ITEMS for g in (L, Y) if not validate(g, it)]
    print('re-pricing validation failures:', bad)
    summary = {'worlds': [ep for ep, _, _ in ps], 'dropped': dropped, 'items': {}}
    n = len(ps)
    for item in items:
        acc = defaultdict(float)
        rules = defaultdict(lambda: [0.0, 0.0])
        desc = {k: defaultdict(float) for k in ('desc_L', 'desc_Y', 'desc_R')}
        first = {k: [] for k in ('desc_L', 'desc_Y', 'desc_R')}
        hours = {k: Counter() for k in ('desc_L', 'desc_Y', 'desc_R')}
        per_world = []
        for ep, L, Y in ps:
            x = world_item(L, Y, item)
            acc['riv_obs'] += x['riv_rev_Y'] - x['riv_rev_L']
            acc['riv_ours'] += x['riv_rev_swap'] - x['riv_rev_L']
            acc['riv_theirs'] += x['riv_rev_Y'] - x['riv_rev_swap']
            acc['own_obs'] += x['own_rev_Y'] - x['own_rev_L']
            acc['riv_units'] += x['riv_units'][1] - x['riv_units'][0]
            acc['own_units'] += x['own_units'][1] - x['own_units'][0]
            acc['riv_units_L'] += x['riv_units'][0]
            for w in range(len(WINDOWS)):
                acc['win%d' % w] += x['win'][w]
            acc['resid'] += x['resid']
            acc['prod'] += x['prod_part']
            acc['hold'] += x['hold_part']
            acc['floor'] += x['floor_part']
            acc['rfloor'] += x['rival_floor_part']
            acc['unexpl'] += x['unexplained']
            acc['flo_L'] += x['floor_units_L']
            acc['flo_S'] += x['floor_units_S']
            acc['mean_dO'] += x['mean_dO']
            for f in ('stock_riv_L', 'slope_riv_L', 'stock_riv_Y', 'slope_riv_Y', 'stock_own_L', 'slope_own_L',
                      'stock_own_Y', 'slope_own_Y', 'cons_per_day_late'):
                acc[f] += x[f]
            acc['comb_obs'] += (x['riv_rev_Y'] + x['own_rev_Y']) - (x['riv_rev_L'] + x['own_rev_L'])
            for k in desc:
                for f in ('units', 'hold_mean', 'hold_le1', 'lot', 'same_step', 'same_day', 'mean_sale_step', 'ahead', 'inter', 'behind'):
                    desc[k][f] += x[k][f]
                if x[k]['first_arrival_day'] is not None:
                    first[k].append(x[k]['first_arrival_day'])
                hours[k].update(x[k]['hours'])
            if item != 'WHEAT':        # wheat arrivals include bought feed wheat; timing rules are meaningless there
                for name, (do, dr, du) in eval_rules(Y, item).items():
                    rules[name][0] += do; rules[name][1] += dr
                lc = leader_calendar(Y, L, item)
                rules['leader_calendar'][0] += lc[0]; rules['leader_calendar'][1] += lc[1]
                for dd in (1, 2, 3):
                    sc = shift_calendar(Y, L, item, dd)
                    rules[f'calendar_{dd}d_earlier'][0] += sc[0]; rules[f'calendar_{dd}d_earlier'][1] += sc[1]
            per_world.append(dict(ep=ep, riv=x['riv_rev_Y'] - x['riv_rev_L'], ours=x['riv_rev_swap'] - x['riv_rev_L'],
                                  own=x['own_rev_Y'] - x['own_rev_L'], prod=x['prod_part'], hold=x['hold_part'],
                                  win=[round(v) for v in x['win']], first=(x['desc_L']['first_arrival_day'], x['desc_Y']['first_arrival_day'], x['desc_R']['first_arrival_day'])))
        m = {k: v / n for k, v in acc.items()}
        print(f'\n=== {item}  (per world, y3 world minus leader world; {n} worlds)')
        print(f"rival revenue {m['riv_obs']:+.0f} = our schedule {m['riv_ours']:+.0f} + rival's own schedule {m['riv_theirs']:+.0f};"
              f" rival units {m['riv_units']:+.1f} (L {m['riv_units_L']:.0f}); our revenue {m['own_obs']:+.0f}, our units {m['own_units']:+.1f}")
        print('our-schedule effect by when our units were sold before each rival unit: ' +
              ', '.join(f"{WINDOWS[w][0]} {m['win%d' % w]:+.0f}" for w in range(len(WINDOWS))) + f", no-count residual {m['resid']:+.0f}")
        print(f"  = production calendar (units not yet arrived) {m['prod']:+.0f} + holding (arrived, in shed) {m['hold']:+.0f}"
              f" + our $1-floor sales {m['floor']:+.0f} + rival's own floor sales {m['rfloor']:+.0f} (unexplained {m['unexpl']:+.0f});"
              f" our floor units per world leader {m['flo_L']:.1f} y3 {m['flo_S']:.1f};"
              f" mean change in our units sold before a rival unit {m['mean_dO']:+.1f}")
        print(f"  market stock vs I0 (price slope $/unit) at the rival's sales: leader world {m['stock_riv_L']:+.0f} ({m['slope_riv_L']:.2f}),"
              f" y3 world {m['stock_riv_Y']:+.0f} ({m['slope_riv_Y']:.2f}); at our sales: leader {m['stock_own_L']:+.0f} ({m['slope_own_L']:.2f}),"
              f" y3 {m['stock_own_Y']:+.0f} ({m['slope_own_Y']:.2f}); town consumption days 20-29 {m['cons_per_day_late']:.1f}/day;"
              f" combined (ours+rival) revenue {m['comb_obs']:+.0f}")
        for k, lab in (('desc_L', 'leader'), ('desc_Y', 'y3'), ('desc_R', 'rival(L)')):
            d = {f: v / n for f, v in desc[k].items()}
            fa = sorted(first[k])
            tot_h = sum(hours[k].values()) or 1
            top = ', '.join(f'h{h}:{c / tot_h:.0%}' for h, c in hours[k].most_common(4))
            print(f"  {lab:8s} units {d['units']:.0f}  first arrival day median {fa[len(fa) // 2] if fa else None}  mean sale day {d['mean_sale_step'] / 24:.1f}"
                  f"  FIFO hold {d['hold_mean']:.1f} steps ({d['hold_le1']:.0%} <=1)  lot {d['lot']:.1f}  same-step-as-other {d['same_step']:.0%}"
                  f" (ahead/interleaved/behind {d['ahead']:.0%}/{d['inter']:.0%}/{d['behind']:.0%})  same-day {d['same_day']:.0%}  top hours {top}")
        print('  our sale-timing rules (market replay, y3 production & rival fixed): ' +
              '; '.join(f'{name} own {v[0] / n:+.0f} rival {v[1] / n:+.0f} margin {(v[0] - v[1]) / n:+.0f}' for name, v in rules.items()))
        summary['items'][item] = dict(mean={k: round(v, 1) for k, v in m.items()},
                                      rules={k: [round(v[0] / n, 1), round(v[1] / n, 1)] for k, v in rules.items()},
                                      first_arrival={k: first[k] for k in first}, per_world=per_world)
    out = Path(agent_dir).parent / f'summary_{Path(agent_dir).name}.json'
    out.write_text(json.dumps(summary, indent=1), encoding='utf-8')
    print('\nwrote', out)




# ---------------------------------------------------------------- deliberate or incidental?
def reaction_stats(g, item, player):
    """Steps where `player` holds the item in its shed at market start. For each observable rival signal (as the
    player sees it when deciding step t: state after step t-1), count sells / opportunities with and without it.
    Signals: rival_harvested = rival's public on-board yield of the item fell at t-1 (it just harvested);
    rival_sold_prev = rival sold the item at t-1 (visible as an unexplained inventory rise); rival_ripe = rival has
    harvestable yield of the item on board. Also: rival sells in t+1..t+3 (NOT observable; front-running check)."""
    k = PIDX[item]
    r = 1 - player
    st = g['steps']
    n = len(st)
    sold = Counter(t for t, oi, it, p, op, itm, price, invb in g['tx'] if p == player and op == 'SELL' and itm == item)
    rsold = Counter(t for t, oi, it, p, op, itm, price, invb in g['tx'] if p == r and op == 'SELL' and itm == item)
    rharv = Counter(t for t, p, prod, u in g['harvest'] if p == r and prod == item)
    oharv = Counter(t for t, p, prod, u in g['harvest'] if p == player and prod == item)
    arr = arrivals(g, item, player)
    c = defaultdict(lambda: [0, 0])     # signal -> [sells, opportunities]
    for t in range(2, n - 3):
        if st[t]['shed'][player][k] <= 0:
            continue
        y = 1 if sold.get(t) else 0
        sig = {
            'rival_harvested(t-1)': rharv.get(t - 1, 0) > 0,
            'rival_sold(t-1)': rsold.get(t - 1, 0) > 0,
            'rival_ripe(t-1)': st[t - 1]['tile'][r][k] > 0,
            'rival_sells_next_3 (unobservable)': any(rsold.get(t + d, 0) for d in (1, 2, 3)),
            'post_tick (t%4==1)': t % 4 == 1,
        }
        # stratified: rival just harvested, split by whether OUR stock just arrived (own calendar coincidence)
        fresh = arr[t] > 0 or arr[t - 1] > 0
        sig['rival_harvested(t-1) | own stock fresh'] = (rharv.get(t - 1, 0) > 0) if fresh else None
        sig['rival_harvested(t-1) | own stock old'] = (rharv.get(t - 1, 0) > 0) if not fresh else None
        sig = {k: v for k, v in sig.items() if v is not None}
        for name, v in sig.items():
            c[(name, v)][0] += y
            c[(name, v)][1] += 1
    return c


def reaction_main(ps):
    for item in ITEMS:
        print(f'\n--- {item}: P(sell this step | holding stock) with / without each rival signal')
        for who, idx in (('leader', 1), ('y3', 2)):
            tot = defaultdict(lambda: [0, 0])
            for row in ps:
                g = row[idx]
                s = row[1]['meta']['seat']
                for key, (a, b) in reaction_stats(g, item, s).items():
                    tot[key][0] += a; tot[key][1] += b
            names = sorted({k[0] for k in tot})
            parts = []
            for nm in names:
                a1, b1 = tot[(nm, True)]; a0, b0 = tot[(nm, False)]
                p1, p0 = (a1 / b1 if b1 else float('nan')), (a0 / b0 if b0 else float('nan'))
                parts.append(f'{nm}: {p1:.2f} vs {p0:.2f} (lift x{p1 / p0 if p0 else float("nan"):.2f}, n={b1})')
            print(f'  {who:6s} ' + ' | '.join(parts))


if __name__ == '__main__':
    main()
    if '--reaction' in sys.argv or True:
        ps, _ = pairs(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else 'results/fresh/market_events_20260924/mgt_y3',
                      'results/fresh/market_events_20260924/LEADER')
        reaction_main(ps)


def paths(ps, item, days=range(8, 30)):
    """Mean over worlds, by day: cumulative units sold before the day starts (leader in L, y3 in Y, rival in L), market stock minus I0 at
    the day's start and the day's mean rival sale price, in both worlds."""
    k = PIDX[item]
    n = len(ps)
    rows = []
    for d in days:
        acc = defaultdict(float)
        cnt = defaultdict(int)
        for ep, L, Y in ps:
            s = L['meta']['seat']; r = 1 - s
            acc['cumL'] += sum(1 for t, *_ in sell_events(L, item, s) if t < 24 * d)
            acc['cumY'] += sum(1 for t, *_ in sell_events(Y, item, s) if t < 24 * d)
            acc['cumR'] += sum(1 for t, *_ in sell_events(L, item, r) if t < 24 * d)
            acc['stockL'] += L['steps'][24 * d]['inv_pre'][k] - I0
            acc['stockY'] += Y['steps'][24 * d]['inv_pre'][k] - I0
            for tag, g in (('pL', L), ('pY', Y)):
                pr = [price for t, oi, it, p, op, itm, price, invb in g['tx'] if p == r and op == 'SELL' and itm == item and t // 24 == d]
                if pr:
                    acc[tag] += sum(pr) / len(pr); cnt[tag] += 1
        rows.append((d, acc['cumL'] / n, acc['cumY'] / n, acc['cumR'] / n, acc['stockL'] / n, acc['stockY'] / n,
                     acc['pL'] / cnt['pL'] if cnt['pL'] else float('nan'), acc['pY'] / cnt['pY'] if cnt['pY'] else float('nan')))
    print(f'\n{item}: day | cum sold leader / y3 / rival | stock-I0 at day start leader world / y3 world | rival mean price L / Y')
    for row in rows:
        print('  d%2d | %6.1f %6.1f %6.1f | %+6.0f %+6.0f | %6.1f %6.1f' % row)
    return rows


def mh_reaction(ps, item, who_idx, signal='rival_harvested'):
    """Mantel-Haenszel odds ratio of selling (given holding stock) when the rival just harvested (t-1) vs not,
    stratified by hour of day x (our stock fresh / old). ~1 means no reaction beyond the hour-of-day routine."""
    k = PIDX[item]
    strata = defaultdict(lambda: [0, 0, 0, 0])      # a: sig&sell, b: sig&no, c: nosig&sell, d: nosig&no
    for row in ps:
        g = row[who_idx]
        player = row[1]['meta']['seat']; r = 1 - player
        st = g['steps']
        sold = Counter(t for t, oi, it, p, op, itm, price, invb in g['tx'] if p == player and op == 'SELL' and itm == item)
        rsold = Counter(t for t, oi, it, p, op, itm, price, invb in g['tx'] if p == r and op == 'SELL' and itm == item)
        rharv = Counter(t for t, p, prod, u in g['harvest'] if p == r and prod == item)
        arr = arrivals(g, item, player)
        for t in range(2, len(st) - 3):
            if st[t]['shed'][player][k] <= 0:
                continue
            y = bool(sold.get(t))
            if signal == 'rival_harvested':
                x = rharv.get(t - 1, 0) > 0 or rharv.get(t - 2, 0) > 0
            elif signal == 'rival_sells_next':
                x = any(rsold.get(t + d, 0) for d in (1, 2, 3))
            else:
                x = rsold.get(t - 1, 0) > 0
            key = (t % 24, arr[t] > 0 or arr[t - 1] > 0)
            strata[key][(0 if x else 2) + (0 if y else 1)] += 1
    num = den = 0.0
    for a, b, c, d in strata.values():
        n = a + b + c + d
        if n:
            num += a * d / n; den += b * c / n
    return num / den if den else float('nan')


def simulate_floor_guard(item, riv_ev, own_ev, cons, thr, r, last=718):
    """Online replay: our planned units (own_ev) are sold as scheduled unless the quote is <= thr, in which case they
    are held and offered again at every later step (appended after that step's planned units, or at order index 0),
    until the final acting step, where everything left is sold. Rival units fixed. Returns (own_rev, riv_rev,
    max_held, units_sold_at_or_below_thr)."""
    by_step = defaultdict(list)
    for t, oi, k in riv_ev:
        by_step[t].append((oi, k, r, 'R'))
    planned = defaultdict(list)
    for t, oi, k in own_ev:
        planned[t].append((oi, k))
    own_rev = riv_rev = 0
    inv = I0
    held = max_held = low = 0
    s = 1 - r
    for t in range(len(cons)):
        evs = list(by_step.get(t, ()))
        pl = planned.get(t, [])
        for oi, k in pl:
            evs.append((oi, k, s, 'O'))
        if held:
            base_oi = min((oi for oi, _ in pl), default=0)
            k0 = max((k for oi, k in pl if oi == base_oi), default=-1) + 1
            for j in range(held):
                evs.append((base_oi, k0 + j, s, 'H'))
            held = 0
        evs.sort(key=lambda e: (e[0], e[1], e[2]))
        i = 0
        while i < len(evs):
            oi, k = evs[i][0], evs[i][1]
            grp = []
            while i < len(evs) and evs[i][0] == oi and evs[i][1] == k:
                grp.append(evs[i]); i += 1
            q = market_price(item, inv)
            for _, _, p, kind in grp:
                if kind == 'R':
                    riv_rev += q
                    if q > 1:
                        inv += 1
                elif q <= thr and t < last:
                    held += 1
                else:
                    own_rev += q
                    low += q <= thr
                    if q > 1:
                        inv += 1
        max_held = max(max_held, held)
        inv -= cons[t]
    return own_rev, riv_rev, max_held, low


def eval_floor_guard(Y, item, thrs=(1, 10, 30)):
    s = Y['meta']['seat']; r = 1 - s
    cons = consumption(Y, item)
    riv = sell_events(Y, item, r)
    own = sell_events(Y, item, s)
    base = simulate_inv(item, *two(riv, own, r), cons)
    b_own, b_riv = sum(p for p, _ in base[s]), sum(p for p, _ in base[r])
    out = {}
    for thr in thrs:
        o, rv, mh, low = simulate_floor_guard(item, riv, own, cons, thr, r)
        out[thr] = (o - b_own, rv - b_riv, mh, low)
    return out


def robustness(ps, items=('STRAWBERRY', 'MILK', 'WOOL', 'MELON'), boots=2000):
    """Per-world spread of the our-schedule effect and of the production part; seed-bootstrap 95% CI of the mean;
    and how many y3 losses (final cash) the market-only 'leader calendar' gain for these products would flip."""
    import random
    rng = random.Random(1)
    gains = defaultdict(float)
    for item in items:
        ours, prod = [], []
        for ep, L, Y in ps:
            x = world_item(L, Y, item)
            ours.append(x['riv_rev_swap'] - x['riv_rev_L'])
            prod.append(x['prod_part'])
            lc = leader_calendar(Y, L, item)
            gains[ep] += lc[0] - lc[1]
        n = len(ours)
        bs = sorted(sum(ours[rng.randrange(n)] for _ in range(n)) / n for _ in range(boots))
        print(f'{item:10s} our-schedule effect on rival: mean {sum(ours) / n:+.0f} (95% CI {bs[int(.025 * boots)]:+.0f}..{bs[int(.975 * boots)]:+.0f}),'
              f' positive in {sum(1 for v in ours if v > 0)}/{n}; production part mean {sum(prod) / n:+.0f}, positive {sum(1 for v in prod if v > 0)}/{n}')
    flips = 0
    losses = 0
    for ep, L, Y in ps:
        s = Y['meta']['seat']
        m = Y['meta']['final_cash'][s] - Y['meta']['final_cash'][1 - s]
        if m < 0:
            losses += 1
            flips += m + gains[ep] > 0
    tot = sum(gains.values()) / len(ps)
    print(f'leader-calendar transplant for {"/".join(items)} (market-only): mean margin {tot:+.0f} per world;'
          f' y3 losses {losses}/{len(ps)}, flipped {flips}')

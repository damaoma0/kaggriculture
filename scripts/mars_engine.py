"""Selling in isolation on the REAL engine ("goods from Mars"). The arm's game is replayed step by step with every farm
action unchanged; only our SELL orders of the chosen products are replaced. The market (lockstep positions, $1 sales
adding no stock, consumption, the rival's recorded orders) is the engine's own.
strategies:
  actual       our own sell orders on Mars stock (harness check: must reproduce the arm's revenues)
  books        the leader's sell orders of those products at the same list positions, quantities capped to what the
               leader actually sold at that step, on Mars stock (no shed check); our other orders fill the free slots
  books_cap    books, but never more units in total than we actually sold of that product
  books_deliv  the leader's order times and positions, but only units that have already reached our shed in the arm's
               game: at each leader order sell up to min(the leader's cumulative units, our units delivered so far) -
               our units sold; the rest waits for the next leader order; whatever is left is sold at step 718. Held
               units are stored off the shed (no capacity: timing alone, the physical game stays the arm's)
In every strategy our real shed is kept exactly as in the arm's game (before every step it is set to the arm's pre-step
stock minus what the arm sold in that step), so drops, midnight overflow and every other physical state match; the
check lines confirm it.
usage: mars_engine.py <team:ep> <arm> [--prods ...] [--json out.json]
       mars_engine.py --panel <arm> <out.json> [--workers 2]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
PRODS = tuple(sys.argv[sys.argv.index('--prods') + 1].split(',')) if '--prods' in sys.argv else ('STRAWBERRY', 'WOOL', 'MILK')
STRATS = tuple(sys.argv[sys.argv.index('--strats') + 1].split(',')) if '--strats' in sys.argv else ('actual', 'books', 'books_cap', 'books_deliv')
R = {'w': None, 'seat': 0, 't': 0, 'ev': None, 'mars': False, 'other': None, 'lost': None, 'lostd': None}
_commit, _drop = E._commit_unit, E._drop_inventories_to_shed


def commit(op, item, price, farm, private, market, shed_capacity=100):
    w = R['w']
    ours = w is not None and farm is w.farms[R['seat']]
    if ours and R['mars'] and op == 'SELL' and item in PRODS and R['t'] >= 264:
        farm['money'] += price                      # Mars stock: no shed check, no shed decrement
        if price > 1:
            market['inventory'][item] += 1
        r = True
    else:
        r = _commit(op, item, price, farm, private, market, shed_capacity)
    if r and w is not None and R['t'] >= 264:
        side = 'us' if ours else 'opp'
        if op == 'SELL' and item in PRODS:
            R['ev'].append((R['t'], side, item, float(price)))
        elif ours:
            R['other'][(R['t'], op, item)] += 1
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
        for kk, v in car.items():
            lost = v - (private['shed'].get(kk, 0) - before.get(kk, 0))
            if lost > 0:
                R['lost'][kk] += lost
                R['lostd'][(R['t'], kk)] += lost
        return
    return _drop(private, cap)


E._commit_unit, E._drop_inventories_to_shed = commit, drop


def play(tape, stream, market_fn=None, shed_fix=None, mars=False):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, ev=[], mars=mars, other=Counter(), lost=Counter(), lostd=Counter())
    pre = {p: {} for p in PRODS}
    hands = {}
    while w.t < 719:
        t = w.t
        R['t'] = t
        if stream is None or t < 264:
            own = UE.tape_action(tape['actions'], t)
        else:
            a = stream[t] if t < len(stream) else {}
            own = dict(a) if isinstance(a, dict) and a else dict(UE.PASS)
        if t >= 264:
            for p in PRODS:
                pre[p][t] = int(w.private(seat)['shed'].get(p, 0) or 0)   # before any fix: what the engine produced
            if shed_fix is not None:
                for p in PRODS:
                    w.private(seat)['shed'][p] = shed_fix[p][t]
            if market_fn is not None:
                own['market'] = market_fn(t, list(own.get('market') or []), w, seat)
            if t % 24 == 1:
                hands[t // 24] = len(w.farms[seat]['hands'])
        acts = [None, None]
        acts[seat], acts[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    out = {'ev': list(R['ev']), 'pre': pre, 'other': Counter(R['other']), 'hands': hands, 'lost': Counter(R['lost']),
           'lostd': Counter(R['lostd']),
           'money': (w.farms[seat]['money'], w.farms[1 - seat]['money'])}
    R['w'] = None
    return out


def rev(G, side, p):
    x = [e[3] for e in G['ev'] if e[1] == side and e[2] == p]
    return len(x), sum(x)


def world(g, arm):
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    stream = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    UE.CFG['maxMarketOrdersPerTurn'] = 10
    L = play(tape, None)
    A = play(tape, stream)
    sold_a = Counter((e[0], e[2]) for e in A['ev'] if e[1] == 'us')
    fix = {p: {t: A['pre'][p][t] - sold_a[(t, p)] for t in A['pre'][p]} for p in PRODS}
    sold_l = Counter((e[0], e[2]) for e in L['ev'] if e[1] == 'us')
    cum_l = {p: {} for p in PRODS}
    for p in PRODS:
        run = 0
        for t in range(264, 719):
            run += sold_l[(t, p)]
            cum_l[p][t] = run
    our_total = Counter(e[2] for e in A['ev'] if e[1] == 'us')
    # units that have reached our shed before step t in the arm's game (a unit dropped during step t is sellable from
    # t + 1; the midnight dump from the next hour 0); held units are stored off the shed (no capacity), so the
    # physical game stays the arm's
    avail = {p: {} for p in PRODS}
    for p in PRODS:
        run = A['pre'][p][264]
        for t in range(264, 719):
            avail[p][t] = run
            nxt = A['pre'][p].get(t + 1)
            if nxt is not None:
                run += nxt - A['pre'][p][t] + sold_a[(t, p)]

    # 'infinite shed': the units the midnight overflow deleted in the arm's game become sellable from the next hour 0
    avail_inf = {p: {} for p in PRODS}
    for p in PRODS:
        extra = 0
        for t in range(264, 719):
            extra += sum(v for (t2, p2), v in A['lostd'].items() if p2 == p and t2 == t - 1)
            avail_inf[p][t] = avail[p][t] + extra
    # units in our shed by the market of step t (drops of step t come before its market; the midnight dump after it)
    avail2 = {p: {t: (avail[p][t + 1] if t % 24 != 23 and t + 1 in avail[p] else avail[p][t]) for t in avail[p]} for p in PRODS}
    avail2i = {p: {t: avail2[p][t] + avail_inf[p][t] - avail[p][t] for t in avail[p]} for p in PRODS}

    def snap_targets(mode):
        """our units per (step, product) when every sale moves to an hour 1 / 5 / 9 / 13 / 17 / 21 (the hour right after a
        town consumption tick). late: to the next such hour (h0 -> h1, h2-h4 -> h5, ...); early: back to the start of its
        4-hour window (h2-h4 -> h1, ...) as far as the units were already in our shed; the rest keep their hour"""
        tgt = Counter()
        for p in PRODS:
            if mode == 'late':
                for t in range(264, 719):
                    n = sold_a[(t, p)]
                    if n:
                        t2 = t if t % 4 == 1 else t + (1 - t % 4) % 4
                        tgt[(t2 if t2 <= 718 else t, p)] += n
                continue
            tgt[(264, p)] += sold_a[(264, p)]
            cum = sold_a[(264, p)]
            for b in range(265, 719, 4):
                block = list(range(b, min(b + 4, 719)))
                room = max(0, avail2[p][b] - cum - sold_a[(b, p)])
                tgt[(b, p)] += sold_a[(b, p)]
                for x in block[1:]:
                    n = sold_a[(x, p)]
                    m = min(n, room)
                    room -= m
                    tgt[(b, p)] += m
                    tgt[(x, p)] += n - m
                cum += sum(sold_a[(x, p)] for x in block)
        return tgt

    prof = json.load(open(ROOT / 'results/fresh/threads_20260928/dsm_hourly_profile.json'))
    lday = {p: Counter(e[0] // 24 for e in L['ev'] if e[1] == 'us' and e[2] == p) for p in PRODS}

    def pattern_target(p, t):
        """the KQ rule: the leader's cumulative sales through yesterday + DSM's hour-of-day share of today's"""
        d, h = t // 24, t % 24
        prev = sum(v for dd, v in lday[p].items() if dd < d)
        return int(prev + (prof[p][h] if p in prof else 1.0) * lday[p].get(d, 0))

    def mk(strategy):
        used = Counter()
        tgt = snap_targets('late' if strategy == 'snap_late' else 'early') if strategy.startswith('snap') else None

        def capped(t, orders, skip=()):
            """our own orders with each product's sells capped to the units the arm really sold at this step (on Mars
            stock an order would otherwise also sell units the arm did not have)"""
            left = Counter({p: sold_a[(t, p)] for p in PRODS})
            out = []
            for o in orders:
                if isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS:
                    q = 0 if o[1] in skip else min(int(o[2]), left[o[1]])
                    left[o[1]] -= q
                    if q > 0:
                        out.append(['SELL', o[1], q])
                else:
                    out.append(o)
            return out

        def fn(t, orders, w, seat):
            if strategy == 'actual':
                return capped(t, orders)
            if strategy in ('pattern_tick', 'pattern_tick0', 'pattern_tick_inf'):
                av2_ = avail2i if strategy.endswith('_inf') else avail2
                h = t % 24
                sold_us = Counter(e[2] for e in R['ev'] if e[1] == 'us')
                out = capped(t, orders, skip=PRODS)
                front = []
                for p in PRODS:
                    if t == 718:
                        q = av2_[p][t] - sold_us[p]
                    elif h % 4 == 1 or (strategy == 'pattern_tick0' and h == 0):
                        q = min(pattern_target(p, t), av2_[p][t]) - sold_us[p]
                    else:
                        q = 0
                    if q > 0:
                        (front if h == 0 else out).append(['SELL', p, q])
                return front + out
            if tgt is not None:
                out = capped(t, orders, skip=PRODS)
                pos = {}
                for i, o in enumerate(orders):
                    if isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS and o[1] not in pos:
                        pos[o[1]] = i
                for p in PRODS:
                    if tgt[(t, p)] > 0:
                        i = pos.get(p, len(out))
                        out.insert(min(i, len(out)), ['SELL', p, tgt[(t, p)]])
                return out
            if strategy in ('h0front', 'h0back'):
                h = t % 24
                if h == 1:                                     # the hour-1 sells move to hour 0
                    return capped(t, orders, skip=PRODS)
                if h == 0 and t + 1 <= 718:
                    mine = capped(t, orders)
                    moved = [['SELL', p, sold_a[(t + 1, p)]] for p in PRODS if sold_a[(t + 1, p)] > 0]
                    return moved + mine if strategy == 'h0front' else mine + moved
                return capped(t, orders)
            keep = [o for o in orders if not (isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS)]
            lead = list(UE.tape_action(tape['actions'], t).get('market') or [])[:10]
            slots = {}
            if strategy in ('books_deliv', 'books_deliv_inf'):
                av_ = avail_inf if strategy.endswith('_inf') else avail
                sold_us = Counter(e[2] for e in R['ev'] if e[1] == 'us')
                done = set()
                for i, o in enumerate(lead):
                    if isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS and sold_l[(t, o[1])] > 0 and o[1] not in done:
                        q = min(cum_l[o[1]][t], av_[o[1]][t]) - sold_us[o[1]]
                        done.add(o[1])
                        if q > 0:
                            slots[i] = ['SELL', o[1], q]
                if t == 718:                                   # the last executed step: sell whatever is left
                    for p in PRODS:
                        n = av_[p][t] - sold_us[p] - sum(s[2] for s in slots.values() if s[1] == p)
                        if n > 0:
                            slots[len(lead) + len(slots) + PRODS.index(p) + 20] = ['SELL', p, n]
            else:
                left = Counter({p: sold_l[(t, p)] for p in PRODS})
                for i, o in enumerate(lead):
                    if isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS and left[o[1]] > 0:
                        q = min(int(o[2]), left[o[1]])
                        if strategy == 'books_cap':
                            q = min(q, our_total[o[1]] - used[o[1]])
                        if q > 0:
                            slots[i] = ['SELL', o[1], q]
                            left[o[1]] -= q
                            used[o[1]] += q
            out, k = [], 0
            late = [slots[i] for i in sorted(slots) if i >= len(keep) + len(slots)]
            for i in range(len(keep) + len(slots)):
                if i in slots:
                    out.append(slots[i])
                elif k < len(keep):
                    out.append(keep[k])
                    k += 1
            return out + keep[k:] + late
        return fn

    res = {'leader': L, 'arm': A}
    checks = {}
    for strat in STRATS:
        UE.CFG['maxMarketOrdersPerTurn'] = 10 if strat == 'actual' else 20
        M = play(tape, stream, mk(strat), fix, mars=True)
        UE.CFG['maxMarketOrdersPerTurn'] = 10
        res[strat] = M
        checks[strat] = {
            'shed_same': all(M['pre'][p][t] == A['pre'][p][t] for p in PRODS for t in A['pre'][p] if t > 264),
            'other_diff': sum(abs(M['other'][k] - A['other'][k]) for k in set(M['other']) | set(A['other'])),
            'hands_same': M['hands'] == A['hands'],
            'lost': dict(M['lost']), 'lost_arm': dict(A['lost'])}
    out = {'checks': checks}
    for p in PRODS:
        out[p] = {k: {'us': rev(G, 'us', p), 'opp': rev(G, 'opp', p)} for k, G in res.items()}
    out['money'] = {k: G['money'] for k, G in res.items()}
    if '--json' in sys.argv:                              # single-world mode: keep every sale event
        out['ev'] = {k: G['ev'] for k, G in res.items()}
    return ep, out


def job(args):
    return world(*args)


def summary(res):
    n = len(res)
    print(f'{n} worlds, per world. margin gap vs DSM on a product = (our revenue - DSM\'s) - (rival revenue in that game - in DSM\'s game)')
    tot = Counter()
    for p in PRODS:
        line = f'{p:10s}'
        for k in ('arm',) + STRATS:
            gap = sum((r[p][k]['us'][1] - r[p]['leader']['us'][1]) - (r[p][k]['opp'][1] - r[p]['leader']['opp'][1]) for r in res.values()) / n
            tot[k] += gap
            line += f' | {k} {gap:+7.0f}'
        print(line)
    print('TOTAL     ' + ''.join(f' | {k} {v:+7.0f}' for k, v in tot.items()))
    if 'actual' in STRATS:
        for k in STRATS:
            if k == 'actual':
                continue
            dd = {p: [((r[p][k]['us'][1] - r[p]['actual']['us'][1]) - (r[p][k]['opp'][1] - r[p]['actual']['opp'][1])) for r in res.values()] for p in PRODS}
            per = [sum(dd[p][i] for p in PRODS) for i in range(n)]
            m = sum(per) / n
            sd = (sum((x - m) ** 2 for x in per) / max(1, n - 1)) ** 0.5
            print(f'  {k} vs actual: margin {m:+.0f} (t {m / (sd / n ** 0.5) if sd else 0:+.2f}, better {sum(x > 0 for x in per)}/{n}); '
                  + ', '.join(f'{p} {sum(dd[p]) / n:+.0f}' for p in PRODS))
    for k in STRATS:
        c = [r['checks'][k] for r in res.values()]
        print(f'  checks {k}: shed identical {sum(x["shed_same"] for x in c)}/{n}, other orders identical '
              f'{sum(x["other_diff"] == 0 for x in c)}/{n}, hands identical {sum(x["hands_same"] for x in c)}/{n}, '
              f'midnight deletions per world {sum(sum(x["lost"].values()) for x in c) / n:.1f} (arm {sum(sum(x["lost_arm"].values()) for x in c) / n:.1f})')
    un = {p: (sum(r[p]['arm']['us'][0] for r in res.values()) / n, sum(r[p]['leader']['us'][0] for r in res.values()) / n) for p in PRODS}
    print('  units sold per world (ours / DSM): ' + ', '.join(f'{p} {a:.0f} / {b:.0f}' for p, (a, b) in un.items()))


if __name__ == '__main__':
    if sys.argv[1] == '--panel':
        arm, outp = sys.argv[2], sys.argv[3]
        nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
        games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
        res = {}
        with Pool(nw) as pool:
            for ep, r in pool.imap_unordered(job, [(g, arm) for g in games]):
                res[ep] = r
                print('done', ep, len(res), flush=True)
        json.dump(res, open(outp, 'w'))
        summary(res)
    else:
        g, arm = sys.argv[1], sys.argv[2]
        ep, r = world(g, arm)
        summary({ep: r})
        if '--json' in sys.argv:
            json.dump(r, open(sys.argv[sys.argv.index('--json') + 1], 'w'))

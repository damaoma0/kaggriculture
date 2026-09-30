"""What the dawn legs' early goods earned, on the real engine with the farm fixed (the mars_engine.py harness): the arm's
game is replayed with every farm action unchanged; our sells are the arm's own ("actual", the harness check), or the same
but every unit a dawn leg delivered is not sold at its drop step and is sold instead at hour 1 of the next day, i.e.
as if carried to the midnight dump ("carried"). actual - carried = the sale-timing value of the early delivery alone
(rival orders fixed; the market's lockstep, consumption and $1 rule are the engine's).
Needs the arm's dawn_trace.py JSON (its "legs": day, drop (hour, tile, goods)).
usage: dawn_mars.py <team:ep> <ARM> <trace json>"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.argv += [] if '--prods' in sys.argv else ['--prods', 'STRAWBERRY,WOOL,MILK,EGG']
import mars_engine as ME  # noqa: E402
import upkeep_engine as UE  # noqa: E402

PRODS = ME.PRODS


def main():
    g, arm, tr = sys.argv[1], sys.argv[2], sys.argv[3]
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    stream = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    legs = json.load(open(tr))['legs']
    UE.CFG['maxMarketOrdersPerTurn'] = 10
    A = ME.play(tape, stream)
    sold_a = Counter((e[0], e[2]) for e in A['ev'] if e[1] == 'us')
    fix = {p: {t: A['pre'][p][t] - sold_a[(t, p)] for t in A['pre'][p]} for p in PRODS}
    defer, add = Counter(), Counter()
    for lg in legs:
        if not lg['drop']:
            continue
        h, tile, goods = lg['drop']
        t = lg['day'] * 24 + h
        for k, n in goods.items():
            if k in PRODS:
                q = min(n, sold_a[(t, k)] - defer[(t, k)])
                if q > 0:
                    defer[(t, k)] += q
                    add[(min(718, (lg['day'] + 1) * 24 + 1), k)] += q

    def mk(carry):
        def fn(t, orders, w, seat):
            left = Counter({p: sold_a[(t, p)] - (defer[(t, p)] if carry else 0) for p in PRODS})
            out = []
            for o in orders:
                if isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS:
                    q = min(int(o[2]), left[o[1]])
                    left[o[1]] -= q
                    if q > 0:
                        out.append(['SELL', o[1], q])
                else:
                    out.append(o)
            if carry:
                front = [['SELL', p, add[(t, p)]] for p in PRODS if add[(t, p)] > 0]
                out = front + out
            return out
        return fn

    # DSM's sale timing (mars_engine's books_deliv): DSM's sell orders at its list positions, each up to min(DSM's cumulative
    # units, our units already in the shed) - our units sold; "carried": the dawn units count as in the shed only from the
    # next hour 1 (as if they had come with the midnight dump)
    L = ME.play(tape, None)
    sold_l = Counter((e[0], e[2]) for e in L['ev'] if e[1] == 'us')
    cum_l = {p: {} for p in PRODS}
    for p in PRODS:
        run = 0
        for t in range(264, 719):
            run += sold_l[(t, p)]
            cum_l[p][t] = run
    avail = {p: {} for p in PRODS}
    for p in PRODS:
        run = A['pre'][p][264]
        for t in range(264, 719):
            avail[p][t] = run
            nxt = A['pre'][p].get(t + 1)
            if nxt is not None:
                run += nxt - A['pre'][p][t] + sold_a[(t, p)]
    avail_c = {p: dict(avail[p]) for p in PRODS}
    for (t0, p), n in defer.items():
        t1 = min(718, (t0 // 24 + 1) * 24 + 1)
        for t in range(t0 + 1, t1):
            avail_c[p][t] -= n

    def mk_books(av_):
        def fn(t, orders, w, seat):
            keep = [o for o in orders if not (isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS)]
            lead = list(UE.tape_action(tape['actions'], t).get('market') or [])[:10]
            sold_us = Counter(e[2] for e in ME.R['ev'] if e[1] == 'us')
            slots, done = {}, set()
            for i, o in enumerate(lead):
                if isinstance(o, list) and o and o[0] == 'SELL' and o[1] in PRODS and sold_l[(t, o[1])] > 0 and o[1] not in done:
                    q = min(cum_l[o[1]][t], av_[o[1]][t]) - sold_us[o[1]]
                    done.add(o[1])
                    if q > 0:
                        slots[i] = ['SELL', o[1], q]
            if t == 718:
                for p in PRODS:
                    n = av_[p][t] - sold_us[p] - sum(x[2] for x in slots.values() if x[1] == p)
                    if n > 0:
                        slots[len(lead) + len(slots) + PRODS.index(p) + 20] = ['SELL', p, n]
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

    res = {}
    for name, fn in (('actual', mk(False)), ('carried', mk(True)), ('dsm_times', mk_books(avail)), ('dsm_times_carried', mk_books(avail_c))):
        UE.CFG['maxMarketOrdersPerTurn'] = 20
        res[name] = ME.play(tape, stream, fn, fix, mars=True)
        UE.CFG['maxMarketOrdersPerTurn'] = 10
    print(f'{arm}: dawn-delivered units moved to the next hour 1: ' + ', '.join(f'{p} {sum(v for (t, q), v in defer.items() if q == p)}' for p in PRODS))
    tot = 0.0
    for p in PRODS:
        a_u, a_r = ME.rev(res['actual'], 'us', p)
        c_u, c_r = ME.rev(res['carried'], 'us', p)
        a_o, c_o = ME.rev(res['actual'], 'opp', p)[1], ME.rev(res['carried'], 'opp', p)[1]
        m = (a_r - c_r) - (a_o - c_o)
        tot += m
        print(f'  {p:10s} ours actual {a_r:8.0f} ({a_u}) vs carried {c_r:8.0f} ({c_u}): {a_r - c_r:+6.0f}; rival {a_o - c_o:+6.0f}; '
              f'margin value of the early delivery {m:+6.0f}')
    tot2 = 0.0
    for p in PRODS:
        a_r, c_r = ME.rev(res['dsm_times'], 'us', p)[1], ME.rev(res['dsm_times_carried'], 'us', p)[1]
        a_o, c_o = ME.rev(res['dsm_times'], 'opp', p)[1], ME.rev(res['dsm_times_carried'], 'opp', p)[1]
        tot2 += (a_r - c_r) - (a_o - c_o)
        print(f'  with DSM sale times: {p:10s} ours {a_r - c_r:+6.0f}, rival {a_o - c_o:+6.0f}, margin value of the early delivery {(a_r - c_r) - (a_o - c_o):+6.0f}')
    print(f'  total with DSM sale times: {tot2:+.0f}')
    arm_rev = sum(ME.rev(A, 'us', p)[1] for p in PRODS)
    print(f'  total margin value of delivering early (vs carrying the same units to the midnight dump): {tot:+.0f}; '
          f'harness check: actual on Mars reproduces the arm revenue {abs(sum(ME.rev(res["actual"], "us", p)[1] for p in PRODS) - arm_rev) < 1e-6}')


if __name__ == '__main__':
    main()

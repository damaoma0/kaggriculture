"""Counterfactual on the REAL engine (farm fixed, only our strawberry sells move; Mars stock = no shed check): what if the
strawberries an arm harvested by hour HMAX of day d (and carried to the midnight dump in its game) had reached the shed
at hour HARR of day d and been sold at once (the executor's DELIVER rule), instead of being sold with the next day's
stock. The next day's own strawberry sells are reduced by the moved units (earliest sells first).
usage: early_arrival.py <team:ep> <arm> <deliv json of the arm> [--hmax 11] [--harr 13,17] [--days 11-28]"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.argv = [sys.argv[0]] + sys.argv[1:] + ['--prods', 'STRAWBERRY']
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mars_engine as ME  # noqa: E402
UE = ME.UE


def arg(k, d):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d


g, arm, dj = sys.argv[1], sys.argv[2], sys.argv[3]
hmax = int(arg('--hmax', '11'))
harrs = [int(x) for x in arg('--harr', '13,17').split(',')]
d0, d1 = [int(x) for x in arg('--days', '11-28').split('-')]
team, ep = g.split(':')
tape = UE.load_tape(int(team), int(ep))
stream = json.loads((ME.ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
UE.CFG['maxMarketOrdersPerTurn'] = 10
A = ME.play(tape, stream)
P = 'STRAWBERRY'
sold_a = Counter((e[0], e[2]) for e in A['ev'] if e[1] == 'us')
fix = {P: {t: A['pre'][P][t] - sold_a[(t, P)] for t in A['pre'][P]}}
D = json.load(open(dj))
units = [u for u in D[arm]['units'] if u['p'] == P and u['how'] == 'midnight' and u['h'] >= 264]
moved = Counter()
for u in units:
    d, h = u['h'] // 24, u['h'] % 24
    if h <= hmax and d0 <= d <= d1:
        moved[d] += 1
print('units moved per day:', dict(sorted(moved.items())), 'total', sum(moved.values()))


def rev(G, side):
    x = [e[3] for e in G['ev'] if e[1] == side and e[2] == P]
    return len(x), sum(x)


def run(harr):
    pend = Counter()

    def fn(t, orders, w, seat):
        left = Counter({P: sold_a[(t, P)]})
        out = []
        d, h = t // 24, t % 24
        if harr is not None and h == 0 and moved.get(d - 1):
            pend[P] += moved[d - 1]
        for o in orders:
            if isinstance(o, list) and o and o[0] == 'SELL' and o[1] == P:
                q = min(int(o[2]), left[P])
                left[P] -= q
                cut = min(q, pend[P])
                q -= cut
                pend[P] -= cut
                if q > 0:
                    out.append(['SELL', P, q])
            else:
                out.append(o)
        if harr is not None and h == harr and moved.get(d):
            out = [['SELL', P, moved[d]]] + out
        return out[:10]
    M = ME.play(tape, stream, fn, fix, mars=True)
    return M


base = run(None)
bu, bo = rev(base, 'us'), rev(base, 'opp')
print(f'base (actual on Mars): us {bu[0]} units {bu[1]:.0f}, rival {bo[0]} units {bo[1]:.0f}')
for harr in harrs:
    M = run(harr)
    u, o = rev(M, 'us'), rev(M, 'opp')
    dm = (u[1] - bu[1]) - (o[1] - bo[1])
    n = max(1, sum(moved.values()))
    print(f'arrive h{harr}: us {u[0]} units {u[1]:.0f} ({u[1] - bu[1]:+.0f}), rival {o[1]:.0f} ({o[1] - bo[1]:+.0f}); '
          f'margin {dm:+.0f} = {dm / n:+.1f} per moved unit')

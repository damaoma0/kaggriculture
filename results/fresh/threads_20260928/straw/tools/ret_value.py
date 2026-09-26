"""Isolated value of an arm's strawberry returns on the REAL engine (farm fixed, only our strawberry sells move, Mars
stock): the arm's own game ('actual') vs the same game where each return's strawberries, sold at once at the return
step, are instead sold with the next day's first strawberry sell (as if they had stayed in the hand until the midnight
dump). margin difference = value of the daytime delivery.
usage: ret_value.py <team:ep> <arm>"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.argv = [sys.argv[0]] + sys.argv[1:] + ['--prods', 'STRAWBERRY']
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mars_engine as ME  # noqa: E402
UE = ME.UE
P = 'STRAWBERRY'
g, arm = sys.argv[1], sys.argv[2]
team, ep = g.split(':')
tape = UE.load_tape(int(team), int(ep))
R = ME.ROOT / 'results/fresh'
stream = json.loads((R / 'day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
m = json.loads((R / 'sector_20260925/multi' / arm / f'{ep}.json').read_text(encoding='utf-8'))
dv = json.load(open(R / 'threads_20260928/straw' / f'deliv_{arm}.json'))
ret = Counter()                                    # return step -> strawberries dropped there by the SRET unit
for d, td in m['tier_days'].items():
    for u in td['units']:
        if not u.get('sret'):
            continue
        for h, tile, op in td['exec'][str(u['u'])]['done']:
            if op == 'SRET':
                t = int(d) * 24 + h
                ret[t] += sum(e['n'] for e in dv[arm]['events'] if e['t'] == t and e['unit'] == u['u'] and e['p'] == P)
print('return steps -> strawberries:', dict(sorted(ret.items())), 'total', sum(ret.values()))
UE.CFG['maxMarketOrdersPerTurn'] = 10
A = ME.play(tape, stream)
sold_a = Counter((e[0], e[2]) for e in A['ev'] if e[1] == 'us')
fix = {P: {t: A['pre'][P][t] - sold_a[(t, P)] for t in A['pre'][P]}}


def rev(G, side):
    x = [e[3] for e in G['ev'] if e[1] == side and e[2] == P]
    return len(x), sum(x)


def run(delay):
    pend = []                                      # [return day, units] waiting for a later day's first own sell

    def fn(t, orders, w, seat):
        left = Counter({P: sold_a[(t, P)]})
        out = []
        cut = min(ret.get(t, 0), sold_a[(t, P)]) if delay else 0
        if cut:
            pend.append([t // 24, cut])
        add = 0
        if delay and sold_a[(t, P)] > 0:
            for x in pend:
                if x[0] < t // 24 and x[1] > 0:
                    add += x[1]
                    x[1] = 0
        if delay and t == 718:
            add += sum(x[1] for x in pend)
            for x in pend:
                x[1] = 0
        for o in orders:
            if isinstance(o, list) and o and o[0] == 'SELL' and o[1] == P:
                q = min(int(o[2]), left[P]) - cut + add
                left[P] -= min(int(o[2]), left[P])
                cut = add = 0
                if q > 0:
                    out.append(['SELL', P, q])
            else:
                out.append(o)
        if add > 0:
            out.append(['SELL', P, add])
        return out[:10]
    return ME.play(tape, stream, fn, fix, mars=True)


base, late = run(False), run(True)
bu, bo = rev(base, 'us'), rev(base, 'opp')
lu, lo = rev(late, 'us'), rev(late, 'opp')
print(f'actual (returns sold at once): us {bu[0]} u {bu[1]:.0f}, rival {bo[1]:.0f}')
print(f'returns delayed to the next day: us {lu[0]} u {lu[1]:.0f}, rival {lo[1]:.0f}')
n = max(1, sum(ret.values()))
dm = (bu[1] - lu[1]) - (bo[1] - lo[1])
print(f'value of the daytime deliveries: own {bu[1] - lu[1]:+.0f}, rival {bo[1] - lo[1]:+.0f}, margin {dm:+.0f} '
      f'({dm / n:+.1f} per returned strawberry)')

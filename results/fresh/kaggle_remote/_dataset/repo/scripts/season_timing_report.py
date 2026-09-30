"""Report for season_timing.py output: per product, when we sell vs the leader (mean day / hour, harvest-to-sale delay),
how our sales sit relative to the rival's same-day sales, and where the rival's extra revenue comes from (by day)."""
import json
import sys
from collections import Counter, defaultdict

d = json.load(open(sys.argv[1]))
arm = sys.argv[2]
prods = sys.argv[3].split(',') if len(sys.argv) > 3 else ['WOOL', 'MILK', 'STRAWBERRY', 'EGG', 'WHEAT', 'CARROT', 'TOMATO', 'FERTILIZER']
n = len(d)


def events(C, side, p):
    ev = []
    for k, v in C.items():
        parts = k.split('|')
        if parts[0] == side and parts[1] == p and parts[4] == 'n':
            day, h = int(parts[2]), int(parts[3])
            ev.append((day * 24 + h, v, C.get(f'{side}|{p}|{day}|{h}|$', 0.0)))
    return sorted(ev)


def harvests(C, p):
    return sorted((int(k.split('|')[2]) * 24 + int(k.split('|')[3]), v) for k, v in C.items() if k.startswith(f'hv|{p}|'))


def fifo_delay(hv, sells):
    q = [[t, u] for t, u in hv]
    tot = cnt = 0
    i = 0
    for t, u, _ in sells:
        while u > 0 and i < len(q):
            if q[i][0] > t:
                break
            m = min(u, q[i][1])
            tot += m * (t - q[i][0])
            cnt += m
            u -= m
            q[i][1] -= m
            if q[i][1] == 0:
                i += 1
        # units sold that came from start stock are ignored
    return tot / cnt if cnt else float('nan')


for p in prods:
    S = {'leader': Counter(), arm: Counter()}
    agg = {s: {'units': 0, 'rev': 0.0, 'tw': 0.0, 'hw': 0.0, 'delay': [], 'before': 0, 'after': 0, 'hours': Counter()} for s in S}
    riv_by_day = defaultdict(lambda: [0.0, 0.0, 0, 0])   # rival revenue in leader game / arm game, units
    riv_by_ourhour = Counter()
    for ep, r in d.items():
        for side in ('leader', arm):
            C = r[side]['C']
            us = events(C, 'us', p)
            op = events(C, 'opp', p)
            hv = harvests(C, p)
            a = agg[side]
            for t, u, rev in us:
                a['units'] += u
                a['rev'] += rev
                a['tw'] += u * t / 24.0
                a['hw'] += u * (t % 24)
                a['hours'][t % 24] += u
            dl = fifo_delay(hv, us)
            if dl == dl:
                a['delay'].append(dl)
            first_opp = {}
            for t, u, _ in op:
                first_opp.setdefault(t // 24, t % 24)
            for t, u, _ in us:
                fo = first_opp.get(t // 24)
                if fo is None:
                    continue
                if t % 24 <= fo:
                    a['before'] += u
                else:
                    a['after'] += u
            for t, u, rev in op:
                x = riv_by_day[t // 24]
                if side == 'leader':
                    x[0] += rev; x[2] += u
                else:
                    x[1] += rev; x[3] += u
    print(f'\n=== {p}  (per world)')
    for side in ('leader', arm):
        a = agg[side]
        u = max(1, a['units'])
        top = ', '.join(f'h{h}:{c / n:.0f}' for h, c in a['hours'].most_common(4))
        dly = sum(a['delay']) / len(a['delay']) if a['delay'] else float('nan')
        ba = a['before'] + a['after']
        print('  %-8s sold %5.0f at %6.1f | mean sale day %5.2f, mean hour %4.1f | harvest->sale %5.1f h | same-day units before the rival\'s first sale %3.0f%% | top hours %s' % (
            side, a['units'] / n, a['rev'] / u, a['tw'] / u, a['hw'] / u, dly, 100 * a['before'] / max(1, ba), top))
    rows = sorted(riv_by_day.items())
    tot = sum(x[1] - x[0] for _, x in rows)
    print('  rival revenue gain by day (arm game - leader game), total %+.0f:' % (tot / n))
    print('   ' + '  '.join('d%d %+.0f' % (dd, (x[1] - x[0]) / n) for dd, x in rows if abs(x[1] - x[0]) / n >= 20))

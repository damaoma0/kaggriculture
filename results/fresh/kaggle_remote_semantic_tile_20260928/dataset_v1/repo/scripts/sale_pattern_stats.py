"""Sale patterns (season_timing.py output), leader vs an arm, days 11-28: per product, sale hours, harvest-to-sale lag
(FIFO), share sold the day it was harvested / the next morning / later, and where our sales fall relative to the
rival's sales of the same product that day. usage: sale_pattern_stats.py <timing json> <arm>"""
import json
import sys
from collections import Counter, defaultdict

d = json.load(open(sys.argv[1]))
arm = sys.argv[2]
n = len(d)
PR = ('WOOL', 'MILK', 'STRAWBERRY', 'WHEAT', 'FERTILIZER', 'EGG')


def events(C, side, p, kind='n'):
    ev = []
    for k, v in C.items():
        parts = k.split('|')
        if len(parts) == 5 and parts[0] == side and parts[1] == p and parts[4] == kind:
            ev += [int(parts[2]) * 24 + int(parts[3])] * int(v)
    return sorted(ev)


def harvests(C, p):
    ev = []
    for k, v in C.items():
        parts = k.split('|')
        if parts[0] == 'hv' and parts[1] == p:
            ev += [int(parts[2]) * 24 + int(parts[3])] * int(v)
    return sorted(ev)


for p in PR:
    print(f'\n=== {p}')
    for side in ('leader', arm):
        H = Counter(); lag = []; same = nextm = later = 0; before = after = 0; nsold = 0
        for ep, r in d.items():
            C = r[side]['C']
            sells = [t for t in events(C, 'us', p) if t < 29 * 24]
            hv = harvests(C, p)
            opp = events(C, 'opp', p)
            opp_by_day = defaultdict(list)
            for t in opp:
                opp_by_day[t // 24].append(t % 24)
            for t in sells:
                H[t % 24 // 4 * 4] += 1
                ob = opp_by_day.get(t // 24, [])
                if ob:
                    # share of the rival's same-day units sold AFTER this unit of ours (ours came first for them)
                    after += sum(1 for h in ob if h > t % 24) / len(ob)
                    before += sum(1 for h in ob if h <= t % 24) / len(ob)
            nsold += len(sells)
            q = list(hv)
            i = 0
            for t in sells:                       # FIFO harvest -> sale
                while i < len(q) and q[i] > t:
                    break
                if i < len(q) and q[i] <= t:
                    h = q[i]
                    i += 1
                    lag.append(t - h)
                    if t // 24 == h // 24:
                        same += 1
                    elif t // 24 == h // 24 + 1 and t % 24 < 12:
                        nextm += 1
                    else:
                        later += 1
        m = max(1, len(lag))
        lag.sort()
        name = 'DSM' if side == 'leader' else arm
        print('  %-4s sold %5.1f/world | hours: %s | harvest->sale median %s h | same day %.0f%%, next morning %.0f%%, later %.0f%% | rival units that day sold after ours %.0f%%' % (
            name, nsold / n, ' '.join('h%d-%d %2.0f%%' % (b, b + 3, 100 * H[b] / max(1, nsold)) for b in range(0, 24, 4)),
            lag[len(lag) // 2] if lag else '-', 100 * same / m, 100 * nextm / m, 100 * later / m, 100 * after / max(1e-9, after + before)))

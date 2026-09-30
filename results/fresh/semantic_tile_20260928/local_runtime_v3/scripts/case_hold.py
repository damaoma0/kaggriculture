"""How long each unit waits in the shed before it is sold, leader game vs arm game (one world, case_delivery.py log +
case_world.py log for the day-11 shed stock). Units enter the shed by daytime delivery (sellable at that step: unit
actions come before the market) or the midnight dump (sellable from the next hour 0); sales are matched to arrivals
FIFO per product. A consumption tick drains the market after the market of hours 0/4/8/12/16/20, so hours 1/5/9/13/17/21
are the first hours after a tick. Categories per unit (a = sellable from, s = sold):
  on arrival          s == a
  same window         a < s < w, where w = the first hour 1/5/9/... after a (no drain gained by waiting)
  next tick hour      s == w (waited exactly into the first hour after the next tick)
  held longer         s > w (same day / later day)
Arrival times come from the shed itself (case_world.py), not from the hand tracer.
usage: case_hold.py <deliv json> <case_world json>"""
import json
import sys
from collections import Counter

d = json.load(open(sys.argv[1]))
cw = json.load(open(sys.argv[2]))
arm = d['arm']


def wnext(a):
    x = a + 1
    while x % 4 != 1:
        x += 1
    return x


for p in d['prods']:
    print(f'== {p}')
    for k, lab in (('leader', 'DSM'), (arm, arm)):
        G = d[k]
        # arrivals from the shed itself (case_world: shed change + units sold); at hour 23 the units dropped by hands
        # that step are sellable at once, the rest is the midnight dump (sellable from the next hour 0)
        day23 = Counter(u['d'] for u in G['units'] if u['p'] == p and u['how'] == 'day' and u['d'] % 24 == 23)
        av = [264] * int(cw[k]['shed'][p].get('264', 0))
        for t, v in cw[k]['arrive'][p].items():
            t = int(t)
            if v <= 0:
                continue
            if t % 24 == 23:
                dd = min(v, day23[t])
                av += [t] * dd + [t + 1] * (v - dd)
            else:
                av += [t] * v
        av.sort()
        sales = sorted((s[0], s[3]) for s in G['sales'] if s[1] == 'us' and s[2] == p)
        C, V = Counter(), Counter()
        for (s, px), a in zip(sales, av):
            w = wnext(a)
            if s < a:
                cat = 'before arrival?'
            elif s == a:
                cat = 'on arrival' + (' (h0 = before the tick)' if a % 24 == 0 else '')
            elif s < w:
                cat = 'same window'
            elif s == w:
                cat = 'next tick hour'
            elif s // 24 == a // 24:
                cat = 'held, same day'
            else:
                cat = 'held, later day'
            C[cat] += 1
            V[cat] += px
        n = len(sales)
        src = Counter('day' if a % 24 != 0 else 'dump/h0' for a in av)
        print(f'  {lab:4s} sold {n} (arrivals: {src["day"]} daytime, {src["dump/h0"]} at hour 0) | ' +
              ' | '.join(f'{c} {C[c]} ({C[c] / n * 100:.0f}%, @{V[c] / C[c]:.0f})' for c in
                         ('on arrival (h0 = before the tick)', 'on arrival', 'same window', 'next tick hour', 'held, same day', 'held, later day', 'before arrival?') if C[c]))
        tick = sum(1 for s, _ in sales if s % 4 == 1)
        print(f'       sold at hours 1/5/9/13/17/21: {tick} ({tick / n * 100:.0f}%)')

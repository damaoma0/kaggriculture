"""summary of strawberry deliveries from a case_delivery.py json: DSM vs arm.
usage: straw_deliv.py <deliv json> [prod]"""
import json
import sys
from collections import Counter
from statistics import median

d = json.load(open(sys.argv[1]))
P = sys.argv[2] if len(sys.argv) > 2 else 'STRAWBERRY'
ACC = [(4, 4), (5, 4), (4, 5), (5, 5)]


def dist(t):
    return min(abs(t[0] - a[0]) + abs(t[1] - a[1]) for a in ACC) if t else None


for k in ('leader', d['arm']):
    G = d[k]
    us = [u for u in G['units'] if u['p'] == P and u['h'] >= 264]
    how = Counter(u['how'] for u in us)
    day = [u for u in us if u['how'] == 'day']
    byh = Counter(u['d'] % 24 for u in day)
    carry = [u['d'] - u['h'] for u in day]
    far = [dist(u['tile']) for u in day if u['tile']]
    hh = Counter(u['h'] % 24 for u in us)
    print(f'== {k}: harvested {len(us)} ({dict(how)})  day-delivered {len(day)}')
    print('   day-delivery hour: ' + ' '.join(f'h{h}:{byh[h]}' for h in sorted(byh)))
    if day:
        print(f'   carry h median {median(carry)} mean {sum(carry)/len(carry):.1f}; tile dist median {median(far) if far else None}')
    b = Counter(('h0-11' if u['d'] % 24 < 12 else 'h12-17' if u['d'] % 24 < 18 else 'h18-23') for u in day)
    print('   by window: ' + str(dict(b)))
    print('   harvest hour: ' + ' '.join(f'h{h}:{hh[h]}' for h in sorted(hh)))
    mid = [u for u in us if u['how'] == 'midnight']
    if mid:
        c2 = [(u['d'] - u['h']) for u in mid]
        print(f'   midnight-dump units carry h median {median(c2)}')
    days = Counter(u['d'] // 24 for u in day)
    print('   day-delivered by day: ' + ' '.join(f'{x}:{days[x]}' for x in sorted(days)))

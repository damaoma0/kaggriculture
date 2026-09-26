"""Report for season_returns.py (+ harvests from season_timing.py): per world and per day (days 11-28)."""
import json
import sys
from collections import Counter

R = json.load(open(sys.argv[1]))
T = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
arm = [k for k in next(iter(R.values())) if k != 'leader'][0]
n = len(R)
ND = 18                                            # days 11-28
PR = ('WOOL', 'MILK', 'STRAWBERRY')


def agg(side):
    C = Counter()
    for r in R.values():
        C.update(r[side])
    return C


def hv(side, p):
    if not T:
        return None
    s = 0
    for r in T.values():
        for k, v in r[side]['C'].items():
            parts = k.split('|')
            if parts[0] == 'hv' and parts[1] == p and int(parts[2]) <= 28:
                s += v
    return s


names = {'leader': 'DSM', arm: arm}
A = {s: agg(s) for s in ('leader', arm)}
print(f'{n} worlds, days 11-28; per farm-day unless noted\n')
print('HANDS RETURNING TO THE SHED')
for s in ('leader', arm):
    C = A[s]
    hd = C['night_hand_loads'] / (n * ND)          # hands employed = hand inventories at the midnight dump
    ret = sum(v for k, v in C.items() if k.startswith('return|hand|')) / (n * ND)
    dl = sum(v for k, v in C.items() if k.startswith('deliv|hand|')) / (n * ND)
    du = sum(v for k, v in C.items() if k.startswith('deliv_units|hand|')) / (n * ND)
    fdl = sum(v for k, v in C.items() if k.startswith('deliv|farmer|')) / (n * ND)
    fdu = sum(v for k, v in C.items() if k.startswith('deliv_units|farmer|')) / (n * ND)
    print('  %-4s hands %.1f | hands that come back to the shed %.1f (%.0f%%), returns %.1f | hands delivering %.1f, deliveries %.1f, %.1f units (%.1f / delivery) | farmer deliveries %.1f, %.1f units' % (
        names[s], hd, C['hands_returning'] / (n * ND), 100 * C['hands_returning'] / max(1, C['night_hand_loads']), ret,
        C['hands_delivering'] / (n * ND), dl, du, du / max(1e-9, dl), fdl, fdu))
print('\nHAND DELIVERIES BY HOUR (per day: deliveries / units)')
print('  hour  ' + ' '.join('%6d' % h for h in range(0, 24, 2)))
for s in ('leader', arm):
    C = A[s]
    row = []
    for h in range(0, 24, 2):
        d_ = (C.get(f'deliv|hand|{h}', 0) + C.get(f'deliv|hand|{h + 1}', 0)) / (n * ND)
        u_ = (C.get(f'deliv_units|hand|{h}', 0) + C.get(f'deliv_units|hand|{h + 1}', 0)) / (n * ND)
        row.append('%.2f/%-4.1f' % (d_, u_))
    print('  %-4s  ' % names[s] + ' '.join('%6s' % x for x in row))
print('\nWOOL / MILK / STRAWBERRY FLOW (per farm-day)')
for p in PR:
    print(f'  {p}')
    for s in ('leader', arm):
        C = A[s]
        h_ = hv(s, p)
        dlv = sum(v for k, v in C.items() if k.startswith(f'dunits|{p}|')) / (n * ND)
        car = C.get(f'carried|{p}', 0) / (n * ND)
        sold = sum(v for k, v in C.items() if k.startswith(f'sell|{p}|')) / (n * ND)
        s_eve = sum(C.get(f'sell|{p}|{h}', 0) for h in range(12, 24)) / (n * ND)
        s_h1 = sum(C.get(f'sell|{p}|{h}', 0) for h in range(0, 4)) / (n * ND)
        byh = ' '.join('h%d-%d:%.1f' % (b, b + 3, sum(C.get(f'dunits|{p}|{h}', 0) for h in range(b, b + 4)) / (n * ND)) for b in range(0, 24, 4))
        print('    %-4s harvested %s | back to the shed before midnight %.1f (%s) | carried to midnight %.1f | sold %.1f (hours 0-3 %.1f, 12-23 %.1f)' % (
            names[s], '%.1f' % (h_ / (n * ND)) if h_ is not None else '-', dlv, byh, car, sold, s_h1, s_eve))
print('\nHAND LOAD AT MIDNIGHT (share of hand-nights)')
for s in ('leader', arm):
    C = A[s]
    tot = max(1, C['night_hand_loads'])
    print('  %-4s ' % names[s] + '  '.join('%d-%d: %.0f%%' % (b, b + 4, 100 * C.get(f'night_load_{b}', 0) / tot) for b in range(0, 35, 5)))

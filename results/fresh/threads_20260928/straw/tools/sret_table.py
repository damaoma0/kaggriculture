"""per arm: every planned return, planned vs executed (hour, strawberries carried, what was dropped, sale price at that
step), aggregates, and the strawberry deliveries by hour vs DSM. usage: sret_table.py ARM [--rows]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

R = Path('C:/Users/xyygl/Documents/kaggriculture/results/fresh')
O = R / 'threads_20260928/straw'
EP = '112604454'
arm = sys.argv[1]
rows = '--rows' in sys.argv
m = json.loads((R / 'sector_20260925/multi' / arm / f'{EP}.json').read_text(encoding='utf-8'))
dv = json.load(open(O / f'deliv_{arm}.json'))
cw = json.load(open(O / f'case_{arm}.json'))
ST = set()
for u in dv[arm]['units'] + dv['leader']['units']:
    if u['p'] == 'STRAWBERRY' and u['tile']:
        ST.add(u['tile'][1] * 10 + u['tile'][0])
sales = defaultdict(list)
for e in cw[arm]['sales']:
    if e[1] == 'us' and e[2] == 'SELL' and e[3] == 'STRAWBERRY':
        sales[e[0]].append(e[4])
ev_by = defaultdict(list)
for e in dv[arm]['events']:
    ev_by[(e['t'], e['unit'])].append(e)
agg = Counter()
prices, h1p = [], []
late_by = []
for d, td in sorted(m['tier_days'].items(), key=lambda x: int(x[0])):
    d = int(d)
    for u in td['units']:
        if not u.get('sret'):
            continue
        info = u['sret']
        uu = u['u']
        done = td['exec'][str(uu)]['done']
        sd = [x for x in done if x[2] == 'SRET']
        agg['planned'] += 1
        agg['planned_straw'] += info[1]
        agg['planned_hours'] += info[3]
        agg['moves'] += info[4]
        if not sd:
            agg['not_executed'] += 1
            if rows:
                print(f'  d{d} u{uu}: planned h{info[-2]} {info[1]} straw, NOT executed; done tail {done[-4:]}')
            continue
        h = sd[0][0]
        t = d * 24 + h
        evs = ev_by.get((t, uu), [])
        drop = Counter()
        for e in evs:
            drop[e['p']] += e['n']
        op = evs[0]['op'] if evs else None
        agg['executed'] += 1
        agg['straw_dropped'] += drop['STRAWBERRY']
        agg['other_dropped'] += sum(v for k, v in drop.items() if k != 'STRAWBERRY')
        agg['op_' + str(op)] += 1
        late_by.append(h - info[-2])
        sp = sales.get(t, [])
        if sp:
            prices += sp
        nx = sales.get((d + 1) * 24 + 1, [])
        if nx:
            h1p.append(sum(nx) / len(nx))
        if rows:
            print(f'  d{d} u{uu}: plan h{info[-2]} (by h{info[-1]}) {info[1]} straw +{info[3]}h moves {info[4]} | exec h{h} {op} '
                  f'{dict(drop)} | sold at that step {len(sp)} @ {round(sum(sp) / len(sp)) if sp else "-"} | next day h1 our '
                  f'strawberry price {round(sum(nx) / len(nx)) if nx else "-"}')
print(f'{arm}: returns planned {agg["planned"]} (straw planned {agg["planned_straw"]}, added h {agg["planned_hours"]}, '
      f'stops handed over {agg["moves"]}), executed {agg["executed"]} (not {agg["not_executed"]}), strawberries dropped '
      f'{agg["straw_dropped"]}, other goods dropped {agg["other_dropped"]}, ops DROP {agg["op_DROP"]} / PLACE {agg["op_PLACE"]}, '
      f'exec hour - plan hour: {dict(Counter(late_by))}; dropped strawberries sold at once @ '
      f'{round(sum(prices) / len(prices)) if prices else "-"} (n {len(prices)}), next-day h1 strawberry price those days @ '
      f'{round(sum(h1p) / len(h1p)) if h1p else "-"}')
for k in ('leader', arm):
    us = [u for u in dv[k]['units'] if u['p'] == 'STRAWBERRY' and u['h'] >= 264]
    day = [u for u in us if u['how'] == 'day']
    byh = Counter(u['d'] % 24 for u in day)
    carry = [u['d'] - u['h'] for u in day]
    print(f'  {"DSM" if k == "leader" else k}: strawberries harvested {len(us)}, delivered in the day {len(day)} '
          f'(h0-11 {sum(v for h, v in byh.items() if h < 12)}, h12-17 {sum(v for h, v in byh.items() if 12 <= h < 18)}, '
          f'h18-23 {sum(v for h, v in byh.items() if h >= 18)}), carry median {median(carry) if carry else "-"} h; by hour '
          + ' '.join(f'h{h}:{byh[h]}' for h in sorted(byh)))

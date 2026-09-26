"""step-by-step trace of the strawberry returns of an arm (one world): planned vs executed, units dropped, sale prices,
and the day's work vs KS1fl (executed ops by type).
usage: sret_trace.py ARM [--days 20,22]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

R = Path('C:/Users/xyygl/Documents/kaggriculture/results/fresh')
O = R / 'threads_20260928/straw'
EP = '112604454'
arm = sys.argv[1]
days = [int(x) for x in sys.argv[sys.argv.index('--days') + 1].split(',')] if '--days' in sys.argv else None
m = json.loads((R / 'sector_20260925/multi' / arm / f'{EP}.json').read_text(encoding='utf-8'))
b = json.loads((R / 'sector_20260925/multi/KS1fl' / f'{EP}.json').read_text(encoding='utf-8'))
dv = json.load(open(O / f'deliv_{arm}.json'))
cw = json.load(open(O / f'case_{arm}.json'))
cwb = json.load(open(O / 'case_KS1fl.json'))
ST = set()
for u in dv[arm]['units'] + dv['leader']['units']:
    if u['p'] == 'STRAWBERRY' and u['tile']:
        ST.add(u['tile'][1] * 10 + u['tile'][0])
sales = defaultdict(list)
for e in cw[arm]['sales']:
    if e[1] == 'us' and e[2] == 'SELL':
        sales[(e[0], e[3])].append(e[4])
ev_by = defaultdict(list)
for e in dv[arm]['events']:
    ev_by[(e['t'], e['unit'])].append(e)
money_a, money_b = m['money'], b['money']
print(f'{arm}: daily margin difference vs KS1fl (morning of day d):')
print('  ' + ' '.join(f"d{d}:{(money_a[d][0] - money_a[d][1]) - (money_b[d][0] - money_b[d][1]):+.0f}" for d in sorted(money_a, key=int)))
diff = [t for t in range(264, 719) if json.dumps(json.load(open(R / f'day12_viz/{arm.lower()}_streams/{EP}.json'))['actions'][t], sort_keys=True)
        != json.dumps(json.load(open(R / f'day12_viz/ks1fl_streams/{EP}.json'))['actions'][t], sort_keys=True)] if False else None
for d, td in sorted(m['tier_days'].items(), key=lambda x: int(x[0])):
    d = int(d)
    rets = [u for u in td['units'] if u.get('sret')]
    if not rets or (days and d not in days):
        continue
    print(f'== day {d}: {len(rets)} return(s) planned')
    for u in rets:
        uu = u['u']
        info = u['sret']        # [arrival at search, units, value, added h, moves, arrival final plan, deadline]
        ex = td['exec'][str(uu)]
        done = ex['done']
        sret_done = [x for x in done if x[2] == 'SRET']
        hv = [(x[0], x[1]) for x in done if x[2] == 'HARVEST' and x[1] in ST]
        t_ret = d * 24 + sret_done[0][0] if sret_done else None
        before = [h for h in hv if sret_done and h[0] < sret_done[0][0]]
        evs = ev_by.get((t_ret, uu), []) if t_ret else []
        dropped = {e['p']: e['n'] for e in evs}
        sp = sales.get((t_ret, 'STRAWBERRY'), []) if t_ret else []
        print(f"  u{uu}: plan: arrive h{info[-2]} (search h{info[0]}, by h{info[-1]}), {info[1]} straw, value {info[2]}, +{info[3]} h, "
              f"{info[4]} stops handed over | exec: SRET at h{sret_done[0][0] if sret_done else None}, straw harvested before it "
              f"{before} (all straw harvests {hv}), dropped {dropped} (op {evs[0]['op'] if evs else None}), strawberry sold that "
              f"step: {len(sp)} @ {round(sum(sp) / len(sp)) if sp else None}")
        plan_s = [s[0] for s in u['stops']]
        print(f"      planned stops: {u['stops']}")
        bu = next((x for x in b['tier_days'][str(d)]['units'] if x['u'] == uu), None)
        if bu:
            print(f"      KS1fl u{uu} stops: {bu['stops']}")
    ob, oa = cwb['KS1fl']['ops'].get(str(d), {}), cw[arm]['ops'].get(str(d), {})
    dd = {k: oa.get(k, 0) - ob.get(k, 0) for k in set(oa) | set(ob) if oa.get(k, 0) != ob.get(k, 0)}
    print(f'  executed ops vs KS1fl that day: {dict(sorted(dd.items()))}')
    print(f"  unfinished at 23: {td.get('unfinished')}")

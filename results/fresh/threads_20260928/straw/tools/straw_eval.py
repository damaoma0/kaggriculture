"""one-world summary of arms vs KS1fl: margin, deaths, unfinished waterings, bank stop, planned / executed returns,
(mars json if present: deletions, strawberry / wool / milk margins by strategy).
usage: straw_eval.py ARM [ARM ...]"""
import json
import sys
from collections import Counter
from pathlib import Path

R = Path('C:/Users/xyygl/Documents/kaggriculture/results/fresh')
O = R / 'threads_20260928/straw'
EP = '112604454'


def one(arm):
    m = json.loads((R / 'sector_20260925/multi' / arm / f'{EP}.json').read_text(encoding='utf-8'))
    own, riv = m['money']['30']
    died = Counter()
    for d, x in m['died'].items():
        died.update(x)
    unf_w = 0
    plans = 0
    units_pl = 0
    moves = 0
    cnt = Counter()
    for d, td in m['tier_days'].items():
        for u, items in (td.get('unfinished') or {}).items():
            for it in items:
                if isinstance(it[1], list):
                    unf_w += sum(1 for c in it[1] if c and c[0] == 'WATER')
        for u in td['units']:
            if u.get('sret'):
                plans += 1
                units_pl += u['sret'][1]
                moves += u['sret'][4] if len(u['sret']) > 4 else 0
        for k, v in (td.get('cnt') or {}).items():
            if k.startswith('sret') or k.startswith('turn') or k.startswith('deliver') or k.startswith('access'):
                cnt[k] += v
    err = m.get('tier_err') or {}
    out = dict(arm=arm, own=own, rival=riv, margin=own - riv, died=dict(died), unfinished_water=unf_w,
               bank_stop='bank stop' in str(err.get('last_error', '')), errors=err.get('errors'),
               steps_over_1s=err.get('steps_over_1s'), bank_used=round(err.get('bank_used') or 0, 2),
               sret_planned=plans, sret_units_planned=units_pl, sret_moves=moves, cnt=dict(cnt))
    mj = O / f'mars_{arm}.json'
    if mj.exists():
        mm = json.loads(mj.read_text())
        out['deleted'] = sum(mm['checks']['actual']['lost_arm'].values())
        out['deleted_by'] = mm['checks']['actual']['lost_arm']
        for p in ('STRAWBERRY', 'WOOL', 'MILK'):
            out['mars_' + p] = {k: [mm[p][k]['us'][0], round(mm[p][k]['us'][1]), round(mm[p][k]['opp'][1])] for k in mm[p]}
    return out


base = one('KS1fl')
for a in ['KS1fl'] + sys.argv[1:]:
    r = one(a)
    print(f"{a:10s} own {r['own']:.0f} rival {r['rival']:.0f} margin {r['margin']:+.0f} (vs KS1fl {r['margin'] - base['margin']:+.0f}; "
          f"own {r['own'] - base['own']:+.0f}, rival {r['rival'] - base['rival']:+.0f}) | died {r['died']} | unfinished WATER "
          f"{r['unfinished_water']} | bank stop {r['bank_stop']} err {r['errors']} >1s {r['steps_over_1s']} | returns planned "
          f"{r['sret_planned']} ({r['sret_units_planned']} straw planned, {r['sret_moves']} stops handed over) | "
          + ' '.join(f'{k}={v}' for k, v in sorted(r['cnt'].items()))
          + (f" | deleted {r['deleted']} {r['deleted_by']}" if 'deleted' in r else ''))

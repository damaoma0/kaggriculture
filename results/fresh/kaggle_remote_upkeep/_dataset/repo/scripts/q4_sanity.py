"""Paired sanity table: a with-SE build vs its baseline on the same ladder-panel worlds (per-game deltas, t 95% CI).

usage: q4_sanity.py <with_SE_agent> <baseline_agent> [cycles_dir=results/fresh/lead_cycles]
Sold units / income / spend / rival from results/fresh/ladder_panel/<agent>/<ep>.json (the panel record); harvested
(produced) units per product from lead_cycles records (crop harvest events + animal harvest events) when both agents
have them for the same worlds. Reconciliation: own cash = 3,000 + income - spend (checked per game).
(Based on the coordinator's q4delta.py.)
"""
import glob
import json
import math
import os
import statistics as st
import sys
from collections import defaultdict

R = 'results/fresh/ladder_panel/'
T975 = {5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 15: 2.131, 20: 2.086}
PRODUCT_OF = {'GOOSE': 'EGG', 'COW': 'MILK', 'SHEEP': 'WOOL'}


def ci(xs):
    n = len(xs)
    m = st.mean(xs)
    if n < 2:
        return m, m, m
    t = T975.get(n - 1, 1.96)
    s = st.stdev(xs) / math.sqrt(n)
    return m, m - t * s, m + t * s


def harvested(cdir, agent, ep):
    f = os.path.join(cdir, agent, f'{ep}.json')
    if not os.path.exists(f):
        return None
    r = json.load(open(f))
    h = defaultdict(float)
    for kind, day, idx, crop, pd, y in r['events']:
        if kind == 'harvest':
            h[crop] += y
    for a, v in (r.get('animal_harvest') or {}).items():
        h[PRODUCT_OF[a]] += v
    return h


def main():
    A, B = sys.argv[1], sys.argv[2]
    cdir = sys.argv[3] if len(sys.argv) > 3 else 'results/fresh/lead_cycles'
    eps = sorted(set(os.path.basename(f) for f in glob.glob(R + A + '/*.json')) &
                 set(os.path.basename(f) for f in glob.glob(R + B + '/*.json')))
    rows = defaultdict(list)
    recon = 0
    for e in eps:
        a = json.load(open(R + A + '/' + e))
        b = json.load(open(R + B + '/' + e))
        for x in (a, b):
            recon = max(recon, abs(3000 + sum(x['revenue'].values()) - sum(x['spend'].values()) - x['final']))
        prods = sorted(set(a['revenue']) | set(b['revenue']) | set(a['sold']) | set(b['sold']))
        for p in prods:
            rows[('sold', p)].append(a['sold'].get(p, 0) - b['sold'].get(p, 0))
            rows[('income', p)].append(a['revenue'].get(p, 0) - b['revenue'].get(p, 0))
        for p in sorted(set(a['rival_revenue']) | set(b['rival_revenue'])):
            rows[('rival income', p)].append(a['rival_revenue'].get(p, 0) - b['rival_revenue'].get(p, 0))
        ha, hb = harvested(cdir, A, e[:-5]), harvested(cdir, B, e[:-5])
        if ha is not None and hb is not None:
            for p in sorted(set(ha) | set(hb)):
                rows[('harvested', p)].append(ha.get(p, 0) - hb.get(p, 0))
        sp = lambda x, pre: sum(v for k, v in x['spend'].items() if k.startswith(pre))
        rows[('spend', 'land')].append(sp(a, 'BUY_LAND') - sp(b, 'BUY_LAND'))
        rows[('spend', 'wages')].append(sp(a, 'HIRE') - sp(b, 'HIRE'))
        rows[('spend', 'seeds')].append(sp(a, 'BUY_SEED') - sp(b, 'BUY_SEED'))
        rows[('spend', 'animals')].append(sp(a, 'BUY_ANIMAL') - sp(b, 'BUY_ANIMAL'))
        rows[('spend', 'bought wheat/fert')].append(sp(a, 'BUY_PRODUCT') - sp(b, 'BUY_PRODUCT'))
        rows[('spend', 'hands hired (count)')].append(a['hires']['got'] - b['hires']['got'])
        rows[('tot', 'income')].append(sum(a['revenue'].values()) - sum(b['revenue'].values()))
        rows[('tot', 'spend')].append(sum(a['spend'].values()) - sum(b['spend'].values()))
        rows[('tot', 'own cash')].append(a['final'] - b['final'])
        rows[('tot', 'rival cash')].append(a['rival'] - b['rival'])
        rows[('tot', 'margin')].append(a['margin'] - b['margin'])
        rows[('tot', 'margin better (count)')].append(1 if a['margin'] > b['margin'] else 0)
    n = len(eps)
    print(f'{A} vs {B}: {n} paired worlds; max ledger residual |3000 + income - spend - final| = {recon:.2f}')
    for sec in ('sold', 'harvested', 'income', 'rival income', 'spend', 'tot'):
        items = [(k, xs) for (s, k), xs in rows.items() if s == sec]
        if not items:
            continue
        print(f'== {sec}' + (' (units)' if sec in ('sold', 'harvested') else ''))
        if sec in ('sold', 'harvested', 'income', 'rival income'):
            items.sort(key=lambda kv: -abs(st.mean(kv[1] + [0] * (n - len(kv[1])))))
        for k, xs in items:
            xs = xs + [0] * (n - len(xs))
            m, lo, hi = ci(xs)
            print(f'  {k:24s} {m:+10.1f}  ({lo:+.0f} .. {hi:+.0f})')


if __name__ == '__main__':
    main()

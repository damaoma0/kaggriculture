"""Plan-volume variants on the 12 p2750 smoke worlds: paired margin vs y3 and vs the deploy baseline, units per product.
usage: lead_pv_report.py agent[,agent...]"""
import json
import random
import statistics as st
import sys
from collections import Counter
from pathlib import Path
P = Path(__file__).resolve().parents[1] / 'results/fresh/ladder_panel'
EPS = sorted(f.stem for f in (P / 'mgt_lead_deploy_s1').glob('*.json'))
PRODS = ('WHEAT', 'CARROT', 'MILK', 'WOOL', 'STRAWBERRY', 'TOMATO', 'MELON', 'EGG', 'FERTILIZER')


def boot(v, n=4000):
    rng = random.Random(1)
    s = sorted(st.mean(rng.choice(v) for _ in v) for _ in range(n))
    return s[int(.025 * n)], s[int(.975 * n)]


def load(a):
    return {e: json.load(open(P / a / f'{e}.json')) for e in EPS if (P / a / f'{e}.json').exists()}


def main():
    names = ['mgt_y3_cal', 'mgt_lead_deploy_s1'] + sys.argv[1].split(',')
    R = {a: load(a) for a in names}
    y, b = R['mgt_y3_cal'], R['mgt_lead_deploy_s1']
    print(f'{"build":22s} n  margin   own cash  vs y3 (95% CI)              vs deploy_s1 (95% CI)        units: ' + ' '.join(p[:5] for p in PRODS))
    for a in names:
        rows = R[a]
        eps = [e for e in EPS if e in rows]
        if not eps:
            continue
        m = st.mean(rows[e]['margin'] for e in eps)
        own = st.mean(rows[e]['final'] for e in eps)
        dy = [rows[e]['margin'] - y[e]['margin'] for e in eps]
        db = [rows[e]['margin'] - b[e]['margin'] for e in eps]
        u = Counter()
        for e in eps:
            u.update(rows[e]['sold'])
        cy = f'{st.mean(dy):+8,.0f} ({boot(dy)[0]:+7,.0f}..{boot(dy)[1]:+7,.0f})' if a != 'mgt_y3_cal' else ' ' * 27
        cb = f'{st.mean(db):+8,.0f} ({boot(db)[0]:+7,.0f}..{boot(db)[1]:+7,.0f}) {sum(x > 0 for x in db)}/{len(db)}' if a not in ('mgt_y3_cal', 'mgt_lead_deploy_s1') else ' ' * 27
        print(f'{a:22s} {len(eps):2d} {m:+8,.0f} {own:9,.0f}  {cy}  {cb}  ' + ' '.join(f'{u[p] / len(eps):5.0f}' for p in PRODS))


if __name__ == '__main__':
    main()

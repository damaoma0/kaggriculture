"""Where does the sale-PRICE gap to her native tapes come from? Offline, from leave-one-out daily series.

usage: mgt_price_gap.py <candidate> [native_agent=mgt_v2e]
Both arms must have been run with the mgt_loo.py that stores revenue_daily / units_daily. For every product:
units and average price by phase of the season (days 0-11, 12-17, 18-23, 24-29), ours vs her native tape, and the
split of the revenue difference into "sold at a different time" and "sold at a different price the same day".
"""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOO = ROOT / 'results' / 'fresh' / 'mg_tape' / 'loo'
PHASES = ((0, 12), (12, 18), (18, 24), (24, 30))
PRODUCTS = ('WOOL', 'MILK', 'EGG', 'STRAWBERRY', 'TOMATO', 'CARROT', 'WHEAT', 'MELON')


def load(agent, arm):
    out = {}
    for p in LOO.glob(f'{agent}-{arm}-*.json'):
        d = json.loads(p.read_text())
        if d.get('revenue_daily'):
            out[int(d['episode'])] = d
    return out


def per_day(d, product):
    """[(units, revenue)] sold on each day, from the cumulative end-of-day ledgers."""
    out, pu, pr = [], 0, 0
    for u, r in zip(d['units_daily'], d['revenue_daily']):
        cu, cr = u.get(product, 0), r.get(product, 0)
        out.append((cu - pu, cr - pr))
        pu, pr = cu, cr
    return out


def main():
    cand = sys.argv[1]
    native = sys.argv[2] if len(sys.argv) > 2 else 'mgt_v2e'
    a, b = load(cand, 'loo'), load(native, 'native_chassis')
    eps = sorted(set(a) & set(b))
    n = len(eps)
    print(f'{cand} (routed) vs {native} native tape: {n} worlds')
    print('product     phase   units ours/native   price ours/native   revenue diff per game')
    for k in PRODUCTS:
        tot = 0.0
        for lo, hi in PHASES:
            uo = un = ro = rn = 0.0
            for e in eps:
                da, db = per_day(a[e], k), per_day(b[e], k)
                uo += sum(x[0] for x in da[lo:hi]); ro += sum(x[1] for x in da[lo:hi])
                un += sum(x[0] for x in db[lo:hi]); rn += sum(x[1] for x in db[lo:hi])
            tot += (ro - rn) / n
            print(f'{k:<11} d{lo:>2}-{hi - 1:<2}  {uo / n:>7.1f} / {un / n:<7.1f}   {ro / max(1, uo):>6.0f} / {rn / max(1, un):<6.0f}   {(ro - rn) / n:>+8.0f}')
        print(f'{k:<11} total {tot:>+52.0f}')
    # rival's sales of the same product, by phase (does V50 sell into our days differently?)
    print('\nrival units sold per game by phase (routed game / native game):')
    for k in ('WOOL', 'MILK', 'STRAWBERRY'):
        row = []
        for lo, hi in PHASES:
            ro = rn = 0
            for e in eps:
                ua, ub = a[e]['rival_units_daily'], b[e]['rival_units_daily']
                ro += ua[min(hi, len(ua)) - 1].get(k, 0) - (ua[lo - 1].get(k, 0) if lo else 0)
                rn += ub[min(hi, len(ub)) - 1].get(k, 0) - (ub[lo - 1].get(k, 0) if lo else 0)
            row.append(f'{ro / n:.0f}/{rn / n:.0f}')
        print(f'  {k:<11}', '  '.join(row))


if __name__ == '__main__':
    main()

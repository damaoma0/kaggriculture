"""Remaining new-world gap of a deploy build vs y3 on the panel worlds, split into VOLUME (units short x y3's price:
what planting / production must fix) and PRICE (our units x (y3 price - ours): what the market layer can fix), per
product, plus the revenue gap per product by day window (from the cumulative revenue_daily snapshots).

usage: lead_newworld_gap.py [agent=mgt_lead_deploy] [ref=mgt_y3_cal] [episodes=smoke|all]
"""
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

P = Path(__file__).resolve().parents[1] / 'results/fresh/ladder_panel'
WINDOWS = ((0, 11), (12, 17), (18, 23), (24, 29))


def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else 'mgt_lead_deploy'
    ref = sys.argv[2] if len(sys.argv) > 2 else 'mgt_y3_cal'
    eps = sorted(f.stem for f in (P / agent).glob('*.json') if (P / ref / f.name).exists())
    n = len(eps)
    U, R, UR, RR = Counter(), Counter(), Counter(), Counter()
    win = {w: Counter() for w in WINDOWS}
    spend_a, spend_r = Counter(), Counter()
    nodaily = [0]
    for e in eps:
        a, r = (json.load(open(P / x / f'{e}.json')) for x in (agent, ref))
        U.update(a['sold']); R.update(a['revenue']); UR.update(r['sold']); RR.update(r['revenue'])
        spend_a.update(a['spend']); spend_r.update(r['spend'])
        ca, cr = a.get('revenue_daily') or [], r.get('revenue_daily') or []
        if not ca or not cr:
            nodaily[0] += 1
            continue
        for (lo, hi) in WINDOWS:
            for p in set(R) | set(RR):
                def at(c, i):
                    return c[min(i, len(c) - 1)].get(p, 0) if c else 0
                # snapshot i = cumulative revenue at the start of day i
                win[(lo, hi)][p] += (at(ca, hi + 1) - at(ca, lo)) - (at(cr, hi + 1) - at(cr, lo))
    if nodaily[0]:
        print(f'day windows use only the {n - nodaily[0]} worlds with daily revenue on both sides (scaled per world of all {n})')
    print(f'{agent} vs {ref}, {n} worlds; revenue {sum(R.values()) / n:,.0f} vs {sum(RR.values()) / n:,.0f} '
          f'({(sum(R.values()) - sum(RR.values())) / n:+,.0f}); spend {sum(spend_a.values()) / n:,.0f} vs {sum(spend_r.values()) / n:,.0f}')
    print(f'{"product":11s} {"units":>13s} {"price":>15s} {"rev gap":>8s} {"volume":>8s} {"price part":>10s}   '
          + '  '.join(f'd{lo}-{hi}' for lo, hi in WINDOWS))
    tv = tp = 0.0
    for p in sorted(set(R) | set(RR), key=lambda p: R[p] - RR[p]):
        pa, pr = R[p] / max(1, U[p]), RR[p] / max(1, UR[p])
        vol = (U[p] - UR[p]) * pr / n
        pri = U[p] * (pa - pr) / n
        tv += vol
        tp += pri
        print(f'{p:11s} {U[p] / n:5.0f} vs {UR[p] / n:5.0f} {pa:6.1f} vs {pr:6.1f} {(R[p] - RR[p]) / n:+8,.0f} {vol:+8,.0f} {pri:+10,.0f}   '
              + '  '.join(f'{win[w][p] / n:+7,.0f}' for w in WINDOWS))
    print(f'{"total":11s} {"":13s} {"":15s} {(sum(R.values()) - sum(RR.values())) / n:+8,.0f} {tv:+8,.0f} {tp:+10,.0f}   '
          + '  '.join(f'{sum(win[w].values()) / n:+7,.0f}' for w in WINDOWS))


if __name__ == '__main__':
    main()

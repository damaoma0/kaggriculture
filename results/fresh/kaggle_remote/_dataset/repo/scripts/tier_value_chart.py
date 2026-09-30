"""Op values as the tier planner sees them (hour-0 plans, from the run's tier_days log): every op in the planned routes
(stops_v: op, mandatory flag, tier, value) and every unplaced extra bundle (unplanned: tile, ops, bundle value), by op and
tile type (crop / animal from the arm's hour-0 board in the labor viewer json).
usage: tier_value_chart.py ARM ep[,ep...]   (needs results/fresh/labor_viz/<ep>.json with the arm's frames)"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))] if v else 0


def main():
    arm, eps = sys.argv[1], sys.argv[2].split(',')
    placed, unpl = defaultdict(list), defaultdict(list)
    for ep in eps:
        r = json.load(open(ROOT / f'results/fresh/labor_viz/{ep}.json', encoding='utf-8'))[0]
        tab = r['tiles']
        fr = {f['step']: f for f in r[arm.lower()]['frames']}
        T = json.load(open(ROOT / f'results/fresh/sector_20260925/multi/{arm}/{ep}.json'))['tier_days']
        for d, td in T.items():
            f = fr.get(int(d) * 24)
            if not f:
                continue
            b = [tab[i] if i is not None and i >= 0 else None for i in f['board']]

            def kind(i):
                t = b[i] if 0 <= i < 100 else None
                if not t:
                    return 'empty'
                return t.get('crop') or t.get('animal') or t.get('kind')
            for u in td.get('units') or []:
                for tile, ops in u.get('stops_v') or []:
                    for op, m, tier, v in ops:
                        placed[(op, kind(tile), 'mand' if m else 'opt')].append(float(v))
            for tile, ops, v in td.get('unplanned') or []:
                unpl[('+'.join(ops), kind(tile))].append(float(v))
    print(f'{arm} {",".join(eps)}: values of PLANNED ops (per op; mandatory ops carry sd_hard +5000 when survival-hard)')
    print(f'  {"op":20s} {"tile":11s} {"":4s} {"n":>5s} {"p10":>7s} {"median":>7s} {"p90":>7s}')
    for k in sorted(placed, key=lambda k: (k[0], k[1], k[2])):
        v = placed[k]
        if len(v) >= 5:
            print(f'  {k[0]:20s} {k[1]:11s} {k[2]:4s} {len(v):5d} {q(v, .1):7.0f} {q(v, .5):7.0f} {q(v, .9):7.0f}')
    print('values of UNPLACED extra bundles (the whole bundle)')
    for k in sorted(unpl, key=lambda k: -len(unpl[k])):
        v = unpl[k]
        if len(v) >= 5:
            print(f'  {k[0]:32s} {k[1]:11s} {len(v):5d} {q(v, .1):7.0f} {q(v, .5):7.0f} {q(v, .9):7.0f}')


if __name__ == '__main__':
    main()

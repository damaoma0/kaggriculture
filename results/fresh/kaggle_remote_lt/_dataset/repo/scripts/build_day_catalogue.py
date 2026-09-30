"""Day work catalogue from an arm's tier log + its labor viewer frames (the format manual_day_score / day_scorer read):
every op the planner considered that day (placed: op, mandatory flag, value, unit; unplaced bundles: value split), the
tile states at hour 0, the units (u, t0) and predicted spawn tiles.
usage: build_day_catalogue.py <labor_viz json> <ARM> <ep> <day> <out.json>"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(viz, arm, ep, day):
    r = json.load(open(viz, encoding='utf-8'))[0]
    tab = r['tiles']
    fr = {f['step']: f for f in r[arm.lower()]['frames']}
    T = json.load(open(ROOT / f'results/fresh/sector_20260925/multi/{arm}/{ep}.json'))['tier_days'][str(day)]
    f = fr[day * 24]
    b = [tab[i] if i is not None and i >= 0 else None for i in f['board']]
    cat = defaultdict(list)
    for u in T['units']:
        for tile, ops in u.get('stops_v') or []:
            for op, m, tier, v in ops:
                cat[tile].append((op, bool(m), round(v), u['u']))
    for tile, ops, v in T['unplanned']:
        for op in ops:
            cat[tile].append((op, False, round(v / len(ops)), None))

    def lab(t):
        if not isinstance(t, dict):
            return 'empty'
        k = t.get('kind')
        if k == 'PLANT':
            return f"{t['crop']} age{day - t['planted_day']} y{t.get('yield_units')}"
        if t.get('animal'):
            return f"{t['animal']} y{t.get('yield_units')}"
        return str(k)
    return {'day': day, 'units': [{'u': u['u'], 't0': u['t0']} for u in T['units']], 'spawn': T['spawn'],
            'shed': f['shed'], 'tiles': {tile: {'state': lab(b[tile]), 'ops': cat[tile]} for tile in sorted(cat)}}


def main():
    viz, arm, ep, day, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    json.dump(build(viz, arm, ep, day), open(out, 'w'), indent=0)


if __name__ == '__main__':
    main()

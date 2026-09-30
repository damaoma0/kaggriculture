"""Why a hand starts ahead of its plan (arm over the 40-world panel, days 11-28, hands only): planned start hour (t0) vs
the hour the hand first acts, the planned start-of-route pickups (plan items before the first work op) vs the pickups
done, and the planned hour of the first work op vs when it was done. Split: hand-days planned to 24 that ended early vs
the rest.
usage: panel_start_slip.py <ARM>"""
import ast
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ('WATER', 'HARVEST', 'FEED', 'CARE', 'COLLECT_FERTILIZER', 'FERTILIZE', 'PLANT', 'DIG', 'PLACE_HARVEST', 'BUILD_COOP',
        'BUILD_PASTURE', 'DELIVER', 'DROP', 'PLACE')


def lst(x):
    return ast.literal_eval(x) if isinstance(x, str) else (x or [])


if __name__ == '__main__':
    arm = sys.argv[1]
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    c = Counter()
    ex_ = []
    for g in games:
        ep = g.split(':')[1].strip()
        res = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text())
        for day, v in res['tier_days'].items():
            if not v or not v.get('exec'):
                continue
            units = {r['u']: r for r in v.get('units') or []}
            for u, e in v['exec'].items():
                u = int(u)
                if u == 0 or u not in units:
                    continue
                plan, done = lst(e.get('plan')), lst(e.get('done'))
                pw = [x for x in plan if x[1] in WORK]
                dw = [x for x in done if x[2] in WORK]
                if not pw or not dw:
                    continue
                grp = 'early' if (units[u]['end'] >= 24 and max(x[0] for x in dw) <= 22) else 'other'
                c[grp] += 1
                t0 = units[u]['t0']
                first_done = min(x[0] for x in done) if done else None
                c[grp + '_t0'] += t0
                c[grp + '_first_act'] += first_done
                c[grp + '_t0_%d' % t0] += 1
                c[grp + '_first_plan_h'] += pw[0][2]
                c[grp + '_first_done_h'] += dw[0][0]
                c[grp + '_picks_done'] += sum(1 for x in done if x[2] == 'PICKUP' and x[0] <= dw[0][0])
                c[grp + '_plan_hops'] += units[u].get('hop', 0)
                gap = pw[0][2] - dw[0][0]
                c[grp + '_gap_%s' % (min(max(gap, -1), 3))] += 1
                if grp == 'early' and gap >= 2 and len(ex_) < 5:
                    ex_.append((ep, day, u, t0, units[u].get('kind'), pw[:3], done[:4], units[u]['stops'][:2]))
    for grp in ('early', 'other'):
        m = max(1, c[grp])
        print(f'{grp}: {m / len(games):.1f} a world | planned t0 {c[grp + "_t0"] / m:.2f} (' + ', '.join(f'h{k.split("_")[-1]} {vv / m:.2f}' for k, vv in sorted(c.items()) if k.startswith(grp + '_t0_'))
              + f'), first action at {c[grp + "_first_act"] / m:.2f} | first work op planned at {c[grp + "_first_plan_h"] / m:.2f}, done at {c[grp + "_first_done_h"] / m:.2f}; '
              f'pickups done before it {c[grp + "_picks_done"] / m:.2f} | gap (planned - done) at the first job: '
              + ', '.join(f'{k.split("_")[-1]} h {vv / m:.0%}' for k, vv in sorted(c.items()) if k.startswith(grp + '_gap_')))
    for x in ex_:
        print('example', x)

"""Where a hand runs ahead of its plan (arm over the 40-world panel, days 11-28, hands only): for each hand-day, match
done work ops to planned ones in order ((tile, op) sequence) and track planned hour - done hour; report the shift at the
first matched op and how it grows along the route, the planned start (t0) vs the first action, and the steps where the
shift jumps (what the planned op before the jump was). Split: hand-days planned to 24 that ended early vs the rest.
usage: panel_plan_shift.py <ARM>"""
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
                pw = [(x[0], x[1], x[2]) for x in plan if x[1] in WORK]
                dw = [(x[1], x[2], x[0]) for x in done if x[2] in WORK]
                if not pw or not dw:
                    continue
                early = units[u]['end'] >= 24 and max(x[2] for x in dw) <= 22
                grp = 'early' if early else 'other'
                c[grp] += 1
                # in-order match
                j = 0
                shifts = []
                prev_op = None
                for t, o, hp in pw:
                    k = next((i for i in range(j, len(dw)) if dw[i][0] == t and dw[i][1] == o), None)
                    if k is None:
                        prev_op = o
                        continue
                    shifts.append((hp - dw[k][2], o, prev_op, t))
                    prev_op = o
                    j = k + 1
                if not shifts:
                    continue
                c[grp + '_first'] += shifts[0][0]
                c[grp + '_last'] += shifts[-1][0]
                c[grp + '_t0'] += units[u]['t0']
                c[grp + '_n'] += 1
                for i in range(1, len(shifts)):
                    dj = shifts[i][0] - shifts[i - 1][0]
                    if dj >= 1:
                        c[grp + '_jumps'] += dj
                        c[grp + '|jump_after|' + str(shifts[i][2])] += dj
                    elif dj <= -1:
                        c[grp + '_backs'] += -dj
                if shifts[0][0] >= 1:
                    c[grp + '|first_ahead'] += 1
    for grp in ('early', 'other'):
        m = max(1, c[grp + '_n'])
        print(f'{grp}: {c[grp] / len(games):.1f} hand-days a world | planned - done hour at the first job {c[grp + "_first"] / m:.2f}, at the last job '
              f'{c[grp + "_last"] / m:.2f} (first job already >= 1 h ahead on {c[grp + "|first_ahead"] / m:.0%}); gained along the route '
              f'{c[grp + "_jumps"] / m:.2f} h, lost {c[grp + "_backs"] / m:.2f} h')
        print('   hours gained right after a planned op of type: ' + ', '.join(f'{k.split("|")[2]} {vv / m:.2f}' for k, vv in sorted(c.items(), key=lambda kv: -kv[1])
                                                                     if k.startswith(grp + '|jump_after|')))

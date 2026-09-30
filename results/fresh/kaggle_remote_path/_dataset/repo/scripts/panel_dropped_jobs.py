"""Planned jobs a hand never did (arm over the 40-world panel, days 11-28, hands only), from the executor summaries
(tier_days[day].exec[u]: plan = [tile, op, planned hour], done = [hour, tile, op]). For every hand-day: planned vs done
work ops, the planned ops missing from done, and whether ANOTHER unit did that (tile, op) the same day (double
assignment / done by someone else first) or not at all; the hand's actual last work hour vs its planned last hour.
Split by hand-days that ended early (idle after the last job, planned to 24) and the rest.
usage: panel_dropped_jobs.py <ARM>"""
import ast
import json
import sys
from collections import Counter, defaultdict
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
            ends = {r['u']: r['end'] for r in v.get('units') or []}
            done_all = defaultdict(set)                   # (tile, op) -> units that did it
            ex = {}
            for u, e in v['exec'].items():
                u = int(u)
                try:
                    plan, done = lst(e.get('plan')), lst(e.get('done'))
                except (ValueError, SyntaxError):
                    c['parse_fail'] += 1
                    continue
                ex[u] = (plan, done)
                for x in done:
                    done_all[(x[1], x[2])].add(u)
            for u, (plan, done) in ex.items():
                if u == 0:
                    continue
                pw = [(x[0], x[1], x[2]) for x in plan if x[1] in WORK]
                dw = [(x[1], x[2], x[0]) for x in done if x[2] in WORK]
                if not pw:
                    continue
                last_plan = max(x[2] for x in pw)
                last_done = max((x[2] for x in dw), default=-1)
                early = ends.get(u, 0) >= 24 and last_done <= 22
                grp = 'early' if early else 'other'
                c[grp] += 1
                c[grp + '_planned'] += len(pw)
                c[grp + '_done'] += len(dw)
                left = Counter((t, o) for t, o, _ in dw)
                for t, o, hp in pw:
                    if left[(t, o)] > 0:
                        left[(t, o)] -= 1
                        continue
                    c[grp + '_missing'] += 1
                    who = done_all.get((t, o), set()) - {u}
                    why = 'done by another unit' if who else 'done by nobody'
                    c[grp + '|' + why] += 1
                    c[grp + '|' + why + '|' + o] += 1
                    c[grp + '_miss_hour'] += hp
                c[grp + '_shift'] += last_plan - last_done
                c[grp + '_extra'] += sum(left.values())
    n = len(games)
    for grp, lab in (('early', 'hand-days planned to 24 that ended early'), ('other', 'all other hand-days')):
        m = max(1, c[grp])
        print(f'{lab}: {c[grp] / n:.1f} a world | planned work ops {c[grp + "_planned"] / m:.1f}, done {c[grp + "_done"] / m:.1f}, '
              f'planned but not done {c[grp + "_missing"] / m:.2f} (at planned hour {c[grp + "_miss_hour"] / max(1, c[grp + "_missing"]):.1f}), '
              f'done but not planned {c[grp + "_extra"] / m:.2f}; last planned job - last done job {c[grp + "_shift"] / m:.2f} h')
        for why in ('done by another unit', 'done by nobody'):
            k = grp + '|' + why
            print(f'   {why:22s} {c[k] / m:.2f} a hand-day: ' + ', '.join(f'{x.split("|")[2]} {vv / m:.2f}' for x, vv in sorted(c.items(), key=lambda kv: -kv[1])
                                                                    if x.startswith(k + '|')))
    if c['parse_fail']:
        print('parse failures', c['parse_fail'])

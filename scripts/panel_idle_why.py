"""Why the tier plan leaves hands idle (arm, from its tier_days log and the labor viewer frames): for every hand-day, the
planned end hour and the last executed op; idle hours split into planned short (route ends before 24) and finished early
(planned to 24, executed less). For planned-short routes: the hand's kind, the free hours, and the unplaced extras
(the log's `unplanned` bundles) that were within reach of the route's last stop (Manhattan steps + op hours <= free
hours), by op, value and whether their tile belonged to another hand's route that day (the fills' owner rule).
Also: wheat waters by plant age (arm and leader), from the frames.
usage: panel_idle_why.py ARM ep[,ep...]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def man(a, b):
    return abs(a % 10 - b % 10) + abs(a // 10 - b // 10)


def wheat_water_ages(frames, tab):
    ages = Counter()
    prev = None
    for f in frames:
        b = [tab[i] if i is not None and i >= 0 else None for i in f['board']]
        if prev is not None and f['step'] // 24 >= 11:
            day = (f['step'] - 1) // 24
            for i in range(100):
                p, c = prev[i], b[i]
                if (p and c and p.get('kind') == 'PLANT' and p.get('crop') == 'WHEAT' and c.get('planted_day') == p.get('planted_day')
                        and c.get('watered_today') and not p.get('watered_today')):
                    ages[day - p['planted_day']] += 1
                elif (c and c.get('kind') == 'PLANT' and c.get('crop') == 'WHEAT' and c.get('watered_today')
                      and not (p and p.get('kind') == 'PLANT' and p.get('planted_day') == c.get('planted_day'))):
                    ages[0] += 1
        prev = b
    return ages


def main():
    arm, eps = sys.argv[1], sys.argv[2].split(',')
    n_w = len(eps)
    idle = Counter()
    kinds = Counter()
    reach = Counter()
    reach_v = defaultdict(list)
    free_h = Counter()
    nothing = 0
    wa_arm, wa_lead = Counter(), Counter()
    for ep in eps:
        T = json.load(open(ROOT / f'results/fresh/sector_20260925/multi/{arm}/{ep}.json'))['tier_days']
        r = json.load(open(ROOT / f'results/fresh/labor_viz/{ep}.json', encoding='utf-8'))[0]
        wa_arm.update(wheat_water_ages(r[arm.lower()]['frames'], r['tiles']))
        wa_lead.update(wheat_water_ages(r['leader']['frames'], r['tiles']))
        for d, td in T.items():
            if int(d) >= 29:
                continue
            units = {str(u['u']): u for u in td.get('units') or []}
            owner = {}
            for u in td.get('units') or []:
                for tile, ops in u.get('stops') or []:
                    owner.setdefault(tile, u['u'])
            unpl = td.get('unplanned') or []
            for uk, e in (td.get('exec') or {}).items():
                u = units.get(uk)
                if not u:
                    continue
                done = e.get('done') or []
                work = [x for x in done if x[2] not in ('PICKUP', 'DROP', 'PASS')]
                last = max((x[0] for x in work), default=None)
                if last is None:
                    continue
                idle_h = max(0, 23 - last)
                if idle_h <= 0:
                    continue
                end = int(u.get('end', 24))
                if end < 24:
                    idle['planned short'] += min(idle_h, 24 - end)
                    idle['finished earlier than planned'] += max(0, idle_h - (24 - end))
                    kinds[u.get('kind')] += min(idle_h, 24 - end)
                    fh = 24 - end
                    free_h[min(fh, 5)] += 1
                    stops = u.get('stops') or []
                    t_end = stops[-1][0] if stops else 44
                    got = False
                    for tile, ops, v in unpl:
                        if man(t_end, tile) + len(ops) <= fh:
                            own = owner.get(tile)
                            tag = 'another hand owns the tile' if (own is not None and own != u['u']) else 'free tile'
                            key = ('+'.join(sorted(set(ops))), tag)
                            reach[key] += 1
                            reach_v[key].append(v)
                            got = True
                    if not got:
                        nothing += 1
                else:
                    idle['finished earlier than planned'] += idle_h
    tot = sum(idle.values())
    print(f'{arm}, {n_w} worlds, per world: idle hand-hours after the last work op {tot / n_w:.0f}')
    for k, v in idle.items():
        print(f'   {k:32s} {v / n_w:6.0f} h')
    print('   planned-short hours by hand kind:', {k: round(v / n_w) for k, v in kinds.most_common()})
    print('   planned-short hand-days by free hours (5 = 5+):', {k: round(v / n_w, 1) for k, v in sorted(free_h.items())})
    print(f'   planned-short hand-days with NO unplaced extra within reach of the route end: {nothing / n_w:.1f}')
    print('   unplaced extras within reach of a planned-short route end (hand-day x extra, per world; median value):')
    for k, v in reach.most_common(14):
        vals = sorted(reach_v[k])
        print(f'      {k[0]:28s} {k[1]:28s} {v / n_w:6.1f}   median {vals[len(vals) // 2]:.0f}')
    print('wheat waters by plant age, per world (age 0 = planting day):')
    for a in range(0, 6):
        print(f'   age {a}: leader {wa_lead[a] / n_w:6.1f}   {arm} {wa_arm[a] / n_w:6.1f}')


if __name__ == '__main__':
    main()

"""Daytime shed visits over the 40-world panel (days 11-28), the leader vs arms. A visit = a unit exchanges goods with the
shed (DROP or PICKUP) at hours 2-22 after having been 2+ steps from the shed since its last exchange (the hour-1..3
loading at the start of a hand's day is not a visit). Per visit: deposit only / pickup only / both, the units it drops
(the unit's inventory decrease), whether the unit goes out again or ends its day there, and the hour. Also the
morning loading (exchanges before the first excursion) for comparison.
usage: panel_shed_visits.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]


def dist(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    far = {}
    seen = set()
    vis = {}                                            # open visit per (day, unit): [hour, deposit, pickup, units dropped]

    def close(key, final):
        v = vis.pop(key, None)
        if v is None:
            return
        kind = 'both' if v[1] and v[2] else 'deposit' if v[1] else 'pickup'
        tag = 'final' if final else 'mid'
        c[f'v_{tag}_{kind}'] += 1
        c[f'u_{tag}_{kind}'] += v[3]
        for it, dq in v[4:]:
            c[f'p_{tag}_{it}'] += dq
        c['vh_%02d' % v[0]] += 1

    while w.t < 696:
        t = w.t
        d, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        drops = []
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            inv0 = [dict(x or {}) for x in w.private(seat)['inventories']]
            for u, p in enumerate(units):
                if (d, u) not in seen:
                    seen.add((d, u))
                    far[(d, u)] = False
                    c['hand_days'] += 1
                if dist(p) >= 2:
                    far[(d, u)] = True
                    close((d, u), False)
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                if op in ('DROP', 'PICKUP') and 1 <= h <= 22:
                    if far[(d, u)] and h >= 2:
                        if (d, u) not in vis:
                            vis[(d, u)] = [h, False, False, 0]
                            c['visits'] += 1
                        far[(d, u)] = False
                    v = vis.get((d, u))
                    if v is not None:
                        v[1 if op == 'DROP' else 2] = True
                        if op == 'DROP':
                            drops.append((u, inv0[u] if u < len(inv0) else {}))
                    else:
                        c['load_' + op] += 1           # before the first excursion: morning loading
                        if op == 'PICKUP':
                            c['lp_%s' % (cm[1] if len(cm) > 1 else '?')] += 1
                            c['lph_%02d' % h] += 1
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
        if drops:
            inv1 = [dict(x or {}) for x in w.private(seat)['inventories']]
            for u, i0 in drops:
                if (d, u) in vis and u < len(inv1):
                    for it, q in i0.items():
                        dq = max(0, int(q) - int(inv1[u].get(it, 0)))
                        vis[(d, u)][3] += dq
                        vis[(d, u)].append((it, dq))
        if t >= 264 and h == 23:
            for key in [k for k in vis if k[0] == d]:
                close(key, True)
    return arm, dict(c)


if __name__ == '__main__':
    arms = ['DSM'] + sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, c in pool.imap_unordered(job, [(g, a) for a in arms for g in games]):
            tot[arm].update(c)
    n = len(games)
    for a in arms:
        c = tot[a]
        print(f'{a}: daytime shed visits {c["visits"] / n:.1f} a world ({c["visits"] / max(1, c["hand_days"]):.2f} a hand-day, {c["hand_days"] / n:.0f} hand-days) | '
              f'morning loading: {c["load_PICKUP"] / n:.1f} pickups, {c["load_DROP"] / n:.1f} drops')
        for tag, lab in (('mid', 'then out again'), ('final', 'ends the day   ')):
            print(f'     {lab}: ' + ', '.join(f'{k} {c.get(f"v_{tag}_{k}", 0) / n:.1f} visits / {c.get(f"u_{tag}_{k}", 0) / n:.0f} units dropped'
                                             for k in ('deposit', 'pickup', 'both')))
        for tag in ('mid', 'final'):
            print(f'     dropped ({tag}): ' + ', '.join(f'{k[len(tag) + 3:]} {v / n:.1f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith(f'p_{tag}_') and v))
        print('     morning pickups by item: ' + ', '.join(f'{k[3:]} {v / n:.1f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('lp_'))
              + ' | by hour: ' + ', '.join(f'{int(k[4:])}:{v / n:.1f}' for k, v in sorted(c.items()) if k.startswith('lph_')))
        print('     visits by hour: ' + ', '.join(f'{h}:{c.get("vh_%02d" % h, 0) / n:.1f}' for h in range(2, 23) if c.get("vh_%02d" % h, 0)))

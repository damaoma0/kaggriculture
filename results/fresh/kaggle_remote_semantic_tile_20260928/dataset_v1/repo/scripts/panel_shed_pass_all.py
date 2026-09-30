"""Free mid-day drop opportunities: over the 40-world panel, for every hand-day of the arm (or DSM), the first step in
hours 2-20 where the hand stands ON a shed tile (a drop costs 1 hour) or next to one (a drop costs ~3 hours) while
carrying >= k units of sellable goods (strawberry, milk, wool, egg, melon, carrot, tomato), after having been 2+ steps
away. Per world: hand-days carrying goods mid-day, passes on / next to the shed, units carried at the pass, the hour,
whether the hand dropped there, and the units those hands still carried into the midnight dump.
usage: panel_shed_pass_all.py <ARM>[,<ARM>...] [--k 3] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
GOODS = ('STRAWBERRY', 'MILK', 'WOOL', 'EGG', 'MELON', 'CARROT', 'TOMATO')


def dist(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def job(args):
    g, arm, k = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    carrying, far, first = set(), {}, {}
    eod = {}
    while w.t < 719:
        t = w.t
        d, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if t < len(s) and isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            invs = w.private(seat)['inventories']
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, pos in enumerate(units):
                inv = invs[u] if u < len(invs) else {}
                n = sum(int(inv.get(p, 0) or 0) for p in GOODS)
                dd = dist(pos)
                if dd >= 2:
                    far[(d, u)] = True
                if 2 <= h <= 20 and n >= k:
                    carrying.add((d, u))
                    for lim in (0, 1):
                        key = (d, u, lim)
                        if dd <= lim and far.get((d, u)) and key not in first:
                            cm = cmds[u] if u < len(cmds) else None
                            first[key] = (h, n, isinstance(cm, list) and bool(cm) and cm[0] == 'DROP')
                if h == 23:
                    eod[(d, u)] = sum(int(inv.get(p, 0) or 0) for p in GOODS)
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c['carry_days'] = len(carrying)
    for lim in (0, 1):
        ks = [key for key in first if key[2] == lim]
        c[f'pass{lim}_days'] = len(ks)
        c[f'pass{lim}_units'] = sum(first[key][1] for key in ks)
        c[f'pass{lim}_hour'] = sum(first[key][0] for key in ks)
        c[f'pass{lim}_drop'] = sum(first[key][2] for key in ks)
        c[f'pass{lim}_eod'] = sum(eod.get(key[:2], 0) for key in ks)
    c['eod_all'] = sum(eod.values())
    return arm, dict(c)


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    k = int(sys.argv[sys.argv.index('--k') + 1]) if '--k' in sys.argv else 3
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, r in pool.imap_unordered(job, [(g, a, k) for a in arms for g in games]):
            tot[arm].update(r)
    n = len(games)
    for a in arms:
        c = tot[a]
        print(f'{a}: hand-days carrying >= {k} goods at hours 2-20: {c["carry_days"] / n:.1f} a world | goods carried into the midnight dump (all hands) {c["eod_all"] / n:.0f}')
        for lim, lab in ((0, 'ON a shed tile'), (1, 'on / next to  ')):
            m = max(1, c[f'pass{lim}_days'])
            print(f'     pass {lab}: {c[f"pass{lim}_days"] / n:.1f} hand-days, {c[f"pass{lim}_units"] / m:.1f} units at the pass, hour {c[f"pass{lim}_hour"] / m:.1f}, '
                  f'dropped there {c[f"pass{lim}_drop"] / n:.1f}; those hands still carried {c[f"pass{lim}_eod"] / n:.0f} units into the dump')

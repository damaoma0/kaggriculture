"""Uncollected (lost) fertilizer over the 40-world panel, days 11-28: the engine sets an animal's fertilizer_available
at every end of day and does not accumulate it, so an animal still flagged at the next end of day lost that day's
fertilizer. Per world, for the leader and arms: lost units by animal, by distance of the pen from the shed, by day, and
the share of animal-days collected.
usage: panel_fert_uncollected.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
R = {'farm': None, 'c': None}
_ra = E._daily_refresh_animals


def ra(farm, day):
    if farm is R['farm'] and day >= 11:
        c = R['c']
        for y, row in enumerate(farm['tiles']):
            for x, t in enumerate(row):
                if isinstance(t, dict) and 'animal' in t and day >= t.get('placed_day', 0) + 1:
                    c['animal_days'] += 1
                    if t.get('fertilizer_available'):
                        d = min(abs(x - a) + abs(y - b) for a, b in SHED)
                        c['lost'] += 1
                        c['lost|' + t['animal']] += 1
                        c['lostd|%d' % min(d, 5)] += 1
                        c['lostday|%d' % day] += 1
    return _ra(farm, day)


E._daily_refresh_animals = ra


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    R.update(c=c)
    while w.t < 696:
        t = w.t
        R['farm'] = w.farms[seat]
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
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
        print(f'{a}: fertilizer lost uncollected {c["lost"] / n:.1f} a world of {c["animal_days"] / n:.0f} animal-days '
              f'({100 * (1 - c["lost"] / max(1, c["animal_days"])):.0f}% collected) | by animal ' +
              ', '.join(f'{k.split("|")[1]} {v / n:.1f}' for k, v in sorted(c.items()) if k.startswith('lost|')) +
              ' | by pen distance from the shed ' + ', '.join(f'{k.split("|")[1]}: {c[k] / n:.1f}' for k in sorted(c) if k.startswith('lostd|')))
        print('     by day: ' + ', '.join(f'{d}:{c.get("lostday|%d" % d, 0) / n:.1f}' for d in range(11, 29)))

"""Idle (wasted) unit-hours over the 40-world panel, days 11-28, for the leader's recorded game and arms: every unit that
exists at a step and is given PASS (or no command) counts one idle hour. Split by hour of day, by where it falls in the
unit's day (before its first action, between actions, after its last action), by distance from the shed, and by idle
hours per unit-day. Also no-effect ops (a command that changed nothing). Writes JSON for the chart.
usage: panel_idle.py <out.json> <ARM>[,<ARM>...] [--workers 4] [--games team:ep,...] [--d0 11]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]


def job(args):
    g, arm, d0 = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    days = defaultdict(list)                         # (day, unit) -> [(hour, idle?, dist)]
    while w.t < 696:
        t = w.t
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= d0 * 24:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                c = cmds[u] if u < len(cmds) else None
                idle = not (isinstance(c, list) and c and c[0] != 'PASS')
                days[(t // 24, u)].append((t % 24, idle, min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c = Counter()
    for (d, u), L in days.items():
        L.sort()
        act = [h for h, idle, _ in L if not idle]
        first, last = (min(act), max(act)) if act else (99, -1)
        n = 0
        for h, idle, dist in L:
            if not idle:
                continue
            n += 1
            c['h%02d' % h] += 1
            c['where|' + ('before' if h < first else ('after' if h > last else 'between'))] += 1
            c['dist|%d' % min(dist, 6)] += 1
            c['total'] += 1
        c['perday|%d' % min(n, 6)] += 1
        c['unitdays'] += 1
    return arm, dict(c)


if __name__ == '__main__':
    out, arms = sys.argv[1], ['DSM'] + sys.argv[2].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    if '--games' in sys.argv:                    # a subset of worlds (team:ep,...)
        games = sys.argv[sys.argv.index('--games') + 1].split(',')
    d0 = int(sys.argv[sys.argv.index('--d0') + 1]) if '--d0' in sys.argv else 11   # first day counted
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, c in pool.imap_unordered(job, [(g, a, d0) for a in arms for g in games]):
            tot[arm].update(c)
    n = len(games)
    res = {a: {k: v / n for k, v in c.items()} for a, c in tot.items()}
    Path(out).write_text(json.dumps(res, indent=1), encoding='utf-8')
    for a in arms:
        r = res[a]
        print(f'{a}: idle {r.get("total", 0):.1f} unit-hours a world | before first action {r.get("where|before", 0):.1f}, between {r.get("where|between", 0):.1f}, '
              f'after last {r.get("where|after", 0):.1f}')

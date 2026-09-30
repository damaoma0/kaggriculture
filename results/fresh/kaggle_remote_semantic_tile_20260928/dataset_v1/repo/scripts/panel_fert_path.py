"""Uncollected fertilizer vs the hands' paths (the leader or an arm over the 40-world panel, days 11-28): a pen-day whose
fertilizer is still waiting at the end of the day is lost (the engine resets fertilizer_available each night). For each
lost pen-day: did a hand WORK the pen that day (feed / care / harvest, no collect), stand on it without working (walked
through), pass next to it (1 step), or come nowhere near; the pen's distance from the shed; whether a hand that stood on
it ended its day idle (the collect hour was free).
usage: panel_fert_path.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST')
NONWORK = MOVES + ('PASS', 'DROP', 'PICKUP', 'PLACE')


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dsh(p):
    return min(d(p, s) for s in SHED)


def job2(args):
    """lost pen-day = fertilizer available at hour 0 and no successful COLLECT that day."""
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    on = defaultdict(set)
    wk = defaultdict(set)
    near = defaultdict(set)
    lastw = {}
    passed = defaultdict(list)
    avail = {}
    collected = set()
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        pre = None
        if t >= 264:
            farm = w.farms[seat]
            if h == 0:
                avail[dd] = {(x, y) for y in range(10) for x in range(10)
                             if isinstance(farm['tiles'][y][x], dict) and farm['tiles'][y][x].get('fertilizer_available')}
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            pre = []
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                on[(dd, p)].add(u)
                for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)):
                    near[(dd, q)].add(u)
                if op not in NONWORK:
                    wk[(dd, p)].add(u)
                    lastw[(dd, u)] = h
                elif op == 'PASS':
                    passed[(dd, u)].append(h)
                if op == 'COLLECT_FERTILIZER':
                    tl = farm['tiles'][p[1]][p[0]]
                    if isinstance(tl, dict) and tl.get('fertilizer_available'):
                        pre.append(p)
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
        if pre:
            for p in pre:
                collected.add((dd, p))
        if t >= 264 and h == 23:
            idle_end = {u for (d0, u), hs in passed.items() if d0 == dd and any(x > lastw.get((d0, u), -1) for x in hs)}
            for q in avail.get(dd, ()):
                c['pen_days'] += 1
                if (dd, q) in collected:
                    continue
                c['lost'] += 1
                c['lost_d%d' % min(dsh(q), 4)] += 1
                ws, os_, ns = wk[(dd, q)], on[(dd, q)] - wk[(dd, q)], near[(dd, q)] - on[(dd, q)]
                if ws:
                    k = 'worked (feed / care / harvest), no collect'
                    c['worked_by_idle_hand'] += bool(ws & idle_end)
                elif os_:
                    k = 'walked over, no work'
                    c['walked_by_idle_hand'] += bool(os_ & idle_end)
                elif ns:
                    k = 'passed 1 step away'
                    c['near_by_idle_hand'] += bool(ns & idle_end)
                else:
                    k = 'no hand within 1 step'
                c['k|' + k] += 1
    return arm, dict(c)


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, c in pool.imap_unordered(job2, [(g, a) for a in arms for g in games]):
            tot[arm].update(c)
    n = len(games)
    for a in arms:
        c = tot[a]
        print(f'{a}: pen-days with fertilizer {c["pen_days"] / n:.0f} a world, lost (never collected that day) {c["lost"] / n:.1f} | by distance from the shed: '
              + ', '.join(f'{k[6:]}{"+" if k == "lost_d4" else ""} steps {v / n:.1f}' for k, v in sorted(c.items()) if k.startswith('lost_d')))
        for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
            if k.startswith('k|'):
                print(f'   {k[2:]:45s} {v / n:5.1f}')
        print(f'   ...of those, a hand that ended its day idle: worked it {c["worked_by_idle_hand"] / n:.1f}, walked over it {c["walked_by_idle_hand"] / n:.1f}, '
              f'passed next to it {c["near_by_idle_hand"] / n:.1f}')

"""Where hand-hours go, the leader vs arms over the 40-world panel (days 11-28): per world, unit-hours moving / working /
shed exchange / PASS; work ops by type; moves per work op; the spread of a hand-day's work tiles (mean distance of its work
tiles from their centroid) and the first work tile's distance from the shed.
usage: panel_hand_time.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST')


def dsh(p):
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
    wt = {}
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                if op in MOVES:
                    c['move'] += 1
                elif op == 'PASS':
                    c['pass'] += 1
                elif op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE')):
                    c['shed'] += 1
                else:
                    c['work'] += 1
                    c['op_' + op] += 1
                    wt.setdefault((dd, u), []).append(p)
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    for key, ps in wt.items():
        cx = sum(p[0] for p in ps) / len(ps)
        cy = sum(p[1] for p in ps) / len(ps)
        c['spread'] += sum(abs(p[0] - cx) + abs(p[1] - cy) for p in ps) / len(ps)
        c['first_d'] += dsh(ps[0])
        c['tiles'] += len(set(ps))
        c['wdays'] += 1
    return arm, dict(c)


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (__import__('os').environ.get('PANEL_GAMES') or (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text()).replace(',', ' ').split()
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, c in pool.imap_unordered(job, [(g, a) for a in arms for g in games]):
            tot[arm].update(c)
    n = len(games)
    for a in arms:
        c = tot[a]
        m = max(1, c['wdays'])
        print(f'{a}: unit-hours a world: move {c["move"] / n:.0f}, work {c["work"] / n:.0f}, shed {c["shed"] / n:.0f}, pass {c["pass"] / n:.0f} | moves per work op '
              f'{c["move"] / max(1, c["work"]):.2f} | per working hand-day ({m / n:.0f} a world): {c["tiles"] / m:.1f} tiles, spread {c["spread"] / m:.2f}, '
              f'first work {c["first_d"] / m:.1f} steps from the shed')
        print('     ops: ' + ', '.join(f'{k[3:]} {v / n:.0f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('op_')))

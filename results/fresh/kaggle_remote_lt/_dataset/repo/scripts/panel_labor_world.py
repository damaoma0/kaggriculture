"""Labor loss per world, an arm vs the leader over the 40-world panel (days 11-28): work ops, moves, idle and shed
unit-hours for both, sorted by the work deficit (leader - arm).
usage: panel_labor_world.py <ARM> [--workers 4] [--top 10]"""
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


def count(tape, s):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    while w.t < 696:
        t = w.t
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
                    c['idle'] += 1
                elif op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE')):
                    c['shed'] += 1
                else:
                    c['work'] += 1
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    return c


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    res = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text())
    m = res['money']['30']
    return g.strip(), count(tape, None), count(tape, s), m[0] - m[1], tape['rewards'][tape['seat']] - tape['rewards'][1 - tape['seat']]


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 10
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    rows = []
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm) for g in games]):
            rows.append(r)
    rows.sort(key=lambda r: -(r[1]['work'] - r[2]['work']))
    print(f'{arm} vs DSM, days 11-28, unit-hours: world | work DSM / ours (deficit) | idle DSM / ours | moves DSM / ours | margin ours / DSM')
    for g, L, A, mA, mL in rows[:top]:
        print(f'   {g} | {L["work"]} / {A["work"]} ({L["work"] - A["work"]:+d}) | {L["idle"]} / {A["idle"]} | {L["move"]} / {A["move"]} | {mA:+.0f} / {mL:+.0f}')
    n = len(rows)
    print(f'   mean deficit {sum(r[1]["work"] - r[2]["work"] for r in rows) / n:+.1f}, worlds with a deficit {sum(1 for r in rows if r[1]["work"] > r[2]["work"])}/{n}')

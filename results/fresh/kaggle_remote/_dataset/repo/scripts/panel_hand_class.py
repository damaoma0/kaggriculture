"""Farming hands vs animal hands, the leader vs arms over the 40-world panel (days 11-28). A hand-day is a FARMING hand
if >= 80% of its work ops are on crop tiles, an ANIMAL hand if >= 80% are on pens, else MIXED. Per class: hand-days a
world, steps walked, tiles worked, work ops, ops per worked tile, idle hours, first / last work hour, op mix, and ops per
visit by tile kind.
usage: panel_hand_class.py <ARM>[,<ARM>...] [--workers 4]"""
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
PENS = ('COW', 'SHEEP', 'GOOSE')
CLS = ('farming', 'mixed', 'animal')


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
    hd = defaultdict(list)
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
                    hd[(dd, u)].append((h, 'move', None, None))
                elif op == 'PASS':
                    hd[(dd, u)].append((h, 'pass', None, None))
                elif op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in PENS):
                    hd[(dd, u)].append((h, 'shed', None, None))
                else:
                    tl = farm['tiles'][p[1]][p[0]]
                    kd = (tl.get('animal') or tl.get('crop') or tl.get('kind')) if isinstance(tl, dict) else 'EMPTY'
                    hd[(dd, u)].append((h, 'work', op, (p, kd)))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c = Counter()
    for (dd, u), ev in hd.items():
        if u == 0:
            continue
        wk = [x for x in ev if x[1] == 'work']
        if not wk:
            continue
        pen = sum(1 for x in wk if x[3][1] in PENS)
        f = pen / len(wk)
        cl = 'animal' if f >= 0.8 else ('farming' if f <= 0.2 else 'mixed')
        c[cl] += 1
        c[cl + '|steps'] += sum(1 for x in ev if x[1] == 'move')
        c[cl + '|idle'] += sum(1 for x in ev if x[1] == 'pass')
        c[cl + '|shed'] += sum(1 for x in ev if x[1] == 'shed')
        c[cl + '|ops'] += len(wk)
        c[cl + '|tiles'] += len(set(x[3][0] for x in wk))
        c[cl + '|first'] += wk[0][0]
        c[cl + '|last'] += wk[-1][0]
        for x in wk:
            c[cl + '|op|' + x[2]] += 1
        vis = defaultdict(list)
        for x in wk:
            vis[x[3]].append(x[2])
        for (p, kd), ops in vis.items():
            k2 = kd if kd in PENS + ('STRAWBERRY', 'WHEAT', 'TOMATO', 'CARROT') else 'other'
            c[cl + '|v|' + k2] += 1
            c[cl + '|vo|' + k2] += len(ops)
    return arm, dict(c)


if __name__ == '__main__':
    arms = sys.argv[1].split(',')
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {a: Counter() for a in arms}
    with Pool(nw) as pool:
        for arm, c in pool.imap_unordered(job, [(g, a) for a in arms for g in games]):
            tot[arm].update(c)
    n = len(games)
    for a in arms:
        c = tot[a]
        print(f'\n{a}:')
        for cl in CLS:
            m = max(1, c[cl])
            print(f'   {cl:8s}: {c[cl] / n:5.1f} hand-days a world ({c[cl] / n / 18:.1f} a day) | steps {c[cl + "|steps"] / m:.1f}, tiles worked {c[cl + "|tiles"] / m:.1f}, '
                  f'ops {c[cl + "|ops"] / m:.1f} ({c[cl + "|ops"] / max(1, c[cl + "|tiles"]):.2f} a tile), shed {c[cl + "|shed"] / m:.1f}, idle {c[cl + "|idle"] / m:.1f} h, '
                  f'work h{c[cl + "|first"] / m:.1f}-h{c[cl + "|last"] / m:.1f}')
            print('            ops: ' + ', '.join(f'{k.split("|")[2]} {v / m:.1f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith(cl + '|op|')))
            ks = [k.split('|')[2] for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith(cl + '|v|')]
            print('            visits / ops a visit: ' + ', '.join(f'{k} {c[cl + "|v|" + k] / m:.1f} / {c[cl + "|vo|" + k] / max(1, c[cl + "|v|" + k]):.2f}' for k in ks))

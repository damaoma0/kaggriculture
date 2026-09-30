"""How path-like each hand-day is, the leader vs arms over the 40-world panel (days 11-28, hands only). A hand-day's worked
tiles in the order first worked; between consecutive worked tiles the gap = steps walked minus 1 (0 = the next tile is
adjacent or the same, a graph path; k = k tiles walked but not worked). Per hand-day: steps walked, worked tiles, ops,
tiles walked without work, the share of transitions that are path steps (gap 0), the largest gap, and whether the
worked tiles form one path (all gaps 0), a near path (every gap <= 1), or have a long jump (a gap >= 4, the hand-8 kind).
Split by route shape (radial / returning).
usage: panel_path_metrics.py <ARM>[,<ARM>...] [--workers 4]"""
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
    ev = defaultdict(list)
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                if u == 0:
                    continue
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                k = 'move' if op in MOVES else ('pass' if op == 'PASS' else ('shed' if (op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE'))) else 'work'))
                ev[(dd, u)].append((p, k))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c = Counter()
    for key, e in ev.items():
        wt = []                                        # worked tiles in first-worked order (a revisit counts as a new visit)
        for p, k in e:
            if k == 'work' and (not wt or wt[-1] != p):
                wt.append(p)
        if len(wt) < 2:
            continue
        ops = sum(1 for p, k in e if k == 'work')
        moves = sum(1 for p, k in e if k == 'move')
        # returning hand: back within 1 of the shed between two worked tiles
        back = False
        far = False
        for p, k in e:
            if dsh(p) >= 2:
                far = True
            elif far and dsh(p) <= 1 and any(k2 == 'work' for p2, k2 in e[e.index((p, k)):]):
                back = True
                break
        shape = 'returning' if back else 'radial'
        gaps = [abs(a[0] - b[0]) + abs(a[1] - b[1]) - 1 for a, b in zip(wt, wt[1:])]
        gaps = [max(0, x) for x in gaps]
        c[shape + '|n'] += 1
        c[shape + '|visits'] += len(wt)
        c[shape + '|tiles'] += len(set(wt))
        c[shape + '|ops'] += ops
        c[shape + '|moves'] += moves
        c[shape + '|walk_only'] += len(set(p for p, k in e if k == 'move') - set(wt))
        c[shape + '|trans'] += len(gaps)
        c[shape + '|gap0'] += sum(1 for x in gaps if x == 0)
        c[shape + '|gapsum'] += sum(gaps)
        mg = max(gaps)
        c[shape + '|maxgap_%s' % (min(mg, 6))] += 1
        c[shape + '|' + ('path' if mg == 0 else 'near path' if mg <= 1 else 'jump 4+' if mg >= 4 else 'gap 2-3')] += 1
        c[shape + '|revisit'] += len(wt) - len(set(wt))
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
        print(f'\n{a}:')
        for sh in ('radial', 'returning'):
            m = max(1, c[sh + '|n'])
            print(f'   {sh:9s}: {c[sh + "|n"] / n:5.1f} hand-days a world | worked visits {c[sh + "|visits"] / m:.1f} ({c[sh + "|tiles"] / m:.1f} tiles, revisits '
                  f'{c[sh + "|revisit"] / m:.2f}), ops {c[sh + "|ops"] / m:.1f}, steps {c[sh + "|moves"] / m:.1f}, tiles walked without work {c[sh + "|walk_only"] / m:.1f} | '
                  f'path steps between visits {100 * c[sh + "|gap0"] / max(1, c[sh + "|trans"]):.0f}%, gap tiles a day {c[sh + "|gapsum"] / m:.2f}')
            print('      shape: ' + ', '.join(f'{k} {100 * c[sh + "|" + k] / m:.0f}%' for k in ('path', 'near path', 'gap 2-3', 'jump 4+'))
                  + ' | largest gap: ' + ', '.join(f'{i}{"+" if i == 6 else ""}: {100 * c.get(sh + "|maxgap_%d" % i, 0) / m:.0f}%' for i in range(7)))

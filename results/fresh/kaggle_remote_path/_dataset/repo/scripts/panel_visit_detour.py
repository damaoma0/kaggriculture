"""How DSM's (or an arm's) mid-day shed visits sit in the route: for each visit (a DROP / PICKUP / product PLACE on a
shed access tile at hours 2-22 after 2+ steps away, and the hand works again afterwards), the last work tile before it
and the first work tile after it (work = any action other than a move / PASS / shed exchange); detour = d(prev, shed) +
d(shed, next) - d(prev, next) in steps; whether prev and next lie in different quadrants (the shed as the hub between
two trips); hours spent from the last work to the next work; ops done per hand-day before and after the visit.
usage: panel_visit_detour.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST', 'PASS')


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dsh(p):
    return min(d(p, s) for s in SHED)


def quad(p):
    return (p[0] >= 5) * 1 + (p[1] >= 5) * 2


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = None if arm == 'DSM' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    log = {}                                             # (day, unit) -> [(hour, pos, kind)] kind: 'work' / 'shed' / 'move'
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
                    k = 'move'
                elif op in ('DROP', 'PICKUP') or (op == 'PLACE' and dsh(p) == 0 and len(cm) > 1 and cm[1] not in ('COW', 'SHEEP', 'GOOSE')):
                    k = 'shed'
                else:
                    k = 'work'
                log.setdefault((dd, u), []).append((h, p, k))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c = Counter()
    for key, ev in log.items():
        far = False
        i = 0
        while i < len(ev):
            h, p, k = ev[i]
            if dsh(p) >= 2:
                far = True
            if k == 'shed' and far and 2 <= h <= 22:
                far = False
                j = i
                while j + 1 < len(ev) and ev[j + 1][2] == 'shed':
                    j += 1
                prev = next((x for x in reversed(ev[:i]) if x[2] == 'work'), None)
                nxt = next((x for x in ev[j + 1:] if x[2] == 'work'), None)
                if prev is not None and nxt is not None:
                    sh = p
                    det = d(prev[1], sh) + d(sh, nxt[1]) - d(prev[1], nxt[1])
                    c['visits'] += 1
                    c['det_%d' % min(det, 6)] += 1
                    c['det_sum'] += det
                    c['xquad'] += quad(prev[1]) != quad(nxt[1])
                    c['gap_h'] += nxt[0] - prev[0]
                    c['sh_ops'] += j - i + 1
                    c['work_before'] += sum(1 for x in ev[:i] if x[2] == 'work')
                    c['work_after'] += sum(1 for x in ev[j + 1:] if x[2] == 'work')
                    c['prev_dsh'] += dsh(prev[1])
                    c['next_dsh'] += dsh(nxt[1])
                i = j + 1
                continue
            i += 1
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
        m = max(1, c['visits'])
        print(f'{a}: mid-day visits with work before and after {c["visits"] / n:.1f} a world | detour steps: '
              + ', '.join(f'{k}{"+" if k == 6 else ""}: {100 * c.get("det_%d" % k, 0) / m:.0f}%' for k in range(7))
              + f' (mean {c["det_sum"] / m:.2f}) | prev / next work in different quadrants {100 * c["xquad"] / m:.0f}%'
              f' | last work -> next work {c["gap_h"] / m:.1f} h ({c["sh_ops"] / m:.1f} shed actions) | prev work {c["prev_dsh"] / m:.1f} / next '
              f'{c["next_dsh"] / m:.1f} steps from the shed | work ops before {c["work_before"] / m:.1f}, after {c["work_after"] / m:.1f}')

"""Start of the hand-day, the leader vs arms over the 40-world panel (days 11-28, hands only): first hour present, shed
actions before the first job (what is picked up), steps from the start tile to the first work tile, the first job (tile
kind + op) and its hour; how often the first job is a pen next to the shed; and the steps / hours to the first job split
by whether the hand loaded something first.
usage: panel_day_start.py <ARM>[,<ARM>...] [--workers 4]"""
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


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def dsh(p):
    return min(d(p, s) for s in SHED)


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
                tl = farm['tiles'][p[1]][p[0]]
                kd = (tl.get('animal') or tl.get('crop') or tl.get('kind')) if isinstance(tl, dict) else '-'
                ev[(dd, u)].append((h, p, op, cm, kd))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c = Counter()
    for key, e in ev.items():
        fw = next((i for i, x in enumerate(e) if x[2] not in MOVES + ('PASS', 'DROP', 'PICKUP', 'PLACE')), None)
        if fw is None:
            continue
        c['n'] += 1
        h0, p0 = e[0][0], e[0][1]
        c['start_h'] += h0
        c['start_h%d' % h0] += 1
        pre = e[:fw]
        picks = [x[3] for x in pre if x[2] == 'PICKUP']
        c['pick_actions'] += len(picks)
        for cm in picks:
            c['pick|' + (cm[1] if len(cm) > 1 else '?')] += 1
        c['pre_moves'] += sum(1 for x in pre if x[2] in MOVES)
        c['pre_pass'] += sum(1 for x in pre if x[2] == 'PASS')
        hf, pf, opf, _, kdf = e[fw]
        c['first_h'] += hf
        c['first_steps'] += d(p0, pf)
        c['first_dist_%d' % min(d(p0, pf), 4)] += 1
        c['first_dsh'] += dsh(pf)
        cls = 'pen' if kdf in PENS else ('crop' if kdf not in ('-', 'COOP', 'PASTURE', 'WEED') else 'other')
        c['first_' + cls] += 1
        c['firstop|' + cls + ':' + opf] += 1
        if cls == 'pen' and dsh(pf) <= 1:
            c['first_pen_near'] += 1
        lab = 'loaded' if picks else 'empty'
        c[lab] += 1
        c[lab + '_steps'] += d(p0, pf)
        c[lab + '_wait'] += hf - h0
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
        m = max(1, c['n'])
        print(f'\n{a}: {m / n:.0f} hand-days a world | start hour {c["start_h"] / m:.2f} (' + ', '.join(f'h{k[7:]} {v / m:.2f}' for k, v in sorted(c.items()) if k.startswith('start_h') and k != 'start_h')
              + f') | first job at hour {c["first_h"] / m:.2f}, {c["first_steps"] / m:.2f} steps from the start tile (' + ', '.join(f'{k[11:]}{"+" if k.endswith("4") else ""}: {v / m:.2f}' for k, v in sorted(c.items()) if k.startswith('first_dist_'))
              + f'), {c["first_dsh"] / m:.2f} from the shed')
        print(f'   before the first job: pickups {c["pick_actions"] / m:.2f} (' + ', '.join(f'{k[5:]} {v / m:.2f}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('pick|'))
              + f'), moves {c["pre_moves"] / m:.2f}, waits {c["pre_pass"] / m:.2f}')
        for lab in ('loaded', 'empty'):
            k = max(1, c[lab])
            print(f'   {lab:6s}: {c[lab] / m:.0%} of hand-days, first job {c[lab + "_steps"] / k:.2f} steps away, {c[lab + "_wait"] / k:.2f} h after the start')
        print(f'   first job: pen {c["first_pen"] / m:.0%} (pen next to the shed {c["first_pen_near"] / m:.0%}), crop {c["first_crop"] / m:.0%}, other {c["first_other"] / m:.0%} | '
              + ', '.join(f'{k[8:]} {v / m:.0%}' for k, v in sorted(c.items(), key=lambda kv: -kv[1]) if k.startswith('firstop|'))[:300])

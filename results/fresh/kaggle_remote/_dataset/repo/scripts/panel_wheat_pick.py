"""Morning wheat loading vs feeding, the leader vs arms over the 40-world panel (days 11-28): per hand-day, wheat PICKUP
actions before the hand first leaves the shed (count and units), the FEEDs that hand does that day, feeds per
wheat-carrying hand, hand-days that pick wheat twice, and wheat left in hand at midnight.
usage: panel_wheat_pick.py <ARM>[,<ARM>...] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]


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
    left = {}
    pk = Counter()
    pku = Counter()
    fd = Counter()
    days = set()
    while w.t < 696:
        t = w.t
        dd, h = t // 24, t % 24
        own = UE.tape_action(tape['actions'], t) if (s is None or t < 264) else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            cmds = [own.get('farmer')] + list(own.get('hands') or [])
            for u, p in enumerate(units):
                key = (dd, u)
                days.add(key)
                if dsh(p) >= 2:
                    left[key] = True
                cm = cmds[u] if u < len(cmds) else None
                op = cm[0] if isinstance(cm, list) and cm else 'PASS'
                if op == 'PICKUP' and len(cm) > 1 and cm[1] == 'WHEAT' and not left.get(key):
                    pk[key] += 1
                    pku[key] += int(cm[2]) if len(cm) > 2 else 1
                if op == 'FEED':
                    fd[key] += 1
            if h == 23:
                for u, x in enumerate(w.private(seat)['inventories']):
                    c['wheat_midnight'] += int((x or {}).get('WHEAT', 0) or 0)
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c['hand_days'] = len(days)
    c['pick_days'] = sum(1 for k in pk if pk[k])
    c['pick_actions'] = sum(pk.values())
    c['pick_units'] = sum(pku.values())
    c['twice'] = sum(1 for k in pk if pk[k] >= 2)
    c['feeds'] = sum(fd.values())
    c['feed_days'] = sum(1 for k in fd if fd[k])
    c['feeds_by_pickers'] = sum(fd[k] for k in pk if pk[k])
    c['pick_nofeed'] = sum(1 for k in pk if pk[k] and not fd[k])
    for k in pk:
        if pk[k]:
            c['fpp_%d' % min(fd[k], 6)] += 1
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
        m = max(1, c['pick_days'])
        print(f'{a}: hand-days loading wheat {c["pick_days"] / n:.1f} a world ({c["pick_actions"] / n:.1f} pickups, {c["pick_units"] / n:.0f} units; twice {c["twice"] / n:.1f}; '
              f'with no feed that day {c["pick_nofeed"] / n:.1f}) | feeds {c["feeds"] / n:.0f} a world by {c["feed_days"] / n:.1f} hand-days, '
              f'{c["feeds_by_pickers"] / m:.1f} per loading hand | wheat in hand at midnight {c["wheat_midnight"] / n:.0f}')
        print('     feeds per loading hand-day: ' + ', '.join(f'{k}{"+" if k == 6 else ""}: {c.get("fpp_%d" % k, 0) / n:.1f}' for k in range(7)))

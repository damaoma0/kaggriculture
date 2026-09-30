"""Planned first stop vs start tile (arm over the 40-world panel, days 11-28, hands only): steps from the ACTUAL start
tile to the route's planned first stop, from the PLANNED spawn tile (the plan's summary 'spawn' list, hands in order),
and from the nearest shed tile; how often the spawn tile was predicted right and the extra steps a misprediction costs.
usage: panel_spawn_first.py <ARM> [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]


def d(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def job(args):
    g, arm = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    res = json.loads((ROOT / 'results/fresh/sector_20260925/multi' / arm / f'{ep}.json').read_text())
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    start = {}
    while w.t < 696:
        t = w.t
        dd = t // 24
        own = UE.tape_action(tape['actions'], t) if t < 264 else (s[t] if isinstance(s[t], dict) and s[t] else dict(UE.PASS))
        if t >= 264:
            farm = w.farms[seat]
            for u, q in enumerate([tuple(farm['farmer'])] + [tuple(x) for x in farm['hands']]):
                start.setdefault((dd, u), q)
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c = Counter()
    for day, v in res['tier_days'].items():
        if not v or not v.get('units'):
            continue
        dd = int(day)
        sp = v.get('spawn') or []
        for r in v['units']:
            u = r['u']
            if u == 0 or not r.get('stops') or (dd, u) not in start:
                continue
            first = r['stops'][0][0]
            ft = (first % 10, first // 10)
            act = start[(dd, u)]
            c['n'] += 1
            c['act_to_first'] += d(act, ft)
            c['near_to_first'] += min(d(q, ft) for q in SHED)
            c['kind_' + r.get('kind', '?')] += 1
            if u - 1 < len(sp):
                pl = tuple(sp[u - 1])
                c['pl_n'] += 1
                c['pl_to_first'] += d(pl, ft)
                c['spawn_ok'] += pl == act
                c['mis_steps'] += d(act, ft) - d(pl, ft)
    return dict(c)


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for c in pool.imap_unordered(job, [(g, arm) for g in games]):
            tot.update(c)
    m = max(1, tot['n'])
    k = max(1, tot['pl_n'])
    print(f"{arm}: hand-days {m / len(games):.0f} a world | planned first stop: {tot['act_to_first'] / m:.2f} steps from the actual start tile, "
          f"{tot['pl_to_first'] / k:.2f} from the planned spawn tile, {tot['near_to_first'] / m:.2f} from the nearest shed tile | "
          f"spawn predicted right {tot['spawn_ok'] / k:.0%}, extra steps from mispredicted spawns {tot['mis_steps'] / k:.2f}")

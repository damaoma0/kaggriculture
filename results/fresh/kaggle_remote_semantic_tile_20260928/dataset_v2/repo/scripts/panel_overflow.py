"""Midnight deletions across the 40-world panel for an arm (and the leader): per world-day the shed content before the
dump, the units carried into it and the units deleted; summary by day of season and by cause (shed held vs carried).
usage: panel_overflow.py <ARM> [--workers 4]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
R = {'w': None, 'seat': 0, 't': 0, 'rows': None}
_drop = E._drop_inventories_to_shed


def drop(private, cap):
    w = R['w']
    if w is not None and R['t'] >= 264 and private is w.private(R['seat']):
        shed = sum(int(v or 0) for v in private['shed'].values())
        car = sum(int(v or 0) for inv in private['inventories'] for v in inv.values())
        R['rows'].append((R['t'] // 24, shed, car, max(0, shed + car - cap)))
    return _drop(private, cap)


E._drop_inventories_to_shed = drop


def job(args):
    g, arm = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    out = {}
    for name in ('leader', arm):
        stream = None if name == 'leader' else json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
        w = UE.World(tape['seed'], tape['shops'])
        seat = tape['seat']
        R.update(w=w, seat=seat, rows=[])
        while w.t < 719:
            t = w.t
            R['t'] = t
            own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
            a2 = [None, None]
            a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
            w.step(a2)
        out[name] = list(R['rows'])
    R['w'] = None
    return ep, out


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    res = {}
    with Pool(nw) as pool:
        for ep, r in pool.imap_unordered(job, [(g, arm) for g in games]):
            res[ep] = r
    json.dump(res, open(ROOT / f'results/fresh/threads_20260928/overflow_{arm.lower()}_40.json', 'w'))
    for name in ('leader', arm):
        byday = defaultdict(lambda: [0, 0, 0, 0])
        tot = Counter()
        for ep, r in res.items():
            for d, shed, car, lost in r[name]:
                x = byday[d]
                x[0] += 1
                x[1] += shed
                x[2] += car
                x[3] += lost
                if lost:
                    tot['days'] += 1
                    tot['lost'] += lost
                    tot['shed_held'] += shed
                    tot['carried'] += car
        n = len(res)
        print(f'== {name}: deleted {tot["lost"] / n:.1f} units / world on {tot["days"] / n:.1f} days; on those days mean shed '
              f'{tot["shed_held"] / max(1, tot["days"]):.0f} + carried {tot["carried"] / max(1, tot["days"]):.0f}')
        print('   by day (mean shed / carried / deleted per world): ' + ' '.join(
            f'd{d}:{x[1] / n:.0f}/{x[2] / n:.0f}/{x[3] / n:.1f}' for d, x in sorted(byday.items()) if x[3]))

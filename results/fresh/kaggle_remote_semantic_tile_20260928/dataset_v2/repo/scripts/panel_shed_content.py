"""On the nights the midnight dump overflows, what the shed already holds (units by product per overflow night), for an
arm and the leader, over the 40-world panel.
usage: panel_shed_content.py <ARM> [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
R = {'w': None, 'seat': 0, 't': 0, 'C': None}
_drop = E._drop_inventories_to_shed


def drop(private, cap):
    w = R['w']
    if w is not None and R['t'] >= 264 and private is w.private(R['seat']):
        sh = sum(private['shed'].values())
        car = sum(v for inv in private['inventories'] for v in inv.values())
        if sh + car > cap:
            for k, v in private['shed'].items():
                if v:
                    R['C'][k] += v
            R['C']['_nights'] += 1
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
        R.update(w=w, seat=seat, C=Counter())
        while w.t < 719:
            t = w.t
            R['t'] = t
            own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
            a2 = [None, None]
            a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
            w.step(a2)
        out[name] = dict(R['C'])
    R['w'] = None
    return out


if __name__ == '__main__':
    arm = sys.argv[1]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {'leader': Counter(), arm: Counter()}
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm) for g in games]):
            for k, v in r.items():
                tot[k].update(v)
    for k, C in tot.items():
        n = C.pop('_nights', 0)
        print(f'{k}: {n} overflow nights; shed content before the dump (units per overflow night): '
              + ', '.join(f'{p} {v / max(1, n):.1f}' for p, v in C.most_common(9)))

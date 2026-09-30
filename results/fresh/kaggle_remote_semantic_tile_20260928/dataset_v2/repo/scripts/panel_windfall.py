"""Where the rival's windfall on a product comes from, over the 40-world panel: at every rival sale in the arm's game,
were we behind the leader's cumulative sales (in its own game) with goods in our shed (held back), behind with an empty
shed (supply), or not behind; rival revenue change vs the leader's game split by those cases (per world).
usage: panel_windfall.py <ARM> <PRODUCT[,PRODUCT]> [--workers 4]"""
import bisect
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
R = {'w': None, 'seat': 0, 't': 0, 'ev': None, 'P': ()}
_commit = E._commit_unit


def commit(op, item, price, farm, private, market, cap=100):
    r = _commit(op, item, price, farm, private, market, cap)
    w = R['w']
    if r and w is not None and op == 'SELL' and item in R['P'] and R['t'] >= 264:
        R['ev'].append((R['t'], 'us' if farm is w.farms[R['seat']] else 'opp', item, price))
    return r


E._commit_unit = commit


def play(tape, stream, P):
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    R.update(w=w, seat=seat, ev=[], P=P)
    shed = {}
    while w.t < 719:
        t = w.t
        R['t'] = t
        if t >= 264:
            shed[t] = {p: w.private(seat)['shed'].get(p, 0) for p in P}
        own = UE.tape_action(tape['actions'], t) if (stream is None or t < 264) else (stream[t] if isinstance(stream[t], dict) and stream[t] else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    R['w'] = None
    return list(R['ev']), shed


def job(args):
    g, arm, P = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    L, _ = play(tape, None, P)
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    A, shedA = play(tape, s, P)
    out = {}
    for p in P:
        cd = sorted(e[0] for e in L if e[1] == 'us' and e[2] == p)
        ca = sorted(e[0] for e in A if e[1] == 'us' and e[2] == p)
        rA, rL = defaultdict(list), defaultdict(list)
        for e in A:
            if e[1] == 'opp' and e[2] == p:
                rA[e[0]].append(e[3])
        for e in L:
            if e[1] == 'opp' and e[2] == p:
                rL[e[0]].append(e[3])
        c = defaultdict(float)
        for t in sorted(set(rA) | set(rL)):
            lag = bisect.bisect_left(cd, t) - bisect.bisect_left(ca, t)
            key = ('held' if shedA.get(t, {}).get(p, 0) > 0 else 'empty') if lag > 0 else 'not_behind'
            c[key + '_units'] += len(rA.get(t, []))
            c[key + '_gain'] += sum(rA.get(t, [])) - sum(rL.get(t, []))
        out[p] = dict(c)
    return out


if __name__ == '__main__':
    arm, P = sys.argv[1], tuple(sys.argv[2].split(','))
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {p: defaultdict(float) for p in P}
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm, P) for g in games]):
            for p, c in r.items():
                for k, v in c.items():
                    tot[p][k] += v
    n = len(games)
    for p in P:
        c = tot[p]
        print(f'{p} ({arm}), per world: rival windfall while we are behind DSM with goods IN the shed {c["held_gain"] / n:+.0f} '
              f'({c["held_units"] / n:.1f} rival units) | behind with an EMPTY shed {c["empty_gain"] / n:+.0f} ({c["empty_units"] / n:.1f}) '
              f'| not behind {c["not_behind_gain"] / n:+.0f} ({c["not_behind_units"] / n:.1f})')

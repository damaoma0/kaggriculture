"""Our cumulative-sales lag behind the leader at the moments the rival sells, over the 40-world panel. Town consumption
is fixed (the engine subtracts shop draws unconditionally, stock may go negative) and the rival replays its recorded
orders, so the market stock difference at any step equals our cumulative sales difference: this is the whole channel
of the rival's windfall. Per rival sale unit: lag = DSM's units sold before that step - ours; averaged by day and by
hour, with the rival's price difference and the part of the lag that sits in our shed / on our tiles at that moment.
usage: panel_lag_at_rival.py <ARM> <PRODUCT> [--workers 4]"""
import bisect
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import panel_windfall as PW  # noqa: E402

UE = PW.UE


def job(args):
    g, arm, p = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    L, shL = PW.play(tape, None, (p,))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    A, shA = PW.play(tape, s, (p,))
    cd = sorted(e[0] for e in L if e[1] == 'us')
    ca = sorted(e[0] for e in A if e[1] == 'us')
    rA = defaultdict(list)
    rL = defaultdict(list)
    for e in A:
        if e[1] == 'opp':
            rA[e[0]].append(e[3])
    for e in L:
        if e[1] == 'opp':
            rL[e[0]].append(e[3])
    c = defaultdict(float)
    for t in sorted(rA):
        lag = bisect.bisect_left(cd, t) - bisect.bisect_left(ca, t)
        n = len(rA[t])
        dpx = sum(rA[t]) - sum(rL.get(t, []))
        for key in (('d', t // 24), ('h', t % 24)):
            c[key + ('n',)] += n
            c[key + ('lag',)] += lag * n
            c[key + ('dpx',)] += dpx
            c[key + ('shed',)] += shA.get(t, {}).get(p, 0) * n
    return {'|'.join(map(str, k)): v for k, v in c.items()}


if __name__ == '__main__':
    arm, p = sys.argv[1], sys.argv[2]
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = defaultdict(float)
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm, p) for g in games]):
            for k, v in r.items():
                tot[k] += v
    n = len(games)
    for kind, rng, lab in (('d', range(11, 30), 'day'), ('h', range(24), 'hour')):
        print(f'{p} ({arm}) by {lab}: rival units / world, mean lag (DSM units sold before the rival\'s sale - ours), our shed '
              f'at that step, rival revenue change / world')
        for x in rng:
            k = f'{kind}|{x}|'
            m = tot.get(k + 'n', 0.0)
            if m:
                print(f'   {lab} {x:2d}: {m / n:5.2f} units | lag {tot[k + "lag"] / m:+5.1f} | our shed {tot[k + "shed"] / m:5.1f} | rival {tot[k + "dpx"] / n:+6.0f}')

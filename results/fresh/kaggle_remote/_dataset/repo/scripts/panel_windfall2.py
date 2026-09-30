"""Refined rival-windfall split (panel_windfall.py counted the shed at the START of a step, so goods that arrived and
were sold in that very step counted as held back). At every rival sale step t in the arm's game: behind = DSM's
cumulative sales of the product THROUGH step t exceed ours; truly held = goods still in our shed AFTER step t
(start of t+1); sold-now = behind, we sold at step t but ran out; empty = behind, nothing in the shed and no sale.
Rival revenue change vs the leader's game per world, and for truly-held steps our shed hold / hour mix.
usage: panel_windfall2.py <ARM> <PRODUCT[,PRODUCT]> [--workers 4]"""
import bisect
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import panel_windfall as PW  # noqa: E402

UE = PW.UE


def job(args):
    g, arm, P = args
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep.strip()))
    L, _ = PW.play(tape, None, P)
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep.strip()}.json').read_text(encoding='utf-8'))['actions']
    A, shedA = PW.play(tape, s, P)
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
        hrs = Counter()
        for t in sorted(set(rA) | set(rL)):
            lag = bisect.bisect_right(cd, t) - bisect.bisect_right(ca, t)
            sold_now = bisect.bisect_right(ca, t) - bisect.bisect_left(ca, t)
            after = shedA.get(t + 1, {}).get(p, 0)
            if lag <= 0:
                key = 'not_behind'
            elif after > 0:
                key = 'held'
                hrs[t % 24] += 1
                c['held_shed_after'] += after
                c['held_steps'] += 1
            elif sold_now:
                key = 'sold_now'
            else:
                key = 'empty'
            c[key + '_units'] += len(rA.get(t, []))
            c[key + '_gain'] += sum(rA.get(t, [])) - sum(rL.get(t, []))
        c['_hours'] = dict(hrs)
        out[p] = dict(c)
    return out


if __name__ == '__main__':
    arm, P = sys.argv[1], tuple(sys.argv[2].split(','))
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {p: defaultdict(float) for p in P}
    hrs = {p: Counter() for p in P}
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm, P) for g in games]):
            for p, c in r.items():
                for k, v in c.items():
                    if k == '_hours':
                        hrs[p].update(v)
                    else:
                        tot[p][k] += v
    n = len(games)
    for p in P:
        c = tot[p]
        print(f'{p} ({arm}), per world rival windfall: truly held {c["held_gain"] / n:+.0f} ({c["held_units"] / n:.1f} rival units, '
              f'our shed after the step {c["held_shed_after"] / max(1, c["held_steps"]):.1f}) | sold-now-but-short {c["sold_now_gain"] / n:+.0f} '
              f'({c["sold_now_units"] / n:.1f}) | empty {c["empty_gain"] / n:+.0f} ({c["empty_units"] / n:.1f}) | not behind '
              f'{c["not_behind_gain"] / n:+.0f} ({c["not_behind_units"] / n:.1f})')
        print(f'   truly-held steps by hour: {dict(sorted(hrs[p].items()))}')

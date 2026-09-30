"""Arrival timing of goods into the shed, the leader's game vs an arm's, over the 40-world panel (days 11-29).
Shed inflow per step = shed(t+1) - shed(t) + our units sold at t (for goods nobody picks up again: strawberry, wool,
milk, egg). Inflow at hour 23 is the midnight dump (end-of-day drop of everything carried); any other hour is a
daytime return. Per product and world: units arriving by daytime return vs midnight dump in each game, and the
unit-matched arrival delay (the k-th unit to arrive in our shed vs the k-th in the leader's, from the day-11 morning):
same step or earlier / later the same day / next day / 2+ days, with the units DSM brought by daytime return that we
brought at midnight.
usage: panel_arrival.py <ARM> <PRODUCT[,PRODUCT]> [--workers 4]"""
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import panel_windfall as PW  # noqa: E402

UE = PW.UE


def arrivals(ev, shed, p):
    sold = Counter(e[0] for e in ev if e[1] == 'us' and e[2] == p)
    out = []                                           # one entry per unit: arrival step
    for t in range(264, 718):
        if t + 1 not in shed or t not in shed:
            continue
        n = shed[t + 1][p] - shed[t][p] + sold.get(t, 0)
        out += [t] * max(0, n)
    return out


def job(args):
    g, arm, P = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    L, shL = PW.play(tape, None, P)
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    A, shA = PW.play(tape, s, P)
    out = {}
    for p in P:
        aL, aA = arrivals(L, shL, p), arrivals(A, shA, p)
        c = Counter()
        c['dsm_day'] = sum(1 for t in aL if t % 24 != 23)
        c['dsm_night'] = sum(1 for t in aL if t % 24 == 23)
        c['us_day'] = sum(1 for t in aA if t % 24 != 23)
        c['us_night'] = sum(1 for t in aA if t % 24 == 23)
        for k, tl in enumerate(aL):
            if k >= len(aA):
                c['us_never'] += 1
                continue
            ta = aA[k]
            dd = ta // 24 - tl // 24
            if ta <= tl:
                c['lag_le0'] += 1
            elif dd == 0:
                c['lag_sameday'] += 1
            elif dd == 1:
                c['lag_nextday'] += 1
                if tl % 24 != 23 and ta % 24 == 23 - 0 and False:
                    pass
            else:
                c['lag_2plus'] += 1
            if ta > tl:
                c['lag_hours'] += ta - tl
            if tl % 24 != 23 and ta // 24 > tl // 24:
                c['dsm_dayret_we_later_day'] += 1       # DSM's daytime return, ours arrives on a later day
        out[p] = dict(c)
    return out


if __name__ == '__main__':
    arm, P = sys.argv[1], tuple(sys.argv[2].split(','))
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = {p: Counter() for p in P}
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm, P) for g in games]):
            for p, c in r.items():
                tot[p].update(c)
    n = len(games)
    for p in P:
        c = tot[p]
        k = sum(c[x] for x in ('lag_le0', 'lag_sameday', 'lag_nextday', 'lag_2plus'))
        print(f'{p} ({arm}) per world: DSM arrivals day {c["dsm_day"] / n:.1f} / midnight {c["dsm_night"] / n:.1f} | ours day '
              f'{c["us_day"] / n:.1f} / midnight {c["us_night"] / n:.1f}')
        print(f'   unit-matched arrival: ours no later {c["lag_le0"] / n:.1f} | later same day {c["lag_sameday"] / n:.1f} | next day '
              f'{c["lag_nextday"] / n:.1f} | 2+ days {c["lag_2plus"] / n:.1f} | never {c["us_never"] / n:.1f} | mean delay of late units '
              f'{c["lag_hours"] / max(1, k - c["lag_le0"]):.1f} h | DSM daytime return that reaches us on a later day '
              f'{c["dsm_dayret_we_later_day"] / n:.1f}')

"""How often our hands already pass the shed mid-day while carrying a product (a free daytime return: DSM's strawberry
returns are afternoon passes, median drop hour 16, ~3 tiles harvested from hour ~5). Over the 40-world panel, for every
hand-day of the arm: the first step in hours [h0, h1] where the hand stands on or next to a shed access tile carrying
>= k units of the product; per world: hand-days carrying the product mid-day, hand-days with such a pass, units carried
at the pass, the hour, and the units those hands still carried into the midnight dump.
usage: panel_shed_pass.py <ARM> <PRODUCT> [--k 3] [--hours 10,20] [--workers 4]"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}


def near(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED) <= 1


def job(args):
    g, arm, p, k, h0, h1 = args
    team, ep = g.split(':')
    ep = ep.strip()
    tape = UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))['actions']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    c = Counter()
    carrying, passed, eod = set(), {}, {}
    while w.t < 719:
        t = w.t
        if t >= 264:
            d, h = t // 24, t % 24
            farm = w.farms[seat]
            invs = w.private(seat)['inventories']
            units = [tuple(farm['farmer'])] + [tuple(q) for q in farm['hands']]
            for u, pos in enumerate(units):
                n = int((invs[u] if u < len(invs) else {}).get(p, 0) or 0)
                if h0 <= h <= h1 and n >= k:
                    carrying.add((d, u))
                    if near(pos) and (d, u) not in passed:
                        passed[(d, u)] = (h, n)
                if h == 23:
                    eod[(d, u)] = n
        own = s[t] if (t >= 264 and t < len(s) and isinstance(s[t], dict) and s[t]) else (UE.tape_action(tape['actions'], t) if t < 264 else dict(UE.PASS))
        a2 = [None, None]
        a2[seat], a2[1 - seat] = own, UE.tape_action(tape['opp_actions'], t)
        w.step(a2)
    c['carry_days'] = len(carrying)
    c['pass_days'] = len(passed)
    c['pass_units'] = sum(n for h, n in passed.values())
    c['pass_hour'] = sum(h for h, n in passed.values())
    c['eod_units_passers'] = sum(eod.get(key, 0) for key in passed)
    c['eod_units_all'] = sum(v for v in eod.values())
    return dict(c)


if __name__ == '__main__':
    arm, p = sys.argv[1], sys.argv[2]
    k = int(sys.argv[sys.argv.index('--k') + 1]) if '--k' in sys.argv else 3
    h0, h1 = map(int, (sys.argv[sys.argv.index('--hours') + 1] if '--hours' in sys.argv else '10,20').split(','))
    nw = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv else 1
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    tot = Counter()
    with Pool(nw) as pool:
        for r in pool.imap_unordered(job, [(g, arm, p, k, h0, h1) for g in games]):
            tot.update(r)
    n = len(games)
    print(f'{p} ({arm}), hours {h0}-{h1}, carrying >= {k}: hand-days carrying {tot["carry_days"] / n:.1f} a world | with a pass on / next to '
          f'the shed {tot["pass_days"] / n:.1f} (units at the pass {tot["pass_units"] / max(1, tot["pass_days"]):.1f}, mean hour '
          f'{tot["pass_hour"] / max(1, tot["pass_days"]):.1f}) | units those hands still carried into the midnight dump '
          f'{tot["eod_units_passers"] / n:.1f} a world (all hands {tot["eod_units_all"] / n:.1f})')

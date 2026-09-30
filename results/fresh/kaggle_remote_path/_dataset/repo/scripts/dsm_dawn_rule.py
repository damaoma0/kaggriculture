"""Learn DSM's dawn-trip rule from its recordings (a DSM-free replacement for sd_tier_dawn_shape): at every day's hour 0
(days 12-29), every animal pen on DSM's board with its animal, Manhattan distance to the nearest shed tile, yield held,
whether tonight is a production night, and whether DSM harvested it in a dawn trip that day (build_dsm_dawn's trips).
Prints the harvest rate by animal x distance x yield, and the trips per day vs the number of candidate pens.
usage: dsm_dawn_rule.py <out.json>"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
AN = E.ANIMALS


def dist(x, y):
    return min(abs(x - a) + abs(y - b) for a, b in SHED)


def job(g):
    team, ep = g.split(':')
    tape = UE.load_tape(int(team), int(ep))
    dawn = json.loads((ROOT / 'results/fresh/threads_20260928/dsm_dawn' / f'{ep}.json').read_text())['days']
    w = UE.World(tape['seed'], tape['shops'])
    seat = tape['seat']
    rows = []
    while w.t < 696:
        t = w.t
        if t >= 12 * 24 and t % 24 == 0:
            d = t // 24
            hit = {p for tr in dawn.get(str(d), []) for p, _ in tr[3]}
            for y, row in enumerate(w.farms[seat]['tiles']):
                for x, tl in enumerate(row):
                    if isinstance(tl, dict) and tl.get('animal') in AN:
                        a = AN[tl['animal']]
                        dsf = d - tl['placed_day'] - a['first_yield_day']
                        rows.append({'ep': ep, 'd': d, 'animal': tl['animal'], 'dist': dist(x, y),
                                     'yield': int(tl.get('yield_units', 0) or 0), 'full': int(tl.get('yield_units', 0) or 0) >= a['max_held'],
                                     'prod_tonight': int(dsf + 1 >= 0 and (dsf + 1) % a['interval'] == 0),
                                     'dawn': int(y * 10 + x in hit)})
        acts = [None, None]
        acts[seat], acts[1 - seat] = UE.tape_action(tape['actions'], t), UE.tape_action(tape['opp_actions'], t)
        w.step(acts)
    return rows


if __name__ == '__main__':
    games = (ROOT / 'results/fresh/threads_20260928/panel_dsm40b.txt').read_text().replace(',', ' ').split()
    rows = []
    for g in games:
        rows += job(g)
    json.dump(rows, open(sys.argv[1], 'w'))
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        k = (r['animal'], min(r['dist'], 3), min(r['yield'], 6))
        agg[k][0] += 1
        agg[k][1] += r['dawn']
    print('animal | distance | yield at dawn -> DSM dawn-harvest rate (pens)')
    for k in sorted(agg):
        n, h = agg[k]
        if n >= 10:
            print(f'  {k[0]:5s} d{k[1]} y{k[2]}: {h / n:.2f} ({n})')

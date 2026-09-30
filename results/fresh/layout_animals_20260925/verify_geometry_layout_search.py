"""Does the shed-tile exclusion (scripts/layout_value.py line 84) explain the 'greedy re-layout worse in 109/109' wage
result? Offline only: the same labour_search.search() cost as layout_value.py (exec'd read-only), on every 4th DSM
tape (data/dsm_tapes/56444344), scoring per day: actual layout, greedy without shed tiles (original), greedy with
shed tiles. No engine, no games. Single process.

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/verify_geometry_layout_search.py [nth=4] [budget=0.05]
"""
import glob
import gzip
import json
import os
import random
import statistics as st
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))


def main():
    nth = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
    ns = {'__name__': 'lv_lib', '__file__': os.path.join(ROOT, 'scripts', 'layout_value.py')}
    exec(compile(open(os.path.join(ROOT, 'scripts', 'layout_value.py'), encoding='utf-8').read(), 'layout_value', 'exec'), ns)
    simulate, instance, greedy, unlocked_by_day = ns['simulate'], ns['instance'], ns['greedy_relayout'], ns['unlocked_by_day']
    finish, cost, remap = ns['finish'], ns['cost'], ns['remap_routes']
    pool_orig = list(ns['ALL_TILES'])
    pool_shed = [(x, y) for y in range(10) for x in range(10)]
    rng = random.Random(20260924)
    rows = []
    paths = sorted(glob.glob(os.path.join(ROOT, 'data', 'dsm_tapes', '56444344', '*.json.gz')))[::nth]
    for gi, p in enumerate(paths):
        with gzip.open(p, 'rt', encoding='utf-8') as fh:
            t = json.load(fh)
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        unlocked = unlocked_by_day(t['boards'])
        freq, first_day, dr, du, dfz = Counter(), {}, {}, {}, {}
        for day in range(30):
            units, routes, busy, c = instance(sim, day)
            dr[day], du[day] = routes, units
            dfz[day] = {u for u in units if finish(units[u], routes[u]) > 24}
            for r in routes.values():
                for j in r:
                    freq[j.tile] += 1
                    first_day[j.tile] = min(first_day.get(j.tile, day), day)
        ns['ALL_TILES'] = pool_orig
        m1 = greedy(freq, first_day, unlocked)
        ns['ALL_TILES'] = pool_shed
        m2 = greedy(freq, first_day, unlocked)
        g = Counter()
        for day in range(30):
            units, routes = du[day], dr[day]
            if not any(routes.values()):
                continue
            ha, uha, wa = cost(units, {u: list(r) for u, r in routes.items()}, budget, rng, dfz[day])
            h1, uh1, w1 = cost(units, remap(routes, m1), budget, rng, dfz[day])
            h2, uh2, w2 = cost(units, remap(routes, m2), budget, rng, dfz[day])
            g.update(dict(wa=wa, w1=w1, w2=w2, uha=uha, uh1=uh1, uh2=uh2))
        rows.append(dict(path=os.path.basename(p), **g))
        print(f'{gi + 1}/{len(paths)} {os.path.basename(p)} wages actual {g["wa"]} greedy {g["w1"]} greedy+shed {g["w2"]}',
              file=sys.stderr)
        del t, acts, sim
    out = dict(games=len(rows), nth=nth, budget=budget,
               wages_mean=dict(actual=round(st.mean(r['wa'] for r in rows), 1), greedy_no_shed=round(st.mean(r['w1'] for r in rows), 1),
                               greedy_with_shed=round(st.mean(r['w2'] for r in rows), 1)),
               unit_hours_mean=dict(actual=round(st.mean(r['uha'] for r in rows), 1), greedy_no_shed=round(st.mean(r['uh1'] for r in rows), 1),
                                    greedy_with_shed=round(st.mean(r['uh2'] for r in rows), 1)),
               games_greedy_no_shed_more_wages=sum(r['w1'] > r['wa'] for r in rows),
               games_greedy_with_shed_more_wages=sum(r['w2'] > r['wa'] for r in rows),
               games_greedy_no_shed_more_unit_hours=sum(r['uh1'] > r['uha'] for r in rows),
               games_greedy_with_shed_more_unit_hours=sum(r['uh2'] > r['uha'] for r in rows),
               rows=rows)
    txt = json.dumps(out, indent=1)
    with open(os.path.join(HERE, 'verify_geometry_layout_search.json'), 'w', encoding='utf-8') as fh:
        fh.write(txt)
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))


if __name__ == '__main__':
    main()

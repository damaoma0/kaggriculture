"""Skeptic check of the layout-test claims (stored data only; no search, no games).

1. results/fresh/layout_value/layout_value.json: visit-weighted distance actual vs greedy, games where greedy is worse.
2. data/dsm_tapes/56444344/*.json.gz boards (the corpus scripts/layout_value.py used): how often animals sit on the
   four shed-access tiles there ('sh'/'go' exact; 'co' = cow or empty coop, resolved by label history where possible).
3. Re-run ONLY the greedy re-layout of scripts/layout_value.py (exec'd read-only; its main() is not run) with its
   ALL_TILES pool (shed tiles excluded, line 84) and with the shed tiles allowed, and report the visit-weighted mean
   distance of both. Same simulate / instance / frequency code as the original.

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/verify_geometry_layout.py
"""
import glob
import gzip
import json
import os
import statistics as st
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
SHED_IDX = {y * 10 + x for x, y in SHED}


def main():
    res = {}
    r = json.load(open(os.path.join(ROOT, 'results', 'fresh', 'layout_value', 'layout_value.json'), encoding='utf-8'))
    G = r['games']
    res['layout_value_json'] = dict(games=len(G), mean_dist_actual=round(st.mean(g['mean_dist_actual'] for g in G), 3),
                                    mean_dist_greedy=round(st.mean(g['mean_dist_greedy'] for g in G), 3),
                                    greedy_farther_games=sum(g['mean_dist_greedy'] > g['mean_dist_actual'] for g in G),
                                    greedy_more_wages_games=sum(g['wage_c'] > g['wage_a'] for g in G),
                                    greedy_more_unit_hours_games=sum(g['uh_c'] > g['uh_a'] for g in G))
    del r, G

    src = open(os.path.join(ROOT, 'scripts', 'layout_value.py'), encoding='utf-8').read()
    ns = {'__name__': 'lv_lib', '__file__': os.path.join(ROOT, 'scripts', 'layout_value.py')}
    exec(compile(src, 'layout_value', 'exec'), ns)
    simulate, instance, greedy, unlocked_by_day, dist_shed = (ns['simulate'], ns['instance'], ns['greedy_relayout'],
                                                            ns['unlocked_by_day'], ns['dist_shed'])
    pool_orig = list(ns['ALL_TILES'])
    pool_shed = [(x, y) for y in range(10) for x in range(10)]
    res['ALL_TILES_len_original'] = len(pool_orig)
    res['shed_tiles_in_original_pool'] = sum(1 for t in pool_orig if t in SHED)

    board = Counter()
    rows = []
    paths = sorted(glob.glob(os.path.join(ROOT, 'data', 'dsm_tapes', '56444344', '*.json.gz')))
    for p in paths:
        with gzip.open(p, 'rt', encoding='utf-8') as fh:
            t = json.load(fh)
        # 2. board occupancy of the shed tiles
        kind = {}
        for d, b in enumerate(t['boards']):
            flat = ''.join(b)
            labs = [flat[2 * i:2 * i + 2] for i in range(100)]
            for i, lab in enumerate(labs):
                if lab == 'go':
                    kind[i] = 'COOP'
                elif lab in ('sh', 'pa'):
                    kind[i] = 'PASTURE'
            for i, lab in enumerate(labs):
                exact_animal = lab in ('sh', 'go')
                co = lab == 'co'
                cow = co and kind.get(i) == 'PASTURE'
                co_unres = co and i not in kind
                board['animal_exact_td'] += exact_animal
                board['co_td'] += co
                board['co_cow_td'] += cow
                board['co_unresolved_td'] += co_unres
                if i in SHED_IDX:
                    board['shed_animal_exact_td'] += exact_animal
                    board['shed_co_td'] += co
                    board['shed_co_cow_td'] += cow
                    board['shed_co_unresolved_td'] += co_unres
                    if 12 <= d <= 23:
                        board['d12_23_shed_unlocked'] += lab != ' L'
                        board['d12_23_shed_animal_lo'] += exact_animal or cow
                        board['d12_23_shed_animal_hi'] += exact_animal or co
                if 12 <= d <= 23 and i == 0:
                    board['d12_23_gamedays'] += 1
        # 3. greedy with and without the shed tiles
        acts = [a if isinstance(a, dict) else {} for a in t['actions']]
        sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
        unlocked = unlocked_by_day(t['boards'])
        freq, first_day = Counter(), {}
        for day in range(30):
            units, routes, busy, c = instance(sim, day)
            for rr in routes.values():
                for j in rr:
                    freq[j.tile] += 1
                    first_day[j.tile] = min(first_day.get(j.tile, day), day)
        tot = sum(freq.values())
        ns['ALL_TILES'] = pool_orig
        m1 = greedy(freq, first_day, unlocked)
        ns['ALL_TILES'] = pool_shed
        m2 = greedy(freq, first_day, unlocked)
        rows.append(dict(a=sum(freq[x] * dist_shed(x) for x in freq) / tot,
                         g=sum(freq[x] * dist_shed(m1[x]) for x in freq) / tot,
                         g_shed=sum(freq[x] * dist_shed(m2[x]) for x in freq) / tot,
                         shed_visit_share_actual=sum(freq[x] for x in freq if x in SHED) / tot,
                         n_tiles=len(freq)))
        del t, acts, sim
    at = board['animal_exact_td'] + board['co_cow_td']
    res['dsm_56444344_boards'] = dict(
        games=len(paths),
        animal_tile_days_on_shed_share_sh_go_plus_resolved_cows=round((board['shed_animal_exact_td'] + board['shed_co_cow_td']) / max(1, at), 4),
        co_tile_days=board['co_td'], co_unresolved_tile_days=board['co_unresolved_td'],
        days12_23_per_gameday=dict(shed_tiles_unlocked=round(board['d12_23_shed_unlocked'] / board['d12_23_gamedays'], 2),
                                   shed_tiles_with_animal_low=round(board['d12_23_shed_animal_lo'] / board['d12_23_gamedays'], 2),
                                   shed_tiles_with_animal_high=round(board['d12_23_shed_animal_hi'] / board['d12_23_gamedays'], 2)))
    res['greedy_recompute'] = dict(
        games=len(rows), actual=round(st.mean(x['a'] for x in rows), 3), greedy_no_shed=round(st.mean(x['g'] for x in rows), 3),
        greedy_with_shed=round(st.mean(x['g_shed'] for x in rows), 3),
        games_greedy_no_shed_farther=sum(x['g'] > x['a'] for x in rows),
        games_greedy_with_shed_farther=sum(x['g_shed'] > x['a'] for x in rows),
        actual_visit_share_on_shed_tiles=round(st.mean(x['shed_visit_share_actual'] for x in rows), 4),
        mean_distinct_tiles_used=round(st.mean(x['n_tiles'] for x in rows), 1))
    txt = json.dumps(res, indent=1)
    with open(os.path.join(HERE, 'verify_geometry_layout.json'), 'w', encoding='utf-8') as fh:
        fh.write(txt)
    print(txt)


if __name__ == '__main__':
    main()

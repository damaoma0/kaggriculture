"""Skeptic re-derivation of the board-geometry claims (independent of geometry.py; stored data only).

Source: data/leader_semantics/<team>/<episode>.json.gz, leader seat only (meta.seat), day-start boards,
labels per data/leader_semantics/README.md (index = y*10+x; 'co' = cow OR empty coop).

'co' resolution here: structure kind per tile tracked from BOTH (a) built/dug records (built on day d -> on board d+1)
and (b) label history ('go' seen -> COOP, 'sh'/'pa' seen -> PASTURE). 'co' on COOP -> empty coop, on PASTURE -> cow.
Also reports the two bounds (all 'co' = cow, all 'co' = empty coop) and counts conflicts between (a) and (b).
Distance = min Manhattan distance to the four shed-access tiles (engine _shed_access_tiles: (4,4),(5,4),(4,5),(5,5)).
Quadrant orientation check: engine LAND_ORDER = NE, SW, SE, so with index y*10+x the NE block must unlock first.

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/verify_geometry_boards.py
"""
import glob
import gzip
import json
import os
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OUT = os.path.dirname(os.path.abspath(__file__))
TEAMS = {'16732748': 'DSM', '16623559': 'DECEM', '16770421': 'Vadim', '16730612': 'MG', '16681125': 'MMPQ',
         '16915014': 'Boey'}
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
DIST = [min(abs(i % 10 - sx) + abs(i // 10 - sy) for sx, sy in SHED) for i in range(100)]
CROP = {'ST', 'TO', 'ME', 'WH', 'CA'}


def quad(i):
    x, y = i % 10, i // 10
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def main():
    pooled = defaultdict(Counter)        # variant -> Counter of (group, dist)
    team_sum = defaultdict(lambda: [0, 0, 0, 0])   # team -> [anim n, anim sum, crop n, crop sum]
    games_closer_all = games_closer_6 = games = 0
    games_closer_all_upper = games_closer_all_lower = 0
    conflicts = unresolved = co_total = 0
    unlock = defaultdict(list)
    order_ok = order_bad = 0
    ring = Counter()                     # days 12-23: per game-day counts
    gd_12_23 = 0
    seats = Counter()
    per_game_diff6 = []
    files_used = 0
    for tid, team in TEAMS.items():
        for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'leader_semantics', tid, '*.json.gz'))):
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                g = json.load(fh)
            files_used += 1
            seats[(team, g['meta']['seat'], g['meta']['team'])] += 1
            kind_b = {}                  # from build records
            kind_l = {}                  # from label history
            an_all, cr_all, an6, cr6 = [], [], [], []
            an_up, an_lo = [], []
            first_unl = {}
            for d, day in enumerate(g['days']):
                b = day['board']
                for i, lab in enumerate(b):
                    if lab == 'go':
                        kind_l[i] = 'COOP'
                    elif lab in ('sh', 'pa'):
                        kind_l[i] = 'PASTURE'
                    if lab != ' L':
                        q = quad(i)
                        if q not in first_unl:
                            first_unl[q] = d
                for i, lab in enumerate(b):
                    dd = DIST[i]
                    grp = None
                    if lab in CROP:
                        grp = 'crop'
                    elif lab in ('sh', 'go'):
                        grp = 'animal'
                    elif lab == 'co':
                        co_total += 1
                        kb, kl = kind_b.get(i), kind_l.get(i)
                        if kb and kl and kb != kl:
                            conflicts += 1
                        k = kb or kl
                        if k == 'PASTURE':
                            grp = 'animal'
                        elif k is None:
                            unresolved += 1
                        an_up.append(dd)         # upper bound: every 'co' is a cow
                    if grp == 'animal':
                        an_all.append(dd)
                        if lab != 'co':
                            an_up.append(dd)
                            an_lo.append(dd)
                        if d >= 6:
                            an6.append(dd)
                        pooled['resolved'][('animal', dd)] += 1
                        team_sum[team][0] += 1
                        team_sum[team][1] += dd
                    elif grp == 'crop':
                        cr_all.append(dd)
                        if d >= 6:
                            cr6.append(dd)
                        pooled['resolved'][('crop', dd)] += 1
                        team_sum[team][2] += 1
                        team_sum[team][3] += dd
                if 12 <= d <= 23:
                    gd_12_23 += 1
                    for i, lab in enumerate(b):
                        r = 'd0' if DIST[i] == 0 else 'd12' if DIST[i] <= 2 else None
                        if r is None or lab == ' L':
                            continue
                        ring[(r, 'unlocked')] += 1
                        if lab in CROP:
                            ring[(r, 'crop')] += 1
                        elif lab in ('sh', 'go') or (lab == 'co' and (kind_b.get(i) or kind_l.get(i)) == 'PASTURE'):
                            ring[(r, 'animal')] += 1
                        elif lab == ' .':
                            ring[(r, 'empty')] += 1
                        else:
                            ring[(r, 'structure_empty')] += 1
                # structures built during day d appear on board d+1; dug tiles lose their kind
                for t in day.get('dug') or []:
                    kind_b.pop(t, None)
                for k, ts in (day.get('built') or {}).items():
                    for t in ts:
                        kind_b[t] = 'COOP' if k == 'BUILD_COOP' else 'PASTURE'
            games += 1
            m = lambda v: sum(v) / len(v) if v else None
            if an_all and cr_all and m(an_all) < m(cr_all):
                games_closer_all += 1
            if an6 and cr6:
                per_game_diff6.append(m(an6) - m(cr6))
                if m(an6) < m(cr6):
                    games_closer_6 += 1
            if an_up and cr_all and m(an_up) < m(cr_all):
                games_closer_all_upper += 1
            if an_lo and cr_all and m(an_lo) < m(cr_all):
                games_closer_all_lower += 1
            for q, d in first_unl.items():
                unlock[q].append(d)
            if 'NE' in first_unl and 'SW' in first_unl:
                if first_unl['NE'] <= first_unl['SW']:
                    order_ok += 1
                else:
                    order_bad += 1
    res = {'files_used': files_used, 'games': games, 'seat_team_check': {f'{k[0]}|seat{k[1]}|meta.team={k[2]}': v for k, v in seats.items()}}
    P = pooled['resolved']
    for grp in ('animal', 'crop'):
        n = sum(v for (g_, _), v in P.items() if g_ == grp)
        s = sum(v * dd for (g_, dd), v in P.items() if g_ == grp)
        res[grp] = dict(tile_days=n, mean_dist=round(s / n, 3),
                        share_d0=round(sum(v for (g_, dd), v in P.items() if g_ == grp and dd == 0) / n, 4),
                        share_le1=round(sum(v for (g_, dd), v in P.items() if g_ == grp and dd <= 1) / n, 4),
                        share_le2=round(sum(v for (g_, dd), v in P.items() if g_ == grp and dd <= 2) / n, 4))
    res['games_animals_closer_all_days'] = games_closer_all
    res['games_animals_closer_days6_29'] = games_closer_6
    res['games_animals_closer_if_all_co_are_cows'] = games_closer_all_upper
    res['games_animals_closer_if_no_co_is_a_cow'] = games_closer_all_lower
    ds = sorted(per_game_diff6)
    res['per_game_anim_minus_crop_days6_29'] = dict(mean=round(sum(ds) / len(ds), 3), p10=round(ds[int(.1 * (len(ds) - 1) + .5)], 3),
                                                   p90=round(ds[int(.9 * (len(ds) - 1) + .5)], 3), n=len(ds))
    res['co_label'] = dict(tile_days=co_total, unresolved=unresolved, build_vs_label_conflicts=conflicts)
    res['per_team_anim_vs_crop'] = {t: (round(v[1] / v[0], 2), round(v[3] / v[2], 2)) for t, v in team_sum.items()}
    res['unlock_day_median'] = {q: sorted(v)[len(v) // 2] for q, v in unlock.items()}
    res['unlock_games'] = {q: len(v) for q, v in unlock.items()}
    res['NE_unlocks_before_or_with_SW'] = [order_ok, order_bad]
    res['ring_days12_23_per_gameday'] = {f'{r}_{k}': round(v / gd_12_23, 2) for (r, k), v in sorted(ring.items())}
    txt = json.dumps(res, indent=1)
    with open(os.path.join(OUT, 'verify_geometry_boards.json'), 'w', encoding='utf-8') as fh:
        fh.write(txt)
    print(txt)


if __name__ == '__main__':
    main()

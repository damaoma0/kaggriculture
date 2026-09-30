"""Skeptic follow-up: what do the dead-reckoned routes say about the fertilizer pick-up (stored data only)?

Uses the same reckoning as verify_geometry_fert.py (imported by exec, read-only) on the leader tapes, only on days
where the reckoned hand count equals semantics labour.hands_present (positions validated there at 99.99% against
effective FERTILIZE tiles). A 'stay' = a unit's maximal run of consecutive non-move commands on one tile.

Per COLLECT_FERTILIZER command:
  a) same stay also has FEED / CARE / HARVEST by the same unit
  b) else the same unit FEED/CARE/HARVESTs that tile at another time that day
  c) else another unit FEED/CAREs that tile that day
  d) else nobody services the tile that day (collect-only animal)
For collect-only stays (no other op in the stay): walking detour = d(prev stay, tile) + d(tile, next stay) -
d(prev stay, next stay), prev = spawn tile for a unit's first stay. Also market FERTILIZER totals from semantics
(summed over the game, so the README's one-day market offset does not matter) and fourth-quadrant purchase per team.

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/verify_geometry_routes.py
"""
import glob
import gzip
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ns = {'__name__': 'vg_lib', '__file__': os.path.join(HERE, 'verify_geometry_fert.py')}
exec(compile(open(os.path.join(HERE, 'verify_geometry_fert.py'), encoding='utf-8').read(), 'vgf', 'exec'), ns)
reckon, dist, MOVES, TEAMS, ROOT = ns['reckon'], ns['dist'], ns['MOVES'], ns['TEAMS'], ns['ROOT']
SERVICE = {'FEED', 'CARE', 'HARVEST'}


def man(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def stays(seq):
    out = []                                   # (pos, [ops], first k)
    cur = None
    for k, (p, cm) in enumerate(seq):
        op = cm[0]
        if op in MOVES:
            cur = None
            continue
        if op == 'PASS':
            continue
        if cur is not None and cur[0] == p:
            cur[1].append(op)
        else:
            cur = (p, [op], k)
            out.append(cur)
    return out


def main():
    res = {}
    tot = Counter()
    for tid, team in TEAMS.items():
        c = Counter()
        se_games = 0
        se_bought = Counter()
        for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'leader_semantics', tid, '*.json.gz'))):
            ep = os.path.basename(f).split('.')[0]
            tp = glob.glob(os.path.join(ROOT, 'data', 'leader_tapes', f'{tid}_*', f'{ep}.json.gz'))
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                sem = json.load(fh)
            with gzip.open(tp[0], 'rt', encoding='utf-8') as fh:
                t = json.load(fh)
            c['games'] += 1
            mk = [dy.get('market') or {} for dy in sem['days']]
            for m in mk:
                c['fert_bought_units'] += (m.get('bought_units') or {}).get('FERTILIZER', 0)
                c['fert_bought_spend'] += (m.get('bought_spend') or {}).get('FERTILIZER', 0)
                c['fert_sold_units'] += (m.get('sold_units') or {}).get('FERTILIZER', 0)
                c['fert_sold_rev'] += (m.get('sold_revenue') or {}).get('FERTILIZER', 0)
            if any(lab != ' L' for dy in sem['days'] for i, lab in enumerate(dy['board']) if i % 10 >= 5 and i // 10 >= 5):
                se_games += 1
            days, spawned = reckon(t['actions'])
            for d, units in days.items():
                if d >= 30 or (sem['days'][d].get('labour') or {}).get('hands_present') != spawned.get(d, 0):
                    continue
                c['moves'] += sum(1 for seq in units.values() for _, cm in seq if cm[0] in MOVES)
                svc = {}                                    # tile -> set of units that FEED/CARE/HARVEST it
                st_by_u = {u: stays(seq) for u, seq in units.items()}
                for u, sl in st_by_u.items():
                    for p, ops, _ in sl:
                        if set(ops) & SERVICE:
                            svc.setdefault(p, set()).add(u)
                for u, sl in st_by_u.items():
                    spawn_p = units[u][0][0]
                    for j, (p, ops, _) in enumerate(sl):
                        nc = ops.count('COLLECT_FERTILIZER')
                        if not nc:
                            continue
                        c['collect'] += nc
                        if set(ops) & SERVICE:
                            c['a_same_stay_service'] += nc
                        elif u in svc.get(p, ()):
                            c['b_same_unit_other_time'] += nc
                        elif svc.get(p):
                            c['c_other_unit_services'] += nc
                        else:
                            c['d_no_service'] += nc
                        if all(o == 'COLLECT_FERTILIZER' for o in ops):
                            prev = sl[j - 1][0] if j > 0 else spawn_p
                            if j + 1 < len(sl):
                                nxt = sl[j + 1][0]
                                det = man(prev, p) + man(p, nxt) - man(prev, nxt)
                                c['collect_only_stays_with_next'] += 1
                                c['collect_only_detour_steps'] += det
                                c['collect_only_zero_detour'] += det == 0
                            else:
                                c['collect_only_stays_last'] += 1
        n = c['collect'] or 1
        g = c['games']
        res[team] = dict(
            games=g, collect_per_game=round(c['collect'] / g, 1),
            a_same_stay_service=round(c['a_same_stay_service'] / n, 4),
            b_same_unit_other_time=round(c['b_same_unit_other_time'] / n, 4),
            c_other_unit_services_tile=round(c['c_other_unit_services'] / n, 4),
            d_nobody_services_tile=round(c['d_no_service'] / n, 4),
            collect_only_stays_per_validated_game=round(c['collect_only_stays_with_next'] / g, 1),
            collect_only_detour_steps_per_game=round(c['collect_only_detour_steps'] / g, 1),
            collect_only_zero_detour_share=round(c['collect_only_zero_detour'] / max(1, c['collect_only_stays_with_next']), 4),
            moves_per_game_validated_days=round(c['moves'] / g, 1),
            fert_bought_per_game=round(c['fert_bought_units'] / g, 1),
            fert_sold_per_game=round(c['fert_sold_units'] / g, 1),
            fert_buy_unit_price=round(c['fert_bought_spend'] / c['fert_bought_units'], 1) if c['fert_bought_units'] else None,
            fert_sell_unit_price=round(c['fert_sold_rev'] / c['fert_sold_units'], 1) if c['fert_sold_units'] else None,
            games_with_4th_quadrant=se_games)
        tot.update(c)
    n = tot['collect'] or 1
    g = tot['games']
    res['ALL_LEADERS'] = dict(
        games=g, a_same_stay_service=round(tot['a_same_stay_service'] / n, 4),
        b_same_unit_other_time=round(tot['b_same_unit_other_time'] / n, 4),
        c_other_unit_services_tile=round(tot['c_other_unit_services'] / n, 4),
        d_nobody_services_tile=round(tot['d_no_service'] / n, 4),
        collect_only_detour_steps_per_game=round(tot['collect_only_detour_steps'] / g, 1),
        collect_only_zero_detour_share=round(tot['collect_only_zero_detour'] / max(1, tot['collect_only_stays_with_next']), 4),
        moves_per_game_validated_days=round(tot['moves'] / g, 1))
    txt = json.dumps(res, indent=1)
    with open(os.path.join(HERE, 'verify_geometry_routes.json'), 'w', encoding='utf-8') as fh:
        fh.write(txt)
    print(txt)


if __name__ == '__main__':
    main()

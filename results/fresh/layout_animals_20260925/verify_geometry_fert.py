"""Skeptic re-derivation of the fertilizer-source / 'outbound' claims (independent of geometry.py; stored data only).

Leaders: data/leader_tapes/<team>_<sub>/<episode>.json.gz ('actions' = the leader seat; checked against
names[seat] and the semantics file's meta.seat), matched to data/leader_semantics/<team>/<episode>.json.gz.
Ours: results/fresh/lead_world_trace/<agent>_<episode>.json ('actions'), checked against
results/fresh/lead_cycles/<agent>/<episode>.json (final cash, per-game FERTILIZE / COLLECT command totals).

Dead reckoning (engine 1.32.7 rules, kaggriculture.py): step s acts on day s//24; the farmer respawns at (4,4) every
day; unit moves off-board are no-ops (locked tiles are passable); HIRE orders among the first 10 market orders spawn a
hand AFTER that step's unit actions, on the first shed-access tile in NWSE order with minimum occupancy
(_spawn_hand). A failed hire (cash) cannot be seen in the tape, so a day is only used for position metrics when the
reckoned number of hands equals the semantics labour.hands_present (dated correctly per README). Positions are
validated against the semantics maintenance.FERTILIZE / FEED tile sets (tiles where the command took effect).

Attribution per unit-day (inventories dump to the shed at midnight): FERTILIZE is 'collected' if the unit has an
unused earlier COLLECT_FERTILIZER that day (FIFO match), else 'shed' if it has unused requested PICKUP FERTILIZER
units, else 'none'; the shed-first order gives the other bound. PICKUP units are REQUESTED n (the engine takes
min(n, shed stock)).

usage: .venv/Scripts/python.exe results/fresh/layout_animals_20260925/verify_geometry_fert.py
"""
import glob
import gzip
import json
import os
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
OUT = os.path.dirname(os.path.abspath(__file__))
TEAMS = {'16732748': 'DSM', '16623559': 'DECEM', '16770421': 'Vadim', '16730612': 'MG', '16681125': 'MMPQ',
         '16915014': 'Boey'}
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}
CROP_OPS = ('WATER', 'FERTILIZE', 'PLANT')


def dist(p):
    return min(abs(p[0] - a) + abs(p[1] - b) for a, b in SHED)


def spawn(positions):
    occ = {t: 0 for t in SHED}
    for p in positions:
        if p in occ:
            occ[p] += 1
    return sorted(occ.items(), key=lambda kv: (kv[1], SHED.index(kv[0])))[0][0]


def reckon(actions):
    """-> {day: {unit: [(pos_before, cmd), ...]}}, {day: hands spawned}"""
    days, spawned = {}, Counter()
    pos = [(4, 4)]
    for s, a in enumerate(actions):
        if isinstance(a, str):
            a = json.loads(a)
        a = a if isinstance(a, dict) else {}
        d = s // 24
        cmds = [a.get('farmer') or ['PASS']] + list(a.get('hands') or [])
        dd = days.setdefault(d, {})
        for u in range(len(pos)):
            c = cmds[u] if u < len(cmds) and cmds[u] else ['PASS']
            dd.setdefault(u, []).append((pos[u], list(c)))
            if c[0] in MOVES:
                dx, dy = MOVES[c[0]]
                nx, ny = pos[u][0] + dx, pos[u][1] + dy
                if 0 <= nx < 10 and 0 <= ny < 10:
                    pos[u] = (nx, ny)
        for o in (a.get('market') or [])[:10]:
            if o and o[0] == 'HIRE':
                pos.append(spawn(pos))
                spawned[d] += 1
        if (s + 1) % 24 == 0:
            pos = [(4, 4)]
    return days, spawned


class Stats:
    def __init__(self):
        self.c = Counter()
        self.games = 0

    def unit_day(self, seq, use_pos):
        c = self.c
        coll = []                 # FIFO of (k, pos)
        pick = 0
        coll2, pick2 = 0, 0
        first_crop = None
        n_col_before_crop = 0
        n_col = 0
        maxd = 0
        maxd_before = {}
        for k, (p, cm) in enumerate(seq):
            op = cm[0]
            if op in CROP_OPS and first_crop is None:
                first_crop = k
            if op == 'COLLECT_FERTILIZER':
                n_col += 1
                coll.append((k, p))
                coll2 += 1
                maxd_before[k] = maxd
                if first_crop is None:
                    n_col_before_crop += 1
                # same stay (no move between) on this tile with a FEED or CARE by the same unit
                j0 = k
                while j0 > 0 and seq[j0 - 1][1][0] not in MOVES:
                    j0 -= 1
                j1 = k
                while j1 + 1 < len(seq) and seq[j1 + 1][1][0] not in MOVES:
                    j1 += 1
                stay_ops = {seq[j][1][0] for j in range(j0, j1 + 1)}
                c['collect_cmds'] += 1
                c['collect_same_stay_feed_or_care'] += bool(stay_ops & {'FEED', 'CARE'})
                if use_pos:
                    c['collect_pos_n'] += 1
                    c['collect_on_shed_tile'] += dist(p) == 0
            elif op == 'PICKUP' and len(cm) > 1 and cm[1] == 'FERTILIZER':
                n = cm[2] if len(cm) > 2 and isinstance(cm[2], int) else 1
                pick += n
                pick2 += n
                c['pickup_fert_cmds'] += 1
                c['pickup_fert_units_requested'] += n
            elif op == 'FERTILIZE':
                c['fert_cmds'] += 1
                if coll:
                    kc, pc = coll.pop(0)
                    c['src_collected'] += 1
                    shed_between = any(seq[j][1][0] in ('PICKUP', 'DROP') or
                                       (seq[j][1][0] == 'PLACE' and len(seq[j][1]) > 1 and seq[j][1][1] == 'FERTILIZER')
                                       for j in range(kc + 1, k))
                    c['src_collected_shed_op_between'] += shed_between
                    if use_pos:
                        c['pos_n'] += 1
                        dc, df = dist(pc), dist(p)
                        c['pos_collect_nearer'] += dc < df
                        c['pos_equal'] += dc == df
                        c['pos_collect_farther'] += dc > df
                        c['pos_sum_dc'] += dc
                        c['pos_sum_df'] += df
                        walked = sum(1 for j in range(kc + 1, k) if seq[j][1][0] in MOVES)
                        man = abs(pc[0] - p[0]) + abs(pc[1] - p[1])
                        c['pos_walked'] += walked
                        c['pos_manhattan'] += man
                        c['pos_no_detour'] += walked == man
                        # strict outbound: before the collect the unit had never been farther out than the
                        # collect tile, and the fertilized tile is farther out than the collect tile
                        c['pos_strict_outbound'] += (maxd_before[kc] <= dc < df)
                elif pick > 0:
                    pick -= 1
                    c['src_shed'] += 1
                else:
                    c['src_none'] += 1
                if pick2 > 0:
                    pick2 -= 1
                    c['lb_shed'] += 1
                elif coll2 > 0:
                    coll2 -= 1
                    c['lb_collected'] += 1
            if use_pos:
                maxd = max(maxd, dist(p))
        if n_col and first_crop is not None:
            c['collects_in_ud_with_crop_op'] += n_col
            c['collects_before_first_crop_op'] += n_col_before_crop

    def summary(self):
        c, g = self.c, max(1, self.games)
        fc = max(1, c['fert_cmds'])
        out = dict(games=self.games,
                   per_game=dict(collect=round(c['collect_cmds'] / g, 1), fertilize_cmds=round(c['fert_cmds'] / g, 1),
                                 pickup_fert_cmds=round(c['pickup_fert_cmds'] / g, 1),
                                 pickup_fert_units_requested=round(c['pickup_fert_units_requested'] / g, 1)),
                   fert_from_same_unit_collect_collected_first=round(c['src_collected'] / fc, 4),
                   fert_from_same_unit_collect_shed_first=round(c['lb_collected'] / fc, 4),
                   fert_from_shed_pickup_collected_first=round(c['src_shed'] / fc, 4),
                   fert_no_source=round(c['src_none'] / fc, 4),
                   collected_sourced_with_shed_op_between=round(c['src_collected_shed_op_between'] / max(1, c['src_collected']), 4),
                   collects_before_first_crop_op=round(c['collects_before_first_crop_op'] / max(1, c['collects_in_ud_with_crop_op']), 4),
                   collects_used_same_unit_day=round(c['src_collected'] / max(1, c['collect_cmds']), 4),
                   collect_in_same_stay_as_feed_or_care=round(c['collect_same_stay_feed_or_care'] / max(1, c['collect_cmds']), 4))
        if c['pos_n']:
            n = c['pos_n']
            out['position_metrics'] = dict(
                n_collected_sourced_fert=n,
                collect_tile_nearer_shed_than_fert_tile=round(c['pos_collect_nearer'] / n, 4),
                equal=round(c['pos_equal'] / n, 4), collect_tile_farther=round(c['pos_collect_farther'] / n, 4),
                mean_dist_collect_tile=round(c['pos_sum_dc'] / n, 3), mean_dist_fert_tile=round(c['pos_sum_df'] / n, 3),
                walked_over_manhattan_collect_to_fert=round(c['pos_walked'] / max(1, c['pos_manhattan']), 3),
                no_detour_share=round(c['pos_no_detour'] / n, 4),
                strict_outbound_share=round(c['pos_strict_outbound'] / n, 4),
                collects_on_a_shed_tile=round(c['collect_on_shed_tile'] / max(1, c['collect_pos_n']), 4))
        return out


def run_leaders(res):
    allst = Stats()
    val = Counter()
    for tid, team in TEAMS.items():
        st = Stats()
        for f in sorted(glob.glob(os.path.join(ROOT, 'data', 'leader_semantics', tid, '*.json.gz'))):
            ep = os.path.basename(f).split('.')[0]
            tp = glob.glob(os.path.join(ROOT, 'data', 'leader_tapes', f'{tid}_*', f'{ep}.json.gz'))
            if len(tp) != 1:
                val['tape_missing_or_duplicate'] += 1
                continue
            with gzip.open(f, 'rt', encoding='utf-8') as fh:
                sem = json.load(fh)
            with gzip.open(tp[0], 'rt', encoding='utf-8') as fh:
                t = json.load(fh)
            val['seat_match'] += t['seat'] == sem['meta']['seat']
            val['name_is_team'] += (t['names'][t['seat']] == sem['meta']['team'])
            days, spawned = reckon(t['actions'])
            st.games += 1
            allst.games += 1
            val['maint_fert_tiles'] += sum(len((dy.get('maintenance') or {}).get('FERTILIZE') or []) for dy in sem['days'])
            for d, units in days.items():
                if d >= 30:
                    continue
                sd = sem['days'][d]
                hp = (sd.get('labour') or {}).get('hands_present')
                ok = hp == spawned.get(d, 0)
                val['days'] += 1
                val['days_hands_match'] += ok
                mf = set((sd.get('maintenance') or {}).get('FERTILIZE') or [])
                mfeed = set((sd.get('maintenance') or {}).get('FEED') or [])
                for u, seq in units.items():
                    if ok:
                        for p, cm in seq:
                            if cm[0] == 'FERTILIZE':
                                val['fert_pos_n'] += 1
                                val['fert_pos_in_effective_set'] += (p[1] * 10 + p[0]) in mf
                            elif cm[0] == 'FEED':
                                val['feed_pos_n'] += 1
                                val['feed_pos_in_effective_set'] += (p[1] * 10 + p[0]) in mfeed
                    st.unit_day(seq, ok)
                    allst.unit_day(seq, ok)
        res[team] = st.summary()
    res['ALL_LEADERS'] = allst.summary()
    res['leader_validation'] = dict(val)
    res['leader_validation']['fert_pos_match_rate'] = round(val['fert_pos_in_effective_set'] / max(1, val['fert_pos_n']), 4)
    res['leader_validation']['feed_pos_match_rate'] = round(val['feed_pos_in_effective_set'] / max(1, val['feed_pos_n']), 4)


def run_ours(res):
    for agent in ('mgt_lpv_dep6', 'mgt_lpv_q4'):
        st = Stats()
        chk = Counter()
        for f in sorted(glob.glob(os.path.join(ROOT, 'results', 'fresh', 'lead_world_trace', f'{agent}_*.json'))):
            with open(f, encoding='utf-8') as fh:
                r = json.load(fh)
            ep = str(r['episode'])
            lc = os.path.join(ROOT, 'results', 'fresh', 'lead_cycles', agent, ep + '.json')
            days, _ = reckon(r['actions'])
            st.games += 1
            fert_t = coll_t = 0
            for d, units in days.items():
                for u, seq in units.items():
                    st.unit_day(seq, False)
                    fert_t += sum(1 for _, cm in seq if cm[0] == 'FERTILIZE')
                    coll_t += sum(1 for _, cm in seq if cm[0] == 'COLLECT_FERTILIZER')
            if os.path.exists(lc):
                with open(lc, encoding='utf-8') as fh:
                    c = json.load(fh)
                chk['lead_cycles_found'] += 1
                chk['final_cash_match'] += (c.get('final') == r.get('final'))
                wk = c.get('work') or []
                wf = sum(v.get('op_FERTILIZE', 0) for day in wk for v in day.values())
                wc = sum(v.get('op_COLLECT_FERTILIZER', 0) for day in wk for v in day.values())
                chk['fert_cmd_total_match'] += (wf == fert_t)
                chk['collect_cmd_total_match'] += (wc == coll_t)
                chk['has_boards'] += bool(c.get('boards'))
        res['OURS_' + agent] = st.summary()
        res['OURS_' + agent]['cross_check_vs_lead_cycles'] = dict(chk)


def main():
    res = {}
    run_leaders(res)
    run_ours(res)
    txt = json.dumps(res, indent=1)
    with open(os.path.join(OUT, 'verify_geometry_fert.json'), 'w', encoding='utf-8') as fh:
        fh.write(txt)
    print(txt)


if __name__ == '__main__':
    main()

"""Route order from STORED action streams (no games): unit positions are rebuilt from the engine's spawn rules and the
recorded moves (moves never fail in these streams; ledger: 0 no-effect moves), then per unit-day tile-op sequences.

usage: lead_route_order.py
Sides: leader = the leader's own actions in the 12 G1 worlds (data/leader_tapes); ours = the current default deploy in
the 12 smoke worlds (results/fresh/lead_world_trace/mgt_lpv_dep7_*.json, our returned action dicts); opp = the recorded
2750-3000 opponents in the same 12 smoke worlds (data/ladder_panel/p2750 opp_actions).
"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
MOVES = {'NORTH': (0, -1), 'SOUTH': (0, 1), 'EAST': (1, 0), 'WEST': (-1, 0)}
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
TILE_OPS = {'WATER', 'FEED', 'CARE', 'HARVEST', 'FERTILIZE', 'COLLECT_FERTILIZER', 'PLANT', 'DIG', 'BUILD_COOP',
            'BUILD_PASTURE', 'PLACE'}
SMOKE = [110937191, 111374151, 111376633, 111416249, 111554912, 111577649, 111681195, 111688786, 111871547,
         111902048, 111916514, 111941962]


def spawn(pos):
    occ = {t: 0 for t in SHED}
    for p in pos:
        if tuple(p) in occ:
            occ[tuple(p)] += 1
    return list(sorted(occ.items(), key=lambda kv: (kv[1], SHED.index(kv[0])))[0][0])


def quad(p):
    return ('N' if p[1] < 5 else 'S') + ('W' if p[0] < 5 else 'E')


def shed_d(p):
    return min(abs(p[0] - sx) + abs(p[1] - sy) for sx, sy in SHED)


def rebuild(actions):
    """per day: {unit: [(hour, kind, op, pos)]} with kind 'move' / 'op' / 'shed' / 'pass'; plus unit-steps."""
    days = [defaultdict(list) for _ in range(30)]
    steps = [0] * 30
    pos = []
    for t, a in enumerate(actions[:719]):
        d, h = divmod(t, 24)
        if h == 0:
            pos = [[4, 4]]                      # farmer at the default spawn; hands vanished at midnight
        a = a if isinstance(a, dict) else {}
        hands = a.get('hands') or []
        while len(pos) - 1 < len(hands):
            pos.append(spawn(pos))
        steps[d] += len(pos)
        units = [a.get('farmer') or ['PASS']] + list(hands)
        for u, act in enumerate(units):
            if u >= len(pos):
                break
            op = act[0] if isinstance(act, list) and act else 'PASS'
            p = tuple(pos[u])
            if op in MOVES:
                dx, dy = MOVES[op]
                pos[u] = [min(9, max(0, p[0] + dx)), min(9, max(0, p[1] + dy))]
                days[d][u].append((h, 'move', op, p))
            elif op in ('PICKUP', 'DROP') or (op == 'PLACE' and p in SHED):
                days[d][u].append((h, 'shed', op, p))
            elif op in TILE_OPS:
                days[d][u].append((h, 'op', op, p))
            else:
                days[d][u].append((h, 'pass', op, p))
    return days, steps


def metrics(days, steps, lo, hi):
    m = Counter()
    for d in range(lo, hi + 1):
        visits_by_tile = defaultdict(set)
        first_q = []
        for u, seq in days[d].items():
            ops = [(h, op, p) for h, k, op, p in seq if k == 'op']
            m['moves'] += sum(1 for x in seq if x[1] == 'move')
            m['shed_actions'] += sum(1 for x in seq if x[1] == 'shed')
            m['ops'] += len(ops)
            for h, op, p in ops:
                visits_by_tile[p].add(u)
            if not ops:
                continue
            first_q.append(quad(ops[0][2]))
            m['first_shed_d'] += shed_d(ops[0][2])
            m['first_n'] += 1
            if len(ops) < 2:
                continue
            m['unit_days'] += 1
            qs = Counter(quad(p) for _, _, p in ops)
            m['quadrants'] += len(qs)
            m['modal_share'] += qs.most_common(1)[0][1] / len(ops)
            xs, ys = [p[0] for _, _, p in ops], [p[1] for _, _, p in ops]
            m['bbox'] += (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
            # consecutive ops: distance, and the moves actually walked between them
            idx_ops = [i for i, x in enumerate(seq) if x[1] == 'op']
            for a_, b_ in zip(idx_ops, idx_ops[1:]):
                pa, pb = seq[a_][3], seq[b_][3]
                dist = abs(pa[0] - pb[0]) + abs(pa[1] - pb[1])
                walked = sum(1 for x in seq[a_ + 1:b_] if x[1] == 'move')
                shed_between = any(x[1] == 'shed' for x in seq[a_ + 1:b_])
                m['pairs'] += 1
                m['dist'] += dist
                m['walked'] += walked
                m['d0' if dist == 0 else 'd1' if dist == 1 else 'd2' if dist == 2 else 'd3+'] += 1
                if shed_between:
                    m['pairs_via_shed'] += 1
                    m['walked_via_shed'] += walked
            # tile visits (runs of same-tile ops) and sweeps (runs of visits to adjacent tiles)
            tiles = [ops[0][2]]
            for _, _, p in ops[1:]:
                if p != tiles[-1]:
                    tiles.append(p)
            m['tile_visits'] += len(tiles)
            runs, cur = [], 1
            for a_, b_ in zip(tiles, tiles[1:]):
                if abs(a_[0] - b_[0]) + abs(a_[1] - b_[1]) <= 1:
                    cur += 1
                else:
                    runs.append(cur)
                    cur = 1
            runs.append(cur)
            m['sweeps'] += len(runs)
        shared = sum(1 for p, us in visits_by_tile.items() if len(us) >= 2)
        m['tiles_visited'] += len(visits_by_tile)
        m['tiles_shared'] += shared
        m['first_distinct_q'] += len(set(first_q))
        m['first_units'] += len(first_q)
        m['unit_steps'] += steps[d]
    return m


def load_sides():
    import lead_g1
    sides = {'leader': [], 'ours': [], 'opp': []}
    for g in lead_g1.GAMES:
        team, ep = g.split(':')
        tp = next(p for p in sorted(lead_g1.TAPES.glob(f'{team}_*/{ep}.json.gz')))
        sides['leader'].append(json.load(gzip.open(tp, 'rt', encoding='utf-8'))['actions'])
    for ep in SMOKE:
        f = ROOT / f'results/fresh/lead_world_trace/mgt_lpv_dep7_{ep}.json'
        if f.exists():
            sides['ours'].append([json.loads(x) for x in json.load(open(f))['actions']])
        g = json.load(gzip.open(ROOT / f'data/ladder_panel/p2750/{ep}.json.gz', 'rt', encoding='utf-8'))
        sides['opp'].append(g['opp_actions'])
    return sides


def main():
    sides = load_sides()
    rows = {}
    for s, games in sides.items():
        for (lo, hi) in ((0, 29), (12, 23)):
            m = Counter()
            for acts in games:
                days, steps = rebuild(acts)
                m.update(metrics(days, steps, lo, hi))
            rows[(s, lo, hi)] = (m, len(games))
    lines = [
        ('games', lambda m, g: '%d' % g),
        ('unit-steps / game', lambda m, g: '%.0f' % (m['unit_steps'] / g)),
        ('moves / game', lambda m, g: '%.0f' % (m['moves'] / g)),
        ('tile ops / game', lambda m, g: '%.0f' % (m['ops'] / g)),
        ('shed actions (pickup/drop/place) / game', lambda m, g: '%.0f' % (m['shed_actions'] / g)),
        ('mean distance between consecutive ops', lambda m, g: '%.2f' % (m['dist'] / max(1, m['pairs']))),
        ('moves walked between consecutive ops', lambda m, g: '%.2f' % (m['walked'] / max(1, m['pairs']))),
        ('  of which pairs with a shed stop between (share / moves each)', lambda m, g: '%.1f%% / %.1f' % (
            100 * m['pairs_via_shed'] / max(1, m['pairs']), m['walked_via_shed'] / max(1, m['pairs_via_shed']))),
        ('  moves between ops without a shed stop, per pair', lambda m, g: '%.2f' % (
            (m['walked'] - m['walked_via_shed']) / max(1, m['pairs'] - m['pairs_via_shed']))),
        ('consecutive-op distance 0 / 1 / 2 / 3+ (%)', lambda m, g: '/'.join('%.0f' % (100 * m[k] / max(1, m['pairs'])) for k in ('d0', 'd1', 'd2', 'd3+'))),
        ('ops per tile visit', lambda m, g: '%.2f' % (m['ops'] / max(1, m['tile_visits']))),
        ('tile visits per sweep (adjacent-tile run)', lambda m, g: '%.2f' % (m['tile_visits'] / max(1, m['sweeps']))),
        ('quadrants visited per unit-day', lambda m, g: '%.2f' % (m['quadrants'] / max(1, m['unit_days']))),
        ('share of a unit-day\'s ops in its main quadrant', lambda m, g: '%.0f%%' % (100 * m['modal_share'] / max(1, m['unit_days']))),
        ('op bounding box per unit-day (tiles)', lambda m, g: '%.1f' % (m['bbox'] / max(1, m['unit_days']))),
        ('tiles worked by >= 2 units the same day (share)', lambda m, g: '%.0f%%' % (100 * m['tiles_shared'] / max(1, m['tiles_visited']))),
        ('first-op quadrants distinct / units (start split)', lambda m, g: '%.2f' % (m['first_distinct_q'] / max(1, m['first_units']))),
        ('shed distance of a unit\'s first op of the day', lambda m, g: '%.2f' % (m['first_shed_d'] / max(1, m['first_n']))),
    ]
    print('| per game | leader (G1) all days | ours (smoke) all days | opp 2750+ (smoke) all days | leader d12-23 | ours d12-23 | opp d12-23 |')
    print('|---|---|---|---|---|---|---|')
    for label, f in lines:
        vals = [f(*rows[(s, lo, hi)]) for (lo, hi) in ((0, 29), (12, 23)) for s in ('leader', 'ours', 'opp')]
        print(f'| {label} | ' + ' | '.join(vals) + ' |')


if __name__ == '__main__':
    main()

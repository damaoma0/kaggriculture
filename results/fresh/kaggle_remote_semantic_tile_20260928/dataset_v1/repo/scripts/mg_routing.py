"""Where Mother-Goose's labour goes and how her crew is routed, versus our benchmark.

Pure analysis of recordings -- no simulation. Two sources, both giving, per step, every unit's
position and the verb it was commanded with:
  * her 30 replays (data/leaders_20260917), her seat: positions from the observation at step t,
    action from step t+1, so the tile a command lands on is exact;
  * our frozen benchmark's recording of HER seat in 8 of her worlds
    (results/fresh/labour_idle/<eid>-<seat>.json), same shops and seed.
Tiles are labelled from the DAY-START board on both sides, so the two are comparable.

Output: results/fresh/mg_executor/routing.json
"""
import json
from collections import Counter, defaultdict
from market_corpus import ROOT
from tape_vs_bench import mg_games
from extract_mg_events import tile_label

OUT = ROOT / 'results/fresh/mg_executor'
BENCH_DIR = ROOT / 'results/fresh/labour_idle'
MOVES = ('NORTH', 'SOUTH', 'EAST', 'WEST')
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
SHED_OPS = ('PICKUP', 'DROP')


def quad(x, y):
    return ('N' if y < 5 else 'S') + ('W' if x < 5 else 'E')


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


# ---------------------------------------------------------------- loading

def load_mg(path, eid, seat):
    replay = json.loads(open(path, encoding='utf-8').read())
    steps, boards, hire_orders = [], [], []
    for t in range(719):
        obs = replay['steps'][t][seat]['observation']
        if not obs.get('farms'):
            obs = replay['steps'][t][0]['observation']
        farm = obs['farms'][seat]
        if t % 24 == 0:
            boards.append([[tile_label(c) for c in row] for row in farm['tiles']])
        act = replay['steps'][t + 1][seat]['action'] or {}
        pos = [list(farm['farmer'])] + [list(h) for h in farm['hands']]
        cmds = [act.get('farmer')] + list(act.get('hands') or [])
        row = []
        for i, p in enumerate(pos):
            c = cmds[i] if i < len(cmds) else None
            op = c[0] if isinstance(c, list) and c and isinstance(c[0], str) else 'NONE'
            row.append((int(p[0]), int(p[1]), op))
        steps.append(row)
        for o in act.get('market') or []:
            if isinstance(o, list) and o and o[0] == 'HIRE':
                hire_orders.append((t // 24, t % 24))
    return dict(episode=eid, seat=seat, side='mg', steps=steps, boards=boards,
                hire_orders=hire_orders)


def load_bench(eid, seat):
    d = json.loads((BENCH_DIR / f'{eid}-{seat}.json').read_text(encoding='utf-8'))
    steps = [[(int(u[0]), int(u[1]), u[2]) for u in row] for row in d['units']]
    return dict(episode=eid, seat=seat, side='bench', steps=steps, boards=d['boards'],
                hire_orders=None, final=d.get('final'))


# ---------------------------------------------------------------- profiling

def hires_from_headcount(steps):
    """A hand hired at hour h appears in the roster at h+1, so the order was issued at h."""
    out = []
    for t, row in enumerate(steps):
        d, h = t // 24, t % 24
        prev = 0 if h == 0 else len(steps[t - 1]) - 1
        n = len(row) - 1
        for _ in range(max(0, n - prev)):
            out.append((d, max(0, h - 1)))
    return out


def profile(game):
    steps, boards = game['steps'], game['boards']
    days, unit_days, tomato_owner, harvest_log = [], [], [], []
    hour_profile = defaultdict(Counter)   # hour -> op counts over days 18-27
    for d in range(30):
        lo, hi = d * 24, min(719, d * 24 + 24)
        board = boards[min(d, len(boards) - 1)]
        tiles = Counter(c for row in board for c in row)
        ops, work_by_label, op_label = Counter(), Counter(), Counter()
        per_unit = defaultdict(lambda: dict(work=[], moves=0, ops=Counter(), labels=Counter(),
                                            quads=Counter(), shed_ops=0, shed_visits=0))
        maxunits = 0
        for t in range(lo, hi):
            row = steps[t]
            maxunits = max(maxunits, len(row))
            for i, (x, y, op) in enumerate(row):
                if op == 'NONE':
                    ops['NONE'] += 1
                    continue
                ops[op] += 1
                if 18 <= d <= 27:
                    hour_profile[t % 24]['MOVE' if op in MOVES else op] += 1
                u = per_unit[i]
                if op in MOVES:
                    u['moves'] += 1
                    continue
                if op == 'PASS':
                    continue
                lab = board[y][x]
                work_by_label[lab] += 1
                op_label[op + '|' + lab] += 1
                u['ops'][op] += 1
                u['labels'][lab] += 1
                u['quads'][quad(x, y)] += 1
                if op in SHED_OPS:
                    u['shed_ops'] += 1
                    if u['work'] and any(p not in SHED for p in u['work']):
                        u['shed_visits'] += 1
                u['work'].append((x, y))
                if op == 'HARVEST':
                    harvest_log.append((d, i, t % 24, lab))
        work = sum(v for k, v in ops.items() if k not in MOVES and k not in ('PASS', 'NONE'))
        moves = sum(ops[m] for m in MOVES)
        tom = Counter()
        for i, u in per_unit.items():
            if not u['work']:
                continue
            seq = u['work']
            travel = sum(abs(seq[j][0] - seq[j - 1][0]) + abs(seq[j][1] - seq[j - 1][1])
                         for j in range(1, len(seq)))
            top_lab, top_n = u['labels'].most_common(1)[0]
            field = [p for p in set(seq) if p not in SHED]
            span = max((abs(a[0] - b[0]) + abs(a[1] - b[1]) for a in field for b in field),
                       default=0)
            bbox = ((max(p[0] for p in field) - min(p[0] for p in field) + 1) *
                    (max(p[1] for p in field) - min(p[1] for p in field) + 1)) if field else 0
            crops = Counter({k: v for k, v in u['labels'].items() if k not in ('.', 'L', 'w')})
            unit_days.append(dict(day=d, unit=i, is_hand=i > 0, work=len(seq), moves=u['moves'],
                                  tiles=len(set(seq)), travel=travel, quads=len(u['quads']),
                                  top_label=top_lab, top_share=top_n / len(seq),
                                  span=span, bbox=bbox, field_tiles=len(field),
                                  first_shed=1.0 if tuple(seq[0]) in SHED else 0.0,
                                  crop_share=(crops.most_common(1)[0][1] / sum(crops.values()))
                                  if crops else None,
                                  shed_ops=u['shed_ops'], shed_visits=u['shed_visits'],
                                  labels=dict(u['labels']), ops=dict(u['ops'])))
            tom[i] = u['labels'].get('TO', 0)
        tt = sum(tom.values())
        tomato_owner.append(dict(day=d, tomato_work=tt,
                                 top_share=(max(tom.values()) / tt) if tt else None,
                                 units=len([1 for v in tom.values() if v])))
        days.append(dict(day=d, units=maxunits, hands=maxunits - 1,
                         commands=sum(ops.values()) - ops['NONE'], moves=moves, pass_=ops['PASS'],
                         work=work, ops=dict(ops), work_by_label=dict(work_by_label),
                         op_label=dict(op_label), tiles=dict(tiles)))
    return dict(days=days, unit_days=unit_days, tomato_owner=tomato_owner, harvest=harvest_log,
                hires=hires_from_headcount(steps), hire_orders=game.get('hire_orders'),
                hour_profile={h: dict(c) for h, c in hour_profile.items()})


# ---------------------------------------------------------------- aggregation

def route(rs):
    if not rs:
        return {}
    return dict(unit_days=len(rs), work_per_day=mean([r['work'] for r in rs]),
                tiles_per_day=mean([r['tiles'] for r in rs]),
                tiles_max=max(r['tiles'] for r in rs),
                ops_per_tile_visit=mean([r['work'] / r['tiles'] for r in rs]),
                starts_at_shed=mean([r['first_shed'] for r in rs]),
                travel_per_action=mean([r['travel'] / r['work'] for r in rs]),
                moves_per_action=mean([r['moves'] / r['work'] for r in rs]),
                quads_per_day=mean([r['quads'] for r in rs]),
                single_quad_share=mean([1.0 if r['quads'] == 1 else 0.0 for r in rs]),
                span=mean([r['span'] for r in rs]), bbox=mean([r['bbox'] for r in rs]),
                span_le3_share=mean([1.0 if r['span'] <= 3 else 0.0 for r in rs]),
                crop_share=mean([r['crop_share'] for r in rs]),
                top_label_share=mean([r['top_share'] for r in rs]),
                single_crop_share=mean([1.0 if r['top_share'] >= 0.999 else 0.0 for r in rs]),
                shed_ops_per_day=mean([r['shed_ops'] for r in rs]),
                midday_shed_returns=mean([r['shed_visits'] for r in rs]),
                share_with_shed_op=mean([1.0 if r['shed_ops'] else 0.0 for r in rs]),
                top_label_mix={k: round(v / len(rs), 3)
                               for k, v in Counter(r['top_label'] for r in rs).most_common()})


def agg_side(profiles):
    n = len(profiles)
    per_day = []
    for d in range(30):
        rows = [p['days'][d] for p in profiles]
        ops, wl = Counter(), Counter()
        for r in rows:
            ops.update(r['ops'])
            wl.update(r['work_by_label'])
        hires = [sum(1 for dd, _ in p['hires'] if dd == d) for p in profiles]
        hire_hours = [h for p in profiles for dd, h in p['hires'] if dd == d]
        per_day.append(dict(
            day=d, hands=mean([r['hands'] for r in rows]), hires=mean(hires),
            hire_hours=sorted(Counter(hire_hours).items()),
            commands=mean([r['commands'] for r in rows]), moves=mean([r['moves'] for r in rows]),
            idle=mean([r['pass_'] + r['ops'].get('NONE', 0) for r in rows]),
            work=mean([r['work'] for r in rows]),
            moves_per_work=mean([r['moves'] / r['work'] if r['work'] else None for r in rows]),
            ops={k: round(v / n, 2) for k, v in sorted(ops.items())},
            work_by_label={k: round(v / n, 2) for k, v in sorted(wl.items())}))
    totals, labels, oplab = Counter(), Counter(), Counter()
    for p in profiles:
        for r in p['days']:
            totals.update(r['ops'])
            labels.update(r['work_by_label'])
            oplab.update(r['op_label'])
    tot_work = sum(v for k, v in totals.items() if k not in MOVES and k not in ('PASS', 'NONE'))
    tot_moves = sum(totals[m] for m in MOVES)
    uds = [u for p in profiles for u in p['unit_days']]
    hands = [u for u in uds if u['is_hand']]
    farmers = [u for u in uds if not u['is_hand']]
    late_hands = [r for r in hands if r['day'] >= 15]
    town = [o for p in profiles for o in p['tomato_owner'] if o['top_share'] is not None]
    town_late = [o for o in town if o['day'] >= 15]
    hw, hw_units, hw_hours = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for p in profiles:
        for d, i, h, lab in p['harvest']:
            hw[lab][d] += 1
            if 18 <= d <= 27:
                hw_units[lab][i] += 1
                hw_hours[lab][h] += 1
    harvest = {}
    for lab in hw:
        harvest[lab] = dict(
            per_day=[round(hw[lab].get(d, 0) / n, 2) for d in range(30)],
            total_per_game=round(sum(hw[lab].values()) / n, 2),
            window_18_27=round(sum(hw[lab].get(d, 0) for d in range(18, 28)) / n, 2),
            window_units={str(k): round(v / n, 2) for k, v in sorted(hw_units[lab].items())},
            window_hours={str(k): round(v / n, 2) for k, v in sorted(hw_hours[lab].items())})
    cadence, hcad = {}, {}
    for lab in ('TO', 'ST', 'WH', 'CA', 'ME'):
        series, hser, tot_w, tot_t = [], [], 0, 0
        for d in range(30):
            w = sum(p['days'][d]['op_label'].get('WATER|' + lab, 0) for p in profiles)
            h = sum(p['days'][d]['op_label'].get('HARVEST|' + lab, 0) for p in profiles)
            t = sum(p['days'][d]['tiles'].get(lab, 0) for p in profiles)
            series.append(round(w / t, 3) if t else None)
            hser.append(round(h / t, 3) if t else None)
            if d >= 12:
                tot_w += w
                tot_t += t
        cadence[lab] = dict(per_day=series, mean_day12_29=round(tot_w / tot_t, 3) if tot_t else None)
        hcad[lab] = hser
    tiles_avg = {}
    for d in range(30):
        c = Counter()
        for p in profiles:
            c.update(p['days'][d]['tiles'])
        tiles_avg[str(d)] = {k: round(v / n, 2) for k, v in sorted(c.items())}
    # waters per harvest: a proxy for watering cadence per production cycle
    wph = {}
    for lab in ('WH', 'ST', 'TO', 'CA', 'ME'):
        w = sum(v for p in profiles for r in p['days'] for k, v in r['op_label'].items()
                if k == 'WATER|' + lab)
        h = sum(v for p in profiles for r in p['days'] for k, v in r['op_label'].items()
                if k == 'HARVEST|' + lab)
        wph[lab] = dict(water=round(w / n, 1), harvest=round(h / n, 1),
                        water_per_harvest=round(w / h, 2) if h else None)
    # role of each unit index (day >= 15): what crop does hand i mostly work?
    roles = {}
    for i in range(0, 13):
        rs = [r for r in uds if r['unit'] == i and r['day'] >= 15]
        if not rs:
            continue
        roles[str(i)] = dict(unit_days=len(rs), work=mean([r['work'] for r in rs]),
                             tiles=mean([r['tiles'] for r in rs]),
                             span=mean([r['span'] for r in rs]),
                             top_label_share=mean([r['top_share'] for r in rs]),
                             mix={k: round(v / len(rs), 2)
                                  for k, v in Counter(r['top_label'] for r in rs).most_common(4)})
    # the harvest window, days 18-27
    wops, wlab, whour = Counter(), Counter(), defaultdict(Counter)
    for p in profiles:
        for d in range(18, 28):
            r = p['days'][d]
            wops.update(r['ops'])
            wlab.update(r['work_by_label'])
    window = dict(days=10, ops={k: round(v / n, 1) for k, v in sorted(wops.items())},
                  work_by_label={k: round(v / n, 1)
                                 for k, v in sorted(wlab.items(), key=lambda kv: -kv[1])},
                  work_per_day=round(sum(v for k, v in wops.items()
                                         if k not in MOVES and k not in ('PASS', 'NONE')) / n / 10, 1),
                  idle_per_day=round((wops.get('PASS', 0) + wops.get('NONE', 0)) / n / 10, 1),
                  by_hour={str(h): {k: round(v / n / 10, 2) for k, v in
                                    sorted(Counter({k: sum(p['hour_profile'].get(h, {}).get(k, 0)
                                                           for p in profiles)
                                                    for k in ('MOVE', 'PASS', 'NONE', 'WATER',
                                                              'HARVEST', 'PLANT', 'FERTILIZE',
                                                              'FEED', 'CARE', 'COLLECT_FERTILIZER',
                                                              'PICKUP', 'DROP', 'PLACE', 'DIG')}).items())}
                           for h in range(24)})
    return dict(
        games=n, per_day=per_day,
        totals=dict(commands=round((sum(totals.values()) - totals.get('NONE', 0)) / n, 1),
                    moves=round(tot_moves / n, 1), work=round(tot_work / n, 1),
                    idle=round((totals.get('PASS', 0) + totals.get('NONE', 0)) / n, 1),
                    moves_per_work=round(tot_moves / tot_work, 3),
                    by_op={k: round(v / n, 1) for k, v in sorted(totals.items())},
                    work_by_label={k: round(v / n, 1)
                                   for k, v in sorted(labels.items(), key=lambda kv: -kv[1])},
                    op_by_label={k: round(v / n, 1)
                                 for k, v in sorted(oplab.items(), key=lambda kv: -kv[1])
                                 if v / n >= 1.0}),
        routing=dict(hands_all=route(hands), hands_day15plus=route(late_hands), farmer=route(farmers)),
        tomato_ownership=dict(all_days=mean([o['top_share'] for o in town]),
                              day15plus=mean([o['top_share'] for o in town_late]),
                              units_on_tomato_day15plus=mean([o['units'] for o in town_late])),
        harvest=harvest, water_per_tile=cadence, harvest_per_tile=hcad, tiles_per_day=tiles_avg,
        water_per_harvest=wph, unit_roles=roles, window_18_27=window,
        hiring=dict(per_game=mean([len(p['hires']) for p in profiles]),
                    by_day=[mean([sum(1 for dd, _ in p['hires'] if dd == d) for p in profiles])
                            for d in range(30)],
                    hour_hist={str(h): round(sum(1 for p in profiles for _, hh in p['hires'] if hh == h) / n, 2)
                               for h in range(24)}))


def trace(eid, day, side='mg'):
    """Print one day of one game: the day-start board and every unit's route."""
    games = {e: (p, s) for p, e, s in mg_games()}
    path, seat = games[eid]
    game = load_mg(path, eid, seat) if side == 'mg' else load_bench(eid, seat)
    board = game['boards'][day]
    print(f'--- {side} episode {eid} seat {seat} day {day}')
    print('    ' + ' '.join(f'{x:>2}' for x in range(10)))
    for y, row in enumerate(board):
        print(f'{y:>3} ' + ' '.join(f'{c:>2}' for c in row))
    routes = defaultdict(list)
    for t in range(day * 24, min(719, day * 24 + 24)):
        for i, (x, y, op) in enumerate(game['steps'][t]):
            if op in MOVES or op in ('PASS', 'NONE'):
                continue
            routes[i].append(f'{t % 24}:{op[:4]}@{x},{y}({board[y][x]})')
    for i in sorted(routes):
        print(f'  u{i:<2}', ' '.join(routes[i]))


def main():
    games = mg_games()
    bench_ids = {(int(f.stem.split('-')[0]), int(f.stem.split('-')[1]))
                 for f in BENCH_DIR.glob('*.json')}
    mg_all, mg_8, bench_8 = [], [], []
    for path, eid, seat in games:
        p = profile(load_mg(path, eid, seat))
        mg_all.append(p)
        if (eid, seat) in bench_ids:
            mg_8.append(p)
            bench_8.append(profile(load_bench(eid, seat)))
    out = dict(episodes=dict(mg_all=[e for _, e, _ in games],
                             paired=sorted(e for e, _ in bench_ids)),
               mg_all=agg_side(mg_all), mg=agg_side(mg_8), bench=agg_side(bench_8))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'routing.json').write_text(json.dumps(out), encoding='utf-8')
    print('wrote', OUT / 'routing.json')
    for name in ('mg_all', 'mg', 'bench'):
        s = out[name]
        print(name, s['games'], 'games | cmds', s['totals']['commands'], '| work', s['totals']['work'],
              '| moves', s['totals']['moves'], '| idle', s['totals']['idle'],
              '| mv/work', s['totals']['moves_per_work'])


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'trace':
        trace(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else 'mg')
    else:
        main()

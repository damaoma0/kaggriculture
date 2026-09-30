"""State-based continuation compiler, with delivery included in route packing.

The v3 helpers only parse jobs and implement schema checks. The compiler and
dispatcher below own all scheduling; no donor moves or worker IDs are used.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import random
import time

from fragments.segment_job_executor_v3 import (
    ANIMAL_PRICE, SEED_PRICE, _own, _get, _walk, _nearest_shed, _shed_access,
    _normalise_jobs, _failure, _check_job, _safety_jobs, _market_orders,
)

_DEADLINE = None


class PlanningBudgetExceeded(Exception):
    pass


def set_deadline(value):
    global _DEADLINE
    previous = _DEADLINE
    _DEADLINE = value
    return previous


def check_budget():
    if _DEADLINE is not None and time.perf_counter() >= _DEADLINE:
        raise PlanningBudgetExceeded('planning_budget')


def _distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _input(job):
    cmd = job['cmd']
    if cmd[0] == 'FEED': return 'WHEAT'
    if cmd[0] == 'FERTILIZE': return 'FERTILIZER'
    if cmd[0] == 'PLACE' and cmd[1] in ANIMAL_PRICE: return cmd[1]
    return None


def _chain(job_list):
    need = Counter()
    output = 0
    for job in job_list:
        p = _input(job)
        if p: need[p] += 1
        if job['cmd'][0] == 'HARVEST': output += sum(max(0, v) for v in job.get('effect', {}).values())
        if job['cmd'][0] == 'COLLECT_FERTILIZER': output += 1
    return {'jobs': job_list, 'pos': tuple(job_list[0]['tile']), 'need': need, 'output': output}


def _route_info(route, origin, inv, size, limit):
    if not route: return (0, 0, 0, {})
    need = Counter()
    for c in route: need.update(c['need'])
    missing = {p: max(0, n - inv.get(p, 0)) for p, n in need.items()}
    pos, length = origin, 0
    if any(missing.values()):
        shed = _nearest_shed(pos, size)
        length += _distance(pos, shed) + sum(v > 0 for v in missing.values())
        pos = shed
    for c in route:
        length += _distance(pos, c['pos']) + len(c['jobs'])
        pos = c['pos']
    cargo = sum(c['output'] for c in route) + sum(inv.values()) - sum(min(need[p], inv.get(p, 0)) for p in need)
    home_cost = _distance(pos, _nearest_shed(pos, size)) + 1
    returns = cargo > 0 and length + home_cost <= limit
    return length, (0 if returns else max(0, cargo)), (home_cost if returns else 0), missing


def _packing_score(infos, limit, midnight_limit):
    overload = sum(max(0, n[0] - limit) for n in infos)
    unbanked = sum(n[1] for n in infos)
    return (overload, max(0, unbanked - midnight_limit),
            sum(n[0] for n in infos), max((n[0] for n in infos), default=0))


def _pack(chains, positions, inventories, size, limit, midnight_limit, day):
    """Bounded insertion/relocation search; metrics avoid constructing commands."""
    rng = random.Random(7019 + day)
    best = None
    cache = {}
    evaluations = 0
    for i, c in enumerate(chains): c['index'] = i
    def route_info(route, u):
        nonlocal evaluations
        key = u, tuple(c['index'] for c in route)
        if key not in cache:
            evaluations += 1
            cache[key] = _route_info(route, positions[u], inventories[u], size, limit)
        return cache[key]
    for attempt in range(8):
        check_budget()
        ordering = list(chains)
        if attempt == 0:
            ordering.sort(key=lambda c: (-len(c['jobs']), -_distance(c['pos'], (4, 4))))
        elif attempt == 1:
            ordering.sort(key=lambda c: (-c['output'], -len(c['jobs'])))
        elif attempt == 2:
            ordering.sort(key=lambda c: (c['pos'][1], c['pos'][0]))
        else: rng.shuffle(ordering)
        routes = [[] for _ in positions]
        infos = [(0, 0, 0, {}) for _ in positions]
        for c in ordering:
            check_budget()
            choice = None
            for u in range(len(positions)):
                for at in range(len(routes[u]) + 1):
                    trial = routes[u][:at] + [c] + routes[u][at:]
                    info = route_info(trial, u)
                    # During construction penalize the incremental inability to
                    # return cargo, as well as travel and overtime.
                    key = (max(0, info[0] - limit),
                           info[0] - infos[u][0] + .08 * (info[1] - infos[u][1]), info[0], u, at)
                    if choice is None or key < choice[0]: choice = key, u, at, info
            _, u, at, info = choice
            routes[u].insert(at, c); infos[u] = info
        for _ in range(15):
            score = _packing_score(infos, limit, midnight_limit)
            if score[:2] == (0, 0): break
            if evaluations > 18000: break
            unbanked = sum(i[1] for i in infos)
            choice = None
            for src in range(len(positions)):
                check_budget()
                if infos[src][0] <= limit and not infos[src][1]: continue
                for ix, c in enumerate(routes[src]):
                    rem = routes[src][:ix] + routes[src][ix + 1:]
                    si = route_info(rem, src)
                    for dst in range(len(positions)):
                        if src == dst: continue
                        for at in range(len(routes[dst]) + 1):
                            ri = route_info(routes[dst][:at] + [c] + routes[dst][at:], dst)
                            trial_score = (
                                score[0] - max(0, infos[src][0] - limit) - max(0, infos[dst][0] - limit)
                                + max(0, si[0] - limit) + max(0, ri[0] - limit),
                                max(0, unbanked - infos[src][1] - infos[dst][1] + si[1] + ri[1] - midnight_limit),
                                score[2] - infos[src][0] - infos[dst][0] + si[0] + ri[0],
                                max(si[0], ri[0], max((infos[u][0] for u in range(len(infos)) if u not in (src, dst)), default=0)))
                            if trial_score < score and (choice is None or trial_score < choice[0]):
                                choice = trial_score, src, ix, dst, at, si, ri
            if choice is None: break
            _, src, ix, dst, at, si, ri = choice
            routes[dst].insert(at, routes[src].pop(ix)); infos[src], infos[dst] = si, ri
        score = _packing_score(infos, limit, midnight_limit)
        if best is None or score < best[0]: best = score, routes, infos
        if score[:2] == (0, 0): break
        if evaluations > 18000: break
    return best


def _build_day(obs, state, rel_day):
    farm, private, _ = _own(obs)
    hour, day = int(obs['hour']), int(obs['day'])
    pending = [j for j in state['jobs'] if j['day'] == rel_day and j['id'] not in state['issued']]
    if state['node'].get('safety_assets', True): pending += _safety_jobs(farm, rel_day, pending)
    groups = defaultdict(list)
    for j in pending:
        if j['cmd'][0] == 'PLACE' and j['cmd'][1] not in ANIMAL_PRICE: continue
        groups[tuple(j['tile'])].append(j)
    for pos, jobs in groups.items():
        jobs.sort(key=lambda j: (j['hour'], str(j['id']).zfill(9)))
        # A weed may have grown on a previously empty establishment tile.
        tile = farm['tiles'][pos[1]][pos[0]]
        if jobs[0]['cmd'][0] in ('PLANT', 'BUILD_COOP', 'BUILD_PASTURE') and isinstance(tile, dict) and tile.get('kind') == 'WEED':
            jobs.insert(0, {'id': 'weed_%d_%d_%d' % (rel_day, *pos), 'day': rel_day,
                           'hour': 0, 'tile': list(pos), 'cmd': ['DIG'], 'authorized_dig': True, 'generated': True})
        bad = _check_job(jobs[0], farm)
        if bad: return None, _failure(bad, tile=list(pos))
    seeds = Counter(j['cmd'][1] for j in pending if j['cmd'][0] == 'PLANT')
    needs = Counter(_input(j) for j in pending if _input(j))
    # Physical stock carried by the current workers is also available.
    available = deepcopy(private)
    for inv in private.get('inventories', []):
        for p, n in inv.items(): available['shed'][p] = available['shed'].get(p, 0) + n
    orders, bad = _market_orders(dict(farm, _segment_prices=obs.get('market', {}).get('prices', {})),
                                 available, seeds, needs, state['node'].get('cash_reserve', 0))
    if bad: return None, _failure(bad)
    positions = [tuple(farm['farmer'])] + list(map(tuple, farm.get('hands', [])))
    invs = list(private.get('inventories', [])) + [{} for _ in positions]
    capacity = 23 if day == 29 else 24
    start = hour + bool(orders)
    limit = capacity - start
    if limit < 0: return None, _failure('day_finished')
    chains = [_chain(jobs) for jobs in groups.values()]
    midnight_limit = 0 if day == 29 else 90
    packed = _pack(chains, positions, invs, len(farm['tiles']), limit, midnight_limit, day)
    score, routes, infos = packed
    if score[0]: return None, _failure('day_capacity_exceeded', overload=score[0], available=limit)
    if score[1]: return None, _failure('delivery_capacity_exceeded', excess=score[1])
    plan = [[['PASS'] for _ in range(capacity)] for _ in positions]
    scheduled = {}
    for u, route in enumerate(routes):
        pos = positions[u]; commands, ids = [], []
        def append(cmds, tags=None):
            commands.extend(cmds); ids.extend(tags if tags is not None else [None] * len(cmds))
        if any(infos[u][3].values()):
            shed = _nearest_shed(pos, len(farm['tiles'])); append(_walk(pos, shed)); pos = shed
            append([['PICKUP', p, n] for p, n in sorted(infos[u][3].items()) if n])
        for c in route:
            append(_walk(pos, c['pos'])); pos = c['pos']
            append([j['cmd'] for j in c['jobs']], [j['id'] for j in c['jobs']])
        if infos[u][2]: append(_walk(pos, _nearest_shed(pos, len(farm['tiles']))) + [['DROP']])
        for at, (cmd, jid) in enumerate(zip(commands, ids), start):
            plan[u][at] = cmd
            if jid is not None: scheduled[(u, at)] = jid
    return {'plan': plan, 'orders': orders, 'jobs': pending, 'scheduled': scheduled}, None


def _preflight(obs, state, rel_day):
    projected = deepcopy(obs)
    farm, private, _ = _own(projected)
    needed = max(0, state['node'].get('hire_to', 11) - len(farm.get('hands', [])) - 1)
    if needed:
        if obs['hour'] > 1: return None, _failure('hiring_window_missed')
        a, b = 1, 1
        costs = []
        for _ in range(farm.get('hires_today', 0) + needed): costs.append(a); a, b = b, a + b
        cost = sum(costs[-needed:])
        if farm['money'] < cost: return None, _failure('hire_budget_shortfall')
        farm['money'] -= cost
        for _ in range(needed):
            pos = [tuple(farm['farmer'])] + list(map(tuple, farm['hands']))
            cells = _shed_access(len(farm['tiles']))
            farm['hands'].append(list(min(cells, key=lambda p: (pos.count(p), cells.index(p)))))
            private['inventories'].append({})
        projected['hour'] += (needed + 9) // 10
    return _build_day(projected, state, rel_day)


def segment_executor_start(obs, node):
    try: jobs = _normalise_jobs(node)
    except (ValueError, KeyError, TypeError) as exc: return _failure(str(exc))
    state = {'ok': True, 'node': node, 'start_day': int(obs['day']), 'jobs': jobs,
             'issued': set(), 'plans': {}, 'failure': None,
             'telemetry': {'issued': [], 'purchases': [], 'rejected': []}}
    _, fail = _preflight(obs, state, 0)
    if fail: state['ok'] = False; state['failure'] = fail['failure']
    return state


def segment_executor_action(obs, state):
    farm, _, _ = _own(obs)
    empty = {'farmer': ['PASS'], 'hands': [['PASS'] for _ in farm.get('hands', [])]}
    if not state or not state.get('ok') or state.get('failure'): return empty
    rel, hour = int(obs['day']) - state['start_day'], int(obs['hour'])
    if rel not in (0, 1, 2): return empty
    if rel not in state['plans']:
        needed = max(0, state['node'].get('hire_to', 11) - len(farm.get('hands', [])) - 1)
        if needed:
            _, fail = _preflight(obs, state, rel)
            if fail: state['failure'] = fail['failure']; return empty
            empty['market'] = [['HIRE'] for _ in range(min(10, needed))]
            return empty
        built, fail = _build_day(obs, state, rel)
        if fail: state['failure'] = fail['failure']; return empty
        state['plans'][rel] = built
        state['telemetry']['purchases'] += built['orders']
    built = state['plans'][rel]
    commands = [row[hour] for row in built['plan']]
    for u, cmd in enumerate(commands):
        jid = built['scheduled'].get((u, hour))
        if jid is not None:
            state['issued'].add(jid)
            state['telemetry']['issued'].append({'day': rel, 'job': jid, 'cmd': cmd})
    action = {'farmer': commands[0], 'hands': commands[1:]}
    if not built.get('orders_emitted'):
        action['market'] = built['orders']; built['orders_emitted'] = True
    return action


def segment_executor_status(state):
    return {'ok': bool(state and state.get('ok') and not state.get('failure')),
            'failure': state.get('failure'), 'issued_jobs': len(state.get('issued', ())),
            'telemetry': state.get('telemetry', {})}

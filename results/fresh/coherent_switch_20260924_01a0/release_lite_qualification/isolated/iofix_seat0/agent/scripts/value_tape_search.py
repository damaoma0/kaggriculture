"""Public-state, whole-season rollout search over existing tape continuations.

This is a research planner, not a competition-time-budget implementation.
The selector accepts an observation and our own agent memory. It never accepts
the episode seed, future opponent actions, future shops, or a recorded suffix.
Alternative tapes are committed only until the next reveal. Native m1 resumes
after that in both the forecasts and the evaluation.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import gc
import json
from pathlib import Path
import random
import statistics
import time
import types

import research_labour_profit as R
from cumulative_engine_profiles import engine_profile
from test_labour_selfplay import project_input

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / 'agents/mgt_m1.py'
SOURCE = SOURCE_PATH.read_text(encoding='utf-8')
CODE = compile(SOURCE, str(SOURCE_PATH), 'exec')
SOURCE_SHA256 = sha256(SOURCE_PATH.read_bytes()).hexdigest()
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
SCENARIOS = ((18719, .7), (39461, 1.0), (67289, 1.3))
MEMORY_KEYS = ('_SHP_STATES', '_MGT_IGNORE', '_MGT_HISTORY', '_MGT_REPORT', '_SHP_REPORT')
_ENGINE = None


def canonical(value):
    if isinstance(value, dict):
        return {str(k): canonical(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, set):
        return sorted((canonical(v) for v in value),key=str)
    return value


def fresh_agent(memory=None, route=None, until=None):
    # Agent globals reference their own functions. Collect discarded clones
    # before decoding another large library, instead of accumulating cycles.
    gc.collect()
    ns = {'__name__': 'value_tape_clone', '__file__': str(SOURCE_PATH)}
    exec(CODE, ns)
    if memory is not None:
        ns['_MGT_IMPL'].chassis.players = deepcopy(memory['players'])
        for key in MEMORY_KEYS:
            value = ns[key]
            value.clear()
            if isinstance(value, list):
                value.extend(deepcopy(memory[key]))
            else:
                value.update(deepcopy(memory[key]))
    if route is not None:
        parent = ns['_MGT_IMPL'].chassis.router
        def committed(obs, step, state):
            if step < until:
                state['route'] = route
                return route
            return parent(obs, step, state)
        ns['_MGT_IMPL'].chassis.router = committed
    return ns['mgt_kaggle_entry']


def memory_of(entry):
    ns = entry.__globals__
    return {'players': deepcopy(ns['_MGT_IMPL'].chassis.players),
            **{key: deepcopy(ns[key]) for key in MEMORY_KEYS}}


def isolated_engine():
    """An independent instance of the installed official engine: no live hooks."""
    global _ENGINE
    if _ENGINE is None:
        path = Path(R.engine().__file__)
        code = path.read_text(encoding='utf-8').split('\njson_path =', 1)[0]
        _ENGINE = types.ModuleType('value_tape_official_engine')
        _ENGINE.__file__ = str(path)
        exec(compile(code, str(path), 'exec'), _ENGINE.__dict__)
    return _ENGINE


def asset_keys(farm):
    result = set()
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            if tile.get('animal'):
                result.add((x, y, tile['animal'], tile['placed_day']))
            elif tile.get('crop') in ('TOMATO', 'STRAWBERRY', 'MELON'):
                result.add((x, y, tile['crop'], tile['planted_day']))
    return result


def shortlist(obs, memory, count=7):
    entry = fresh_agent(memory)
    ns = entry.__globals__
    player, day = int(obs['player']), int(obs['day'])
    current = memory['players'][player]['route']
    # This is the normal m1 choice at this reveal, with the same overlay mask.
    entry(deepcopy(obs))
    native = ns['_MGT_IMPL'].chassis.players[player]['route']
    board = ns['_mgt_labels'](ns['_mgt_board'](obs['farms'][player]))
    ignored = memory['_MGT_IGNORE'].get(player) or ()
    shops = list(obs['town']['unlocked_shops'])
    vectors = [ns['_mgt_vec'](shops, j) for j in range(9)]
    rows = []
    for i, tape in enumerate(ns['_MGT_TAPES']):
        h = sum(a != b for j, (a, b) in enumerate(zip(board, tape['lab'][day])) if j not in ignored)
        d = ns['_mgt_distance'](vectors, shops, tape, len(shops))
        rows.append(dict(route=i, episode=tape['ep'], hamming=h, distance=d))
    by_id = {r['route']: r for r in rows}
    chosen = [None, current]
    if native != current:
        chosen.append(native)
    # Different physical tolerances give a small Pareto-oriented shortlist.
    for limit in (8, 14, 24):
        eligible = sorted((r for r in rows if r['hamming'] <= limit),
                          key=lambda r: (r['distance'], r['hamming'], r['route']))
        added = 0
        for r in eligible:
            if r['route'] not in chosen:
                chosen.append(r['route'])
                added += 1
            if added == 2:
                break
    chosen = chosen[:count]
    return [dict(route=None, episode=by_id[native]['episode'], hamming=by_id[native]['hamming'],
                 distance=by_id[native]['distance'], name='native_adaptive'),
            *[dict(by_id[i], name='commit_until_next_reveal') for i in chosen if i is not None]]


def rival_schedule(obs, scale):
    """Visible cohorts only, ideal care; short crops repeat on their own tiles.

    This is an explicit supply scenario, not access to rival private stocks or
    an assertion that the rival can execute all the work. Negative flows charge
    feed and fertilizer through the same market as our farm.
    """
    start = int(obs['day'])
    daily = {day: Counter() for day in range(start, 30)}
    for row in obs['farms'][1-int(obs['player'])]['tiles']:
        for tile in row:
            if not isinstance(tile, dict) or not (tile.get('crop') or tile.get('animal')):
                continue
            current, day = deepcopy(tile), start
            while day < 30:
                output, work, inputs, release = engine_profile(current, day, 30, fertilize=True)
                for p, days in output.items():
                    for d, n in days.items():
                        daily[d][p] += n
                for d, products in inputs.items():
                    for p, n in products.items():
                        daily[d][p] -= n
                if current.get('crop') not in ('WHEAT', 'CARROT') or release >= 30:
                    break
                day = release
                current = isolated_engine()._new_plant(tile['crop'], day, 24)
    # Balanced cumulative rounding avoids creating a unit every small flow.
    carry = Counter()
    result = {}
    for day, flows in daily.items():
        rounded = {}
        for p, n in flows.items():
            carry[p] += scale*n
            take = int(carry[p])
            carry[p] -= take
            if take:
                rounded[p] = take
        result[day] = rounded
    return result


def future_shops(obs, scenario_seed):
    shops = list(obs['town']['unlocked_shops'])
    # A fixed local RNG; the real episode seed is never provided to this module.
    rng = random.Random(scenario_seed + 1009*int(obs['day']))
    types_ = sorted(isolated_engine().SHOPS)
    sequence = {}
    for day in range(int(obs['day']), 30):
        if day > obs['day'] and day in range(3, 25, 3) and len(shops) < 8:
            shops.append(rng.choice(types_))
        sequence[day] = list(shops)
    return sequence


def rollout(obs, memory, route, scenario, until=None):
    E = isolated_engine()
    start, seat = int(obs['step']), int(obs['player'])
    day = start//24
    until = min(719, (day+3)*24) if until is None else until
    seed, scale = scenario
    flows, shops = rival_schedule(obs, scale), future_shops(obs, seed)
    entry = fresh_agent(memory, route, until)
    public, state = project_input(obs)
    env = public.env
    initial_money = [f['money'] for f in state[0].observation.farms]
    # Synthetic rival goods are scenario inputs. Supply costs enter the ledger;
    # its cash constraint would otherwise confuse supply error with tape value.
    state[0].observation.farms[1-seat]['money'] = 10_000_000
    rival_start = 10_000_000
    original_rival_tiles = deepcopy(obs['farms'][1-seat]['tiles'])
    surviving, output, feeds, failures = None, Counter(), Counter(), Counter()
    starting_animals = {(x,y,tile['animal'],tile['placed_day'])
        for y,row in enumerate(obs['farms'][seat]['tiles']) for x,tile in enumerate(row)
        if isinstance(tile,dict) and tile.get('animal')}
    events = []
    old_commit, old_unit, old_hire = E._commit_unit, E._apply_unit_action, E._do_hire
    t = start
    def commit(op, p, price, farm, private, market, cap=100):
        ok = old_commit(op, p, price, farm, private, market, cap)
        if ok:
            events.append((t, 0 if farm is state[0].observation.farms[seat] else 1, op, p, price))
        elif farm is state[0].observation.farms[seat] and op != 'SELL':
            failures[op] += 1
        return ok
    def unit(farm, private, u, cmd, *args, **kwargs):
        ours = farm is state[0].observation.farms[seat]
        pos = E._farmer_position(farm, u)
        before = dict(private['inventories'][u]) if ours and pos is not None else None
        tile = farm['tiles'][pos[1]][pos[0]] if ours and pos is not None else None
        retained_animal = (isinstance(tile,dict) and tile.get('animal') and
                          (*pos,tile['animal'],tile['placed_day']) in starting_animals)
        result = old_unit(farm, private, u, cmd, *args, **kwargs)
        if before is not None and cmd:
            after = private['inventories'][u]
            if cmd[0] in ('HARVEST', 'COLLECT_FERTILIZER'):
                output.update({p: n-before.get(p, 0) for p,n in after.items() if n>before.get(p,0)})
            if cmd[0] == 'FEED' and retained_animal and before.get('WHEAT',0)>after.get('WHEAT',0) and t<until:
                feeds[(t//24, *pos)] += 1
        return result
    def hire(farm, private, size, *args, **kwargs):
        old = len(farm['hands'])
        result = old_hire(farm, private, size, *args, **kwargs)
        if farm is state[0].observation.farms[seat] and old == len(farm['hands']):
            failures['HIRE'] += 1
        return result
    E._commit_unit, E._apply_unit_action, E._do_hire = commit, unit, hire
    try:
        for t in range(start, 719):
            d, h = divmod(t, 24)
            for s in state:
                s.observation.step = t
            if h == 0:
                state[0].observation.town['unlocked_shops'][:] = shops[d]
                state[0].observation.farms[1-seat]['tiles'] = deepcopy(original_rival_tiles)
            state[seat].action = entry(deepcopy(state[seat].observation))
            rival = state[1-seat].observation.private
            rival['shed'] = {p: n for p,n in flows.get(d,{}).items() if n>0} if h == 1 else {}
            orders = [['SELL' if n>0 else 'BUY_PRODUCT', p, abs(n)]
                      for p,n in flows.get(d,{}).items()] if h == 1 else []
            state[1-seat].action = {'farmer':['PASS'], 'hands':[], 'market':orders}
            E.interpreter(state, env)
            if t+1 == until:
                surviving = asset_keys(state[0].observation.farms[seat])
    finally:
        E._commit_unit, E._apply_unit_action, E._do_hire = old_commit, old_unit, old_hire
    own = state[0].observation.farms[seat]['money'] - initial_money[seat]
    rival = state[0].observation.farms[1-seat]['money'] - rival_start
    return dict(cash_gain=own, rival_gain=rival, margin_gain=own-rival,
                output=dict(output), failures=dict(failures),
                survives=sorted(surviving or ()), feeds={str(k):v for k,v in feeds.items()},
                revenue=dict(sum((Counter({p:price}) for _,s,op,p,price in events if s==0 and op=='SELL'),Counter())))


def choose(obs, memory, *, count=7, scenarios=SCENARIOS):
    started = time.perf_counter()
    candidates = shortlist(obs, memory, count)
    existing = asset_keys(obs['farms'][int(obs['player'])])
    rows = []
    base = None
    for candidate in candidates:
        predictions = [rollout(obs, memory, candidate['route'], scenario) for scenario in scenarios]
        row = dict(candidate, predictions=predictions)
        if base is None:
            base = predictions
        deltas = [p['margin_gain']-b['margin_gain'] for p,b in zip(predictions,base)]
        cash = [p['cash_gain']-b['cash_gain'] for p,b in zip(predictions,base)]
        losses = []
        for p,b in zip(predictions,base):
            protected = existing & set(map(tuple,b['survives']))
            missing = protected - set(map(tuple,p['survives']))
            if missing:
                losses.append({'assets': sorted(missing)})
            extra_failures = Counter(p['failures']) - Counter(b['failures'])
            if extra_failures.get('HIRE',0):
                losses.append({'extra_failed_hires':extra_failures['HIRE']})
            less_feed = Counter(b['feeds']) - Counter(p['feeds'])
            if less_feed:
                losses.append({'lost_feed_actions':sum(less_feed.values())})
        mean = statistics.mean(deltas)
        score = mean - .5*statistics.pstdev(deltas)
        row.update(margin_deltas=deltas, cash_deltas=cash, mean_margin=mean,
                   risk_score=score, minimum_margin=min(deltas), protection_failures=losses,
                   admitted=not losses and min(deltas)>=-500 and statistics.mean(cash)>0 and score>350)
        rows.append(row)
    allowed = [r for r in rows if r['admitted']]
    chosen = max(allowed, key=lambda r:r['risk_score']) if allowed else rows[0]
    return chosen['route'], dict(day=int(obs['day']), selected=chosen['route'],
        selected_episode=chosen['episode'], candidates=rows,
        seconds=time.perf_counter()-started,
        input_sha256=sha256(json.dumps(canonical([obs,memory]),sort_keys=True,default=str).encode()).hexdigest(),
        until=min(719,(int(obs['day'])+3)*24), source_sha256=SOURCE_SHA256,
        planner_sha256=PLANNER_SHA256,
        official_engine_sha256=sha256(Path(R.engine().__file__).read_bytes()).hexdigest(),
        protocol='Public observation and native agent memory only; three sampled future-shop/supply scenarios; full-season native continuation; next-reveal commitment.')

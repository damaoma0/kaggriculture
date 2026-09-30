"""Build the leader-imitation router on the frozen benchmark's execution chassis.

WHAT THIS IMITATES, AND WHAT IT INHERITS
The segment study (docs/leader_segments.md) found our V45 tape already matches the leaders on the
parts of their policy that are about *timing*: fixed opening through day 5, second quadrant on days
6-8 and third on days 9-11, melon cash-out days 9-11, liquidation in days 27-29 at ~17.5% of season
revenue, and the same 11-hires/day ceiling except for surplus late hires. Those are inherited from
the chassis rather than re-implemented, because round 1 of the self-play gate showed that pulling
individual behaviours out of the chassis (the hire ceiling, the fertilizer flow) costs money: the
chassis is co-adapted.

What the leaders actually do differently is the one thing this controller implements: crop
QUANTITIES conditioned on revealed shop demand, plus their crop calendar (strawberry replanting
through day 16, carrot ramp from day 18 rather than day 24) and their refusal to buy the fourth
quadrant.

TARGETS USE ENGINE CONSTANTS, NOT FITTED THRESHOLDS
  * a shop instance consumes one unit of each product it demands per 4 turns = 6/day; single-product
    shops (Yarn, Pet Cafe) consume double;
  * the town centre consumes one of every product per day;
  * shops unlock on days 3,6,...,24, so undrawn shops contribute their expected rate (the mean over
    the eight equally likely types), discounted by _LL_FUTURE_WEIGHT because the leaders condition on
    *revealed* demand (their plantings correlate +0.93/+0.94 with demand visible at day 12);
  * a plant's output is its scheduled productions that still fit before the last selling day, and
    short-cycle crops are replanted by the chassis, so their tile runs several cycles;
  * the opponent is assumed to mirror our supply, so we can clear about half of total absorption.

WHAT IT CANNOT IMITATE
Majkel1337's policy is nondeterministic (15 of 210 same-seat game pairs diverge with identical full
observation histories), so its conditioning rule is not identifiable from replays and nothing here
tries to reproduce it. Mother-Goose is deterministic and is the imitation target. Neither leader
conditions production on the opponent, so no opponent term exists here.
"""
from hashlib import sha256
import json
from market_corpus import ROOT

BASE = ROOT / 'agents/benchmark_frozen_56280048.py'
BASE_SHA = '07c313e53d390ab6e1dd563fa2059dd1ea78988af4e0df3f8bbe1c6d8085ea4f'

HEADER = '''

# --------------------------------------------------------------------------- leader imitation: {name}
# Built on agents/benchmark_frozen_56280048.py (SHA-256 {sha}) by scripts/build_leaderlike.py.
# {description}
_LL_NAME = {name!r}
_LL_STATS = {{}}
_LL_PARENT = [v for v in globals().values() if callable(v)][-1]

_LL_SHOP_RATES = {{
    'BAKERY': {{'EGG': 6.0, 'WHEAT': 6.0}},
    'PIZZA_SHOP': {{'MILK': 6.0, 'TOMATO': 6.0, 'WHEAT': 6.0}},
    'BRUNCH_SPOT': {{'EGG': 6.0, 'WHEAT': 6.0, 'STRAWBERRY': 6.0}},
    'YARN_STORE': {{'WOOL': 12.0}},
    'ICE_CREAM_SHOP': {{'STRAWBERRY': 6.0, 'MILK': 6.0, 'WHEAT': 6.0}},
    'PET_CAFE': {{'CARROT': 12.0}},
    'SMOOTHIE_SHOP': {{'STRAWBERRY': 6.0, 'MILK': 6.0}},
    'FARMERS_MARKET': {{'WHEAT': 6.0, 'CARROT': 6.0, 'TOMATO': 6.0, 'STRAWBERRY': 6.0}},
}}
_LL_DRAW_DAYS = (3, 6, 9, 12, 15, 18, 21, 24)
_LL_SEASON_END = 29
_LL_TOWN_RATE = 1.0
_LL_SHARE = 0.5
_LL_FUTURE_WEIGHT = 0.5
# scheduled production ages and units per production, from the engine crop table
_LL_PRODUCTIONS = {{'STRAWBERRY': (10, 12, 14, 16), 'TOMATO': (8, 9, 10, 11), 'CARROT': (3,), 'WHEAT': (4,)}}
_LL_UNITS = {{'STRAWBERRY': 1.0, 'TOMATO': 1.0, 'CARROT': 3.0, 'WHEAT': 4.0}}
_LL_CYCLE = {{'CARROT': 4, 'WHEAT': 5}}  # one-time crops are replanted by the chassis
_LL_STRAW_BOUNDS = ({straw_min}, {straw_max})
_LL_CARROT_BOUNDS = (0, {carrot_max})
_LL_STRAW_SWAP_DAYS = {straw_swap_days}
_LL_CARROT_SWAP_DAYS = {carrot_swap_days}
_LL_MAX_STRAW_SWAPS = {max_straw_swaps}
_LL_MAX_CARROT_SWAPS = {max_carrot_swaps}
_LL_SWAPS_PER_TURN = 2
_LL_SEED_BUFFER = 2
_LL_MODE = '{mode}'
_LL_STRAW_PLANT_FLOOR = {straw_floor}
_LL_DO_STRAW_CAP = {do_straw_cap}
_LL_DO_SWAPS = {do_swaps}
_LL_DO_NO_QUAD4 = {do_no_quad4}


def _ll_count(key, n=1):
    _LL_STATS[key] = _LL_STATS.get(key, 0) + n


def _ll_farm(observation):
    return observation['farms'][int(observation['player'])]


def _ll_day(observation):
    return int(observation['step']) // 24


def _ll_units_per_plant(crop, day):
    """Units one new plant of `crop` can still deliver if planted today."""
    units = 0.0
    cycle = _LL_CYCLE.get(crop)
    if cycle:
        start = day
        while start + max(_LL_PRODUCTIONS[crop]) <= _LL_SEASON_END:
            units += _LL_UNITS[crop]
            start += cycle
        return units
    for age in _LL_PRODUCTIONS[crop]:
        if day + age <= _LL_SEASON_END:
            units += _LL_UNITS[crop]
    return units


def _ll_expected_rate(crop):
    total = sum(rates.get(crop, 0.0) for rates in _LL_SHOP_RATES.values())
    return total / float(len(_LL_SHOP_RATES))


def _ll_absorption(observation, crop, day):
    """Units of `crop` the town can consume from the moment a plant sown today starts producing."""
    start = day + _LL_PRODUCTIONS[crop][0]
    if start >= _LL_SEASON_END:
        return 0.0
    shops = list((observation.get('town') or {{}}).get('unlocked_shops') or [])
    total = _LL_TOWN_RATE * (_LL_SEASON_END - start)
    for index, name in enumerate(shops):
        reveal = _LL_DRAW_DAYS[index] if index < len(_LL_DRAW_DAYS) else _LL_DRAW_DAYS[-1]
        rate = _LL_SHOP_RATES.get(name, {{}}).get(crop, 0.0)
        if rate:
            total += rate * max(0, _LL_SEASON_END - max(reveal, start))
    expected = _ll_expected_rate(crop)
    for index in range(len(shops), len(_LL_DRAW_DAYS)):
        reveal = _LL_DRAW_DAYS[index]
        total += _LL_FUTURE_WEIGHT * expected * max(0, _LL_SEASON_END - max(reveal, start))
    return total


def _ll_target(observation, crop, day, bounds):
    per_plant = _ll_units_per_plant(crop, day)
    if per_plant <= 0:
        return bounds[0]
    target = int(round(_LL_SHARE * _ll_absorption(observation, crop, day) / per_plant))
    return max(bounds[0], min(bounds[1], target))


def _ll_alive(farm, crop):
    return sum(1 for row in farm['tiles'] for tile in row
               if isinstance(tile, dict) and tile.get('crop') == crop)


def _ll_units(action):
    return [action.get('farmer')] + list(action.get('hands') or [])


def _ll_apply_units(action, units):
    return dict(action, farmer=units[0], hands=units[1:])


def _ll_is_plant(unit, crop=None):
    return (isinstance(unit, (list, tuple)) and len(unit) > 1 and unit[0] == 'PLANT'
            and (crop is None or unit[1] == crop))


def _ll_projected_supply(observation, crop, day):
    """Units of `crop` we are already committed to selling: stock on hand, yield standing on the
    tiles, and every scheduled production still to come from plants already in the ground."""
    total = 0.0
    private = observation.get('private') or {{}}
    total += float((private.get('shed') or {{}}).get(crop, 0) or 0)
    for inventory in private.get('inventories') or []:
        total += float((inventory or {{}}).get(crop, 0) or 0)
    for row in _ll_farm(observation)['tiles']:
        for tile in row:
            if not (isinstance(tile, dict) and tile.get('crop') == crop):
                continue
            total += float(tile.get('yield_units') or 0)
            planted = int(tile.get('planted_day', day) or day)
            for age in _LL_PRODUCTIONS[crop]:
                if day < planted + age <= _LL_SEASON_END:
                    total += _LL_UNITS[crop]
    return total


def _ll_new_plant_units(crop, day):
    """Units one plant sown today delivers before the season ends, counting one cycle only."""
    total = 0.0
    for age in _LL_PRODUCTIONS[crop]:
        if day + age <= _LL_SEASON_END:
            total += _LL_UNITS[crop]
    return total


def _ll_room_for(observation, crop, day):
    """Marginal test: can the town still absorb the output of one more plant sown today?"""
    share = _LL_SHARE * _ll_absorption(observation, crop, day)
    supply = _ll_projected_supply(observation, crop, day)
    return share - supply >= _ll_new_plant_units(crop, day)
'''

BODY = '''

def _ll_controller(observation, action):
    day = _ll_day(observation)
    farm = _ll_farm(observation)
    seeds = (observation.get('private') or {}).get('seeds') or {}
    straw_target = _ll_target(observation, 'STRAWBERRY', day, _LL_STRAW_BOUNDS)
    straw_alive = _ll_alive(farm, 'STRAWBERRY')
    _LL_STATS['straw_target_last'] = straw_target
    _LL_STATS['straw_alive_last'] = straw_alive
    units = _ll_units(action)
    changed = False

    # 1. Demand-conditioned strawberry quantity: never hold more plants than the town can absorb.
    if _LL_MODE == 'units':
        blocked = (not _ll_room_for(observation, 'STRAWBERRY', day)) and straw_alive >= _LL_STRAW_PLANT_FLOOR
    else:
        blocked = straw_alive >= straw_target
    if _LL_DO_STRAW_CAP and blocked:
        for index, unit in enumerate(units):
            if _ll_is_plant(unit, 'STRAWBERRY'):
                units[index] = ['PASS']
                _ll_count('straw_plants_suppressed')
                changed = True

    # 2. The leaders' calendar: strawberry top-ups through day 16 and the carrot ramp from day 18,
    #    taken at planting visits the chassis already routes a worker to, so no new labour is needed.
    swaps = 0
    if _LL_DO_SWAPS:
        plans = []
        straw_room = (_ll_room_for(observation, 'STRAWBERRY', day) if _LL_MODE == 'units'
                      else straw_alive < straw_target)
        if (_LL_STRAW_SWAP_DAYS[0] <= day <= _LL_STRAW_SWAP_DAYS[1] and straw_room
                and _LL_STATS.get('straw_swaps', 0) < _LL_MAX_STRAW_SWAPS):
            plans.append(('STRAWBERRY', max(1, straw_target - straw_alive)))
        if _LL_CARROT_SWAP_DAYS[0] <= day <= _LL_CARROT_SWAP_DAYS[1]:
            carrot_target = _ll_target(observation, 'CARROT', day, _LL_CARROT_BOUNDS)
            carrot_alive = _ll_alive(farm, 'CARROT')
            _LL_STATS['carrot_target_last'] = carrot_target
            carrot_room = (_ll_room_for(observation, 'CARROT', day) if _LL_MODE == 'units'
                           else carrot_alive < carrot_target)
            if carrot_room and _LL_STATS.get('carrot_swaps', 0) < _LL_MAX_CARROT_SWAPS:
                    plans.append(('CARROT', max(1, carrot_target - carrot_alive)))
        for crop, room in plans:
            if room <= 0:
                continue
            available = int(seeds.get(crop, 0) or 0)
            for index, unit in enumerate(units):
                if swaps >= _LL_SWAPS_PER_TURN or room <= 0 or available <= 0:
                    break
                if _ll_is_plant(unit, 'WHEAT'):
                    units[index] = ['PLANT', crop]
                    available -= 1
                    room -= 1
                    swaps += 1
                    changed = True
                    _ll_count(crop.lower() + '_swaps')
    if changed:
        action = _ll_apply_units(action, units)

    # 3. Seed buffer for the swaps, and the leaders' refusal of the fourth quadrant.
    orders = list(action.get('market') or [])
    kept, touched = [], False
    for order in orders:
        if (_LL_DO_NO_QUAD4 and isinstance(order, (list, tuple)) and order and order[0] == 'BUY_LAND'
                and len(farm.get('unlocked_quadrants') or []) >= 3):
            _ll_count('land_orders_dropped')
            touched = True
            continue
        kept.append(order)
    if _LL_DO_SWAPS and len(kept) <= 8:
        for crop, window, cap, used in (
                ('STRAWBERRY', _LL_STRAW_SWAP_DAYS, _LL_MAX_STRAW_SWAPS, _LL_STATS.get('straw_swaps', 0)),
                ('CARROT', _LL_CARROT_SWAP_DAYS, _LL_MAX_CARROT_SWAPS, _LL_STATS.get('carrot_swaps', 0))):
            if not (window[0] - 1 <= day <= window[1] and used < cap):
                continue
            bounds = _LL_STRAW_BOUNDS if crop == 'STRAWBERRY' else _LL_CARROT_BOUNDS
            if _LL_MODE == 'units':
                if not _ll_room_for(observation, crop, day):
                    continue
            elif _ll_alive(farm, crop) >= _ll_target(observation, crop, day, bounds):
                continue
            if int(seeds.get(crop, 0) or 0) >= _LL_SEED_BUFFER:
                continue
            kept.append(['BUY_SEED', crop, _LL_SEED_BUFFER])
            _ll_count(crop.lower() + '_seed_orders_added')
            touched = True
            break
    if touched:
        action = dict(action, market=kept)

    # 4. Surplus strawberry seed purchases once the target is met.
    surplus_seeds = (not _ll_room_for(observation, 'STRAWBERRY', day) if _LL_MODE == 'units'
                     else straw_alive + int(seeds.get('STRAWBERRY', 0) or 0) >= straw_target)
    if _LL_DO_STRAW_CAP and surplus_seeds:
        orders = list(action.get('market') or [])
        kept = []
        for order in orders:
            if (isinstance(order, (list, tuple)) and order and order[0] == 'BUY_SEED'
                    and len(order) > 1 and order[1] == 'STRAWBERRY'):
                _ll_count('straw_seed_orders_suppressed')
                continue
            kept.append(order)
        if len(kept) != len(orders):
            action = dict(action, market=kept)
    return action


def agent(observation, configuration=None):
    action = _LL_PARENT(observation, configuration)
    try:
        return _ll_controller(observation, action)
    except Exception:
        _ll_count('controller_errors')
        return action


agent.sp_telemetry = _LL_STATS
agent = globals().pop('agent')
'''

QUAD_GATES = '''

_LL_V219_PARENT = _v219_qualifies
_LL_V233_PARENT = _v233_eligible


def _v219_qualifies(obs, native):
    return False


def _v233_eligible(obs, native):
    return False
'''

VARIANTS = {
    'leaderlike_v2': dict(description='Imitation v2: marginal-unit test for every crop decision '
                                      '(stock on hand plus scheduled productions versus absorption), '
                                      'leader crop calendar, no fourth quadrant.',
                          mode='units', do_straw_cap='True', do_swaps='True', do_no_quad4='True'),
    'leaderlike_v2cap': dict(description='Imitation v2 ablation: marginal-unit strawberry cap only.',
                             mode='units', do_straw_cap='True', do_swaps='False', do_no_quad4='False'),
    'leaderlike_v2swaps': dict(description='Imitation v2 ablation: leader crop calendar only.',
                               mode='units', do_straw_cap='False', do_swaps='True', do_no_quad4='False'),
    'leaderlike_v1': dict(description='Full imitation: demand-conditioned strawberry cap, strawberry '
                                      'top-ups to day 16, carrot ramp from day 18, no fourth quadrant.',
                          do_straw_cap='True', do_swaps='True', do_no_quad4='True'),
    'leaderlike_cap': dict(description='Ablation: demand-conditioned strawberry cap only.',
                           do_straw_cap='True', do_swaps='False', do_no_quad4='False'),
    'leaderlike_swaps': dict(description='Ablation: leader crop calendar only (strawberry top-ups, '
                                         'carrot ramp from day 18).',
                             do_straw_cap='False', do_swaps='True', do_no_quad4='False'),
}
DEFAULTS = dict(mode='count', straw_floor=12, straw_min=8, straw_max=40, carrot_max=45, straw_swap_days=(12, 16),
                carrot_swap_days=(18, 26), max_straw_swaps=10, max_carrot_swaps=24)


def main():
    base_text = BASE.read_text(encoding='utf-8')
    assert sha256(BASE.read_bytes()).hexdigest() == BASE_SHA, 'frozen benchmark changed'
    from kaggle_environments.agent import get_last_callable
    manifest = {'benchmark': str(BASE.relative_to(ROOT)), 'benchmark_sha256': BASE_SHA, 'variants': {}}
    for name, spec in VARIANTS.items():
        fields = dict(DEFAULTS)
        fields.update(spec)
        text = base_text + HEADER.format(name=name, sha=BASE_SHA, **fields)
        if spec['do_no_quad4'] == 'True':
            text += QUAD_GATES
        text += BODY
        path = ROOT / 'agents' / f'{name}.py'
        path.write_text(text, encoding='utf-8')
        fn = get_last_callable(path.read_text(encoding='utf-8'), path=str(path))
        line = getattr(getattr(fn, '__code__', None), 'co_firstlineno', None)
        assert line and line > len(base_text.splitlines()), (name, 'layer is not the entry point', line)
        manifest['variants'][name] = dict(path=str(path.relative_to(ROOT)), entry_line=line,
                                          sha256=sha256(path.read_bytes()).hexdigest(),
                                          description=spec['description'], config=fields)
        print(f'built {name}: entry line {line}, sha {manifest["variants"][name]["sha256"][:12]}')
    out = ROOT / 'results/fresh/selfplay/leaderlike.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()

"""Build self-play candidates by appending one layer to the FROZEN current agent.

The benchmark is agents/benchmark_frozen_56280048.py, a byte copy of the uploaded submission
56280048 (SHA-256 07c313e5...85ea4f). Every candidate is that exact file plus one appended layer,
so the only behavioural difference is the layer under test.

Kaggle's loader calls the LAST callable in module globals, which in the benchmark is the line-3599
price-impact wrapper (its forecast layer is inert). Each layer therefore captures
`[v for v in globals().values() if callable(v)][-1]` as its parent and re-exports `agent` last, so
candidate == deployed benchmark + layer.
"""
from hashlib import sha256
import json
from market_corpus import ROOT

BASE = ROOT / 'agents/benchmark_frozen_56280048.py'
BASE_SHA = '07c313e53d390ab6e1dd563fa2059dd1ea78988af4e0df3f8bbe1c6d8085ea4f'

HEADER = '''

# --------------------------------------------------------------------------- self-play candidate: {name}
# Appended to the frozen benchmark (agents/benchmark_frozen_56280048.py, SHA-256 {sha}).
# {description}
_SP_NAME = {name!r}
_SP_STATS = {{}}
_SP_PARENT = [v for v in globals().values() if callable(v)][-1]


def _sp_count(key, n=1):
    _SP_STATS[key] = _SP_STATS.get(key, 0) + n


def _sp_orders(action):
    orders = action.get('market') or []
    return [o for o in orders if isinstance(o, (list, tuple)) and o and isinstance(o[0], str)], orders


def _sp_own_farm(observation):
    return observation['farms'][int(observation['player'])]
'''

FOOTER = '''

agent.sp_telemetry = _SP_STATS
agent = globals().pop('agent')
'''

# --------------------------------------------------------------------------- layers
HIRE_CAP = '''
# Both leaders spend exactly 696 per 3-day segment on labour once ramped, i.e. 11 hires/day
# (fib 1+1+2+3+5+8+13+21+34+55+89 = 232/day). The 12th and 13th hand cost 144 and 233 for one
# worker-day each. Dropping the surplus HIRE orders is index-safe: hands are appended in hire
# order, so only the highest hand indices lose their scripted jobs.
_SP_HIRE_CAP = __CAP__


def agent(observation, configuration=None):
    action = _SP_PARENT(observation, configuration)
    orders, raw = _sp_orders(action)
    if not raw:
        return action
    used = int(_sp_own_farm(observation).get('hires_today') or 0)
    kept, dropped = [], 0
    for order in raw:
        if isinstance(order, (list, tuple)) and order and order[0] == 'HIRE':
            if used >= _SP_HIRE_CAP:
                dropped += 1
                continue
            used += 1
        kept.append(order)
    if dropped:
        _sp_count('hires_dropped', dropped)
        action = dict(action, market=kept)
    return action
'''

NO_QUAD4 = '''
# Neither current leader buys the fourth quadrant in 60/60 audited games; we buy it in ~25% of
# games through V45's two conditional programs. Disable both gates (they are called by global
# name) and drop any BUY_LAND once three quadrants are owned.
_SP_V219_PARENT = _v219_qualifies
_SP_V233_PARENT = _v233_eligible


def _v219_qualifies(obs, native):
    _sp_count('v219_gate_suppressed')
    return False


def _v233_eligible(obs, native):
    _sp_count('v233_gate_suppressed')
    return False


def agent(observation, configuration=None):
    action = _SP_PARENT(observation, configuration)
    orders, raw = _sp_orders(action)
    if not raw or len(_sp_own_farm(observation).get('unlocked_quadrants') or []) < 3:
        return action
    kept = [o for o in raw if not (isinstance(o, (list, tuple)) and o and o[0] == 'BUY_LAND')]
    if len(kept) != len(raw):
        _sp_count('land_orders_dropped', len(raw) - len(kept))
        action = dict(action, market=kept)
    return action
'''

FERT_RETAIN = '''
# Majkel1337 spends 0 on fertilizer and applies 160 units; we spend 2,571 buying it back after
# selling 340. Stop the round trip: never buy fertilizer as a product, and hold a floor of own
# stock back from sale so the existing input tours can draw on it.
_SP_FERT_FLOOR = 12


def _sp_fert_stock(observation):
    private = observation.get('private') or {}
    total = int((private.get('shed') or {}).get('FERTILIZER', 0) or 0)
    for inv in private.get('inventories') or []:
        total += int((inv or {}).get('FERTILIZER', 0) or 0)
    return total


def agent(observation, configuration=None):
    action = _SP_PARENT(observation, configuration)
    orders, raw = _sp_orders(action)
    if not raw:
        return action
    stock = _sp_fert_stock(observation)
    kept, changed = [], False
    for order in raw:
        if isinstance(order, (list, tuple)) and order and order[0] == 'BUY_PRODUCT' and len(order) > 1 \\
                and order[1] == 'FERTILIZER':
            _sp_count('fertilizer_buys_dropped')
            changed = True
            continue
        if isinstance(order, (list, tuple)) and order and order[0] == 'SELL' and len(order) > 1 \\
                and order[1] == 'FERTILIZER':
            want = int(order[2]) if len(order) > 2 else 1
            allowed = max(0, stock - _SP_FERT_FLOOR)
            if allowed <= 0:
                _sp_count('fertilizer_sales_withheld', want)
                changed = True
                continue
            if want > allowed:
                _sp_count('fertilizer_sale_units_withheld', want - allowed)
                order = [order[0], order[1], allowed]
                changed = True
            stock -= min(want, allowed)
        kept.append(order)
    if changed:
        action = dict(action, market=kept)
    return action
'''

NULL = '''
# Harness control: identical behaviour to the benchmark. Any deviation from a ~50% win rate and a
# ~0 margin here would mean the gate itself is biased (e.g. by seat or by loader state).


def agent(observation, configuration=None):
    _sp_count('calls')
    return _SP_PARENT(observation, configuration)
'''


STRAW = """
# Item 1: demand-conditioned strawberry quantity.
#
# The benchmark plants the same 33 strawberries in every world and sells ~249 units regardless of
# whether the town can absorb them. Measured over 16 self-play worlds, those identical units earn
# 5,391 with two strawberry-demanding shops and 57,194 with seven (Spearman +0.72): in poor worlds
# the marginal units clear at the $1 floor while tomato and egg inventories sit far below neutral.
#
# The target uses engine constants only, no fitted thresholds:
#   * a shop instance consumes one strawberry per 4 turns = 6/day, the town centre 1/day;
#   * our first strawberry production lands about day 15, so a shop revealed on day d can absorb
#     6 * (29 - max(d, 15)) units;
#   * four of the eight shop types demand strawberries, so each undrawn shop adds an instance with
#     probability 1/2;
#   * a plant yields 4 units (one per scheduled production, unfertilised);
#   * the opponent is assumed to mirror our supply, so we can clear about half of total absorption.
_SP_STRAW_SHOPS = ('BRUNCH_SPOT', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP', 'FARMERS_MARKET')
_SP_DRAW_DAYS = (3, 6, 9, 12, 15, 18, 21, 24)
_SP_SHOP_RATE = 6
_SP_TOWN_RATE = 1
_SP_FIRST_SALE_DAY = 15
_SP_SEASON_END = 29
_SP_UNITS_PER_PLANT = 4
_SP_STRAW_MIN = 8
_SP_STRAW_MAX = 33
_SP_STRAW_MODE = __MODE__
_SP_STRAW_FLAT = __FLAT__


def _sp_window(reveal_day):
    return max(0, _SP_SEASON_END - max(reveal_day, _SP_FIRST_SALE_DAY))


def _sp_absorption(observation):
    shops = list((observation.get('town') or {}).get('unlocked_shops') or [])
    total = _SP_TOWN_RATE * _sp_window(0)
    for index, name in enumerate(shops):
        reveal = _SP_DRAW_DAYS[index] if index < len(_SP_DRAW_DAYS) else _SP_DRAW_DAYS[-1]
        if name in _SP_STRAW_SHOPS:
            total += _SP_SHOP_RATE * _sp_window(reveal)
    for index in range(len(shops), len(_SP_DRAW_DAYS)):
        total += 0.5 * _SP_SHOP_RATE * _sp_window(_SP_DRAW_DAYS[index])
    return total


def _sp_straw_target(observation):
    if _SP_STRAW_MODE == 'flat':
        return _SP_STRAW_FLAT
    share = 0.5 * _sp_absorption(observation)
    return max(_SP_STRAW_MIN, min(_SP_STRAW_MAX, int(round(share / _SP_UNITS_PER_PLANT))))


def _sp_straw_on_board(farm):
    return sum(1 for row in farm['tiles'] for tile in row
               if isinstance(tile, dict) and tile.get('crop') == 'STRAWBERRY')


def agent(observation, configuration=None):
    action = _SP_PARENT(observation, configuration)
    farm = _sp_own_farm(observation)
    target = _sp_straw_target(observation)
    allowance = target - _sp_straw_on_board(farm)
    _SP_STATS['target_last'] = target
    changed = False
    if allowance <= 0:
        units = [action.get('farmer')] + list(action.get('hands') or [])
        kept = []
        for unit in units:
            if isinstance(unit, (list, tuple)) and len(unit) > 1 and unit[0] == 'PLANT' and unit[1] == 'STRAWBERRY':
                _sp_count('plants_suppressed')
                kept.append(['PASS'])
                changed = True
            else:
                kept.append(unit)
        if changed:
            action = dict(action, farmer=kept[0], hands=kept[1:])
    else:
        for unit in [action.get('farmer')] + list(action.get('hands') or []):
            if isinstance(unit, (list, tuple)) and len(unit) > 1 and unit[0] == 'PLANT' and unit[1] == 'STRAWBERRY':
                allowance -= 1
    seeds = int(((observation.get('private') or {}).get('seeds') or {}).get('STRAWBERRY', 0) or 0)
    if _sp_straw_on_board(farm) + seeds >= target:
        orders, raw = _sp_orders(action)
        kept = []
        for order in raw:
            if isinstance(order, (list, tuple)) and order and order[0] == 'BUY_SEED' and len(order) > 1 \
                    and order[1] == 'STRAWBERRY':
                _sp_count('seed_orders_suppressed')
                _sp_count('seed_units_suppressed', int(order[2]) if len(order) > 2 else 1)
                changed = True
                continue
            kept.append(order)
        if len(kept) != len(raw):
            action = dict(action, market=kept)
    return action
"""


FLIP = """
# Opening wheat flip size. The benchmark opens with BUY 70 / SELL 70 on turn 0 (V45's EXP284 layer).
# This layer replaces exactly that turn-0 order list with a BUY q / SELL q round trip (q = 0: no orders)
# and leaves everything else, including turn 1's SELL 13 / BUY 5, unchanged.
_SP_FLIP_Q = __Q__
_SP_V45_OPEN = [['BUY_PRODUCT', 'WHEAT', 70], ['SELL', 'WHEAT', 70]]


def agent(observation, configuration=None):
    action = _SP_PARENT(observation, configuration)
    if int(observation['step']) == 0:
        if action.get('market') == _SP_V45_OPEN:
            _sp_count('opening_replaced')
            market = [] if _SP_FLIP_Q == 0 else [['BUY_PRODUCT', 'WHEAT', _SP_FLIP_Q], ['SELL', 'WHEAT', _SP_FLIP_Q]]
            action = dict(action, market=market)
        else:
            _sp_count('opening_unexpected')
    return action
"""

NASH5 = """
# The certified equilibrium of the opening wheat subgame (docs/wheat_flip_equilibrium.md): buy the five
# feed units on turn 0 and keep them, and drop turn 1's now-redundant SELL 13 / BUY 5. Identical to the
# capital-fix layer of agents/v45_event_opening_fixed.py, applied to the frozen benchmark.
_SP_V45_OPEN = [['BUY_PRODUCT', 'WHEAT', 70], ['SELL', 'WHEAT', 70]]
_SP_V45_TURN1 = [['SELL', 'WHEAT', 13], ['BUY_PRODUCT', 'WHEAT', 5]]


def agent(observation, configuration=None):
    action = _SP_PARENT(observation, configuration)
    step = int(observation['step'])
    market = action.get('market') or []
    if step == 0 and market == _SP_V45_OPEN:
        _sp_count('opening_replaced')
        action = dict(action, market=[['BUY_PRODUCT', 'WHEAT', 5]])
    elif step == 1 and market[:2] == _SP_V45_TURN1:
        _sp_count('turn1_trimmed')
        action = dict(action, market=market[2:])
    return action
"""

LAYERS = {
    'sp_null': dict(description='Control: no behavioural change.', body=NULL),
    'sp_flip0': dict(description='Opening flip: no turn-0 wheat orders.', body=FLIP.replace('__Q__', '0')),
    'sp_flip5': dict(description='Opening flip: BUY 5 / SELL 5 on turn 0.', body=FLIP.replace('__Q__', '5')),
    'sp_flip35': dict(description='Opening flip: BUY 35 / SELL 35 on turn 0.', body=FLIP.replace('__Q__', '35')),
    'sp_flip6': dict(description='Opening flip: BUY 6 / SELL 6 on turn 0.', body=FLIP.replace('__Q__', '6')),
    'sp_flip7': dict(description='Opening flip: BUY 7 / SELL 7 on turn 0.', body=FLIP.replace('__Q__', '7')),
    'sp_flip8': dict(description='Opening flip: BUY 8 / SELL 8 on turn 0.', body=FLIP.replace('__Q__', '8')),
    'sp_flip10': dict(description='Opening flip: BUY 10 / SELL 10 on turn 0.', body=FLIP.replace('__Q__', '10')),
    'sp_flip70': dict(description='Opening flip: BUY 70 / SELL 70 (identity check).', body=FLIP.replace('__Q__', '70')),
    'sp_nash5': dict(description='Opening: buy 5 feed wheat on turn 0 and keep them (certified Nash).', body=NASH5),
    'sp_hirecap11': dict(description='Item 3: cap hires at 11/day, the rate both leaders never exceed.',
                         body=HIRE_CAP.replace('__CAP__', '11')),
    'sp_hirecap12': dict(description='Item 3 variant: cap hires at 12/day (drops only the 233-cost 13th hand).',
                         body=HIRE_CAP.replace('__CAP__', '12')),
    'sp_hirecap13': dict(description='Item 3 variant: cap hires at 13/day.',
                         body=HIRE_CAP.replace('__CAP__', '13')),
    'sp_strawdemand': dict(description='Item 1: strawberry count from projected town absorption.',
                           body=STRAW.replace('__MODE__', "'demand'").replace('__FLAT__', '33')),
    'sp_strawcut24': dict(description='Item 1 control: flat cap of 24 strawberries, no conditioning.',
                          body=STRAW.replace('__MODE__', "'flat'").replace('__FLAT__', '24')),
    'sp_strawcut16': dict(description='Item 1 control: flat cap of 16 strawberries, no conditioning.',
                          body=STRAW.replace('__MODE__', "'flat'").replace('__FLAT__', '16')),
    'sp_noquad4': dict(description='Item 5: never buy the fourth quadrant (both leaders, 60/60 games).',
                       body=NO_QUAD4),
    'sp_fertretain': dict(description='Item 4: stop the fertilizer round trip (no purchases, retain a floor).',
                          body=FERT_RETAIN),
}


def build(name, spec, base_text):
    text = base_text + HEADER.format(name=name, sha=BASE_SHA, description=spec['description']) \
        + spec['body'] + FOOTER
    path = ROOT / 'agents' / f'{name}.py'
    path.write_text(text, encoding='utf-8')
    return path


def main():
    base_text = BASE.read_text(encoding='utf-8')
    actual = sha256(BASE.read_bytes()).hexdigest()
    assert actual == BASE_SHA, f'frozen benchmark changed: {actual}'
    from kaggle_environments.agent import get_last_callable
    manifest = {'benchmark': str(BASE.relative_to(ROOT)), 'benchmark_sha256': BASE_SHA, 'candidates': {}}
    for name, spec in LAYERS.items():
        path = build(name, spec, base_text)
        fn = get_last_callable(path.read_text(encoding='utf-8'), path=str(path))
        line = getattr(getattr(fn, '__code__', None), 'co_firstlineno', None)
        assert line and line > len(base_text.splitlines()), (name, 'layer is not the entry point', line)
        manifest['candidates'][name] = dict(path=str(path.relative_to(ROOT)),
                                            sha256=sha256(path.read_bytes()).hexdigest(),
                                            entry_line=line, description=spec['description'])
        print(f'built {name}: entry point at line {line}, sha {manifest["candidates"][name]["sha256"][:12]}')
    out = ROOT / 'results/fresh/selfplay/candidates.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()

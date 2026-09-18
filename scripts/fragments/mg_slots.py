# --------------------------------------------------------------------------- MG slot layer
# Crop swaps on the native tape's own visits (Mother-Goose policy on the V45 chassis).
#
# The chassis replays unit commands by dead reckoning, so the crew's visit to every tile is known in advance
# (tape calendar above). A swap replaces the crop the tape plants at one of its PLANT visits and rewrites
# the crew's later commands on that tile - and only on that tile, only inside the new crop's life - so the
# new crop is planted, watered, harvested and cleared by visits the tape already makes. No unit moves
# differently, no hire is added, and every other tile keeps its tape commands.
#
# A swap is committed only if the calendar proves it can be serviced (engine rules, CROPS table below): a
# watering turn on the planting day, never two consecutive days without a watering turn, harvest turns that
# collect the crop before it decays, and no other tape planting on the tile while the new crop occupies it.
# Seeds: the new crop's seeds are bought on the step before planting; purchases of the replaced crop are
# capped at what the remaining tape plantings still need, so no seed is stranded. Sales: only the units our
# programs harvested are sold by this layer; the tape's own stock keeps its own sale schedule.
_MGS_CFG = __MGS_CFG__
_MGS_STATES = {}
_MGS_REPORT = {}
_MGS_SHED_OPS = ('PICKUP', 'DROP')
# engine CROPS: first_yield_day, max_yield_day, interval, max_yield, ongoing
_MGS_CROPS = {
    'WHEAT': (2, 4, 0, 6, False), 'CARROT': (2, 3, 0, 4, False), 'TOMATO': (8, 8, 1, 4, True),
    'STRAWBERRY': (10, 10, 2, 4, True), 'MELON': (10, 12, 0, 6, False)}
_MGS_SHOP_DEMAND = {
    'BAKERY': ('EGG', 'WHEAT'), 'PIZZA_SHOP': ('MILK', 'TOMATO', 'WHEAT'),
    'BRUNCH_SPOT': ('EGG', 'WHEAT', 'STRAWBERRY'), 'YARN_STORE': ('WOOL',),
    'ICE_CREAM_SHOP': ('STRAWBERRY', 'MILK', 'WHEAT'), 'PET_CAFE': ('CARROT',),
    'SMOOTHIE_SHOP': ('STRAWBERRY', 'MILK'), 'FARMERS_MARKET': ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY')}


def _mgs_count(key, n=1):
    _MGS_REPORT[key] = _MGS_REPORT.get(key, 0) + n


# ---- coexistence with the benchmark's own day-18 tomato programme (V219) ---------------------------------
# V219 qualifies once, at step 432, and refuses if any tomato plant, seed or shed tomato exists. Our tomato
# programs, their reserved seeds and their harvested units are hidden from that check, so V219 decides
# exactly as it would on the tape's own farm. (V219 is a parent layer: it resolves this name at call time.)
_MGS_V219_QUALIFIES = globals().get('_v219_qualifies')


def _mgs_v219_masked(obs):
    player = int(obs['player'])
    st = _MGS_STATES.get(player)
    if not st:
        return obs
    step = int(obs['step'])
    ours = [t for t, p in st['programs'].items() if p['crop'] == 'TOMATO' and p['t0'] <= step < p['end']]
    credit = int(st['credit'].get('TOMATO', 0))
    reserve = int(st['reserve'].get('TOMATO', 0))
    if not ours and not credit and not reserve:
        return obs
    farms = list(obs['farms'])
    farm = dict(farms[player])
    tiles = [list(r) for r in farm['tiles']]
    for x, y in ours:
        c = tiles[y][x]
        if isinstance(c, dict) and c.get('crop') == 'TOMATO':
            tiles[y][x] = None
    farm['tiles'] = tiles
    farms[player] = farm
    private = dict(obs['private'])
    shed = dict(private.get('shed') or {})
    shed['TOMATO'] = max(0, int(shed.get('TOMATO', 0) or 0) - credit)
    seeds = dict(private.get('seeds') or {})
    seeds['TOMATO'] = max(0, int(seeds.get('TOMATO', 0) or 0) - reserve)
    private['shed'], private['seeds'] = shed, seeds
    masked = dict(obs)
    masked['farms'], masked['private'] = farms, private
    _mgs_count('v219_masked_checks')
    return masked


if _MGS_V219_QUALIFIES is not None:
    def _v219_qualifies(obs, native):
        try:
            obs = _mgs_v219_masked(obs)
        except Exception:
            _mgs_count('v219_mask_errors')
        return _MGS_V219_QUALIFIES(obs, native)


# ---- market model -------------------------------------------------------------------------------------
# Engine economics only: _r37_market_price is the chassis's exact copy of the engine price function; a shop
# instance consumes 1 unit of each product it lists every 4 turns (2 if it lists one product) = 6/day from the
# day it unlocks (instance i unlocks on day 3(i+1)); the town centre consumes 1/day. Undrawn instances count at
# their expected rate over the 8 equally likely shop types. Units are sold on the day they are harvested,
# ours and the opponent's interleaved unit by unit.
def _mgs_rate(shop, product):
    d = _MGS_SHOP_DEMAND.get(shop, ())
    return (12.0 if len(d) == 1 else 6.0) if product in d else 0.0


def _mgs_daily_consumption(shops, product, day):
    total = 1.0
    expected = sum(_mgs_rate(s, product) for s in _MGS_SHOP_DEMAND) / float(len(_MGS_SHOP_DEMAND))
    for i in range(8):
        if 3 * (i + 1) > day:
            break
        total += _mgs_rate(shops[i], product) if i < len(shops) else expected
    return total


def _mgs_market(product, inv0, day0, shops, ours, opp, W=None):
    """Revenue (ours, opponent's) from selling the given {day: units} harvest schedules from day0 to day 29.
    Each day's harvest is sold evenly over the next W days (the sale layers spread lots; W=4 matches the
    observed strawberry outcomes of the isolation panel, scripts/calibrate_straw_model.py), in six slots per
    day, and shop consumption is applied every 4 turns as in the engine (the town centre once per day)."""
    W = int(W or _MGS_CFG.get('sale_spread_days', 4))
    so, sp = {}, {}
    for sched, q in ((ours, so), (opp, sp)):
        for d, u in sched.items():
            days = list(range(d, min(30, d + W))) or [29]
            share = u / (len(days) * 6.0)
            for x in days:
                for k in range(6):
                    q[(x, k)] = q.get((x, k), 0.0) + share
    inv = float(inv0)
    r_o = r_p = 0.0
    co = cp = 0.0
    for d in range(day0, 30):
        per = _mgs_daily_consumption(shops, product, d)
        for k in range(6):
            inv -= (per - 1.0) / 6.0 + (1.0 if k == 0 else 0.0)
            co += so.get((d, k), 0.0)
            cp += sp.get((d, k), 0.0)
            a, b = int(co), int(cp)
            co -= a
            cp -= b
            while a > 0 or b > 0:
                if a > 0:
                    r_o += _r37_market_price(product, int(round(inv)))
                    inv += 1
                    a -= 1
                if b > 0:
                    r_p += _r37_market_price(product, int(round(inv)))
                    inv += 1
                    b -= 1
    return r_o, r_p


def _mgs_add(sched, day, units):
    if day <= 29 and units:
        sched[day] = sched.get(day, 0.0) + units


def _mgs_board_supply(farm, crop, day0, per_production):
    """Future harvest schedule of the plants of ``crop`` standing on a farm's board at day0: yield already
    standing on the tile is sold at day0; later productions on their production days."""
    first, maxday, interval, maxy, ongoing = _MGS_CROPS[crop]
    sched = {}
    for row in farm['tiles']:
        for t in row:
            if isinstance(t, dict) and t.get('kind') == 'PLANT' and t.get('crop') == crop:
                P = int(t.get('planted_day', day0))
                if ongoing:
                    _mgs_add(sched, day0, float(t.get('yield_units', 0) or 0))
                    for k in range(maxy):
                        d = P + first + k * interval
                        if d > day0:
                            _mgs_add(sched, d, per_production)
                else:
                    _mgs_add(sched, max(day0, P + maxday), per_production)
    return sched


def _mgs_route_at(route, t):
    return 2 if t >= 648 else route


def _mgs_tape_at(route, t):
    tape = _IMPL.chassis.routes[_mgs_route_at(route, t)]
    return tape[t] if 0 <= t < len(tape) and isinstance(tape[t], dict) else {}


def _mgs_tape_units_now(route, step):
    """Number of tape units (farmer + tape hands) present at ``step``: the farmer plus one per tape HIRE
    executed earlier today (hands hired at hour h act from h+1)."""
    start = step - step % 24
    n = 1
    for t in range(start, step):
        n += sum(1 for o in (_mgs_tape_at(route, t).get('market') or []) if o and o[0] == 'HIRE')
    return n


def _mgs_usable(cmd):
    """A turn at the tile that the layer may repurpose: not a move, not a shed transaction, not an
    animal/structure placement (PLACE of an item is a shed transaction too)."""
    if not cmd:
        return True
    op = cmd[0]
    if op in _TC_MOVES or op in _MGS_SHED_OPS or op == 'PLACE':
        return False
    return op in ('PASS', 'PLANT', 'WATER', 'HARVEST', 'FERTILIZE', 'DIG')


def _mgs_turns(state, tile, t0, t1):
    """Usable turns at ``tile`` in [t0, t1): (step, unit)."""
    out = []
    for t in range(t0, min(t1, 719)):
        row = state['sim'].get(t)
        if not row:
            continue
        for u, (x, y, c) in enumerate(row):
            if (x, y) == tile and _mgs_usable(c):
                out.append((t, u))
    return out


def _mgs_life_end_day(crop, P):
    """First day on which the crop has decayed: ongoing crops decay from the day after their last
    production; one-time crops from the day after max_yield_day."""
    first, maxday, interval, maxy, ongoing = _MGS_CROPS[crop]
    if ongoing:
        return P + first + (maxy - 1) * interval + 1
    return P + maxday + 1


def _mgs_plan(state, tile, t0, crop, replaced=None):
    """Serviceability of ``crop`` planted at step t0 on ``tile`` using only the tape's own turns there.
    Returns (expected_units, why, harvest_day)."""
    first, maxday, interval, maxy, ongoing = _MGS_CROPS[crop]
    P = t0 // 24
    end = _mgs_life_end_day(crop, P)
    if end > 30:
        return 0, 'beyond season', None
    for t in range(t0 + 1, min(719, end * 24)):
        for x, y, c in state['sim'].get(t) or []:
            if (x, y) == tile and c and c[0] == 'PLANT' and len(c) > 1 and c[1] != replaced:
                return 0, 'conflict with tape ' + c[1].lower(), None
    by_day = {}
    for t, u in _mgs_turns(state, tile, t0 + 1, end * 24):
        by_day.setdefault(t // 24, []).append(t)
    if not by_day.get(P):
        return 0, 'no same-day water', None
    last_harvest_day = end - 1
    harvest_days = [d for d in range(P + first, last_harvest_day + 1) if by_day.get(d)]
    if not harvest_days:
        return 0, 'no harvest turn', None
    H = harvest_days[-1]
    for d in range(P + 1, H):
        if not by_day.get(d) and not by_day.get(d - 1):
            return 0, f'two dry days {d - 1}-{d}', None
    if ongoing:
        productions = [P + first + k * interval for k in range(maxy)]
        units = sum(1 for d in productions if d <= H)
        return units, ('full' if units == maxy else f'last turn day {H}'), H
    ws = (maxday + 1) // 2
    watered = 0
    for d in range(P + ws, H + 1):
        n = len(by_day.get(d) or [])
        if d < H and n >= 1:
            watered += 1
        elif d == H and n >= 2:
            watered += 1
    units = min(maxy, 1 + watered)
    return units, ('full' if units == maxy else f'{units} of {maxy}'), H


def _mgs_sim(state, obs, route, step):
    farm = obs['farms'][int(obs['player'])]
    n = _mgs_tape_units_now(route, step)
    positions = [tuple(farm['farmer'])] + [tuple(h) for h in farm['hands']]
    positions = positions[:min(n, len(positions))]
    state['sim'] = _tc_simulate(lambda t: _mgs_tape_at(route, t), step, 718, positions)
    state['sim_from'] = step
    _mgs_count('calendar_builds')


def _mgs_check_positions(state, obs, route, step):
    row = state['sim'].get(step)
    if not row:
        return False
    farm = obs['farms'][int(obs['player'])]
    positions = [tuple(farm['farmer'])] + [tuple(h) for h in farm['hands']]
    for u, (x, y, c) in enumerate(row):
        if u >= len(positions) or positions[u] != (x, y):
            return False
    return True


def _mgs_plantings(state, crop, day_lo, day_hi, t_from):
    """Tape PLANT <crop> visits on days [day_lo, day_hi] at or after t_from: (step, unit, tile)."""
    out = []
    for t in range(max(t_from, day_lo * 24), min(719, (day_hi + 1) * 24)):
        row = state['sim'].get(t)
        if not row:
            continue
        for u, (x, y, c) in enumerate(row):
            if c and c[0] == 'PLANT' and len(c) > 1 and c[1] == crop:
                out.append((t, u, (x, y)))
    return out


def _mgs_commit(state, t0, u, tile, crop, replaced, units, H, rule):
    state['swaps'][(t0, u)] = {'tile': tile, 'crop': crop, 'from': replaced, 't0': t0, 'expected': units}
    state['programs'][tile] = {'crop': crop, 't0': t0, 'day': t0 // 24, 'unit': u, 'harvest_day': H,
                               'end': _mgs_life_end_day(crop, t0 // 24) * 24, 'planted': False,
                               'expected': units, 'harvested': 0}
    state['rule_taken'][rule] = state['rule_taken'].get(rule, 0) + 1
    _mgs_count('swaps_committed')
    _mgs_count('swaps_' + crop.lower())
    _mgs_count('expected_units_' + crop.lower(), units)


def _mgs_demand(shops, product):
    """Shop instances demanding ``product`` (single-product shops consume double)."""
    n = 0.0
    for s in shops:
        d = _MGS_SHOP_DEMAND.get(s, ())
        if product in d:
            n += 2.0 if len(d) == 1 else 1.0
    return n


def _mgs_expected_demand(shops, product, upto):
    """Known shops plus the expected contribution of the undrawn ones up to ``upto`` instances
    (each of the 8 shop types is equally likely)."""
    known = _mgs_demand(shops[:upto], product)
    missing = max(0, upto - len(shops))
    per = sum((2.0 if len(d) == 1 else 1.0) for d in _MGS_SHOP_DEMAND.values() if product in d) / 8.0
    return known + missing * per


def _mgs_table(table, x):
    """Piecewise-linear lookup in a sorted list of (x, value) points."""
    pts = sorted(table)
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / float(x1 - x0)
    return pts[-1][1]


def _mgs_select_swap(state, rule, step):
    lo, hi = rule['days']
    for t0, u, tile in _mgs_plantings(state, rule['from'], lo, hi, step + 1):
        if (t0, u) in state['swaps'] or tile in state['programs']:
            continue
        if rule.get('every', 1) > 1:
            idx = state.setdefault('rule_idx', {}).get(rule['name'], 0)
            state['rule_idx'][rule['name']] = idx + 1
            if idx % rule['every'] != rule.get('offset', 0):
                state['swaps'][(t0, u)] = None
                continue
        if rule.get('max') is not None and state['rule_taken'].get(rule['name'], 0) >= rule['max']:
            state['swaps'][(t0, u)] = None
            continue
        units, why, H = _mgs_plan(state, tile, t0, rule['to'], rule['from'])
        if units < rule.get('min_units', 4):
            state['swaps'][(t0, u)] = None
            _mgs_count('rejected_' + why.split(' ')[0])
            continue
        _mgs_commit(state, t0, u, tile, rule['to'], rule['from'], units, H, rule['name'])


def _mgs_select_batch(state, obs, rule, step):
    """Mother-Goose R5 + R9 on the tape's day-11 strawberry batch: keep a demand-keyed number of strawberry
    slots, give ``melons`` slots to a second melon wave and the rest to tomatoes (capped when no tomato shop
    is visible). Decided once, the day before the batch, from the shops visible then plus the expected
    demand of the undrawn shops up to the first ``shops_upto`` instances."""
    lo, hi = rule['days']
    cands = [c for c in _mgs_plantings(state, rule['from'], lo, hi, step + 1)
             if c[:2] not in state['swaps'] and c[2] not in state['programs']]
    if not cands:
        return
    shops = list((obs.get('town') or {}).get('unlocked_shops') or [])
    upto = rule.get('shops_upto', 4)
    straw = _mgs_expected_demand(shops, 'STRAWBERRY', upto)
    tomato_known = _mgs_demand(shops, 'TOMATO')
    n = len(cands)
    keep = int(round(_mgs_table(rule['straw_keep'], straw) * n / float(rule.get('table_slots', n))))
    keep = max(0, min(n, keep))
    melons = min(rule.get('melons', 0), n - keep) if rule.get('melons') else 0
    tomatoes = n - keep - melons
    if tomato_known <= 0 and rule.get('tomato_cap_no_shop') is not None:
        tomatoes = min(tomatoes, rule['tomato_cap_no_shop'])
    _MGS_REPORT['batch_decision'] = dict(day=step // 24, shops=shops, straw_demand=straw,
                                         tomato_shops=tomato_known, slots=n, keep=keep, melons=melons,
                                         tomatoes=tomatoes)
    # melons first: the slots with the best melon plan (her fixed tiles break ties)
    prefer = [tuple(p) for p in rule.get('melon_tiles', [])]
    plans = []
    for t0, u, tile in cands:
        m_units, m_why, m_H = _mgs_plan(state, tile, t0, 'MELON', rule['from']) if melons else (0, '', None)
        t_units, t_why, t_H = _mgs_plan(state, tile, t0, 'TOMATO', rule['from'])
        plans.append(dict(t0=t0, u=u, tile=tile, m=(m_units, m_H), t=(t_units, t_H), why=t_why))
    used = set()
    for p in sorted(plans, key=lambda p: (-p['m'][0], 0 if p['tile'] in prefer else 1, p['t0'])):
        if melons <= 0:
            break
        if p['m'][0] >= rule.get('melon_min_units', 5):
            _mgs_commit(state, p['t0'], p['u'], p['tile'], 'MELON', rule['from'], p['m'][0], p['m'][1], rule['name'])
            used.add((p['t0'], p['u']))
            melons -= 1
    for p in sorted(plans, key=lambda p: p['t0']):
        if tomatoes <= 0:
            break
        if (p['t0'], p['u']) in used:
            continue
        if p['t'][0] >= rule.get('min_units', 4):
            _mgs_commit(state, p['t0'], p['u'], p['tile'], 'TOMATO', rule['from'], p['t'][0], p['t'][1], rule['name'])
            used.add((p['t0'], p['u']))
            tomatoes -= 1
        else:
            _mgs_count('rejected_' + p['why'].split(' ')[0])
    for p in plans:
        if (p['t0'], p['u']) not in used:
            state['swaps'][(p['t0'], p['u'])] = None
    # her add direction: extra strawberries on the tape's wheat slots in strawberry-rich worlds
    if rule.get('add_table') and rule.get('wheat_days'):
        n_add = int(round(_mgs_table(rule['add_table'], straw)))
        wlo, whi = rule['wheat_days']
        added = 0
        for t0, u, tile in _mgs_plantings(state, 'WHEAT', wlo, whi, step + 1):
            if added >= n_add:
                break
            if (t0, u) in state['swaps'] or tile in state['programs']:
                continue
            units, why, H = _mgs_plan(state, tile, t0, 'STRAWBERRY', 'WHEAT')
            if units < 4:
                continue
            _mgs_commit(state, t0, u, tile, 'STRAWBERRY', 'WHEAT', units, H, rule['name'])
            added += 1
        _MGS_REPORT['batch_decision']['added'] = added


def _mgs_select_share(state, obs, rule, step):
    """Mother-Goose R6: a share of the tape's wheat replants becomes tomatoes, the share set by the tomato
    shops visible on ``share_day``."""
    lo, hi = rule['days']
    if 'share' not in state.setdefault('shares', {}).get(rule['name'], {}):
        shops = list((obs.get('town') or {}).get('unlocked_shops') or [])
        share = _mgs_table(rule['share'], _mgs_demand(shops, 'TOMATO'))
        state['shares'][rule['name']] = {'share': share, 'acc': 0.0}
        _MGS_REPORT['share_' + rule['name']] = round(share, 3)
    sh = state['shares'][rule['name']]
    for t0, u, tile in _mgs_plantings(state, rule['from'], lo, hi, step + 1):
        if (t0, u) in state['swaps'] or tile in state['programs']:
            continue
        sh['acc'] += sh['share']
        if sh['acc'] < 1.0:
            state['swaps'][(t0, u)] = None
            continue
        units, why, H = _mgs_plan(state, tile, t0, rule['to'], rule['from'])
        if units < rule.get('min_units', 4):
            state['swaps'][(t0, u)] = None
            _mgs_count('rejected_' + why.split(' ')[0])
            continue
        sh['acc'] -= 1.0
        _mgs_commit(state, t0, u, tile, rule['to'], rule['from'], units, H, rule['name'])


def _mgs_tile_ops(state, tile, t0, t1, op):
    return sum(1 for t in range(t0, min(t1, 719)) for x, y, c in (state['sim'].get(t) or [])
               if (x, y) == tile and c and c[0] == op)


def _mgs_select_econ(state, obs, rule, step):
    """Demand-keyed strawberry allocation from engine economics (both directions).

    Options on the tape's day-11 strawberry batch (n slots): keep k as strawberries, give m (<= max_melons) to a
    second-wave melon, turn the rest into tomatoes; or keep the whole batch and turn ``a`` of the tape's
    wheat plantings on ``wheat_days`` into (unfertilized) strawberries. Every option is valued with the market
    model against an opponent whose standing plants are read off its board and whose future strawberry
    plantings mirror our tape's (a lineage clone). Objective: margin (our revenue change minus the opponent's)
    net of seeds, the fertilizer the tape would have spent on swapped strawberries (sold instead) and the
    wheat cycles an added strawberry displaces. The tape's allocation is the zero point."""
    player = int(obs['player'])
    day0 = step // 24
    farm, opp_farm = obs['farms'][player], obs['farms'][1 - player]
    shops = list((obs.get('town') or {}).get('unlocked_shops') or [])
    inv = (obs.get('market') or {}).get('inventory') or {}
    prices = (obs.get('market') or {}).get('prices') or {}
    lo, hi = rule['days']
    forced = rule.get('force_melons')
    batch = [c for c in _mgs_plantings(state, 'STRAWBERRY', lo, hi, step + 1)
             if c[:2] not in state['swaps'] and c[2] not in state['programs']]
    F = rule.get('tape_units_per_straw', 7.5) / 4.0
    # tape strawberry supply outside the batch: plants on the board + later tape plantings not in the batch
    base_ours = _mgs_board_supply(farm, 'STRAWBERRY', day0, F)
    future = _mgs_plantings(state, 'STRAWBERRY', day0, 29, step + 1)
    for t0, u, tile in future:
        if (t0, u, tile) in batch:
            continue
        for k in range(4):
            _mgs_add(base_ours, t0 // 24 + 10 + 2 * k, F)
    opp = _mgs_board_supply(opp_farm, 'STRAWBERRY', day0, F)
    for t0, u, tile in future:
        for k in range(4):
            _mgs_add(opp, t0 // 24 + 10 + 2 * k, F)
    fert_price = float(prices.get('FERTILIZER', 30) or 30)
    wheat_price = float(prices.get('WHEAT', 30) or 30) + rule.get('wheat_uplift', 8)
    # candidate slots with their serviceable plans
    slots = []
    for t0, u, tile in batch:
        tu, _, tH = _mgs_plan(state, tile, t0, 'TOMATO', 'STRAWBERRY')
        mu, _, mH = _mgs_plan(state, tile, t0, 'MELON', 'STRAWBERRY') if rule.get('max_melons') else (0, '', None)
        fe = _mgs_tile_ops(state, tile, t0, (t0 // 24 + 17) * 24, 'FERTILIZE')
        fe_tw = _mgs_tile_ops(state, tile, (t0 // 24 + 6) * 24, (t0 // 24 + 11) * 24, 'FERTILIZE')
        slots.append(dict(t0=t0, u=u, tile=tile, P=t0 // 24, tomato=(tu, tH), melon=(mu, mH), fe=fe, fe_tw=fe_tw))
    adds = []
    if rule.get('wheat_days'):
        wlo, whi = rule['wheat_days']
        for t0, u, tile in _mgs_plantings(state, 'WHEAT', wlo, whi, step + 1):
            if (t0, u) in state['swaps'] or tile in state['programs'] or any(a['tile'] == tile for a in adds):
                continue
            su, _, sH = _mgs_plan(state, tile, t0, 'STRAWBERRY', 'WHEAT')
            if su < 4:
                continue
            P = t0 // 24
            lost = 1 + _mgs_tile_ops(state, tile, t0 + 1, (P + 17) * 24, 'PLANT')
            fe = _mgs_tile_ops(state, tile, t0, (P + 17) * 24, 'FERTILIZE')
            adds.append(dict(t0=t0, u=u, tile=tile, P=P, H=sH, lost=lost, fe=fe))
        adds.sort(key=lambda a: (a['lost'], a['t0']))
        adds = adds[:rule.get('max_add', 12)]
    n = len(slots)
    tomato_ok = [s for s in slots if s['tomato'][0] >= 4]
    melon_ok = [s for s in slots if s['melon'][0] >= rule.get('melon_min_units', 5)]
    # melon market: first-wave plants on both boards
    m_base_o = _mgs_board_supply(farm, 'MELON', day0, 6.0)
    m_base_p = _mgs_board_supply(opp_farm, 'MELON', day0, 6.0)

    def value(k, m, a):
        drop = n - k                                  # batch slots leaving strawberry
        t = drop - m
        so = dict(base_ours)
        batch_days = sorted(s['P'] for s in slots)
        for P in batch_days[:k]:
            for j in range(4):
                _mgs_add(so, P + 10 + 2 * j, F)
        for ad in adds[:a]:
            for j in range(4):
                _mgs_add(so, ad['P'] + 10 + 2 * j, 1.0)
        rs_o, rs_p = _mgs_market('STRAWBERRY', inv.get('STRAWBERRY', 10000), day0, shops, so, opp)
        to = {}
        per_prod = rule.get('tomato_units_per_plant', 4.0) / 4.0
        for s in tomato_ok[:t]:
            for j in range(4):
                _mgs_add(to, s['P'] + 8 + j, per_prod)
        # the tomato market also carries both farms' own day-18 programme (V219) when tomato demand makes it
        # likely (it needs >= 3 Pizza/Farmers Market instances among the shops visible on day 18)
        v219 = {}
        if sum(sh in ('PIZZA_SHOP', 'FARMERS_MARKET') for sh in shops) >= rule.get('v219_tomato_shops', 2):
            for x in range(26, 30):
                _mgs_add(v219, x, 20.0)
        to_all = dict(v219)
        for x, u_ in to.items():
            _mgs_add(to_all, x, u_)
        if to_all or v219:
            rt_o, rt_p = _mgs_market('TOMATO', inv.get('TOMATO', 10000), day0, shops, to_all, v219)
        else:
            rt_o, rt_p = 0.0, 0.0
        mo = dict(m_base_o)
        for s in melon_ok[:m]:
            _mgs_add(mo, s['melon'][1], float(s['melon'][0]))
        rm_o, rm_p = _mgs_market('MELON', inv.get('MELON', 10000), day0, shops, mo, m_base_p)
        dropped = (tomato_ok[:t] + melon_ok[:m])
        cost = 50.0 * t + 80.0 * m + 100.0 * a - 100.0 * drop
        hands = _MGS_CFG.get('hands') or {}
        if t and hands.get('enabled'):
            # owned hands on the three window days the tape does not cover (ages 7, 8, 10): one hand per
            # ~6 tiles, priced at the 12th/13th hire of the day, plus bought fertilizer (2 per plant)
            k = min(int(hands.get('max_hands', 3)), max(1, -(-(3 * t + 2) // 20)))
            cost += 3.0 * sum(_MGH_FIB[11 + j] for j in range(k)) + 2.0 * t * (fert_price + 10.0)
        # fertilizer the tape would have spent on dropped strawberries is sold instead, except what a
        # fertilized tomato uses (cfg 'fertilize_swaps')
        used = sum(min(1, s['fe_tw']) for s in tomato_ok[:t]) if _MGS_CFG.get('fertilize_swaps') else 0
        fert = fert_price * (sum(s['fe'] for s in dropped) - used + sum(ad['fe'] for ad in adds[:a]))
        wheat = sum(ad['lost'] for ad in adds[:a]) * (4.0 * wheat_price - 10.0)
        ours = rs_o + rt_o + rm_o - cost + fert - wheat
        theirs = rs_p + rt_p + rm_p
        state.setdefault('econ_parts', {})[(k, m, a)] = dict(straw=rs_o, straw_opp=rs_p, tomato=rt_o, melon=rm_o,
                                                           seeds=-cost, fert=fert, wheat=-wheat)
        return ours, theirs

    base_o, base_p = value(n, 0, 0)
    best = (0.0, n, 0, 0, 0.0, 0.0) if forced is None or len(melon_ok) < forced else (-1e18, n, 0, 0, 0.0, 0.0)
    options = [(k, m, 0) for m in range(0, min(rule.get('max_melons', 0), len(melon_ok)) + 1)
               for k in range(0, n + 1) if n - k - m >= 0 and n - k - m <= len(tomato_ok)]
    options += [(n, 0, a) for a in range(1, len(adds) + 1)]
    if forced is not None and len(melon_ok) >= forced:
        # her rule: exactly ``forced`` second-wave melons; the model still sets the rest of the batch and adds
        options = [(k, forced, 0) for k in range(0, n - forced + 1) if n - k - forced <= len(tomato_ok)]
        options += [(n - forced, forced, a) for a in range(1, len(adds) + 1)]
    objective = rule.get('objective', 'margin')
    for k, m, a in options:
        o, p = value(k, m, a)
        d_own, d_opp = o - base_o, p - base_p
        score = d_own - d_opp if objective == 'margin' else d_own
        if score > best[0] + (rule.get('min_gain', 150.0) if best[0] > -1e17 else 0.0):
            best = (score, k, m, a, d_own, d_opp)
    score, k, m, a, d_own, d_opp = best
    _MGS_REPORT['econ_decision'] = dict(day=day0, shops=shops, slots=n, tomato_ok=len(tomato_ok),
                                        melon_ok=len(melon_ok), adds=len(adds), keep=k, melons=m, add=a,
                                        tomatoes=n - k - m, pred_own=round(d_own), pred_opp=round(d_opp),
                                        pred_score=round(score))
    if rule.get('dry_run'):
        # validation mode: record predictions for fixed alternatives, change nothing
        so = dict(base_ours)
        for s_ in slots:
            for j in range(4):
                _mgs_add(so, s_['P'] + 10 + 2 * j, F)
        rs_o, rs_p = _mgs_market('STRAWBERRY', inv.get('STRAWBERRY', 10000), day0, shops, so, opp)
        _MGS_REPORT['econ_diag'] = dict(
            inv0=inv.get('STRAWBERRY'), supply_ours=round(sum(so.values())), supply_opp=round(sum(opp.values())),
            consumption=round(sum(_mgs_daily_consumption(shops, 'STRAWBERRY', d) for d in range(day0, 30))),
            straw_rev_ours=round(rs_o), straw_rev_opp=round(rs_p),
            ours_by_day={d: round(v, 1) for d, v in sorted(so.items())},
            base_ours={d: round(v, 2) for d, v in sorted(base_ours.items())},
            opp_by_day={d: round(v, 2) for d, v in sorted(opp.items())},
            batch_P=[s_['P'] for s_ in slots], tomato_ok_P=[s_['P'] for s_ in tomato_ok],
            fe=[s_['fe'] for s_ in slots], day0=day0, shops=shops,
            inv={k: inv.get(k) for k in ('STRAWBERRY', 'TOMATO', 'MELON', 'WHEAT')},
            prices={k: prices.get(k) for k in ('STRAWBERRY', 'TOMATO', 'WHEAT', 'FERTILIZER')},
            adds=[(a_['P'], a_['lost'], a_['fe']) for a_ in adds])
        preds = {}
        for kk in rule.get('probe_keep', []):
            if n - kk <= len(tomato_ok):
                o, p = value(kk, 0, 0)
                preds[kk] = (round(o - base_o), round(p - base_p))
        _MGS_REPORT['econ_probe'] = preds
        parts = state.get('econ_parts', {})
        base = parts.get((n, 0, 0), {})
        _MGS_REPORT['econ_parts'] = {str(kk): {c: round(v - base.get(c, 0)) for c, v in parts.get((kk, 0, 0), {}).items()}
                                     for kk in rule.get('probe_keep', []) if (kk, 0, 0) in parts}
        for s in slots:
            state['swaps'][(s['t0'], s['u'])] = None
        return
    melon_set = melon_ok[:m]
    tomato_set = [s for s in tomato_ok if s not in melon_set][:n - k - m]
    chosen = set()
    for s in melon_set:
        _mgs_commit(state, s['t0'], s['u'], s['tile'], 'MELON', 'STRAWBERRY', s['melon'][0], s['melon'][1], rule['name'])
        chosen.add((s['t0'], s['u']))
    for s in tomato_set:
        _mgs_commit(state, s['t0'], s['u'], s['tile'], 'TOMATO', 'STRAWBERRY', s['tomato'][0], s['tomato'][1], rule['name'])
        chosen.add((s['t0'], s['u']))
    for s in slots:
        if (s['t0'], s['u']) not in chosen:
            state['swaps'][(s['t0'], s['u'])] = None
    for ad in adds[:a]:
        # adds are valued with the batch intact; with melons forced the batch keeps n - m strawberries
        units, _, H = _mgs_plan(state, ad['tile'], ad['t0'], 'STRAWBERRY', 'WHEAT')
        _mgs_commit(state, ad['t0'], ad['u'], ad['tile'], 'STRAWBERRY', 'WHEAT', units, H, rule['name'])


# ---- herd: sheep/cow placements converted to geese on the tape's own visits -----------------------------
# A tape animal arrives through a chain: BUY_ANIMAL <A> (market) -> PICKUP <A> at the shed by unit u ->
# BUILD_PASTURE on tile X (any unit) -> PLACE <A> on X by unit u. Converting it to a goose rewrites that
# chain: the purchase item, the pickup item, BUILD_PASTURE -> BUILD_COOP on X and the placed animal. Only
# chains whose build lies in the future are convertible (a built pasture cannot hold a goose), and all
# placements served by one multi-animal pickup convert together. Feed, care and harvest visits on X are
# animal-agnostic and stay as they are; a goose's max_held (4) covers the tape's cow/sheep harvest cadence.
_MGS_STRUCT = {'COW': 'BUILD_PASTURE', 'SHEEP': 'BUILD_PASTURE', 'GOOSE': 'BUILD_COOP'}


def _mgs_herd_chains(state, step):
    """Tape animal chains with a future build: list of dicts."""
    sim = state['sim']
    chains = []
    for t in range(step + 1, min(719, 29 * 24)):
        for u, (x, y, c) in enumerate(sim.get(t) or []):
            if not (c and c[0] == 'PLACE' and len(c) > 1 and c[1] in _MGS_STRUCT):
                continue
            animal, tile = c[1], (x, y)
            pick = None
            for tp in range(t - 1, max(step, t - 24) - 1, -1):
                row = sim.get(tp) or []
                if u < len(row) and row[u][2] and row[u][2][0] == 'PICKUP' and len(row[u][2]) > 1 and row[u][2][1] == animal:
                    pick = (tp, u, int(row[u][2][2]) if len(row[u][2]) > 2 else 1)
                    break
            build = None
            for tb in range(t - 1, step, -1):
                for bu, (bx, by, bc) in enumerate(sim.get(tb) or []):
                    if (bx, by) == tile and bc and bc[0] in ('BUILD_PASTURE', 'BUILD_COOP'):
                        build = (tb, bu, bc[0])
                        break
                if build:
                    break
            chains.append(dict(place=(t, u), tile=tile, animal=animal, pick=pick, build=build))
    return chains


_MGS_ANIMAL_COST = {'COW': 400, 'SHEEP': 500, 'GOOSE': 300}
_MGS_ANIMAL_PRODUCT = {'COW': 'MILK', 'SHEEP': 'WOOL', 'GOOSE': 'EGG'}


def _mgs_herd_ok(rule, shops):
    """Condition for converting at this purchase, from the shops visible now."""
    cond = rule.get('condition', 'mg')
    if cond == 'yarn_visible':
        return 'YARN_STORE' in shops
    if cond == 'no_yarn_visible':
        return 'YARN_STORE' not in shops
    first_two = shops[:2]                      # her R8 partition
    milk = sum(s_ in ('PIZZA_SHOP', 'ICE_CREAM_SHOP', 'SMOOTHIE_SHOP') for s_ in first_two)
    return 'YARN_STORE' not in first_two and milk < 2


def _mgs_select_herd(state, obs, rule, step):
    """Decide conversions at each tape animal purchase (the one executing next step), from the shops visible
    now and a cash check. Purchased animals are matched to the tape's later pickups first-in first-out; a
    pickup converts only if every placement it serves still has its structure build in the future."""
    herd = state['herd']
    if 'chains' not in herd:
        herd['chains'] = _mgs_herd_chains(state, step)
        herd['decided'] = set()
    if herd.get('route') is None:
        return
    tape_buys = []
    for o in _mgs_tape_at(herd['route'], step + 1).get('market') or []:
        if len(o) > 2 and o[0] == 'BUY_ANIMAL' and o[1] in rule.get('convert', ('SHEEP',)):
            tape_buys.append((o[1], int(o[2])))
    if not tape_buys:
        return
    shops = list((obs.get('town') or {}).get('unlocked_shops') or [])
    allowed = _mgs_herd_ok(rule, shops)
    to = rule.get('to', 'GOOSE')
    money = float(obs['farms'][int(obs['player'])]['money'])
    for animal, qty in tape_buys:
        picks = {}
        for ch in herd['chains']:
            if ch['animal'] != animal or not ch['pick'] or ch['pick'][0] <= step + 1:
                continue
            picks.setdefault((ch['pick'][0], ch['pick'][1]), []).append(ch)
        remaining = qty
        for key in sorted(picks):
            if remaining <= 0:
                break
            if key in herd['decided']:
                continue
            group = picks[key]
            herd['decided'].add(key)
            n = group[0]['pick'][2]
            remaining -= n
            if not allowed or remaining < 0 or len(group) != n:
                continue
            if any(not ch['build'] or ch['build'][0] <= step + 1 or ch['build'][2] != _MGS_STRUCT[animal] for ch in group):
                _mgs_count('herd_built_already')
                continue
            extra = (_MGS_ANIMAL_COST[to] - _MGS_ANIMAL_COST[animal]) * n
            if extra > 0 and money < extra + rule.get('cash_margin', 300):
                _mgs_count('herd_declined_cash')
                continue
            money -= max(0, extra)
            for ch in group:
                herd['build'][ch['build'][:2]] = _MGS_STRUCT[to]
                herd['place'][ch['place']] = (to, ch['tile'])
            herd['pick'][key] = (to, n, animal)
            herd['buy'][(animal, to)] = herd['buy'].get((animal, to), 0) + n
            _mgs_count('herd_converted', n)


def _mgs_herd_rewrite(state, obs, action, step):
    herd = state.get('herd')
    if not herd or not (herd['build'] or herd['place'] or herd['pick'] or herd['buy']):
        return action
    cmds = [list(action.get('farmer') or ['PASS'])] + [list(h or ['PASS']) for h in (action.get('hands') or [])]
    farm = obs['farms'][int(obs['player'])]
    positions = [tuple(farm['farmer'])] + [tuple(h) for h in farm['hands']]
    row = state['sim'].get(step) or []
    changed = False
    for u in range(min(len(row), len(cmds), len(positions))):
        c = cmds[u]
        if not c:
            continue
        if (step, u) in herd['build'] and c[0] in ('BUILD_PASTURE', 'BUILD_COOP') and c[0] != herd['build'][(step, u)]:
            cmds[u] = [herd['build'][(step, u)]]
            changed = True
            _mgs_count('herd_builds')
        elif (step, u) in herd['pick'] and c[0] == 'PICKUP' and len(c) > 1:
            to, n, frm = herd['pick'][(step, u)]
            if c[1] == frm:
                cmds[u] = ['PICKUP', to] + ([n] if n > 1 else [])
                changed = True
                _mgs_count('herd_pickups')
        elif (step, u) in herd['place'] and c[0] == 'PLACE' and len(c) > 1:
            to, tile = herd['place'][(step, u)]
            if positions[u] == tile and c[1] != to:
                cmds[u] = ['PLACE', to]
                changed = True
                _mgs_count('herd_places')
                herd['tiles'].add(tile)
    market = [list(o) for o in (action.get('market') or [])]
    for o in list(market):
        if len(o) > 2 and o[0] == 'BUY_ANIMAL':
            for (frm, to), left in list(herd['buy'].items()):
                if frm != o[1] or left <= 0:
                    continue
                n = min(int(o[2]), left)
                herd['buy'][(frm, to)] -= n
                _mgs_count('herd_buys', n)
                if n == int(o[2]):
                    o[1] = to
                else:
                    o[2] = int(o[2]) - n
                    if len(market) < 10:
                        market.append(['BUY_ANIMAL', to, n])
                changed = True
                break
    # production credit from converted animals: the tape's own sales keep their schedule; ours add to them
    for u in range(min(len(cmds), len(positions))):
        if cmds[u] and cmds[u][0] == 'HARVEST' and positions[u] in herd['tiles']:
            x, y = positions[u]
            cell = farm['tiles'][y][x]
            if isinstance(cell, dict) and cell.get('animal') in _MGS_ANIMAL_PRODUCT:
                prod = _MGS_ANIMAL_PRODUCT[cell['animal']]
                n = int(cell.get('yield_units', 0) or 0)
                state['credit'][prod] = state['credit'].get(prod, 0) + n
                _mgs_count('herd_' + prod.lower(), n)
    if changed:
        action = dict(action, farmer=cmds[0], hands=cmds[1:], market=market)
    return action


def _mgs_select(state, obs, step):
    for rule in _MGS_CFG.get('swaps', []):
        key = 'rule_done_' + rule['name']
        if state.get(key):
            continue
        lo, hi = rule['days']
        start = rule.get('decide_day', lo - 1) * 24
        if step < start or step >= (hi + 1) * 24:
            continue
        kind = rule.get('kind', 'swap')
        if kind == 'batch':
            _mgs_select_batch(state, obs, rule, step)
            state[key] = True
        elif kind == 'econ':
            _mgs_select_econ(state, obs, rule, step)
            state[key] = True
        elif kind == 'herd':
            state['herd']['route'] = (_IMPL.chassis.players.get(int(obs['player'])) or {}).get('route')
            _mgs_select_herd(state, obs, rule, step)
        elif kind == 'share':
            if step >= rule.get('share_day', lo) * 24:
                _mgs_select_share(state, obs, rule, step)
        else:
            _mgs_select_swap(state, rule, step)
        if step >= hi * 24:
            state[key] = True


def _mgs_last_turn_today(state, tile, step):
    return not _mgs_turns(state, tile, step + 1, (step // 24 + 1) * 24)


def _mgs_rewrite(state, obs, action, step):
    """Rewrite tape-unit commands standing on program tiles inside each program's life."""
    player = int(obs['player'])
    farm = obs['farms'][player]
    day = step // 24
    positions = [tuple(farm['farmer'])] + [tuple(h) for h in farm['hands']]
    cmds = [list(action.get('farmer') or ['PASS'])] + [list(h or ['PASS']) for h in (action.get('hands') or [])]
    n_tape = len(state['sim'].get(step) or [])
    seeds = dict(obs['private'].get('seeds') or {})
    changed = False
    for u in range(min(n_tape, len(cmds), len(positions))):
        tile = positions[u]
        prog = state['programs'].get(tile)
        if not prog or step < prog['t0'] or step >= prog['end']:
            continue
        cmd = cmds[u]
        if not _mgs_usable(cmd):
            continue
        x, y = tile
        cell = farm['tiles'][y][x]
        crop = prog['crop']
        first, maxday, interval, maxy, ongoing = _MGS_CROPS[crop]
        is_ours = isinstance(cell, dict) and cell.get('kind') == 'PLANT' and cell.get('crop') == crop
        new = None
        if not prog['planted']:
            if step == prog['t0'] and cell is None and seeds.get(crop, 0) > 0:
                new = ['PLANT', crop]
                seeds[crop] -= 1
                state['reserve'][crop] = max(0, state['reserve'].get(crop, 0) - 1)
                prog['planted'] = 'requested'
            elif step >= prog['t0'] and prog['planted'] is False:
                # the planting turn was lost (weed, missing seed): hand the tile back to the tape
                prog['end'] = step
                _mgs_count('plantings_missed')
                continue
        elif is_ours:
            if prog['planted'] == 'requested':
                prog['planted'] = True
                _mgs_count('plantings_confirmed')
            age = day - cell.get('planted_day', day)
            y_units = int(cell.get('yield_units', 0) or 0)
            watered = cell.get('watered_today')
            if ongoing:
                last_prod = first + (maxy - 1) * interval
                fert_active = int(cell.get('fertilized_until_day', -1) or -1) >= day
                later = not _mgs_last_turn_today(state, tile, step)
                must_water = not watered and int(cell.get('consecutive_unwatered', 0) or 0) >= 1 and not later
                inv_u = (obs['private'].get('inventories') or [{}] * (u + 1))
                carries = u < len(inv_u) and int((inv_u[u] or {}).get('FERTILIZER', 0) or 0) > 0
                # fertilizer the tape brought for its own crop here (cfg 'fertilize_swaps'): doubles the next
                # productions on watered days, so the tile's cap (max_yield) forces an earlier harvest
                use_fert = (_MGS_CFG.get('fertilize_swaps') and cmd[0] == 'FERTILIZE' and carries and not fert_active
                            and age < last_prod and (watered or later))
                inc = 2 if fert_active else 1
                if use_fert:
                    new = ['FERTILIZE']
                    _mgs_count('fertilized_swaps')
                elif age >= last_prod:
                    new = ['HARVEST'] if y_units > 0 else ['PASS']
                elif y_units > 0 and y_units + inc > maxy and not must_water:
                    new = ['HARVEST']
                elif not watered:
                    new = ['WATER']
                elif y_units > 0:
                    new = ['HARVEST']
                else:
                    new = ['PASS']
            else:
                H = prog.get('harvest_day') or (prog['day'] + maxday)
                final_day = day >= H or age >= maxday
                if age >= first and final_day and _mgs_last_turn_today(state, tile, step):
                    new = ['HARVEST']
                elif not watered:
                    new = ['WATER']
                elif age >= first and final_day:
                    new = ['HARVEST']
                else:
                    new = ['PASS']
            if new[0] == 'HARVEST':
                prog['harvested'] += y_units
                state['credit'][crop] = state['credit'].get(crop, 0) + y_units
                _mgs_count('harvest_issued_' + crop.lower(), y_units)
        elif isinstance(cell, dict) and cell.get('kind') == 'WEED':
            new = ['DIG']
            if prog['planted'] is True and not prog.get('closed'):
                if prog['harvested'] < prog['expected']:
                    _mgs_count('lost_plants_' + crop.lower())
                prog['closed'] = True
        else:
            # our crop is gone (harvested one-time crop, dug, or never confirmed): the tile goes back to
            # the tape at once, so its own later plantings on this tile run unchanged
            prog['end'] = step
            _mgs_count('tiles_returned')
            continue
        if new is not None and new != cmd:
            cmds[u] = new
            changed = True
            _mgs_count('rewrites_' + new[0].lower())
    if changed:
        action = dict(action, farmer=cmds[0], hands=cmds[1:])
    return action


def _mgs_seeds(state, obs, action, step):
    """Buy our crops' seeds one step ahead against our own seed reserve (never another programme's seeds);
    cap purchases of replaced crops at what the remaining tape plantings still need."""
    market = [list(o) for o in (action.get('market') or [])]
    held = dict(obs['private'].get('seeds') or {})
    # seeds planted by this step's own commands are gone before this step's market runs
    for c in [action.get('farmer') or ['PASS']] + list(action.get('hands') or []):
        if c and c[0] == 'PLANT' and len(c) > 1:
            held[c[1]] = max(0, held.get(c[1], 0) - 1)
    reserve = state['reserve']
    need = {}
    for (t0, u), sw in state['swaps'].items():
        if sw and t0 == step + 1:
            need[sw['crop']] = need.get(sw['crop'], 0) + 1
    changed = False
    own_orders = []
    for crop, n in need.items():
        short = n - reserve.get(crop, 0)
        if short > 0:
            if len(market) >= 10:
                _mgs_count('seed_order_room')
                continue
            order = ['BUY_SEED', crop, short]
            market.append(order)
            own_orders.append(order)
            reserve[crop] = reserve.get(crop, 0) + short
            _mgs_count('seeds_bought_' + crop.lower(), short)
            changed = True
    replaced = {sw['from'] for sw in state['swaps'].values() if sw}
    for crop in replaced:
        remaining = 0
        for t in range(step + 1, 719):
            row = state['sim'].get(t)
            if not row:
                continue
            for u, (x, y, c) in enumerate(row):
                if c and c[0] == 'PLANT' and len(c) > 1 and c[1] == crop:
                    if state['swaps'].get((t, u)):
                        continue
                    prog = state['programs'].get((x, y))
                    if prog and prog['t0'] <= t < prog['end']:
                        continue
                    remaining += 1
        tape_held = max(0, held.get(crop, 0) - reserve.get(crop, 0))
        allowance = max(0, remaining - tape_held)
        for o in market:
            if len(o) > 2 and o[0] == 'BUY_SEED' and o[1] == crop and not any(o is x for x in own_orders):
                q = max(0, int(o[2]))
                keep = min(q, allowance)
                allowance -= keep
                if keep != q:
                    _mgs_count('seed_cut_' + crop.lower(), q - keep)
                    o[2] = keep
                    changed = True
    if changed:
        action = dict(action, market=market)
    return action


def _mgs_sell(state, obs, action):
    """Sell the units our programs harvested (credit), never the tape's own stock of the same crop."""
    credit = {c: n for c, n in state['credit'].items() if n > 0}
    if not credit:
        return action
    market = [list(o) for o in (action.get('market') or [])]
    try:
        projected = projected_shed(action, FarmView(obs))
    except Exception:
        projected = dict(obs['private'].get('shed') or {})
    changed = False
    for crop in sorted(credit):
        planned = sum(max(0, int(o[2])) for o in market if len(o) > 2 and o[0] == 'SELL' and o[1] == crop)
        q = min(credit[crop], max(0, int(projected.get(crop, 0) or 0) - planned))
        if q <= 0:
            continue
        for o in market:
            if len(o) > 2 and o[0] == 'SELL' and o[1] == crop:
                o[2] = int(o[2]) + q
                break
        else:
            if len(market) >= 10:
                continue
            market.append(['SELL', crop, q])
        state['credit'][crop] -= q
        _mgs_count('sell_units_' + crop.lower(), q)
        changed = True
    if changed:
        action = dict(action, market=market)
    return action


_MGS_V45_OPEN = [['BUY_PRODUCT', 'WHEAT', 70], ['SELL', 'WHEAT', 70]]


_MGS_MG_OPEN0 = [['BUY_PRODUCT', 'WHEAT', 13], ['BUY_PRODUCT', 'WHEAT', 5], ['SELL', 'WHEAT', 13]]
_MGS_V45_TURN1 = [['SELL', 'WHEAT', 13], ['BUY_PRODUCT', 'WHEAT', 5]]


def _mgs_opening(action, step):
    """Optional opening changes. cfg 'opening' = 'mg': Mother-Goose's recorded wheat orders (turn 0 BUY 13,
    BUY 5, SELL 13; turn 1 SELL 5, BUY 5 in place of V45's SELL 13, BUY 5). cfg 'flip' = q: replaces exactly
    V45's turn-0 BUY 70 / SELL 70 round trip with BUY q / SELL q."""
    market = action.get('market') or []
    if _MGS_CFG.get('opening') == 'nash5':
        # certified equilibrium of the opening wheat game: buy the five feed units on turn 0 and keep them
        if step == 0 and market == _MGS_V45_OPEN:
            _mgs_count('opening_replaced')
            return dict(action, market=[['BUY_PRODUCT', 'WHEAT', 5]])
        if step == 1 and [list(o) for o in market[:2]] == _MGS_V45_TURN1:
            _mgs_count('turn1_replaced')
            return dict(action, market=[list(o) for o in market[2:]])
        return action
    if _MGS_CFG.get('opening') == 'mg':
        if step == 0 and market == _MGS_V45_OPEN:
            _mgs_count('opening_replaced')
            return dict(action, market=[list(o) for o in _MGS_MG_OPEN0])
        if step == 1 and [list(o) for o in market[:2]] == _MGS_V45_TURN1:
            _mgs_count('turn1_replaced')
            return dict(action, market=[['SELL', 'WHEAT', 5], ['BUY_PRODUCT', 'WHEAT', 5]] + [list(o) for o in market[2:]])
        return action
    q = _MGS_CFG.get('flip')
    if q is None or step != 0:
        return action
    if action.get('market') == _MGS_V45_OPEN:
        _mgs_count('opening_replaced')
        return dict(action, market=[] if q == 0 else [['BUY_PRODUCT', 'WHEAT', q], ['SELL', 'WHEAT', q]])
    _mgs_count('opening_unexpected')
    return action


def agent(observation, configuration=None):
    action = _MGS_PARENT(observation, configuration)
    try:
        step = int(observation['step'])
        player = int(observation['player'])
        state = _MGS_STATES.get(player)
        if state is None or step <= state.get('last', -1):
            _MGS_REPORT.clear()
            state = _MGS_STATES[player] = {'last': -1, 'sim': {}, 'swaps': {}, 'programs': {}, 'rule_taken': {},
                                           'credit': {}, 'reserve': {},
                                           'herd': {'build': {}, 'pick': {}, 'place': {}, 'buy': {}, 'tiles': set()}}
        state['last'] = step
        if step <= 1:
            action = _mgs_opening(action, step)
        if step < 145 or step >= 718:
            return action
        native = _IMPL.chassis.players.get(player) or {}
        route = native.get('route')
        if route is None:
            return action
        if not state['sim'] or not _mgs_check_positions(state, observation, route, step):
            if state['sim']:
                _mgs_count('calendar_resync')
            _mgs_sim(state, observation, route, step)
        _mgs_select(state, observation, step)
        action = _mgs_rewrite(state, observation, action, step)
        action = _mgs_herd_rewrite(state, observation, action, step)
        _hands = globals().get('_mgh_service')
        if _hands is not None:
            action = _hands(state, observation, action, step)
        action = _mgs_seeds(state, observation, action, step)
        action = _mgs_sell(state, observation, action)
    except Exception as exc:
        _mgs_count('errors')
        _MGS_REPORT['last_error'] = repr(exc)[:200]
    return action


agent.mgs_telemetry = _MGS_REPORT

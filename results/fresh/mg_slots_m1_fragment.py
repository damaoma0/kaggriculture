# --------------------------------------------------------------------------- MG slot layer
# Crop swaps on the native tape's own visits (Mother-Goose policy on the V45 chassis).
#
# The chassis replays unit commands by dead reckoning, so the crew's visit to every tile is known in advance
# (tape calendar above). A swap replaces the crop the tape plants at one of its PLANT visits and rewrites
# the crew's later commands on that tile - and only on that tile, only inside the new crop's life - so the
# new crop is planted, watered, harvested and cleared by visits the tape already makes. No unit moves
# differently, no hire is added, and every other tile keeps its tape commands.
#
# A swap is committed only if the calendar proves it can be serviced: a watering turn on the planting day,
# never two consecutive days without a watering turn, and a turn on the day the last unit is available.
# Seeds: the swapped crop's seeds are bought on the step before planting; purchases of the replaced crop
# are capped at what the remaining (unswapped) tape plantings still need, so no seed is stranded.
_MGS_CFG = __MGS_CFG__
_MGS_STATES = {}
_MGS_REPORT = {}
_MGS_CROP_LIFE = {'TOMATO': 8, 'STRAWBERRY': 10}   # first_yield_day
_MGS_SEED_COST = {'WHEAT': 10, 'CARROT': 20, 'TOMATO': 50, 'STRAWBERRY': 100, 'MELON': 80}
_MGS_SHED_OPS = ('PICKUP', 'DROP')


def _mgs_count(key, n=1):
    _MGS_REPORT[key] = _MGS_REPORT.get(key, 0) + n


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


def _mgs_tomato_plan(state, tile, t0, replaced=None):
    """Serviceability of a tomato planted at step t0 on ``tile`` with the tape's own visits.
    Returns (expected_units, detail) - 0 when it cannot survive, or when the tape plants a different crop
    on this tile while the tomato would still occupy it (that planting would be lost)."""
    P = t0 // 24
    for t in range(t0 + 1, min(719, (P + 12) * 24)):
        for x, y, c in state['sim'].get(t) or []:
            if (x, y) == tile and c and c[0] == 'PLANT' and len(c) > 1 and c[1] != replaced:
                return 0, 'conflict with tape ' + c[1].lower()
    turns = _mgs_turns(state, tile, t0 + 1, (P + 12) * 24)
    by_day = {}
    for t, u in turns:
        by_day.setdefault(t // 24, []).append(t)
    if not by_day.get(P):
        return 0, 'no same-day water'
    for d in range(P + 1, P + 11):
        if not by_day.get(d) and not by_day.get(d - 1):
            return 0, f'two dry days {d - 1}-{d}'
    if by_day.get(P + 11):
        return 4, 'full'
    for d, units in ((P + 10, 3), (P + 9, 2), (P + 8, 1)):
        if by_day.get(d):
            return units, f'last turn day {d}'
    return 0, 'no harvest turn'


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


def _mgs_select(state, obs, step):
    """Commit swaps for tape plantings in the look-ahead window, per _MGS_CFG['swaps'] rules."""
    for rule in _MGS_CFG.get('swaps', []):
        key = 'rule_done_' + rule['name']
        if state.get(key):
            continue
        lo, hi = rule['days']
        if step < lo * 24 - 24 or step >= (hi + 1) * 24:
            continue
        candidates = _mgs_plantings(state, rule['from'], lo, hi, step + 1)
        taken = 0
        for t0, u, tile in candidates:
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
            units, why = _mgs_tomato_plan(state, tile, t0, rule['from'])
            if units < rule.get('min_units', 4):
                state['swaps'][(t0, u)] = None
                _mgs_count('rejected_' + why.split(' ')[0])
                continue
            state['swaps'][(t0, u)] = {'tile': tile, 'crop': rule['to'], 'from': rule['from'], 't0': t0,
                                      'expected': units}
            state['programs'][tile] = {'crop': rule['to'], 't0': t0, 'day': t0 // 24, 'unit': u,
                                       'end': (t0 // 24 + 12) * 24, 'planted': False, 'expected': units,
                                       'harvested': 0}
            state['rule_taken'][rule['name']] = state['rule_taken'].get(rule['name'], 0) + 1
            _mgs_count('swaps_committed')
            _mgs_count('expected_units', units)
        if step >= hi * 24:
            state[key] = True


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
        is_ours = isinstance(cell, dict) and cell.get('kind') == 'PLANT' and cell.get('crop') == prog['crop']
        new = None
        if not prog['planted']:
            if step == prog['t0'] and cell is None and seeds.get(prog['crop'], 0) > 0:
                new = ['PLANT', prog['crop']]
                seeds[prog['crop']] -= 1
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
            if age >= 11:
                new = ['HARVEST'] if y_units > 0 else ['PASS']
            elif not cell.get('watered_today'):
                new = ['WATER']
            elif y_units > 0:
                new = ['HARVEST']
            else:
                new = ['PASS']
            if new[0] == 'HARVEST':
                prog['harvested'] += y_units
                _mgs_count('harvest_issued_units', y_units)
        elif isinstance(cell, dict) and cell.get('kind') == 'WEED':
            new = ['DIG']
            if prog['planted'] is True and not prog.get('closed'):
                if prog['harvested'] < prog['expected']:
                    _mgs_count('lost_plants')
                prog['closed'] = True
        else:
            # our crop is gone (dug, or never confirmed): the tile goes back to the tape at once, so its
            # own later plantings on this tile (wheat cycles, carrots) run unchanged
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
    """Buy the swapped crop's seeds one step ahead; cap purchases of replaced crops at remaining need."""
    market = [list(o) for o in (action.get('market') or [])]
    held = dict(obs['private'].get('seeds') or {})
    # seeds planted by this step's own commands are gone before this step's market runs
    for c in [action.get('farmer') or ['PASS']] + list(action.get('hands') or []):
        if c and c[0] == 'PLANT' and len(c) > 1:
            held[c[1]] = max(0, held.get(c[1], 0) - 1)
    # 1. seeds for swapped plantings next step
    need = {}
    for (t0, u), sw in state['swaps'].items():
        if sw and t0 == step + 1:
            need[sw['crop']] = need.get(sw['crop'], 0) + 1
    changed = False
    for crop, n in need.items():
        bought = sum(int(o[2]) for o in market if len(o) > 2 and o[0] == 'BUY_SEED' and o[1] == crop)
        short = n - held.get(crop, 0) - bought
        if short > 0:
            if len(market) >= 10:
                _mgs_count('seed_order_room')
                continue
            market.append(['BUY_SEED', crop, short])
            _mgs_count('seeds_bought_' + crop.lower(), short)
            changed = True
    # 2. cap purchases of crops whose tape plantings were swapped away
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
        allowance = max(0, remaining - held.get(crop, 0))
        for o in market:
            if len(o) > 2 and o[0] == 'BUY_SEED' and o[1] == crop:
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
    if not state['programs']:
        return action
    market = [list(o) for o in (action.get('market') or [])]
    crops = {p['crop'] for p in state['programs'].values()}
    try:
        projected = projected_shed(action, FarmView(obs))
    except Exception:
        projected = dict(obs['private'].get('shed') or {})
    changed = False
    for crop in sorted(crops):
        if any(len(o) > 1 and o[0] == 'SELL' and o[1] == crop for o in market):
            continue
        q = int(projected.get(crop, 0) or 0)
        if q > 0 and len(market) < 10:
            market.append(['SELL', crop, q])
            _mgs_count('sell_units_' + crop.lower(), q)
            changed = True
    if changed:
        action = dict(action, market=market)
    return action


def agent(observation, configuration=None):
    action = _MGS_PARENT(observation, configuration)
    try:
        step = int(observation['step'])
        player = int(observation['player'])
        state = _MGS_STATES.get(player)
        if state is None or step <= state.get('last', -1):
            state = _MGS_STATES[player] = {'last': -1, 'sim': {}, 'swaps': {}, 'programs': {}, 'rule_taken': {}}
            _MGS_REPORT.clear()
        state['last'] = step
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
        action = _mgs_seeds(state, observation, action, step)
        action = _mgs_sell(state, observation, action)
    except Exception as exc:
        _mgs_count('errors')
        _MGS_REPORT['last_error'] = repr(exc)[:200]
    return action


agent.mgs_telemetry = _MGS_REPORT

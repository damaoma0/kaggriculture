# --------------------------------------------------------------------------- owned hands
# Production-window servicing of the slot layer's tomato programmes. The tape's own visits give a swapped
# tomato 5 units (scripts/tomato_schedule_test.py); 8 needs a unit on the tile with fertilizer at ages 7 and
# 10 and water on each of ages 7-10 - Mother-Goose's schedule on 285 of her plants
# (results/fresh/mg_executor/servicing.json). Hands are hired after every other layer's hire window (the
# tape hires by hour 2, the chassis's V219/V233 programmes request by hour 6), so their indices sit above
# every tape hand and no other layer addresses them. They buy their fertilizer with the hire order, pick it
# up at the shed, walk the bed nearest-first doing FERTILIZE -> WATER -> HARVEST on each tile (no-ops are
# skipped), and drop their cargo at the shed before midnight. A failed hire leaves the tape's visits, so the
# tile still yields 5.
_MGH_CFG = _MGS_CFG.get('hands') or {}
_MGH_FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597]
_MGH_CANON = {7: ('FERTILIZE', 'WATER'), 8: ('WATER', 'HARVEST'), 9: ('WATER', 'HARVEST'),
              10: ('FERTILIZE', 'WATER', 'HARVEST'), 11: ('HARVEST',)}
_MGH_SHED = ((4, 4), (5, 4), (4, 5), (5, 5))


def _mgh_fib(n):
    return _MGH_FIB[n] if n < len(_MGH_FIB) else _MGH_FIB[-1]


def _mgh_dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _mgh_walk(pos, target):
    if pos[0] != target[0]:
        return ['EAST' if pos[0] < target[0] else 'WEST']
    if pos[1] != target[1]:
        return ['SOUTH' if pos[1] < target[1] else 'NORTH']
    return None


def _mgh_home(pos):
    return min(_MGH_SHED, key=lambda p: (_mgh_dist(pos, p), _MGH_SHED.index(p)))


def _mgh_chain(start, tiles):
    """Nearest-neighbour order of tiles from start; returns (ordered tiles, travel)."""
    left = list(tiles)
    out, pos, travel = [], start, 0
    while left:
        nxt = min(left, key=lambda t: (_mgh_dist(pos, t), t[1], t[0]))
        travel += _mgh_dist(pos, nxt)
        out.append(nxt)
        left.remove(nxt)
        pos = nxt
    return out, travel


def _mgh_plan(state, obs, step):
    """Today's tasks {tile: [ops]} for owned TOMATO programmes in their production window, minus tiles the
    tape's calendar already covers today (enough usable turns there and no fertilizer needed)."""
    day = step // 24
    farm = obs['farms'][int(obs['player'])]
    plan = {}
    for tile, prog in state['programs'].items():
        if prog['crop'] != 'TOMATO' or prog['planted'] is not True or step >= prog['end']:
            continue
        x, y = tile
        cell = farm['tiles'][y][x]
        if not (isinstance(cell, dict) and cell.get('kind') == 'PLANT' and cell.get('crop') == 'TOMATO'):
            continue
        age = day - int(cell.get('planted_day', day))
        ops = _MGH_CANON.get(age)
        if not ops:
            continue
        ops = list(ops)
        if 'FERTILIZE' in ops and int(cell.get('fertilized_until_day', -1) or -1) >= day + 1:
            ops.remove('FERTILIZE')
        tape_turns = len(_mgs_turns(state, tile, day * 24, (day + 1) * 24))
        if 'FERTILIZE' not in ops and tape_turns >= len(ops):
            continue
        plan[tile] = ops
    return plan


def _mgh_reset(h, day):
    h.clear()
    h.update(day=day, requested=None, owned=[], queue={}, ops={}, pickup={}, picked={}, first=None, k=0, plan={})


def _mgh_request(state, obs, action, step):
    h = state['hands']
    day, hour = step // 24, step % 24
    if h.get('day') != day:
        _mgh_reset(h, day)
    if h['requested'] is not None or day < _MGH_CFG.get('first_day', 12) or day > 28:
        return action
    player = int(obs['player'])
    route = (_IMPL.chassis.players.get(player) or {}).get('route')
    if route is None:
        return action
    last_tape_hire = max([t % 24 for t in range(day * 24, min(719, day * 24 + 24))
                          for o in (_mgs_tape_at(route, t).get('market') or []) if o and o[0] == 'HIRE'], default=-1)
    gate = last_tape_hire
    for name in ('_V219_STATES', '_V233_STATES'):
        st = (globals().get(name) or {}).get(player) or {}
        if st.get('eligible') or st.get('committed'):
            gate = max(gate, 6)
    if hour <= gate:
        return action
    if hour > _MGH_CFG.get('latest_hour', 9):
        h['requested'] = (step, 0)
        return action
    plan = _mgh_plan(state, obs, step)
    if not plan:
        h['requested'] = (step, 0)
        return action
    farm = obs['farms'][player]
    per_hand = 23 - hour - 1                       # acts from hour+1 to 23, last turn kept for DROP
    n_fert = sum(1 for ops in plan.values() if 'FERTILIZE' in ops)
    work = sum(len(ops) for ops in plan.values())
    _, travel = _mgh_chain((4, 5), list(plan))
    need = work + travel + (1 if n_fert else 0) + 2
    k = min(int(_MGH_CFG.get('max_hands', 2)), max(1, -(-need // max(1, per_hand))))
    hires_today = int(farm.get('hires_today', 0))
    parent_hires = sum(1 for o in (action.get('market') or []) if o and o[0] == 'HIRE')
    cost = sum(_mgh_fib(hires_today + parent_hires + i) for i in range(k))
    fert_price = float((obs.get('market') or {}).get('prices', {}).get('FERTILIZER', 40) or 40) + 10
    shed_fert = int(obs['private'].get('shed', {}).get('FERTILIZER', 0) or 0)
    buy = max(0, n_fert - shed_fert)
    cost += buy * fert_price
    if float(farm['money']) < cost + _MGH_CFG.get('cash_margin', 500):
        _mgs_count('hands_declined_cash')
        h['requested'] = (step, 0)
        return action
    market = [list(o) for o in (action.get('market') or [])]
    if len(market) + k + (1 if buy else 0) > 10:
        _mgs_count('hands_declined_orders')
        h['requested'] = (step, 0)
        return action
    market += [['HIRE'] for _ in range(k)]
    if buy:
        market.append(['BUY_PRODUCT', 'FERTILIZER', buy])
        _mgs_count('hands_fert_bought', buy)
    h['requested'] = (step, k)
    h['first'] = 1 + len(farm['hands']) + parent_hires
    h['k'] = k
    h['plan'] = plan
    _mgs_count('hands_requested', k)
    _mgs_count('hands_hire_cost', cost - buy * fert_price)
    return dict(action, market=market)


def _mgh_assign(h, farm):
    """Split today's tiles into k nearest-neighbour chains, one per owned hand, from its spawn tile."""
    tiles = sorted(h['plan'], key=lambda t: (t[1], t[0]))
    k = len(h['owned'])
    chunks = [tiles[i::k] for i in range(k)] if k > 1 else [tiles]
    # rebalance by geometry: assign each tile to the chain whose current end is nearest
    if k > 1:
        chains = [[] for _ in range(k)]
        ends = [tuple(farm['hands'][idx - 1]) for idx in h['owned']]
        for t in tiles:
            j = min(range(k), key=lambda j: (len(chains[j]), _mgh_dist(ends[j], t)))
            chains[j].append(t)
            ends[j] = t
        chunks = chains
    for idx, chunk in zip(h['owned'], chunks):
        start = tuple(farm['hands'][idx - 1])
        order, _ = _mgh_chain(start, chunk)
        h['queue'][idx] = order
        h['ops'][idx] = {t: list(h['plan'][t]) for t in order}
        h['pickup'][idx] = sum(1 for t in order if 'FERTILIZE' in h['plan'][t])
        h['picked'][idx] = False


def _mgh_step(state, obs, h, idx, step):
    farm = obs['farms'][int(obs['player'])]
    day, hour = step // 24, step % 24
    pos = tuple(farm['hands'][idx - 1])
    invs = obs['private'].get('inventories') or []
    inv = invs[idx] if idx < len(invs) else {}
    cargo = sum(int(v or 0) for k_, v in inv.items() if k_ != 'FERTILIZER')
    home = _mgh_home(pos)
    turns_left = 24 - hour
    # end of day: get the cargo into the shed before midnight (the tape's hour-23 storage guard then sees it)
    if cargo and turns_left <= _mgh_dist(pos, home) + 1:
        return _mgh_walk(pos, home) or ['DROP']
    if h['pickup'].get(idx, 0) > 0 and not h['picked'].get(idx):
        if pos in _MGH_SHED:
            h['picked'][idx] = True
            have = int(inv.get('FERTILIZER', 0) or 0)
            want = h['pickup'][idx] - have
            if want > 0 and int(obs['private'].get('shed', {}).get('FERTILIZER', 0) or 0) > 0:
                _mgs_count('hands_pickups')
                return ['PICKUP', 'FERTILIZER', want]
        else:
            return _mgh_walk(pos, home)
    queue = h['queue'].get(idx) or []
    while queue:
        tile = queue[0]
        if pos != tile:
            return _mgh_walk(pos, tile)
        x, y = tile
        cell = farm['tiles'][y][x]
        ops = h['ops'][idx].get(tile) or []
        while ops:
            op = ops.pop(0)
            if not (isinstance(cell, dict) and cell.get('kind') == 'PLANT'):
                continue
            if op == 'FERTILIZE':
                if int(inv.get('FERTILIZER', 0) or 0) > 0 and int(cell.get('fertilized_until_day', -1) or -1) < day:
                    _mgs_count('hands_fertilize')
                    return ['FERTILIZE']
            elif op == 'WATER':
                if not cell.get('watered_today'):
                    _mgs_count('hands_water')
                    return ['WATER']
            elif op == 'HARVEST':
                units = int(cell.get('yield_units', 0) or 0)
                if units > 0:
                    state['credit']['TOMATO'] = state['credit'].get('TOMATO', 0) + units
                    prog = state['programs'].get(tile)
                    if prog:
                        prog['harvested'] += units
                    _mgs_count('hands_harvest_units', units)
                    return ['HARVEST']
        queue.pop(0)
    if cargo or int(inv.get('FERTILIZER', 0) or 0) > 0:
        return _mgh_walk(pos, home) or ['DROP']
    return ['PASS']


def _mgh_drive(state, obs, action, step):
    h = state['hands']
    farm = obs['farms'][int(obs['player'])]
    if not h.get('owned') and h.get('requested') and h['requested'][1] and h['requested'][0] == step - 1:
        k, first = h['k'], h['first']
        if len(farm['hands']) + 1 >= first + k:
            h['owned'] = list(range(first, first + k))
            _mgh_assign(h, farm)
            _mgs_count('hands_hired', k)
        else:
            _mgs_count('hands_shortfall', k)
    if not h.get('owned'):
        return action
    cmds = [list(action.get('farmer') or ['PASS'])] + [list(c or ['PASS']) for c in (action.get('hands') or [])]
    n_units = 1 + len(farm['hands'])
    while len(cmds) < n_units:
        cmds.append(['PASS'])
    for idx in h['owned']:
        if idx >= n_units:
            continue
        cmds[idx] = _mgh_step(state, obs, h, idx, step)
    return dict(action, farmer=cmds[0], hands=cmds[1:n_units])


def _mgh_service(state, obs, action, step):
    if not _MGH_CFG.get('enabled'):
        return action
    state.setdefault('hands', {})
    action = _mgh_drive(state, obs, action, step)
    action = _mgh_request(state, obs, action, step)
    return action

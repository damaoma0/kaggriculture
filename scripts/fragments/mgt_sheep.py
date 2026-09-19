# --------------------------------------------------------------------------- Yarn-responsive sheep overlay
# Mother-Goose's own plan adds sheep when Yarn Stores are revealed: season sheep = 4 + sum over Yarn Stores of
# {reveal day 3: 10, 6: 9, 9: 4, 12: 2, 15: 2, later: 0} (additive, fits 88% of 584 games within +-1;
# results/fresh/mg_tape/yarn_rule.json). A borrowed tape recorded in a world with fewer Yarn Stores does not,
# which is the largest single routing loss (wool -13.5k in those worlds). This overlay buys the missing sheep
# and services them with owned hands:
#   * deficit = her rule's target - sheep the tape has bought and still plans to buy - sheep we bought;
#   * tiles: fields the current tape only ever plants with wheat or carrots from now on (tape calendar), nearest
#     the shed; a tape visit to a converted tile is a no-op, or a HARVEST that collects the wool for us;
#   * hands are hired after the tape's last hire of the day, so they sit above every tape hand index;
#   * every day: buy the feed wheat with the hire, pick it up, then per sheep FEED, CARE, HARVEST, COLLECT.
# Engine economics: a sheep fed and cared for daily yields 6 wool at its first production (6 days after placement)
# and 4 every 3 days after; a converted wheat tile gives up about 4 wheat per 4 days.
_SHP_PARENT = agent
_SHP_CFG = __SHEEP_CFG__
_SHP_STATES = {}
_SHP_REPORT = {}
_SHP_NUM = {}
_SHP_LOOKUP = {3: 10, 6: 9, 9: 4, 12: 2, 15: 2}
_SHP_FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]
_SHP_SHED = ((4, 4), (5, 4), (4, 5), (5, 5))


def _shp_count(key, n=1):
    _SHP_REPORT[key] = _SHP_REPORT.get(key, 0) + n


def _shp_walk(pos, target):
    if pos[0] != target[0]:
        return ['EAST' if pos[0] < target[0] else 'WEST']
    if pos[1] != target[1]:
        return ['SOUTH' if pos[1] < target[1] else 'NORTH']
    return None


def _shp_dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _shp_home(pos):
    return min(_SHP_SHED, key=lambda p: (_shp_dist(pos, p), _SHP_SHED.index(p)))


def _shp_route(player):
    st = _MGT_IMPL.chassis.players.get(player) or {}
    return _MGT_ROUTES.get(st.get('route'))


def _shp_tape_sheep(tape, t_from, t_to):
    n = 0
    for t in range(max(0, t_from), min(len(tape), t_to)):
        for o in (tape[t].get('market') or []):
            if len(o) >= 3 and o[0] == 'BUY_ANIMAL' and o[1] == 'SHEEP':
                n += int(o[2])
    return n


def _shp_last_hire_hour(tape, day):
    hours = [t % 24 for t in range(day * 24, min(len(tape), day * 24 + 24))
             for o in (tape[t].get('market') or []) if o and o[0] == 'HIRE']
    return max(hours) if hours else -1


def _shp_field_tiles(tape, farm, step, n):
    """Tiles the tape only plants with wheat/carrot from now on (and never builds on), currently empty or
    holding wheat/carrot, nearest the shed and each other."""
    day = step // 24
    sim = _tc_simulate(lambda t: tape[t] if t < len(tape) else {}, day * 24, 718, [(4, 4)])
    future = {}
    for t, row in sim.items():
        if t < step:
            continue
        for x, y, c in row:
            if not c:
                continue
            if c[0] == 'PLANT' and len(c) > 1:
                future.setdefault((x, y), set()).add(c[1])
            elif c[0] in ('BUILD_PASTURE', 'BUILD_COOP', 'PLACE'):
                future.setdefault((x, y), set()).add('STRUCTURE')
    ok = []
    for (x, y), crops in future.items():
        if not crops <= {'WHEAT', 'CARROT'} or (x, y) in _SHP_SHED:
            continue
        cell = farm['tiles'][y][x]
        if cell is None or (isinstance(cell, dict) and cell.get('kind') == 'PLANT' and cell.get('crop') in ('WHEAT', 'CARROT')):
            ok.append((x, y))
    if len(ok) < n:
        return []
    chosen = [min(ok, key=lambda p: (_shp_dist(p, (4, 5)), p))]
    while len(chosen) < n:
        rest = [p for p in ok if p not in chosen]
        chosen.append(min(rest, key=lambda p: (min(_shp_dist(p, q) for q in chosen), _shp_dist(p, (4, 5)), p)))
    return chosen


def _shp_decide(state, obs, action, step):
    """Commit a purchase (once) when her rule calls for more sheep than the tape will deliver."""
    if state.get('committed') or state.get('declined_day') == step // 24:
        return action
    day, hour = step // 24, step % 24
    if day < _SHP_CFG.get('first_day', 9) or day > _SHP_CFG.get('last_day', 16):
        return action
    player = int(obs['player'])
    tape = _shp_route(player)
    if tape is None:
        return action
    if hour <= max(_shp_last_hire_hour(tape, day), 1) or hour > _SHP_CFG.get('latest_hour', 8):
        return action
    shops = list((obs.get('town') or {}).get('unlocked_shops') or [])
    target = 4 + sum(_SHP_LOOKUP.get(3 * (i + 1), 0) for i, s in enumerate(shops) if s == 'YARN_STORE')
    planned = state['tape_bought'] + _shp_tape_sheep(tape, step, 719)
    deficit = target - planned
    n = min(int(_SHP_CFG.get('max_sheep', 6)), deficit)
    if n < _SHP_CFG.get('min_deficit', 3):
        state['declined_day'] = day
        return action
    farm = obs['farms'][player]
    prices = (obs.get('market') or {}).get('prices') or {}
    if float(prices.get('WOOL', 0) or 0) < _SHP_CFG.get('min_wool_price', 120):
        state['declined_day'] = day
        _shp_count('declined_price')
        return action
    tiles = _shp_field_tiles(tape, farm, step, n)
    if not tiles:
        state['declined_day'] = day
        _shp_count('declined_tiles')
        return action
    hires_today = int(farm.get('hires_today', 0))
    parent_hires = sum(1 for o in (action.get('market') or []) if o and o[0] == 'HIRE')
    k = 2 if n > 3 else 1
    cost = 500 * n + sum(_SHP_FIB[min(15, hires_today + parent_hires + i)] for i in range(k)) \
        + n * (float(prices.get('WHEAT', 40) or 40) + 12)
    if float(farm['money']) < cost + _SHP_CFG.get('cash_margin', 2000):
        state['declined_day'] = day
        _shp_count('declined_cash')
        return action
    market = [list(o) for o in (action.get('market') or [])]
    if len(market) + k + 2 > 10:
        return action
    market += [['BUY_ANIMAL', 'SHEEP', n], ['BUY_PRODUCT', 'WHEAT', n]] + [['HIRE'] for _ in range(k)]
    state.update(committed=True, n=n, tiles=tiles, placed=set(), bought_day=day,
                 pending=dict(step=step, first=1 + len(farm['hands']) + parent_hires, k=k, setup=True))
    _shp_count('commitments')
    _shp_count('sheep_bought', n)
    _SHP_REPORT['decision'] = dict(day=day, target=target, planned=planned, n=n, tiles=tiles, shops=shops)
    return dict(action, market=market)


def _shp_daily_hire(state, obs, action, step):
    """Every later day: one or two hands plus the day's feed wheat, after the tape's last hire."""
    day, hour = step // 24, step % 24
    if not state.get('committed') or day <= state['bought_day'] or state.get('hired_day') == day:
        return action
    player = int(obs['player'])
    tape = _shp_route(player)
    if tape is None or hour <= max(_shp_last_hire_hour(tape, day), 0) or hour > 10:
        return action
    farm = obs['farms'][player]
    alive = [t for t in state['tiles'] if isinstance(farm['tiles'][t[1]][t[0]], dict) and farm['tiles'][t[1]][t[0]].get('animal') == 'SHEEP']
    pending = [t for t in state['tiles'] if t not in state['placed']]
    if not alive and not pending:
        state['hired_day'] = day
        return action
    k = 2 if len(alive) + len(pending) > 4 else 1
    market = [list(o) for o in (action.get('market') or [])]
    if len(market) + k + 1 > 10:
        return action
    parent_hires = sum(1 for o in market if o and o[0] == 'HIRE')
    feed = len(alive) + len(pending)
    market += [['BUY_PRODUCT', 'WHEAT', feed]] + [['HIRE'] for _ in range(k)]
    state['hired_day'] = day
    state['pending'] = dict(step=step, first=1 + len(farm['hands']) + parent_hires, k=k, setup=False)
    _shp_count('hand_days', k)
    return dict(action, market=market)


def _shp_confirm(state, obs, step):
    p = state.get('pending')
    if not p or p['step'] != step - 1:
        return
    state['pending'] = None
    farm = obs['farms'][int(obs['player'])]
    if len(farm['hands']) + 1 >= p['first'] + p['k']:
        hands = list(range(p['first'], p['first'] + p['k']))
        tiles = list(state['tiles'])
        chunks = [tiles[i::len(hands)] for i in range(len(hands))]
        state['workers'] = {h: dict(tiles=sorted(c, key=lambda t: (_shp_dist(t, (4, 5)), t)), loaded=False, day=step // 24)
                            for h, c in zip(hands, chunks) if c}
    else:
        _shp_count('hire_shortfalls')
        state['workers'] = {}


def _shp_work(state, obs, idx, role, step):
    farm = obs['farms'][int(obs['player'])]
    day, hour = step // 24, step % 24
    if role['day'] != day or idx - 1 >= len(farm['hands']):
        return None
    pos = tuple(farm['hands'][idx - 1])
    invs = obs['private'].get('inventories') or []
    inv = invs[idx] if idx < len(invs) else {}
    shed = obs['private'].get('shed') or {}
    home = _shp_home(pos)
    if not role['loaded']:
        if pos not in _SHP_SHED:
            return _shp_walk(pos, home)
        need_sheep = [t for t in role['tiles'] if t not in state['placed']]
        if need_sheep and int(inv.get('SHEEP', 0) or 0) < len(need_sheep) and int(shed.get('SHEEP', 0) or 0) > 0 and not role.get('got_sheep'):
            role['got_sheep'] = True
            return ['PICKUP', 'SHEEP', min(len(need_sheep), int(shed.get('SHEEP', 0)))]
        want = len(role['tiles'])
        if int(inv.get('WHEAT', 0) or 0) < want and int(shed.get('WHEAT', 0) or 0) > 0 and not role.get('got_wheat'):
            role['got_wheat'] = True
            return ['PICKUP', 'WHEAT', min(want, int(shed.get('WHEAT', 0)))]
        role['loaded'] = True
    # last day: bring the wool home before the final step
    cargo = sum(int(v or 0) for k_, v in inv.items() if k_ in ('WOOL', 'FERTILIZER'))
    if day == 29 and cargo and 24 - hour <= _shp_dist(pos, home) + 2:
        return _shp_walk(pos, home) or ['DROP']
    for tile in role['tiles']:
        x, y = tile
        cell = farm['tiles'][y][x]
        todo = None
        if isinstance(cell, dict) and cell.get('animal') == 'SHEEP':
            state['placed'].add(tile)
            if not cell.get('fed_today') and int(inv.get('WHEAT', 0) or 0) > 0:
                todo = ['FEED']
            elif not cell.get('cared_today'):
                todo = ['CARE']
            elif int(cell.get('yield_units', 0) or 0) > 0:
                todo = ['HARVEST']
            elif cell.get('fertilizer_available') and hour < 22:
                todo = ['COLLECT_FERTILIZER']
        elif tile not in state['placed'] and int(inv.get('SHEEP', 0) or 0) > 0:
            if cell is None:
                todo = ['BUILD_PASTURE']
            elif isinstance(cell, dict) and cell.get('kind') == 'PASTURE' and not cell.get('animal'):
                todo = ['PLACE', 'SHEEP']
            elif isinstance(cell, dict) and cell.get('kind') == 'PLANT':
                age = day - int(cell.get('planted_day', day))
                todo = ['HARVEST'] if (age >= 2 and int(cell.get('yield_units', 0) or 0) > 0) else ['DIG']
            elif isinstance(cell, dict) and cell.get('kind') == 'WEED':
                todo = ['DIG']
        if todo:
            if pos != tile:
                return _shp_walk(pos, tile)
            _shp_count('ops_' + todo[0].lower())
            return todo
    if day == 29 and cargo:
        return _shp_walk(pos, home) or ['DROP']
    return ['PASS']


def agent(observation, configuration=None):
    action = _SHP_PARENT(observation, configuration)
    try:
        if not _SHP_CFG.get('enabled'):
            return action
        step = int(observation['step'])
        player = int(observation['player'])
        state = _SHP_STATES.get(player)
        if state is None or step <= state.get('last', -1):
            state = _SHP_STATES[player] = {'last': -1, 'tape_bought': 0, 'workers': {}}
            _SHP_REPORT.clear()
        state['last'] = step
        for o in (action.get('market') or []):
            if len(o) >= 3 and o[0] == 'BUY_ANIMAL' and o[1] == 'SHEEP':
                state['tape_bought'] += int(o[2])
        _shp_confirm(state, observation, step)
        if state.get('workers'):
            farm = observation['farms'][player]
            n_units = 1 + len(farm['hands'])
            cmds = [list(action.get('farmer') or ['PASS'])] + [list(c or ['PASS']) for c in (action.get('hands') or [])]
            while len(cmds) < n_units:
                cmds.append(['PASS'])
            for idx, role in list(state['workers'].items()):
                if idx < n_units:
                    cmd = _shp_work(state, observation, idx, role, step)
                    if cmd is not None:
                        cmds[idx] = cmd
            action = dict(action, farmer=cmds[0], hands=cmds[1:n_units])
        action = _shp_decide(state, observation, action, step)
        action = _shp_daily_hire(state, observation, action, step)
    except Exception as exc:
        _shp_count('errors')
        _SHP_REPORT['last_error'] = repr(exc)[:200]
    _SHP_NUM.clear()
    for _src in (_MGT_REPORT, _SHP_REPORT):
        for _k, _v in _src.items():
            if isinstance(_v, (int, float)):
                _SHP_NUM[_k] = _v
    return action


agent.mgt_telemetry = _MGT_REPORT
agent.mgt_history = _MGT_HISTORY
agent.shp_telemetry = _SHP_REPORT
agent.sp_telemetry = _SHP_NUM

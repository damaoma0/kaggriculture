"""Own-state projection and verification using the checked-in engine mechanics.

Only the current public observation and our private inventory are read. Shops
are held through the next reveal, the rival makes no trades, and new weeds are
omitted. This is a feasibility scenario, not a guarantee about market prices.
"""
from collections import Counter
from copy import deepcopy
from cumulative_engine_profiles import ENGINE as _CP_ENGINE


def physical_step(obs, action):
    """Return predicted own physical state before market/day-end processing."""
    farm = deepcopy(obs['farms'][obs['player']])
    private = deepcopy(obs['private'])
    commands = [action.get('farmer', ['PASS'])] + action.get('hands', [])
    demand = Counter(c[1] for c in commands if c and c[0] == 'PLANT')
    blocked = {p for p, n in demand.items() if n > private['seeds'].get(p, 0)}
    changed, output, overflow = [], Counter(), 0
    for u, cmd in enumerate(commands[:len(farm['hands']) + 1]):
        if cmd and cmd[0] == 'PLANT' and cmd[1] in blocked: cmd = ['PASS']
        pos = _CP_ENGINE._farmer_position(farm, u)
        before_tile = deepcopy(farm['tiles'][pos[1]][pos[0]])
        inv = dict(private['inventories'][u])
        if cmd and cmd[0] == 'DROP' and tuple(pos) in _CP_ENGINE._shed_access_tiles(len(farm['tiles'])):
            overflow += max(0, sum(inv.values()) + sum(private['shed'].values()) - 100)
        _CP_ENGINE._apply_unit_action(farm, private, u, cmd, len(farm['tiles']), obs['day'], 24, 100)
        after_tile = farm['tiles'][pos[1]][pos[0]]
        changed.append(before_tile != after_tile or inv != private['inventories'][u])
        if cmd and cmd[0] in ('HARVEST', 'COLLECT_FERTILIZER'):
            output.update({p: n - inv.get(p, 0) for p, n in private['inventories'][u].items() if n > inv.get(p, 0)})
    return farm, private, changed, dict(output), overflow


def sale_action(obs, state, action):
    """Sell actual available goods after today's physical commands, keeping inputs."""
    farm, private, _, _, _ = physical_step(obs, action)
    rel = obs['day'] - state['start_day']
    need = Counter()
    for job in state['jobs']:
        if job['day'] != rel or job['id'] in state['issued']: continue
        op = job['cmd'][0]
        if op == 'FEED': need['WHEAT'] += 1
        if op == 'FERTILIZE': need['FERTILIZER'] += 1
        if op == 'PLACE' and job['cmd'][1] in _CP_ENGINE.ANIMALS: need[job['cmd'][1]] += 1
    # Inputs already carried by workers do not need reserving twice in the shed.
    for inv in private['inventories']:
        for p, n in inv.items(): need[p] = max(0, need[p] - n)
    orders = list(action.get('market', []))
    sales = []
    for p in sorted(_CP_ENGINE.PRODUCTS, key=lambda p: (-obs['market']['prices'][p], p)):
        n = max(0, private['shed'].get(p, 0) - need[p])
        if n and len(sales) + len(orders) < 10: sales.append(['SELL', p, n])
    result = dict(action); result['market'] = sales + orders
    return result


def project_step(obs, action):
    """One deterministic, own-farm step, without rival trades or random weeds."""
    result = deepcopy(obs)
    farm, private, changes, output, overflow = physical_step(obs, action)
    result['farms'][obs['player']] = farm
    result['private'] = private
    market = result['market']
    failures = []
    for order in action.get('market', [])[:10]:
        op = order[0]
        if op == 'HIRE':
            before = len(farm['hands'])
            _CP_ENGINE._do_hire(farm, private, len(farm['tiles']))
            if len(farm['hands']) == before: failures.append('hire_shortfall')
            continue
        if op not in ('SELL', 'BUY_PRODUCT', 'BUY_ANIMAL', 'BUY_SEED'):
            failures.append('unsupported_order'); continue
        p, count = order[1:3]
        for _ in range(count):
            if op in ('SELL', 'BUY_PRODUCT'):
                price = _CP_ENGINE.market_price(p, market['inventory'][p] - (op == 'BUY_PRODUCT'), market.get('params'))
            elif op == 'BUY_ANIMAL': price = _CP_ENGINE.ANIMALS[p]['cost']
            else: price = _CP_ENGINE.CROPS[p]['seed']
            if not _CP_ENGINE._commit_unit(op, p, price, farm, private, market, 100):
                if op != 'SELL': failures.append('purchase_shortfall')
                break
    step, day = obs['step'], obs['day']
    if step % 4 == 0:
        for shop in obs['town']['unlocked_shops']:
            products = _CP_ENGINE.SHOPS[shop]
            for p in products: market['inventory'][p] -= 2 if len(products) == 1 else 1
    if step % 24 == 0:
        for p in _CP_ENGINE.TOWN_CENTER_PRODUCTS: market['inventory'][p] -= 1
    _CP_ENGINE._refresh_prices(market)
    _CP_ENGINE._decay_plants(farm, step)
    if (step + 1) % 24 == 0:
        _CP_ENGINE._daily_refresh_plants(farm, day, 24)
        _CP_ENGINE._daily_refresh_animals(farm, day)
        carried = sum(sum(i.values()) for i in private['inventories'])
        overflow += max(0, carried + sum(private['shed'].values()) - 100)
        _CP_ENGINE._drop_inventories_to_shed(private, 100)
        farm['farmer'] = list(_CP_ENGINE._default_spawn(len(farm['tiles'])))
        farm['hands'] = []; farm['hires_today'] = 0; private['inventories'] = [{}]
    result['step'] = step + 1
    result['day'], result['hour'] = divmod(step + 1, 24)
    return result, {'failures': failures, 'changes': changes, 'output': output, 'overflow': overflow}


def check_window(obs, node, executor):
    """Reject the whole window before activation if any declared day fails."""
    projected = deepcopy(obs)
    state = executor.segment_executor_start(projected, node)
    if not state.get('ok'): return {'ok': False, 'failure': state['failure']}
    output, actions = Counter(), []
    for step in range(obs['step'], min(obs['step'] + 24 * int(node.get('span', 3)), 719)):
        action = executor.segment_executor_action(projected, state)
        if state.get('failure'): return {'ok': False, 'failure': state['failure'], 'step': step}
        action = sale_action(projected, state, action)
        rel, hour = projected['day'] - state['start_day'], projected['hour']
        scheduled = state['plans'].get(rel, {}).get('scheduled', {})
        projected, report = project_step(projected, action)
        if report['failures'] or report['overflow']:
            return {'ok': False, 'failure': {'reason': 'projection_failed', **report}, 'step': step}
        commands = [action.get('farmer', ['PASS'])] + action.get('hands', [])
        for u, cmd in enumerate(commands):
            if (u, hour) not in scheduled or cmd[0] not in ('PLANT', 'PLACE', 'HARVEST', 'BUILD_COOP', 'BUILD_PASTURE'):
                continue
            if u >= len(report['changes']) or not report['changes'][u]:
                return {'ok': False, 'failure': {'reason': 'unfulfilled_job', 'command': cmd, 'unit': u}, 'step': step}
        output.update(report['output']); actions.append(action)
    return {'ok': True, 'output': dict(output), 'end_observation': projected, 'end_farm': projected['farms'][obs['player']],
            'end_private': projected['private'], 'actions': actions}

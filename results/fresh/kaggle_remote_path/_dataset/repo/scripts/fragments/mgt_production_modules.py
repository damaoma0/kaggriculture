# Conservative production-module overlay for frozen agents/mgt_m1.py.
#
# It only substitutes a *next-step* native WHEAT PLANT.  The replacement is
# committed after the base agent has selected its route, pins that route until
# the carrot is clear, and uses only the native farmer/hand visits proved by
# the tape calendar.  There are deliberately no new moves, hands or FERTILIZE
# commands.  This is intentionally much narrower than mg_slots.py.
_MPM_CFG = __MPM_CFG__
_MPM_STATES = {}
_MPM_REPORT = {'events': [], 'committed': 0, 'errors': 0, 'mismatches': 0,
               'displaced_wheat': 0, 'unused_seed': 0, 'router_pins': 0,
               'movement_mutations': 0, 'hire_mutations': 0}
_MPM_PARENT = agent
_MPM_BASE_ROUTER = _MGT_IMPL.chassis.router
_MPM_MOVES = _TC_MOVES


def _mpm_note(kind, **data):
    _MPM_REPORT[kind] = _MPM_REPORT.get(kind, 0) + 1
    row = {'kind': kind}
    row.update(data)
    events = _MPM_REPORT['events']
    events.append(row)
    if len(events) > 80:
        del events[:-80]


def _mpm_state(player, step):
    st = _MPM_STATES.get(player)
    if st is None or step <= st.get('last', -1):
        _MPM_REPORT.clear()
        _MPM_REPORT.update({'events': [], 'committed': 0, 'errors': 0, 'mismatches': 0,
                            'displaced_wheat': 0, 'unused_seed': 0, 'router_pins': 0,
                            'movement_mutations': 0, 'hire_mutations': 0})
        st = {'last': -1, 'sim': {}, 'sim_route': None, 'programs': {}, 'reserve': 0,
              'credit': 0, 'carry': {}, 'pending': {}, 'prev_inv': {}, 'prev_shed': None, 'cycles': 0, 'active': {}}
        _MPM_STATES[player] = st
    st['last'] = step
    _MPM_REPORT['active'] = st['active']
    return st


def _mpm_tape(route, t):
    tape = _MGT_IMPL.chassis.routes.get(route) or ()
    return tape[t] if 0 <= t < len(tape) and isinstance(tape[t], dict) else {}


def _mpm_own_hands(player):
    # mgt_m1's sheep layer may insert its own hands.  Calendar unit indices are
    # tape indices, so remove those hands before simulating and map them back
    # when rewriting the returned full action.
    try:
        return set((_SHP_STATES.get(player) or {}).get('own') or ())
    except Exception:
        return set()


def _mpm_mapping(obs, player):
    own = _mpm_own_hands(player)
    actual = [0] + [i for i in range(1, len(obs['farms'][player].get('hands') or []) + 1) if i not in own]
    return actual


def _mpm_calendar(st, obs, player, route, step):
    mapping = _mpm_mapping(obs, player)
    farm = obs['farms'][player]
    allpos = [tuple(farm['farmer'])] + [tuple(p) for p in (farm.get('hands') or [])]
    pos = [allpos[i] for i in mapping if i < len(allpos)]
    if not pos:
        return False
    st['sim'] = _tc_simulate(lambda t: _mpm_tape(route, t), step, 718, pos)
    st['sim_route'], st['sim_from'], st['mapping'] = route, step, mapping
    _mpm_note('calendar_build', route=route, step=step)
    return True


def _mpm_usable(cmd):
    return bool(cmd) and cmd[0] in ('PASS', 'PLANT', 'WATER', 'HARVEST', 'DIG', 'FERTILIZE')


def _mpm_visits(st, tile, lo, hi):
    ans = {}
    for t in range(lo, min(719, hi)):
        for u, (x, y, cmd) in enumerate(st['sim'].get(t) or ()):
            if (x, y) == tile and _mpm_usable(cmd):
                ans.setdefault(t // 24, []).append((t, u))
    return ans


def _mpm_plan(st, t0, unit, tile):
    """Reserve WATER at ages 0 and 2, then HARVEST at age 2 or 3."""
    day = t0 // 24
    if day < int(_MPM_CFG.get('day_lo', 12)) or day > int(_MPM_CFG.get('day_hi', 21)):
        return None, 'outside_window'
    if day + 3 >= 30:
        return None, 'season_end'
    v = _mpm_visits(st, tile, t0 + 1, (day + 4) * 24)
    jobs = None
    age2 = v.get(day + 2) or ()
    later = [q for q in age2 if q[0] > age2[0][0] and q[0] % 24 < 23] if age2 else []
    if v.get(day) and later:
        a0, a2 = v[day][0], v[day + 2]
        jobs, harvest_day = {a0[0]: (a0[1], ['WATER']), a2[0][0]: (a2[0][1], ['WATER']),
                             later[0][0]: (later[0][1], ['HARVEST'])}, day + 2
    elif v.get(day) and v.get(day + 2) and any(t % 24 < 23 for t, u in (v.get(day + 3) or ())):
        a0, a2 = v[day][0], v[day + 2][0]
        ah = next(q for q in v[day + 3] if q[0] % 24 < 23)
        jobs, harvest_day = {a0[0]: (a0[1], ['WATER']), a2[0]: (a2[1], ['WATER']),
                             ah[0]: (ah[1], ['HARVEST'])}, day + 3
    if jobs is None:
        return None, 'care_proof'
    # Never overwrite another planned crop while ours is alive.  The selected
    # WHEAT planting itself is the one allowed exception.
    for t in range(t0 + 1, (day + 4) * 24):
        for x, y, cmd in st['sim'].get(t) or ():
            if (x, y) == tile and cmd and cmd[0] == 'PLANT':
                return None, 'future_plant'
    return {'harvest_day': harvest_day, 'expected': 2, 'visits': v, 'jobs': jobs}, None


def _mpm_visible_value(obs, wheat_units):
    shops = list((obs.get('town') or {}).get('unlocked_shops') or ())
    carrot_demand = sum(1 for s in shops if s in ('PET_CAFE', 'FARMERS_MARKET'))
    if not carrot_demand:
        return False, 'no_visible_carrot_demand'
    prices = (obs.get('market') or {}).get('prices') or {}
    carrot = float(prices.get('CARROT', 0) or 0)
    wheat = float(prices.get('WHEAT', 0) or 0)
    # Demand is visible now; prices are deliberately only current snapshots.
    return 2 * carrot >= 20 + max(6, wheat_units) * wheat, 'value_gate'


def _mpm_pin_router(obs, step, native):
    try:
        player = int(obs['player'])
        st = _MPM_STATES.get(player)
        live = [p for p in (st or {}).get('programs', {}).values() if step < p.get('pin_end', p.get('end', 0))]
        if live:
            route = live[0]['route']
            native['route'] = route
            _MPM_REPORT['router_pins'] = _MPM_REPORT.get('router_pins', 0) + 1
            return route
    except Exception as exc:
        _MPM_REPORT['router_pin_errors'] = _MPM_REPORT.get('router_pin_errors', 0) + 1
        _MPM_REPORT['last_error'] = repr(exc)[:180]
    return _MPM_BASE_ROUTER(obs, step, native)


_MGT_IMPL.chassis.router = _mpm_pin_router


def _mpm_reconcile(st, obs, player):
    invs = obs['private'].get('inventories') or ()
    mapping = st.get('mapping') or _mpm_mapping(obs, player)
    known = set(mapping) | set(st['prev_inv']) | set(st['carry']) | set(st['pending'])
    shed_now = int((obs['private'].get('shed') or {}).get('CARROT', 0) or 0)
    shed_gain = max(0, shed_now - int(st['prev_shed'] if st['prev_shed'] is not None else shed_now))
    for actual in known:
        now = int((invs[actual] if actual < len(invs) else {}).get('CARROT', 0) or 0)
        old = int(st['prev_inv'].get(actual, now))
        # A harvested unit is not credited merely because HARVEST was issued:
        # the next observation must show it in the actual worker inventory.
        expected = int(st['pending'].get(actual, 0))
        if expected and now > old:
            got = min(expected, now - old)
            st['pending'][actual] = expected - got
            st['carry'][actual] = st['carry'].get(actual, 0) + got
            for p in st['programs'].values():
                if p.get('harvest_actor') == actual and p.get('awaiting', 0):
                    take = min(got, p['awaiting'])
                    p['actual'] += take
                    p['awaiting'] -= take
            _mpm_note('harvest_confirmed', actor=actual, units=got)
        elif expected and now <= old:
            st['pending'][actual] = 0
            _MPM_REPORT['mismatches'] += 1
            _mpm_note('harvest_missing', actor=actual, expected=expected)
        # Only a tape worker which harvested our program can create sale credit.
        held = int(st['carry'].get(actual, 0))
        if held and now < old:
            removed = min(held, old - now)
            moved = min(removed, shed_gain)
            st['carry'][actual] = held - removed
            st['credit'] += moved
            shed_gain -= moved
            if moved:
                _mpm_note('delivered', actor=actual, units=moved)
            if removed > moved:
                _mpm_note('delivery_uncredited', actor=actual, units=removed-moved)
        st['prev_inv'][actual] = now
    st['prev_shed'] = shed_now


def _mpm_commit(st, obs, player, route, step):
    if _MPM_CFG.get('mode') == 'off' or st['cycles'] >= int(_MPM_CFG.get('max_cycles', 2)):
        return
    if any(step < p.get('pin_end', p['end']) for p in st['programs'].values()):
        return
    # The native next action, not a guessed future route.  This permits a seed
    # top-up on this step and pins starting immediately on the following one.
    if step % 24 >= 22:  # leave a normal observation after the seed order
        return
    t0 = step + 1
    row = st['sim'].get(t0) or ()
    for u, (x, y, cmd) in enumerate(row):
        if not (cmd and cmd[0] == 'PLANT' and len(cmd) > 1 and cmd[1] == 'WHEAT'):
            continue
        tile = (x, y)
        if tile in st['programs']:
            continue
        plan, why = _mpm_plan(st, t0, u, tile)
        if not plan:
            _mpm_note('rejected_' + why, tile=tile, step=t0)
            continue
        if _MPM_CFG.get('mode') == 'value':
            ok, why = _mpm_visible_value(obs, 6)
            if not ok:
                _mpm_note('rejected_' + why, tile=tile, step=t0)
                continue
        # Budget guard uses the known seed price plus a cash buffer.  The order
        # cap is checked again before appending in _mpm_seed_topup.
        price = float(((obs.get('market') or {}).get('prices') or {}).get('CARROT', 0) or 0)
        money = float(obs['farms'][player].get('money', 0) or 0)
        if _MPM_CFG.get('mode') != 'pin_only' and money < 20 + float(_MPM_CFG.get('cash_margin', 100)):
            _mpm_note('rejected_budget', tile=tile, step=t0, money=money, price=price)
            continue
        # Wheat's native one-shot lifetime reaches age 4.  Keep the route pinned
        # until that original crop would have cleared, not merely our harvest.
        p = dict(plan, tile=tile, t0=t0, unit=u, route=route, end=(plan['harvest_day'] + 1) * 24,
                 pin_end=(t0 // 24 + 5) * 24,
                 planted=False, actual=0, phase='reserved', source='native_wheat')
        st['programs'][tile] = p
        st['active'][str(tile)] = {'start': t0, 'tile': tile, 'phase': 'reserved', 'end': p['end'],
                                   'expected': p['expected'], 'actual': 0, 'source': 'native_wheat', 'route': route,
                                   'original_wheat_release': p['pin_end']}
        st['cycles'] += 1
        _MPM_REPORT['displaced_wheat'] += 1
        _mpm_note('committed', tile=tile, date=t0 // 24, expected_harvest=p['expected'], route=route,
                  displaced_wheat_plantings=1)
        return


def _mpm_seed_topup(st, action, step):
    if _MPM_CFG.get('mode') == 'pin_only':
        return action
    pending = [p for p in st['programs'].values() if p['t0'] == step + 1 and not p['planted']]
    if not pending or st['reserve'] >= len(pending):
        return action
    market = [list(o) for o in (action.get('market') or ())]
    if len(market) >= 10:
        for p in pending:
            _mpm_note('rejected_order_cap', tile=p['tile'], step=p['t0'])
            p['end'] = p['pin_end'] = step
            p['phase'] = 'aborted_order_cap'
        return action
    q = len(pending) - st['reserve']
    market.append(['BUY_SEED', 'CARROT', q])
    st['reserve'] += q
    _MPM_REPORT['seed_buys'] = _MPM_REPORT.get('seed_buys', 0) + q
    return dict(action, market=market)


def _mpm_rewrite(st, obs, action, player, step):
    if _MPM_CFG.get('mode') == 'pin_only':
        return action
    farm = obs['farms'][player]
    mapping = _mpm_mapping(obs, player)  # sheep hires can change this daily
    st['mapping'] = mapping
    cmds = [list(action.get('farmer') or ['PASS'])] + [list(c or ['PASS']) for c in (action.get('hands') or ())]
    seeds = int((obs['private'].get('seeds') or {}).get('CARROT', 0) or 0)
    for tile, p in list(st['programs'].items()):
        if not (p['t0'] <= step < p['end']):
            continue
        row = st['sim'].get(step) or ()
        for u, (x, y, native) in enumerate(row):
            if (x, y) != tile or u >= len(mapping):
                continue
            actual = mapping[u]
            if actual >= len(cmds) or not _mpm_usable(native):
                continue
            # Calendar positions are a promise, not an authority.  If a tape
            # hire or sheep hand changed the live mapping, abandon this tile.
            allpos = [tuple(farm['farmer'])] + [tuple(v) for v in (farm.get('hands') or ())]
            if actual >= len(allpos) or allpos[actual] != (x, y):
                p['end'] = p['pin_end'] = step
                p['phase'] = 'aborted_position_mismatch'
                _MPM_REPORT['mismatches'] += 1
                _mpm_note('position_mismatch', tile=tile, unit=u, actor=actual, step=step)
                continue
            if not _mpm_usable(cmds[actual]):
                p['end'] = p['pin_end'] = step
                p['phase'] = 'aborted_command_conflict'
                _MPM_REPORT['mismatches'] += 1
                _mpm_note('command_conflict', tile=tile, step=step, command=cmds[actual])
                continue
            cell = farm['tiles'][y][x]
            new = None
            if p['planted'] is False:
                if step == p['t0']:
                    # Engine resolves all unit PLANTs before market orders.  Do
                    # not borrow a seed from an unrelated native CARROT plant.
                    native_carrots = sum(1 for c in cmds if c and c[0] == 'PLANT' and len(c) > 1 and c[1] == 'CARROT')
                    if cell is None and seeds >= native_carrots + 1:
                        new, seeds, p['planted'], p['phase'] = ['PLANT', 'CARROT'], seeds - 1, 'requested', 'plant_requested'
                        st['reserve'] = max(0, st['reserve'] - 1)
                        _mpm_note('plant_requested', tile=tile, date=step // 24)
                    else:
                        p['end'] = p['pin_end'] = step
                        p['phase'] = 'aborted_plant'
                        _MPM_REPORT['unused_seed'] += st['reserve']
                        _mpm_note('plant_aborted', tile=tile, reason='occupied_or_no_seed')
                if new is not None:
                    cmds[actual] = new
                continue
            ours = isinstance(cell, dict) and cell.get('kind') == 'PLANT' and cell.get('crop') == 'CARROT'
            if not ours:
                if step > p['t0']:
                    p['end'] = step
                    p['phase'] = 'closed'
                    if p['actual'] != p['expected']:
                        _MPM_REPORT['mismatches'] += 1
                    _mpm_note('closed', tile=tile, actual=p['actual'], expected=p['expected'])
                continue
            if p['planted'] == 'requested':
                p['planted'], p['phase'] = True, 'planted_confirmed'
                _mpm_note('plant_confirmed', tile=tile, date=step // 24)
            age = step // 24 - int(cell.get('planted_day', step // 24) or step // 24)
            # Own every usable visit while the carrot is alive.  In particular
            # do not let the replaced tape's FERTILIZE or early HARVEST leak
            # through and destroy the crop before the selected age-3 harvest.
            new = ['PASS']
            job = p.get('jobs', {}).get(step)
            if job is not None and job[0] == u:
                new, p['phase'] = list(job[1]), ('care' if job[1][0] == 'WATER' else 'harvest')
            if new[0] == 'HARVEST':
                units = int(cell.get('yield_units', 0) or 0)
                p['awaiting'] = p.get('awaiting', 0) + units
                p['harvest_actor'] = actual
                st['pending'][actual] = st['pending'].get(actual, 0) + units
                _mpm_note('harvest_issued', tile=tile, units=units)
            cmds[actual] = new
        active = st['active'].get(str(tile))
        if active:
            active['phase'], active['actual'] = p['phase'], p['actual']
    return dict(action, farmer=cmds[0], hands=cmds[1:])


def _mpm_sell(st, obs, action):
    if _MPM_CFG.get('mode') == 'pin_only' or st['credit'] <= 0:
        return action
    market = [list(o) for o in (action.get('market') or ())]
    # Native carrot sales remain ahead of ours.  We only sell a confirmed,
    # delivered module credit that survives those pre-existing orders.
    planned = sum(int(o[2]) for o in market if len(o) > 2 and o[0] == 'SELL' and o[1] == 'CARROT')
    shed = int((obs['private'].get('shed') or {}).get('CARROT', 0) or 0)
    native_use = min(st['credit'], planned, shed)
    if native_use:
        st['credit'] -= native_use
        _mpm_note('credit_consumed_by_native_sale', units=native_use)
    q = min(st['credit'], max(0, shed - planned))
    if q <= 0 or len(market) >= 10:
        return action
    market.append(['SELL', 'CARROT', q])
    st['credit'] -= q
    _MPM_REPORT['sales'] = _MPM_REPORT.get('sales', 0) + q
    _mpm_note('sale', units=q)
    return dict(action, market=market)


def agent(observation, configuration=None):
    action = _MPM_PARENT(observation, configuration)
    try:
        step, player = int(observation['step']), int(observation['player'])
        st = _mpm_state(player, step)
        _mpm_reconcile(st, observation, player)
        if _MPM_CFG.get('mode') == 'off' or step < 12 * 24 or step >= 718:
            return action
        native = _MGT_IMPL.chassis.players.get(player) or {}
        route = native.get('route')
        if route is None:
            _mpm_note('rejected_no_route', step=step)
            return action
        if st.get('sim_route') != route or step not in st.get('sim', {}) or st.get('mapping') != _mpm_mapping(observation, player):
            _mpm_calendar(st, observation, player, route, step)
        _mpm_commit(st, observation, player, route, step)
        before = action
        action = _mpm_seed_topup(st, action, step)
        action = _mpm_rewrite(st, observation, action, player, step)
        action = _mpm_sell(st, observation, action)
        for tile, p in st['programs'].items():
            st['active'][str(tile)].update(phase=p['phase'], actual=p['actual'], end=p['end'])
        # Hard regression telemetry: the module is forbidden from changing
        # movement or HIRE orders in this exact observation/action pair.
        def _moves(a):
            return [c for c in [a.get('farmer') or ['PASS']] + list(a.get('hands') or ()) if c and c[0] in _MPM_MOVES]
        def _hires(a):
            return [o for o in (a.get('market') or ()) if o and o[0] == 'HIRE']
        if _moves(before) != _moves(action):
            _MPM_REPORT['movement_mutations'] += 1
            _mpm_note('movement_mutation')
        if _hires(before) != _hires(action):
            _MPM_REPORT['hire_mutations'] += 1
            _mpm_note('hire_mutation')
    except Exception as exc:
        _MPM_REPORT['errors'] = _MPM_REPORT.get('errors', 0) + 1
        _MPM_REPORT['last_error'] = repr(exc)[:240]
    return action


agent.mgt_pm_telemetry = _MPM_REPORT
agent.mgt_telemetry = _MGT_REPORT


def mgt_pm_kaggle_entry(observation, configuration=None):
    return agent(observation, configuration)


mgt_pm_kaggle_entry.mgt_pm_telemetry = _MPM_REPORT

# Experimental complete TOMATO lifecycles on native WHEAT visits.
_ROT_MODE = __ROT_MODE__
_ROT_PARENT = agent
_ROT_ROUTER = _MGT_IMPL.chassis.router
_ROT_STATES = {}
_ROT_REPORT = {'mode': _ROT_MODE, 'events': [], 'committed': 0, 'errors': 0}


def _rot_note(kind, **values):
    _ROT_REPORT[kind] = _ROT_REPORT.get(kind, 0) + 1
    if not kind.startswith('reject_'):
        _ROT_REPORT['events'].append(dict(kind=kind, **values))


def _rot_mapping(obs, player):
    own = set((_SHP_STATES.get(player) or {}).get('own') or ())
    return [0] + [i for i in range(1, len(obs['farms'][player].get('hands') or []) + 1) if i not in own]


def _rot_usable(cmd):
    return bool(cmd) and cmd[0] in ('PASS', 'PLANT', 'WATER', 'HARVEST', 'DIG', 'FERTILIZE')


def _rot_pin(obs, step, state):
    st = _ROT_STATES.get(int(obs['player'])) or {}
    live = [p for p in st.get('programs', []) if p['start'] <= step <= p['end']]
    if live:
        state['route'] = live[0]['route']
        return state['route']
    return _ROT_ROUTER(obs, step, state)


_MGT_IMPL.chassis.router = _rot_pin


def _rot_plan(sim, start, unit, tile):
    day = start // 24
    visits = []
    for t in range(start + 1, min(719, (day + 13) * 24)):
        for u, (x, y, cmd) in enumerate(sim.get(t, ())):
            if (x, y) == tile and _rot_usable(cmd):
                visits.append((t, u))
    jobs = {start: (unit, ['PLANT', 'TOMATO'])}
    # The engine starts seedlings with consecutive_unwatered=1, so the
    # planting day must have a water visit even when tomorrow is available.
    last_water = day - 2
    # Water on every available day. Prove that no pair of dry days occurs.
    for d in range(day, day + 11):
        available = [(t, u) for t, u in visits if t // 24 == d]
        if available:
            t, u = available[0]
            jobs[t] = (u, ['WATER'])
            last_water = d
        if d - last_water >= 2:
            return None
    harvest = next(((t, u) for t, u in visits if t // 24 == day + 11 and t % 24 < 23), None)
    if harvest is None:
        return None
    cleanup = next(((t, u) for t, u in visits if t > harvest[0]), None)
    if cleanup is None:
        return None
    jobs[harvest[0]] = (harvest[1], ['HARVEST'])
    jobs[cleanup[0]] = (cleanup[1], ['DIG'])
    return {'start': start, 'end': cleanup[0], 'tile': tile, 'jobs': jobs,
            'planted': False, 'actual': 0, 'harvest_step': harvest[0]}


def _rot_reconcile(st, obs):
    invs = obs['private'].get('inventories') or ()
    shed = int((obs['private'].get('shed') or {}).get('TOMATO', 0))
    gain = max(0, shed - st.get('shed', shed))
    for u in set(st['old_inv']) | set(st['pending']) | set(st['carry']):
        now = int((invs[u] if u < len(invs) else {}).get('TOMATO', 0))
        old = st['old_inv'].get(u, now)
        expected = st['pending'].pop(u, 0)
        if expected:
            got = min(expected, max(0, now - old))
            st['carry'][u] = st['carry'].get(u, 0) + got
            _rot_note('harvest_confirmed' if got == expected else 'harvest_shortfall', units=got, expected=expected)
        carried = st['carry'].get(u, 0)
        if carried and old > now:
            removed = min(carried, old - now)
            moved = min(removed, gain)
            st['carry'][u] -= removed
            st['credit'] += moved
            gain -= moved
            _rot_note('delivered', units=moved, lost=removed-moved)
    st['old_inv'] = {u: int(inv.get('TOMATO', 0)) for u, inv in enumerate(invs)}
    st['shed'] = shed


def _rot_apply(obs, action):
    step, player = int(obs['step']), int(obs['player'])
    st = _ROT_STATES.get(player)
    if st is None or step <= st['last']:
        st = {'last': -1, 'programs': [], 'sim': {}, 'route': None,
              'old_inv': {}, 'pending': {}, 'carry': {}, 'credit': 0}
        _ROT_STATES[player] = st
    st['last'] = step
    _rot_reconcile(st, obs)
    if step < 12 * 24:
        return action
    farm = obs['farms'][player]
    route = (_MGT_IMPL.chassis.players.get(player) or {}).get('route')
    mapping = _rot_mapping(obs, player)
    allpos = [tuple(farm['farmer'])] + [tuple(v) for v in farm.get('hands') or []]
    if route is None:
        return action
    if st['route'] != route or step not in st['sim'] or step % 24 == 0 or mapping != st.get('mapping'):
        tape = _MGT_IMPL.chassis.routes[route]
        st['sim'] = _tc_simulate(lambda t: tape[t] if t < len(tape) else {}, step, 718, [allpos[i] for i in mapping])
        st['route'], st['mapping'] = route, mapping
    market = [list(o) for o in action.get('market') or []]
    if len(st['programs']) < 2 and 12 <= (step + 1) // 24 <= 18 and step % 24 < 22:
        for u, (x, y, cmd) in enumerate(st['sim'].get(step + 1, ())):
            if cmd != ['PLANT', 'WHEAT'] or any(p['tile'] == (x, y) for p in st['programs']):
                continue
            if float(farm.get('money', 0)) < 550 or len(market) >= 10:
                _rot_note('reject_budget')
                continue
            p = _rot_plan(st['sim'], step + 1, u, (x, y))
            if p is None:
                _rot_note('reject_calendar')
                continue
            p['route'] = route
            st['programs'].append(p)
            _rot_note('committed', tile=(x, y), start=p['start'], end=p['end'], route=route)
            if _ROT_MODE == 'rotate':
                market.append(['BUY_SEED', 'TOMATO', 1])
            break
    cmds = [list(action.get('farmer') or ['PASS'])] + [list(c or ['PASS']) for c in action.get('hands') or []]
    if _ROT_MODE == 'rotate':
        for p in st['programs']:
            if not p['start'] <= step <= p['end']:
                continue
            x, y = p['tile']
            cell = farm['tiles'][y][x]
            if step > p['start'] and not p['planted']:
                if isinstance(cell, dict) and cell.get('crop') == 'TOMATO' and cell.get('planted_day') == p['start'] // 24:
                    p['planted'] = True
                    _rot_note('plant_confirmed', tile=p['tile'])
                else:
                    p['end'] = step - 1
                    _rot_note('plant_failed', tile=p['tile'])
                    continue
            for u, (vx, vy, native) in enumerate(st['sim'].get(step, ())):
                if (vx, vy) != (x, y) or not _rot_usable(native):
                    continue
                actual = mapping[u] if u < len(mapping) else -1
                if actual < 0 or actual >= len(cmds) or allpos[actual] != (x, y) or not _rot_usable(cmds[actual]):
                    p['end'] = step - 1
                    _rot_note('position_or_command_conflict', tile=p['tile'], step=step)
                    break
                job = p['jobs'].get(step)
                new = list(job[1]) if job and job[0] == u else ['PASS']
                if new[0] == 'PLANT':
                    other = sum(c == ['PLANT', 'TOMATO'] for c in cmds)
                    if cell is not None or int((obs['private'].get('seeds') or {}).get('TOMATO', 0)) <= other:
                        p['end'] = step - 1
                        _rot_note('plant_unavailable', tile=p['tile'])
                        break
                if new[0] == 'HARVEST':
                    amount = int((cell or {}).get('yield_units', 0))
                    st['pending'][actual] = st['pending'].get(actual, 0) + amount
                    _rot_note('harvest_requested', tile=p['tile'], units=amount)
                cmds[actual] = new
        # Sell only tracked harvests that actually reached the shed.
        planned = sum(int(o[2]) for o in market if len(o) > 2 and o[:2] == ['SELL', 'TOMATO'])
        shed = int((obs['private'].get('shed') or {}).get('TOMATO', 0))
        st['credit'] -= min(st['credit'], planned, shed)
        q = min(st['credit'], max(0, shed - planned))
        if q and len(market) < 10:
            market.append(['SELL', 'TOMATO', q])
            st['credit'] -= q
            _rot_note('sold', units=q)
    return dict(action, farmer=cmds[0], hands=cmds[1:], market=market)


def agent(observation, configuration=None):
    original = _ROT_PARENT(observation, configuration)
    try:
        return _rot_apply(observation, original)
    except Exception as exc:
        _rot_note('errors', error=repr(exc))
        return original


def rotation_calendar_entry(observation, configuration=None):
    return agent(observation, configuration)

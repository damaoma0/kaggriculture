# A registered, local sequence variant. Inserted before the Kaggle entry point.
# This changes one worker's four-command prefix on one named donor tape.
_TV_SPEC = __TAPE_VARIANT_SPEC__
_TV_REPORT = {'variant': _TV_SPEC['id'], 'decisions': []}
_TV_ROUTER_PARENT = _MGT_IMPL.chassis.router
_TV_ROUTE_ID = next((i for i, t in enumerate(_MGT_TAPES)
                     if t['ep'] == _TV_SPEC['base_tape_episode']), None)
_TV_ORIGINAL = list(_MGT_ROUTES[_TV_ROUTE_ID]) if _TV_ROUTE_ID is not None else None


def _tv_router(observation, step, state):
    if step == 0:
        _TV_REPORT['decisions'] = []
        if _TV_ROUTE_ID is not None:
            _MGT_ROUTES[_TV_ROUTE_ID] = list(_TV_ORIGINAL)
            _MGT_IMPL.chassis.routes[_TV_ROUTE_ID] = _MGT_ROUTES[_TV_ROUTE_ID]
    route = _TV_ROUTER_PARENT(observation, step, state)
    day = step // 24
    if step % 24 or route != _TV_ROUTE_ID or str(day) not in _TV_SPEC['days']:
        return route
    spec = _TV_SPEC['days'][str(day)]
    farm = observation['farms'][int(observation['player'])]
    cow = farm['tiles'][4][4]
    sheep = farm['tiles'][4][3]
    prices = (observation.get('market') or {}).get('prices') or {}
    milk, wool = float(prices.get('MILK', 0)), float(prices.get('WOOL', 0))
    shops = (observation.get('town') or {}).get('unlocked_shops') or []
    reason = 'applied'
    if 'YARN_STORE' not in shops:
        reason = 'no_revealed_yarn_store'
    elif milk > 40 or wool < milk + 20:
        reason = 'price_condition'
    elif not (isinstance(cow, dict) and cow.get('animal') == 'COW'
              and isinstance(sheep, dict) and sheep.get('animal') == 'SHEEP'):
        reason = 'animals_differ'
    elif int(sheep.get('placed_day', -1)) != 0 or int(sheep.get('pending_care_bonus', 0)) >= 5:
        reason = 'cohort_or_bank_differs'
    else:
        # Day-end production strictly after today's care. Harvest must also
        # precede the donor's explicit conversion of the pasture.
        payout = 5
        while payout <= day:
            payout += 3
        if payout + 1 >= _TV_SPEC['first_repurpose_day']:
            reason = 'retirement_before_harvest'
    record = {'day': day, 'milk': milk, 'wool': wool, 'reason': reason}
    _TV_REPORT['decisions'].append(record)
    if reason != 'applied':
        return route
    # Copy-on-write: action dictionaries are shared between the 584 base tapes.
    # The chassis and sheep calendar must both see the identical revised tape.
    tape = list(_MGT_ROUTES[route])
    unit = spec['unit']
    for edit in spec['edits']:
        t = day * 24 + edit['hour']
        assert tape[t]['hands'][unit - 1] == edit['before']
        action = dict(tape[t])
        action['hands'] = list(action['hands'])
        action['hands'][unit - 1] = list(edit['after'])
        tape[t] = action
    _MGT_ROUTES[route] = tape
    _MGT_IMPL.chassis.routes[route] = tape
    return route


_MGT_IMPL.chassis.router = _tv_router

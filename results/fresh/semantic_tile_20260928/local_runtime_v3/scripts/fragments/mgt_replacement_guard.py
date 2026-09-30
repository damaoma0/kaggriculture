"""Experimental guard: optional animal service must respect explicit crop conversion."""


def _shp_replacement_calendar(state, tape, day):
    cache = state.setdefault('replacement_calendar', {})
    key = (id(tape), day)
    if key in cache:
        return cache[key]
    if len(cache) > 8:
        cache.clear()
    # Two unfed nights clear an animal. Inspect today and the next two days;
    # the donor's later shop path is never consulted.
    start, stop = day * 24, min(len(tape), (day + 3) * 24) - 1
    sim = _tc_simulate(lambda t: tape[t], start, stop, [(4, 4)])
    digs, feeds, replacements = {}, set(), {}
    for step, units in sim.items():
        for x, y, command in units:
            if not command:
                continue
            tile = (x, y)
            if command[0] == 'FEED':
                feeds.add(tile)
            elif command[0] == 'DIG':
                digs[tile] = step
            elif command[0] == 'PLANT' and len(command) > 1 and tile in digs:
                if tile not in feeds and digs[tile] < step:
                    replacements.setdefault(tile, step)
    cache[key] = replacements
    return replacements


def _shp_topups(state, obs, tape, day):
    rows = _shp_topups_before_replacement(state, obs, tape, day)
    if not any(ops & {'FEED', 'CARE'} for _, _, ops in rows):
        return rows
    replacements = _shp_replacement_calendar(state, tape, day)
    farm = obs['farms'][int(obs['player'])]
    kept, suppressed = [], set()
    for value, tile, ops in rows:
        if tile not in replacements or not ops & {'FEED', 'CARE'}:
            kept.append((value, tile, ops))
            continue
        x, y = tile
        cell = farm['tiles'][y][x]
        species = cell.get('animal') if isinstance(cell, dict) else None
        if species not in _SHP_ANIMALS:
            kept.append((value, tile, ops))
            continue
        suppressed.add(tile)
        _shp_count('replacement_service_suppressed')
        # Preserve only an already-requested, physically available final harvest.
        # Do not value future output from the animal whose retirement we honor.
        waiting = int(cell.get('yield_units', 0) or 0)
        if 'HARVEST' in ops and waiting > 0:
            product = _SHP_ANIMALS[species][0]
            price = max(0.0, float((obs.get('market') or {}).get('prices', {}).get(product, 0) or 0))
            kept.append((waiting * price, tile, {'HARVEST'}))
            _shp_count('replacement_final_harvest_retained')
    if suppressed:
        for name in ('orphans', 'rescue_pinned'):
            state[name] = [tile for tile in state.get(name, []) if tile not in suppressed]
    return kept

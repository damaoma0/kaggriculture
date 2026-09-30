"""Transfer an investment calendar while servicing the live farm's own cohorts.

Donor movement and exact tile identities are not inputs to the generated jobs.
New planting counts and fertilizer budgets come from one coherent donor window.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from cumulative_engine_profiles import ENGINE as _CC_ENGINE


def _fields(value):
    if isinstance(value, dict): return value
    if not isinstance(value, str): return {}
    return dict(part.split('=', 1) for part in value.split('|') if '=' in part)


def adapt_calendar(obs, donor=None, *, maintenance=False, sustain_cap=0):
    farm = deepcopy(obs['farms'][obs['player']])
    start = obs['day']
    investments = defaultdict(Counter)
    herds = defaultdict(Counter)
    fertilizers = defaultdict(Counter)
    harvest_ages = defaultdict(list)
    if donor is not None:
        for job in donor['jobs']:
            op, rel = job['cmd'][0], job['day']
            fields = _fields(job.get('pre_tile'))
            if op == 'PLANT': investments[rel][job['cmd'][1]] += 1
            if op == 'PLACE' and job['cmd'][1] in _CC_ENGINE.ANIMALS: herds[rel][job['cmd'][1]] += 1
            if op == 'FERTILIZE' and fields.get('crop'): fertilizers[rel][fields['crop']] += 1
            if op == 'HARVEST' and fields.get('crop') and fields.get('planted_day') is not None:
                harvest_ages[fields['crop']].append(donor['day'] + rel - int(fields['planted_day']))
    age_target = {p: sorted(ages)[len(ages) // 2] for p, ages in harvest_ages.items()}
    if sustain_cap:
        age_target.update(WHEAT=2, CARROT=3)
    jobs, slack = [], []
    for rel in range(3):
        day = start + rel
        if day > 29: break
        priv = {'seeds': {p: 1000 for p in _CC_ENGINE.CROPS}, 'shed': {}, 'inventories': [{}]}
        farm['hands'] = []
        ordinals = Counter()
        def act(pos, cmd):
            farm['farmer'] = list(pos)
            inv = priv['inventories'][0]
            p = 'WHEAT' if cmd[0] == 'FEED' else 'FERTILIZER' if cmd[0] == 'FERTILIZE' else None
            if cmd[0] == 'PLACE' and cmd[1] in _CC_ENGINE.ANIMALS: p = cmd[1]
            if p: inv[p] = inv.get(p, 0) + 1
            before = dict(inv)
            tile = deepcopy(farm['tiles'][pos[1]][pos[0]])
            _CC_ENGINE._apply_unit_action(farm, priv, 0, cmd, len(farm['tiles']), day, 24)
            effect = {p: n - before.get(p, 0) for p, n in inv.items() if n > before.get(p, 0)}
            jobs.append({'day': rel, 'hour': ordinals[pos], 'tile': list(pos), 'cmd': cmd,
                         'pre_tile': tile, 'effect': effect,
                         'authorized_dig': cmd[0] == 'DIG'})
            ordinals[pos] += 1
        for y, row in enumerate(farm['tiles']):
            for x, tile in enumerate(row):
                if not isinstance(tile, dict): continue
                pos = x, y
                if tile.get('animal'):
                    species = _CC_ENGINE.ANIMALS[tile['animal']]
                    future = [d for d in range(day + 1, 30) if d - tile['placed_day'] >= species['first_yield_day']
                              and (d - tile['placed_day'] - species['first_yield_day']) % species['interval'] == 0]
                    if future and not tile.get('fed_today'): act(pos, ['FEED'])
                    if any(d > day + 1 for d in future) and not tile.get('cared_today'): act(pos, ['CARE'])
                    if tile.get('yield_units', 0): act(pos, ['HARVEST'])
                    if tile.get('fertilizer_available'): act(pos, ['COLLECT_FERTILIZER'])
                    continue
                if tile.get('kind') != 'PLANT': continue
                p = tile['crop']; crop = _CC_ENGINE.CROPS[p]; age = day - tile['planted_day']
                next_age = age + 1 - crop['first_yield_day']
                produces = crop['ongoing'] and next_age >= 0 and next_age % crop['interval'] == 0 and next_age // crop['interval'] < crop['max_yield'] and day < 29
                grow = not crop['ongoing'] and (crop['max_yield_day'] + 1) // 2 <= age <= crop['max_yield_day'] and tile.get('yield_units', 0) < crop['max_yield']
                price = obs['market']['prices'].get(p, 0)
                fertilizer_price = obs['market']['prices'].get('FERTILIZER', 100)
                renew = bool(sustain_cap and produces and .7 * price > fertilizer_price + 20)
                if ((not maintenance and fertilizers[rel][p]) or renew) and (grow or produces) and tile.get('fertilized_until_day', -1) < day:
                    act(pos, ['FERTILIZE']); fertilizers[rel][p] -= 1
                if not tile.get('watered_today') and (grow or (produces and tile.get('fertilized_until_day', -1) >= day)
                                                     or (day < 29 and tile.get('consecutive_unwatered', 0) >= 1)):
                    act(pos, ['WATER'])
                if tile.get('yield_units', 0) and age >= crop['first_yield_day']:
                    if crop['ongoing'] or age >= age_target.get(p, crop['max_yield_day']) or day == 29:
                        act(pos, ['HARVEST'])
                tile = farm['tiles'][y][x]
                last_age = crop['first_yield_day'] + (crop['max_yield'] - 1) * crop['interval'] if crop['ongoing'] else None
                if isinstance(tile, dict) and crop['ongoing'] and age >= last_age and not tile.get('yield_units', 0):
                    act(pos, ['DIG'])
        if not maintenance or sustain_cap:
            for species, count in sorted(herds[rel].items()):
                animal = _CC_ENGINE.ANIMALS[species]
                if day + animal['first_yield_day'] >= 30:
                    slack.append({'day': day, 'animal': species, 'unplaced': count, 'reason': 'matures_after_season'}); continue
                options = [(x, y) for y, row in enumerate(farm['tiles']) for x, tile in enumerate(row)
                           if tile is None or isinstance(tile, dict) and
                           (tile.get('kind') == 'WEED' or tile.get('kind') == animal['structure'] and not tile.get('animal'))]
                options.sort(key=lambda p: (abs(p[0] - 4.5) + abs(p[1] - 4.5), p))
                for pos in options[:count]:
                    tile = farm['tiles'][pos[1]][pos[0]]
                    if isinstance(tile, dict) and tile.get('kind') == 'WEED': act(pos, ['DIG']); tile = None
                    if tile is None: act(pos, ['BUILD_COOP' if animal['structure'] == 'COOP' else 'BUILD_PASTURE'])
                    act(pos, ['PLACE', species]); act(pos, ['FEED']); act(pos, ['CARE'])
                if len(options) < count: slack.append({'day': day, 'animal': species, 'unplaced': count-len(options), 'reason': 'occupied_land'})
            available = [(x, y) for y, row in enumerate(farm['tiles']) for x, tile in enumerate(row)
                         if tile is None or isinstance(tile, dict) and tile.get('kind') == 'WEED']
            available.sort(key=lambda p: (abs(p[0] - 4.5) + abs(p[1] - 4.5), p))
            planting = investments[rel].copy()
            if sustain_cap:
                # A bounded, joint fallback keeps short crop cycles running.
                # Value the whole extra batch on the engine's glut curve rather
                # than multiplying output by the current spot quote.
                options = []
                for p, age, units in (('WHEAT', 2, 2), ('CARROT', 3, 3)):
                    if day + age >= 30: continue
                    inventory = obs['market']['inventory'][p]
                    expected_units = sustain_cap * units
                    revenue = sum(_CC_ENGINE.market_price(p, inventory + q, obs['market'].get('params')) for q in range(expected_units))
                    value = (revenue - sustain_cap * _CC_ENGINE.CROPS[p]['seed']) / (age + 1)
                    options.append((value, p))
                if options:
                    value, p = max(options)
                    if value > 20 * sustain_cap: planting[p] = min(sustain_cap, len(available))
            for p, count in sorted(planting.items()):
                if day + _CC_ENGINE.CROPS[p]['first_yield_day'] >= 30:
                    slack.append({'day': day, 'crop': p, 'unplaced': count, 'reason': 'matures_after_season'}); continue
                used = 0
                for _ in range(min(count, len(available))):
                    pos = available.pop(0)
                    if farm['tiles'][pos[1]][pos[0]] is not None: act(pos, ['DIG'])
                    act(pos, ['PLANT', p]); act(pos, ['WATER']); used += 1
                if used < count: slack.append({'day': day, 'crop': p, 'unplaced': count - used, 'reason': 'occupied_land'})
        for hour in range(23 if day == 29 else 24):
            _CC_ENGINE._decay_plants(farm, day * 24 + hour)
        if day < 29:
            _CC_ENGINE._daily_refresh_plants(farm, day, 24)
            _CC_ENGINE._daily_refresh_animals(farm, day)
        # The per-tile model above is only a target generator. Hourly decay,
        # transport, funding and actual output are checked by the full projector.
    return {'id': 'maintain' if donor is None else 'adapt:' + donor['id'], 'day': start,
            'jobs': jobs, 'safety_assets': False, 'hire_to': 12, 'calendar_slack': slack,
            'start_farm': deepcopy(obs['farms'][obs['player']])}

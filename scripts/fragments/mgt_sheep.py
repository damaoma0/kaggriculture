# --------------------------------------------------------------------------- Yarn-responsive sheep overlay
# Mother-Goose's own plan adds sheep when Yarn Stores are revealed: season sheep = 4 + sum over Yarn Stores of
# {reveal day 3: 10, 6: 9, 9: 4, 12: 2, 15: 2, later: 0} (additive, fits 88% of 584 games within +-1;
# results/fresh/mg_tape/yarn_rule.json). A borrowed tape recorded in a world with fewer Yarn Stores does not,
# which is the largest single routing loss (4 of 40 leave-one-out worlds lose 32k each, wool -30k). This overlay
# buys the missing sheep and services them with hands of its own:
#   * deficit = her rule's target - sheep we actually hold - sheep the tape's recorded boards still add
#     (her tapes over-request animal orders, so order counts overstate what arrives);
#   * each commitment is sized by the engine economics: a sheep fed and cared for daily yields 6 wool at its
#     first production (end of day placed+5) and 4 every 3 days after; every block of sheep pays for its own
#     hand at the day's marginal Fibonacci wage, its feed, and the field it displaces;
#   * tiles: empty tiles the current tape never uses again, or fields it only plants with wheat or carrots
#     (tape calendar), grown as one compact block near the shed;
#   * the overlay's hands are HIDDEN from the tape layer (observation without them, commands merged back by real
#     index); they are hired right after the tape's last hire of the day (hour 1 on 96% of her days), never
#     before it, because an extra unit on a shed tile displaces the tape's next spawns;
#   * every day: buy the feed wheat with the hire, load, then tile by tile FEED, CARE, HARVEST, COLLECT, falling
#     back to feed-only when the day is running out. A sheep is not fed after its last useful production day.
#   * TOP-UP: her servicing is demand-conditioned (584 tapes, scripts/mg_care_rule.py): sheep are cared for on
#     46% of animal-days (fed 68%) with no Yarn Store and 75-90% with one or more; cows 65% -> 86% as milk shops
#     appear; geese always ~92%. A borrowed tape therefore under-services animals when our world has more
#     demand. Every day the tape's FEED/CARE visits are read from the tape calendar; an animal it skips gets a
#     CARE (or FEED + CARE) from an overlay hand when the banked unit (+1 product at the next fed production)
#     is worth it, and a hand is hired only when its run is worth more than its marginal wage.
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


def _shp_tape_future(player, day):
    """Sheep the current tape still ADDS after today, from its recorded boards."""
    st = _MGT_IMPL.chassis.players.get(player) or {}
    r = st.get('route')
    if r is None or not (0 <= r < len(_MGT_TAPES)):
        return 0
    counts = [sum(1 for x in b if x == 'sh') for b in _MGT_TAPES[r]['lab']]
    d = min(day, len(counts) - 1)
    return max(0, max(counts[d:]) - counts[d])


def _shp_owned(obs, player):
    """Sheep we hold: on the board, in the shed, in anyone's hands."""
    farm = obs['farms'][player]
    n = sum(1 for row in farm['tiles'] for c in row if isinstance(c, dict) and c.get('animal') == 'SHEEP')
    n += int((obs['private'].get('shed') or {}).get('SHEEP', 0) or 0)
    for inv in (obs['private'].get('inventories') or []):
        n += int((inv or {}).get('SHEEP', 0) or 0)
    return n


def _shp_reserved(tape, step, item):
    """Units of ``item`` the tape's own crew still PICKs UP from the shed today (from this step on). The shed is
    shared and her feed purchases are sized exactly: a hand of ours that takes that wheat starves her animals."""
    n = 0
    for t in range(step, min(len(tape), (step // 24 + 1) * 24)):
        a = tape[t] if isinstance(tape[t], dict) else {}
        for c in [a.get('farmer')] + list(a.get('hands') or []):
            if c and c[0] == 'PICKUP' and len(c) > 1 and c[1] == item:
                n += int(c[2]) if len(c) > 2 else 100
    return n


def _shp_feed_guard(obs, action, step, tape):
    """Her crew feeds from the shed's wheat stock, which her own fields refill; on a borrowed tape (or with fields
    turned into pasture) the stock can run short, the PICKUP comes up empty and her animals starve (two unfed
    days = lost). One step ahead of every tape wheat PICKUP, buy what the shed will be missing."""
    if not _SHP_CFG.get('feed_guard', True) or step % 24 == 23 or step + 1 >= len(tape):
        return action
    nxt = tape[step + 1] if isinstance(tape[step + 1], dict) else {}
    need = 0
    for c in [nxt.get('farmer')] + list(nxt.get('hands') or []):
        if c and c[0] == 'PICKUP' and len(c) > 2 and c[1] == 'WHEAT':
            need += int(c[2])
    if need <= 0:
        return action
    have = int((obs['private'].get('shed') or {}).get('WHEAT', 0) or 0)
    for c in [action.get('farmer')] + list(action.get('hands') or []):
        if c and c[0] == 'PICKUP' and len(c) > 2 and c[1] == 'WHEAT':
            have -= int(c[2])
    have = max(0, have)
    market = [list(o) for o in (action.get('market') or [])]
    for o in market:
        if len(o) >= 3 and o[1] == 'WHEAT':
            if o[0] == 'BUY_PRODUCT':
                have += int(o[2])
            elif o[0] == 'SELL':
                have = max(0, have - int(o[2]))
    short = min(int(_SHP_CFG.get('feed_guard_max', 20)), need - have)
    if short <= 0 or len(market) >= 10:
        return action
    market.append(['BUY_PRODUCT', 'WHEAT', short])
    _shp_count('guard_wheat', short)
    return dict(action, market=market)


def _shp_last_hire_hour(tape, day):
    """The overlay hires only AFTER the tape's last hire of the day: a hand of ours standing on a shed tile
    changes where the engine spawns the tape's next hands (least-occupied shed tile), and a displaced tape hand
    replays its whole day one tile off."""
    hours = [t % 24 for t in range(day * 24, min(len(tape), day * 24 + 24))
             for o in (tape[t].get('market') or []) if o and o[0] == 'HIRE']
    return max(hours) if hours else -1


def _shp_tape_hires(tape, day):
    return sum(1 for t in range(day * 24, min(len(tape), day * 24 + 24))
               for o in (tape[t].get('market') or []) if o and o[0] == 'HIRE')


def _shp_wages(first_index, k):
    return sum(_SHP_FIB[min(15, first_index + i)] for i in range(k))


def _shp_per_hand(hour, setup):
    """Sheep one hand hired at ``hour`` can service: it acts from hour+1, spends ~6 turns loading and walking,
    then FEED + CARE + a step per sheep (dig, build, place on the set-up day; feeding can wait a day there)."""
    turns = 23 - hour - 6
    return max(1, min(3 if setup else 4, turns // (4 if setup else 3)))


def _shp_hands_for(n, hour, setup=False):
    return -(-n // _shp_per_hand(hour, setup)) if n > 0 else 0


_SHP_ANIMALS = {'SHEEP': ('WOOL', 6, 3), 'COW': ('MILK', 8, 2), 'GOOSE': ('EGG', 4, 1)}


def _shp_next_prod(species, placed_day, day):
    """First production (end of day) strictly after ``day``; None when it falls after day 28."""
    _, first, interval = _SHP_ANIMALS[species]
    d = placed_day + first - 1
    while d <= day:
        d += interval
    return d if d <= 28 else None


def _shp_tape_today(tape, day):
    """Tiles the tape's crew FEEDs / CAREs today (tape calendar)."""
    sim = _tc_simulate(lambda t: tape[t] if t < len(tape) else {}, day * 24, day * 24 + 23, [(4, 4)])
    feed, care = set(), set()
    for row in sim.values():
        for x, y, c in row:
            if c and c[0] == 'FEED':
                feed.add((x, y))
            elif c and c[0] == 'CARE':
                care.add((x, y))
    return feed, care


def _shp_cal(state, tape, day):
    """Cached (feed tiles, care tiles) of the tape's crew on ``day``."""
    cache = state.setdefault('cal', {})
    key = (id(tape), day)
    if key not in cache:
        if len(cache) > 16:
            cache.clear()
        cache[key] = _shp_tape_today(tape, day)
    return cache[key]


def _shp_topups(state, obs, tape, day):
    """[(value, tile, ops)] for tape animals the tape under-services today.
      bank    a fed and cared day banks +1 unit for the NEXT production - which pays it only if the animal is fed
              on that day. Her low-demand tapes feed just often enough to keep the animal (2 days in 3) and skip
              production days, so a banked unit is only counted when the tape feeds the next production day, or
              charged a second feed when it does not (the payout feed below then follows on that day).
      payout  on a production day with a bank, a FEED the tape skips is worth the whole bank.
    Values use ``topup_factor`` of today's price; feed at wheat + 12."""
    if not _SHP_CFG.get('topup', True) or day < 1 or day > 28:
        return []
    farm = obs['farms'][int(obs['player'])]
    prices = (obs.get('market') or {}).get('prices') or {}
    wheat = float(prices.get('WHEAT', 40) or 40) + 12.0
    factor = _SHP_CFG.get('topup_factor', 0.8)
    feed, care = _shp_cal(state, tape, day)
    outlook = {_SHP_ANIMALS[a][0]: _shp_outlook(obs, _SHP_ANIMALS[a][0], a) for a in _SHP_ANIMALS}
    out = []
    for y, row in enumerate(farm['tiles']):
        for x, c in enumerate(row):
            if not (isinstance(c, dict) and c.get('animal') in _SHP_ANIMALS) or (x, y) in state['tiles']:
                continue
            species = c['animal']
            product, first, interval = _SHP_ANIMALS[species]
            placed = int(c.get('placed_day', day))
            price = factor * outlook[product]
            fed = bool(c.get('fed_today')) or (x, y) in feed
            cared = bool(c.get('cared_today')) or (x, y) in care
            since = day + 1 - placed - first
            bank = int(c.get('pending_care_bonus', 0) or 0)
            ops, value = set(), 0.0
            if since >= 0 and since % interval == 0 and bank > 0 and not fed:
                ops.add('FEED')                                   # payout
                value += bank * price - wheat
                fed = True
            nxt = _shp_next_prod(species, placed, day)
            if nxt is not None and not cared and bank < 5:
                v = price
                if not fed:
                    v -= wheat
                if (x, y) not in _shp_cal(state, tape, nxt)[0]:
                    v -= wheat                                    # we will have to feed the production day too
                if v >= _SHP_CFG.get('topup_min', 40.0):
                    ops.add('CARE')
                    if not fed:
                        ops.add('FEED')
                    value += v
            if ops and value >= _SHP_CFG.get('topup_min', 40.0):
                out.append((value, (x, y), ops))
    return out


def _shp_runs(state, mandatory, optional, hour, base, max_hands, heavy=()):
    """Split the day's work into one run per hand: the flock first (nearest-neighbour walk from the shed), then
    top-ups by value density. A hand beyond the flock's needs is kept only when its run is worth more than
    ``topup_margin`` x its marginal wage. Returns [[(tile, ops_or_None), ...], ...]."""
    budget = 23 - hour - 1                                # acts from hour+1, one turn to load
    runs, cur, used, pos = [], [], 0, (4, 5)
    todo = list(mandatory)
    while todo:
        t = min(todo, key=lambda q: (_shp_dist(pos, q), q))
        todo.remove(t)
        cost = _shp_dist(pos, t) + (3 if t in heavy else 2)   # FEED + CARE (+ HARVEST when wool is waiting)
        if cur and used + cost > budget:
            runs.append(cur)
            cur, used, pos = [], 0, (4, 5)
            cost = _shp_dist(pos, t) + (3 if t in heavy else 2)
        cur.append((t, None))
        used += cost
        pos = t
    if cur and len(runs) >= max_hands and runs:
        runs[-1].extend(cur)                              # more flock than hands: overload the last run
        cur = []
    flock_hands = len(runs) + (1 if cur else 0)
    rest = sorted(optional, key=lambda o: -o[0])
    value = 0.0
    margin = _SHP_CFG.get('topup_margin', 1.5)
    while rest and len(runs) < max_hands:
        # next top-up: best value per turn from where this hand stands
        best = max(rest, key=lambda o: o[0] / (_shp_dist(pos, o[1]) + len(o[2])))
        cost = _shp_dist(pos, best[1]) + len(best[2])
        if used + cost > budget:
            if cur and (len(runs) < flock_hands or value >= margin * _SHP_FIB[min(15, base + len(runs))]):
                runs.append(cur)
            elif cur and len(runs) >= flock_hands:
                break                                     # this hand does not pay; a later one would pay less
            cur, used, pos, value = [], 0, (4, 5), 0.0
            if _shp_dist(pos, best[1]) + len(best[2]) > budget:
                rest.remove(best)
            continue
        rest.remove(best)
        cur.append((best[1], best[2]))
        used += cost
        value += best[0]
        pos = best[1]
    if cur and len(runs) < max_hands and (len(runs) < flock_hands or value >= margin * _SHP_FIB[min(15, base + len(runs))]):
        runs.append(cur)
    return runs


# Engine price curve (kaggriculture.MARKET_PARAMS): price = base +/- amp * f(|inventory - 10000|), amp = target*base/f(T).
_SHP_MARKET = {'WOOL': (200, 105, 'log', 0.20, 'sq', 3.20), 'MILK': (160, 122, 'sqrt', 0.60, 'linear', 1.60),
               'EGG': (50, 332, 'hinge', 0.40, 'log', 0.20)}
_SHP_DEMAND = {'WOOL': {'YARN_STORE': 12}, 'MILK': {'PIZZA_SHOP': 6, 'ICE_CREAM_SHOP': 6, 'SMOOTHIE_SHOP': 6},
               'EGG': {'BAKERY': 6, 'BRUNCH_SPOT': 6}}
_SHP_RATE = {'SHEEP': 1.2, 'COW': 1.2, 'GOOSE': 1.8}     # units per animal-day at her usual care level


def _shp_shape(func, x, T):
    import math
    x = max(0.0, x)
    if func == 'sq':
        return x * x
    if func == 'sqrt':
        return math.sqrt(x)
    if func == 'log':
        return math.log(1.0 + x)
    if func == 'hinge':
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    return x


def _shp_price(item, x):
    """Engine price at glut x = market inventory - 10000 (negative = scarcity)."""
    base, T, bf, bt, af, at = _SHP_MARKET[item]
    if x < 0:
        return max(1.0, base + bt * base / _shp_shape(bf, T, T) * _shp_shape(bf, -x, T))
    return max(1.0, base - at * base / _shp_shape(af, T, T) * _shp_shape(af, x, T))


def _shp_flows(obs, item, species):
    """(glut now, daily consumption by day, daily supply from the animals both farms hold now)."""
    inv = float(((obs.get('market') or {}).get('inventory') or {}).get(item, 10000) or 10000)
    shops = list((obs.get('town') or {}).get('unlocked_shops') or [])
    now = 1.0 + sum(_SHP_DEMAND[item].get(s, 0) for s in shops)
    per_shop = sum(_SHP_DEMAND[item].values()) / 8.0           # an undrawn shop, in expectation
    day = int(obs['step']) // 24
    use = {}
    for d in range(day, 30):
        extra = sum(1 for i in range(len(shops), 8) if 3 * (i + 1) <= d)
        use[d] = now + per_shop * extra
    animals = sum(1 for farm in obs['farms'] for row in farm['tiles'] for c in row
                  if isinstance(c, dict) and c.get('animal') == species)
    return inv - 10000.0, use, animals * _SHP_RATE[species]


def _shp_wool_gain(obs, player, day, n):
    """Extra wool REVENUE of n more sheep bought today, price impact included: the day-by-day glut with and
    without them (both farms' sheep keep supplying, shops keep consuming), our own wool repriced too."""
    x0, use, supply = _shp_flows(obs, 'WOOL', 'SHEEP')
    farm = obs['farms'][player]
    mine = _SHP_RATE['SHEEP'] * sum(1 for row in farm['tiles'] for c in row
                                    if isinstance(c, dict) and c.get('animal') == 'SHEEP')
    xa = xb = x0
    rev_a = rev_b = 0.0
    for d in range(day, 29):
        k = d - (day + 6)                                     # sold the day after each production
        new = n * (6 if k == 0 else 4 if (k > 0 and k % 3 == 0) else 0)
        pa = 0.5 * (_shp_price('WOOL', xa) + _shp_price('WOOL', xa + supply - use[d]))
        pb = 0.5 * (_shp_price('WOOL', xb) + _shp_price('WOOL', xb + supply + new - use[d]))
        rev_a += mine * pa
        rev_b += (mine + new) * pb
        xa += supply - use[d]
        xb += supply + new - use[d]
    return rev_b - rev_a


def _shp_outlook(obs, item, species, days=3):
    """Price the product is heading for over the next days (never above today's)."""
    x, use, supply = _shp_flows(obs, item, species)
    day = int(obs['step']) // 24
    for d in range(day, min(29, day + days)):
        x += supply - use[d]
    today = float(((obs.get('market') or {}).get('prices') or {}).get(item, 0) or 0)
    return min(today, _shp_price(item, x))


def _shp_last_prod(placed_day):
    """Last production day (end of day) whose wool can still be harvested and sold (by day 29)."""
    first = placed_day + 5
    if first > 28:
        return -1
    return first + 3 * ((28 - first) // 3)


def _shp_units(day):
    """Wool a sheep placed on ``day`` yields if fed and cared for daily: 6 at the first production (end of
    day+5), then 4 every 3 days; the day-28 production is left out (it has to be harvested and sold on day 29)."""
    n, d, first = 0, day + 5, True
    while d <= 27:
        n += 6 if first else 4
        first = False
        d += 3
    return n


def _shp_field_tiles(tape, farm, step, n, taken=()):
    """``n`` more tiles for sheep: empty tiles the tape never uses again, or fields it only plants with wheat or
    carrots from now on; grown as one compact block from the tiles already taken (or from the shed)."""
    day = step // 24
    sim = _tc_simulate(lambda t: tape[t] if t < len(tape) else {}, day * 24, 718, [(4, 4)])
    future = {}
    for t, row in sim.items():
        if t < step:
            continue
        for x, y, c in row:
            if not c or c[0] in ('PASS', 'NORTH', 'SOUTH', 'EAST', 'WEST', 'PICKUP', 'DROP'):
                continue
            use = future.setdefault((x, y), set())
            if c[0] == 'PLANT' and len(c) > 1:
                use.add(c[1])
            elif c[0] in ('WATER', 'HARVEST', 'DIG', 'FERTILIZE'):
                use.add('TEND')
            else:
                use.add('STRUCTURE')
    ok = []
    for y, row in enumerate(farm['tiles']):
        for x, cell in enumerate(row):
            p = (x, y)
            if p in _SHP_SHED or p in taken or cell == 'LOCKED':
                continue
            use = future.get(p, set())
            if cell is None or (isinstance(cell, dict) and cell.get('kind') == 'WEED'):
                if use <= {'WHEAT', 'CARROT', 'TEND'}:
                    ok.append(p)
            elif isinstance(cell, dict) and cell.get('kind') == 'PLANT' and cell.get('crop') in ('WHEAT', 'CARROT'):
                if use <= {'WHEAT', 'CARROT', 'TEND'}:
                    ok.append(p)
    n = min(n, len(ok))
    if n <= 0:
        return []
    chosen = list(taken)
    out = []
    while len(out) < n:
        rest = [p for p in ok if p not in out]
        if chosen:
            nxt = min(rest, key=lambda p: (min(_shp_dist(p, q) for q in chosen) + (2 if future.get(p) else 0),
                                           _shp_dist(p, (4, 5)), p))
        else:
            nxt = min(rest, key=lambda p: (_shp_dist(p, (4, 5)) + (2 if future.get(p) else 0), p))
        chosen.append(nxt)
        out.append(nxt)
    _SHP_STATES.setdefault('_crop_tiles', set()).clear()
    _SHP_STATES['_crop_tiles'].update(p for p in out if future.get(p))
    return out


def _shp_flock(state, day=None):
    """Tiles still worth servicing."""
    return [t for t in state['tiles'] if t not in state['lost']
            and (day is None or day <= _shp_last_prod(state['placed_day'].get(t, day)))]


def _shp_decide(state, obs, action, step):
    """Add sheep (possibly several times) when her rule calls for more than we hold plus what the tape still
    delivers; the size of each commitment maximises the engine-economics profit within cash."""
    day, hour = step // 24, step % 24
    if state.get('decided_day') == day:
        return action
    if day < _SHP_CFG.get('first_day', 6) or day > _SHP_CFG.get('last_day', 19):
        return action
    if hour < 1 or hour > _SHP_CFG.get('latest_hour', 8):
        return action
    player = int(obs['player'])
    tape = _shp_route(player)
    if tape is None:
        return action
    if hour <= _shp_last_hire_hour(tape, day):
        return action
    market = [list(o) for o in (action.get('market') or [])]
    if len(market) > 6:                                   # no room for the orders this hour; try the next
        return action
    state['decided_day'] = day
    shops = list((obs.get('town') or {}).get('unlocked_shops') or [])
    target = 4 + sum(_SHP_LOOKUP.get(3 * (i + 1), 0) for i, s in enumerate(shops) if s == 'YARN_STORE')
    owned = _shp_owned(obs, player)
    planned = owned + _shp_tape_future(player, day)
    flock = _shp_flock(state)
    deficit = min(int(_SHP_CFG.get('max_sheep', 16)) - len(flock), target - planned)
    if deficit < _SHP_CFG.get('min_deficit', 2):
        return action
    farm = obs['farms'][player]
    prices = (obs.get('market') or {}).get('prices') or {}
    wool, wheat = float(prices.get('WOOL', 0) or 0), float(prices.get('WHEAT', 40) or 40)
    days_left = 29 - day
    hired_today = state.get('hired_day') == day
    cash = float(farm['money']) - _SHP_CFG.get('cash_margin', 2000)
    slots = 10 - len(market) - 2
    best = None
    tiles_all = _shp_field_tiles(tape, farm, step, deficit, tuple(state['tiles']))
    crop_tiles = set(_SHP_STATES.get('_crop_tiles') or ())
    if len(tiles_all) < _SHP_CFG.get('min_deficit', 2):
        _shp_count('declined_tiles')
        return action
    deficit = len(tiles_all)
    bases = [_shp_tape_hires(tape, d) for d in range(day + 1, 29)]
    base_today = int(farm.get('hires_today', 0)) + sum(1 for o in market if o and o[0] == 'HIRE')
    for n in range(deficit, 0, -1):
        k_today = _shp_hands_for(n, hour, True) + (0 if hired_today else _shp_hands_for(len(flock), hour))
        if k_today > min(slots, _SHP_CFG.get('max_hands', 4)):
            continue
        after, before = _shp_hands_for(len(flock) + n, 0), _shp_hands_for(len(flock), 0)
        if after > _SHP_CFG.get('max_hands', 4):
            continue
        wage = sum(_shp_wages(b, after) - _shp_wages(b, before) for b in bases)
        wage_today = _shp_wages(base_today, k_today)
        # wool revenue from the engine price curve (85%), feed at wheat + 12, a converted field ~1 wheat a day
        fields = sum(1 for t in tiles_all[:n] if t in crop_tiles)
        profit = (_SHP_CFG.get('wool_factor', 0.85) * _shp_wool_gain(obs, player, day, n) - 500.0 * n
                  - n * days_left * (wheat + 12.0) - fields * days_left * wheat - wage - wage_today)
        cost = 500 * n + wage_today + (len(flock) + n + 2) * (wheat + 12)
        if cost > cash:
            continue
        if best is None or profit > best[0]:
            best = (profit, n, k_today)
    if best is None:
        _shp_count('declined_cash')
        return action
    profit, n, k = best
    if n < _SHP_CFG.get('min_deficit', 2) or profit < _SHP_CFG.get('min_profit', 1000.0):
        _shp_count('declined_profit')
        return action
    tiles = tiles_all[:n]
    feed = n + 2 + (0 if hired_today else len(flock))
    parent_hires = sum(1 for o in market if o and o[0] == 'HIRE')
    market += [['BUY_ANIMAL', 'SHEEP', n], ['BUY_PRODUCT', 'WHEAT', feed]] + [['HIRE'] for _ in range(k)]
    work = list(tiles) + ([] if hired_today else flock)
    state['tiles'] = state['tiles'] + tiles
    path, cur = [], (4, 5)
    while work:
        nxt = min(work, key=lambda t: (_shp_dist(cur, t), t))
        work.remove(nxt)
        path.append((nxt, None))
        cur = nxt
    size = -(-len(path) // k)
    state.update(committed=True, hired_day=day,
                 pending=dict(step=step, before=len(farm['hands']), parent=parent_hires, k=k,
                              runs=[path[i * size:(i + 1) * size] for i in range(k)]))
    _shp_count('commitments')
    _shp_count('sheep_bought', n)
    _shp_count('hand_days', k)
    _SHP_REPORT.setdefault('decisions', []).append(dict(day=day, hour=hour, target=target, owned=owned, planned=planned,
                                                        n=n, hands=k, tiles=tiles, wool=wool, profit=round(profit)))
    return dict(action, market=market)


def _shp_daily_hire(state, obs, action, step):
    """Every day: the flock's hands plus top-up hands that pay for themselves, and the feed wheat, at the first
    hour with free order slots."""
    day, hour = step // 24, step % 24
    if state.get('hired_day') == day or hour > _SHP_CFG.get('hire_until', 6):
        return action
    if not state.get('committed') and not _SHP_CFG.get('topup', True):
        return action
    player = int(obs['player'])
    tape = _shp_route(player)
    if tape is None:
        return action
    if hour <= _shp_last_hire_hour(tape, day):
        return action
    market = [list(o) for o in (action.get('market') or [])]
    if len(market) > 7:
        return action                                     # try again next hour
    farm = obs['farms'][player]
    flock = _shp_flock(state, day)
    waiting = {t for t in _shp_flock(state) if isinstance(farm['tiles'][t[1]][t[0]], dict)
               and int(farm['tiles'][t[1]][t[0]].get('yield_units', 0) or 0) > 0}
    harvest_only = [t for t in waiting if t not in flock]  # past their last production, wool still on the tile
    optional = _shp_topups(state, obs, tape, day)
    state['hired_day'] = day
    if not flock and not harvest_only and not optional:
        return action
    parent_hires = sum(1 for o in market if o and o[0] == 'HIRE')
    base = max(_shp_tape_hires(tape, day), int(farm.get('hires_today', 0)) + parent_hires)
    max_hands = min(int(_SHP_CFG.get('max_hands', 4)), 10 - len(market) - 1)
    runs = _shp_runs(state, list(flock) + harvest_only, optional, hour, base, max_hands, heavy=waiting)
    if not runs:
        return action
    feeds = sum(1 for run in runs for t, ops in run if (ops is None and t in flock) or (ops and 'FEED' in ops))
    wage = _shp_wages(int(farm.get('hires_today', 0)) + parent_hires, len(runs))
    if float(farm['money']) < wage + feeds * 70 + _SHP_CFG.get('hire_margin', 300):
        _shp_count('declined_hire_cash')
        runs = runs[:1] if flock else []
        if not runs:
            return action
        feeds = sum(1 for run in runs for t, ops in run if (ops is None and t in flock) or (ops and 'FEED' in ops))
    if feeds and day < 29:
        buy = max(0, feeds + 1 - int(state.get('wheat_credit', 0)))
        state['wheat_credit'] = 0
        if buy:
            market.append(['BUY_PRODUCT', 'WHEAT', buy])
    market += [['HIRE'] for _ in runs]
    state['pending'] = dict(step=step, before=len(farm['hands']), parent=parent_hires, k=len(runs), runs=runs)
    _shp_count('hand_days', len(runs))
    _shp_count('topup_tasks', sum(1 for run in runs for _, ops in run if ops))
    return dict(action, market=market)


def _shp_confirm(state, obs, step):
    """The step after a hire: which real hand indices are ours (orders fill in list order, the tape's first)."""
    p = state.get('pending')
    if not p or p['step'] != step - 1:
        return
    state['pending'] = None
    day = step // 24
    farm = obs['farms'][int(obs['player'])]
    arrived = len(farm['hands']) - p['before']
    ours = max(0, min(p['k'], arrived - p['parent']))
    if ours < p['k']:
        _shp_count('hire_shortfalls')
    if state.get('own_day') != day:
        state['own_day'], state['own'], state['workers'] = day, set(), {}
    if ours < 1:
        return
    first = 1 + p['before'] + min(p['parent'], arrived)
    runs = [list(r) for r in p['runs']]
    while len(runs) > ours:                               # short hire: fold the last runs into the ones we have
        extra = runs.pop()
        runs[-1].extend(x for x in extra if x[1] is None)
    for i in range(ours):
        h = first + i
        run = runs[i] if i < len(runs) else []
        state['own'].add(h)
        state['workers'][h] = dict(tiles=[t for t, _ in run], ops={t: o for t, o in run if o}, day=day, tries=0)


def _shp_work(state, obs, idx, role, step):
    """One command for an owned hand: load at the shed, then tile by tile - set-up, FEED, CARE, HARVEST, COLLECT -
    nearest tile with work first; feed-only when the remaining turns would not cover every unfed sheep."""
    farm = obs['farms'][int(obs['player'])]
    day, hour = step // 24, step % 24
    if role['day'] != day or idx - 1 >= len(farm['hands']):
        return None
    pos = tuple(farm['hands'][idx - 1])
    invs = obs['private'].get('inventories') or []
    inv = invs[idx] if idx < len(invs) else {}
    shed = obs['private'].get('shed') or {}
    home = _shp_home(pos)
    have_wheat, have_sheep = int(inv.get('WHEAT', 0) or 0), int(inv.get('SHEEP', 0) or 0)
    topup = role.get('ops') or {}
    cells = {t: farm['tiles'][t[1]][t[0]] for t in role['tiles'] if t not in topup}
    extra = {t: farm['tiles'][t[1]][t[0]] for t in topup}
    extra = {t: c for t, c in extra.items() if isinstance(c, dict) and c.get('animal')}
    extra_feed = [t for t, c in extra.items() if 'FEED' in topup[t] and not c.get('fed_today')]
    for t, c in cells.items():
        if isinstance(c, dict) and c.get('animal') == 'SHEEP':
            if t not in state['placed']:
                state['placed'].add(t)
                state['placed_day'][t] = day
        elif t in state['placed'] and t not in state['lost']:
            state['lost'].add(t)
            _shp_count('sheep_lost')
    last_day = day >= 29
    live = {t: c for t, c in cells.items() if t not in state['lost']}
    sheep = {t: c for t, c in live.items() if isinstance(c, dict) and c.get('animal') == 'SHEEP'}
    useful = {t for t in sheep if not last_day and day <= _shp_last_prod(state['placed_day'].get(t, day))}
    caring = {t for t in useful if day < _shp_last_prod(state['placed_day'].get(t, day))}
    unplaced = [t for t in live if t not in state['placed']]
    unfed = [t for t in useful if not sheep[t].get('fed_today')]
    # loading: sheep to place and wheat for everything that still needs feeding today
    if pos in _SHP_SHED and role['tries'] < 6:
        tape = _shp_route(int(obs['player'])) or []
        free_sheep = int(shed.get('SHEEP', 0) or 0) - _shp_reserved(tape, step, 'SHEEP')
        if unplaced and have_sheep < len(unplaced) and free_sheep > 0:
            role['tries'] += 1
            return ['PICKUP', 'SHEEP', min(len(unplaced) - have_sheep, free_sheep)]
        want = len(unfed) + (0 if last_day else len(unplaced)) + len(extra_feed)
        free_wheat = int(shed.get('WHEAT', 0) or 0) - _shp_reserved(tape, step, 'WHEAT')
        if have_wheat < want and free_wheat > 0:
            role['tries'] += 1
            return ['PICKUP', 'WHEAT', min(want - have_wheat, free_wheat)]
        if have_wheat < want and role['tries'] < 4 and hour < 12:
            role['tries'] += 1
            state['need_wheat'] = max(state.get('need_wheat', 0), want - have_wheat)
            return ['PASS']                       # wait a turn for the re-bought feed to land
    cargo = sum(int(v or 0) for k_, v in inv.items() if k_ in ('WOOL', 'FERTILIZER'))
    if last_day and cargo and 24 - hour <= _shp_dist(pos, home) + 2:
        return _shp_walk(pos, home) or ['DROP']
    # feed-only mode when the day is running out
    turns_left = 24 - hour
    feed_need, cur = 0, pos
    for t in sorted(unfed, key=lambda t: _shp_dist(pos, t)):
        feed_need += _shp_dist(cur, t) + 1
        cur = t
    feed_only = bool(unfed) and have_wheat > 0 and feed_need + 2 >= turns_left
    todo = []
    for t, c in live.items():
        if t in sheep:
            if t in useful and not c.get('fed_today') and have_wheat > 0:
                todo.append((t, ['FEED']))
            elif feed_only:
                continue
            elif t in caring and not c.get('cared_today'):
                todo.append((t, ['CARE']))
            elif int(c.get('yield_units', 0) or 0) > 0:
                todo.append((t, ['HARVEST']))
            elif c.get('fertilizer_available') and hour < 22 and not last_day:
                todo.append((t, ['COLLECT_FERTILIZER']))
        elif t not in state['placed'] and have_sheep > 0 and not feed_only:
            if c is None:
                todo.append((t, ['BUILD_PASTURE']))
            elif isinstance(c, dict) and c.get('kind') == 'PASTURE' and not c.get('animal'):
                todo.append((t, ['PLACE', 'SHEEP']))
            elif isinstance(c, dict) and c.get('kind') == 'PLANT':
                age = day - int(c.get('planted_day', day))
                todo.append((t, ['HARVEST'] if (age >= 2 and int(c.get('yield_units', 0) or 0) > 0) else ['DIG']))
            elif isinstance(c, dict) and c.get('kind') == 'WEED':
                todo.append((t, ['DIG']))
    if not feed_only:
        for t, c in extra.items():
            if 'FEED' in topup[t] and not c.get('fed_today'):
                if have_wheat > len(unfed):               # the flock's feed comes first
                    todo.append((t, ['FEED']))
                continue                                  # care without feed banks nothing
            if 'CARE' in topup[t] and not c.get('cared_today'):
                todo.append((t, ['CARE']))
    if todo:
        tile, cmd = min(todo, key=lambda x: (_shp_dist(pos, x[0]), x[0]))
        if pos != tile:
            return _shp_walk(pos, tile)
        _shp_count('ops_' + cmd[0].lower())
        return cmd
    if unfed and have_wheat == 0 and role['tries'] < 6 and pos not in _SHP_SHED:
        return _shp_walk(pos, home)                   # out of feed: back to the shed for more
    if hour == 23 and pos not in _SHP_SHED:           # cargo still out: it is auto-dropped at midnight
        for item in ('WOOL', 'FERTILIZER'):
            if int(inv.get(item, 0) or 0):
                state['credit'][item] = state['credit'].get(item, 0) + int(inv[item])
        state['wheat_credit'] = state.get('wheat_credit', 0) + have_wheat
        return ['PASS']
    load = cargo + have_wheat
    if load and (cargo or hour >= 20 or not unfed):
        step_home = _shp_walk(pos, home)
        if step_home:
            return step_home
        shed_total = sum(int(v or 0) for v in shed.values())
        if shed_total + load > 100 and hour < 22:
            return ['PASS']                           # wait for room rather than lose the overflow
        for item in ('WOOL', 'FERTILIZER'):
            if int(inv.get(item, 0) or 0):
                state['credit'][item] = state['credit'].get(item, 0) + int(inv[item])
        state['wheat_credit'] = state.get('wheat_credit', 0) + have_wheat
        role['tries'] = 9                             # done for the day: no more loading
        return ['DROP']
    return ['PASS']


def _shp_hidden(obs, player, own):
    """The observation the tape layer sees: without the overlay's hands."""
    farm = dict(obs['farms'][player])
    farm['hands'] = [h for i, h in enumerate(farm['hands']) if (i + 1) not in own]
    farms = list(obs['farms'])
    farms[player] = farm
    private = dict(obs['private'])
    private['inventories'] = [v for i, v in enumerate(private.get('inventories') or []) if i not in own]
    out = dict(obs)
    out['farms'], out['private'] = farms, private
    return out


def agent(observation, configuration=None):
    if not _SHP_CFG.get('enabled'):
        return _SHP_PARENT(observation, configuration)
    own, state = set(), None
    try:
        step = int(observation['step'])
        player = int(observation['player'])
        state = _SHP_STATES.get(player)
        if state is None or step <= state.get('last', -1):
            state = _SHP_STATES[player] = {'last': -1, 'workers': {}, 'tiles': [], 'placed': set(), 'placed_day': {},
                                           'lost': set(), 'own': set(), 'own_day': -1, 'credit': {}, 'wheat_credit': 0}
            _SHP_REPORT.clear()
        state['last'] = step
        if state.get('own_day') != step // 24:
            state['own_day'], state['own'], state['workers'] = step // 24, set(), {}
        _shp_confirm(state, observation, step)
        own = set(state['own'])
    except Exception as exc:
        _shp_count('errors')
        _SHP_REPORT['last_error'] = repr(exc)[:200]
        own = set()
    try:
        seen = _shp_hidden(observation, int(observation['player']), own) if own else observation
    except Exception:
        seen, own = observation, set()
    action = _SHP_PARENT(seen, configuration)
    try:
        step = int(observation['step'])
        player = int(observation['player'])
        farm = observation['farms'][player]
        if own:
            tape_cmds = [list(c or ['PASS']) for c in (action.get('hands') or [])]
            merged, j = [], 0
            for idx in range(1, len(farm['hands']) + 1):
                if idx in own:
                    role = state['workers'].get(idx)
                    cmd = _shp_work(state, observation, idx, role, step) if role else None
                    merged.append(cmd or ['PASS'])
                else:
                    merged.append(tape_cmds[j] if j < len(tape_cmds) else ['PASS'])
                    j += 1
            action = dict(action, hands=merged)
        action = _shp_decide(state, observation, action, step)
        action = _shp_daily_hire(state, observation, action, step)
        _MGT_IGNORE[player] = {y * 10 + x for x, y in state['tiles']}
        _tape_now = _shp_route(player)
        if _tape_now is not None:
            action = _shp_feed_guard(observation, action, step, _tape_now)
        shed_now = observation['private'].get('shed') or {}
        for item in ('WOOL', 'FERTILIZER'):
            q = min(int(state['credit'].get(item, 0)), int(shed_now.get(item, 0) or 0))
            market = [list(o) for o in (action.get('market') or [])]
            if q > 0 and len(market) < 10:
                market.append(['SELL', item, q])
                action = dict(action, market=market)
                state['credit'][item] -= q
                _shp_count('sold_' + item.lower(), q)
        if state.get('need_wheat'):
            market = [list(o) for o in (action.get('market') or [])]
            if len(market) < 10 and step % 24 < 12:
                market.append(['BUY_PRODUCT', 'WHEAT', int(state['need_wheat']) + 1])
                action = dict(action, market=market)
                _shp_count('feed_rebuys')
            state['need_wheat'] = 0
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

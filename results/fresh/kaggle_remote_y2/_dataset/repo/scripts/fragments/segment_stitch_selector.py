"""Selector body embedded by build_segment_stitch_agent.py.

The selector uses only the current observation and segment start snapshots.  It
never compares unrevealed shops or donor future actions.
"""
import copy as _ss_copy

_SS_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "FERTILIZER")
_SS_DAYS = (12, 15, 18, 21, 24, 27)
_SS_SEGMENTS = __SS_LIBRARY__
_SS_STATE_ONLY = __SS_STATE_ONLY__
_SS_BY_DAY = {}
for _ss_node in _SS_SEGMENTS:
    _SS_BY_DAY.setdefault(int(_ss_node.get("day", -1)), []).append(_ss_node)
_SS_STATES = {}
SEGMENT_REPORT = {"activations": 0, "preflight_failures": 0, "fallbacks": 0,
                  "decisions": [], "outputs": {}, "failures": [], 'attempts': []}


def _ss_tile_sig(t):
    if not isinstance(t, dict):
        return t
    return tuple((k, t.get(k)) for k in (
        "kind", "crop", "animal", "planted_day", "placed_day", "yield_units",
        "pending_care_bonus", "fed_today", "cared_today", "watered_today",
        "fertilizer_available", "consecutive_unfed") if k in t)


def _ss_state_sig(farm, private):
    tiles = farm.get("tiles", [])
    return tuple(_ss_tile_sig(t) for row in tiles for t in row), (
        tuple(sorted((private.get("shed") or {}).items())),
        tuple(sorted((private.get("seeds") or {}).items())),
        int(farm.get("money", 0)), len(farm.get("hands", [])))


def _ss_distance(obs, node):
    player = int(obs.get("player", 0)); farm = obs["farms"][player]
    nf = node.get("start_farm") or {}
    a = farm.get("tiles", []); b = nf.get("tiles", [])
    d = 0.0
    for y in range(min(len(a), len(b))):
        for x in range(min(len(a[y]), len(b[y]))):
            ta, tb = a[y][x], b[y][x]
            if _ss_tile_sig(ta) != _ss_tile_sig(tb):
                # Existing crops and animals dominate cosmetic board mismatch.
                d += 4.0 if isinstance(ta, dict) and (ta.get("crop") or ta.get("animal")) else 1.0
    d += 1.5 * abs(len(farm.get("hands", [])) - len(nf.get("hands", [])))
    for key in ("shed", "seeds"):
        aa = (obs.get("private") or {}).get(key, {})
        bb = (node.get("start_private") or {}).get(key, {})
        d += 0.15 * sum(abs(int(aa.get(k, 0)) - int(bb.get(k, 0))) for k in set(aa) | set(bb))
    return d


def _ss_compatible(obs, node):
    player = int(obs.get("player", 0)); farm = obs["farms"][player]
    nf = node.get("start_farm") or {}; a, b = farm.get("tiles", []), nf.get("tiles", [])
    if len(a) != len(b): return False
    for y in range(len(a)):
        if len(a[y]) != len(b[y]): return False
        for x in range(len(a[y])):
            ta, tb = a[y][x], b[y][x]
            # Never transplant onto a different incumbent crop/animal or age.
            if isinstance(ta, dict) and isinstance(tb, dict):
                for k in ("kind", "crop", "animal", "planted_day", "placed_day"):
                    if ta.get(k) != tb.get(k): return False
    return True


def _ss_value(node, obs):
    prices = obs.get('market', {}).get('prices', {})
    out = node.get('output') or {}
    value = sum(float(out.get(p, 0)) * float(prices.get(p, 0)) for p in _SS_PRODUCTS)
    seed_prices = {'WHEAT': 10, 'CARROT': 20, 'TOMATO': 50, 'STRAWBERRY': 100, 'MELON': 80}
    animal_prices = {'GOOSE': 300, 'COW': 400, 'SHEEP': 500}
    cost = 0
    investment = 0
    for j in node.get('jobs', []):
        cmd = j['cmd']; op = cmd[0]
        if op == 'PLANT': cost += seed_prices.get(cmd[1], 0)
        if op == 'FEED': cost += prices.get('WHEAT', 0)
        if op == 'FERTILIZE': cost += prices.get('FERTILIZER', 0)
        if op == 'PLACE' and cmd[1] in animal_prices: cost += animal_prices[cmd[1]]
    # Replacement-cost credit for positive terminal additions, shrinking with
    # time remaining. This is a heuristic, not a future-price prediction.
    def assets(farm):
        result = {}
        for row in farm.get('tiles', []):
            for tile in row:
                if isinstance(tile, dict):
                    p = tile.get('crop') or tile.get('animal')
                    if p: result[p] = result.get(p, 0) + 1
        return result
    before, after = assets(node['start_farm']), assets(node.get('end_farm', {}))
    for product, n in after.items():
        investment += max(0, n - before.get(product, 0)) * (seed_prices.get(product, animal_prices.get(product, 0)))
    return value - cost + min(1, max(0, (27 - int(obs['day'])) / 10)) * investment


def _ss_choose(obs, day):
    nearest = sorted(_SS_BY_DAY.get(day, ()), key=lambda n: (_ss_distance(obs, n), str(n['id'])))
    candidates = []
    for node in nearest:
        trial = _ss_remap(obs, node)
        if trial is not None:
            candidates.append((node, trial, _ss_distance(obs, node)))
        if len(candidates) >= 8: break
    SEGMENT_REPORT['attempts'].append({'day': day, 'remappable': len(candidates)})
    if not _SS_STATE_ONLY:
        candidates.sort(key=lambda v: (-(_ss_value(v[0], obs) - 100 * v[2]), str(v[0]['id'])))
    for node, trial, distance in candidates[:4]:
        trial['safety_assets'] = True
        for workers in (11, 12, 13):
            trial['hire_to'] = workers
            state = _SS_EXECUTOR["segment_executor_start"](obs, trial)
            if state.get("ok"):
                return node, trial, state
            SEGMENT_REPORT["preflight_failures"] += 1
            if state.get('failure', {}).get('reason') != 'day_capacity_exceeded': break
    return None


def _ss_sell(obs, state, action):
    player = int(obs.get('player', 0))
    view = _View(obs, player, _MGT_IMPL.chassis.cfg)
    available = _MGT_IMPL.chassis._projected_shed(action, view)
    day = int(obs['day']); hour = int(obs['hour'])
    # Inputs still needed by this day's unissued jobs must remain purchasable
    # from the shed until the assigned workers have collected them.
    reserve = {}
    for j in state['jobs']:
        if state['start_day'] + j['day'] != day or j['id'] in state['issued']: continue
        p = 'WHEAT' if j['cmd'][0] == 'FEED' else ('FERTILIZER' if j['cmd'][0] == 'FERTILIZE' else None)
        if p: reserve[p] = reserve.get(p, 0) + 1
    if day == 29 and hour >= 21: reserve = {}
    orders = list(action.get('market', []))
    sales = []
    for p in sorted(_SS_PRODUCTS, key=lambda p: -view.prices.get(p, 0)):
        qty = max(0, available.get(p, 0) - reserve.get(p, 0))
        if qty and len(orders) + len(sales) < 10: sales.append(['SELL', p, qty])
    action['market'] = sales + orders
    return action


def _ss_tile_sig_dict(t):
    if not isinstance(t, dict): return t
    return {k: t.get(k) for k in ("kind", "crop", "animal", "planted_day", "placed_day", "birth_day") if k in t}


def _ss_dispatch(observation, configuration=None):
    try:
        player = int(observation.get("player", 0)); day = int(observation.get("day", 0))
        state = _SS_STATES.get(player)
        if state and day - int(state.get("start_day", day)) in (0, 1, 2):
            action = _SS_EXECUTOR["segment_executor_action"](observation, state)
            if state.get("failure"):
                if not state.get('reported_failure'):
                    SEGMENT_REPORT['failures'].append({'day': day, 'failure': state['failure']})
                    SEGMENT_REPORT["fallbacks"] += 1
                    state['reported_failure'] = True
                return _SS_BASELINE(observation, configuration)
            return _ss_sell(observation, state, action)
        if day in _SS_DAYS and int(observation.get("hour", 0)) == 0:
            chosen = _ss_choose(observation, day)
            if chosen:
                node, trial, state = chosen
                _SS_STATES[player] = state
                SEGMENT_REPORT["activations"] += 1
                SEGMENT_REPORT["decisions"].append({"day": day, "id": node.get("id"), "distance": _ss_distance(observation, node), 'workers': trial['hire_to'], 'remap_distance': trial.get('_tile_remap_distance', 0)})
                SEGMENT_REPORT["outputs"][str(day)] = node.get("output", {})
                return _ss_sell(observation, state, _SS_EXECUTOR["segment_executor_action"](observation, state))
            SEGMENT_REPORT["fallbacks"] += 1
        return _SS_BASELINE(observation, configuration)
    except Exception as exc:
        SEGMENT_REPORT["fallbacks"] += 1
        SEGMENT_REPORT["last_error"] = repr(exc)[:240]
        return _SS_BASELINE(observation, configuration)


def segment_stitch_entry(observation, configuration=None):
    return _ss_dispatch(observation, configuration)

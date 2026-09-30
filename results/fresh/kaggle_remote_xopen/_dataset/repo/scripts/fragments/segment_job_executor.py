"""Portable three-day tile-job executor.

This fragment deliberately compiles jobs into fresh routes from the current
observation.  It does not read or replay a donor action tape.  It is a narrow,
strict executor: coordinates must already be compatible with the live farm and
any unschedulable or unfunded day sets ``state['failure']`` rather than emitting
an incomplete purchase plan.
"""

from collections import Counter, defaultdict
from copy import deepcopy
import random

MOVES = {(0, -1): "NORTH", (0, 1): "SOUTH", (1, 0): "EAST", (-1, 0): "WEST"}
SUPPORTED = {"PLANT", "WATER", "HARVEST", "FERTILIZE", "FEED", "CARE", "COLLECT_FERTILIZER", "DIG", "DROP", "BUILD_COOP", "BUILD_PASTURE", "PLACE"}
SEED_PRICE = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_PRICE = {"GOOSE": 300, "COW": 400, "SHEEP": 500}


def _get(observation, key, default=None):
    try:
        return observation.get(key, default)
    except AttributeError:
        return getattr(observation, key, default)


def _own(observation):
    player = int(_get(observation, "player", 0))
    return _get(observation, "farms", [])[player], _get(observation, "private", {}), player


def _tile(farm, pos):
    x, y = pos
    tiles = farm.get("tiles", [])
    return tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else "OUTSIDE"


def _signature(tile):
    if not isinstance(tile, dict):
        return tile
    return {k: tile.get(k) for k in ("kind", "crop", "animal", "planted_day", "placed_day") if k in tile}


def _walk(a, b):
    x, y = a
    out = []
    while x != b[0]:
        step = 1 if b[0] > x else -1
        out.append([MOVES[(step, 0)]])
        x += step
    while y != b[1]:
        step = 1 if b[1] > y else -1
        out.append([MOVES[(0, step)]])
        y += step
    return out


def _shed_access(board_size):
    # The board's central 2x2 shed-access cells, including all four corners.
    mid = board_size // 2
    return [(mid - 1, mid - 1), (mid, mid - 1), (mid - 1, mid), (mid, mid)]


def _nearest_shed(pos, board_size):
    return min(_shed_access(board_size), key=lambda q: (abs(pos[0] - q[0]) + abs(pos[1] - q[1]), q))


def _failure(reason, **details):
    return {"ok": False, "failure": {"reason": reason, **details}, "telemetry": {"issued": [], "rejected": [reason]}}


def _check_job(job, farm):
    cmd = job["cmd"][0]
    pos = tuple(job["tile"])
    tile = _tile(farm, pos)
    expected = job.get('pre_tile')
    if isinstance(expected, dict) and isinstance(tile, dict):
        if any(expected.get(k) != tile.get(k) for k in ('crop', 'animal')):
            return 'asset_identity_mismatch'
    if cmd not in SUPPORTED:
        return "unsupported_command"
    if cmd == "PLANT":
        return None if tile is None else "plant_target_not_empty"
    if cmd == "DIG":
        return None if job.get("authorized_dig") is True else "dig_not_explicitly_authorized"
    if cmd in ("WATER", "FERTILIZE"):
        if not (isinstance(tile, dict) and tile.get("kind") == "PLANT"):
            return "missing_live_plant"
        if job.get("crop") and tile.get("crop") != job["crop"]:
            return "crop_identity_mismatch"
    if cmd == "HARVEST":
        if not (isinstance(tile, dict) and (tile.get("kind") == "PLANT" or tile.get("animal"))):
            return "missing_live_harvestable_asset"
    if cmd in ("BUILD_COOP", "BUILD_PASTURE"):
        return None if tile is None else "structure_target_not_empty"
    if cmd == "PLACE":
        animal = job["cmd"][1] if len(job["cmd"]) > 1 else None
        # Extracted native jobs may contain a shed-style PLACE of a product.
        # It needs no animal purchase and is deferred to the engine projection.
        if animal not in ANIMAL_PRICE:
            return None
        expected = "COOP" if animal == "GOOSE" else "PASTURE"
        if job.get("build_before"):
            return None
        if not (isinstance(tile, dict) and tile.get("kind") == expected and not tile.get("animal")):
            return "missing_empty_matching_structure"
    if cmd in ("FEED", "CARE", "COLLECT_FERTILIZER"):
        if not (isinstance(tile, dict) and tile.get("animal")):
            return "missing_live_animal"
        if job.get("animal") and tile.get("animal") != job["animal"]:
            return "animal_identity_mismatch"
    return None


def _normalise_jobs(node):
    jobs = []
    for i, raw in enumerate(node.get("jobs", [])):
        try:
            day, hour = int(raw["day"]), int(raw["hour"])
            x, y = map(int, raw["tile"])
            cmd = list(raw["cmd"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("malformed_job")
        if not (0 <= day <= 2 and 0 <= hour <= 23 and len(cmd) >= 1):
            raise ValueError("job_outside_three_day_window")
        jobs.append(dict(raw, id=i, day=day, hour=hour, tile=[x, y], cmd=cmd, generated=False))
    for job in jobs:
        if job["cmd"][0] == "PLACE":
            job["build_before"] = any(other["tile"] == job["tile"] and other["day"] == job["day"] and
                                       other["hour"] < job["hour"] and other["cmd"][0] in ("BUILD_COOP", "BUILD_PASTURE")
                                       for other in jobs)
        if job["cmd"][0] == "DIG" and job.get("pre_tile") is not None:
            job["authorized_dig"] = True
    return jobs


def segment_executor_start(observation, node):
    """Return mutable executor state, or a failure object.

    ``node`` has ``jobs`` with relative day/hour/tile/cmd entries.  Optional
    ``start.farm`` supplies a sparse source signature; only the tile identities
    named there are checked, so unrelated live assets are never rebuilt.
    """
    try:
        farm, private, player = _own(observation)
        jobs = _normalise_jobs(node)
    except ValueError as exc:
        return _failure(str(exc))
    if not jobs:
        return _failure("no_jobs")
    # Do not validate future mutations against the day-zero board.  A later
    # WATER/PLACE may be the continuation of an earlier PLANT/BUILD chain.
    # Per-day preflight is performed when that day reaches the live observation.
    declared = (node.get("start") or {}).get("tiles", {})
    for key, expected in declared.items():
        try:
            x, y = map(int, key.split(",")) if isinstance(key, str) else map(int, key)
        except (TypeError, ValueError):
            return _failure("bad_start_tile_signature")
        if _signature(_tile(farm, (x, y))) != expected:
            return _failure("start_tile_signature_mismatch", tile=[x, y])
    state = {
        "ok": True, "player": player, "start_day": int(_get(observation, "day", 0)), "node": node,
        "jobs": jobs, "issued": set(), "plans": {}, "failure": None,
        "telemetry": {"issued": [], "generated_safety_jobs": 0, "purchases": [], "rejected": []},
    }
    _, failure = _preflight(observation, state, 0)
    if failure:
        state['ok'] = False
        state['failure'] = failure['failure']
    return state


def _safety_jobs(farm, rel_day, existing_ids):
    """Preserve vulnerable live assets omitted by the donor job map."""
    generated = []
    touched = defaultdict(set)
    for job in existing_ids: touched[tuple(job["tile"])].add(job["cmd"][0])
    for y, row in enumerate(farm.get("tiles", [])):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            ops = touched[(x, y)]
            if tile.get("kind") == "PLANT" and "WATER" not in ops and tile.get("consecutive_unwatered", 0) >= 1:
                generated.append({"id": "s%d_%d_%d_w" % (rel_day, x, y), "day": rel_day, "hour": 23,
                                  "tile": [x, y], "cmd": ["WATER"], "generated": True})
            elif tile.get("animal"):
                # Feed/care prevents a donor omission from silently abandoning
                # the incumbent herd.  Harvest held output before it is capped.
                if tile.get("yield_units", 0) > 0 and "HARVEST" not in ops:
                    generated.append({"id": "s%d_%d_%d_h" % (rel_day, x, y), "day": rel_day, "hour": 20,
                                      "tile": [x, y], "cmd": ["HARVEST"], "generated": True})
                if "FEED" not in ops:
                    generated.append({"id": "s%d_%d_%d_f" % (rel_day, x, y), "day": rel_day, "hour": 22, "tile": [x, y], "cmd": ["FEED"], "generated": True})
                if "CARE" not in ops:
                    generated.append({"id": "s%d_%d_%d_c" % (rel_day, x, y), "day": rel_day, "hour": 23, "tile": [x, y], "cmd": ["CARE"], "generated": True})
    return generated


def _requirements(jobs, private):
    seeds, carried = Counter(), Counter()
    for job in jobs:
        op = job["cmd"][0]
        if op == "PLANT":
            if len(job["cmd"]) < 2:
                return None, None, "plant_without_crop"
            seeds[job["cmd"][1]] += 1
        elif op == "FEED": carried["WHEAT"] += 1
        elif op == "FERTILIZE": carried["FERTILIZER"] += 1
        elif op == "PLACE" and len(job["cmd"]) >= 2 and job["cmd"][1] in ANIMAL_PRICE:
            if len(job["cmd"]) < 2: return None, None, "place_without_animal"
            carried[job["cmd"][1]] += 1
    orders = []
    cash = int(private.get("_unused_cash", 10**9))  # actual farm budget is applied by caller
    del cash
    return seeds, carried, None


def _market_orders(farm, private, seed_need, carried_need, reserve):
    cash = int(farm.get("money", 0)) - int(reserve)
    orders = []
    for crop, need in sorted(seed_need.items()):
        missing = max(0, need - int(private.get("seeds", {}).get(crop, 0)))
        price = SEED_PRICE.get(crop)
        if price is None:
            return None, "unknown_seed_price"
        if cash < missing * price:
            return None, "seed_budget_shortfall"
        if missing:
            orders.append(["BUY_SEED", crop, missing]); cash -= missing * price
    for item, need in sorted(carried_need.items()):
        missing = max(0, need - int(private.get("shed", {}).get(item, 0)))
        price = ANIMAL_PRICE.get(item, int((_get(farm, "_segment_prices", {}) or {}).get(item, 0)))
        # Prices are copied into state from observation, never guessed.
        if missing and price <= 0:
            return None, "missing_live_product_quote"
        if cash < missing * price:
            return None, "input_budget_shortfall"
        if missing:
            orders.append(["BUY_ANIMAL" if item in ANIMAL_PRICE else "BUY_PRODUCT", item, missing]); cash -= missing * price
    return orders, None


"""Additional functions loaded inside the executor namespace by its builder."""

def _route(chains, origin, inventory, board_size):
    required = Counter()
    for chain in chains:
        for job in chain:
            op = job['cmd'][0]
            if op == 'FEED': required['WHEAT'] += 1
            if op == 'FERTILIZE': required['FERTILIZER'] += 1
            if op == 'PLACE' and job['cmd'][1] in ANIMAL_PRICE:
                required[job['cmd'][1]] += 1
    commands, ids = [], []
    pos = origin
    def append(cmds, tags=None):
        commands.extend(cmds)
        ids.extend(tags if tags is not None else [None] * len(cmds))
    missing = {p: max(0, n - inventory.get(p, 0)) for p, n in required.items()}
    if any(missing.values()):
        shed = _nearest_shed(pos, board_size)
        append(_walk(pos, shed)); pos = shed
        append([['PICKUP', p, n] for p, n in sorted(missing.items()) if n])
    for chain in chains:
        target = tuple(chain[0]['tile'])
        append(_walk(pos, target)); pos = target
        append([j['cmd'] for j in chain], [j['id'] for j in chain])
    # Delivery is assigned after packing. At ordinary midnight the engine
    # deposits inventories automatically; only output above shed capacity
    # needs a worker to walk home. Every final-day output must be delivered.
    return commands, ids


def _build_day(observation, state, rel_day):
    farm, private, _ = _own(observation)
    hour = int(_get(observation, 'hour', 0))
    pending = [j for j in state['jobs'] if j['day'] == rel_day and j['id'] not in state['issued']]
    if state['node'].get('safety_assets', True):
        pending += _safety_jobs(farm, rel_day, pending)
    chains = defaultdict(list)
    for job in pending:
        # Product PLACE is logistics, not production. Routes use fresh DROP.
        if job['cmd'][0] == 'PLACE' and job['cmd'][1] not in ANIMAL_PRICE:
            continue
        chains[tuple(job['tile'])].append(job)
    for chain in chains.values():
        chain.sort(key=lambda j: (j['hour'], (0, j['id']) if isinstance(j['id'], int) else (1, str(j['id']))))
        bad = _check_job(chain[0], farm)
        if bad: return None, _failure(bad, tile=chain[0]['tile'])
    seeds, carried, bad = _requirements(pending, private)
    if bad: return None, _failure(bad)
    copied_farm = dict(farm, _segment_prices=_get(observation, 'market', {}).get('prices', {}))
    orders, bad = _market_orders(copied_farm, private, seeds, carried, state['node'].get('cash_reserve', 0))
    if bad: return None, _failure(bad)
    if len(orders) > 10: return None, _failure('market_order_cap')
    positions = [tuple(farm['farmer'])] + [tuple(q) for q in farm.get('hands', [])]
    inventories = list(private.get('inventories', []))
    inventories += [{} for _ in range(max(0, len(positions) - len(inventories)))]
    capacity = 23 if int(_get(observation, 'day', 0)) == 29 else 24
    start = hour + bool(orders)
    limit = capacity - start
    board_size = len(farm['tiles'])
    # Tile chains remain intact; worker routes are recomputed from live starts.
    # Deterministic restarts only change packing order, never production targets.
    chain_list = list(chains.values())
    best = None
    rng = random.Random(1241 + int(_get(observation, 'day', 0)))
    for attempt in range(3):
        ordering = list(chain_list)
        if attempt == 0:
            ordering.sort(key=lambda c: (-len(c), -sum(abs(c[0]['tile'][k] - 4.5) for k in (0, 1))))
        elif attempt == 1:
            ordering.sort(key=lambda c: (c[0]['tile'][1], c[0]['tile'][0]))
        else:
            rng.shuffle(ordering)
        assigned = [[] for _ in positions]
        lengths = [0 for _ in positions]
        for chain in ordering:
            options = []
            for u in range(len(positions)):
                for insertion in range(len(assigned[u]) + 1):
                    trial = assigned[u][:insertion] + [chain] + assigned[u][insertion:]
                    cmds, _ = _route(trial, positions[u], inventories[u], board_size)
                    n = len(cmds)
                    # Prefer fitting an existing trip; avoid reserving every
                    # worker for one nearby tile and stranding remote chains.
                    options.append((max(0, n - limit), n - lengths[u], n, u, insertion))
            _, _, n, u, insertion = min(options)
            assigned[u].insert(insertion, chain)
            lengths[u] = n
        # Repair overloaded routes by relocating one complete tile chain. This
        # preserves tile chronology while releasing a badly packed worker.
        for repair in range(30):
            if max(lengths, default=0) <= limit: break
            old_score = (sum(max(0, n - limit) for n in lengths), max(lengths), sum(lengths))
            move = None
            for source in sorted(range(len(positions)), key=lambda u: -lengths[u]):
                if lengths[source] <= limit: continue
                for index, chain in enumerate(assigned[source]):
                    remainder = assigned[source][:index] + assigned[source][index + 1:]
                    short_length = len(_route(remainder, positions[source], inventories[source], board_size)[0])
                    for target in range(len(positions)):
                        if target == source: continue
                        for insertion in range(len(assigned[target]) + 1):
                            trial = assigned[target][:insertion] + [chain] + assigned[target][insertion:]
                            target_length = len(_route(trial, positions[target], inventories[target], board_size)[0])
                            proposed = list(lengths)
                            proposed[source], proposed[target] = short_length, target_length
                            score = (sum(max(0, n - limit) for n in proposed), max(proposed), sum(proposed))
                            if score < old_score and (move is None or score < move[0]):
                                move = (score, source, index, target, insertion, short_length, target_length)
            if move is None: break
            _, source, index, target, insertion, short_length, target_length = move
            chain = assigned[source].pop(index)
            assigned[target].insert(insertion, chain)
            lengths[source], lengths[target] = short_length, target_length
        score = (max(lengths, default=0), sum(lengths))
        if best is None or score < best[0]: best = score, assigned
        if score[0] <= limit: break
    if best is None or best[0][0] > limit:
        return None, _failure('day_capacity_exceeded', required=max(best[0][0], 0) if best else 0, available=limit)
    plan = [[['PASS'] for _ in range(capacity)] for _ in positions]
    scheduled = {}
    midnight_output = 0
    for u, worker_chains in enumerate(best[1]):
        commands, ids = _route(worker_chains, positions[u], inventories[u], board_size)
        held_output = sum(sum(j.get('effect', {}).values())
                          if j['cmd'][0] == 'HARVEST' else 1 if j['cmd'][0] == 'COLLECT_FERTILIZER' else 0
                          for c in worker_chains for j in c)
        if held_output:
            last = tuple(worker_chains[-1][0]['tile'])
            delivery = _walk(last, _nearest_shed(last, board_size)) + [['DROP']]
            if len(commands) + len(delivery) <= limit:
                commands += delivery
                ids += [None] * len(delivery)
            else:
                midnight_output += held_output
        for offset, (cmd, job_id) in enumerate(zip(commands, ids)):
            plan[u][start + offset] = cmd
            if job_id is not None: scheduled[(u, start + offset)] = job_id
    if midnight_output > (0 if int(_get(observation, 'day', 0)) == 29 else 90):
        return None, _failure('delivery_capacity_exceeded', unbanked=midnight_output)
    return {'day': rel_day, 'plan': plan, 'jobs': pending, 'orders': orders, 'scheduled': scheduled}, None


def _preflight(observation, state, rel_day):
    """Check resource and routing feasibility before spending on new workers."""
    projected = deepcopy(dict(observation))
    farm, private, player = _own(projected)
    desired = int(state['node'].get('hire_to', 11))
    n = len(farm.get('hands', [])) + 1
    needed = max(0, desired - n)
    hour = int(_get(observation, 'hour', 0))
    if needed and hour > 1:
        return None, _failure('hiring_window_missed')
    if needed:
        a, b = 1, 1
        costs = []
        for k in range(int(farm.get('hires_today', 0)) + needed):
            costs.append(a); a, b = b, a + b
        cost = sum(costs[-needed:])
        if farm['money'] < cost: return None, _failure('hire_budget_shortfall')
        farm['money'] -= cost
        farm['hands'] = list(farm.get('hands', []))
        for _ in range(needed):
            all_pos = [tuple(farm['farmer'])] + list(map(tuple, farm['hands']))
            cells = _shed_access(len(farm['tiles']))
            pos = min(cells, key=lambda q: (all_pos.count(q), cells.index(q)))
            farm['hands'].append(list(pos))
        private['inventories'] = list(private.get('inventories', [])) + [{} for _ in range(needed)]
        projected['hour'] = hour + (needed + 9) // 10
    return _build_day(projected, state, rel_day)


def segment_executor_action(observation, state):
    farm, private, _ = _own(observation)
    day = int(_get(observation, 'day', 0))
    hour = int(_get(observation, 'hour', 0))
    empty = {'farmer': ['PASS'], 'hands': [['PASS'] for _ in farm.get('hands', [])]}
    if not state or not state.get('ok') or state.get('failure'): return empty
    rel_day = day - state['start_day']
    if rel_day not in (0, 1, 2): return empty
    if rel_day not in state['plans']:
        _, failure = _preflight(observation, state, rel_day)
        if failure:
            state['failure'] = failure['failure']; return empty
        needed = max(0, int(state['node'].get('hire_to', 11)) - 1 - len(farm.get('hands', [])))
        if needed:
            empty['market'] = [['HIRE'] for _ in range(min(10, needed))]
            return empty
        built, failure = _build_day(observation, state, rel_day)
        if failure:
            state['failure'] = failure['failure']; return empty
        state['plans'][rel_day] = built
        state['telemetry']['purchases'] += built['orders']
    built = state['plans'][rel_day]
    if hour >= len(built['plan'][0]): return empty
    commands = [row[hour] for row in built['plan']]
    for unit, cmd in enumerate(commands):
        job_id = built['scheduled'].get((unit, hour))
        if job_id is not None:
            state['issued'].add(job_id)
            state['telemetry']['issued'].append({'day': rel_day, 'job': job_id, 'cmd': cmd})
    action = {'farmer': commands[0], 'hands': commands[1:]}
    if not built.get('orders_emitted'):
        action['market'] = built['orders']
        built['orders_emitted'] = True
    return action


def segment_executor_status(state):
    """Serializable telemetry; a successful compile is not engine validation."""
    if not state: return {"ok": False, "reason": "no_state"}
    return {"ok": bool(state.get("ok") and not state.get("failure")), "failure": state.get("failure"),
            "issued_jobs": len(state.get("issued", ())), "telemetry": state.get("telemetry", {})}

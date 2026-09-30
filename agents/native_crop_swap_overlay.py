"""Bounded native-route wheat-to-carrot cohort substitution overlay.

Append this file to agents/v45_event_opening_fixed.py.  It changes only crop
commands on audited cells and appends bounded CARROT seed purchases.  Movement,
hires, land orders, and all inherited market orders (including WHEAT) remain
unchanged.

Audited native windows (official-engine seeds 157900/157901):
* day-13 WHEAT replants at (1,2), (1,3), (2,2) have age-3 visits on day 16;
* day-15 WHEAT replants at (3,9), (4,9) have age-3 visits on day 18.

CARROT decays at the beginning of age 4.  A managed age-3 WATER is therefore
changed to HARVEST.  The next native PLANT is never advanced.  The target order
makes max_plots=2 a contiguous day-13 pair and max_plots=4 add the third day-13
cell plus one day-15 cell.
"""
from copy import deepcopy as _cohort_deepcopy


_SWAP_CONFIG = {
    "max_plots": 2,                 # supported experiment values: 2 or 4
    "start_day": 12,
    "require_carrot_shop": True,   # PET_CAFE or FARMERS_MARKET currently visible
    "reserve_money": 4000,
    "seed_topup": 2,               # at most two CARROT seeds requested per turn
    "last_plant_day": 26,          # age-3 harvest must fit by day 29
}
_COHORT_TARGETS = ((1, 2), (1, 3), (2, 2), (3, 9), (4, 9))
_COHORT_PARENT = agent
_COHORT_STATES = {}
_COHORT_STATS = {
    "commitments": 0,
    "harvest_units": 0,
    "expired_unharvested_yield": 0,
    "seedpurchases": 0,
    "changedcommands": 0,
    "overnight_auto_drop_harvests": 0,
    "overnight_auto_drop_units": 0,
    "carrotsellrequests": 0,
    "contract_errors": 0,
}
_COHORT_LAST_ERROR = {"value": ""}


def _cohort_reset(player, step):
    for key in _COHORT_STATS:
        _COHORT_STATS[key] = 0
    _COHORT_LAST_ERROR["value"] = ""
    limit = int(_SWAP_CONFIG.get("max_plots", 2))
    if limit not in (2, 4):
        limit = 2
    state = {
        "step": step,
        "selected": set(_COHORT_TARGETS[:limit]),
        "enabled": False,
        "ever_committed": False,
        "managed": {},
        "pending_plants": [],
        "pending_harvests": [],
        "last_tiles": {},
    }
    _COHORT_STATES[player] = state
    return state


def _cohort_tile(farm, cell):
    x, y = cell
    return farm["tiles"][y][x]


def _cohort_carrot_shop(obs):
    shops = obs.get("town", {}).get("unlocked_shops", [])
    return any(shop in ("PET_CAFE", "FARMERS_MARKET") for shop in shops)


def _cohort_observe(obs, state):
    """Confirm requested work and count decay before creating this turn's action."""
    farm = obs["farms"][int(obs["player"])]
    step = int(obs["step"])

    pending_plants = state.get("pending_plants", [])
    state["pending_plants"] = []
    for pending in pending_plants:
        cell = tuple(pending["cell"])
        tile = _cohort_tile(farm, cell)
        if (isinstance(tile, dict) and tile.get("kind") == "PLANT"
                and tile.get("crop") == "CARROT"
                and int(tile.get("planted_day", -1)) == pending["day"]):
            state["managed"][cell] = pending["day"]
            state["ever_committed"] = True
            _COHORT_STATS["commitments"] += 1

    pending_harvests = state.get("pending_harvests", [])
    state["pending_harvests"] = []
    for pending in pending_harvests:
        cell = tuple(pending["cell"])
        tile = _cohort_tile(farm, cell)
        still_same = (isinstance(tile, dict) and tile.get("kind") == "PLANT"
                      and tile.get("crop") == "CARROT"
                      and int(tile.get("planted_day", -1)) == pending["planted_day"])
        if not still_same and not (isinstance(tile, dict) and tile.get("kind") == "WEED"):
            _COHORT_STATS["harvest_units"] += pending["units"]
            if pending["overnight"]:
                _COHORT_STATS["overnight_auto_drop_harvests"] += 1
                _COHORT_STATS["overnight_auto_drop_units"] += pending["units"]
            state["managed"].pop(cell, None)

    for cell in state["selected"]:
        old = state["last_tiles"].get(cell)
        tile = _cohort_tile(farm, cell)
        if (isinstance(old, dict) and old.get("kind") == "PLANT"
                and old.get("crop") == "CARROT"
                and isinstance(tile, dict) and tile.get("kind") == "WEED"):
            _COHORT_STATS["expired_unharvested_yield"] += max(0, int(old.get("yield_units", 0)))
            state["managed"].pop(cell, None)
        state["last_tiles"][cell] = _cohort_deepcopy(tile)

    state["step"] = step


def _cohort_project(obs, action, state):
    """Apply actor commands in engine order so same-turn harvest/plant is visible."""
    player = int(obs["player"])
    day = int(obs["step"]) // 24
    farm, private = _PLANNER_NS["_clone_state"](obs["farms"][player], obs["private"])
    commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
    changed = [list(c) for c in commands]
    native_carrot_requests = sum(
        bool(c) and len(c) > 1 and c[:2] == ["PLANT", "CARROT"] for c in commands)
    swap_seed_budget = max(0, int(private["seeds"].get("CARROT", 0)) - native_carrot_requests)

    for actor, original in enumerate(commands[:len(private["inventories"])]):
        positions = [farm["farmer"], *farm["hands"]]
        if actor >= len(positions):
            break
        cell = tuple(positions[actor])
        tile = _cohort_tile(farm, cell)
        command = list(original)

        if (state["enabled"] and cell in state["selected"]
                and day >= int(_SWAP_CONFIG.get("start_day", 12))
                and day <= int(_SWAP_CONFIG.get("last_plant_day", 26))
                and command[:2] == ["PLANT", "WHEAT"]
                and tile is None and swap_seed_budget > 0):
            command = ["PLANT", "CARROT"]
            swap_seed_budget -= 1
            state["pending_plants"].append({"cell": list(cell), "day": day,
                                             "step": int(obs["step"]), "actor": actor})

        managed = cell in state["managed"]
        tile = _cohort_tile(farm, cell)
        if (managed and isinstance(tile, dict) and tile.get("kind") == "PLANT"
                and tile.get("crop") == "CARROT"):
            age = day - int(tile.get("planted_day", day))
            if command and command[0] == "WATER" and age == 3:
                command = ["HARVEST"]
            elif command and command[0] == "DIG":
                # A native weed-repair DIG must not remove the live managed crop.
                command = ["PASS"]

            if command and command[0] == "HARVEST" and age >= 2 and int(tile.get("yield_units", 0)) > 0:
                state["pending_harvests"].append({
                    "cell": list(cell),
                    "planted_day": int(tile.get("planted_day", day)),
                    "units": int(tile.get("yield_units", 0)),
                    "step": int(obs["step"]),
                    "overnight": int(obs["step"]) % 24 == 23,
                })

        if command != original:
            changed[actor] = command
            _COHORT_STATS["changedcommands"] += 1
        _PLANNER_NS["_apply_unit_action"](
            farm, private, actor, command, 10, day, 24, 100)

    result = _cohort_deepcopy(action)
    result["farmer"] = changed[0]
    result["hands"] = changed[1:]
    return result


def _cohort_seed_topup(obs, action, state):
    if not state["enabled"]:
        return action
    day = int(obs["step"]) // 24
    if not int(_SWAP_CONFIG.get("start_day", 12)) <= day <= int(_SWAP_CONFIG.get("last_plant_day", 26)):
        return action
    private = obs["private"]
    desired = len(state["selected"])
    commands = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
    projected_consumption = sum(
        bool(c) and len(c) > 1 and c[:2] == ["PLANT", "CARROT"] for c in commands)
    market = list(action.get("market") or [])
    inherited_seed_orders = sum(
        max(0, int(o[2])) for o in market
        if len(o) > 2 and o[:2] == ["BUY_SEED", "CARROT"])
    projected_stock = (max(0, int(private["seeds"].get("CARROT", 0)) - projected_consumption)
                       + inherited_seed_orders)
    need = max(0, desired - projected_stock)
    quantity = min(max(0, int(_SWAP_CONFIG.get("seed_topup", 2))), need)
    if quantity <= 0:
        return action
    farm = obs["farms"][int(obs["player"])]
    reserve = int(_SWAP_CONFIG.get("reserve_money", 4000))
    quantity = min(quantity, max(0, int((float(farm["money"]) - reserve) // 20)))
    if quantity <= 0 or len(market) >= 10:
        return action
    result = _cohort_deepcopy(action)
    result["market"] = market + [["BUY_SEED", "CARROT", quantity]]
    _COHORT_STATS["seedpurchases"] += quantity
    return result


def _cohort_sell(obs, action, state):
    """Sell CARROT after native drops without changing routes or parent orders."""
    if not state.get("ever_committed"):
        return action
    market = list(action.get("market") or [])
    if len(market) >= 10 or any(o and len(o) > 1 and o[:2] == ["SELL", "CARROT"] for o in market):
        return action
    # Existing baseline helper projects this turn's exact unit commands on a
    # cloned own farm. It is source-local and adds no engine import/dependency.
    _, projected_private = _r127_fields(obs, action)
    quantity = max(0, int(projected_private["shed"].get("CARROT", 0)))
    if quantity <= 0:
        return action
    result = _cohort_deepcopy(action)
    result["market"] = market + [["SELL", "CARROT", quantity]]
    _COHORT_STATS["carrotsellrequests"] += quantity
    return result


def _cohort_contract(parent, result):
    """Ensure this overlay never changes movement, hiring, land, or parent orders."""
    before = [parent.get("farmer") or ["PASS"], *(parent.get("hands") or [])]
    after = [result.get("farmer") or ["PASS"], *(result.get("hands") or [])]
    if len(before) != len(after):
        return False
    allowed = {("PLANT", "WHEAT", "PLANT", "CARROT"),
               ("WATER", None, "HARVEST", None),
               ("DIG", None, "PASS", None)}
    moves = {"NORTH", "SOUTH", "EAST", "WEST"}
    for a, b in zip(before, after):
        if a == b:
            continue
        key = (a[0], a[1] if len(a) > 1 else None,
               b[0], b[1] if len(b) > 1 else None)
        if key not in allowed or a[0] in moves or b[0] in moves:
            return False
    old_market = list(parent.get("market") or [])
    new_market = list(result.get("market") or [])
    return (new_market[:len(old_market)] == old_market
            and all(o[:2] in (["BUY_SEED", "CARROT"], ["SELL", "CARROT"])
                    for o in new_market[len(old_market):])
            and len(new_market) <= 10)


def agent(observation, configuration=None):
    parent = _COHORT_PARENT(observation, configuration)
    try:
        player = int(observation["player"])
        step = int(observation["step"])
        state = _COHORT_STATES.get(player)
        if state is None or step <= state["step"]:
            state = _cohort_reset(player, step)
        _cohort_observe(observation, state)
        day = step // 24
        gate = (not bool(_SWAP_CONFIG.get("require_carrot_shop", True))) or _cohort_carrot_shop(observation)
        if day >= int(_SWAP_CONFIG.get("start_day", 12)) and gate:
            state["enabled"] = True
        result = _cohort_project(observation, parent, state)
        result = _cohort_seed_topup(observation, result, state)
        result = _cohort_sell(observation, result, state)
        if not _cohort_contract(parent, result):
            _COHORT_STATS["contract_errors"] += 1
            _COHORT_LAST_ERROR["value"] = "contract rejected proposed action"
            result = parent
    except Exception as error:
        _COHORT_STATS["contract_errors"] += 1
        _COHORT_LAST_ERROR["value"] = type(error).__name__ + ": " + str(error)
        result = parent
    agent.telemetry = dict(getattr(_COHORT_PARENT, "telemetry", {}),
                           **{"cohort_" + k: v for k, v in _COHORT_STATS.items()},
                           cohort_last_error=_COHORT_LAST_ERROR["value"])
    return result


agent.telemetry = {}

# Explicit final callable for Kaggle's last-callable loader after concatenation.
agent = globals().pop("agent")

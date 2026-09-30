# ===== XOPEN FOLLOWER CORE (scripts/xopen_follow.py; pasted verbatim into the xopen agents by scripts/xopen_build.py) ===
"""xopen follower: follow a recorded leader game EXACTLY until the cash-safe date D, repair breakages with an
expected-value failsafe, then hand off to our closed-loop executor. Thread xopen, 2026-09-25. Stdlib only.

Design: results/fresh/xopen_20260925/design.md, with the review's required changes applied:
  B1  PLANT feasibility per crop per step across ALL units against the seeds held at step start (the engine turns
      every PLANT of a crop into PASS when the step's requests exceed the seeds): a dry pass counts the plantings,
      the in-sync recorded ones go first, then by value; the others are substituted (recorded ones become catch-up
      jobs). When our seeds and plantings equal the recording's at that step the recorded commands stay verbatim.
  B2  role k = the k-th successful hire of the day (capped at the recording's crew); a spawn-tile mismatch is an
      offset that is walked away (lagged replay, lag <= lag_max) or rendezvoused; every offset is logged.
  B3  destructive recorded ops (DIG, HARVEST of a one-time crop) run only when our tile's (label, planted / placed
      day) equals the recording's; DIG as a substitute or a job only on WEED tiles.
  B4  substitutes use only the unit's inventory surplus over what its role carried at that recorded step; released
      units never act on tiles in-sync roles still claim today and never pick up shed stock the in-sync roles'
      remaining recorded pickups need today. (No shadow executor runs before D: released units work the job pool.)
  B5  own fills are inferred from observation deltas with an exact engine-rule simulation of our unit phase: seeds =
      seeds after the market - seeds after the simulated unit phase; animals / products from the shed after the
      simulated unit phase; wheat and fertilizer solved in list order; hires = farm["hires_today"]; land =
      dunlocked. scripts/xopen_compile.py checks the inference against the engine-hooked leader fills.
  B6  the glue re-enables the deploy's own retrieval for the reveal days not yet reached on an early (abort) handoff.
  B7  the delay cost of a deferred purchase uses a falling price path (median leader sale price / base by day,
      data/leader_semantics) over the expected deferral length k and a cash-timing weight (a coin arriving on day
      j < D is worth 1 + cash_rate x (D - j)); a purchase whose dependent asset is still on time after k days costs
      nothing to defer, ties go FIFO by the dependent op's step; the queue is re-ranked every step (a delay cost
      rises as its date nears, so nothing starves) and cancelled only when no date is left.
  non-blocking 1-7: catch-up orders go in at the next step (cumulative deficits); day-6 ties prefer day-6 cash <=
      ours; fixed D = 11 by default with the dynamic rule logged in shadow (R_plan without land beyond land_max, the
      deferral queue included); the check runs to day 14 (the successor's committed spend on the followed plan);
      per-tile hidden state is compared at every day start; plans are compiled to day 13 (full games for the
      leader-world controls); the SELL stock prediction is the simulated unit phase (same-step pickups included).
Identity: when our state equals the recording's at a step (money, shed, seeds, hires, land; nothing deferred) the
recorded action is emitted verbatim, so the no-breakage control reproduces the leader to the dollar.
"""
import os as _xo_os
import gzip as _xo_gzip
import json as _xo_json
import time as _xo_time
from collections import Counter as _XC

XO_CFG = {
    "mode": "off",           # "off" | "replay" (tape verbatim) | "replay_capped" (tape unit commands + capped market) | "follow"
    "D_fixed": 11,           # handoff at hour 0 of this day (fixed rule)
    "dyn": False,            # True: the dynamic cash-safe rule decides D (floor D_floor, cap D_cap); always logged in shadow
    "D_floor": 10, "D_cap": 13,
    "dyn_h_min": 0.30, "dyn_margin": 1.25, "dyn_horizon": 14,
    "reretrieve6": True,     # day 6, hour 0: re-pick among state-identical pool games by our two shops
    "reretrieve9": True,     # day 9: switch only to an exactly state-identical game with a lower 3-shop distance
    "pool_max_diff": 2,      # tiles allowed to differ at the day-6 match
    "land_max": 2,
    "drop_land": [],         # replay mode: quadrant indexes (0 NE, 1 SW, 2 SE) whose BUY_LAND is dropped
    "failsafe": "ev",        # "ev" (rank by EV lost per coin freed) | "naive" (tier 0 first, then list order)
    "hold": 0.0,             # E1-stress: withhold this share of each sale's proceeds from spending until D
    "cash_rate": 0.05,       # EV cash-timing term (per day a coin of revenue arrives before D)
    "lag_max": 3,            # a late / offset hand replays its role lagged when the lag is at most this
    "rv_hour": 20,           # no rendezvous after this hour: the hand is released for the day
    "surv_hour": 16,         # survival net from this hour
    "abort_ham": 8, "abort_owned": 12,
    "plans_dir": None,       # default <root>/results/fresh/xopen_20260925/plans
    "plan": "16732748_112655730",   # day-0 recording (team_episode): DSM's seat of 112655730, the deploy's exemplar
    "exclude_ep": None,      # never re-retrieve this episode (env XO_EXCLUDE_EP; leakage guard)
    "log_max": 4000,
}

_XO_CROPS = {
    "WHEAT": {"seed": 10, "first": 2, "maxday": 4, "interval": 0, "max": 6, "ongoing": False},
    "CARROT": {"seed": 20, "first": 2, "maxday": 3, "interval": 0, "max": 4, "ongoing": False},
    "TOMATO": {"seed": 50, "first": 8, "maxday": 8, "interval": 1, "max": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "maxday": 10, "interval": 2, "max": 4, "ongoing": True},
    "MELON": {"seed": 80, "first": 10, "maxday": 12, "interval": 0, "max": 6, "ongoing": False},
}
_XO_ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}
_XO_PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
_XO_BASE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250, "EGG": 50, "MILK": 160,
            "WOOL": 200, "FERTILIZER": 100}
_XO_SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
_XO_SHEDSET = set(_XO_SHED)
_XO_MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
_XO_LAND_ORDER = ["NE", "SW", "SE"]
_XO_LAND_PRICES = [1000, 2000, 4000]
_XO_CUTOFF = {"STRAWBERRY": 13, "TOMATO": 18, "MELON": 19, "WHEAT": 25, "CARROT": 26}
_XO_LAST_ANIMAL = {"SHEEP": 17, "COW": 18, "GOOSE": 20}
_XO_CATCHUP = {"STRAWBERRY": 6, "TOMATO": 5, "MELON": 3, "WHEAT": 1, "CARROT": 1}
_XO_TILE_OPS = {"PLANT", "WATER", "HARVEST", "FERTILIZE", "DIG", "BUILD_COOP", "BUILD_PASTURE", "FEED",
                "COLLECT_FERTILIZER", "CARE"}
_XO_ASSET_OPS = {"PLANT", "BUILD_COOP", "BUILD_PASTURE"}
_XO_ONETIME_UNITS = {"WHEAT": 4, "CARROT": 3, "MELON": 6}      # one-time crop units with full watering, unfertilized
_XO_LAB_CROP = {"ST": "STRAWBERRY", "TO": "TOMATO", "ME": "MELON", "WH": "WHEAT", "CA": "CARROT"}
# median leader sale price / base price by day (data/leader_semantics, 540 games, offset-corrected, gaps filled,
# 3-day smoothed); the build writes the table from results/fresh/xopen_20260925/price_curve.json into this name.
_XO_PRICE_CURVE = None


# =========================================================================================== small helpers
def _xo_g(o, k, default=None):
    try:
        v = o[k]
        return default if v is None else v
    except (KeyError, TypeError, IndexError):
        return getattr(o, k, default)


def _xo_fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _xo_dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _xo_step_toward(p, q):
    """one move from p toward q (x first, then y); None when p == q."""
    if p[0] < q[0]:
        return ["EAST"]
    if p[0] > q[0]:
        return ["WEST"]
    if p[1] < q[1]:
        return ["SOUTH"]
    if p[1] > q[1]:
        return ["NORTH"]
    return None


def _xo_near_shed(p):
    return min(_XO_SHED, key=lambda s: (_xo_dist(p, s), _XO_SHED.index(s)))


def _xo_quad(idx):
    x, y = idx % 10, idx // 10
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def _xo_label(t):
    """corpus tile label (data/leader_semantics): a WEED reads as empty."""
    if t == "LOCKED":
        return " L"
    if t is None:
        return " ."
    kind = t.get("kind")
    if kind == "PLANT":
        return str(t.get("crop"))[:2]
    if kind == "WEED":
        return " ."
    if t.get("animal"):
        return str(t["animal"])[:2].lower()
    return str(kind)[:2].lower()


def _xo_tsig(t):
    """tile signature (label, planted / placed day); a WEED is its own label here."""
    if isinstance(t, dict):
        if t.get("kind") == "WEED":
            return ["WD", None]
        if t.get("kind") == "PLANT":
            return [str(t.get("crop"))[:2], t.get("planted_day")]
        if t.get("animal"):
            return [str(t["animal"])[:2].lower(), t.get("placed_day")]
        return [str(t.get("kind"))[:2].lower(), None]
    return [_xo_label(t), None]


def _xo_statekey(tiles):
    """day-start state key: per tile (label, planted / placed day); = scripts/xopen_open_stats._state on a live board."""
    out = []
    for row in tiles:
        for t in row:
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                out.append([_xo_label(t), t.get("planted_day")])
            elif isinstance(t, dict) and t.get("animal"):
                out.append([_xo_label(t), t.get("placed_day")])
            else:
                out.append([_xo_label(t), None])
    return out


def _xo_hidden(t):
    """per-tile hidden state compared at day start (watering parity, fertilized_until, care bank, unfed, yield)."""
    if isinstance(t, dict) and t.get("kind") == "PLANT":
        return [t.get("crop"), t.get("planted_day"), t.get("consecutive_unwatered"), t.get("yield_units"),
                t.get("fertilized_until_day")]
    if isinstance(t, dict) and t.get("animal"):
        return [t.get("animal"), t.get("placed_day"), t.get("consecutive_unfed"), t.get("pending_care_bonus", 0),
                t.get("yield_units")]
    return None


def _xo_tile(tiles, idx):
    return tiles[idx // 10][idx % 10]


def _xo_is_plant(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT"


def _xo_is_weed(t):
    return isinstance(t, dict) and t.get("kind") == "WEED"


def _xo_animal(t):
    return t.get("animal") if isinstance(t, dict) else None


def _xo_cnt(d):
    return _XC({k: int(v) for k, v in dict(d or {}).items() if v})


def _xo_parse(obs):
    me = int(_xo_g(obs, "player", 0))
    farm = _xo_g(obs, "farms")[me]
    priv = _xo_g(obs, "private", {}) or {}
    step = int(_xo_g(obs, "step", 0))
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
    invs = [_xo_cnt(i) for i in (_xo_g(priv, "inventories", []) or [])]
    while len(invs) < len(pos):
        invs.append(_XC())
    shops = []
    for s in list(_xo_g(_xo_g(obs, "town", {}), "unlocked_shops", []) or []):
        if isinstance(s, dict):
            s = s.get("name") or s.get("type") or s.get("kind")
        shops.append(str(s))
    return dict(step=step, day=step // 24, hour=step % 24, me=me, money=float(farm["money"]), tiles=farm["tiles"],
                pos=pos, invs=invs[:len(pos)], shed=_xo_cnt(_xo_g(priv, "shed", {})),
                seeds=_xo_cnt(_xo_g(priv, "seeds", {})), unlocked=list(farm.get("unlocked_quadrants", ["NW"])),
                prices=dict(_xo_g(_xo_g(obs, "market", {}), "prices", {}) or {}), shops=shops,
                hires_today=int(farm.get("hires_today", 0) or 0))


# =========================================================================================== engine-rule unit phase
def _xo_new_plant(crop, day, tpd=24):
    cd = _XO_CROPS[crop]
    return {"kind": "PLANT", "crop": crop, "planted_day": day, "watered_today": False, "consecutive_unwatered": 1,
            "yield_units": 0 if cd["ongoing"] else 1,
            "max_lifespan_step": (-1 if cd["ongoing"] else (day + cd["maxday"] + 1) * tpd), "fertilized_until_day": -1}


def _xo_new_animal(animal, day):
    return {"kind": _XO_ANIMALS[animal]["structure"], "animal": animal, "placed_day": day, "yield_units": 0,
            "consecutive_unfed": 0, "fed_today": False, "cared_today": False, "fertilizer_available": False,
            "pending_care_bonus": 0}


def _xo_sim_state(P):
    """copy of the mutable part of a parsed observation for the unit-phase simulation."""
    return dict(tiles=[[(dict(t) if isinstance(t, dict) else t) for t in row] for row in P["tiles"]],
                shed=_XC(P["shed"]), seeds=_XC(P["seeds"]), pos=[tuple(p) for p in P["pos"]],
                invs=[_XC(i) for i in P["invs"]])


def _xo_apply_one(st, idx, action, day, tpd=24, cap=100):
    """engine _apply_unit_action (data/kaggriculture.py, engine 1.32.7) on the simulation state; returns the effect."""
    ef = {"op": None, "eff": False, "tile": None, "gain": _XC(), "use": _XC(), "pick": _XC(), "dep": _XC(), "lost": _XC()}
    if not isinstance(action, list) or not action:
        return ef
    op = action[0]
    ef["op"] = op
    if idx >= len(st["pos"]):
        return ef
    fx, fy = st["pos"][idx]
    while len(st["invs"]) <= idx:
        st["invs"].append(_XC())
    inv = st["invs"][idx]
    if op in _XO_MOVES:
        dx, dy = _XO_MOVES[op]
        nx, ny = fx + dx, fy + dy
        if 0 <= nx < 10 and 0 <= ny < 10:
            st["pos"][idx] = (nx, ny)
            ef["eff"] = True
        return ef
    if op == "PASS":
        return ef
    tiles = st["tiles"]
    tile = tiles[fy][fx]
    ef["tile"] = fy * 10 + fx
    shed = st["shed"]
    if op == "DROP":
        if (fx, fy) not in _XO_SHEDSET:
            return ef
        for item, n in list(inv.items()):
            if n <= 0:
                del inv[item]
                continue
            room = max(0, cap - sum(shed.values()))
            take = min(n, room)
            if take > 0:
                shed[item] += take
                ef["dep"][item] += take
            if n - take > 0:
                ef["lost"][item] += n - take
            del inv[item]
            ef["eff"] = True
        return ef
    if op == "PICKUP":
        if (fx, fy) not in _XO_SHEDSET or len(action) < 2:
            return ef
        item = action[1]
        try:
            n = int(action[2]) if len(action) >= 3 else 1
        except (TypeError, ValueError):
            return ef
        if n <= 0:
            return ef
        n = min(n, shed.get(item, 0))
        if n <= 0:
            return ef
        shed[item] -= n
        if shed[item] <= 0:
            del shed[item]
        inv[item] += n
        ef["pick"][item] += n
        ef["eff"] = True
        return ef
    if op == "PLACE":
        if len(action) < 2:
            return ef
        item = action[1]
        if item in _XO_ANIMALS and isinstance(tile, dict) and tile.get("kind") == _XO_ANIMALS[item]["structure"] \
                and "animal" not in tile:
            if inv.get(item, 0) >= 1:
                inv[item] -= 1
                if inv[item] <= 0:
                    del inv[item]
                tiles[fy][fx] = _xo_new_animal(item, day)
                ef["use"][item] += 1
                ef["eff"] = True
            return ef
        if (fx, fy) in _XO_SHEDSET:
            try:
                n = int(action[2]) if len(action) >= 3 else 1
            except (TypeError, ValueError):
                return ef
            if n <= 0:
                return ef
            n = min(n, inv.get(item, 0))
            if n <= 0:
                return ef
            n = min(n, max(0, cap - sum(shed.values())))
            if n <= 0:
                return ef
            inv[item] -= n
            if inv[item] <= 0:
                del inv[item]
            shed[item] += n
            ef["dep"][item] += n
            ef["eff"] = True
        return ef
    if tile == "LOCKED":
        return ef
    if op == "PLANT":
        if len(action) < 2 or action[1] not in _XO_CROPS or tile is not None:
            return ef
        crop = action[1]
        if st["seeds"].get(crop, 0) <= 0:
            return ef
        st["seeds"][crop] -= 1
        tiles[fy][fx] = _xo_new_plant(crop, day, tpd)
        ef["eff"] = True
        return ef
    if op == "WATER":
        if not _xo_is_plant(tile) or tile["watered_today"]:
            return ef
        tile["watered_today"] = True
        cd = _XO_CROPS[tile["crop"]]
        if not cd["ongoing"]:
            age = day - tile["planted_day"]
            ws = (cd["maxday"] + 1) // 2
            if ws <= age <= cd["maxday"]:
                bonus = 2 if tile["fertilized_until_day"] >= day else 1
                tile["yield_units"] = min(cd["max"], tile["yield_units"] + bonus)
        ef["eff"] = True
        return ef
    if op == "HARVEST":
        if not isinstance(tile, dict) or tile.get("yield_units", 0) <= 0:
            return ef
        if tile.get("kind") == "PLANT":
            cd = _XO_CROPS[tile["crop"]]
            if day - tile["planted_day"] < cd["first"]:
                return ef
            u = tile["yield_units"]
            tile["yield_units"] = 0
            inv[tile["crop"]] += u
            ef["gain"][tile["crop"]] += u
            if not cd["ongoing"]:
                tiles[fy][fx] = None
            ef["eff"] = True
        elif "animal" in tile:
            u = tile["yield_units"]
            tile["yield_units"] = 0
            p = _XO_ANIMALS[tile["animal"]]["product"]
            inv[p] += u
            ef["gain"][p] += u
            ef["eff"] = True
        return ef
    if op == "FERTILIZE":
        if not _xo_is_plant(tile) or inv.get("FERTILIZER", 0) < 1:
            return ef
        inv["FERTILIZER"] -= 1
        if inv["FERTILIZER"] <= 0:
            del inv["FERTILIZER"]
        tile["fertilized_until_day"] = max(tile.get("fertilized_until_day", -1), day + 2)
        ef["use"]["FERTILIZER"] += 1
        ef["eff"] = True
        return ef
    if op == "DIG":
        if tile is None or (isinstance(tile, dict) and "animal" in tile):
            return ef
        tiles[fy][fx] = None
        ef["eff"] = True
        return ef
    if op in ("BUILD_COOP", "BUILD_PASTURE"):
        if tile is not None:
            return ef
        tiles[fy][fx] = {"kind": "COOP" if op == "BUILD_COOP" else "PASTURE"}
        ef["eff"] = True
        return ef
    if op == "FEED":
        if not (isinstance(tile, dict) and "animal" in tile) or tile["fed_today"] or inv.get("WHEAT", 0) < 1:
            return ef
        inv["WHEAT"] -= 1
        if inv["WHEAT"] <= 0:
            del inv["WHEAT"]
        tile["fed_today"] = True
        ef["use"]["WHEAT"] += 1
        ef["eff"] = True
        return ef
    if op == "COLLECT_FERTILIZER":
        if not (isinstance(tile, dict) and "animal" in tile) or not tile["fertilizer_available"]:
            return ef
        tile["fertilizer_available"] = False
        inv["FERTILIZER"] += 1
        ef["gain"]["FERTILIZER"] += 1
        ef["eff"] = True
        return ef
    if op == "CARE":
        if not (isinstance(tile, dict) and "animal" in tile) or tile["cared_today"]:
            return ef
        tile["cared_today"] = True
        ef["eff"] = True
        return ef
    return ef


def _xo_blocked(cmds, seeds):
    dem = _XC(c[1] for c in cmds if isinstance(c, list) and len(c) >= 2 and c[0] == "PLANT")
    return {crop for crop, n in dem.items() if n > seeds.get(crop, 0)}


def xo_sim_units(P, cmds, day=None):
    """the engine's unit phase of one player for commands cmds[unit] (the atomic PLANT check included)."""
    st = _xo_sim_state(P)
    day = P["day"] if day is None else day
    blocked = _xo_blocked(cmds, st["seeds"])
    effs = []
    for idx, c in enumerate(cmds):
        if isinstance(c, list) and len(c) >= 2 and c[0] == "PLANT" and c[1] in blocked:
            c = ["PASS"]
        effs.append(_xo_apply_one(st, idx, c, day))
    st["effects"] = effs
    st["blocked"] = blocked
    return st


def _xo_probe(st, idx, cmd, day):
    """would the command change the state (engine rules)? Copies only the unit's tile row / inventory."""
    if idx >= len(st["pos"]):
        return False
    fx, fy = st["pos"][idx]
    tiles = [row if y != fy else [(dict(t) if isinstance(t, dict) and x == fx else t) for x, t in enumerate(row)]
             for y, row in enumerate(st["tiles"])]
    probe = dict(tiles=tiles, shed=_XC(st["shed"]), seeds=_XC(st["seeds"]), pos=list(st["pos"]),
                 invs=[(_XC(i) if n == idx else i) for n, i in enumerate(st["invs"])])
    return _xo_apply_one(probe, idx, cmd, day)["eff"]


# =========================================================================================== price path / EV (B7)
def _xo_curve(p, day):
    global _XO_PRICE_CURVE
    if _XO_PRICE_CURVE is None:
        _XO_PRICE_CURVE = {}
        try:
            fp = _xo_os.path.join(_xo_root_default(), "results", "fresh", "xopen_20260925", "price_curve.json")
            with open(fp, encoding="utf-8") as fh:
                _XO_PRICE_CURVE = _xo_json.load(fh)["curve"]
        except Exception:
            _XO_PRICE_CURVE = {}
    row = _XO_PRICE_CURVE.get(p)
    if not row:
        return 1.0
    return float(row[max(0, min(len(row) - 1, int(day)))])


def _xo_price_fc(p, day, today, prices):
    q = float(prices.get(p) or _XO_BASE.get(p, 0))
    c0 = max(0.05, _xo_curve(p, today))
    return q * _xo_curve(p, day) / c0


def _xo_schedule(kind, name, pday, fert=False):
    """[(day, units)] production of a fresh asset created on pday (watered / fed / cared as the plans do); days <= 29."""
    out = []
    if kind == "crop":
        cd = _XO_CROPS[name]
        if cd["ongoing"]:
            for k in range(cd["max"]):
                d = pday + cd["first"] + k * cd["interval"]
                if d <= 29:
                    out.append((d, 3 if fert else 1))
        else:
            d = pday + cd["maxday"]
            if d <= 29:
                out.append((d, min(cd["max"], _XO_ONETIME_UNITS.get(name, 1) + (2 if fert else 0))))
    else:
        a = _XO_ANIMALS[name]
        d = pday + a["first"]
        first = True
        while d <= 29:
            out.append((d, min(a["max_held"], 1 + (a["first"] - 1 if first else a["interval"]))))
            first = False
            d += a["interval"]
    return out


def xo_asset_ev(kind, name, pday, today, prices, D, cash_rate, fert=False):
    """expected value (coins, cash-timing weighted) of an asset created on pday, seen from today."""
    if pday > 29:
        return 0.0
    w = lambda j: 1.0 + cash_rate * max(0, D - j)
    v = 0.0
    if kind == "crop":
        for d, u in _xo_schedule(kind, name, pday, fert):
            v += u * _xo_price_fc(name, d, today, prices) * w(d)
        return v
    a = _XO_ANIMALS[name]
    sched = _xo_schedule(kind, name, pday)
    if not sched:
        return 0.0
    last = sched[-1][0]
    for d, u in sched:
        v += u * _xo_price_fc(a["product"], d, today, prices) * w(d)
    for d in range(pday, last + 1):            # feed wheat; about half the daily fertilizer is collected and sold
        v -= _xo_price_fc("WHEAT", d, today, prices) * w(d)
        if d > pday:
            v += 0.5 * _xo_price_fc("FERTILIZER", d, today, prices) * w(d)
    return v


def xo_delay_cost(kind, name, pday, new_day, today, prices, D, cash_rate, fert=False):
    """EV lost when the asset is created on new_day instead of pday; the whole EV when new_day is past its catch-up
    window or its last useful day (plant_cutoff / last_animal)."""
    if new_day <= pday:
        return 0.0
    ev0 = xo_asset_ev(kind, name, pday, today, prices, D, cash_rate, fert)
    if kind == "crop":
        if new_day - pday > _XO_CATCHUP.get(name, 1) or new_day > _XO_CUTOFF.get(name, 29):
            return max(0.0, ev0)
    else:
        if new_day > _XO_LAST_ANIMAL.get(name, 29):
            return max(0.0, ev0)
    return max(0.0, ev0 - xo_asset_ev(kind, name, new_day, today, prices, D, cash_rate, fert))


# =========================================================================================== plan loading
_XO_PLAN_CACHE = {}


def _xo_root_default():
    fn = XO_HOOKS.get("root") if isinstance(globals().get("XO_HOOKS"), dict) else None
    if fn:
        try:
            return fn()
        except Exception:
            pass
    here = globals().get("__file__")
    cands = [_xo_os.getcwd()]
    if here:
        cands.append(_xo_os.path.dirname(_xo_os.path.dirname(_xo_os.path.abspath(here))))
    for c in cands:
        if _xo_os.path.isdir(_xo_os.path.join(c, "data", "leader_semantics")):
            return c
    return _xo_os.getcwd()


def xo_plans_dir():
    return XO_CFG.get("plans_dir") or _xo_os.path.join(_xo_root_default(), "results", "fresh", "xopen_20260925", "plans")


def xo_load_plan(key):
    """compiled plan (scripts/xopen_compile.py) -> preprocessed dict (cached per process)."""
    if key in _XO_PLAN_CACHE:
        return _XO_PLAN_CACHE[key]
    p = _xo_os.path.join(xo_plans_dir(), "%s.json.gz" % key)
    if not _xo_os.path.isfile(p) and _xo_os.path.isfile(p[:-3]):
        p = p[:-3]                                   # Kaggle may unpack .gz uploads
    op = _xo_gzip.open if p.endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as fh:
        raw = _xo_json.load(fh)
    pl = xo_prepare_plan(raw)
    _XO_PLAN_CACHE[key] = pl
    return pl


def _xo_okey(o):
    if not isinstance(o, list) or len(o) < 2:
        return None
    if o[0] == "BUY_SEED":
        return "SEED:" + str(o[1])
    if o[0] == "BUY_ANIMAL":
        return "ANIMAL:" + str(o[1])
    if o[0] == "BUY_PRODUCT":
        return "PRODUCT:" + str(o[1])
    return None


def xo_prepare_plan(raw):
    """index a compiled plan: cumulative effective counts, role spawns, claims (tile ops by role), shed pickups,
    dependency lists (future effective PLANT / PLACE per crop / species), fertilizer targets."""
    pl = dict(raw)
    T0 = int(raw["T0"])
    steps = raw["steps"]
    pl["T0"], pl["T1"] = T0, T0 + len(steps)
    pl["key"] = "%s_%s" % (raw["team"], raw["ep"])
    E, S, H, Q = [], [], [], []
    runE, runS, runH, runQ = _XC(), _XC(), 0, 0
    for j, s in enumerate(steps):
        t = T0 + j
        if t % 24 == 0:
            runH = 0
        for o, fill, coins in s.get("mk", []):
            k = _xo_okey(o)
            if k and fill:
                runE[k] += int(fill)
            elif isinstance(o, list) and o and o[0] == "SELL" and fill:
                runS[str(o[1])] += int(fill)
        runH += int(s.get("hs", 0) or 0)
        runQ += int(s.get("ld", 0) or 0)
        E.append(_XC(runE))
        S.append(_XC(runS))
        H.append(runH)
        Q.append(runQ)
    pl["E"], pl["S"], pl["H"], pl["Q"] = E, S, H, Q
    pl["Q0"] = int(raw.get("Q0", 0))            # quadrants beyond NW owned at T0
    days = {}
    uses = {}
    fz = []
    for j, s in enumerate(steps):
        t = T0 + j
        d = t // 24
        D_ = days.setdefault(d, {"spawn": {}, "ops": {}, "picks": {}, "units_max": 0})
        u = s["u"]
        D_["units_max"] = max(D_["units_max"], len(u))
        for k, e in enumerate(u):
            if k >= 1 and k not in D_["spawn"]:
                D_["spawn"][k] = (t, (e[0], e[1]))
            cmd = e[2]
            op = cmd[0] if isinstance(cmd, list) and cmd else "PASS"
            on_tile = (e[0], e[1]) not in _XO_SHEDSET or op in _XO_TILE_OPS
            if op in _XO_TILE_OPS or (op == "PLACE" and len(cmd) > 1 and cmd[1] in _XO_ANIMALS and on_tile):
                D_["ops"].setdefault(k, []).append((t, e[1] * 10 + e[0], op, int(e[3]), cmd))
            elif op == "PICKUP" and len(cmd) > 1:
                try:
                    n = int(cmd[2]) if len(cmd) >= 3 else 1
                except (TypeError, ValueError):
                    n = 1
                D_["picks"].setdefault(k, []).append((t, str(cmd[1]), n))
            if e[3] and op == "PLANT" and len(cmd) > 1:
                uses.setdefault("SEED:" + str(cmd[1]), []).append((t, e[1] * 10 + e[0]))
            elif e[3] and op == "PLACE" and len(cmd) > 1 and cmd[1] in _XO_ANIMALS and e[5] is not None \
                    and e[5][0] in ("co", "pa"):
                uses.setdefault("ANIMAL:" + str(cmd[1]), []).append((t, e[1] * 10 + e[0]))
            elif e[3] and op == "FERTILIZE":
                fz.append((t, _XO_LAB_CROP.get((e[5] or [None])[0])))
    pl["days"], pl["uses"], pl["fert_uses"] = days, uses, fz
    pl["dayinfo"] = {int(x["d"]): x for x in raw.get("days", [])}
    return pl


def _xo_rec(pl, t, k):
    """recorded entry of role k at step t: [x, y, cmd, eff, tile, tsig] or None."""
    if pl is None or t < pl["T0"] or t >= pl["T1"]:
        return None
    u = pl["steps"][t - pl["T0"]]["u"]
    return u[k] if k < len(u) else None


def _xo_stp(pl, t):
    if pl is None or t < pl["T0"] or t >= pl["T1"]:
        return None
    return pl["steps"][t - pl["T0"]]


def _xo_cum(pl, t, what):
    """the recording's cumulative effective counts through step t (clamped to the plan's range; 0 before it)."""
    zero = _XC() if what in ("E", "S") else 0
    if pl is None or t < pl["T0"]:
        return zero
    return pl[what][min(pl["T1"], t + 1) - 1 - pl["T0"]]


# =========================================================================================== per-game state
_XO = {}
_XO_REPORT = {}
XO_HOOKS = {}       # glue: "root"() -> repo root


def _xo_log(kind, **kw):
    if _XO.get("dry"):
        return
    ev = dict(kind=kind, step=_XO.get("t", -1))
    ev.update(kw)
    lg = _XO.setdefault("events", [])
    if len(lg) < XO_CFG["log_max"]:
        lg.append(ev)
    _XO["count"][kind + (":" + kw["cause"] if kw.get("cause") else "")] += 1
    if kind in ("breakage", "repair", "defer", "cancel", "release", "abort", "rendezvous", "lag", "substitute", "job"):
        d = max(0, _XO.get("t", 0)) // 24
        _XO["by_day"].setdefault(d, _XC())[kind + (":" + kw["cause"] if kw.get("cause") else "")] += 1


def _xo_diverge(cause, **kw):
    if _XO.get("dry") or _XO.get("first_div") is not None:
        return
    t = _XO.get("t", -1)
    _XO["first_div"] = dict(step=t, day=t // 24, hour=t % 24, cause=cause, **kw)


def xo_init(plan=None, tape=None):
    """reset the per-game state. plan: preprocessed plan (follow / replay_capped); tape: raw tape (replay modes)."""
    _XO.clear()
    _XO.update(dict(
        plan=plan, tape=tape, t=-1, dry=False, handed=False, D=None, D_reason=None, D_shadow=None, abort=None,
        first_div=None, first_div_exact=None, first_hidden=None,
        bought=_XC(), sold=_XC(), hires_today=0, quads=0, adj=_XC(), carry=_XC(), carryS=_XC(),
        revenue=_XC(), spend=_XC(), hold_res=0.0, prev=None, units={}, jobs={}, jid=0, owned=set(),
        count=_XC(), by_day={}, events=[], cuts=[], deferred_by_day=_XC(), queue={}, queue_coins=0.0,
        cash_by_day={}, plan_cash_by_day={}, placed_by_day={}, ham_by_day={}, hidden_by_day={}, plans=[],
        t0short=_XC(), fills_amb=0, money_resid_max=0.0, tmax=0.0, tsum=0.0, lag_max_seen=0, spawn_offsets=0,
        exclude=set(), plan_shops=list((plan or {}).get("shops") or []), rev_ratio=1.0, D_plan=XO_CFG["D_fixed"],
    ))
    ex = XO_CFG.get("exclude_ep") or _xo_os.environ.get("XO_EXCLUDE_EP")
    if ex:
        for e in str(ex).split(","):
            if e.strip():
                _XO["exclude"].add(int(e))
    if plan is not None:
        _XO["plans"].append(dict(day=0, key=plan["key"]))
    _XO_REPORT.clear()


# =========================================================================================== fill inference (B5)
def _xo_solve_pf(orders, item, stock0, delta):
    """wheat / fertilizer: total buy fills b (given to our BUY_PRODUCT orders of item in list order) with
    bought - sold == delta, sells resolving on the stock in list order. -> [(bought, sold)] (all consistent b)."""
    seq = []
    for o in orders:
        if isinstance(o, list) and len(o) >= 3 and o[1] == item and o[0] in ("SELL", "BUY_PRODUCT"):
            try:
                seq.append((o[0], max(0, int(o[2]))))
            except (TypeError, ValueError):
                pass
    qb = sum(q for op, q in seq if op == "BUY_PRODUCT")
    sols = []
    for b in range(qb + 1):
        left, stock, bought, sold = b, stock0, 0, 0
        for op, q in seq:
            if op == "BUY_PRODUCT":
                f = min(q, left)
                left -= f
                stock += f
                bought += f
            else:
                s = min(q, max(0, stock))
                stock -= s
                sold += s
        if bought - sold == delta:
            sols.append((bought, sold))
    return sols


def xo_infer(prev, P):
    """fills of our previous step from the observation delta.
    prev = {step, day, money, unl, orders, post (simulated unit phase), prices, hires_before}."""
    out = dict(hires=0, land=0, buy=_XC(), sell=_XC(), amb=[], spend=0.0, wages=0.0, landc=0.0, rev=0.0, resid=0.0)
    post = prev["post"]
    boundary = P["day"] != prev["day"]
    shed_after = _XC(P["shed"])
    if boundary:
        carried = _XC()
        for inv in post["invs"]:
            carried.update(inv)
        if sum(P["shed"].values()) >= 100 and carried:
            out["amb"].append("midnight_overflow")
        for k, v in carried.items():
            shed_after[k] -= v
        shed_after = _XC({k: v for k, v in shed_after.items() if v > 0})
        out["hires"] = 0                   # hour-23 hires vanish at midnight; the follower issues none at hour 23
    else:
        out["hires"] = max(0, P["hires_today"] - prev["hires_before"])
    out["land"] = max(0, len(P["unlocked"]) - prev["unl"])
    for c in _XO_CROPS:
        n = P["seeds"].get(c, 0) - post["seeds"].get(c, 0)
        if n > 0:
            out["buy"]["SEED:" + c] += n
        elif n < 0:
            out["amb"].append("seed_" + c)
    for it in set(shed_after) | set(post["shed"]):
        dlt = shed_after.get(it, 0) - post["shed"].get(it, 0)
        if it in _XO_ANIMALS:
            if dlt > 0:
                out["buy"]["ANIMAL:" + it] += dlt
            elif dlt < 0:
                out["amb"].append("animal_" + it)
        elif it in ("WHEAT", "FERTILIZER"):
            sols = _xo_solve_pf(prev["orders"], it, post["shed"].get(it, 0), dlt)
            if not sols:
                out["amb"].append("pf_" + it)
                b, s = max(0, dlt), max(0, -dlt)
            elif len(sols) == 1:
                b, s = sols[0]
            else:
                out["amb"].append("pf_multi_" + it)
                pr = float(prev["prices"].get(it, _XO_BASE[it]))
                rest = P["money"] - prev["money"]
                b, s = min(sols, key=lambda bs: abs(rest - (bs[1] * pr - bs[0] * (pr + 1))))
            if b:
                out["buy"]["PRODUCT:" + it] += b
            if s:
                out["sell"][it] += s
        elif it in _XO_PRODUCTS:
            if dlt < 0:
                out["sell"][it] += -dlt
            elif dlt > 0:
                out["amb"].append("product_" + it)
    h0 = prev["hires_before"]
    out["wages"] = float(sum(_xo_fib(h0 + i) for i in range(out["hires"])))
    q0 = max(0, prev["unl"] - 1)
    out["landc"] = float(sum(_XO_LAND_PRICES[min(2, q0 + i)] for i in range(out["land"])))
    sp = 0.0
    for k, n in out["buy"].items():
        kind, it = k.split(":")
        if kind == "SEED":
            sp += n * _XO_CROPS[it]["seed"]
        elif kind == "ANIMAL":
            sp += n * _XO_ANIMALS[it]["cost"]
        else:
            sp += n * (float(prev["prices"].get(it, _XO_BASE[it])) + 1)
    out["spend"] = sp
    out["rev"] = max(0.0, P["money"] - prev["money"] + sp + out["wages"] + out["landc"])
    out["resid"] = out["rev"] - sum(n * float(prev["prices"].get(p, 0)) for p, n in out["sell"].items())
    return out


def _xo_apply_fills(f, P, prev_day):
    for k, n in f["buy"].items():
        _XO["bought"][k] += n
    for k, n in f["sell"].items():
        _XO["sold"][k] += n
    _XO["quads"] += f["land"]
    _XO["revenue"][prev_day] += f["rev"]
    _XO["spend"][prev_day] += f["spend"] + f["wages"] + f["landc"]
    if XO_CFG["hold"] > 0 and not _XO["handed"]:
        _XO["hold_res"] += XO_CFG["hold"] * f["rev"]
    if f["amb"]:
        _XO["fills_amb"] += 1
        _xo_log("fills_ambiguous", cause=",".join(f["amb"])[:60])
    _XO["money_resid_max"] = max(_XO["money_resid_max"], abs(f.get("resid", 0.0)))


# =========================================================================================== cumulative deficits (A.5)
def _xo_wants(P, t):
    """what the recording had bought / sold / hired / unlocked through step t and we have not (retried every step)."""
    pl = _XO["plan"]
    E = _xo_cum(pl, t, "E")
    S = _xo_cum(pl, t, "S")
    wb = _XC()
    for k in set(E) | set(_XO["carry"]) | set(_XO["adj"]):
        v = E.get(k, 0) + _XO["carry"].get(k, 0) + _XO["adj"].get(k, 0) - _XO["bought"].get(k, 0)
        if v > 0:
            wb[k] = v
    ws = _XC()
    for k in set(S) | set(_XO["carryS"]):
        v = S.get(k, 0) + _XO["carryS"].get(k, 0) - _XO["sold"].get(k, 0)
        if v > 0:
            ws[k] = v
    wh = (_xo_cum(pl, t, "H") if (pl is not None and t >= pl["T0"]) else 0) - P["hires_today"]
    q_rec = (pl["Q0"] + _xo_cum(pl, t, "Q")) if pl is not None else 0
    wl = min(q_rec, XO_CFG["land_max"]) - (len(P["unlocked"]) - 1)
    return wb, ws, max(0, wh), max(0, wl)


# =========================================================================================== roles (A.3 / B2)
def _xo_role_remaining(pl, k, t, day):
    """(value, ops) of role k's remaining effective recorded tile ops today from step t."""
    ops = pl["days"].get(day, {}).get("ops", {}).get(k, []) if pl else []
    rem = [o for o in ops if o[0] >= t and o[3]]
    v = 0.0
    for (s, tile, op, eff, cmd) in rem:
        v += 60.0 if op in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE") else 25.0 if op in ("HARVEST", "FEED") else 10.0
    return v, rem


def _xo_rv_search(pl, k, t, pos, inv, P):
    """earliest recorded step s > t at which a unit at pos can stand on role k's recorded position after picking up
    at the shed what the role carries then (WHEAT / FERTILIZER / animals). -> (s, target, pickups) or None."""
    day = t // 24
    end = min(day * 24 + XO_CFG["rv_hour"], pl["T1"] - 1)
    for s in range(t + 1, end + 1):
        r = _xo_rec(pl, s, k)
        if r is None:
            continue
        tgt = (r[0], r[1])
        st = _xo_stp(pl, s)
        need = []
        iv = st.get("iv", []) if st else []
        if k < len(iv):
            for it, n in sorted((iv[k] or {}).items()):
                if (it in ("WHEAT", "FERTILIZER") or it in _XO_ANIMALS) and n > inv.get(it, 0) and P["shed"].get(it, 0) > 0:
                    need.append([it, int(n - inv.get(it, 0))])
        if need:
            sh = _xo_near_shed(pos)
            cost = _xo_dist(pos, sh) + len(need) + _xo_dist(sh, tgt)
        else:
            cost = _xo_dist(pos, tgt)
        if cost <= s - t:
            return s, tgt, need
    return None


def _xo_orphan(pl, k, i_from, i_to):
    """recorded effective asset / harvest ops of role k in [i_from, i_to) become catch-up jobs."""
    if _XO.get("dry"):
        return
    for i in range(i_from, i_to):
        r = _xo_rec(pl, i, k)
        if r is None or not r[3]:
            continue
        cmd = r[2]
        op = cmd[0] if isinstance(cmd, list) and cmd else "PASS"
        tile = r[1] * 10 + r[0]
        if op == "PLANT" and len(cmd) > 1:
            _xo_add_job(tile, "PLANT", cmd[1], src="orphan", pday=i // 24)
        elif op in ("BUILD_COOP", "BUILD_PASTURE"):
            _xo_add_job(tile, op, None, src="orphan")
        elif op == "PLACE" and len(cmd) > 1 and cmd[1] in _XO_ANIMALS and r[5] is not None and r[5][0] in ("co", "pa"):
            _xo_add_job(tile, "PLACE", cmd[1], src="orphan")
        elif op == "HARVEST":
            _xo_add_job(tile, "HARVEST", None, src="orphan")


def _xo_assign_new_hands(P, t):
    """map hands that appeared this step to recorded roles: role k = the k-th successful hire of the day (capped at
    the recording's crew); a late or offset hand takes, among the roles still unmapped, the one with the most
    remaining value it can reach lagged (lag <= lag_max) or by rendezvous; otherwise it is released."""
    pl = _XO["plan"]
    day = t // 24
    U = _XO["units"]
    spawn = pl["days"].get(day, {}).get("spawn", {}) if pl else {}
    for j in range(1, len(P["pos"])):
        if j in U:
            continue
        pos = P["pos"][j]
        mapped = {u.get("role") for u in U.values() if u.get("role") is not None}
        if j not in spawn or j in mapped:
            U[j] = dict(role=None, mode="rel")
            _xo_log("release", cause="extra_hand", unit=j)
            continue
        s_k, p_k = spawn[j]
        p_k = tuple(p_k)
        if pos != p_k:
            _XO["spawn_offsets"] += 1
            _xo_log("breakage", cause="spawn_offset", unit=j, pos=list(pos), rec=list(p_k))
        if t == s_k and pos == p_k:
            U[j] = dict(role=j, mode="sync", i=t)
            continue
        if t < s_k:
            U[j] = dict(role=j, mode="wait", i=s_k, goal=p_k, gs=s_k)
            _xo_log("lag", cause="hire_early", unit=j, role=j)
            continue
        cands = []
        for kk, (sk2, pk2) in spawn.items():
            if kk in mapped or sk2 > t:
                continue
            val, _ = _xo_role_remaining(pl, kk, t, day)
            cands.append((-val, 0 if kk == j else 1, kk, sk2, tuple(pk2)))
        cands.sort()
        U[j] = dict(role=None, mode="rel")
        for _, _, kk, sk2, pk2 in cands:
            lag = t + _xo_dist(pos, pk2) - sk2
            if lag <= XO_CFG["lag_max"]:
                U[j] = dict(role=kk, mode="walk", i=sk2, goal=pk2, gs=sk2)
                _xo_log("lag", cause="late_hire" if t > sk2 else "offset", unit=j, role=kk, lag=lag)
                _xo_diverge("hire_late", role=kk)
                break
            rv = _xo_rv_search(pl, kk, t, pos, P["invs"][j] if j < len(P["invs"]) else _XC(), P)
            if rv is not None:
                s, tgt, need = rv
                U[j] = dict(role=kk, mode="rv", i=s, goal=tgt, gs=s, need=need)
                _xo_orphan(pl, kk, sk2, s)
                _xo_log("rendezvous", cause="late_hire", unit=j, role=kk, at=s)
                _xo_diverge("hire_late", role=kk)
                break
        if U[j]["role"] is None:
            _xo_log("release", cause="no_rendezvous", unit=j)


# =========================================================================================== jobs (B.2)
def _xo_add_job(tile, op, arg, src="catchup", pday=None, deadline=None, value=None):
    if _XO.get("dry"):
        return None
    for j in _XO["jobs"].values():
        if j["tile"] == tile and j["op"] == op and j["arg"] == arg:
            return j
    t = _XO["t"]
    day = t // 24
    if deadline is None:
        if op == "PLANT":
            # catch-up window of the crop, never after plant_cutoff; PLANT + WATER must fit the day
            last = min(29, (pday if pday is not None else day) + _XO_CATCHUP.get(arg, 1), _XO_CUTOFF.get(arg, 29))
            deadline = last * 24 + 21
        elif op == "PLACE":
            deadline = min(29, day + 2, _XO_LAST_ANIMAL.get(arg, 29)) * 24 + 22
        else:
            deadline = day * 24 + 22
    _XO["jid"] += 1
    j = dict(id=_XO["jid"], tile=tile, op=op, arg=arg, src=src, pday=pday if pday is not None else day,
             deadline=deadline, value=value, unit=None, created=t)
    _XO["jobs"][j["id"]] = j
    _xo_log("job", cause=src + "_" + op, tile=tile, arg=arg)
    return j


def _xo_job_value(op, arg, P):
    day = P["day"]
    D = _XO.get("D_plan", XO_CFG["D_fixed"])
    if op == "PLANT" and arg in _XO_CROPS:
        return max(20.0, xo_asset_ev("crop", arg, day, day, P["prices"], D, XO_CFG["cash_rate"]))
    if op == "PLACE" and arg in _XO_ANIMALS:
        return max(50.0, xo_asset_ev("animal", arg, day, day, P["prices"], D, XO_CFG["cash_rate"]))
    if op in ("BUILD_COOP", "BUILD_PASTURE"):
        return 80.0
    if op == "DIG":
        return 60.0
    if op == "HARVEST":
        return 40.0
    return 30.0


def _xo_land_expected(idx):
    """is the quadrant of this tile one we will own (NW, or a purchase within land_max)? A tile of a quadrant beyond
    land_max stays locked for good (the recording's purchase is cancelled); within it, the purchase may only be late."""
    q = _xo_quad(idx)
    if q == "NW":
        return True
    return _XO_LAND_ORDER.index(q) < XO_CFG["land_max"]


def _xo_job_valid(j, tiles, P):
    """-> (still needed, prerequisite op or None, item needed from the shed or None)."""
    t = _xo_tile(tiles, j["tile"])
    op = j["op"]
    if t == "LOCKED":
        # waits for a late land purchase (not doable yet: the unit greedy skips locked tiles); dropped when the
        # quadrant is beyond land_max
        return (op in ("PLANT", "BUILD_COOP", "BUILD_PASTURE", "PLACE") and _xo_land_expected(j["tile"])
                and P["day"] <= _XO_CUTOFF.get(j["arg"], 29)), None, None
    if op == "PLANT":
        if _xo_is_plant(t) and t.get("crop") == j["arg"]:
            return False, None, None
        if P["day"] > _XO_CUTOFF.get(j["arg"], 29):
            return False, None, None
        if _xo_is_weed(t):
            return True, "DIG", None
        return (t is None), None, None
    if op in ("BUILD_COOP", "BUILD_PASTURE"):
        if isinstance(t, dict) and t.get("kind") == ("COOP" if op == "BUILD_COOP" else "PASTURE"):
            return False, None, None
        if _xo_is_weed(t):
            return True, "DIG", None
        return (t is None), None, None
    if op == "PLACE":
        a = j["arg"]
        ok = isinstance(t, dict) and t.get("kind") == _XO_ANIMALS[a]["structure"] and "animal" not in t
        return ok, None, (a if ok else None)
    if op == "DIG":
        return _xo_is_weed(t), None, None
    if op == "WATER":
        return (_xo_is_plant(t) and not t.get("watered_today")), None, None
    if op == "FEED":
        ok = isinstance(t, dict) and bool(t.get("animal")) and not t.get("fed_today")
        return ok, None, ("WHEAT" if ok else None)
    if op == "HARVEST":
        if _xo_is_plant(t):
            cd = _XO_CROPS[t["crop"]]
            age = P["day"] - t["planted_day"]
            return (t.get("yield_units", 0) > 0 and age >= cd["first"] and (cd["ongoing"] or age >= cd["maxday"])), None, None
        return (isinstance(t, dict) and bool(t.get("animal")) and t.get("yield_units", 0) > 0), None, None
    return False, None, None


def _xo_job_cmds(jb, pre):
    ops = [[pre]] if pre else []
    if jb["op"] == "PLANT":
        ops += [["PLANT", jb["arg"]], ["WATER"]]
    elif jb["op"] == "PLACE":
        ops += [["PLACE", jb["arg"], 1]]
    else:
        ops += [[jb["op"]]]
    return ops


# =========================================================================================== substitution
def _xo_surplus(pl, k, i, inv, item):
    """units of item the unit carries beyond what role k carried before recorded step i (B4)."""
    st = _xo_stp(pl, i)
    rec = 0
    if st is not None and k is not None and k < len(st.get("iv", [])):
        rec = int((st["iv"][k] or {}).get(item, 0))
    return inv.get(item, 0) - rec


def _xo_substitute(st, idx, pos, day, pl, k, i, rec_cmd):
    """-> (command, advance): a repair op on this tile first (DIG a weed / HARVEST a finished one-time crop that blocks
    a recorded PLANT / BUILD; advance False, so the recorded op runs next step: lag + 1), else a useful maintenance op
    on this tile using only surplus inputs, else PASS."""
    x, y = pos
    tile = st["tiles"][y][x]
    op = rec_cmd[0] if isinstance(rec_cmd, list) and rec_cmd else "PASS"
    if op in ("PLANT", "BUILD_COOP", "BUILD_PASTURE"):
        if _xo_is_weed(tile):
            return ["DIG"], False
        if _xo_is_plant(tile):
            cd = _XO_CROPS[tile["crop"]]
            age = day - tile["planted_day"]
            if not cd["ongoing"] and age >= cd["maxday"] and tile.get("yield_units", 0) > 0:
                return ["HARVEST"], False
    inv = st["invs"][idx] if idx < len(st["invs"]) else _XC()
    if _xo_is_plant(tile):
        if not tile.get("watered_today"):
            return ["WATER"], True
        cd = _XO_CROPS[tile["crop"]]
        age = day - tile["planted_day"]
        if cd["ongoing"] and tile.get("yield_units", 0) > 0 and age >= cd["first"]:
            return ["HARVEST"], True
    if isinstance(tile, dict) and tile.get("animal"):
        if not tile.get("fed_today") and _xo_surplus(pl, k, i, inv, "WHEAT") > 0:
            return ["FEED"], True
        if not tile.get("cared_today"):
            return ["CARE"], True
        if tile.get("yield_units", 0) > 0:
            return ["HARVEST"], True
        if tile.get("fertilizer_available"):
            return ["COLLECT_FERTILIZER"], True
    return ["PASS"], True


def _xo_destructive(cmd, tile):
    op = cmd[0] if isinstance(cmd, list) and cmd else None
    if op == "DIG":
        return True
    return op == "HARVEST" and _xo_is_plant(tile) and not _XO_CROPS[tile["crop"]]["ongoing"]


# =========================================================================================== unit commands
def _xo_goal_cmd(u, pos):
    """walk / rendezvous / wait: pickups at the shed first, then toward the goal; PASS when early."""
    need = u.get("need") or []
    if need:
        if pos in _XO_SHEDSET:
            it, n = need[0]
            u["need"] = need[1:]
            return ["PICKUP", it, int(n)]
        return _xo_step_toward(pos, _xo_near_shed(pos)) or ["PASS"]
    return _xo_step_toward(pos, tuple(u["goal"])) or ["PASS"]


def _xo_released_cmd(j, u, pos, st, P, claims, budget, t):
    """greedy for a released unit: the best open job by value per step (survival x3); shed pickups within budget."""
    inv = st["invs"][j] if j < len(st["invs"]) else _XC()
    best = None
    for jb in _XO["jobs"].values():
        if jb["unit"] is not None and jb["unit"] != j:
            continue
        if jb["deadline"] < t or _xo_tile(st["tiles"], jb["tile"]) == "LOCKED":
            continue
        ok, pre, item = _xo_job_valid(jb, st["tiles"], P)
        if not ok or (jb["tile"] in claims and jb["src"] != "survival"):
            continue
        if jb["op"] == "PLANT" and st["seeds"].get(jb["arg"], 0) <= 0:
            continue
        tp = (jb["tile"] % 10, jb["tile"] // 10)
        if item and inv.get(item, 0) <= 0:
            if budget.get(item, 0) <= 0:
                continue
            sh = _xo_near_shed(pos)
            cost = _xo_dist(pos, sh) + 1 + _xo_dist(sh, tp)
        else:
            cost = _xo_dist(pos, tp)
        cost += len(_xo_job_cmds(jb, pre))
        if t + cost > jb["deadline"] + 2:
            continue
        val = (jb["value"] if jb["value"] is not None else _xo_job_value(jb["op"], jb["arg"], P)) \
            * (3.0 if jb["src"] == "survival" else 1.0)
        key = (val / (1.0 + cost), -jb["id"])
        if best is None or key > best[0]:
            best = (key, jb, item, pre, tp)
    if best is None:
        return ["PASS"]
    _, jb, item, pre, tp = best
    if not _XO.get("dry"):
        jb["unit"] = j
        u["job"] = jb["id"]
    if item and inv.get(item, 0) <= 0:
        if pos in _XO_SHEDSET:
            budget[item] -= 1
            return ["PICKUP", item, 1]
        return _xo_step_toward(pos, _xo_near_shed(pos)) or ["PASS"]
    if pos != tp:
        return _xo_step_toward(pos, tp)
    if pre:
        return [pre]
    if jb["op"] == "PLANT":
        return ["PLANT", jb["arg"]]
    if jb["op"] == "PLACE":
        return ["PLACE", jb["arg"], 1]
    return [jb["op"]]


def _xo_detour(u, j, pos, st, P, claims, t, pl, k):
    """PASS-slot detour of an in-sync unit: a job at q with 2 dist(p, q) + ops <= the run of recorded PASSes from t;
    walk, act, walk back: the unit is on its recorded position again when the run ends."""
    if _XO.get("dry") or not _XO["jobs"]:
        return None
    run, s = 0, t
    while (s // 24) == (t // 24):
        r = _xo_rec(pl, s, k)
        if r is None or not (isinstance(r[2], list) and r[2] and r[2][0] == "PASS"):
            break
        run += 1
        s += 1
    if run < 3:
        return None
    inv = st["invs"][j] if j < len(st["invs"]) else _XC()
    best = None
    for jb in _XO["jobs"].values():
        if jb["unit"] is not None or jb["deadline"] < t or _xo_tile(st["tiles"], jb["tile"]) == "LOCKED":
            continue
        ok, pre, item = _xo_job_valid(jb, st["tiles"], P)
        if not ok or (item and inv.get(item, 0) <= 0) or (jb["tile"] in claims and jb["src"] != "survival"):
            continue
        if jb["op"] == "PLANT" and st["seeds"].get(jb["arg"], 0) <= 0:
            continue
        if item == "WHEAT" and _xo_surplus(pl, k, t, inv, "WHEAT") <= 0:
            continue
        tp = (jb["tile"] % 10, jb["tile"] // 10)
        ops = _xo_job_cmds(jb, pre)
        if 2 * _xo_dist(pos, tp) + len(ops) > run:
            continue
        val = (jb["value"] if jb["value"] is not None else _xo_job_value(jb["op"], jb["arg"], P)) \
            * (3.0 if jb["src"] == "survival" else 1.0)
        if best is None or val > best[0]:
            best = (val, jb, tp, ops)
    if best is None:
        return None
    _, jb, tp, ops = best
    seq, p = [], pos
    while p != tp:
        mv = _xo_step_toward(p, tp)
        seq.append(mv)
        dx, dy = _XO_MOVES[mv[0]]
        p = (p[0] + dx, p[1] + dy)
    seq += ops
    while p != pos:
        mv = _xo_step_toward(p, pos)
        seq.append(mv)
        dx, dy = _XO_MOVES[mv[0]]
        p = (p[0] + dx, p[1] + dy)
    jb["unit"] = j
    u["detour"] = seq
    u["detour_job"] = jb["id"]
    _xo_log("repair", cause="detour_" + jb["op"], unit=j, tile=jb["tile"], src=jb["src"])
    return seq


def _xo_claims(pl, t, day, U):
    """tiles in-sync roles will still act on today (their remaining recorded tile ops)."""
    cl = {}
    if pl is None:
        return cl
    for j, u in U.items():
        k = u.get("role")
        if k is None or u.get("mode") == "rel":
            continue
        i0 = u.get("i", t)
        for (s, tile, op, eff, cmd) in pl["days"].get(day, {}).get("ops", {}).get(k, []):
            if s >= i0:
                cl.setdefault(tile, set()).add(op)
    return cl


def _xo_shed_budget(pl, P, t, day, U):
    """shed stock released units may take: shed minus the in-sync roles' remaining recorded pickups today (B4)."""
    b = _XC(P["shed"])
    if pl is None:
        return b
    for j, u in U.items():
        k = u.get("role")
        if k is None or u.get("mode") == "rel":
            continue
        i0 = u.get("i", t)
        for (s, it, n) in pl["days"].get(day, {}).get("picks", {}).get(k, []):
            if s >= i0:
                b[it] -= n
    return b


def _xo_ucopy(u):
    v = dict(u)
    for key in ("need", "detour"):
        if key in v and isinstance(v[key], list):
            v[key] = [list(x) if isinstance(x, list) else x for x in v[key]]
    return v


def _xo_units_pass(P, t, U, drop):
    pl = _XO["plan"]
    day = t // 24
    claims = _xo_claims(pl, t, day, U)
    budget = _xo_shed_budget(pl, P, t, day, U)
    st = _xo_sim_state(P)
    cmds, meta = [], []
    for j in range(len(P["pos"])):
        u = U.get(j)
        if u is None:
            u = U[j] = dict(role=None, mode="rel")
        cmd, info = _xo_unit_cmd(j, u, st, P, t, claims, budget, drop)
        cmds.append(cmd)
        meta.append(info)
        _xo_apply_one(st, j, cmd, day)
    return cmds, meta, claims


def _xo_plant_cut(cmds, meta, P, t):
    """B1: units whose PLANT is dropped so each crop's plantings fit the seeds held at step start."""
    pl = _XO["plan"]
    stp = _xo_stp(pl, t)
    dem = {}
    for j, c in enumerate(cmds):
        if isinstance(c, list) and len(c) >= 2 and c[0] == "PLANT":
            dem.setdefault(c[1], []).append(j)
    drop = set()
    for crop, js in dem.items():
        have = P["seeds"].get(crop, 0)
        if len(js) <= have:
            continue
        if stp is not None:
            rec_n = sum(1 for e in stp["u"] if isinstance(e[2], list) and len(e[2]) > 1 and e[2][0] == "PLANT" and e[2][1] == crop)
            if rec_n == len(js) and int((stp.get("sd") or {}).get(crop, 0)) == have and all(meta[jj].get("src") == "rec" for jj in js):
                continue            # the recording's own blocked step, same seeds: keep it verbatim (identity)
        js2 = sorted(js, key=lambda jj: (0 if meta[jj].get("src") == "rec" else 1, -float(meta[jj].get("val", 0.0)), jj))
        drop.update(js2[have:])
    return drop


def _xo_build_units(P, t):
    """unit commands for this step: dry passes (no side effects, unit copies) until the per-crop PLANT cut is stable,
    then the final pass (B1)."""
    U = _XO["units"]
    drop = set()
    for _ in range(3):
        U2 = {j: _xo_ucopy(u) for j, u in U.items()}
        _XO["dry"] = True
        try:
            cmds, meta, _ = _xo_units_pass(P, t, U2, drop)
        finally:
            _XO["dry"] = False
        d2 = drop | _xo_plant_cut(cmds, meta, P, t)
        if d2 == drop:
            break
        drop = d2
    cmds, meta, claims = _xo_units_pass(P, t, U, drop)
    for j in drop:
        if j < len(meta) and meta[j].get("src") in ("rec", "sub"):
            _xo_log("breakage", cause="plant_seed_cut", unit=j)
    # safety: a PLANT the dry passes could not see (a detour starting on its own tile) must not block the others
    for j in _xo_plant_cut(cmds, meta, P, t):
        _xo_log("breakage", cause="plant_seed_cut_late", unit=j)
        cmds[j] = ["PASS"]
    return cmds, meta


def _xo_unit_cmd(j, u, st, P, t, claims, budget, drop):
    """one unit's command for this step (u is mutated; the dry passes run on copies)."""
    pl = _XO["plan"]
    day = t // 24
    pos = st["pos"][j]
    mode = u.get("mode")
    if u.get("detour"):
        cmd = u["detour"][0]
        u["detour"] = u["detour"][1:]
        u["i"] = u.get("i", t) + 1                # the recorded PASS run is consumed in lockstep
        if not u["detour"]:
            u.pop("detour", None)
            jid = u.pop("detour_job", None)
            if jid in _XO["jobs"] and not _XO.get("dry"):
                _XO["jobs"][jid]["unit"] = None
        if cmd[0] == "PLANT" and j in drop:
            cmd = ["PASS"]
        return list(cmd), dict(src="detour", val=0.0)
    if mode in ("wait", "walk", "rv"):
        # walk: lagged start at the role's recorded spawn step u["i"]; wait / rv: sync at the recorded step u["gs"]
        at_goal = pos == tuple(u["goal"]) and not u.get("need")
        if at_goal and (mode == "walk" or t >= u.get("gs", t)):
            u["mode"] = mode = "sync"
        else:
            return _xo_goal_cmd(u, pos), dict(src=mode, val=0.0)
    if mode == "sync" and pl is not None and u.get("role") is not None:
        k = u["role"]
        i = u.get("i", t)
        while i < t:                               # absorb lag on recorded PASSes
            r = _xo_rec(pl, i, k)
            if r is not None and isinstance(r[2], list) and r[2] and r[2][0] == "PASS":
                i += 1
            else:
                break
        u["i"] = i
        r = _xo_rec(pl, i, k)
        if r is None or i // 24 != day:
            u["mode"] = "rel"
            return _xo_released_cmd(j, u, pos, st, P, claims, budget, t), dict(src="rel", val=0.0)
        lag = t - i
        if not _XO.get("dry"):
            _XO["lag_max_seen"] = max(_XO["lag_max_seen"], lag)
        if pos != (r[0], r[1]) or lag > 2 * XO_CFG["lag_max"]:
            why = "desync" if pos != (r[0], r[1]) else "lag"
            _xo_log("breakage", cause=why, unit=j, role=k, pos=list(pos), rec=[r[0], r[1]], lag=lag)
            _xo_diverge(why, role=k)
            rv = _xo_rv_search(pl, k, t, pos, st["invs"][j] if j < len(st["invs"]) else _XC(), P)
            if rv is not None:
                s, tgt, need = rv
                _xo_orphan(pl, k, i, s)
                u.update(mode="rv", i=s, goal=tgt, gs=s, need=need)
                _xo_log("rendezvous", cause=why, unit=j, role=k, at=s)
                return _xo_goal_cmd(u, pos), dict(src="rv", val=0.0)
            _xo_orphan(pl, k, i, (t // 24) * 24 + 24)
            u["mode"] = "rel"
            _xo_log("release", cause="no_rendezvous_" + why, unit=j, role=k)
            return _xo_released_cmd(j, u, pos, st, P, claims, budget, t), dict(src="rel", val=0.0)
        cmd = r[2] if isinstance(r[2], list) and r[2] else ["PASS"]
        op = cmd[0]
        tidx = r[1] * 10 + r[0]
        tile = st["tiles"][r[1]][r[0]]
        if op in _XO_MOVES:
            u["i"] = i + 1
            return list(cmd), dict(src="rec", val=0.0)
        if op == "PASS":
            u["i"] = i + 1
            if lag == 0:
                seq = _xo_detour(u, j, pos, st, P, claims, t, pl, k)
                if seq:
                    u["detour"] = seq[1:]
                    if not u["detour"]:
                        u.pop("detour", None)
                    return list(seq[0]), dict(src="detour", val=0.0)
            return ["PASS"], dict(src="rec", val=0.0)
        eff_rec = int(r[3])
        if tile == "LOCKED" and op in _XO_TILE_OPS and not _xo_land_expected(tidx):
            # a quadrant we never buy (land_max): the recorded op cannot happen; the unit keeps its recorded path
            u["i"] = i + 1
            if eff_rec:
                _xo_log("cancel", cause="land_max_op", unit=j, op=op, tile=tidx)
            return ["PASS"], dict(src="sub", val=0.0)
        feas = _xo_probe(st, j, cmd, day)
        dest = _xo_destructive(cmd, tile)
        sig_ok = (r[5] is None) or (_xo_tsig(tile) == list(r[5]))
        if op == "PLANT" and j in drop:
            feas = False
        if not eff_rec:
            # the recording's command had no effect: verbatim (identity) unless it would destroy something of ours
            u["i"] = i + 1
            if dest and feas:
                sub, adv = _xo_substitute(st, j, pos, day, pl, k, i, cmd)
                _xo_log("substitute", cause="noeff_destructive", unit=j, op=op, tile=tidx)
                return sub, dict(src="sub", val=0.0)
            if op == "PLANT" and j in drop:
                return ["PASS"], dict(src="sub", val=0.0)
            return list(cmd), dict(src="rec", val=0.0)
        if feas and dest and (not sig_ok or tidx in _XO["owned"]):
            feas = False
            _xo_log("breakage", cause="destructive_guard", unit=j, op=op, tile=tidx, ours=_xo_tsig(tile), rec=r[5])
            if op == "HARVEST":
                _xo_add_job(tidx, "HARVEST", None, src="guard", deadline=(day + 2) * 24 + 20)
        if feas:
            u["i"] = i + 1
            val = _xo_job_value(op, cmd[1] if len(cmd) > 1 else None, P) if op in ("PLANT", "PLACE") else 0.0
            return list(cmd), dict(src="rec", val=val)
        # the recording's op took effect there but is infeasible here: repair / substitute on the same tile
        _xo_diverge("infeasible_" + op, role=k, tile=tidx)
        sub, adv = _xo_substitute(st, j, pos, day, pl, k, i, cmd)
        cause = "weed" if (op in _XO_ASSET_OPS and _xo_is_weed(tile)) else ("seed_cut" if (op == "PLANT" and j in drop) else "infeasible_" + op)
        _xo_log("breakage", cause=cause, unit=j, role=k, tile=tidx, sub=sub[0])
        if adv:
            u["i"] = i + 1
            if op == "PLANT" and len(cmd) > 1:
                _xo_add_job(tidx, "PLANT", cmd[1], src="catchup", pday=day)
            elif op in ("BUILD_COOP", "BUILD_PASTURE"):
                _xo_add_job(tidx, op, None, src="catchup")
            elif op == "PLACE" and len(cmd) > 1 and cmd[1] in _XO_ANIMALS and r[5] is not None and r[5][0] in ("co", "pa"):
                _xo_add_job(tidx, "PLACE", cmd[1], src="catchup")
        else:
            _xo_log("repair", cause="prereq_" + sub[0], unit=j, tile=tidx)
        return sub, dict(src="sub", val=0.0)
    if mode != "rel":
        u["mode"] = "rel"
    cmd = _xo_released_cmd(j, u, pos, st, P, claims, budget, t)
    if isinstance(cmd, list) and cmd and cmd[0] == "PLANT" and j in drop:
        cmd = ["PASS"]
    return cmd, dict(src="rel", val=_xo_job_value("PLANT", cmd[1], P) if cmd[0] == "PLANT" else 0.0)


def _xo_survival(P, t, day):
    """survival jobs: our assets that die / escape tonight with no remaining recorded op of an in-sync role on them;
    no free capacity for an open one -> release the in-sync role with the lowest remaining value."""
    pl = _XO["plan"]
    covered = _xo_claims(pl, t, day, _XO["units"])
    tiles = P["tiles"]
    dnext = ((pl or {}).get("dayinfo") or {}).get(day + 1) or {}
    knext = dnext.get("key")

    def kept(idx, tl):
        """the recording keeps this asset alive tonight (its next-day state key still shows it), or the tile is
        executor-owned (our asset differs from the recording's): only then does the survival net save it. The
        leader's own deliberate losses (retired animals, abandoned plants) are not repaired, which keeps the
        follower identical to the recording in its own world."""
        if idx in _XO["owned"] or not knext:
            return True
        return list(knext[idx]) == _xo_tsig(tl)
    for idx in range(100):
        tl = _xo_tile(tiles, idx)
        if _xo_is_plant(tl) and not tl.get("watered_today") and int(tl.get("consecutive_unwatered", 0)) >= 1:
            if "WATER" not in covered.get(idx, set()) and kept(idx, tl):
                _xo_add_job(idx, "WATER", None, src="survival", value=200.0)
        elif isinstance(tl, dict) and tl.get("animal") and not tl.get("fed_today") and int(tl.get("consecutive_unfed", 0)) >= 1:
            if "FEED" not in covered.get(idx, set()) and kept(idx, tl):
                _xo_add_job(idx, "FEED", None, src="survival", value=200.0)
    free = [j for j, u in _XO["units"].items() if u.get("mode") == "rel" and not u.get("job")]
    open_s = [jb for jb in _XO["jobs"].values() if jb["src"] == "survival" and jb["unit"] is None]
    if open_s and not free and pl is not None and P["hour"] >= XO_CFG["surv_hour"] + 2:
        best = None
        for j, u in _XO["units"].items():
            if u.get("mode") != "sync" or u.get("role") in (None, 0) or u.get("detour"):
                continue
            v, _ = _xo_role_remaining(pl, u["role"], t, day)
            if best is None or v < best[0]:
                best = (v, j)
        if best is not None:
            u = _XO["units"][best[1]]
            _xo_log("release", cause="survival_net", unit=best[1], role=u.get("role"), value=best[0])
            _xo_orphan(pl, u["role"], max(t, u.get("i", t)), (t // 24) * 24 + 24)
            u["mode"] = "rel"


# =========================================================================================== market (A.5, C)
def _xo_unit_cost(o, prices, hires, quads):
    op = o[0]
    if op == "HIRE":
        return float(_xo_fib(hires))
    if op == "BUY_LAND":
        return float(_XO_LAND_PRICES[min(2, quads)])
    if op == "BUY_SEED":
        return float(_XO_CROPS.get(o[1], {"seed": 10})["seed"])
    if op == "BUY_ANIMAL":
        return float(_XO_ANIMALS.get(o[1], {"cost": 300})["cost"])
    if op == "BUY_PRODUCT":
        return float(prices.get(o[1]) or _XO_BASE.get(o[1], 25)) + 1.0
    return 0.0


def _xo_sim_list(orders, money, stock, prices, hires, quads, sell_frac=0.9):
    """list-order affordability estimate -> (per-order units filled, money left)."""
    m, stock, h, q = money, _XC(stock), hires, quads
    fills = []
    for o in orders:
        op = o[0]
        if op == "SELL":
            u = min(int(o[2]), max(0, stock.get(o[1], 0)))
            stock[o[1]] -= u
            m += u * float(prices.get(o[1], 0) or 0) * sell_frac
            fills.append(u)
        elif op in ("HIRE", "BUY_LAND"):
            c = _xo_unit_cost(o, prices, h, q)
            if m >= c:
                m -= c
                h += op == "HIRE"
                q += op == "BUY_LAND"
                fills.append(1)
            else:
                fills.append(0)
        elif op in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT"):
            c = _xo_unit_cost(o, prices, h, q)
            u = 0
            for _ in range(int(o[2])):
                if m < c:
                    break
                m -= c
                u += 1
                if op == "BUY_PRODUCT":
                    c += 0.2
            if op == "BUY_PRODUCT":
                stock[o[1]] += u
            fills.append(u)
        else:
            fills.append(0)
    return fills, m


def _xo_want_units(o):
    return 1 if o[0] in ("HIRE", "BUY_LAND") else int(o[2])


def _xo_guard_reserve(pl, t, hires):
    """wages of the recording's hires in the next steps until its next SELL (at most 3 steps): the hire guard."""
    res, h = 0.0, hires
    for s in range(t + 1, min(t + 4, (t // 24) * 24 + 24)):
        stp = _xo_stp(pl, s)
        if stp is None:
            break
        mk = stp.get("mk", [])
        if any(isinstance(o, list) and o and o[0] == "SELL" for o, f, c in mk):
            break
        for o, f, c in mk:
            if isinstance(o, list) and o and o[0] == "HIRE" and f:
                res += _xo_fib(h)
                h += 1
    return res


def _xo_deps(key, q, P, t):
    """the next q uses (catch-up jobs first, then the recording's future effective PLANT / PLACE) not covered by
    what we hold: [(dependent step, tile)]."""
    pl = _XO["plan"]
    kind, name = key.split(":")
    if kind == "SEED":
        held = P["seeds"].get(name, 0)
        pend = [(jb["created"], jb["tile"]) for jb in _XO["jobs"].values() if jb["op"] == "PLANT" and jb["arg"] == name]
    else:
        held = P["shed"].get(name, 0) + sum(i.get(name, 0) for i in P["invs"])
        pend = [(jb["created"], jb["tile"]) for jb in _XO["jobs"].values() if jb["op"] == "PLACE" and jb["arg"] == name]
    fut = [(s, tile) for (s, tile) in (pl["uses"].get(key, []) if pl else []) if s >= t]
    seq = sorted(pend) + fut
    return seq[held:held + q]


def _xo_item_ratio(o, P, t, kd):
    """(ratio, ev_loss, first dependent step) of a buy: expected value lost per coin freed over k days (B7)."""
    pl = _XO["plan"]
    day = t // 24
    prices = P["prices"]
    D = _XO.get("D_plan", XO_CFG["D_fixed"])
    cr = XO_CFG["cash_rate"]
    op = o[0]
    cost = _xo_unit_cost(o, prices, P["hires_today"], len(P["unlocked"]) - 1) * _xo_want_units(o)
    if op in ("BUY_SEED", "BUY_ANIMAL"):
        key = _xo_okey(o)
        deps = _xo_deps(key, int(o[2]), P, t)
        if not deps:
            return 0.0, 0.0, 10 ** 9          # nothing in the plan uses it (an over-ask): cut first
        loss, first = 0.0, 10 ** 9
        for s, tile in deps:
            pd = max(day, s // 24)
            first = min(first, s)
            if op == "BUY_SEED":
                loss += xo_delay_cost("crop", o[1], pd, max(pd, day + kd), day, prices, D, cr)
            else:
                loss += xo_delay_cost("animal", o[1], pd, max(pd, day + kd), day, prices, D, cr)
        return loss / max(1.0, cost), loss, first
    if op == "BUY_PRODUCT" and o[1] == "WHEAT":
        rise = max(0.2, _xo_price_fc("WHEAT", day + kd, day, prices) - _xo_price_fc("WHEAT", day, day, prices))
        loss = rise * int(o[2])
        return loss / max(1.0, cost), loss, 10 ** 9 - 1
    if op == "BUY_PRODUCT" and o[1] == "FERTILIZER":
        crops = [c for s, c in (pl["fert_uses"] if pl else []) if t <= s < t + 24 and c]
        v = 0.0
        for c2 in crops[:int(o[2])]:
            v += 1.5 * _xo_price_fc(c2, day + 3, day, prices) * min(kd, 3) / 3.0
        return v / max(1.0, cost), v, 10 ** 9 - 2
    if op == "BUY_LAND":
        quad = _XO_LAND_ORDER[min(2, len(P["unlocked"]) - 1)]
        loss, first = 0.0, 10 ** 9
        for key, lst in (pl["uses"].items() if pl else []):
            kind, name = key.split(":")
            for (s, tile) in lst:
                if _xo_quad(tile) == quad and t <= s < t + 72:
                    pd = s // 24
                    loss += xo_delay_cost("crop" if kind == "SEED" else "animal", name, pd, max(pd, day + kd), day, prices, D, cr)
                    first = min(first, s)
        return loss / max(1.0, cost), loss, first
    if op == "HIRE":
        return 0.0, 0.0, 10 ** 9              # a hire of a role with no committed op left today
    return 0.0, 0.0, 10 ** 9


def _xo_committed_roles(pl, t, day):
    """roles with a remaining recorded op today that took effect in the recording (their wages are tier 0)."""
    out = {0}
    for k, ops in (pl["days"].get(day, {}).get("ops", {}).items() if pl else []):
        if any(s >= t and eff for (s, tile, op, eff, cmd) in ops):
            out.add(k)
    return out


def _xo_feed_need(P, post, t):
    """tier-0 feed wheat: animals not yet fed today plus the recording's placements later today, minus the wheat held
    (and from hour 18 tomorrow's morning need when the recording buys no wheat before hour 6 tomorrow)."""
    pl = _XO["plan"]
    day = t // 24
    n_unfed = sum(1 for idx in range(100) if _xo_animal(_xo_tile(post["tiles"], idx)) and not _xo_tile(post["tiles"], idx).get("fed_today"))
    placing = sum(1 for key, lst in (pl["uses"].items() if pl else []) if key.startswith("ANIMAL:")
                  for (s, tile) in lst if t < s < day * 24 + 24)
    held = post["shed"].get("WHEAT", 0) + sum(i.get("WHEAT", 0) for i in post["invs"])
    need = n_unfed + placing - held
    if P["hour"] >= 18 and pl is not None:
        early = False
        for s in range((day + 1) * 24, (day + 1) * 24 + 6):
            stp = _xo_stp(pl, s)
            if stp and any(isinstance(o, list) and len(o) > 1 and o[0] == "BUY_PRODUCT" and o[1] == "WHEAT" and f
                           for o, f, c in stp.get("mk", [])):
                early = True
        if not early:
            n_anim = sum(1 for idx in range(100) if _xo_animal(_xo_tile(post["tiles"], idx)))
            need = max(need, n_unfed + placing + n_anim - held)
    return max(0, need)


def _xo_market(P, t, post):
    """the recording's market list of this step, verbatim when our state equals the recording's; else transformed
    with the cumulative caps and catch-ups, then the failsafe."""
    pl = _XO["plan"]
    hour = t % 24
    stp = _xo_stp(pl, t)
    rec = [list(o) for o, f, c in stp.get("mk", [])] if stp else []
    if stp is not None and XO_CFG["hold"] <= 0 and not _XO["queue"]:
        ident = (abs(P["money"] - float(stp["m"])) < 1e-6 and _xo_cnt(stp["sh"]) == P["shed"]
                 and _xo_cnt(stp["sd"]) == P["seeds"] and len(P["unlocked"]) - 1 == int(stp.get("q", -1))
                 and P["hires_today"] == int(stp.get("ht", -1))
                 and not any(_XO["carry"].values()) and not any(_XO["adj"].values()) and not any(_XO["carryS"].values()))
        if ident:
            return rec
    _XO["count"]["market_transformed"] += 1
    _xo_diverge("market_state", money=round(P["money"], 1), rec_money=(stp or {}).get("m"))
    wb, ws, wh, wl = _xo_wants(P, t)
    stock = _XC(post["shed"])
    out = []
    for o in rec:
        op = o[0] if o else None
        if op == "HIRE":
            if wh > 0 and hour < 23:
                out.append(["HIRE"])
                wh -= 1
        elif op in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT") and len(o) >= 3:
            k = _xo_okey(o)
            q = min(int(o[2]), wb.get(k, 0))
            if q > 0:
                out.append([op, o[1], q])
                wb[k] -= q
                if op == "BUY_PRODUCT":
                    stock[o[1]] += q
        elif op == "SELL" and len(o) >= 3:
            q = min(int(o[2]), max(0, stock.get(o[1], 0)), ws.get(o[1], 0))
            if q > 0:
                out.append(["SELL", o[1], q])
                stock[o[1]] -= q
                ws[o[1]] -= q
            elif int(o[2]) > 0 and ws.get(o[1], 0) > 0:
                _xo_log("breakage", cause="sale_short", item=o[1], qty=int(o[2]))
        elif op == "BUY_LAND":
            if wl > 0:
                out.append(["BUY_LAND"])
                wl -= 1
            else:
                _xo_log("cancel", cause="land_max", item="LAND")
    front = []
    for p in sorted(ws):
        q = min(ws[p], max(0, stock.get(p, 0)))
        if q > 0:
            front.append(["SELL", p, q])               # unsold recorded sales: they fund the buys, so first
            stock[p] -= q
    if hour < XO_CFG["rv_hour"]:
        out += [["HIRE"] for _ in range(wh)]            # failed / late hires retried
    for k in sorted(wb):
        kind, it = k.split(":")
        out.append([{"SEED": "BUY_SEED", "ANIMAL": "BUY_ANIMAL", "PRODUCT": "BUY_PRODUCT"}[kind], it, wb[k]])
    if wl > 0 and not any(o[0] == "BUY_LAND" for o in out):
        out.append(["BUY_LAND"])
    # tier-0 feed wheat: when the list buys less than today's feed need, a catch-up buy (the cumulative cap then
    # trims the recording's later wheat buys)
    fneed = _xo_feed_need(P, post, t) - sum(int(o[2]) for o in out if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")
    if fneed > 0 and pl is not None:            # the recording's own wheat buys later today (its cap allows them)
        later = 0
        for s in range(t + 1, (t // 24) * 24 + 22):
            stq = _xo_stp(pl, s)
            if stq:
                later += sum(int(f) for o, f, c in stq.get("mk", [])
                             if isinstance(o, list) and len(o) > 1 and o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")
        fneed -= later
    if fneed > 0 and hour < 23:
        out.append(["BUY_PRODUCT", "WHEAT", fneed])
        _xo_log("repair", cause="feed_wheat_catchup", qty=fneed)
    return _xo_failsafe(P, t, post, front + out)


def _xo_failsafe(P, t, post, lst):
    """C: when the list is not affordable (money - hold reserve - hire guard): tier 0 (wages of committed roles, feed
    wheat) goes first after the sales; the rest is kept by EV lost per coin freed (ev) or in list order (naive) while
    it fits; the rest is deferred (it stays in the cumulative deficit and is retried every step) or cancelled."""
    pl = _XO["plan"]
    day = t // 24
    prices = P["prices"]
    quads = len(P["unlocked"]) - 1
    h0 = P["hires_today"]
    guard = _xo_guard_reserve(pl, t, h0 + sum(1 for o in lst if o[0] == "HIRE"))
    budget = P["money"] - _XO["hold_res"]
    fills, _ = _xo_sim_list(lst, budget - guard, post["shed"], prices, h0, quads)
    if all(f >= _xo_want_units(o) for o, f in zip(lst, fills) if o[0] != "SELL"):
        _XO["queue"].clear()
        _XO["queue_coins"] = 0.0
        return lst[:10]
    sells = [o for o in lst if o[0] == "SELL"]
    hires = [o for o in lst if o[0] == "HIRE"]
    lands = [o for o in lst if o[0] == "BUY_LAND"]
    buys = [o for o in lst if o[0] in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT")]
    committed = _xo_committed_roles(pl, t, day)
    tier0_h, rest_h = [], []
    for n_, o in enumerate(hires):
        (tier0_h if (h0 + n_ + 1) in committed else rest_h).append(o)
    feed = _xo_feed_need(P, post, t)
    tier0_w, items = [], []
    for o in buys:
        if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT" and feed > 0:
            q0 = min(int(o[2]), feed)
            tier0_w.append(["BUY_PRODUCT", "WHEAT", q0])
            feed -= q0
            if int(o[2]) > q0:
                items.append(["BUY_PRODUCT", "WHEAT", int(o[2]) - q0])
        else:
            items.append(list(o))
    items += rest_h + lands
    t0 = sells + tier0_h + tier0_w
    f0, m0 = _xo_sim_list(t0, budget, post["shed"], prices, h0, quads)
    short0 = any(f < _xo_want_units(o) for o, f in zip(t0, f0) if o[0] != "SELL")
    if short0 and pl is not None:
        # pull today's later recorded SELLs of items already in the shed forward: the fewest needed, then the hires
        stock = _XC(post["shed"])
        for o in sells:
            stock[o[1]] -= int(o[2])
        for s in range(t + 1, day * 24 + 24):
            stp = _xo_stp(pl, s)
            if not stp or not short0:
                break
            for o, f, c in stp.get("mk", []):
                if isinstance(o, list) and o and o[0] == "SELL" and f and stock.get(o[1], 0) > 0:
                    q = min(int(f), stock[o[1]])
                    sells = sells + [["SELL", o[1], q]]
                    stock[o[1]] -= q
                    _XO["carryS"][o[1]] -= q            # sold ahead of the recording: its later cap is met early
                    _xo_log("repair", cause="sells_forward", item=o[1], qty=q)
                    t0 = sells + tier0_h + tier0_w
                    f0, m0 = _xo_sim_list(t0, budget, post["shed"], prices, h0, quads)
                    short0 = any(f2 < _xo_want_units(o2) for o2, f2 in zip(t0, f0) if o2[0] != "SELL")
                    if not short0:
                        break
    if short0:
        _XO["t0short"][day] += 1
        _xo_log("breakage", cause="tier0_short", money=round(P["money"], 1))
    avail = m0 - guard
    need = sum(_xo_unit_cost(o, prices, h0, quads) * _xo_want_units(o) for o in items)
    kd = _xo_kdays(t, max(0.0, need - max(0.0, avail)))
    if XO_CFG["failsafe"] == "naive":
        order = [(o, None, None) for o in items]                    # the recording's list order
    else:
        sc = []
        for n_, o in enumerate(items):
            ratio, loss, first = _xo_item_ratio(o, P, t, kd)
            sc.append((-ratio, first, n_, o, ratio, loss))
        sc.sort(key=lambda z: z[:3])                               # ratio desc; ties FIFO by the dependent op's step
        order = [(z[3], z[4], z[5]) for z in sc]
    m, h = avail, h0 + len(tier0_h)
    kept, rest, qcoins = [], [], 0.0
    for o, ratio, loss in order:
        c = _xo_unit_cost(o, prices, h, quads)
        want = _xo_want_units(o)
        u = 0
        while u < want and m >= c:
            m -= c
            u += 1
            if o[0] == "HIRE":
                h += 1
                c = _xo_unit_cost(o, prices, h, quads)
            elif o[0] == "BUY_PRODUCT":
                c += 0.2
        if u > 0:
            kept.append(list(o) if o[0] in ("HIRE", "BUY_LAND") else [o[0], o[1], u])
        if u < want:
            dc = _xo_cut(o, want - u, _xo_unit_cost(o, prices, h, quads), t, kd, ratio, loss)
            qcoins += dc
            if dc > 0 and o[0] not in ("HIRE", "BUY_LAND"):
                rest.append([o[0], o[1], want - u])
    _XO["queue_coins"] = qcoins
    _XO["deferred_by_day"][day] = max(_XO["deferred_by_day"].get(day, 0.0), qcoins)
    out = sells + tier0_h + tier0_w + kept
    if guard <= 0:
        # the affordability estimate is conservative (sales at 0.9 of the quote): deferred buys stay at the end of
        # the list, in the same priority order, so whatever the real proceeds cover is still bought this step (the
        # engine stops each order at its first unaffordable unit; no hire is waiting on these coins)
        out = out + rest
    return out[:10]


def _xo_kdays(t, short):
    """expected deferral length (days): until the recording's projected surplus, at our revenue ratio, covers it."""
    pl = _XO["plan"]
    if short <= 0 or pl is None:
        return 1
    day = t // 24
    acc = 0.0
    for d in range(day + 1, min(29, day + 8)):
        di = pl["dayinfo"].get(d)
        if di:
            acc += _XO.get("rev_ratio", 0.93) * float(di.get("V", 0.0)) - float(di.get("R", 0.0))
        if acc >= short:
            return max(1, d - day)
    return 3


def _xo_cut(o, q, unit_cost, t, kd, ratio, loss):
    """a cut: deferred (it stays in the cumulative deficit, retried every step, re-ranked) or cancelled (no feasible
    date left: past plant_cutoff / last_animal, or a hire at the end of the day). -> deferred coins."""
    day = t // 24
    key = _xo_okey(o) or o[0]
    cancel = (o[0] == "BUY_SEED" and day > _XO_CUTOFF.get(o[1], 29)) or \
             (o[0] == "BUY_ANIMAL" and day > _XO_LAST_ANIMAL.get(o[1], 29))
    new = key not in _XO["queue"]
    if new or cancel:
        rec = dict(step=t, day=day, item=key, qty=int(q), coins=round(unit_cost * q, 1), k=kd,
                   ratio=None if ratio is None else round(ratio, 4), ev_loss=None if loss is None else round(loss, 1),
                   action="cancel" if cancel else "defer", arm=XO_CFG["failsafe"])
        if len(_XO["cuts"]) < 1500:
            _XO["cuts"].append(rec)
    if cancel and key.split(":")[0] in ("SEED", "ANIMAL", "PRODUCT"):
        _XO["adj"][key] -= int(q)
        _xo_log("cancel", cause="cutoff", item=key, qty=int(q))
        return 0.0
    if new:
        _xo_log("defer", cause="cash", item=key, qty=int(q), ratio=None if ratio is None else round(ratio, 4),
                ev=None if loss is None else round(loss, 1))
    _XO["queue"][key] = int(q)
    _XO["count"]["defer_steps"] += 1
    return unit_cost * q


# =========================================================================================== day start
def _xo_dayinfo():
    """per-day plan flows {d: {V, R, land_q, cash, ...}}: the compiled plan's, else the replay mode's (from the
    recording's semantics, scripts/xopen_cash_safe.sem_flows logic; set by the E1 glue)."""
    di = _XO.get("dayinfo")
    if di:
        return di
    pl = _XO.get("plan")
    return (pl or {}).get("dayinfo") or {}


def _xo_dyn_rule(P, t):
    """the cash-safe rule at hour 0 of day t: the plan stays funded on every morning t..horizon with its revenue cut
    by h = max(h_min, our shortfall so far) and the margin; R_plan without land beyond land_max, plus the queue."""
    dinfo = _xo_dayinfo()
    day = t // 24
    if not dinfo:
        return False, {}
    got = sum(v for d, v in _XO["revenue"].items() if d < day)
    exp_ = sum(float(dinfo.get(d, {}).get("V", 0.0)) for d in range(0, day))
    h = max(XO_CFG["dyn_h_min"], 1.0 - got / max(1.0, exp_))
    B = P["money"] - _XO["hold_res"]
    for s in range(day, XO_CFG["dyn_horizon"] + 1):
        di = dinfo.get(s)
        if not di:
            continue
        lq = di.get("land_q") or []                     # quadrant indexes the recording bought that day
        R = float(di.get("R", 0.0)) - sum(_XO_LAND_PRICES[q] for q in lq if q >= XO_CFG["land_max"])
        if s == day:
            R += _XO.get("queue_coins", 0.0)
        if B < XO_CFG["dyn_margin"] * R:
            return False, dict(h=round(h, 3), fail_day=s, B=round(B, 1), R=round(R, 1))
        B += (1.0 - h) * float(di.get("V", 0.0)) - R
    return True, dict(h=round(h, 3), B_end=round(B, 1))


def _xo_day_start(P, t):
    """hour 0: logs, handoff decision, re-retrieval, weed scan, hidden-state compare, executor-owned tiles, abort.
    -> None (keep following) or the handoff reason."""
    pl = _XO["plan"]
    day = t // 24
    _XO["units"] = {0: dict(role=0, mode="sync", i=t)}
    for jb in list(_XO["jobs"].values()):
        jb["unit"] = None
        if jb["deadline"] < t or jb["src"] in ("survival", "owned"):
            _XO["jobs"].pop(jb["id"], None)
    if pl is not None:
        exp_ = sum(float(pl["dayinfo"].get(d, {}).get("V", 0.0)) for d in range(day))
        _XO["rev_ratio"] = sum(_XO["revenue"].values()) / exp_ if exp_ > 0 else 1.0
        di = pl["dayinfo"].get(day)
        if di:
            lab = [_xo_label(x) for row in P["tiles"] for x in row]
            _XO["ham_by_day"][day] = sum(1 for a, b in zip(lab, di.get("board", lab)) if a != b)
            hid = di.get("hidden")
            if hid:
                mm = 0
                for idx in range(100):
                    a, b = _xo_hidden(_xo_tile(P["tiles"], idx)), hid[idx]
                    if (a is None) != (b is None) or (a is not None and list(a) != list(b)[:len(a)]):
                        mm += 1
                _XO["hidden_by_day"][day] = mm
                if mm and _XO.get("first_hidden") is None:
                    _XO["first_hidden"] = day
            _XO["plan_cash_by_day"][day] = di.get("cash")
    # handoff decision; the dynamic rule is evaluated in shadow from D_floor
    reason = None
    if XO_CFG["D_floor"] <= day < XO_CFG["D_cap"] and _XO.get("D_shadow") is None:
        ok, info = _xo_dyn_rule(P, t)
        _XO.setdefault("dyn_trace", {})[day] = info
        if ok:
            _XO["D_shadow"] = day
    if XO_CFG["dyn"]:
        if _XO.get("D_shadow") == day:
            reason = "dyn"
        elif day >= XO_CFG["D_cap"]:
            reason = "cap"
    elif day >= XO_CFG["D_fixed"]:
        reason = "fixed"
    if reason is None and pl is not None:
        if _XO["ham_by_day"].get(day, 0) > XO_CFG["abort_ham"]:
            reason = "abort_hamming"
        elif len(_XO["owned"]) > XO_CFG["abort_owned"]:
            reason = "abort_owned"
        elif _XO["t0short"].get(day - 1, 0) and _XO["t0short"].get(day - 2, 0):
            reason = "abort_tier0"
        elif t >= pl["T1"]:
            reason = "abort_plan_end"
    if reason is not None:
        return reason
    if pl is not None and day == 6 and XO_CFG["reretrieve6"]:
        _xo_reretrieve(P, t, day)
    elif pl is not None and day == 9 and XO_CFG["reretrieve9"]:
        _xo_reretrieve(P, t, day)
    pl = _XO["plan"]
    if pl is None:
        return None
    # weed scan: tiles the recording plants / builds on today or tomorrow (not where the recording digs the weed
    # itself before that op: its own DIG is followed like any other command)
    for d in (day, day + 1):
        digs = {}
        for k, ops in pl["days"].get(d, {}).get("ops", {}).items():
            for (s, tile, op, eff, cmd) in ops:
                if eff and op == "DIG":
                    digs[tile] = min(digs.get(tile, 10 ** 9), s)
        for k, ops in pl["days"].get(d, {}).get("ops", {}).items():
            for (s, tile, op, eff, cmd) in ops:
                if eff and op in _XO_ASSET_OPS and _xo_is_weed(_xo_tile(P["tiles"], tile)) and digs.get(tile, 10 ** 9) > s:
                    _xo_add_job(tile, "DIG", None, src="weed", deadline=max(t, s - 1), value=80.0)
    # executor-owned tiles (B.3): a live asset of ours where the recording has another label, or 2+ days off
    di = pl["dayinfo"].get(day)
    if di and di.get("key"):
        for idx in range(100):
            a = _xo_tile(P["tiles"], idx)
            if not (_xo_is_plant(a) or _xo_animal(a)):
                continue
            b, sa = di["key"][idx], _xo_tsig(a)
            off = (b[1] is not None and sa[1] is not None and abs(int(b[1]) - int(sa[1])) >= 2)
            if (b[0] != sa[0] or off) and idx not in _XO["owned"]:
                _XO["owned"].add(idx)
                _xo_log("breakage", cause="owned_tile", tile=idx, ours=sa, rec=b)
    for idx in _XO["owned"]:
        _xo_add_job(idx, "HARVEST", None, src="owned", deadline=day * 24 + 21, value=40.0)
    return None


def _xo_reretrieve(P, t, day):
    """day 6: among the pool games whose day-6 state equals ours (<= pool_max_diff tiles, hidden shed / seed stock
    close), the smallest shop distance for our two revealed shops; ties: day-6 cash <= ours, then |cash - ours|,
    then DSM before Vadim, then the episode id. Day 9: only an exactly state-identical game with a lower 3-shop
    distance than the plan followed."""
    pool = _xo_pool_index()
    if not pool:
        return
    key = _xo_statekey(P["tiles"])
    n_sh = 3 if day >= 9 else 2
    shops = P["shops"][:n_sh]
    qv = _xo_demand_vec(shops)
    cur = _XO["plan"]
    cands = []
    for g in pool:
        if int(g["ep"]) in _XO["exclude"]:
            continue
        gk = g.get("key%d" % day)
        if not gk:
            continue
        diff = sum(1 for a, b in zip(key, gk) if list(a) != list(b))
        if diff > (0 if day == 9 else XO_CFG["pool_max_diff"]):
            continue
        hs = g.get("shed%d" % day) or {}
        if abs(int(hs.get("WHEAT", 0)) - P["shed"].get("WHEAT", 0)) > 2 or \
                abs(int(hs.get("FERTILIZER", 0)) - P["shed"].get("FERTILIZER", 0)) > 2:
            continue
        sd = g.get("seeds%d" % day) or {}
        if any(abs(int(sd.get(c, 0)) - P["seeds"].get(c, 0)) > 1 for c in _XO_CROPS):
            continue
        dist = _xo_shop_dist(qv, _xo_demand_vec(list(g["shops"])[:n_sh]))
        cash = float(g.get("cash%d" % day, 0.0))
        cands.append((diff, round(dist, 6), 0 if cash <= P["money"] else 1, abs(cash - P["money"]),
                      0 if str(g["team"]) == "16732748" else 1, int(g["ep"]), g))
    if not cands:
        _xo_log("reretrieve", cause="no_candidate", day=day)
        return
    cands.sort(key=lambda z: z[:6])
    best = cands[0][6]
    kk = "%s_%s" % (best["team"], best["ep"])
    if day == 9:
        if cur is not None and not (cands[0][1] < _xo_shop_dist(qv, _xo_demand_vec(list(_XO["plan_shops"])[:n_sh]))):
            return
    if cur is not None and kk == cur["key"]:
        _XO["plans"].append(dict(day=day, key=kk, shop_dist=cands[0][1], diff=cands[0][0], kept=True, n_cands=len(cands)))
        return
    try:
        newp = xo_load_plan(kk)
    except Exception as exc:
        _xo_log("reretrieve", cause="load_failed", key=kk, err=str(exc)[:80])
        return
    _xo_switch_plan(newp, t)
    _XO["plans"].append(dict(day=day, key=kk, shop_dist=cands[0][1], diff=cands[0][0], cash=best.get("cash%d" % day),
                             n_cands=len(cands)))
    _xo_log("reretrieve", cause="switch", key=kk, day=day, shop_dist=cands[0][1], n=len(cands))


def _xo_switch_plan(newp, t):
    """keep the cumulative deficits continuous at a plan switch: carry += old - new cumulative counts through t-1."""
    old = _XO["plan"]
    Eo, En = _xo_cum(old, t - 1, "E"), _xo_cum(newp, t - 1, "E")
    So, Sn = _xo_cum(old, t - 1, "S"), _xo_cum(newp, t - 1, "S")
    for k in set(Eo) | set(En):
        _XO["carry"][k] += Eo.get(k, 0) - En.get(k, 0)
    for k in set(So) | set(Sn):
        _XO["carryS"][k] += So.get(k, 0) - Sn.get(k, 0)
    Qo = (old["Q0"] + _xo_cum(old, t - 1, "Q")) if old else 0
    Qn = newp["Q0"] + _xo_cum(newp, t - 1, "Q")
    if Qo != Qn:
        _xo_log("breakage", cause="switch_land_mismatch", old=Qo, new=Qn)
    _XO["plan"] = newp
    _XO["plan_shops"] = list(newp.get("shops") or [])


_XO_POOL = None
_XO_DEM = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
           'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
           'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
           'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
           'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
_XO_DPROD = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
_XO_DW = (3.0, 2.0, 2.0, 1.5, 1.5, 1.0, 0.5)


def _xo_demand_vec(shops):
    """= scripts/leader_plan_retrieval.demand_vec"""
    c = [0] * len(_XO_DPROD)
    for s in shops:
        for p, n in _XO_DEM.get(s, {}).items():
            c[_XO_DPROD.index(p)] += n
    return tuple(c)


def _xo_shop_dist(a, b):
    """= scripts/leader_plan_retrieval.shop_distance"""
    return sum(w * abs(x - y) for w, x, y in zip(_XO_DW, a, b))


def _xo_pool_index():
    global _XO_POOL
    if _XO_POOL is None:
        try:
            with open(_xo_os.path.join(xo_plans_dir(), "pool_index.json"), encoding="utf-8") as fh:
                _XO_POOL = _xo_json.load(fh)
        except Exception:
            _XO_POOL = []
    return _XO_POOL


# =========================================================================================== main step
def xo_follow_step(obs):
    """one following step -> (action dict, None), or (None, reason) to hand off now."""
    t0 = _xo_time.time()
    P = _xo_parse(obs)
    t = P["step"]
    _XO["t"] = t
    day, hour = P["day"], P["hour"]
    prev = _XO["prev"]
    if prev is not None and prev["step"] == t - 1:
        _xo_apply_fills(xo_infer(prev, P), P, prev["day"])
    else:
        _XO["quads"] = len(P["unlocked"]) - 1
    _XO["hires_today"] = P["hires_today"]
    for k in list(_XO["queue"]):                          # deferrals the cumulative deficits no longer hold are done
        wb, _, _, _ = _xo_wants(P, t - 1)
        if wb.get(k, 0) <= 0:
            _XO["queue"].pop(k, None)
    _xo_observe_P(P)
    if hour == 0:
        reason = _xo_day_start(P, t)
        if reason is not None:
            return None, reason
    if hour >= XO_CFG["surv_hour"]:
        _xo_survival(P, t, day)
    _xo_assign_new_hands(P, t)
    for jb in list(_XO["jobs"].values()):                 # jobs done / expired
        ok, pre, item = _xo_job_valid(jb, P["tiles"], P)
        if ok and jb["deadline"] >= t:
            if jb["unit"] is not None:
                u = _XO["units"].get(jb["unit"], {})
                if not (u.get("mode") == "rel" and u.get("job") == jb["id"]) and u.get("detour_job") != jb["id"]:
                    jb["unit"] = None
            continue
        if not ok:
            _xo_log("repair", cause="done_" + jb["src"] + "_" + jb["op"], tile=jb["tile"])
        elif jb["src"] not in ("survival", "owned", "guard"):
            _xo_log("breakage", cause="irreparable_" + jb["op"], tile=jb["tile"])
            if jb["op"] in ("PLANT", "BUILD_COOP", "BUILD_PASTURE", "PLACE"):
                _XO["owned"].add(jb["tile"])
        u = _XO["units"].get(jb["unit"]) if jb["unit"] is not None else None
        if u is not None and u.get("job") == jb["id"]:
            u.pop("job", None)
        _XO["jobs"].pop(jb["id"], None)
    cmds, meta = _xo_build_units(P, t)
    post = xo_sim_units(P, cmds)
    market = _xo_market(P, t, post)
    act = {"farmer": cmds[0], "hands": cmds[1:], "market": market}
    pl = _XO["plan"]
    stp = _xo_stp(pl, t)
    if stp is not None and _XO.get("first_div_exact") is None:
        ru = [e[2] for e in stp["u"]]
        rm = [o for o, f, c in stp.get("mk", [])]
        if ru != cmds or rm != market:
            _XO["first_div_exact"] = dict(step=t, day=day, hour=hour, units=ru != cmds, market=rm != market,
                                          cause=(_XO.get("first_div") or {}).get("cause"))
    _XO["prev"] = dict(step=t, day=day, money=P["money"], unl=len(P["unlocked"]), orders=market, post=post,
                       prices=P["prices"], hires_before=P["hires_today"])
    dt = _xo_time.time() - t0
    _XO["tmax"] = max(_XO["tmax"], dt)
    _XO["tsum"] += dt
    return act, None


def _xo_placed_log(P, day):
    """animals placed on day-1, read at hour 0 of day from placed_day (a placed-yesterday animal cannot have escaped)."""
    if day <= 0:
        return
    c = _XC()
    for row in P["tiles"]:
        for tl in row:
            if isinstance(tl, dict) and tl.get("animal") and tl.get("placed_day") == day - 1:
                c[tl["animal"]] += 1
    _XO["placed_by_day"][day - 1] = dict(c)


def _xo_observe_P(P):
    """every step, every phase (following, replay, after the handoff): cash at hour 0, animals placed by day, and
    plantings by day (a (tile, planted_day) pair seen for the first time; the unit phase of step t shows at t+1)."""
    day = P["day"]
    if P["hour"] == 0:
        _XO["cash_by_day"][day] = P["money"]
        _xo_placed_log(P, day)
    seen = _XO.setdefault("plant_seen", set())
    pbd = _XO.setdefault("plants_by_day", {})
    for y, row in enumerate(P["tiles"]):
        for x, tl in enumerate(row):
            if isinstance(tl, dict) and tl.get("kind") == "PLANT":
                key = (y * 10 + x, tl.get("planted_day"))
                if key not in seen:
                    seen.add(key)
                    c = pbd.setdefault(int(tl.get("planted_day", day)), {})
                    c[tl["crop"]] = c.get(tl["crop"], 0) + 1


def xo_observe(obs):
    """light bookkeeping on every step after the handoff: cash, animals placed and plantings by day."""
    try:
        _xo_observe_P(_xo_parse(obs))
    except Exception:
        pass


def xo_replay_step(obs):
    """replay modes: the tape's action verbatim ('replay', optionally without some BUY_LAND orders), or its unit
    commands with the market capped by the compiled plan's effective totals ('replay_capped'; land <= land_max)."""
    P = _xo_parse(obs)
    t = P["step"]
    _XO["t"] = t
    _xo_observe_P(P)
    tape = _XO["tape"]
    a = tape["actions"][t] if tape is not None and t < len(tape["actions"]) and isinstance(tape["actions"][t], dict) else {}
    act = _xo_json.loads(_xo_json.dumps(a)) if a else {"farmer": ["PASS"], "hands": [], "market": []}
    act.setdefault("farmer", ["PASS"])
    act.setdefault("hands", [])
    act.setdefault("market", [])
    if XO_CFG["mode"] == "replay_capped" and _XO["plan"] is not None:
        prev = _XO["prev"]
        if prev is not None and prev["step"] == t - 1:
            _xo_apply_fills(xo_infer(prev, P), P, prev["day"])
        wb, ws, wh, wl = _xo_wants(P, t)
        out = []
        for o in act["market"] or []:
            op = o[0] if isinstance(o, list) and o else None
            if op == "HIRE":
                if wh > 0:
                    out.append(o)
                    wh -= 1
            elif op in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT") and len(o) >= 3:
                k = _xo_okey(o)
                q = min(int(o[2]), wb.get(k, 0))
                if q > 0:
                    out.append([op, o[1], q])
                    wb[k] -= q
            elif op == "BUY_LAND":
                if wl > 0:
                    out.append(o)
                    wl -= 1
                else:
                    _xo_log("cancel", cause="land_max", item="LAND")
            else:
                out.append(o)
        act["market"] = out
        cmds = [act["farmer"]] + list(act["hands"])
        _XO["prev"] = dict(step=t, day=P["day"], money=P["money"], unl=len(P["unlocked"]), orders=out,
                           post=xo_sim_units(P, cmds), prices=P["prices"], hires_before=P["hires_today"])
    else:
        if XO_CFG.get("drop_land"):
            mk, nl = [], 0
            for o in act["market"] or []:
                if isinstance(o, list) and o and o[0] == "BUY_LAND":
                    if (len(P["unlocked"]) - 1 + nl) in XO_CFG["drop_land"]:
                        _xo_log("cancel", cause="drop_land", item="LAND")
                        continue
                    nl += 1
                mk.append(o)
            act["market"] = mk
        # our fills of the previous step (revenue by day for the dynamic rule, sold units for the handoff); the
        # commands and orders are not changed by this bookkeeping
        prev = _XO["prev"]
        if prev is not None and prev["step"] == t - 1:
            _xo_apply_fills(xo_infer(prev, P), P, prev["day"])
        cmds = [act.get("farmer") or ["PASS"]] + list(act.get("hands") or [])
        mko = act.get("market") if isinstance(act.get("market"), list) else []
        _XO["prev"] = dict(step=t, day=P["day"], money=P["money"], unl=len(P["unlocked"]), orders=list(mko)[:10],
                           post=xo_sim_units(P, cmds), prices=P["prices"], hires_before=P["hires_today"])
    return act


def xo_report():
    """per-game report (JSON-able): divergence, breakages, repairs, cuts, cash / animals by day, handoff."""
    X = _XO
    rep = dict(
        cfg={k: v for k, v in XO_CFG.items() if k != "log_max"},
        plans=X.get("plans"), D=X.get("D"), D_reason=X.get("D_reason"), D_shadow=X.get("D_shadow"),
        dyn_trace={str(d): v for d, v in (X.get("dyn_trace") or {}).items()}, abort=X.get("abort"),
        first_div=X.get("first_div"), first_div_exact=X.get("first_div_exact"), first_hidden=X.get("first_hidden"),
        counts=dict(X.get("count", {})), by_day={str(d): dict(c) for d, c in (X.get("by_day") or {}).items()},
        cuts=X.get("cuts"), deferred_by_day={str(d): round(v, 1) for d, v in (X.get("deferred_by_day") or {}).items()},
        cash_by_day={str(d): v for d, v in (X.get("cash_by_day") or {}).items()},
        plan_cash_by_day={str(d): v for d, v in (X.get("plan_cash_by_day") or {}).items()},
        placed_by_day={str(d): v for d, v in (X.get("placed_by_day") or {}).items()},
        ham_by_day={str(d): v for d, v in (X.get("ham_by_day") or {}).items()},
        hidden_by_day={str(d): v for d, v in (X.get("hidden_by_day") or {}).items()},
        revenue_by_day={str(d): round(v, 1) for d, v in (X.get("revenue") or {}).items()},
        owned=sorted(X.get("owned") or ()), jobs_open=len(X.get("jobs") or {}),
        pending_at_handoff=X.get("pending_at_handoff"), lag_max=X.get("lag_max_seen"),
        spawn_offsets=X.get("spawn_offsets"), fills_ambiguous=X.get("fills_amb"),
        money_resid_max=round(X.get("money_resid_max", 0.0), 1), tmax=round(X.get("tmax", 0.0), 4),
        tsum=round(X.get("tsum", 0.0), 3), events=(X.get("events") or [])[:XO_CFG["log_max"]],
    )
    _XO_REPORT.clear()
    _XO_REPORT.update(rep)
    return rep
# ===== END XOPEN FOLLOWER CORE ====================================================================================

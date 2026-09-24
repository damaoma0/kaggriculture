"""mgt_lead_deploy: mgt_lead's executor playing worlds it has never seen, choosing its own targets.

Research agent (2026-09-24). The EXECUTOR SECTION below is a verbatim copy of agents/mgt_lead.py (owned by the
E1 thread; copied from git HEAD, sha256 30857000a5d69e3b); re-sync by copying that file between the two marker lines. Only the
DEPLOY section after it is new: it builds the Target the executor follows (retrieval of leader games at days
0/3/6/9, count-model composition from day 12, sell-everything rule, hands from the day's work) and holds the
entry point, which is the LAST callable in the file (Kaggle's loader and scripts/ladder_panel.py call that one).
"""
# ============================================================================================
# ===== BEGIN EXECUTOR SECTION (verbatim agents/mgt_lead.py) ==================================
# ============================================================================================
"""mgt_lead: follow a leader's per-day BOARD plan with our own closed-loop execution.

Research agent (2026-09-24). Not a replay of the leader's actions: every step reads the live
observation, derives the jobs still needed on each tile (structural diff toward the target's
boards + maintenance of our own live assets + harvests), and dispatches farmer/hands greedily
(nearest task, with shed pickups for wheat / fertilizer / animals). Market: sell following the
target's cumulative per-day sold units (capped by our stock), buy what today's jobs need when
cash allows (re-tried every hour), hire the target's day hand count.

Target: set with configure(semantics_dict) (a data/leader_semantics/<team>/<ep>.json.gz object).
NOTE (data quirk): in those files market.*, animals.bought and labour.hires_arrived of index d
belong to actual day d+1 (index 0 = days 0 and 1); boards, plantings, maintenance and
hands_present are correctly dated.
"""
import time
from collections import Counter

CROPS = {
    "WHEAT":      {"seed": 10, "first": 2, "maxday": 4, "interval": 0, "max": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first": 2, "maxday": 3, "interval": 0, "max": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first": 8, "maxday": 8, "interval": 1, "max": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "maxday": 10, "interval": 2, "max": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first": 10, "maxday": 12, "interval": 0, "max": 6, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
LABEL_CROP = {"WH": "WHEAT", "CA": "CARROT", "TO": "TOMATO", "ST": "STRAWBERRY", "ME": "MELON"}
CROP_LABEL = {v: k for k, v in LABEL_CROP.items()}
LATE = {"WHEAT": 1, "CARROT": 1, "MELON": 2, "TOMATO": 3, "STRAWBERRY": 3}
MOVES = {(0, -1): "NORTH", (0, 1): "SOUTH", (1, 0): "EAST", (-1, 0): "WEST"}

CFG = {
    "smart_water": True,     # engine-derived skips: water only when survival / yield needs it
    "hire_mode": "target",   # "target" = the target's hands that day
    "hire_extra": 0,
    "sell_mode": "cum",      # cumulative target sold units per product
    "zone_penalty": 0,
    "prio_mode": "new",
    "late_hour": 15,
    "sticky": False,
    "fert_ongoing": True,
    "deliver_value": 300,
    "window_urgent": ["MELON", "WHEAT", "CARROT"],
    "wheat_days": 1,
    "late": {"STRAWBERRY": 6, "TOMATO": 5, "MELON": 3},  # catch-up days for missed plantings
    "keep_bonus": 1.5,
}

def _curve():
    order = []
    for qx, qy, rows in ((0, 0, range(4, -1, -1)), (5, 0, range(0, 5)), (5, 5, range(5, 10)), (0, 5, range(9, 4, -1))):
        for k, y in enumerate(rows):
            xs = range(qx, qx + 5) if k % 2 == 0 else range(qx + 4, qx - 1, -1)
            if qx == 0 and qy == 0:
                xs = range(4, -1, -1) if k % 2 == 0 else range(0, 5)
            for x in xs:
                order.append(y * 10 + x)
    return order


CURVE = _curve()
CURVE_POS = {idx: i for i, idx in enumerate(CURVE)}

_T = None      # Target
_S = None      # per-game state


def _quad(x, y):
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


class Target:
    def __init__(self, sem):
        days = sem["days"]
        self.n = len(days)
        self.board = [d["board"] for d in days]
        self.plant = []          # day -> {tile: crop}
        self.fert = []           # day -> set(tile)
        self.hands = [int(d["labour"].get("hands_present", 0)) for d in days]
        self.cash = [d.get("cash_start") for d in days]
        self.final = sem["meta"]["rewards"][sem["meta"]["seat"]]
        struct_kind = {}
        self.struct_by_day = []  # day -> {tile: kind} desired structures at END of day d
        for d, day in enumerate(days):
            self.plant.append({t: c for c, ts in day["planted"].items() for t in ts})
            self.fert.append(set(day["maintenance"].get("FERTILIZE", [])))
            for op, ts in day["built"].items():
                for t in ts:
                    struct_kind[t] = "COOP" if op == "BUILD_COOP" else "PASTURE"
            for t in day["dug"]:
                # a dug structure disappears
                if t in struct_kind and (d + 1 >= self.n or self.board[d + 1][t] not in ("co", "pa", "sh", "go")):
                    struct_kind.pop(t, None)
            self.struct_by_day.append(dict(struct_kind))
        # desired animals at end of day d: from board d+1 (last day: board of day 29)
        self.animals_by_day = []
        for d in range(self.n):
            b = self.board[d + 1] if d + 1 < self.n else self.board[d]
            want = {}
            for t, kind in self.struct_by_day[d].items():
                lab = b[t]
                if kind == "COOP" and lab == "go":
                    want[t] = "GOOSE"
                elif kind == "PASTURE" and lab == "sh":
                    want[t] = "SHEEP"
                elif kind == "PASTURE" and lab == "co":
                    want[t] = "COW"
            self.animals_by_day.append(want)
        # quadrant unlock day
        self.land_day = {}
        for q in LAND_ORDER:
            for d in range(self.n):
                b = self.board[d + 1] if d + 1 < self.n else self.board[d]
                if any(b[y * 10 + x] != " L" for y in range(10) for x in range(10) if _quad(x, y) == q):
                    self.land_day[q] = d
                    break
        # actual-day sold units (fix the one-day shift of the semantics' market block)
        sold = [Counter() for _ in range(self.n)]
        for i, day in enumerate(days):
            actual = 1 if i == 0 else i + 1
            if actual < self.n:
                sold[actual].update(day["market"]["sold_units"])
        self.cum_sold = []
        run = Counter()
        for d in range(self.n):
            run = run + sold[d]
            self.cum_sold.append(Counter(run))
        # plant events list (pd, tile, crop)
        self.events = [(d, t, c) for d in range(self.n) for t, c in self.plant[d].items()]


def configure(sem, **cfg):
    global _T, _S
    _T = Target(sem)
    _S = None
    CFG.update(cfg)


def _new_state():
    return {
        "pmap": {},        # (pd, T) -> our tile for a plant event
        "done": set(),     # fulfilled plant events (pd, T)
        "smap": {},        # target structure tile -> our tile
        "assign": {},      # unit -> tile idx
        "sold": Counter(),  # our cumulative sold units (issued)
        "day": -1,
        "log": Counter(),
        "tmax": 0.0,
    }


# --------------------------------------------------------------------------- helpers

def _g(o, k, default=None):
    try:
        v = o[k]
        return default if v is None else v
    except (KeyError, TypeError, IndexError):
        return getattr(o, k, default)


def _tile(tiles, idx):
    return tiles[idx // 10][idx % 10]


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _near_shed(p):
    return min(SHED, key=lambda q: (_dist(p, q), q))


def _step_toward(p, q):
    dx, dy = q[0] - p[0], q[1] - p[1]
    if dx:
        return [MOVES[(1 if dx > 0 else -1, 0)]]
    if dy:
        return [MOVES[(0, 1 if dy > 0 else -1)]]
    return ["PASS"]


def _is_plant(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT"


def _is_weed(t):
    return isinstance(t, dict) and t.get("kind") == "WEED"


def _animal(t):
    return t.get("animal") if isinstance(t, dict) else None


def _ongoing_last_age(crop):
    c = CROPS[crop]
    return c["first"] + c["interval"] * (c["max"] - 1)


def _plant_state(t, day):
    """returns (age, harvestable_now, finished)"""
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if c["ongoing"]:
        last = _ongoing_last_age(t["crop"])
        finished = (age >= last and t.get("yield_units", 0) <= 0) or age > last + 1
        return age, t.get("yield_units", 0) > 0 and age >= c["first"], finished
    return age, age >= c["first"], False


def _onetime_should_harvest(t, day):
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if age < c["first"]:
        return False
    if age >= c["maxday"]:
        return True
    y = t.get("yield_units", 0)
    if y >= c["max"]:
        return True
    # remaining possible gain
    fert = t.get("fertilized_until_day", -1) >= day
    return False if fert else (y >= _unfert_max(t["crop"]))


def _unfert_max(crop):
    c = CROPS[crop]
    ws = (c["maxday"] + 1) // 2
    return min(c["max"], 1 + (c["maxday"] - ws + 1))


def _water_needed(t, day, last_day):
    """(needed, urgent)"""
    if t.get("watered_today"):
        return False, False
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if day >= last_day:
        # final day: only yield-adding water on one-time crops matters
        if not c["ongoing"]:
            ws = (c["maxday"] + 1) // 2
            return ws <= age <= c["maxday"], False
        return False, False
    if t.get("consecutive_unwatered", 0) >= 1:
        return True, True
    if not CFG["smart_water"]:
        return True, False
    if not c["ongoing"]:
        ws = (c["maxday"] + 1) // 2
        return ws <= age <= c["maxday"], False
    # ongoing: water on a fertilized production day
    fert = t.get("fertilized_until_day", -1) >= day
    if fert:
        k = (day + 1) - t["planted_day"] - c["first"]
        if k >= 0 and k % c["interval"] == 0 and k // c["interval"] + 1 <= c["max"]:
            return True, False
    return False, False


# --------------------------------------------------------------------------- planning

def _free_tile(tiles, near, reserved):
    best = None
    for idx in range(100):
        if idx in reserved:
            continue
        t = _tile(tiles, idx)
        if t == "LOCKED":
            continue
        if t is None or _is_weed(t):
            key = (_dist((idx % 10, idx // 10), near) + (1 if t is not None else 0), idx)
            if best is None or key < best[0]:
                best = (key, idx)
    return None if best is None else best[1]


def _plan(obs, S, tiles, day):
    """Structural jobs for today: {our_idx: job} where job = ('PLANT', crop, event) |
    ('BUILD', kind) | ('PLACE', species) (a BUILD may carry a place species)."""
    T = _T
    jobs = {}
    last = T.n - 1
    d = min(day, last)
    # reserve target tiles used for structural work in the next days (keep the layout free)
    reserved = set()
    for dd in range(d, min(last, d + 2) + 1):
        for t in T.plant[dd]:
            reserved.add(t)
    for t in T.struct_by_day[d]:
        reserved.add(S["smap"].get(t, t))
    # structures + animals
    want_struct = T.struct_by_day[d]
    want_animal = T.animals_by_day[d]
    for tt, kind in want_struct.items():
        m = S["smap"].get(tt, tt)
        cur = _tile(tiles, m)
        if cur == "LOCKED":
            continue
        if isinstance(cur, dict) and cur.get("kind") == kind:
            sp = want_animal.get(tt)
            if sp and not _animal(cur):
                jobs[m] = ("PLACE", sp)
            continue
        ok = cur is None or _is_weed(cur)
        if not ok and _is_plant(cur):
            age, harv, fin = _plant_state(cur, day)
            ok = fin or (not CROPS[cur["crop"]]["ongoing"] and harv)
        if not ok:
            m2 = _free_tile(tiles, (tt % 10, tt // 10), reserved | set(jobs))
            if m2 is None:
                continue
            S["smap"][tt] = m2
            m = m2
            reserved.add(m2)
        jobs[m] = ("BUILD", kind, want_animal.get(tt))
    # plantings (today's events + recent catch-up)
    for (pd, tt, crop) in T.events:
        if pd > d or d - pd > CFG["late"].get(crop, LATE[crop]):
            continue
        key = (pd, tt)
        if key in S["done"]:
            continue
        if pd < d and T.board[d][tt] != CROP_LABEL[crop]:
            continue  # the target's own cohort is gone; no catch-up
        m = S["pmap"].get(key, tt)
        cur = _tile(tiles, m)
        if _is_plant(cur) and cur["crop"] == crop and cur["planted_day"] >= pd:
            S["done"].add(key)
            continue
        if m in jobs:
            m = None
        if m is not None:
            if cur == "LOCKED":
                m = None
            elif cur is None or _is_weed(cur):
                pass
            elif _is_plant(cur):
                age, harv, fin = _plant_state(cur, day)
                c = CROPS[cur["crop"]]
                if not (fin or (not c["ongoing"] and harv and age >= c["maxday"] - 1)):
                    m = None
            else:
                m = None
        if m is None:
            if cur == "LOCKED" and _T.land_day.get(_quad(tt % 10, tt // 10), 99) <= day:
                continue  # land coming (we buy it today); wait rather than remap
            m2 = _free_tile(tiles, (tt % 10, tt // 10), reserved | set(jobs))
            if m2 is None:
                continue
            S["pmap"][key] = m2
            m = m2
        jobs[m] = ("PLANT", crop, key)
    # fertilize targets (mapped)
    fert = set()
    for tt in T.fert[d]:
        m = tt
        for (pd, t2), mm in S["pmap"].items():
            if t2 == tt:
                m = mm
        fert.add(m)
    return jobs, fert


def _tile_ops(idx, t, job, fert, day, last_day, seeds):
    """ordered ops for our tile now; also the items the sequence needs and a priority."""
    ops, need, prio = [], Counter(), 3
    if job is not None:
        kind = job[0]
        if kind == "PLANT":
            crop = job[1]
            if seeds.get(crop, 0) <= 0:
                pass  # wait for seeds; still do maintenance below
            elif t is None:
                ops += [["PLANT", crop], ["WATER"]]
                prio = 0
            elif _is_weed(t):
                ops += [["DIG"], ["PLANT", crop], ["WATER"]]
                prio = 0
            elif _is_plant(t):
                age, harv, fin = _plant_state(t, day)
                c = CROPS[t["crop"]]
                if fin:
                    ops += [["DIG"], ["PLANT", crop], ["WATER"]]
                    prio = 0
                elif not c["ongoing"] and harv:
                    ws = (c["maxday"] + 1) // 2
                    if not t.get("watered_today") and ws <= age <= c["maxday"]:
                        ops += [["WATER"]]
                    ops += [["HARVEST"], ["PLANT", crop], ["WATER"]]
                    prio = 0
            if ops:
                return ops, need, prio
        elif kind == "BUILD":
            k, sp = job[1], job[2]
            if t is None:
                ops += [["BUILD_" + k]]
            elif _is_weed(t) or _is_plant(t):
                if _is_plant(t):
                    c = CROPS[t["crop"]]
                    if not c["ongoing"] and _plant_state(t, day)[1]:
                        ops += [["HARVEST"]]
                    else:
                        ops += [["DIG"]]
                else:
                    ops += [["DIG"]]
                ops += [["BUILD_" + k]]
            if sp:
                ops += [["PLACE", sp], ["FEED"], ["CARE"]]
                need[sp] += 1
                need["WHEAT"] += 1
            return ops, need, 0
        elif kind == "PLACE":
            sp = job[1]
            if isinstance(t, dict) and not _animal(t):
                ops += [["PLACE", sp], ["FEED"], ["CARE"]]
                need[sp] += 1
                need["WHEAT"] += 1
                return ops, need, 0
    if _is_plant(t):
        c = CROPS[t["crop"]]
        age = day - t["planted_day"]
        own_fert = False
        if CFG["fert_ongoing"] and c["ongoing"] and day < last_day - 1:
            # a production falls within the 3 fertilized days and the plant is not finished
            last = _ongoing_last_age(t["crop"])
            for k in range(3):
                a = age + k + 1  # production visible at age a happens at the end of day+k
                if c["first"] <= a <= last and (a - c["first"]) % c["interval"] == 0:
                    own_fert = True
                    break
        if (idx in fert or own_fert) and t.get("fertilized_until_day", -1) < day and day < last_day:
            ops.append(["FERTILIZE"])
            need["FERTILIZER"] += 1
            prio = min(prio, 2)
        wn, urgent = _water_needed(t, day, last_day)
        if wn:
            ops.append(["WATER"])
            # a window water on a one-time crop adds a unit (melon ~ $200): treat as urgent
            valuable = (not c["ongoing"]) and CFG["window_urgent"] and t["crop"] in CFG["window_urgent"]
            prio = min(prio, 1 if (urgent or valuable) else 2)
        if c["ongoing"]:
            if t.get("yield_units", 0) > 0 and age >= c["first"]:
                ops.append(["HARVEST"])
                prio = min(prio, 1)
        else:
            if age >= c["first"]:
                # harvest after today's water when nothing more can be gained
                y = t.get("yield_units", 0)
                ws = (c["maxday"] + 1) // 2
                will_water = wn and ws <= age <= c["maxday"]
                bonus = (2 if t.get("fertilized_until_day", -1) >= day else 1) if will_water else 0
                tt = dict(t)
                tt["yield_units"] = min(c["max"], y + bonus)
                if _onetime_should_harvest(tt, day) or (day >= last_day):
                    ops.append(["HARVEST"])
                    prio = min(prio, 1)
    elif _animal(t):
        if day < last_day:
            if not t.get("fed_today"):
                ops.append(["FEED"])
                need["WHEAT"] += 1
                prio = min(prio, 1 if t.get("consecutive_unfed", 0) >= 1 else 2)
            if not t.get("cared_today"):
                ops.append(["CARE"])
                prio = min(prio, 2)
        if t.get("fertilizer_available"):
            ops.append(["COLLECT_FERTILIZER"])
            prio = min(prio, 2)
        if t.get("yield_units", 0) > 0:
            ops.append(["HARVEST"])
            prio = min(prio, 1)
    return ops, need, prio


# --------------------------------------------------------------------------- the agent

def agent(obs, config=None):
    global _S
    t0 = time.time()
    step = int(_g(obs, "step", 0))
    if _S is None or step == 0 or step < _S.get("last_step", -1):
        _S = _new_state()
    S = _S
    S["last_step"] = step
    me = int(_g(obs, "player", 0))
    farm = _g(obs, "farms")[me]
    private = _g(obs, "private", {})
    day, hour = divmod(step, 24)
    last_day = 29
    tiles = farm["tiles"]
    money = float(farm["money"])
    shed = Counter({k: int(v) for k, v in dict(_g(private, "shed", {})).items() if v})
    seeds = Counter({k: int(v) for k, v in dict(_g(private, "seeds", {})).items() if v})
    invs = [Counter({k: int(v) for k, v in dict(i).items() if v}) for i in _g(private, "inventories", [])]
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
    while len(invs) < len(pos):
        invs.append(Counter())
    prices = dict(_g(_g(obs, "market", {}), "prices", {}))
    if _T is None:
        return {"farmer": ["PASS"], "hands": [["PASS"]] * (len(pos) - 1), "market": []}
    if S["day"] != day:
        S["day"] = day
        S["assign"] = {}
    unlocked = list(farm.get("unlocked_quadrants", ["NW"]))

    jobs, fert = _plan(obs, S, tiles, day)

    # ---- tile tasks
    tasks = {}
    for idx in range(100):
        t = _tile(tiles, idx)
        if t == "LOCKED":
            continue
        ops, need, prio = _tile_ops(idx, t, jobs.get(idx), fert, day, last_day, seeds)
        if ops:
            tasks[idx] = (ops, need, prio)

    carried = Counter()
    for inv in invs:
        carried.update(inv)
    demand = Counter()
    for ops, need, prio in tasks.values():
        demand.update(need)

    # ---- dispatch
    n = len(pos)
    actions = [["PASS"] for _ in range(n)]
    prev = S["assign"]
    for u in list(prev):
        if u >= n or (prev[u] != "D" and prev[u] not in tasks):
            prev.pop(u, None)
    if CFG["sticky"]:
        assign = prev
    else:
        # fresh matching every step; deliveries stay sticky, current tasks get a small bonus
        assign = {u: v for u, v in prev.items() if v == "D"}
        S["assign"] = assign
    taken = set(v for v in assign.values() if v != "D")
    shed_left = Counter(shed)
    seeds_left = Counter(seeds)
    d_ = min(day, _T.n - 1)
    quota_open = {p for p in PRODUCTS if p != "WHEAT"
                  and _T.cum_sold[d_].get(p, 0) - S["sold"][p] - shed.get(p, 0) > 0}
    fert_short = demand.get("FERTILIZER", 0) > shed.get("FERTILIZER", 0)

    def deliverable(inv):
        return {k: v for k, v in inv.items() if v > 0 and k in PRODUCTS and k != "WHEAT"
                and not (k == "FERTILIZER" and fert_short)}

    def usable_ops(u, ops, need):
        """ops this unit can run at the tile now (items carried or obtainable at the shed)."""
        inv = invs[u]
        lack = {k for k, v in need.items() if inv.get(k, 0) < v and shed_left.get(k, 0) <= 0}
        if not lack:
            return ops
        out = []
        placing_blocked = False
        for op in ops:
            c = op[0]
            if c == "PLACE" and op[1] in lack:
                placing_blocked = True
                continue
            if placing_blocked and c in ("FEED", "CARE"):
                continue
            if c in ("FEED", "CARE") and "WHEAT" in lack:
                continue
            if c == "FERTILIZE" and "FERTILIZER" in lack:
                continue
            out.append(op)
        return out

    def cost(u, idx):
        ops, need, prio = tasks[idx]
        p = pos[u]
        tgt = (idx % 10, idx // 10)
        ok = usable_ops(u, ops, need)
        if not ok:
            return None
        miss = [k for k, v in need.items() if invs[u].get(k, 0) < v and shed_left.get(k, 0) > 0]
        if miss:
            s = _near_shed(p)
            c = _dist(p, s) + len(miss) + _dist(s, tgt)
        else:
            c = _dist(p, tgt)
        # a plant pipeline must be finished (watered) today
        if any(o[0] == "PLANT" for o in ok) and hour + c + len(ok) > 24:
            return None
        if len(ok) < len(ops):
            c += 2
        if CFG["prio_mode"] == "old":
            return c + prio * (6 if hour >= 14 else 3)
        # urgency only matters when the day runs short: plant/place pipelines and
        # death-preventing work first late in the day
        if hour >= CFG["late_hour"] and prio >= 2:
            c += 10
        return c

    # zones: contiguous chunks of the curve with balanced work, recomputed when the crew changes
    zkey = (day, n)
    if S.get("zkey") != zkey:
        S["zkey"] = zkey
        w = [0.0] * 100
        for idx, (ops, need, prio) in tasks.items():
            w[CURVE_POS[idx]] = len(ops) + 1.5
        tot = sum(w) or 1.0
        zone = {}
        acc = 0.0
        for i, idx in enumerate(CURVE):
            u = min(n - 1, int(acc / tot * n)) if n > 1 else 0
            zone[idx] = u
            acc += w[i]
        S["zone"] = zone
    zone = S["zone"]
    zneed = [Counter() for _ in range(n)]
    for idx, (ops, need, prio) in tasks.items():
        zu = zone.get(idx, 0)
        if zu < n:
            zneed[zu].update(need)

    def cost2(u, idx):
        c = cost(u, idx)
        if c is None:
            return None
        if not CFG["sticky"] and prev.get(u) == idx:
            c -= CFG["keep_bonus"]
        if not CFG["zone_penalty"]:
            return c
        return c + (0 if zone.get(idx, 0) == u else CFG["zone_penalty"])

    # delivery for same-day sale when cash binds (or a unit carries a lot)
    for u in range(n):
        if u in assign:
            continue
        dv = deliverable(invs[u])
        val = sum(prices.get(k, 0) * v for k, v in dv.items() if k in quota_open)
        if dv and hour < 22 and (sum(dv.values()) >= 10 or val >= CFG["deliver_value"]
                                 or (S.get("short") and val > 0)):
            assign[u] = "D"
    free = [u for u in range(n) if u not in assign]
    while free:
        best = None
        for u in free:
            for idx in tasks:
                if idx in taken:
                    continue
                c = cost2(u, idx)
                if c is None:
                    continue
                if best is None or c < best[0]:
                    best = (c, u, idx)
        if best is None:
            break
        _, u, idx = best
        assign[u] = idx
        taken.add(idx)
        free.remove(u)

    plant_count = Counter()
    endgame = day >= last_day
    for u in range(n):
        p = pos[u]
        inv = invs[u]
        # final day delivery
        if endgame:
            sellable = sum(v for k, v in inv.items() if k in PRODUCTS)
            s = _near_shed(p)
            if sellable and (22 - hour) <= _dist(p, s) + 1:
                actions[u] = ["DROP"] if p == s else _step_toward(p, s)
                assign.pop(u, None)
                continue
        idx = assign.get(u)
        if p in SHED and idx != "D" and hour < 22:
            want = zneed[u] if CFG["zone_penalty"] else Counter(
                {k: min(3, max(0, demand[k] - carried[k])) for k in ("WHEAT", "FERTILIZER")})
            got = None
            for k in ("WHEAT", "FERTILIZER"):
                gap = min(want.get(k, 0) - inv.get(k, 0), max(0, demand[k] - carried[k]), shed_left.get(k, 0))
                if gap > 0:
                    got = (k, gap)
                    break
            if got:
                shed_left[got[0]] -= got[1]
                carried[got[0]] += got[1]
                actions[u] = ["PICKUP", got[0], int(got[1])]
                continue
        if idx is None or idx == "D":
            dv = deliverable(inv)
            if dv and hour < 23:
                s = _near_shed(p)
                if p != s:
                    actions[u] = _step_toward(p, s)
                else:
                    if all(k in dv for k in inv):
                        actions[u] = ["DROP"]
                    else:
                        k = sorted(dv)[0]
                        actions[u] = ["PLACE", k, int(inv[k])]
                    if len(dv) <= 1:
                        assign.pop(u, None)
            else:
                assign.pop(u, None)
            continue
        ops, need, prio = tasks[idx]
        tgt = (idx % 10, idx // 10)
        miss = [k for k, v in need.items() if inv.get(k, 0) < v and shed_left.get(k, 0) > 0]
        if miss:
            s = _near_shed(p)
            if p != s:
                actions[u] = _step_toward(p, s)
                continue
            k = miss[0]
            cover = max(0, demand[k] - carried[k])
            amt = min(shed_left[k], max(need[k] - inv.get(k, 0), min(cover, zneed[u][k] - inv.get(k, 0))))
            amt = max(1, amt)
            shed_left[k] -= amt
            carried[k] += amt
            actions[u] = ["PICKUP", k, int(amt)]
            continue
        if p != tgt:
            actions[u] = _step_toward(p, tgt)
            continue
        # at tile: first executable op
        act = None
        t = _tile(tiles, idx)
        for op in usable_ops(u, ops, need):
            c = op[0]
            if c == "FEED" and inv.get("WHEAT", 0) <= 0:
                continue
            if c == "CARE" and isinstance(t, dict) and not t.get("fed_today") and any(o[0] == "FEED" for o in ops):
                continue
            if c == "FERTILIZE" and inv.get("FERTILIZER", 0) <= 0:
                continue
            if c == "PLACE" and inv.get(op[1], 0) <= 0:
                break
            if c == "PLANT":
                if seeds_left.get(op[1], 0) <= 0 or hour >= 23:
                    break
                seeds_left[op[1]] -= 1
                plant_count[op[1]] += 1
            act = op
            break
        if act is None:
            assign.pop(u, None)
            actions[u] = ["PASS"]
        else:
            actions[u] = list(act)

    # ---- diagnostics
    if hour == 23 and day < last_day:
        lg = S["log"]
        for idx, (ops, need, prio) in tasks.items():
            t = _tile(tiles, idx)
            if _is_plant(t) and not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                lg["die_%s_%s" % (t["crop"], "assigned" if idx in taken else "unassigned")] += 1
            if _animal(t) and not t.get("fed_today"):
                lg["unfed_%s" % ("assigned" if idx in taken else "unassigned")] += 1
    lg = S["log"]
    for u in range(n):
        if actions[u] == ["PASS"]:
            lg["pass_h%02d" % (hour // 6 * 6)] += 1

    # ---- market
    orders = _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
                     unlocked, farm, pos, last_day)
    dt = time.time() - t0
    S["tmax"] = max(S["tmax"], dt)
    return {"farmer": actions[0], "hands": actions[1:], "market": orders}


def _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
            unlocked, farm, pos, last_day):
    T = _T
    d = min(day, T.n - 1)
    sells, hires, buys = [], [], []
    endgame = day >= last_day
    # reserves: wheat for today's remaining feeding, fertilizer for pending fertilize
    reserve = Counter()
    n_anim = sum(1 for r in farm["tiles"] for t in r if _animal(t))
    reserve["WHEAT"] = max(0, demand.get("WHEAT", 0) - carried.get("WHEAT", 0)
                           + (n_anim * CFG["wheat_days"] if day < last_day - 1 else 0))
    n_plants = sum(1 for r in farm["tiles"] for t in r if _is_plant(t))
    tomorrow = min(len(T.fert[d + 1]) if d + 1 < T.n else 0, n_plants)
    if CFG["fert_ongoing"]:
        n_on = sum(1 for r in farm["tiles"] for t in r if _is_plant(t) and CROPS[t["crop"]]["ongoing"])
        tomorrow = max(tomorrow, n_on // 2)
    reserve["FERTILIZER"] = max(0, demand.get("FERTILIZER", 0) + tomorrow - carried.get("FERTILIZER", 0))
    if endgame:
        reserve = Counter()
    # sell following the target's cumulative sold units
    for p in PRODUCTS:
        have = shed.get(p, 0) - reserve.get(p, 0)
        if have <= 0:
            continue
        if endgame:
            n = have
        else:
            quota = T.cum_sold[d].get(p, 0) - S["sold"][p]
            n = min(have, quota)
        if n > 0:
            sells.append(["SELL", p, int(n)])
    # shed overflow guard: midnight drop discards above 100
    total = sum(shed.values()) + sum(sum(i.values()) for i in invs)
    sold_now = sum(o[2] for o in sells)
    if not endgame and hour >= 20 and total - sold_now > 95:
        extra = total - sold_now - 90
        for p in sorted(PRODUCTS, key=lambda q: -(shed.get(q, 0))):
            if extra <= 0:
                break
            already = sum(o[2] for o in sells if o[1] == p)
            can = shed.get(p, 0) - reserve.get(p, 0) - already
            k = min(can, extra)
            if k > 0:
                sells.append(["SELL", p, int(k)])
                extra -= k
    # value estimate of sells (for budgeting this step)
    cash = money + sum(prices.get(o[1], 0) * o[2] * 0.85 for o in sells)
    # wheat for feed first (animals are the largest investment)
    wheat_buy = []
    short = False
    if not endgame:
        k = demand.get("WHEAT", 0) - carried.get("WHEAT", 0) - shed.get("WHEAT", 0)
        pw = max(1, prices.get("WHEAT", 25))
        short |= k > int(cash // (pw + 2))
        k = min(k, int(cash // (pw + 2)))
        if k > 0:
            wheat_buy.append(["BUY_PRODUCT", "WHEAT", int(k)])
            cash -= k * (pw + 1)
    # hires
    if not endgame and hour <= 12:
        want = T.hands[d] + CFG["hire_extra"]
        have = len(pos) - 1
        k = max(0, want - have)
        hires_today = int(farm.get("hires_today", 0))
        for i in range(k):
            c = _fib(hires_today + i)
            if cash - c < 0:
                break
            cash -= c
            hires.append(["HIRE"])
    # land
    nq = len(unlocked) - 1
    if nq < 3:
        q = LAND_ORDER[nq]
        if T.land_day.get(q, 99) <= day:
            if cash >= LAND_PRICES[nq]:
                buys.append(["BUY_LAND"])
                cash -= LAND_PRICES[nq]
            else:
                short = True
    # animals for place jobs
    need_an = Counter()
    for ops, need, prio in tasks.values():
        for k, v in need.items():
            if k in ANIMALS:
                need_an[k] += v
    # also place jobs whose structure is not yet ready (tasks exist anyway via BUILD)
    for sp, v in need_an.items():
        k = v - shed.get(sp, 0) - carried.get(sp, 0)
        short |= k > int(cash // ANIMALS[sp]["cost"])
        k = min(k, int(cash // ANIMALS[sp]["cost"]))
        if k > 0:
            buys.append(["BUY_ANIMAL", sp, int(k)])
            cash -= k * ANIMALS[sp]["cost"]
    # seeds
    need_seed = Counter()
    for idx, job in jobs.items():
        if job[0] == "PLANT":
            need_seed[job[1]] += 1
    for crop, v in need_seed.items():
        k = v - seeds.get(crop, 0)
        short |= k > int(cash // CROPS[crop]["seed"])
        k = min(k, int(cash // CROPS[crop]["seed"]))
        if k > 0:
            buys.append(["BUY_SEED", crop, int(k)])
            cash -= k * CROPS[crop]["seed"]
    # assemble within the 10-order cap: sells first (cash), then hires, then buys
    buys = wheat_buy + buys
    orders = []
    for o in sells:
        if len(orders) >= 4 and hour == 0:
            break
        orders.append(o)
    room = 10 - len(orders) - min(len(buys), 3)
    orders += hires[:max(0, room)]
    for o in buys + sells[len([x for x in orders if x[0] == "SELL"]):]:
        if len(orders) >= 10:
            break
        orders.append(o)
    for o in orders:
        if o[0] == "SELL":
            S["sold"][o[1]] += o[2]
    S["short"] = short
    return orders


# ============================================================================================
# ===== END EXECUTOR SECTION ==================================================================
# ============================================================================================
# ===== DEPLOY TARGET CONSTRUCTION (mgt_lead_deploy only) ======================================
# Everything below builds and updates the Target (_T) that the executor above follows, in a world
# the corpus has never seen:
#   day 0      family A's opening (DSM 112655730, the family's exemplar game)
#   days 3/6/9 re-select a leader game with leader_plan_retrieval.retrieve (lam=1.0; k=1 at day 3,
#              k=5 -> the neighbours' medoid at days 6/9); the switch keeps our live assets (structures
#              of the new plan are mapped onto ours of the same kind, plantings remap to free tiles)
#   day 12+    composition targets from the leader count model (ridge, data/leader_semantics/count_model.json):
#              crop deficits -> planting events on free tiles (preferring the last retrieved game's tiles),
#              animal deficits -> structures/animals; animals stop being fed when their remaining output
#              cannot pay for the wheat (hook on _tile_ops, the executor code itself is unchanged)
#   selling    every product as soon as it is in the shed (the leaders hold ~4 units of wool/milk/eggs and
#              sell each harvest within a day), except wheat: keep what the herd eats until the end
#   hands      days 0-11: the followed game's hands; day 12+: corpus regression on our crop/animal counts
# ============================================================================================
import os as _dep_os
import sys as _dep_sys
import gzip as _dep_gzip
import json as _dep_json
import glob as _dep_glob

DEP_CFG = {
    "k_day3": 1, "k_late": 5, "lam": 1.0,
    "compose_from": 12,
    "h_short": 1, "h_long": 3,          # count-model horizon: WH/CA vs ST/TO/ME and animals
    "last_plant": {"STRAWBERRY": 18, "TOMATO": 20, "MELON": 17, "WHEAT": 26, "CARROT": 26},
    "last_animal": {"SHEEP": 17, "COW": 18, "GOOSE": 20},
    "hands_coef": (6.186, 0.040, 0.123),  # hands ~ b0 + b1*crop tiles + b2*animal tiles (corpus days 12-28)
    "nofeed_from": 15,
    "wheat_margin": 10,
    "max_new_per_crop": 12,
}


def _dep_find_root():
    cands = [_dep_os.getcwd()]
    for p in list(_dep_sys.path):
        if isinstance(p, str) and p:
            cands += [p, _dep_os.path.dirname(p)]
    for c in cands:
        try:
            if _dep_os.path.isfile(_dep_os.path.join(c, "data", "leader_semantics", "count_model.json")):
                return c
        except Exception:
            pass
    return _dep_os.getcwd()


_DEP_ROOT = _dep_find_root()
_DEP_SEM_DIR = _dep_os.path.join(_DEP_ROOT, "data", "leader_semantics")
if _dep_os.path.join(_DEP_ROOT, "scripts") not in _dep_sys.path:
    _dep_sys.path.insert(0, _dep_os.path.join(_DEP_ROOT, "scripts"))
import leader_plan_retrieval as _dep_lpr  # noqa: E402  (stdlib-only module)
_dep_lpr.load_corpus()               # parse the 240-game index once, at import

with open(_dep_os.path.join(_DEP_SEM_DIR, "count_model.json")) as _dep_fh:
    _DEP_CM = _dep_json.load(_dep_fh)
_DEP_LABELS = tuple(_DEP_CM["meta"]["labels"])
_DEP_DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
               'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
               'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
               'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
               'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
_DEP_CM_PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
_DEP_EXEMPLAR = 112655730           # family A exemplar (openings.json), DSM
_DEP_SEM_CACHE = {}
_DEP_ANIMAL_LABEL = {"SHEEP": "sh", "COW": "co", "GOOSE": "go"}


def _dep_sem_path(ep):
    hits = _dep_glob.glob(_dep_os.path.join(_DEP_SEM_DIR, "*", "%s.json.gz" % ep))
    return hits[0] if hits else None


def _dep_load_sem(ep):
    ep = int(ep)
    if ep not in _DEP_SEM_CACHE:
        with _dep_gzip.open(_dep_sem_path(ep), "rt", encoding="utf-8") as fh:
            _DEP_SEM_CACHE[ep] = _dep_json.load(fh)
    return _DEP_SEM_CACHE[ep]


def _dep_predict(shops, counts, day, horizon):
    dv = [0] * len(_DEP_CM_PRODUCTS)
    for s in shops:
        for p, k in _DEP_DEMAND.get(s, {}).items():
            dv[_DEP_CM_PRODUCTS.index(p)] += k
    cnt = [float(counts.get(l, 0)) for l in _DEP_LABELS]
    day = max(0, min(29, int(day)))
    df = day / 29.0
    feat = list(dv) + cnt + [df] + [df * x for x in dv]
    unlocked = 100 - int(counts.get(" L", 0))
    co = _DEP_CM["coefficients"][str(int(horizon))]
    out = {}
    for l in _DEP_LABELS:
        c = co[l]
        v = c["bias"]
        for w, x in zip(c["coef"], feat):
            v += w * x
        out[l] = max(0.0, min(float(unlocked), v))
    return out


def _dep_label(t):
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


def _dep_labels(tiles):
    return [_dep_label(t) for row in tiles for t in row]


def _dep_shops(obs):
    out = []
    for s in list(_g(_g(obs, "town", {}), "unlocked_shops", []) or []):
        if isinstance(s, dict):
            s = s.get("name") or s.get("type") or s.get("kind")
        out.append(str(s))
    return out


class _DepTarget:
    """Mutable Target with the executor's interface (n, board, plant, fert, hands, cash, final,
    struct_by_day, animals_by_day, land_day, cum_sold, events)."""

    def __init__(self, t):
        self.n = t.n
        self.board = [list(b) for b in t.board]
        self.plant = [dict(x) for x in t.plant]
        self.fert = [set(x) for x in t.fert]
        self.hands = list(t.hands)
        self.cash = list(t.cash)
        self.final = t.final
        self.struct_by_day = [dict(x) for x in t.struct_by_day]
        self.animals_by_day = [dict(x) for x in t.animals_by_day]
        self.land_day = dict(t.land_day)
        self.cum_sold = [Counter() for _ in range(t.n)]
        self.events = list(t.events)


_DEP = {}
_DEP_BASE = None
_MGT_REPORT = {}     # numeric diagnostics, copied into the ladder-panel result ("router")
_MGT_HISTORY = []    # (day, followed episode) -> the ladder-panel result's "switches"


def _dep_struct_map(T, D, tiles):
    """map the plan's structure tiles (days >= D) onto our structures of the same kind."""
    want = {}
    for d in range(D, T.n):
        want.update(T.struct_by_day[d])
    ours = {}
    for idx in range(100):
        t = _tile(tiles, idx)
        if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"):
            ours[idx] = t["kind"]
    smap, claimed = {}, set()
    for tt, kind in want.items():
        if ours.get(tt) == kind:
            smap[tt] = tt
            claimed.add(tt)
    for tt in sorted(want):
        if tt in smap:
            continue
        kind = want[tt]
        best = None
        for idx, k in ours.items():
            if k != kind or idx in claimed:
                continue
            key = (_dist((idx % 10, idx // 10), (tt % 10, tt // 10)), idx)
            if best is None or key < best[0]:
                best = (key, idx)
        if best is not None:
            smap[tt] = best[1]
            claimed.add(best[1])
    return smap


def _dep_switch(T, t2, D, tiles):
    S = _S
    late = CFG["late"]
    for d in range(D, T.n):
        T.board[d] = list(t2.board[d])
        T.plant[d] = dict(t2.plant[d])
        T.fert[d] = set(t2.fert[d])
        T.hands[d] = t2.hands[d]
        T.struct_by_day[d] = dict(t2.struct_by_day[d])
        T.animals_by_day[d] = dict(t2.animals_by_day[d])
    done = S["done"] if S is not None else set()
    pending = [e for e in T.events if e[0] < D and (e[0], e[1]) not in done
               and D - e[0] <= late.get(e[2], LATE[e[2]])]
    T.events = [e for e in T.events if e[0] < D] + [e for e in t2.events if e[0] >= D]
    for (pd, tt, crop) in pending:            # keep our pending catch-ups valid under the new board
        for d in range(D, min(T.n, pd + late.get(crop, LATE[crop]) + 1)):
            T.board[d][tt] = CROP_LABEL[crop]
    for q, dq in t2.land_day.items():
        T.land_day[q] = dq
    if S is not None:
        S["smap"] = _dep_struct_map(T, D, tiles)


def _dep_retrieve(day, shops, labels, k):
    res = _dep_lpr.retrieve(shops, labels, day, k=k, lam=DEP_CFG["lam"])
    if not res:
        return None
    if len(res) == 1:
        return res[0][1]
    corpus = {g["episode"]: g for g in _dep_lpr.load_corpus()}
    dd = min(29, day + 3)
    best = None
    for _, ep, _w in res:
        b = corpus[ep]["boards"][dd]
        cost = sum(w2 * _dep_lpr.hamming(b, corpus[ep2]["boards"][dd]) for _, ep2, w2 in res)
        if best is None or cost < best[0]:
            best = (cost, ep)
    return best[1]


def _dep_crop_alive_at(t, day_at):
    """does our plant tile t still show its crop at the start of day_at (lifecycle by engine rules)?"""
    c = CROPS[t["crop"]]
    age = day_at - t["planted_day"]
    if c["ongoing"]:
        return age <= _ongoing_last_age(t["crop"])
    return age < c["maxday"]


def _dep_free_tiles(tiles, reserved, pref_board, label):
    cands = []
    for idx in range(100):
        if idx in reserved:
            continue
        t = _tile(tiles, idx)
        if t == "LOCKED":
            continue
        if t is None or _is_weed(t):
            pref = 0 if (pref_board is not None and pref_board[idx] == label) else 1
            x, y = idx % 10, idx // 10
            cands.append((pref, abs(x - 4.5) + abs(y - 4.5), idx))
    cands.sort()
    return [c[2] for c in cands]


def _dep_compose(obs, day):
    """composition targets for today from the count model."""
    T = _T
    S = _S
    me = int(_g(obs, "player", 0))
    farm = _g(obs, "farms")[me]
    tiles = farm["tiles"]
    shops = _dep_shops(obs)
    labels = _dep_labels(tiles)
    counts = Counter(labels)
    d = day
    first = not _DEP.get("composing")
    if first:
        _DEP["composing"] = True
        T.events = [e for e in T.events if e[0] < d]
        for dd in range(d, T.n):
            T.plant[dd] = {}
            T.fert[dd] = set()
    # the plan from today: our live board
    struct, anim = {}, {}
    for idx in range(100):
        t = _tile(tiles, idx)
        if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"):
            struct[idx] = t["kind"]
            if t.get("animal"):
                anim[idx] = t["animal"]
    # keep structures/animals we asked for on earlier compose days and not yet built/placed
    for idx, kind in _DEP.get("new_struct", {}).items():
        if idx not in struct:
            cur = _tile(tiles, idx)
            if cur is None or _is_weed(cur) or (_is_plant(cur) and _plant_state(cur, day)[2]):
                struct[idx] = kind
    na0 = _DEP.get("new_anim", {})
    for idx in list(na0):
        if idx in anim:
            na0.pop(idx)             # placed: from now on it is simply one of our animals
    for idx, sp in na0.items():
        if struct.get(idx) and idx not in anim and d <= DEP_CFG["last_animal"][sp] + 2:
            anim[idx] = sp
    starving = {_animal(_tile(tiles, i)) for i in _DEP.get("nofeed", ())}
    # the executor's reservations for today..today+2
    reserved = set(struct)
    for dd in range(d, min(T.n, d + 3)):
        reserved |= set(T.plant[dd])
    lead_t = _DEP.get("lead_t")
    pred_s = _dep_predict(shops, counts, d, DEP_CFG["h_short"])
    pred_l = _dep_predict(shops, counts, d, DEP_CFG["h_long"])
    done = S["done"] if S is not None else set()
    log = _DEP["log"]
    for crop in ("STRAWBERRY", "TOMATO", "MELON", "WHEAT", "CARROT"):
        if d > DEP_CFG["last_plant"][crop]:
            continue
        lab = CROP_LABEL[crop]
        h = DEP_CFG["h_short"] if crop in ("WHEAT", "CARROT") else DEP_CFG["h_long"]
        pred = pred_s if h == DEP_CFG["h_short"] else pred_l
        surv = 0
        for idx in range(100):
            t = _tile(tiles, idx)
            if _is_plant(t) and t["crop"] == crop and _dep_crop_alive_at(t, d + h):
                surv += 1
        pend = 0
        for (pd, tt, c2) in T.events:
            if c2 == crop and pd <= d and d - pd <= CFG["late"].get(crop, LATE[crop]) and (pd, tt) not in done:
                m = S["pmap"].get((pd, tt), tt) if S is not None else tt
                cur = _tile(tiles, m)
                if not (_is_plant(cur) and cur["crop"] == crop and cur["planted_day"] >= pd):
                    pend += 1
        need = int(pred[lab] - surv - pend + 0.5)
        need = min(need, DEP_CFG["max_new_per_crop"])
        if need <= 0:
            continue
        pref = None
        if lead_t is not None:
            pref = lead_t.board[min(lead_t.n - 1, d + h)]
        free = _dep_free_tiles(tiles, reserved, pref, lab)
        for idx in free[:need]:
            T.events.append((d, idx, crop))
            T.plant[d][idx] = crop
            reserved.add(idx)
            for dd in range(d, min(T.n, d + CFG["late"].get(crop, LATE[crop]) + 1)):
                T.board[dd][idx] = lab
            log["plant_" + crop] += 1
    # animals
    ns = _DEP.setdefault("new_struct", {})
    na = _DEP.setdefault("new_anim", {})
    for sp in ("SHEEP", "COW", "GOOSE"):
        if d > DEP_CFG["last_animal"][sp] or sp in starving:
            continue
        lab = _DEP_ANIMAL_LABEL[sp]
        have = sum(1 for v in anim.values() if v == sp)
        need = int(pred_l[lab] - have + 0.5)
        if need <= 0:
            continue
        kind = ANIMALS[sp]["structure"]
        empties = [idx for idx, k in struct.items() if k == kind and idx not in anim]
        for idx in empties[:need]:
            anim[idx] = sp
            na[idx] = sp
            need -= 1
            log["animal_" + sp] += 1
        if need > 0:
            pref = lead_t.board[min(lead_t.n - 1, d + 3)] if lead_t is not None else None
            free = _dep_free_tiles(tiles, reserved, pref, lab)
            for idx in free[:need]:
                struct[idx] = kind
                anim[idx] = sp
                ns[idx] = kind
                na[idx] = sp
                reserved.add(idx)
                log["animal_" + sp] += 1
                log["build_" + kind] += 1
    for dd in range(d, T.n):
        T.struct_by_day[dd] = dict(struct)
        T.animals_by_day[dd] = dict(anim)
    if S is not None:
        for idx in struct:
            S["smap"][idx] = idx
    # land: the model expects fewer locked tiles than we have
    nq = len(list(farm.get("unlocked_quadrants", ["NW"]))) - 1
    if nq < 3 and pred_l[" L"] <= counts.get(" L", 0) - 13 and d <= 20:
        q = LAND_ORDER[nq]
        if T.land_day.get(q, 99) > d:
            T.land_day[q] = d
            log["land"] += 1
    # hands from today's work
    crops = sum(1 for idx in range(100) if _is_plant(_tile(tiles, idx))) + len(T.plant[d])
    b0, b1, b2 = DEP_CFG["hands_coef"]
    T.hands[d] = max(0, min(14, int(b0 + b1 * crops + b2 * len(anim) + 0.5)))


def _dep_nofeed(obs, day):
    """animals whose remaining output cannot pay for their feed."""
    me = int(_g(obs, "player", 0))
    tiles = _g(obs, "farms")[me]["tiles"]
    prices = dict(_g(_g(obs, "market", {}), "prices", {}))
    pw = float(prices.get("WHEAT", 25)) + 1
    out = set()
    if day < DEP_CFG["nofeed_from"]:
        return out
    for idx in range(100):
        t = _tile(tiles, idx)
        sp = _animal(t)
        if not sp:
            continue
        a = ANIMALS[sp]
        pd0 = t.get("placed_day", 0) or 0
        prods = [p for p in range(day, 29) if p - pd0 >= a["first"] and (p - pd0 - a["first"]) % a["interval"] == 0]
        if not prods:
            out.add(idx)
            continue
        b = int(t.get("pending_care_bonus", 0) or 0)
        cur, units = day, 0
        for p in prods:
            b += p - cur
            units += min(a["max_held"], 1 + b)
            b = 1
            cur = p + 1
        unfed = sum(1 for p in prods if p <= day + 1)
        value = (units - unfed) * float(prices.get(a["product"], 0)) * 0.8
        cost = (prods[-1] - day + 1) * pw
        if value < cost:
            out.add(idx)
    return out


_dep_orig_tile_ops = _tile_ops


def _dep_tile_ops(idx, t, job, fert, day, last_day, seeds):
    ops, need, prio = _dep_orig_tile_ops(idx, t, job, fert, day, last_day, seeds)
    if job is None and idx in _DEP.get("nofeed", ()) and _animal(t):
        k = sum(1 for o in ops if o[0] == "FEED")
        ops = [o for o in ops if o[0] not in ("FEED", "CARE")]
        if k and need.get("WHEAT", 0):
            need["WHEAT"] -= k
            if need["WHEAT"] <= 0:
                del need["WHEAT"]
        if not any(o[0] in ("HARVEST",) for o in ops):
            prio = 3 if not ops else min(prio, 2)
    return ops, need, prio


_tile_ops = _dep_tile_ops


def _dep_sell_quota(obs, day):
    """cumulative sell quota for the executor: everything, except wheat the herd still eats."""
    T = _T
    d = min(day, T.n - 1)
    S = _S
    step = int(_g(obs, "step", 0))
    sold = S["sold"] if (S is not None and step > 0) else Counter()
    me = int(_g(obs, "player", 0))
    tiles = _g(obs, "farms")[me]["tiles"]
    private = _g(obs, "private", {})
    shed = dict(_g(private, "shed", {}))
    n_anim = sum(1 for row in tiles for t in row if _animal(t))
    nofeed = _DEP.get("nofeed", ())
    n_fed = n_anim - sum(1 for idx in nofeed if _animal(_tile(tiles, idx)))
    keep = n_fed * max(0, 28 - day) + DEP_CFG["wheat_margin"]
    cs = Counter()
    for p in PRODUCTS:
        if p == "WHEAT":
            cs[p] = sold[p] + max(0, int(shed.get("WHEAT", 0) or 0) - keep)
        else:
            cs[p] = sold[p] + 10 ** 6
    T.cum_sold[d] = cs


def _dep_init():
    global _T, _DEP_BASE
    if _DEP_BASE is None:
        _DEP_BASE = Target(_dep_load_sem(_DEP_EXEMPLAR))
    _T = _DepTarget(_DEP_BASE)
    _DEP.clear()
    _DEP.update({"switched": set(), "composed": set(), "lead_t": _DEP_BASE, "nofeed": set(),
                 "log": Counter(), "picks": [], "errors": 0, "tmax": 0.0})
    _MGT_REPORT.clear()
    del _MGT_HISTORY[:]
    _MGT_HISTORY.append((0, _DEP_EXEMPLAR))


def _dep_update(obs, day, hour):
    T = _T
    me = int(_g(obs, "player", 0))
    farm = _g(obs, "farms")[me]
    tiles = farm["tiles"]
    if day in (3, 6, 9) and day not in _DEP["switched"] and day < DEP_CFG["compose_from"]:
        shops = _dep_shops(obs)
        if len(shops) >= day // 3 or hour >= 2:
            _DEP["switched"].add(day)
            k = DEP_CFG["k_day3"] if day == 3 else DEP_CFG["k_late"]
            ep = _dep_retrieve(day, shops, _dep_labels(tiles), k)
            if ep is not None:
                t2 = Target(_dep_load_sem(ep))
                _dep_switch(T, t2, day, tiles)
                _DEP["lead_t"] = t2
                _DEP["picks"].append((day, int(ep)))
                _MGT_HISTORY.append((day, int(ep)))
    if day >= DEP_CFG["compose_from"] and day not in _DEP["composed"]:
        _DEP["composed"].add(day)
        _dep_compose(obs, day)
        _DEP["nofeed"] = _dep_nofeed(obs, day)
    _dep_sell_quota(obs, day)


# ===== END DEPLOY SECTION; the entry point must stay the LAST callable in the file ===========
def mgt_lead_deploy_agent(obs, config=None):
    t0 = time.time()
    step = int(_g(obs, "step", 0))
    day, hour = divmod(step, 24)
    if step == 0 or not _DEP or step < _DEP.get("last_step", -1):
        _dep_init()
    _DEP["last_step"] = step
    try:
        _dep_update(obs, day, hour)
    except Exception as exc:          # never crash the game on a target-construction error
        _DEP["errors"] += 1
        _DEP["last_error"] = "%s: %s" % (type(exc).__name__, exc)
    out = agent(obs, config)
    _DEP["tmax"] = max(_DEP["tmax"], time.time() - t0)
    if hour == 23 or step >= 718:
        _MGT_REPORT.update({k: v for k, v in _DEP["log"].items()})
        _MGT_REPORT.update(errors=_DEP["errors"], tmax=round(_DEP["tmax"], 4), n_nofeed=len(_DEP.get("nofeed", ())),
                           exec_tmax=round(_S["tmax"], 4) if _S else 0)
    return out

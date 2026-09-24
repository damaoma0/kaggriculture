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
    "dispatch": "greedy",    # "greedy" (per-step matching) | "route" (sweep plan per day; 0.506, experimental)
    "two_opt": True,
    "travel_w": 1.4,
    "reach_w": 4.0,
    "insert_by_finish": True,
    "pick_k": 4,
    "prio3": True,
    "hires_first": True,
    "fert_prio": 1,
    "pick_cap": {"WHEAT": 3, "FERTILIZER": 4},
    "deliver_value_late": 1000,
    "hires_at_front": True,
    "place_bonus": 8,
    "place_bonus_days": 0,
    "window_p0": ["MELON"],
    "fert_reserve_soon": True,
    "lazy_fetch": False,
    "harvest_before_build": True,
    "spawn_allot": False,
    "maint_source": "ours",   # ablation: "leader" = the leader's per-tile per-day WATER/FEED/CARE/FERTILIZE
    "sched_maint": True,      # (default on since 2026-09-24: S1f 0.862/0.854/0.833 vs A29 0.792/0.780/0.785) scheduler: maintenance jobs (value, deadline) from scripts/fragments/sem_maintenance.py
    "surv_reserve": False,    # from surv_hour: survival jobs (dies / escapes tonight) get nearest-first routes, only their op
    "surv_hour": 16,
    "sched_dispatch": False,  # scheduler: dispatch by value density among jobs finishable before their deadline
    "sched_hire": False,      # scheduler: hire the n-th hand while the value only it adds exceeds fib(n)
    "mj_every": 3,            # re-solve maintenance jobs at most every N hours when the asset set changed
    "mj_collect": True,       # value the daily fertilizer an animal yields (keeps old animals fed longer)
    "opt_harvest_frac": 0.15, # value of an optional (early) harvest = held units x price x this (cash now)
    "plan_value": 400.0,      # value of a plan job (plant / build / place pipeline) for the scheduler
    "travel_est": 2.0,
    "sched_cost": "skip",     # "skip" (value picks today's skips, distance routes) | "prize" | "density"
    "step_value": 40.0,       # coins one unit-step is worth (prize cost)
    "skip_slack": 1.0,        # skip dispatch: fraction of the remaining unit-hours the kept jobs may fill        # hiring model: travel steps per tile job
    "hire_idle": 0.0,         # hiring model: extra coins a hand must earn (idle risk)
    "maint_safety": False,    # ablation B2: with maint_source="leader", still save plants/animals that die tonight
    "hands_d29_fix": True,    # A29 (default on since 2026-09-24): hire the day-28 count on day 29 (the corpus records 0 hands on day 29 because the day-end hook never runs on the last day)
    "sell_source": "leader",  # ablation: "shed" = mgt_lead_deploy's sell-as-it-reaches-the-shed rule
    "hire_source": "ours",    # ablation: "leader_steps" = the leader's HIRE orders at the leader's steps
    "route_once": True,
    "add_radius": 3,
    "late_p1": 0,
    "steal_radius": 5,
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

_SMNS = None


def _sm():
    """scripts/fragments/sem_maintenance.py (stdlib-only; pasted into the single-file agent later)."""
    global _SMNS
    if _SMNS is None:
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "fragments", "sem_maintenance.py")
        if not os.path.isfile(path):
            path = os.path.join(os.getcwd(), "scripts", "fragments", "sem_maintenance.py")
        ns = {}
        with open(path, encoding="utf-8") as fh:
            exec(compile(fh.read(), "sem_maintenance", "exec"), ns)
        _SMNS = ns
    return _SMNS


_T = None      # Target
_S = None      # per-game state


def _quad(x, y):
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# =========================================================================== TARGET (interface)
# A target supplies, per day d: events [(plant_day, tile, crop)], plant[d] {tile: crop}, fert[d] set(tile),
# struct_by_day[d] {tile: 'COOP'|'PASTURE'}, animals_by_day[d] {tile: species}, hands[d], cum_sold[d]
# Counter(product -> cumulative units sold through day d), land_day {quadrant: day}, board[d] (labels), n.
# Deployment builds the same fields from other sources (replace Target / configure only).

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
        # OPTIONAL fields (ablation only; deployment targets may omit them):
        # maint[d] = {'WATER'|'FEED'|'CARE'|'FERTILIZE': set(tile)} the leader's own maintenance that day
        self.maint = [{op: set(ts) for op, ts in day["maintenance"].items()} for day in days]
        self.hire_steps = {}      # step -> number of HIRE orders the leader issued (set by the ablation harness)


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


# =========================================================================== PLANNER (target -> tile jobs)

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
    if CFG["maint_source"] == "leader":
        mp = {}
        for (pd, t2), mm in S["pmap"].items():
            mp[t2] = mm
        mp.update({k: v for k, v in S["smap"].items()})
        lm = getattr(T, "maint", None)
        S["lmaint"] = {op: {mp.get(tt, tt) for tt in ts} for op, ts in (lm[d] if lm else {}).items()}
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
                        if CFG["harvest_before_build"]:
                            return [["HARVEST"]], need, 0
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
    if CFG["sched_maint"] and _S is not None and (_is_plant(t) or _animal(t)):
        r = _sched_tile_ops(idx, t, day)
        if r is not None:
            return r
    if _is_plant(t):
        c = CROPS[t["crop"]]
        age = day - t["planted_day"]
        own_fert = False
        lm = _S.get("lmaint") if (CFG["maint_source"] == "leader" and _S) else None
        if CFG["fert_ongoing"] and c["ongoing"] and day < last_day - 1:
            # a production falls within the 3 fertilized days and the plant is not finished
            last = _ongoing_last_age(t["crop"])
            for k in range(3):
                a = age + k + 1  # production visible at age a happens at the end of day+k
                if c["first"] <= a <= last and (a - c["first"]) % c["interval"] == 0:
                    own_fert = True
                    break
        if lm is not None:
            own_fert = False
        if (idx in fert or own_fert) and t.get("fertilized_until_day", -1) < day and day < last_day:
            ops.append(["FERTILIZE"])
            need["FERTILIZER"] += 1
            prio = min(prio, CFG["fert_prio"])
        wn, urgent = _water_needed(t, day, last_day)
        if lm is not None:
            cu1 = t.get("consecutive_unwatered", 0) >= 1 and day < last_day
            wn = (idx in lm.get("WATER", ()) or (CFG["maint_safety"] and cu1)) and not t.get("watered_today")
            urgent = wn and cu1
        if wn:
            ops.append(["WATER"])
            # a window water on a one-time crop adds a unit (melon ~ $200): treat as urgent
            valuable = (not c["ongoing"]) and CFG["window_urgent"] and t["crop"] in CFG["window_urgent"]
            if CFG["prio3"]:
                hard = (not c["ongoing"]) and t["crop"] in CFG["window_p0"]
                prio = min(prio, 0 if (urgent or (valuable and hard)) else 1 if valuable else 2)
            else:
                prio = min(prio, 1 if (urgent or valuable) else 2)
        if c["ongoing"]:
            if t.get("yield_units", 0) > 0 and age >= c["first"]:
                ops.append(["HARVEST"])
                risk = age >= _ongoing_last_age(t["crop"]) or t.get("yield_units", 0) >= c["max"] - 1 or day >= last_day - 1
                prio = min(prio, 1 if (risk or not CFG["prio3"]) else 2)
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
            lma = _S.get("lmaint") if (CFG["maint_source"] == "leader" and _S) else None
            if not t.get("fed_today") and (lma is None or idx in lma.get("FEED", ())
                                           or (CFG["maint_safety"] and t.get("consecutive_unfed", 0) >= 1)):
                ops.append(["FEED"])
                need["WHEAT"] += 1
                if CFG["prio3"]:
                    prio = min(prio, 0 if t.get("consecutive_unfed", 0) >= 1 else 1)
                else:
                    prio = min(prio, 1 if t.get("consecutive_unfed", 0) >= 1 else 2)
            if not t.get("cared_today") and (lma is None or idx in lma.get("CARE", ())):
                ops.append(["CARE"])
                prio = min(prio, 2)
        if t.get("fertilizer_available"):
            ops.append(["COLLECT_FERTILIZER"])
            prio = min(prio, 2)
        if t.get("yield_units", 0) > 0:
            ops.append(["HARVEST"])
            risk = t.get("yield_units", 0) >= ANIMALS[t["animal"]]["max_held"] - 2 or day >= last_day - 1
            prio = min(prio, 1 if (risk or not CFG["prio3"]) else 2)
    return ops, need, prio


def _sched_done(cmd, t, day):
    if cmd == "WATER":
        return bool(t.get("watered_today"))
    if cmd == "FEED":
        return bool(t.get("fed_today"))
    if cmd == "CARE":
        return bool(t.get("cared_today"))
    if cmd == "FERTILIZE":
        return t.get("fertilized_until_day", -1) >= day + 2
    if cmd == "HARVEST":
        return t.get("yield_units", 0) <= 0
    if cmd == "COLLECT_FERTILIZER":
        return not t.get("fertilizer_available")
    return False


def _sched_tile_ops(idx, t, day):
    """maintenance ops of our live asset from the value/deadline job list (sem_maintenance)."""
    S = _S
    asset = t.get("crop") if _is_plant(t) else t.get("animal")
    start = t.get("planted_day") if _is_plant(t) else t.get("placed_day")
    if (idx, asset, start) not in S.get("mj_known", ()):
        return None          # planted / placed after the last solve: our own rules until the next refresh
    ops, need, prio, val, dl = [], Counter(), 3, 0.0, 23
    for j in sorted(S.get("mj", {}).get(idx, ()), key=lambda j: j.get("order", 0)):
        if j.get("asset") != asset:
            continue
        cmd = j["cmd"]
        if _sched_done(cmd, t, day):
            continue
        if j.get("optional"):
            # early harvest only where the yield keeps accruing anyway (animals, strawberry / tomato); a one-time
            # crop's harvest ends the plant, so it waits for the module's required harvest
            if _is_plant(t) and not CROPS[t["crop"]]["ongoing"]:
                continue
            v = float(j.get("held", 0)) * float(j.get("price", 0)) * CFG["opt_harvest_frac"]
        else:
            v = max(0.0, float(j.get("value", 0.0)))
        ops.append([cmd])
        for k, n in (j.get("needs") or {}).items():
            need[k] += n
        val += v
        if v > 0:
            dl = min(dl, int(j.get("deadline", 23)))
        prio = min(prio, 0 if j.get("kind") == "survival" else 1 if v > 0 else 2)
    # CARE pays only when fed: keep FEED before CARE on the tile
    ops.sort(key=lambda o: {"FERTILIZE": 0, "FEED": 0, "WATER": 1, "CARE": 1, "HARVEST": 2, "COLLECT_FERTILIZER": 3}.get(o[0], 5))
    S["tval"][idx] = (val, dl)
    return ops, need, prio


def _first_need(ops, inv):
    """items the ops before (and including) the first item-consuming op need that inv lacks."""
    need = Counter()
    for op in ops:
        c = op[0]
        k = "WHEAT" if c == "FEED" else "FERTILIZER" if c == "FERTILIZE" else op[1] if c == "PLACE" else None
        if k is None:
            continue
        need[k] += 1
        return [k] if inv.get(k, 0) < need[k] else []
    return []


# =========================================================================== EXECUTOR + MARKET
# Target-agnostic except: _market reads _T.cum_sold / _T.hands / _T.land_day / _T.fert (sell quota, hires, land).


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
    if CFG["sched_maint"]:
        sig = []
        for idx in range(100):
            t = _tile(tiles, idx)
            if _is_plant(t):
                sig.append((idx, t["crop"], t["planted_day"]))
            elif _animal(t):
                sig.append((idx, t["animal"], t.get("placed_day")))
        sig = tuple(sig)
        if S.get("mj_day") != day or (S.get("mj_sig") != sig and hour - S.get("mj_hour", -99) >= CFG["mj_every"]):
            try:
                jl = _sm()["maintenance_jobs"](obs, me, prices=None, fertilize="auto", include_optional=True,
                                              collect=CFG["mj_collect"], log=S.setdefault("abandon", []))
            except Exception as exc:  # never crash: fall back to the previous list
                S["log"]["mj_error"] += 1
                jl = None
            if jl is not None:
                by = {}
                for j in jl:
                    by.setdefault(j["tile"][1] * 10 + j["tile"][0], []).append(j)
                S["mj"] = by
                S["mj_day"], S["mj_sig"], S["mj_hour"] = day, sig, hour
                S["mj_known"] = set(sig)
                S["log"]["mj_calls"] += 1
    S["tval"] = {}

    # ---- tile tasks
    tasks = {}
    for idx in range(100):
        t = _tile(tiles, idx)
        if t == "LOCKED":
            continue
        ops, need, prio = _tile_ops(idx, t, jobs.get(idx), fert, day, last_day, seeds)
        if ops:
            tasks[idx] = (ops, need, prio)
            if idx not in S["tval"]:
                S["tval"][idx] = ((CFG["plan_value"] if jobs.get(idx) else 50.0 * len(ops)), 23)

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

    skipped_now = set()
    if CFG["sched_dispatch"] and CFG["sched_cost"] == "skip":
        # temporary skips: keep the highest value-density jobs that fit the crew's remaining unit-hours
        cap = sum(max(0, 23 - hour) for _ in range(n)) * CFG["skip_slack"]
        items = []
        for i2, (o2, n2, p2) in tasks.items():
            v2, dl2 = S["tval"].get(i2, (0.0, 23))
            tt2 = len(o2) + CFG["travel_est"]
            items.append((-(v2 / tt2), i2, tt2))
        items.sort()
        acc = 0.0
        for _, i2, tt2 in items:
            acc += tt2
            if acc > cap:
                skipped_now.add(i2)
        if hour == 12:
            S["log"]["skip_jobs_h12"] += len(skipped_now)

    def cost(u, idx):
        ops, need, prio = tasks[idx]
        p = pos[u]
        tgt = (idx % 10, idx // 10)
        ok = usable_ops(u, ops, need)
        if not ok:
            return None
        if CFG["lazy_fetch"]:
            miss = [k for k in _first_need(ok, invs[u]) if shed_left.get(k, 0) > 0]
        else:
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
        if CFG["sched_dispatch"] and CFG["sched_cost"] == "skip":
            if idx in skipped_now:
                c += 30             # today's temporary skip: only when nothing else is left
        elif CFG["sched_dispatch"]:
            v, dl = S["tval"].get(idx, (0.0, 23))
            tt = c + len(ok)
            structural = any(o[0] in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE", "DIG") for o in ok)
            if hour + tt - 1 > dl and not structural:
                v *= 0.2            # past its deadline most of the value is gone
            if CFG["sched_cost"] == "prize":
                # prize-collecting: travel + ops minus the job's value in unit-steps
                c2 = tt - v / CFG["step_value"]
                if prev.get(u) == idx:
                    c2 -= CFG["keep_bonus"]
                return c2
            dens = (v + 1.0) / max(1.0, tt)
            if prev.get(u) == idx:
                dens *= 1.3
            return -dens
        if CFG["prio_mode"] == "old":
            return c + prio * (6 if hour >= 14 else 3)
        # urgency only matters when the day runs short: plant/place pipelines and
        # death-preventing work first late in the day
        if CFG["place_bonus"] and day <= CFG["place_bonus_days"] and any(o[0] == "PLACE" for o in ops):
            c -= CFG["place_bonus"]  # animals first (the leaders place every animal early in the day)
        if hour >= CFG["late_hour"] and prio >= 2:
            c += 10
        elif CFG["prio3"] and hour >= CFG["late_hour"] and prio == 1:
            c += CFG["late_p1"]
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
        if not CFG["sticky"] and prev.get(u) == idx and not CFG["sched_dispatch"]:
            c -= CFG["keep_bonus"]
        if not CFG["zone_penalty"]:
            return c
        return c + (0 if zone.get(idx, 0) == u else CFG["zone_penalty"])

    if CFG["dispatch"] == "route":
        actions, taken = _dispatch_route(S, day, hour, last_day, tiles, pos, invs, tasks, shed, seeds,
                                          demand, carried, prices, quota_open, fert_short)
    # delivery for same-day sale when cash binds (or a unit carries a lot)
    for u in range(n):
        if CFG["dispatch"] == "route":
            break
        if u in assign:
            continue
        dv = deliverable(invs[u])
        val = sum(prices.get(k, 0) * v for k, v in dv.items() if k in quota_open)
        late = CFG["prio3"] and hour >= CFG["late_hour"]
        if dv and hour < 22 and (((sum(dv.values()) >= 10 or val >= CFG["deliver_value"]) and not late)
                                 or (S.get("short") and val > 0) or (val >= CFG["deliver_value_late"] and hour < 20)):
            assign[u] = "D"
    surv_route = {}
    if CFG["surv_reserve"] and hour >= CFG["surv_hour"] and day < last_day and CFG["dispatch"] != "route":
        # every tile whose asset dies / escapes tonight unless served: nearest-arrival greedy routes
        surv = []
        for idx in tasks:
            t_ = _tile(tiles, idx)
            if _is_plant(t_) and not t_.get("watered_today") and t_.get("consecutive_unwatered", 0) >= 1:
                surv.append((idx, "WATER"))
            elif _animal(t_) and not t_.get("fed_today") and t_.get("consecutive_unfed", 0) >= 1:
                if any(invs[v].get("WHEAT", 0) > 0 for v in range(n)) or shed_left.get("WHEAT", 0) > 0:
                    surv.append((idx, "FEED"))
        if surv:
            clock = {u: hour for u in range(n) if assign.get(u) != "D"}
            where = {u: pos[u] for u in clock}
            wheat = {u: invs[u].get("WHEAT", 0) for u in clock}
            left = list(surv)
            while left and clock:
                best = None
                for u in clock:
                    for idx, op in left:
                        q = (idx % 10, idx // 10)
                        if op == "FEED" and wheat[u] <= 0:
                            s0 = _near_shed(where[u])
                            arr = clock[u] + _dist(where[u], s0) + 1 + _dist(s0, q)
                        else:
                            arr = clock[u] + _dist(where[u], q)
                        if best is None or arr < best[0]:
                            best = (arr, u, idx, op)
                arr, u, idx, op = best
                if arr > 23:
                    break
                surv_route.setdefault(u, []).append((idx, op))
                clock[u], where[u] = arr + 1, (idx % 10, idx // 10)
                if op == "FEED":
                    wheat[u] = max(0, wheat[u] - 1) if wheat[u] > 0 else 0
                left.remove((idx, op))
            S["log"]["surv_routed"] += sum(len(r) for r in surv_route.values())
            S["log"]["surv_unroutable"] += len(left)
        for u, r in surv_route.items():
            assign[u] = r[0][0]
            taken.add(r[0][0])
    free = [u for u in range(n) if u not in assign] if CFG["dispatch"] != "route" else []
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
        if CFG["dispatch"] == "route":
            break
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
                {k: min(CFG["pick_cap"].get(k, 3), max(0, demand[k] - carried[k])) for k in ("WHEAT", "FERTILIZER")})
            if CFG["spawn_allot"] and hour <= 2 and n > 1:
                # full-day allotment at spawn: this hand's share of the day's feeding
                share = -(-demand["WHEAT"] // n) + 1
                want["WHEAT"] = min(max(0, demand["WHEAT"] - carried["WHEAT"] + inv.get("WHEAT", 0)), share)
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
        if u in surv_route:
            sop = surv_route[u][0][1]
            if sop == "FEED" and inv.get("WHEAT", 0) <= 0 and shed_left.get("WHEAT", 0) > 0:
                s0 = _near_shed(p)
                if p != s0:
                    actions[u] = _step_toward(p, s0)
                else:
                    k = min(shed_left["WHEAT"], max(1, sum(1 for _, o in surv_route[u] if o == "FEED")))
                    shed_left["WHEAT"] -= k
                    actions[u] = ["PICKUP", "WHEAT", int(k)]
                continue
            if p != tgt:
                actions[u] = _step_toward(p, tgt)
                continue
            actions[u] = [sop]
            continue
        if CFG["lazy_fetch"]:
            miss = [k for k in _first_need(usable_ops(u, ops, need), inv) if shed_left.get(k, 0) > 0]
        else:
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
    if hour in (1, 23) and day < last_day:
        lg = S["log"]
        nf = sum(1 for ops, need, prio in tasks.values() if any(o[0] == "FERTILIZE" for o in ops))
        lg["fert_tasks_h%02d" % hour] += nf
        lg["fert_stock_h%02d" % hour] += shed.get("FERTILIZER", 0) + carried.get("FERTILIZER", 0)
    if hour == 23 and day < last_day and S.get("tval"):
        S["log"]["skipped_value"] += int(sum(v for i, (v, dl) in S["tval"].items() if i in tasks))
        S["log"]["skipped_jobs"] += len(tasks)
    if hour == 23 and day < last_day:
        lg = S["log"]
        for idx, (ops, need, prio) in tasks.items():
            t = _tile(tiles, idx)
            if _is_plant(t) and not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                lg["die_%s_%s" % (t["crop"], "assigned" if idx in taken else "unassigned")] += 1

            if _animal(t) and not t.get("fed_today"):
                lg["unfed_%s" % ("assigned" if idx in taken else "unassigned")] += 1
    if hour == 23 and day < last_day:
        for idx in range(100):
            t = _tile(tiles, idx)
            if _is_plant(t) and not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                if idx not in tasks:
                    S["log"]["dying_no_task"] += 1
                elif any(o[0] == "WATER" for o in tasks[idx][0]):
                    S["log"]["dying_water_task"] += 1
                else:
                    S["log"]["dying_task_without_water"] += 1
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


# ---- route dispatcher (sweep plan per day, executed closed loop) ---------------------------

import math as _math


def _job_items(ops):
    wheat = sum(1 for o in ops if o[0] == "FEED")
    fert = sum(1 for o in ops if o[0] == "FERTILIZE") - sum(1 for o in ops if o[0] == "COLLECT_FERTILIZER")
    animals = Counter(o[1] for o in ops if o[0] == "PLACE")
    return wheat, fert, animals


def _route_time(start_hour, p, route, tasks):
    t = start_hour
    for idx in route:
        q = (idx % 10, idx // 10)
        t += _dist(p, q) + len(tasks[idx][0])
        p = q
    return t


def _route_len(p, r):
    c, L = p, 0
    for i in r:
        q = (i % 10, i // 10)
        L += _dist(c, q)
        c = q
    return L


def _order_route(p, jobs, tasks):
    """nearest neighbour from p, then 2-opt on travel."""
    left = list(jobs)
    out = []
    cur = p
    while left:
        j = min(left, key=lambda i: (_dist(cur, (i % 10, i // 10)), i))
        out.append(j)
        left.remove(j)
        cur = (j % 10, j // 10)
    if CFG["two_opt"] and len(out) > 3:
        best = _route_len(p, out)
        improved = True
        loops = 0
        while improved and loops < 6:
            improved = False
            loops += 1
            for i in range(len(out) - 1):
                for k in range(i + 1, len(out)):
                    r = out[:i] + out[i:k + 1][::-1] + out[k + 1:]
                    L = _route_len(p, r)
                    if L < best:
                        out, best, improved = r, L, True
    return out


def _build_routes(S, hour, pos, tasks, n):
    """sweep: sort jobs by angle around the shed centre, cut into n balanced sectors, order each."""
    jobs = list(tasks)
    if not jobs:
        return {u: [] for u in range(n)}
    ang = {i: _math.atan2((i // 10) - 4.5, (i % 10) - 4.5) for i in jobs}
    jobs.sort(key=lambda i: (ang[i], _dist((4.5, 4.5), (i % 10, i // 10))))
    # start the sweep at the largest angular gap so no sector wraps across a cluster
    if len(jobs) > 2:
        gaps = [((ang[jobs[(k + 1) % len(jobs)]] - ang[jobs[k]]) % (2 * _math.pi), k) for k in range(len(jobs))]
        g, k = max(gaps)
        jobs = jobs[k + 1:] + jobs[:k + 1]
    home = (4, 4)

    def gtime(g):
        if not g:
            return 0
        need = set()
        for i in g:
            w_, f_, an = _job_items(tasks[i][0])
            if w_:
                need.add("W")
            if f_ > 0:
                need.add("F")
            need.update(an)
        # nearest-neighbour tour length from the shed
        left, cur, L = list(g), home, 0
        while left:
            j = min(left, key=lambda i: _dist(cur, (i % 10, i // 10)))
            L += _dist(cur, (j % 10, j // 10))
            cur = (j % 10, j // 10)
            left.remove(j)
        return len(need) + L + sum(len(tasks[i][0]) for i in g)

    def split(T):
        groups, cur = [], []
        for i in jobs:
            if cur and gtime(cur + [i]) > T:
                groups.append(cur)
                cur = []
            cur.append(i)
        groups.append(cur)
        return groups

    lo, hi = 1.0, 24.0 * 4
    best = split(hi)
    for _ in range(9):
        mid = (lo + hi) / 2
        g = split(mid)
        if len(g) <= n:
            best, hi = g, mid
        else:
            lo = mid
    groups = best
    while len(groups) < n:
        groups.append([])
    order = sorted(range(len(groups)), key=lambda g: -len(groups[g]))
    free = list(range(n))
    routes = {u: [] for u in range(n)}
    for g in order:
        if not free:
            break
        grp = groups[g]
        if grp:
            cx = sum(i % 10 for i in grp) / len(grp)
            cy = sum(i // 10 for i in grp) / len(grp)
            u = min(free, key=lambda v: (_dist(pos[v], (cx, cy)), v))
        else:
            u = free[-1]
        free.remove(u)
        routes[u] = _order_route(pos[u], grp, tasks)
    return routes


def _insert(routes, pos, hour, idx, tasks, limit=23.5):
    best = None
    q = (idx % 10, idx // 10)
    for u, r in routes.items():
        base = _route_time(hour, pos[u], r, tasks)
        prev = pos[u]
        for k in range(len(r) + 1):
            nxt = (r[k] % 10, r[k] // 10) if k < len(r) else None
            add = _dist(prev, q) + len(tasks[idx][0]) + (_dist(q, nxt) - _dist(prev, nxt) if nxt else 0)
            fin = base + add
            key = (fin > limit, fin if CFG["insert_by_finish"] else add, add)
            if best is None or key < best[0]:
                best = (key, u, k)
            if nxt:
                prev = nxt
    if best is None:
        return False
    _, u, k = best
    routes[u].insert(k, idx)
    return True


def _dispatch_route(S, day, hour, last_day, tiles, pos, invs, tasks, shed, seeds, demand, carried, prices,
                    quota_open, fert_short):
    n = len(pos)
    actions = [["PASS"] for _ in range(n)]
    lg = S["log"]
    key = (day, n)
    full = n >= _T.hands[min(day, _T.n - 1)] + 1 or hour >= 2
    if CFG["route_once"]:
        if S.get("rday") != day:
            S["rday"] = day
            S["rbuilt"] = False
            S["routes"] = _build_routes(S, hour, pos, tasks, n)
            S["deliver"] = set()
        elif not S["rbuilt"] and full:
            S["rbuilt"] = True
            S["routes"] = _build_routes(S, hour, pos, tasks, n)
    elif S.get("rkey") != key:
        S["rkey"] = key
        S["routes"] = _build_routes(S, hour, pos, tasks, n)
        S["deliver"] = set()
    routes = S["routes"]
    for u in list(routes):
        if u >= n:
            routes.pop(u)
    for u in range(n):
        routes.setdefault(u, [])
        routes[u] = [i for i in routes[u] if i in tasks]
    routed = set(i for r in routes.values() for i in r)
    for idx in sorted(tasks, key=lambda i: tasks[i][2]):
        if idx not in routed:
            if CFG["route_once"]:
                q = (idx % 10, idx // 10)
                near = min((_dist(q, (j % 10, j // 10)) for r in routes.values() for j in r), default=99)
                near = min(near, min(_dist(q, pos[v]) for v in range(n)))
                if near > CFG["add_radius"]:
                    continue
            _insert(routes, pos, hour, idx, tasks)
            routed.add(idx)
    # idle hands take the nearest task nobody has
    if CFG["route_once"]:
        for u in range(n):
            if routes[u]:
                continue
            free_t = [i for i in tasks if i not in routed]
            if free_t:
                i = min(free_t, key=lambda i: _dist(pos[u], (i % 10, i // 10)))
                routes[u] = [i]
                routed.add(i)
    shed_left = Counter(shed)
    seeds_left = Counter(seeds)
    endgame = day >= last_day

    def deliverable(inv):
        return {k: v for k, v in inv.items() if v > 0 and k in PRODUCTS and k != "WHEAT"
                and not (k == "FERTILIZER" and fert_short)}

    def route_need(u, k=None):
        need = Counter()
        bal = 0
        fneed = 0
        for i in (routes[u] if k is None else routes[u][:k]):
            w, f, an = _job_items(tasks[i][0])
            need["WHEAT"] += w
            bal -= f
            fneed = max(fneed, -bal)
            for a, c in an.items():
                need[a] += c
        need["FERTILIZER"] = fneed
        return need

    # idle units steal the job whose owner would reach it much later than they can
    for u in range(n):
        if routes[u] or hour >= 23:
            continue
        best = None
        for v, r in routes.items():
            if v == u or len(r) < 2:
                continue
            t = hour
            prev = pos[v]
            for k, i in enumerate(r):
                q = (i % 10, i // 10)
                t += _dist(prev, q) + len(tasks[i][0])
                prev = q
                if k == 0:
                    continue
                gain = t - (hour + _dist(pos[u], q))
                if _dist(pos[u], q) > CFG["steal_radius"]:
                    continue
                if gain > 2 and (best is None or gain > best[0]):
                    best = (gain, v, k, i)
        if best:
            _, v, k, i = best
            routes[v].pop(k)
            routes[u] = [i]

    # wheat rebalancing: FEED jobs of units without wheat (shed empty) go to units carrying surplus wheat
    if shed_left.get("WHEAT", 0) <= 0:
        surplus = {v: invs[v].get("WHEAT", 0) - route_need(v)["WHEAT"] for v in range(n)}
        for u in range(n):
            have = invs[u].get("WHEAT", 0)
            for i in list(routes[u]):
                if not any(o[0] == "FEED" for o in tasks[i][0]):
                    continue
                if have > 0:
                    have -= 1
                    continue
                donors = [v for v in range(n) if v != u and surplus[v] > 0]
                if not donors:
                    break
                q = (i % 10, i // 10)
                v = min(donors, key=lambda v: _dist(pos[v], q))
                routes[u].remove(i)
                r = routes[v]
                k = min(range(len(r) + 1), key=lambda k: (_dist((r[k - 1] % 10, r[k - 1] // 10) if k else pos[v], q)
                                                          + (_dist(q, (r[k] % 10, r[k] // 10)) if k < len(r) else 0)))
                r.insert(k, i)
                surplus[v] -= 1
                lg["feed_moved"] += 1

    for u in range(n):
        p = pos[u]
        inv = invs[u]
        if endgame:
            sellable = sum(v for k, v in inv.items() if k in PRODUCTS)
            s0 = _near_shed(p)
            if sellable and (22 - hour) <= _dist(p, s0) + 1:
                actions[u] = ["DROP"] if p == s0 else _step_toward(p, s0)
                continue
        rn = route_need(u, CFG["pick_k"] if n == 1 else None)
        dv = deliverable(inv)
        if "FERTILIZER" in dv:
            keep = rn.get("FERTILIZER", 0)
            if dv["FERTILIZER"] <= keep:
                dv.pop("FERTILIZER")
            else:
                dv["FERTILIZER"] -= keep
        if not endgame and (u in S["deliver"] or (dv and hour < 22)):
            val = sum(prices.get(k, 0) * v for k, v in dv.items() if k in quota_open)
            if dv and (u in S["deliver"] or sum(dv.values()) >= 10 or val >= CFG["deliver_value"]
                       or (S.get("short") and val > 0)):
                S["deliver"].add(u)
                s0 = _near_shed(p)
                if p != s0:
                    actions[u] = _step_toward(p, s0)
                elif all(k in dv for k in inv):
                    actions[u] = ["DROP"]
                    S["deliver"].discard(u)
                else:
                    k = sorted(dv)[0]
                    actions[u] = ["PLACE", k, int(dv[k])]
                    if len(dv) <= 1:
                        S["deliver"].discard(u)
                continue
            S["deliver"].discard(u)
        if p in SHED and hour < 23:
            got = None
            for k in ["WHEAT", "FERTILIZER"] + sorted(a for a in rn if a in ANIMALS):
                gap = min(rn.get(k, 0) - inv.get(k, 0), shed_left.get(k, 0))
                if gap > 0:
                    got = (k, gap)
                    break
            if got:
                shed_left[got[0]] -= got[1]
                actions[u] = ["PICKUP", got[0], int(got[1])]
                continue
        act = None
        for attempt in range(len(routes[u])):
            idx = routes[u][0]
            ops, need, prio = tasks[idx]
            tgt = (idx % 10, idx // 10)
            lack = [k for k, v in need.items() if inv.get(k, 0) < v]
            if lack and all(shed_left.get(k, 0) > 0 for k in lack):
                s0 = _near_shed(p)
                if p == s0:
                    k = lack[0]
                    amt = int(min(shed_left[k], max(need[k] - inv.get(k, 0), rn.get(k, 0) - inv.get(k, 0))))
                    shed_left[k] -= amt
                    act = ["PICKUP", k, amt]
                else:
                    act = _step_toward(p, s0)
                break
            usable = []
            has_feed = any(o[0] == "FEED" for o in ops)
            for op in ops:
                c = op[0]
                if c == "PLACE" and inv.get(op[1], 0) <= 0:
                    break
                if c in ("FEED", "CARE") and has_feed and inv.get("WHEAT", 0) <= 0:
                    continue
                if c == "FERTILIZE" and inv.get("FERTILIZER", 0) <= 0:
                    continue
                if c == "PLANT" and (seeds_left.get(op[1], 0) <= 0 or hour >= 23):
                    break
                usable.append(op)
            if not usable:
                routes[u].append(routes[u].pop(0))
                continue
            if p != tgt:
                act = _step_toward(p, tgt)
            else:
                op = usable[0]
                if op[0] == "PLANT":
                    seeds_left[op[1]] -= 1
                act = list(op)
            break
        if act is None:
            lg["route_idle"] += 1
            if dv and hour < 23:
                s0 = _near_shed(p)
                if p != s0:
                    act = _step_toward(p, s0)
                else:
                    k = sorted(dv)[0]
                    act = ["PLACE", k, int(dv[k])]
            else:
                act = ["PASS"]
        actions[u] = act
    taken = set(i for r in routes.values() for i in r)
    return actions, taken


def _sched_hands(S, day, hour, tasks, jobs=None):
    """hire the n-th hand while the value of the jobs only it adds (in value-density order, within the day's
    remaining unit-hours) exceeds fib(n-1); decided at hour 0 (re-used for later retries)."""
    key = ("hands", day)
    if key in S and hour > 0:
        return S[key]
    items = []
    for idx, (ops, need, prio) in tasks.items():
        v, dl = S.get("tval", {}).get(idx, (0.0, 23))
        tt = len(ops) + CFG["travel_est"] + (0.5 if need else 0.0)
        items.append((v / tt, v, tt))
    for idx, job in (jobs or {}).items():
        if idx in tasks:
            continue            # plan job whose seeds / animals are not in yet: it still needs a hand today
        tt = 3 + CFG["travel_est"]
        items.append((CFG["plan_value"] / tt, CFG["plan_value"], tt))
    items.sort(reverse=True)

    def done_value(k):
        cap = (24 - hour) + (23 - hour) * k
        tot = acc = 0.0
        for dens, v, tt in items:
            if acc + tt > cap:
                break
            acc += tt
            tot += v
        return tot
    k, prev_v = 0, done_value(0)
    cut = 0.0
    while k < 14:
        vk = done_value(k + 1)
        marginal = vk - prev_v
        if marginal <= _fib(k) + CFG["hire_idle"]:
            cut = marginal
            break
        k, prev_v = k + 1, vk
    S[key] = k
    lg = S["log"]
    lg["hire_hands"] += k
    lg["hire_cut_value"] += int(cut)
    return k


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
        if CFG["fert_reserve_soon"]:
            n_on = 0
            for r in farm["tiles"]:
                for t in r:
                    if _is_plant(t) and CROPS[t["crop"]]["ongoing"] and t.get("fertilized_until_day", -1) <= day:
                        c = CROPS[t["crop"]]
                        age = day - t["planted_day"]
                        last = _ongoing_last_age(t["crop"])
                        if any(c["first"] <= age + k + 1 <= last and (age + k + 1 - c["first"]) % c["interval"] == 0
                               for k in range(1, 4)):
                            n_on += 1
            tomorrow = max(tomorrow, n_on)
        else:
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
            if CFG["sell_source"] == "shed":
                # mgt_lead_deploy rule: everything as soon as it is in the shed, except the wheat the herd eats
                if p == "WHEAT":
                    n_an = sum(1 for r_ in farm["tiles"] for t_ in r_ if _animal(t_))
                    quota = shed.get("WHEAT", 0) - (n_an * max(0, 28 - day) + 10)
                else:
                    quota = have
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
    # hires come first: without hands nothing is maintained (death spiral); sell beyond quota to fund them
    hires = []
    if (not endgame or CFG["hands_d29_fix"]) and hour <= 12 and CFG["hires_first"]:
        want = T.hands[d] + CFG["hire_extra"]
        if CFG["sched_hire"]:
            want = _sched_hands(S, day, hour, tasks, jobs)
        elif CFG["hands_d29_fix"] and d == T.n - 1 and T.hands[d] == 0 and d > 0:
            # semantics artifact: hands_present of the last day is 0 (the end-of-day hook never runs on day 29)
            want = T.hands[d - 1] + CFG["hire_extra"]
        k = max(0, want - (len(pos) - 1))
        hires_today = int(farm.get("hires_today", 0))
        cost_all = sum(_fib(hires_today + i) for i in range(k))
        if cash < cost_all:
            gap = cost_all - cash
            for p in sorted(PRODUCTS, key=lambda q: -prices.get(q, 0)):
                if gap <= 0:
                    break
                already = sum(o[2] for o in sells if o[1] == p)
                can = shed.get(p, 0) - reserve.get(p, 0) - already
                if can <= 0 or prices.get(p, 0) <= 1:
                    continue
                q = min(can, int(gap // max(1, prices[p] * 0.85)) + 1)
                sells.append(["SELL", p, int(q)])
                gap -= q * prices[p] * 0.85
                cash += q * prices[p] * 0.85
        for i in range(k):
            c = _fib(hires_today + i)
            if cash - c < 0:
                break
            cash -= c
            hires.append(["HIRE"])
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
    if not endgame and hour <= 12 and not CFG["hires_first"]:
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
    if CFG["hire_source"] == "leader_steps":
        # the leader's own HIRE orders, at the leader's steps (they fail on cash exactly as orders do)
        hires = [["HIRE"]] * int(getattr(T, "hire_steps", {}).get(int(_g(obs, "step", 0)), 0))
    orders = []
    hire_cost = sum(_fib(int(farm.get("hires_today", 0)) + i) for i in range(len(hires)))
    if CFG["hires_at_front"] and hires and money >= hire_cost:
        # hands hired at hour h act from h+1: every hour a hire waits costs a unit-hour
        orders += hires[:10]
        hires = hires[10:]
    elif CFG["hires_at_front"] and hires:
        # fund the hires with the fewest, most valuable sales first, then hire in the same step
        est = money
        for o in sorted(sells, key=lambda o: -prices.get(o[1], 0) * o[2]):
            if est >= hire_cost or len(orders) >= 4:
                break
            orders.append(o)
            est += prices.get(o[1], 0) * o[2] * 0.85
        room = 10 - len(orders)
        orders += hires[:room]
        hires = hires[room:]
        sells = [o for o in sells if o not in orders]
    for o in sells:
        if len(orders) >= 4 and hour == 0 and not CFG["hires_at_front"]:
            break
        if len(orders) >= 10:
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

"""mgt_lead_deploy: mgt_lead's executor playing worlds it has never seen, choosing its own targets.

Research agent (2026-09-24). The EXECUTOR SECTION below is a verbatim copy of agents/mgt_lead.py (owned by the
E1 thread; copied from agents/mgt_lead.py = E1 scheduler build + idle tracer / helper split / p1 threshold (2026-09-25), sha256 26fc70382a2bfb5b; executor CFG defaults that differ in this copy: sell_source "sem", p1_min_value 30, release_stale_d True; re-sync by copying that file between the two marker lines. Only the
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
    "mj_fertilize": "auto",   # sem_maintenance fertilize: "auto" (when the extra units pay at market price) | True | {crop: ...}
    "early_onetime": False,   # optional harvest of wheat / carrot from one day before full yield (cycle research)
    "spawn_allot": False,
    "maint_source": "ours",   # ablation: "leader" = the leader's per-tile per-day WATER/FEED/CARE/FERTILIZE
    "sched_maint": True,      # (default on since 2026-09-24: S1f 0.862/0.854/0.833 vs A29 0.792/0.780/0.785) scheduler: maintenance jobs (value, deadline) from scripts/fragments/sem_maintenance.py
    "surv_reserve": True,     # (default on since R16: 0.874/0.866/0.844 vs 0.862/0.854/0.833) from surv_hour: survival jobs (dies / escapes tonight) get nearest-first routes, only their op
    "surv_hour": 16,
    "surv_harvest": False,
    "atrisk_bonus": 0,        # greedy cost bonus (steps) for a one-time crop at/after full yield with a harvest pending (decays tomorrow)
    "plant_cutoff": {"STRAWBERRY": 13, "TOMATO": 18, "MELON": 19, "WHEAT": 25, "CARROT": 26},   # last planting day with a full harvest before the end (min_maintenance); later plantings incl. catch-ups are skipped (2026-09-25: full panel +336, G1 +0.007)    # survival routes also take one-time crops at/after full-yield age (missed harvests decay)
    "sched_dispatch": False,  # scheduler: dispatch by value density among jobs finishable before their deadline
    "sched_hire": False,      # scheduler: hire the n-th hand while the value only it adds exceeds fib(n)
    "p1_min_value": 30.0,     # maintenance ops worth <= this (coins) count as priority 2 (deferred after late_hour); DEPLOY default 30 (2026-09-25: full panel +382, CI +61..+702; mgt_lead.py keeps 0)
    "deliver_units": 10,      # a unit carrying this many products walks them to the shed for same-day sale
    "release_stale_d": True,  # drop a delivery assignment once nothing deliverable is carried (1 idle step per DROP); DEPLOY default (with p1_min_value 30)
    "helper_split": False,    # a unit left free by the greedy joins a held animal tile and takes its last op
    "helper_crops": False,    # helper split also on ongoing crops (strawberry / tomato: HARVEST is independent of water)
    "idle_trace": None,       # research: directory for the idle-pass / dropped-job trace (one jsonl per game)
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
    "sell_source": "sem",  # sem = scripts/fragments/sem_market.py hold-and-batch rule; leader = the deploy quota (sell on arrival); shed = G1 ablation rule
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
        here = globals().get("__file__")          # undefined under Kaggle's loader (exec of the source)
        cands = [os.path.join(os.path.dirname(os.path.abspath(here)), "..", "scripts", "fragments", "sem_maintenance.py")] if here else []
        cands.append(os.path.join(os.getcwd(), "scripts", "fragments", "sem_maintenance.py"))
        path = next((c for c in cands if os.path.isfile(c)), cands[-1])
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
    cut = CFG["plant_cutoff"]
    for (pd, tt, crop) in T.events:
        if pd > d or d - pd > CFG["late"].get(crop, LATE[crop]):
            continue
        if cut and d > cut.get(crop, 99):
            ck = ("cut", pd, tt)
            if ck not in S["done"]:
                S["done"].add(ck)
                S["log"]["cut_" + crop] += 1       # would-be planting skipped: no full harvest reachable
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
            # crop's harvest ends the plant, so it waits for the module's required harvest -- unless early_onetime
            # (y3-style: wheat / carrot from one day before full yield, replanted the same day by the target)
            if _is_plant(t) and not CROPS[t["crop"]]["ongoing"]:
                c_ = CROPS[t["crop"]]
                if not (CFG["early_onetime"] and t["crop"] in ("WHEAT", "CARROT")
                        and day - t["planted_day"] >= c_["maxday"] - 1):
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
        prio = min(prio, 0 if j.get("kind") == "survival" else 1 if v > CFG["p1_min_value"] else 2)
    if _is_plant(t) and not CROPS[t["crop"]]["ongoing"] and t.get("yield_units", 0) > 0 \
            and day - t["planted_day"] >= CROPS[t["crop"]]["maxday"] and any(o[0] == "HARVEST" for o in ops):
        S.setdefault("atrisk", set()).add(idx)
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
                jl = _sm()["maintenance_jobs"](obs, me, prices=None, fertilize=CFG["mj_fertilize"], include_optional=True,
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
    S["atrisk"] = set()

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
        if CFG["atrisk_bonus"] and idx in S.get("atrisk", ()):
            c -= CFG["atrisk_bonus"]  # the whole crop is lost if this harvest waits until tomorrow
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
    if CFG["release_stale_d"]:
        for u in [u for u, v in assign.items() if v == "D" and u < n and not deliverable(invs[u])]:
            assign.pop(u, None)
    for u in range(n):
        if CFG["dispatch"] == "route":
            break
        if u in assign:
            continue
        dv = deliverable(invs[u])
        val = sum(prices.get(k, 0) * v for k, v in dv.items() if k in quota_open)
        late = CFG["prio3"] and hour >= CFG["late_hour"]
        if dv and hour < 22 and (((sum(dv.values()) >= CFG["deliver_units"] or val >= CFG["deliver_value"]) and not late)
                                 or (S.get("short") and val > 0) or (val >= CFG["deliver_value_late"] and hour < 20)):
            assign[u] = "D"
    surv_route = {}
    if CFG["surv_reserve"] and hour >= CFG["surv_hour"] and day < last_day and CFG["dispatch"] != "route":
        # every tile whose asset dies / escapes tonight unless served: nearest-arrival greedy routes
        surv = []
        for idx in tasks:
            t_ = _tile(tiles, idx)
            if (CFG["surv_harvest"] and _is_plant(t_) and not CROPS[t_["crop"]]["ongoing"] and t_.get("yield_units", 0) > 0
                    and day - t_["planted_day"] >= CROPS[t_["crop"]]["maxday"]
                    and any(o[0] == "HARVEST" for o in tasks[idx][0])):
                surv.append((idx, "HARVEST"))   # a one-time crop past full yield starts decaying tomorrow morning
            elif _is_plant(t_) and not t_.get("watered_today") and t_.get("consecutive_unwatered", 0) >= 1:
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
    helper = {}
    if CFG["helper_split"] and free:
        # units the greedy left free (every open task held): join a held animal tile with >= 2 open ops and take its
        # last independent op (collect / harvest / care) if they get there before the owner could finish alone
        owners = {v: w for w, v in assign.items() if isinstance(v, int)}
        cand = []
        for idx, (ops, need, prio) in tasks.items():
            t_h = _tile(tiles, idx)
            if idx not in owners or len(ops) < 2:
                continue
            if _animal(t_h):
                if not any(o[0] in ("HARVEST", "COLLECT_FERTILIZER", "CARE") for o in ops):
                    continue
            elif not (CFG["helper_crops"] and _is_plant(t_h) and CROPS[t_h["crop"]]["ongoing"]
                      and any(o[0] == "HARVEST" for o in ops) and not any(o[0] in ("PLANT", "DIG") for o in ops)):
                continue
            tgt = (idx % 10, idx // 10)
            cand.append((idx, tgt, _dist(pos[owners[idx]], tgt) + len(ops)))
        for u in list(free):
            best = None
            for idx, tgt, fin in cand:
                if idx in helper.values():
                    continue
                arr = _dist(pos[u], tgt) + 1
                if arr >= fin or hour + arr > 23:
                    continue
                if best is None or arr < best[0]:
                    best = (arr, idx)
            if best is not None:
                helper[u] = best[1]
                free.remove(u)
        S["log"]["helper_steps"] += len(helper)

    assign0 = dict(assign)
    shed_left0 = Counter(shed_left)
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
        if u in helper:
            hidx = helper[u]
            htgt = (hidx % 10, hidx // 10)
            if p != htgt:
                actions[u] = _step_toward(p, htgt)
            else:
                hop = None
                for op in reversed(tasks[hidx][0]):
                    if op[0] in ("HARVEST", "COLLECT_FERTILIZER", "CARE"):
                        hop = op
                        break
                actions[u] = list(hop) if hop else ["PASS"]
            continue
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
    if step >= 718 and not S.get("abandon_logged"):
        S["abandon_logged"] = True
        for e in S.get("abandon", []):
            S["log"]["abandon_%s_%s" % (e.get("verdict"), e.get("kind"))] += 1
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
    if CFG["idle_trace"]:
        _sl_now = Counter(shed_left)
        shed_left.clear(); shed_left.update(shed_left0)      # judge the idle units as the dispatcher saw the shed
        try:
            _idle_trace(S, obs, me, tiles, day, hour, n, pos, invs, tasks, taken, assign0, actions, shed_left,
                        cost, usable_ops, surv_route)
        except Exception as exc:
            S["log"]["trace_error"] += 1
        shed_left.clear(); shed_left.update(_sl_now)
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


# ---- research: idle-pass / dropped-job trace (CFG idle_trace) -----------------------------

def _idle_trace(S, obs, me, tiles, day, hour, n, pos, invs, tasks, taken, assign0, actions, shed_left, cost, usable_ops,
                surv_route):
    """Buffer every PASS of the day with the open tasks and why that unit did not take each; at hour 23 value the
    jobs still open with a fresh sem_maintenance solve (minus what hour 23 itself does) and write one day record."""
    import json as _json
    import os as _os
    buf = S.setdefault("itr_buf", [])
    if S.get("itr_day") != day:
        S["itr_day"] = day
        buf.clear()
        S["itr_open"] = {}
    first_open = S["itr_open"]
    work = S.setdefault("itr_work", Counter())
    if hour == 0:
        work.clear()
    mjv = {}
    for idx_, jl_ in S.get("mj", {}).items():
        for j_ in jl_:
            if not j_.get("optional"):
                mjv[(idx_, j_["cmd"])] = float(j_.get("value", 0.0))
    for u in range(n):
        a = actions[u]
        c = a[0] if a else "PASS"
        if c in ("NORTH", "SOUTH", "EAST", "WEST"):
            work["move"] += 1
        elif c in ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER"):
            idx_ = pos[u][1] * 10 + pos[u][0]
            v_ = mjv.get((idx_, c))
            work["op_" + c] += 1
            work["opv_" + ("none" if v_ is None else "0" if v_ <= 0 else "lt30" if v_ < 30 else "lt100" if v_ < 100 else "ge100")] += 1
            work["opval"] += v_ or 0.0
        elif c in ("PICKUP", "DROP", "PLACE"):
            work["shed_" + c] += 1
        elif c == "PASS":
            work["pass"] += 1
        else:
            work["plan_" + c] += 1
    for idx, (ops, need, prio) in tasks.items():
        for o in ops:
            first_open.setdefault((idx, o[0]), hour)
    for u in range(n):
        if actions[u] != ["PASS"]:
            continue
        a0 = assign0.get(u)
        if a0 is not None and a0 != "D":
            t = _tile(tiles, a0)
            buf.append({"h": hour, "u": u, "kind": "tile_noop", "idx": a0, "pos": list(pos[u]),
                        "ops": [o[0] if len(o) == 1 else o[0] + ":" + str(o[1]) for o in tasks.get(a0, ([], 0, 0))[0]],
                        "inv": dict(invs[u]), "fed": bool(isinstance(t, dict) and t.get("fed_today"))})
            continue
        why = {}
        for idx, (ops, need, prio) in tasks.items():
            tgt = (idx % 10, idx // 10)
            if idx in taken:
                owner = [v for v, w in assign0.items() if w == idx]
                ow = owner[0] if owner else -1
                why[idx] = ("taken", _dist(pos[u], tgt), ow, _dist(pos[ow], tgt) if ow >= 0 else None)
                continue
            ok = usable_ops(u, ops, need)
            if not ok:
                lack = sorted(k for k, v in need.items() if invs[u].get(k, 0) < v and shed_left.get(k, 0) <= 0)
                why[idx] = ("lack:" + ",".join(lack), None, None, None)
                continue
            c = cost(u, idx)
            why[idx] = ("plant_late" if c is None else "valid", _dist(pos[u], tgt), None, None)
        buf.append({"h": hour, "u": u, "kind": "no_task" if a0 is None else "deliver", "pos": list(pos[u]),
                    "inv": dict(invs[u]), "why": why,
                    "open": {idx: [o[0] for o in ops] for idx, (ops, need, prio) in tasks.items()}})
    if hour != 23:
        return
    # dropped = fresh solve's (non-optional, value > 0) jobs still open at hour 23, minus the ops executed at hour 23
    done23 = set()
    for u in range(n):
        a = actions[u]
        if a and a[0] in ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER"):
            done23.add((pos[u][1] * 10 + pos[u][0], a[0]))
    try:
        jl = _sm()["maintenance_jobs"](obs, me, prices=None, fertilize=CFG["mj_fertilize"], include_optional=False,
                                      collect=CFG["mj_collect"])
    except Exception:
        jl = []
    dropped = []
    for j in jl:
        idx = j["tile"][1] * 10 + j["tile"][0]
        v = float(j.get("value", 0.0))
        if v <= 0 or (idx, j["cmd"]) in done23:
            continue
        t = _tile(tiles, idx)
        in_task = idx in tasks and any(o[0] == j["cmd"] for o in tasks[idx][0])
        passes = []
        for b in buf:
            if b["kind"] == "tile_noop":
                continue
            if idx in b["why"] and j["cmd"] in b["open"].get(idx, ()):
                passes.append([b["h"], b["u"]] + list(b["why"][idx]))
        dropped.append({"idx": idx, "cmd": j["cmd"], "value": round(v, 1), "kind": j.get("kind"),
                        "asset": j.get("asset"), "deadline": j.get("deadline"), "in_task": in_task,
                        "first_open": first_open.get((idx, j["cmd"])), "idle": passes,
                        "cu": (t.get("consecutive_unwatered") if _is_plant(t) else t.get("consecutive_unfed")
                               if isinstance(t, dict) else None)})
    plan_open = {idx: [o[0] for o in ops] for idx, (ops, need, prio) in tasks.items()
                 if any(o[0] in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE") for o in ops)}
    passes_kind = {}
    for b in buf:
        k = b["kind"] + ("" if b["kind"] != "tile_noop" else ":" + ",".join(b["ops"]))
        passes_kind.setdefault(k, [0, 0])
        passes_kind[k][0] += 1
        passes_kind[k][1] += 1 if b["h"] >= 18 else 0
    noop = [{k: b[k] for k in ("h", "u", "idx", "ops", "inv", "fed")} for b in buf if b["kind"] == "tile_noop"]
    idle_detail = []
    for b in buf:
        if b["kind"] == "tile_noop":
            continue
        cnt = {}
        for idx, (r, _d, _o, _od) in b["why"].items():
            cnt[r] = cnt.get(r, 0) + 1
        idle_detail.append([b["h"], b["u"], b["pos"], b["inv"], cnt, len(b["open"])])
    rec = {"day": day, "n": n, "work": dict(work), "dropped": dropped, "plan_open23": plan_open, "passes": passes_kind,
           "noop": noop, "idle": idle_detail, "mj_hour": S.get("mj_hour")}
    path = S.get("itr_path")
    if path is None:
        _os.makedirs(CFG["idle_trace"], exist_ok=True)
        path = _os.path.join(CFG["idle_trace"], "%d_%d_%d.jsonl" % (_os.getpid(), int(time.time() * 1000), me))
        S["itr_path"] = path
    with open(path, "a", encoding="utf-8") as f:
        f.write(_json.dumps(rec) + "\n")
    buf.clear()


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


# ===== BEGIN SEM_MARKET SELL BLOCK (2026-09-24; mgt_lead_deploy_sell only) =================================
# CFG["sell_source"] == "sem": the hold-and-batch rule of scripts/fragments/sem_market.py replaces the sell quota
# (sell-on-arrival / leader cumulative units). The rest of _market (hire funding, shed-overflow guard, buys, order
# assembly) is unchanged. Wheat keeps the deploy's herd reserve (its cum_sold quota), fertilizer the executor's
# pending-fertilize reserve. Merge = copy this block + the two-line call site marked SEM_MARKET CALL SITE in _market.
_SMKNS = None
SEM_MARKET_PARAMS = None                 # research override: {"W":.., "P": {product: {...}}}; env SEM_MARKET_JSON
try:
    import os as _smk_os0
    import json as _smk_json0
    if _smk_os0.environ.get("SEM_MARKET_JSON"):
        SEM_MARKET_PARAMS = _smk_json0.loads(_smk_os0.environ["SEM_MARKET_JSON"])
except Exception:
    SEM_MARKET_PARAMS = None


def _smk():
    """scripts/fragments/sem_market.py (stdlib-only; pasted into the single-file agent later)."""
    global _SMKNS
    if _SMKNS is None:
        import os
        here = globals().get("__file__")          # undefined under Kaggle's loader (exec of the source)
        cands = [os.path.join(os.path.dirname(os.path.abspath(here)), "..", "scripts", "fragments", "sem_market.py")] if here else []
        cands.append(os.path.join(os.getcwd(), "scripts", "fragments", "sem_market.py"))
        path = next((c for c in cands if os.path.isfile(c)), cands[-1])
        ns = {}
        with open(path, encoding="utf-8") as fh:
            exec(compile(fh.read(), "sem_market", "exec"), ns)
        _SMKNS = ns
    return _SMKNS


def _smk_sells(S, obs, T, d, shed, reserve, endgame):
    res = Counter() if endgame else Counter(reserve)
    if not endgame:
        # wheat: the deploy's quota keeps what the herd eats (cum_sold = sold + shed - keep)
        w_have = shed.get("WHEAT", 0) - res.get("WHEAT", 0)
        w_ok = max(0, min(w_have, T.cum_sold[d].get("WHEAT", 0) - S["sold"]["WHEAT"]))
        res["WHEAT"] = shed.get("WHEAT", 0) - w_ok
    me = int(_g(obs, "player", 0))
    return _smk()["sell_orders"](obs, me, dict(shed), dict(res), S.setdefault("smk", {}), SEM_MARKET_PARAMS,
                                 sold_total=dict(S["sold"]))


def _smk_wheat_buys(obs, day, shed, carried, reserve, farm, cash, sells, buys):
    """wheat buy-ahead (sem_market.wheat_buy) with the cash left after this step's other purchases."""
    tiles = farm["tiles"]
    nofeed = _DEP.get("nofeed", ()) if isinstance(globals().get("_DEP"), dict) else ()
    n_fed = sum(1 for row in tiles for t in row if _animal(t))
    n_fed -= sum(1 for idx in nofeed if _animal(_tile(tiles, idx)))
    n_fed += sum(int(shed.get(sp, 0)) for sp in ANIMALS)            # bought, not yet placed
    in_shed = sum(int(v) for v in shed.values())
    in_shed -= sum(o[2] for o in sells if o[0] == "SELL")
    in_shed += sum(o[2] for o in buys if o[0] in ("BUY_PRODUCT", "BUY_ANIMAL"))
    room = 100 - in_shed
    stock_w = int(shed.get("WHEAT", 0)) + int(carried.get("WHEAT", 0)) + sum(o[2] for o in buys if o[:2] == ["BUY_PRODUCT", "WHEAT"])
    w = _smk()
    room = min(room, int(((SEM_MARKET_PARAMS or {}).get("wheat") or {}).get("room_total", w["SMK_WHEAT"]["room_total"])) - in_shed)
    k = w["wheat_buy"](obs, int(_g(obs, "player", 0)), stock_w, reserve.get("WHEAT", 0), max(0, n_fed), max(0, room),
                       cash, None, SEM_MARKET_PARAMS)
    return [["BUY_PRODUCT", "WHEAT", int(k)]] if k > 0 else []
# ===== END SEM_MARKET SELL BLOCK ===========================================================================


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
    if CFG["sell_source"] == "sem":      # SEM_MARKET CALL SITE (see the SEM_MARKET SELL BLOCK above _market)
        sells = _smk_sells(S, obs, T, d, shed, reserve, endgame)
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
    if CFG["sell_source"] == "sem" and not endgame:   # SEM_MARKET CALL SITE 2 (wheat buy-ahead, lowest priority)
        buys = buys + _smk_wheat_buys(obs, day, shed, carried, reserve, farm, cash, sells, buys)
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
    "last_plant": {"STRAWBERRY": 13, "TOMATO": 18, "MELON": 19, "WHEAT": 25, "CARROT": 26},   # last full-harvest planting days (min_maintenance), 2026-09-25
    "last_animal": {"SHEEP": 17, "COW": 18, "GOOSE": 20},
    "hands_coef": (6.186, 0.040, 0.123),  # hands ~ b0 + b1*crop tiles + b2*animal tiles (corpus days 12-28)
    "nofeed_from": 99,                  # no-feed hook off (plan-volume c1, 2026-09-25: the executor's maintenance module already stops end-of-life animals; the hook starved producing ones: +4.8k/world p2750, +0.024 G1)
    "wheat_margin": 10,
    "wheat_keep_days": 99,              # hold the wheat the herd eats to the end (2 days: -3.1k own cash on 12 worlds)
    "max_new_per_crop": 12,
    "switch_days": (3, 6, 9),
    "hands_add": 1,                     # extra hands on top of the regression, composition days (+2.0k/+3.1k margin on 12 worlds)
    "pred_mult": {"ME": 3.0},           # label -> multiplier on the count model's prediction; melons x3 (2026-09-25: melon is the highest-value crop per tile-day, full panel +315 vs cutoffs)
    "co_fix": False,                    # 'co' = cow OR empty coop in the corpus labels: compare with our cows + empty coops
    "land_max": 2,                      # quadrants we buy: never the $4000 SE one (12 worlds: +5.6k margin; 1 quadrant +1.3k)
    "cm_file": "count_model_540.json",  # count model: clean 540-game refit (2026-09-25; the 600-game fit included 60 quarantined scripted Boey games; count_model.json = the 240-game fit)
    "hands_add_early": 1,               # extra hand on the days before compose_from (c1)
    "fill_free": 0,                     # late-season fill: plant wheat / carrots on free tiles beyond fill_keep_empty (0 = off)
    "fill_keep_empty": 4,
    "fill_max": 10,                     # at most this many fill plantings a day
    "fill_last": {"WHEAT": 25, "CARROT": 26},   # last planting day with a full harvest (sem_maintenance / min_maintenance)
    "fill_carrot_base": 0.2,            # carrot share of the fill ...
    "fill_carrot_per_shop": 0.15,       # ... + this per visible carrot-demanding shop instance (Pet Cafe counts 2), max 0.6
    "replant_same_day": 1,              # a wheat / carrot tile harvested during the day is replanted the same day (rpc1, 2026-09-25: full panel +1,222 vs sem)
    "replant_from": 12,                 # ... from this day (12 = the count-model phase only)
    "replant_unmet": 0,                 # a harvested wheat / carrot tile first takes the highest-value crop whose count target went unmet today (no free tile)
    "replant_cap": 1.0,                 # ... but no wheat replant once wheat tiles reach cap x the count model's wheat target (0 = no cap)
    "wc_swap": 0,                       # composition: turn this base share of the count model's wheat plantings into carrots ...
    "wc_swap_per_shop": 0.15,           # ... + this per carrot-demanding shop instance (max 0.7), when carrots can still be harvested
}
DEP_CFG.update({})   # variant dep6
DEP_CFG.update({'land_max': 3})   # variant q4
try:                                    # research overrides (ablations): DEP_CFG_JSON='{"key": value}'
    import os as _dep_os0
    import json as _dep_json0
    DEP_CFG.update(_dep_json0.loads(_dep_os0.environ.get("DEP_CFG_JSON") or "{}"))
except Exception:
    pass


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

with open(_dep_os.path.join(_DEP_SEM_DIR, DEP_CFG.get("cm_file", "count_model.json"))) as _dep_fh:
    _DEP_CM = _dep_json.load(_dep_fh)
_DEP_LABELS = tuple(_DEP_CM["meta"]["labels"])
_DEP_DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
               'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
               'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
               'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
               'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
_DEP_CM_PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
_DEP_EXEMPLAR = 112655730           # family A exemplar (openings.json), DSM
_DEP_EXEMPLAR_TEAM = DEP_CFG.get("exemplar_team", "16732748")   # DSM's own seat of that game (it exists under both teams)
_DEP_SEM_CACHE = {}
_DEP_ANIMAL_LABEL = {"SHEEP": "sh", "COW": "co", "GOOSE": "go"}


def _dep_sem_path(ep, team=None):
    if team is not None:
        p = _dep_os.path.join(_DEP_SEM_DIR, str(team), "%s.json.gz" % ep)
        if _dep_os.path.isfile(p):
            return p
    # sorted: glob order is filesystem-dependent and 48 corpus episodes exist under two teams (leaders who met)
    hits = sorted(_dep_glob.glob(_dep_os.path.join(_DEP_SEM_DIR, "*", "%s.json.gz" % ep)))
    return hits[0] if hits else None


def _dep_load_sem(ep, team=None):
    key = (int(ep), None if team is None else str(team))
    if key not in _DEP_SEM_CACHE:
        with _dep_gzip.open(_dep_sem_path(int(ep), team), "rt", encoding="utf-8") as fh:
            _DEP_SEM_CACHE[key] = _dep_json.load(fh)
    return _DEP_SEM_CACHE[key]


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
    """-> (team_id, episode) of the leader game to follow (team-aware: a met pair of leaders shares an episode id)."""
    res = _dep_lpr.retrieve(shops, labels, day, k=k, lam=DEP_CFG["lam"])
    if not res:
        return None
    if len(res) == 1:
        return (str(res[0][0]), res[0][1])
    corpus = {(str(g["team_id"]), g["episode"]): g for g in _dep_lpr.load_corpus()}
    dd = min(29, day + 3)
    best = None
    for tm, ep, _w in res:
        b = corpus[(str(tm), ep)]["boards"][dd]
        cost = sum(w2 * _dep_lpr.hamming(b, corpus[(str(tm2), ep2)]["boards"][dd]) for tm2, ep2, w2 in res)
        if best is None or cost < best[0]:
            best = (cost, (str(tm), ep))
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
    _DEP["wh_pred"] = (d, pred_s.get("WH", 0.0))
    pred_l = _dep_predict(shops, counts, d, DEP_CFG["h_long"])
    for lab_, mult_ in DEP_CFG["pred_mult"].items():
        pred_s[lab_] = pred_s.get(lab_, 0) * mult_
        pred_l[lab_] = pred_l.get(lab_, 0) * mult_
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
        if len(free) < need:
            _DEP.setdefault("unmet", {})[crop] = (d, need - len(free))
            log["unmet_" + crop] += need - len(free)
            if S is not None:
                S["log"]["unmet_" + crop] += need - len(free)     # visible in the G1 harness's agent_log
        k_swap = 0
        if crop == "WHEAT" and DEP_CFG["wc_swap"] and d <= DEP_CFG["last_plant"]["CARROT"]:
            car_dem = sum(_DEP_DEMAND.get(sh, {}).get("CARROT", 0) for sh in shops)
            share = min(0.7, DEP_CFG["wc_swap"] + DEP_CFG["wc_swap_per_shop"] * car_dem)
            k_swap = int(round(need * share))
        for i_, idx in enumerate(free[:need]):
            crop_i = "CARROT" if i_ < k_swap else crop
            T.events.append((d, idx, crop_i))
            T.plant[d][idx] = crop_i
            reserved.add(idx)
            for dd in range(d, min(T.n, d + CFG["late"].get(crop_i, LATE[crop_i]) + 1)):
                T.board[dd][idx] = CROP_LABEL[crop_i]
            log["plant_" + crop_i] += 1
    # late-season fill: the count model's wheat / carrot targets fall off late, leaving free tiles idle
    if DEP_CFG["fill_free"] and d <= max(DEP_CFG["fill_last"].values()):
        free = _dep_free_tiles(tiles, reserved, None, None)
        n_fill = min(DEP_CFG["fill_max"], max(0, len(free) - DEP_CFG["fill_keep_empty"]))
        car_dem = sum(_DEP_DEMAND.get(sh, {}).get("CARROT", 0) for sh in shops)
        share = min(0.6, DEP_CFG["fill_carrot_base"] + DEP_CFG["fill_carrot_per_shop"] * car_dem)
        k_car = int(round(n_fill * share)) if d <= DEP_CFG["fill_last"]["CARROT"] else 0
        for i, idx in enumerate(free[:n_fill]):
            crop = "CARROT" if i < k_car else "WHEAT"
            if d > DEP_CFG["fill_last"][crop]:
                continue
            T.events.append((d, idx, crop))
            T.plant[d][idx] = crop
            reserved.add(idx)
            for dd in range(d, min(T.n, d + CFG["late"].get(crop, LATE[crop]) + 1)):
                T.board[dd][idx] = CROP_LABEL[crop]
            log["fill_" + crop] += 1
    # animals
    ns = _DEP.setdefault("new_struct", {})
    na = _DEP.setdefault("new_anim", {})
    for sp in ("SHEEP", "COW", "GOOSE"):
        if d > DEP_CFG["last_animal"][sp] or sp in starving:
            continue
        lab = _DEP_ANIMAL_LABEL[sp]
        have = sum(1 for v in anim.values() if v == sp)
        if sp == "COW" and DEP_CFG["co_fix"]:
            have += sum(1 for idx, k in struct.items() if k == "COOP" and idx not in anim)
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
    T.hands[d] = max(0, min(14, int(b0 + b1 * crops + b2 * len(anim) + 0.5) + DEP_CFG["hands_add"]))


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
    keep = n_fed * min(DEP_CFG["wheat_keep_days"], max(0, 28 - day)) + DEP_CFG["wheat_margin"]
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
        _DEP_BASE = Target(_dep_load_sem(_DEP_EXEMPLAR, _DEP_EXEMPLAR_TEAM))
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
    if day in DEP_CFG["switch_days"] and day not in _DEP["switched"] and day < DEP_CFG["compose_from"]:
        shops = _dep_shops(obs)
        if len(shops) >= day // 3 or hour >= 2:
            _DEP["switched"].add(day)
            k = DEP_CFG["k_day3"] if day == 3 else DEP_CFG["k_late"]
            pick = _dep_retrieve(day, shops, _dep_labels(tiles), k)
            ep = None if pick is None else pick[1]
            if ep is not None:
                t2 = Target(_dep_load_sem(ep, pick[0]))
                _dep_switch(T, t2, day, tiles)
                _DEP["lead_t"] = t2
                _DEP["picks"].append((day, int(ep)))
                _MGT_HISTORY.append((day, int(ep)))
    if day >= DEP_CFG["compose_from"] and day not in _DEP["composed"]:
        _DEP["composed"].add(day)
        _dep_compose(obs, day)
        _DEP["nofeed"] = _dep_nofeed(obs, day)
    for i in range(DEP_CFG["land_max"], 3):
        T.land_day[LAND_ORDER[i]] = 99
    if DEP_CFG["replant_same_day"] and day >= DEP_CFG["replant_from"]:
        if hour == 0 or _DEP.get("ds_day") != day:
            _DEP["ds_day"] = day
            _DEP["ds_crops"] = {i: _tile(tiles, i)["crop"] for i in range(100)
                                if _is_plant(_tile(tiles, i)) and _tile(tiles, i)["crop"] in ("WHEAT", "CARROT")}
        else:
            capped = False
            if DEP_CFG["replant_cap"] and _DEP.get("wh_pred", (None,))[0] == day:
                n_wh = sum(1 for j in range(100) if _is_plant(_tile(tiles, j)) and _tile(tiles, j)["crop"] == "WHEAT")
                n_wh += sum(1 for j, c in T.plant[day].items() if c == "WHEAT" and _tile(tiles, j) is None)
                capped = n_wh >= DEP_CFG["replant_cap"] * _DEP["wh_pred"][1]
            for i, crop in _DEP["ds_crops"].items():
                if DEP_CFG["replant_unmet"] and _tile(tiles, i) is None and i not in T.plant[day]:
                    um = _DEP.get("unmet", {})
                    alt = None
                    for c2 in ("STRAWBERRY", "MELON", "TOMATO", "CARROT"):
                        dd_, k_ = um.get(c2, (None, 0))
                        if dd_ == day and k_ > 0 and day <= DEP_CFG["last_plant"][c2]:
                            alt = c2
                            break
                    if alt is not None:
                        um[alt] = (day, um[alt][1] - 1)
                        T.events.append((day, i, alt))
                        T.plant[day][i] = alt
                        for dd in range(day, min(T.n, day + CFG["late"].get(alt, LATE[alt]) + 1)):
                            T.board[dd][i] = CROP_LABEL[alt]
                        _DEP["log"]["replant_unmet_" + alt] += 1
                        if _S is not None:
                            _S["log"]["replant_unmet_" + alt] += 1
                        continue
                if crop == "WHEAT" and capped:
                    continue
                if _tile(tiles, i) is None and i not in T.plant[day] and day <= DEP_CFG["last_plant"][crop]:
                    T.events.append((day, i, crop))
                    T.plant[day][i] = crop
                    for dd in range(day, min(T.n, day + CFG["late"].get(crop, LATE[crop]) + 1)):
                        T.board[dd][i] = CROP_LABEL[crop]
                    _DEP["log"]["replant_" + crop] += 1
    if DEP_CFG["hands_add_early"] and day < DEP_CFG["compose_from"] and ("he", day) not in _DEP:
        _DEP[("he", day)] = True
        T.hands[day] = min(14, T.hands[day] + DEP_CFG["hands_add_early"])
    _dep_sell_quota(obs, day)


_DEP_TRACE_PATH = _dep_os.environ.get("DEP_TRACE")     # research only: per-day state dump


def _dep_trace(obs, day, hour, step):
    me = int(_g(obs, "player", 0))
    farm = _g(obs, "farms")[me]
    tr = _DEP.setdefault("trace", [])
    lt = _DEP.get("lead_t")
    tr.append({"day": day, "money": farm["money"], "hands": len(farm["hands"]), "target_hands": _T.hands[min(day, 29)],
               "counts": dict(Counter(_dep_labels(farm["tiles"]))),
               "lead_counts": dict(Counter(lt.board[min(day, 29)])) if lt is not None else None,
               "lead_cash": lt.cash[min(day, 29)] if lt is not None else None,
               "shed": dict(_g(_g(obs, "private", {}), "shed", {})), "log": dict(_DEP["log"]),
               "exec_log": dict(_S["log"]) if _S else {}})
    if step >= 718:
        with open(_DEP_TRACE_PATH, "w") as fh:
            _dep_json.dump(tr, fh)


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
    if _DEP_TRACE_PATH and (hour == 0 or step >= 718):
        _dep_trace(obs, day, hour, step)
    if hour == 23 or step >= 718:
        _MGT_REPORT.update({k: v for k, v in _DEP["log"].items()})
        _MGT_REPORT.update(errors=_DEP["errors"], tmax=round(_DEP["tmax"], 4), n_nofeed=len(_DEP.get("nofeed", ())),
                           exec_tmax=round(_S["tmax"], 4) if _S else 0)
    return out

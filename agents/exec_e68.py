"""E68 - the days 6-8 executor (user 2026-09-30: "for days 6-8 and 9-11 we need separate executor. For 6 we plan in all
money generating goods to be brought back immediately then do other work"; "DSM plans for bringing in - selling -
buying seeds - go out - plant. We are not modeling this.").

It replaces KB115LT2 on the configured days and plays the tiler's day plan (TilePlanView: plant[d], animals_by_day[d],
struct_by_day[d], land_day, hands[d]) as ROUTES with an explicit cash chain (v5):
  1. money runs first (money_goods of the day; day 6 = everything, user rule): each unit in turn takes the pen with the
     best value per hour of its round trip, chains a further pen on the way home when its load is small, and drops at a
     shed tile - sold in that tick (market orders run after unit actions; SELLs come before buys, so the proceeds fund
     that tick's purchases);
  2. the land at the first tick the money (cash + shed stock + the money-run drops) covers it;
  3. every other job by cheapest insertion into the units' routes (after their money runs), in priority order:
     keep-alive jobs, plan jobs (plantings / placements in ROI order: cheap seeds, dearer seeds, cows, geese, sheep;
     builds; valuable yield-window waterings), then production jobs (feed + care rounds, cheap waterings, harvests) by
     value density. A route is simulated engine-exactly: walking, pickups at a shed tile (animals, feed wheat: shared
     pickups merged; carried goods are dropped - and sold - at every shed stop), ops, and waits for the land or for
     cash. Every purchase (seed / animal / feed wheat) is made at the latest tick before its use that the day's cash
     timeline can fund; a job that cannot be funded or finished today is left for the next plan.
Re-planned every hour: each unit keeps its previous job sequence (stops regenerated, the first stop kept first), jobs
that no longer fit and new jobs are re-inserted. Engine-exact (kaggriculture 1.32.7): one step or one op an hour, a
seedling dies unless watered on its planting day, all PLANTs of a crop fail in a tick that asks for more than the seed
stock, hires spawn on the least-occupied shed tile (after the unit actions of the hour) and act from the next hour.
"""
import math
from collections import Counter

# ---- engine constants (kaggriculture 1.32.7) ----
CROPS = {
    "WHEAT": {"seed": 10, "first": 2, "maxd": 4, "max": 6, "ongoing": False},
    "CARROT": {"seed": 20, "first": 2, "maxd": 3, "max": 4, "ongoing": False},
    "TOMATO": {"seed": 50, "first": 8, "maxd": 8, "max": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "maxd": 10, "max": 4, "ongoing": True},
    "MELON": {"seed": 80, "first": 10, "maxd": 12, "max": 6, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP", "first": 4, "interval": 1, "product": "EGG"},
    "COW": {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "product": "WOOL"},
}
MARKET = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20), "CARROT": (35, 450, "hinge", 1.00, "sqrt", 0.70),
    "TOMATO": (60, 200, "hinge", 0.40, "sqrt", 0.60), "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60), "EGG": (50, 332, "hinge", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60), "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}
I0 = 10000
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
LAND_ORDER = ("NE", "SW", "SE")
LAND_PRICES = (1000, 2000, 4000)
DIRS = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
SELLABLE = ("WOOL", "MILK", "EGG", "FERTILIZER", "STRAWBERRY", "MELON", "TOMATO", "CARROT")
MONEY_GOODS = ("WOOL", "MILK", "EGG", "FERTILIZER")
MOVES = ("NORTH", "SOUTH", "EAST", "WEST", "PASS")

DEFAULTS = {
    "days": [6, 7, 8],
    "money_first": 1,          # money runs before any other work (user rule for day 6) ...
    "bringback_days": [6, 8],     # user ruling: each worker's hour-0 bring-back fixed and followed as is, the day planned
                               # after it (other days: the day's money jobs inserted first, each with its drop)
    "money_goods": {"6": ["WOOL", "MILK", "EGG", "FERTILIZER"], "7": ["WOOL", "MILK", "EGG"],
                    "8": ["WOOL", "MILK", "EGG", "FERTILIZER"]},   # ... for these goods on each day; other goods are
                               # collected during the pen's feed / care visit and sold at the unit's next shed stop
    "money_fert_dist": {"6": 2, "8": 2},   # fertilizer is a money run only from pens this close to a shed tile; farther pens
                               # are collected on the feed / care visit and sold at the unit's next shed stop
    "feed_buy": {"6": "all", "7": "all", "8": "all"},   # wheat bought for keep-alive feeds only ("keep") or all feeds
    "chain_detour": 1,         # a money run takes a further pen when that adds <= this many walking hours ...
    "chain_max_value": 300.0,  # ... and the load carried is worth less than this (produce goes straight home)
    "v_plan": 400.0,           # plantings / placements
    "v_build": 200.0,          # a structure the plan builds ahead of its animal
    "v_keep": 1000.0,          # keep-alive water / feed
    "window_promote": 150.0,   # yield-window waterings worth at least this join the plan tier (melons)
    "fund_order": ["WHEAT", "CARROT", "STRAWBERRY", "MELON", "TOMATO", "COW", "GOOSE", "SHEEP"],
    "feed_batch": {"6": 6, "7": 3, "8": 3},   # most pens fed per wheat pickup (a new pickup drops - sells - the
                               # fertilizer collected so far)
    "carry_days": 2,           # missed plantings of the last days are planted when the plan still keeps them
    "feed_horizon": {"6": 2, "7": 99, "8": 99},   # feed + care required for animals producing within this many days
                               # (DSM day 6: the two oldest cows and the sheep; days 7-8: every animal)
    "feed_tier": 2,            # feed + care is production (user ruling: required): tier 2 with the plan jobs (3 = optional)
    "feed_new": 0,             # feed animals placed today
    "care": 1,                 # CARE with every FEED
    "window_water": 1,         # yield-window waterings of one-time crops
    "harvest_crops": 1,        # ripe one-time crops
    "farmer_h0": 1,            # the farmer works from hour 0 (hire spawns predicted after his move)
    "hire_first_h0": 1,        # hires before SELL orders at hour 0
    "keep_wheat": 1,           # never sell wheat (feed)
    "wheat_buy_pad": 1.0,      # price pad per unit of feed wheat bought
    "wait_penalty": 2.0,       # insertion cost per added waiting hour (on top of the added route hours)
    "cash_free_first": 0,      # 1 = cash-free jobs (waterings, care, harvests, builds) inserted before the purchase-bound
                               # plan jobs, which then fall where the money is (plan jobs may evict them when short of time)
    "fix_first": 1,            # 1 = a unit's first planned stop stays first at the hourly re-plan (0: waits can be filled)
    "polish_h0": 0,            # local-search evaluations at the hour-0 plan (0 = off)
    "polish_hour": 0,          # ... at every later hour
    "polish_reach": 3,
    "polish_obj": "end",       # "end" = sum of route end hours; "finish" = sum of every job's finish hour (load balance)         # a job moves next to stops of another route within this distance (or to its end)
    "cash_myopic": 0,          # 1 = a purchase fits the cash with the income, the land and the purchases up to its tick
                               # (later planned purchases re-checked at their own time); 0 = every planned purchase reserved
    "ec_weight": 0.0,          # insertion cost + this x the job's finish hour: spreads work to the unit that finishes it
                               # soonest (load balance) instead of chaining it onto the cheapest route
    "roles": 0,                # 1 = hour-0 role planner (planters / builders / pen servicers / waterers, swept chunks)
    "role_order": ["plant", "build", "pen", "water"],
    "crew_slack": 1.25,        # roles 2: the afternoon crew is sized for this x the block's work in the hours left   # chunk assignment and cash priority order of the roles
    "land_after_bb": {},       # {"8": 1}: that day the land waits for the bring-back's last drop (DSM buys it after the
                               # second milk; early land locks the morning cash away from feed wheat / seeds / geese)
    "warm_priority": 0,        # 1 = the hourly re-plan gives the cash to purchases by plan priority (seeds before animals
                               # before optional wheat), not by purchase tick (user: seed first, then the rest)
    "stock_fifo": 0,           # 1 = a stock unit (seed, shed wheat, bought animal) goes to the earliest take across routes
                               # (0 = to the route evaluated first, for the whole day)
    "order_cap": 0,            # 1 = purchases only where the tick's 10 market-order slots (hires, sells, land) leave room
    "pen_by": {},              # {"8": 11}: that day's feed / care jobs go in to finish by that hour when they can
    "pen_first": {},           # {"8": 1}: that day's feed / care jobs are inserted before the keep-alive tier
    "pen_rounds": {},          # {"8": 3}: hour-0 morning pen rounds of this many pens (pickup, pens, drop; roles 2)
    "prebuy_wheat": {},        # {"7": 8}: at hour 23 of that day buy wheat for the next morning up to this stock
    "warm_dedup": 0,           # 1 = the warm start keeps a job in one route only (no cross-unit tile substitutes)
    "playbook": None,          # path of a playbook (pb_extract.py): the day's hands follow its routes (no planner)
    "pb_cash_wait": 2,         # playbook: ticks a purchase may wait for cash before the route's last planting is cut
    "pb_lock_wait": 10,        # playbook: ticks a hand may wait on a locked tile before it skips that visit
    "pb_dsm_order": 0,         # playbook: hands served (cash, shed stock) in the order of DSM's visit hours, not by index
    "pb_wheat_ahead": 0,       # playbook: buy a wheat pickup's shortfall one tick before the hand reaches the shed
    "pb_drop_cash": 0,         # playbook: this tick's drops count in the tick's purchase budget (sold in the same market)
    "pb_place_check": 0,       # playbook: an animal pickup only for a following placement whose tile is still free
    "playbook_lib": None,      # path of a playbook library (games by shops / day-5 board); the game is picked at the
                               # first playbook day and followed on the others
    "pb_exclude_env": "MGT_EXCLUDE",   # environment variable naming an episode the library may not use (test worlds)
    "pb_place_free": 0,        # playbook (with pb_place_check): an animal already in the shed is picked up without the check
    "pb_daily_select": 0,      # playbook library: re-pick the game every morning (shops so far, previous dusk board)
    "pb_orphans": 0,           # playbook: routes of hands the day's hires did not deliver merge into the other hands
    "pb_keepalive_hour": None, # playbook: from this hour a crop dying tonight without water goes to the nearest hand
    "pb_no_late_plant": 0,     # playbook: no PLANT at hour 23 (its planting-day water cannot follow)
    "pb_multi_place": 0,       # playbook (with pb_place_check): a pickup of n animals serves its next n placements
    "pb_prefer_cash": 0,       # playbook library: among equal matches prefer the game where DSM ended with more cash
    "keep_by": 20,             # a keep-alive job is inserted only where it is finished by this hour (slack for delays)
    "evict": 1,                # a keep-alive / plan job that fits nowhere may evict production jobs (lowest value first)
    "evict_max": 4,            # most production jobs removed from one route for it
    "max_positions": 8,        # insertion points tried per route (cheapest detours + the end); 0 = all
    "log_plans": 0,            # keep the hour-0 per-unit plan in the diagnostics
    "log_hours": 0,            # keep each hour's actions / open jobs / reasons
}


def _shape(func, x, T):
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return math.sqrt(x)
    if func == "log":
        return math.log(1.0 + x)
    if func == "hinge":
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    return x


def price(item, inv):
    base, T, bf, bt, af, at = MARKET[item]
    if inv < I0:
        p = base + bt * base / _shape(bf, T, T) * _shape(bf, I0 - inv, T)
    else:
        p = base - at * base / _shape(af, T, T) * _shape(af, inv - I0, T)
    return max(1, int(round(p)))


def sale_value(item, n, inv):
    return float(sum(price(item, inv + k) for k in range(int(n))))


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def near_shed(p):
    return min(SHED, key=lambda s: (dist(p, s), SHED.index(s)))


def step_toward(p, q):
    """x first, then y"""
    if p[0] != q[0]:
        return "EAST" if q[0] > p[0] else "WEST"
    if p[1] != q[1]:
        return "SOUTH" if q[1] > p[1] else "NORTH"
    return None


def moved(p, mv):
    d = DIRS[mv]
    return (p[0] + d[0], p[1] + d[1])


def spawn_tile(positions):
    """engine _spawn_hand: least-occupied shed tile, NWSE order on ties"""
    occ = {s: 0 for s in SHED}
    for p in positions:
        if tuple(p) in occ:
            occ[tuple(p)] += 1
    return min(SHED, key=lambda s: (occ[s], SHED.index(s)))


class Cash:
    """projected cash after each tick's market (ticks h..23); delta = every event, soft = the planned purchases among them.
    myopic: a purchase at t must fit every hard event (income, land) and the soft purchases up to t only"""

    def __init__(self, money, h, myopic=False):
        self.h = h
        self.base = float(money)
        self.delta = [0.0] * 25
        self.soft = [0.0] * 25
        self.myopic = myopic

    def copy(self):
        c = Cash(self.base, self.h, self.myopic)
        c.delta, c.soft = list(self.delta), list(self.soft)
        return c

    def at(self, t):
        return self.base + sum(self.delta[self.h:t + 1])

    def add(self, t, v, soft=False):
        if t <= 24:
            self.delta[max(t, self.h)] += v
            if soft:
                self.soft[max(t, self.h)] += v

    def ok(self, t, cost):
        if not self.myopic:
            run = self.base + sum(self.delta[self.h:t])
            for k in range(t, 24):
                run += self.delta[k]
                if run - cost < -1e-6:
                    return False
            return True
        run = self.base + sum(self.delta[self.h:t + 1])
        if run - cost < -1e-6:
            return False
        for k in range(t + 1, 24):
            run += self.delta[k] - self.soft[k]
            if run - cost < -1e-6:
                return False
        return True

    def earliest(self, t0, cost):
        for t in range(max(t0, self.h), 24):
            if self.ok(t, cost):
                return t
        return None


class Job:
    __slots__ = ("key", "kind", "tile", "pre", "ops", "cls", "value", "crop", "animal", "mand", "locked", "goods", "extra")

    def __init__(self, key, kind, tile, ops, cls, value, pre=(), crop=None, animal=None, mand=False, locked=False,
                 goods=None, extra=None):
        self.key, self.kind, self.tile, self.ops, self.cls, self.value = key, kind, tile, list(ops), cls, value
        self.pre, self.crop, self.animal, self.mand, self.locked = list(pre), crop, animal, mand, locked
        self.goods = goods or {}
        self.extra = extra or {}


class Unit:
    __slots__ = ("idx", "pos", "t", "inv", "steps", "jobs", "done")

    def __init__(self, idx, pos, t, inv):
        self.idx, self.pos, self.t, self.inv = idx, tuple(pos), t, Counter(inv)
        self.steps, self.jobs, self.done = [], [], False


# ------------------------------------------------------------------------------------------------ job catalogue
def _animal_produces(t, day):
    a = ANIMALS[t["animal"]]
    ds = day + 1 - int(t.get("placed_day", day)) - a["first"]
    return ds >= 0 and ds % a["interval"] == 0


def _next_production(t, day):
    """the day whose night refresh brings the animal's next production"""
    a = ANIMALS[t["animal"]]
    for d in range(day, day + 12):
        ds = d + 1 - int(t.get("placed_day", d)) - a["first"]
        if ds >= 0 and ds % a["interval"] == 0:
            return d
    return day + 99


def _plan_field(plan, name, day):
    try:
        return {int(k): v for k, v in (getattr(plan, name)[day] or {}).items()}
    except Exception:
        return {}


def derive_jobs(obs, plan, day, cfg):
    me = int(obs.get("player", 0))
    farm = obs["farms"][me]
    tiles = farm["tiles"]
    prices = (obs.get("market") or {}).get("prices") or {}
    keep_animals = _plan_field(plan, "animals_by_day", day)
    plant_today = _plan_field(plan, "plant", day)
    # missed plantings of the last days, while the plan still keeps that crop on the tile (its board of today)
    try:
        board_today = list(plan.board[day])
    except Exception:
        board_today = None
    lab = {"WHEAT": "WH", "CARROT": "CA", "TOMATO": "TO", "STRAWBERRY": "ST", "MELON": "ME"}
    for d0 in range(max(0, day - int(cfg["carry_days"])), day):
        for idx, crop in _plan_field(plan, "plant", d0).items():
            if idx in plant_today or board_today is None or board_today[idx] != lab.get(crop):
                continue
            t0 = farm["tiles"][idx // 10][idx % 10]
            if isinstance(t0, dict) and t0.get("kind") == "PLANT" and t0.get("crop") == crop:
                continue                                   # planted (on that day or later)
            if isinstance(t0, dict) and t0.get("animal"):
                continue
            plant_today[idx] = crop
    struct_today = _plan_field(plan, "struct_by_day", day)
    mg = set((cfg["money_goods"] or {}).get(str(day), MONEY_GOODS)) if cfg["money_first"] else set()
    fbuy = (cfg["feed_buy"] or {}).get(str(day), "all")
    jobs = {}
    wheat_stock = int(((obs.get("private") or {}).get("shed") or {}).get("WHEAT", 0) or 0) \
        + sum(int((i or {}).get("WHEAT", 0) or 0) for i in ((obs.get("private") or {}).get("inventories") or []))
    for y in range(10):
        for x in range(10):
            t = tiles[y][x]
            idx = y * 10 + x
            if not isinstance(t, dict):
                continue
            if t.get("animal"):
                sp = t["animal"]
                prod = ANIMALS[sp]["product"]
                pv = float(prices.get(prod, 0) or 0)
                yu = int(t.get("yield_units", 0) or 0)
                service = []                               # pen ops not taken as money runs (done on the pen visit)
                if yu > 0:
                    if prod in mg:
                        jobs["MH%d" % idx] = Job("MH%d" % idx, "money", (x, y), ["HARVEST"], 0, yu * pv, goods={prod: yu})
                    else:
                        service.append("HARVEST")
                if t.get("fertilizer_available"):
                    fd = (cfg["money_fert_dist"] or {}).get(str(day), 99)
                    if "FERTILIZER" in mg and dist(near_shed((x, y)), (x, y)) <= int(fd):
                        fv = float(prices.get("FERTILIZER", 0) or 0)
                        jobs["MF%d" % idx] = Job("MF%d" % idx, "money", (x, y), ["COLLECT_FERTILIZER"], 0, fv,
                                                 goods={"FERTILIZER": 1})
                    else:
                        service.append("COLLECT_FERTILIZER")
                leaving = bool(keep_animals) and keep_animals.get(idx) != sp
                new = int(t.get("placed_day", -1)) == day
                care_op = ["CARE"] if cfg["care"] and not t.get("cared_today") and not leaving else []
                if not t.get("fed_today") and not leaving and (not new or cfg["feed_new"]):
                    mand = int(t.get("consecutive_unfed", 0) or 0) >= 1
                    bank = int(t.get("pending_care_bonus", 0) or 0)
                    v = (cfg["v_keep"] if mand else 0.0) + (pv if cfg["care"] else 0.0)                         + (bank * pv if _animal_produces(t, day) else 0.0)
                    fh = (cfg["feed_horizon"] or {}).get(str(day), 99)
                    soon = _next_production(t, day) - day <= int(fh)
                    jobs["F%d" % idx] = Job("F%d" % idx, "feed", (x, y), service + ["FEED"] + care_op,
                                            1 if mand else (int(cfg["feed_tier"]) if soon else 3), v,
                                            mand=mand, extra={"buy": mand or fbuy == "all"})
                    if service:                            # without wheat the pen still gets its collect / care visit
                        fv = sum(float(prices.get(g, 0) or 0) for g in (["FERTILIZER"] if "COLLECT_FERTILIZER" in service else []))
                        jobs["G%d" % idx] = Job("G%d" % idx, "care", (x, y), service + care_op, 3, fv + 0.5 * pv,
                                                extra={"alt_of": "F%d" % idx})
                elif service or care_op:
                    jobs["C%d" % idx] = Job("C%d" % idx, "care", (x, y), service + care_op,
                                            int(cfg["feed_tier"]) if care_op else 3, pv)
            elif t.get("kind") == "PLANT":
                if idx in plant_today:
                    continue                                   # the plant job below handles this tile
                crop = t["crop"]
                cd = CROPS[crop]
                age = day - int(t.get("planted_day", day))
                yu = int(t.get("yield_units", 0) or 0)
                decays = int(t.get("max_lifespan_step", -1)) >= 0 and int(t["max_lifespan_step"]) <= (day + 1) * 24
                if cfg["harvest_crops"] and not cd["ongoing"] and age >= cd["first"] and yu > 0 and (age >= cd["maxd"] or decays):
                    v = yu * float(prices.get(crop, 0) or 0)
                    jobs["H%d" % idx] = Job("H%d" % idx, "harvest", (x, y), ["HARVEST"], 1 if decays else 3, v)
                    continue
                if t.get("watered_today"):
                    continue
                if int(t.get("consecutive_unwatered", 0) or 0) >= 1:
                    jobs["W%d" % idx] = Job("W%d" % idx, "water", (x, y), ["WATER"], 1, cfg["v_keep"], mand=True)
                elif cfg["window_water"] and not cd["ongoing"]:
                    ws = (cd["maxd"] + 1) // 2
                    if ws <= age <= cd["maxd"] and yu < cd["max"]:
                        bonus = 2 if int(t.get("fertilized_until_day", -1)) >= day else 1
                        v = bonus * float(prices.get(crop, 0) or 0)
                        jobs["W%d" % idx] = Job("W%d" % idx, "water", (x, y), ["WATER"], 2 if v >= cfg["window_promote"] else 3, v)
    if fbuy == "keep":
        feeds = [j for j in jobs.values() if j.kind == "feed"]
        room = wheat_stock - sum(1 for j in feeds if j.mand)
        for j in sorted((j for j in feeds if not j.mand), key=lambda j_: -j_.value):
            if room > 0:
                room -= 1
            else:
                del jobs[j.key]
    for idx, crop in plant_today.items():
        x, y = idx % 10, idx // 10
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == crop and int(t.get("planted_day", -1)) == day:
            if not t.get("watered_today"):
                jobs["W%d" % idx] = Job("W%d" % idx, "water", (x, y), ["WATER"], 1, cfg["v_keep"], mand=True)
            continue
        pre = []
        if isinstance(t, dict):
            if t.get("animal"):
                continue                                       # an animal stands there: not plantable today
            if t.get("kind") == "PLANT" and not CROPS[t["crop"]]["ongoing"] and int(t.get("yield_units", 0) or 0) > 0 \
                    and day - int(t.get("planted_day", day)) >= CROPS[t["crop"]]["first"]:
                pre = ["HARVEST"]
            else:
                pre = ["DIG"]
        jobs["P%d" % idx] = Job("P%d" % idx, "plant", (x, y), ["PLANT", "WATER"], 2, cfg["v_plan"], pre=pre,
                                crop=crop, locked=(t == "LOCKED"))
    for idx, sp in keep_animals.items():
        x, y = idx % 10, idx // 10
        t = tiles[y][x]
        if isinstance(t, dict) and t.get("animal"):
            continue                                           # placed already (or another animal stands there)
        kind = ANIMALS[sp]["structure"]
        if t == "LOCKED" or t is None:
            pre = ["BUILD_" + kind]
        elif isinstance(t, dict) and t.get("kind") == kind:
            pre = []
        else:
            pre = ["DIG", "BUILD_" + kind]
        jobs["A%d" % idx] = Job("A%d" % idx, "place", (x, y), ["PLACE"], 2, cfg["v_plan"], pre=pre, animal=sp,
                                locked=(t == "LOCKED"))
    for idx, kind in struct_today.items():
        if idx in keep_animals:
            continue
        x, y = idx % 10, idx // 10
        t = tiles[y][x]
        if t == "LOCKED" or t is None:
            jobs["B%d" % idx] = Job("B%d" % idx, "build", (x, y), ["BUILD_" + kind], 2, cfg["v_build"],
                                    locked=(t == "LOCKED"))
    return jobs


def job_done(job, tiles, day):
    x, y = job.tile
    t = tiles[y][x]
    k = job.kind
    if k == "money":
        if not (isinstance(t, dict) and t.get("animal")):
            return True
        if job.ops[0] == "HARVEST":
            return int(t.get("yield_units", 0) or 0) <= 0
        return not t.get("fertilizer_available")
    if k == "plant":
        return isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == job.crop \
            and int(t.get("planted_day", -1)) == day
    if k == "place":
        return isinstance(t, dict) and t.get("animal") == job.animal
    if k == "build":
        return isinstance(t, dict) and t.get("kind") == job.ops[0].replace("BUILD_", "")
    if k == "water":
        return not (isinstance(t, dict) and t.get("kind") == "PLANT") or bool(t.get("watered_today"))
    if k == "feed":
        return not (isinstance(t, dict) and t.get("animal")) or bool(t.get("fed_today"))
    if k == "care":
        if not (isinstance(t, dict) and t.get("animal")):
            return True
        left = ("CARE" in job.ops and not t.get("cared_today")) \
            or ("COLLECT_FERTILIZER" in job.ops and t.get("fertilizer_available")) \
            or ("HARVEST" in job.ops and int(t.get("yield_units", 0) or 0) > 0)
        return not left
    if k == "harvest":
        return not (isinstance(t, dict) and t.get("kind") == "PLANT" and int(t.get("yield_units", 0) or 0) > 0)
    return True


# ------------------------------------------------------------------------------------------------ routes
class Stop:
    """a route stop: a job (its tile), a pickup at the nearest shed tile (item, qty) or a drop at the nearest shed tile"""
    __slots__ = ("kind", "key", "item", "qty")

    def __init__(self, kind, key=None, item=None, qty=0):
        self.kind, self.key, self.item, self.qty = kind, key, item, qty


class Eval:
    __slots__ = ("ok", "reason", "steps", "end", "events", "buys", "waits", "use", "drops", "owners", "done", "use_t")

    def __init__(self, ok, reason=None, steps=None, end=99, events=None, buys=None, waits=0, use=None, drops=None,
                 owners=None, done=None, use_t=None):
        self.ok, self.reason, self.steps, self.end = ok, reason, steps or [], end
        self.events, self.buys, self.waits, self.use, self.drops = events or [], buys or [], waits, use or Counter(), drops or []
        self.owners = owners or []
        self.done = done or {}
        self.use_t = use_t or []                    # (tick, stock key, units) of every stock take


FAIL = Eval(False, "empty")


class Route:
    __slots__ = ("u", "stops", "fixed", "ev")

    def __init__(self, u):
        self.u, self.stops, self.fixed, self.ev = u, [], 0, Eval(True, end=u.t)


class Sim:
    def __init__(self, obs, plan, day, hour, cfg, jobs):
        me = int(obs.get("player", 0))
        self.farm = obs["farms"][me]
        self.priv = obs.get("private") or {}
        self.day, self.h, self.cfg, self.jobs = day, hour, cfg, jobs
        self.tiles = self.farm["tiles"]
        self.prices = dict((obs.get("market") or {}).get("prices") or {})
        self.market_inv = dict((obs.get("market") or {}).get("inventory") or {})
        self.money = float(self.farm.get("money", 0) or 0)
        shed = {k: int(v) for k, v in (self.priv.get("shed") or {}).items() if v}
        seeds = {k: int(v) for k, v in (self.priv.get("seeds") or {}).items() if v}
        self.stock = Counter()
        for k, v in shed.items():
            if k in ANIMALS or k == "WHEAT":
                self.stock["shed:" + k] = v
        for k, v in seeds.items():
            self.stock["seed:" + k] = v
        self.shed_goods = {g: n for g, n in shed.items() if g in SELLABLE and n > 0}
        owned = list(self.farm.get("unlocked_quadrants") or ["NW"])
        self.land_q, self.land_price, self.land_tick = None, 0, None
        nxt = LAND_ORDER[len(owned) - 1] if len(owned) - 1 < len(LAND_ORDER) else None
        try:
            if nxt is not None and int(plan.land_day.get(nxt, 99)) <= day:
                self.land_q, self.land_price = nxt, LAND_PRICES[len(owned) - 1]
        except Exception:
            pass
        self.mg = set((cfg["money_goods"] or {}).get(str(day), MONEY_GOODS)) if cfg["money_first"] else set()
        self.routes = []
        self.base = Cash(self.money, hour, bool(cfg["cash_myopic"]))   # money + shed-stock sales + land
        self.total = Cash(self.money, hour, bool(cfg["cash_myopic"]))  # + every route's drops and purchases
        self.why = {}
        self.unfunded = []
        self.evicted = []
        self.why_all = {}
        self.free_cash = False                      # evaluation without cash limits (land-tick pass)
        self.buy_slots_now = None                   # order_cap: purchase order slots left at the current tick
        self.by_strict = True                       # pen_by: first insertion pass keeps a job's finish-by hour

    # -- valuation
    def sale(self, goods):
        v = 0.0
        for g, n in goods.items():
            if g in SELLABLE and n > 0:
                inv = self.market_inv.get(g)
                v += n * (price(g, int(inv) + n // 2) if inv is not None else float(self.prices.get(g, 0) or 0))
        return v

    def unit_cost(self, item):
        if item in ANIMALS:
            return float(ANIMALS[item]["cost"])
        return float(self.prices.get(item, 30) or 30) + float(self.cfg["wheat_buy_pad"])

    # -- cash timeline
    def add_base(self, t, v):
        self.base.add(t, v)
        self.total.add(t, v)

    def cash_without(self, r):
        c = self.total.copy()
        for (t, v, s) in r.ev.events:
            c.add(t, -v, s)
        return c

    def avail_without(self, r):
        a = Counter(self.stock)
        for r2 in self.routes:
            if r2 is not r:
                a.subtract(r2.ev.use)
        return a

    def takes_without(self, r):
        """stock_fifo: {key: [(tick, units)]} of the other routes' stock takes"""
        out = {}
        for r2 in self.routes:
            if r2 is not r:
                for (tt, k, n) in r2.ev.use_t:
                    out.setdefault(k, []).append((tt, n))
        return out

    def commit(self, r, stops, ev):
        for (t, v, s) in r.ev.events:
            self.total.add(t, -v, s)
        for (t, v, s) in ev.events:
            self.total.add(t, v, s)
        r.stops, r.ev = stops, ev


def _fail(reason):
    return Eval(False, reason)


def eval_route(S, r, stops, strict=False, deadlines=None):
    strict_key = strict if isinstance(strict, str) else None
    done = {}
    """engine-exact simulation of unit r.u through stops against everyone else's cash events; strict: keep-alive jobs
    must be finished by cfg keep_by (slack for later delays; used for new insertions)"""
    u = r.u
    c = None if S.free_cash else S.cash_without(r)
    avail = S.avail_without(r)
    use = Counter()
    use_t = []
    fifo = bool(S.cfg["stock_fifo"])
    others = S.takes_without(r) if fifo else None

    def free(key, tt):
        """stock units this route can still take at tick tt"""
        if not fifo:
            return avail[key] - use[key]
        return S.stock[key] - sum(n for (t2, n) in others.get(key, ()) if t2 <= tt) - use[key]
    t, p, inv = u.t, u.pos, Counter(u.inv)
    steps, events, buys, drops = [], [], [], []
    owners = []
    waits = 0

    def wait_to(tt):
        nonlocal t, waits
        while t < tt:
            steps.append((t, ["PASS"]))
            t += 1
            waits += 1

    others_now = None
    if S.buy_slots_now is not None:
        others_now = {(o[0], o[1]) for r2 in S.routes if r2 is not r for (tt, o) in r2.ev.buys if tt == S.h}
    own_now = set()

    def pay(t_need, cost, key=None):
        """returns the tick the purchase is made at (the latest-possible buy that the timeline can fund) or None"""
        lo = max(t_need, S.h)
        if lo == S.h and others_now is not None and key is not None:
            now = others_now | own_now
            if key not in now and len(now) >= S.buy_slots_now:
                lo = S.h + 1                             # no order slot left this tick
        if S.free_cash:
            b = lo
        else:
            b = c.earliest(lo, cost)
            if b is None:
                return None
            c.add(b, -cost, True)
            events.append((b, -cost, True))
        if b == S.h and key is not None:
            own_now.add(key)
        return b

    for si, st in enumerate(stops):
        tgt = S.jobs[st.key].tile if st.kind == "job" else near_shed(p)
        while p != tgt:
            mv = step_toward(p, tgt)
            steps.append((t, [mv]))
            p = moved(p, mv)
            t += 1
        if t > 23:
            return _fail("late")
        if st.kind in ("pick", "drop"):
            goods = {g: n for g, n in inv.items() if n > 0 and g in SELLABLE}
            if goods:
                steps.append((t, ["DROP"]))
                v = S.sale(goods)
                if c is not None:
                    c.add(t, v)
                events.append((t, v, False))
                drops.append((t, goods))
                for g in goods:
                    del inv[g]
                t += 1
            if st.kind == "drop":
                continue
            item, q = st.item, int(st.qty)
            key = "shed:" + item
            take = max(0, min(q, free(key, t)))
            use[key] += take
            if take:
                use_t.append((t, key, take))
            nb = q - take
            if nb > 0:
                cost = nb * S.unit_cost(item)
                b = pay(t - 1, cost, ("BUY_ANIMAL" if item in ANIMALS else "BUY_PRODUCT", item))
                if b is None or b + 1 > 23:
                    return _fail("no_cash_" + item.lower())
                wait_to(b + 1)
                buys.append((b, ["BUY_ANIMAL" if item in ANIMALS else "BUY_PRODUCT", item, nb]))
                owners.append(next((s2.key for s2 in stops[si + 1:] if s2.kind == "job" and s2.key in S.jobs
                                    and ((S.jobs[s2.key].kind == "place" and S.jobs[s2.key].animal == item)
                                         or (item == "WHEAT" and "FEED" in S.jobs[s2.key].ops))), None))
            steps.append((t, ["PICKUP", item, q]))
            inv[item] += q
            t += 1
            continue
        j = S.jobs[st.key]
        if j.locked:
            if S.land_tick is None:
                return _fail("no_land")
            wait_to(S.land_tick + 1)
        x, y = j.tile
        t_ = S.tiles[y][x]
        for op in j.pre:
            steps.append((t, [op]))
            if op == "HARVEST" and isinstance(t_, dict) and t_.get("crop"):
                inv[t_["crop"]] += int(t_.get("yield_units", 0) or 0)
            t += 1
        if j.kind == "plant":
            key = "seed:" + j.crop
            if free(key, t) > 0:
                use[key] += 1
                use_t.append((t, key, 1))
            else:
                b = pay(t - 1, float(CROPS[j.crop]["seed"]), ("BUY_SEED", j.crop))
                if b is None or b + 1 > 22:
                    return _fail("no_cash_seed")
                wait_to(b + 1)
                buys.append((b, ["BUY_SEED", j.crop, 1]))
                owners.append(j.key)
            steps.append((t, ["PLANT", j.crop]))
            t += 1
            steps.append((t, ["WATER"]))
            t += 1
        elif j.kind == "place":
            if inv[j.animal] <= 0:
                return _fail("no_animal")
            steps.append((t, ["PLACE", j.animal]))
            inv[j.animal] -= 1
            t += 1
        else:
            for op in j.ops:
                if op == "FEED":
                    if inv["WHEAT"] <= 0:
                        return _fail("no_wheat")
                    inv["WHEAT"] -= 1
                elif op == "COLLECT_FERTILIZER":
                    inv["FERTILIZER"] += 1
                elif op == "HARVEST" and isinstance(t_, dict):
                    if t_.get("animal"):
                        inv[ANIMALS[t_["animal"]]["product"]] += int(t_.get("yield_units", 0) or 0)
                    elif t_.get("crop"):
                        inv[t_["crop"]] += int(t_.get("yield_units", 0) or 0)
                steps.append((t, [op]))
                t += 1
        if t > 24:
            return _fail("late")
        if strict_key is not None and st.key == strict_key and S.by_strict and j.extra.get("by") is not None \
                and t > int(j.extra["by"]):
            return _fail("late_by")
        if strict and j.mand and t > int(S.cfg["keep_by"]) and (strict_key is None or st.key == strict_key):
            return _fail("late_keep")
        if deadlines and st.key in deadlines and t > deadlines[st.key]:
            return _fail("delays_keep")
        done[st.key] = t
    if t > 24:
        return _fail("late")
    return Eval(True, None, steps, t, events, buys, waits, use, drops, owners, done, use_t)


def _wheat_before(S, r, stops, pos):
    """wheat in hand when reaching stops[pos]: carried at the start + picked - fed before pos"""
    w = r.u.inv.get("WHEAT", 0)
    last_pick = None
    for i, st in enumerate(stops[:pos]):
        if st.kind == "pick" and st.item == "WHEAT":
            w += st.qty
            last_pick = i
        elif st.kind == "job":
            j = S.jobs.get(st.key)
            if j is not None and "FEED" in j.ops:
                w -= 1
    return w, last_pick


def _animals_before(S, r, stops, pos, animal):
    a = r.u.inv.get(animal, 0)
    for st in stops[:pos]:
        if st.kind == "pick" and st.item == animal:
            a += st.qty
        elif st.kind == "job":
            j = S.jobs.get(st.key)
            if j is not None and j.kind == "place" and j.animal == animal:
                a -= 1
    return a


def build_insertion(S, r, j, pos):
    """the stop list with job j inserted at pos (plus the pickup / drop stops it needs)"""
    stops = [Stop(s.kind, s.key, s.item, s.qty) for s in r.stops]
    if j.kind == "money":
        if pos < len(stops) and stops[pos].kind == "drop" and pos > 0 and stops[pos - 1].kind == "job" \
                and S.jobs.get(stops[pos - 1].key) is not None and S.jobs[stops[pos - 1].key].kind == "money":
            stops.insert(pos, Stop("job", j.key))           # chain before an existing money-run drop
        else:
            stops[pos:pos] = [Stop("job", j.key), Stop("drop")]
        return stops
    if j.kind == "place":
        if _animals_before(S, r, stops, pos, j.animal) > 0:
            stops.insert(pos, Stop("job", j.key))
        elif pos > 0 and stops[pos - 1].kind == "pick" and stops[pos - 1].item == j.animal:
            stops[pos - 1].qty += 1
            stops.insert(pos, Stop("job", j.key))
        else:
            stops[pos:pos] = [Stop("pick", item=j.animal, qty=1), Stop("job", j.key)]
        return stops
    if "FEED" in j.ops:
        w, last_pick = _wheat_before(S, r, stops, pos)
        fb = S.cfg["feed_batch"]
        fb = int(fb.get(str(S.day), 6)) if isinstance(fb, dict) else int(fb)
        if w > 0:
            stops.insert(pos, Stop("job", j.key))
        elif last_pick is not None and stops[last_pick].qty < fb:
            stops[last_pick].qty += 1
            stops.insert(pos, Stop("job", j.key))
        else:
            stops[pos:pos] = [Stop("pick", item="WHEAT", qty=1), Stop("job", j.key)]
        return stops
    stops.insert(pos, Stop("job", j.key))
    return stops


def _stop_tile(S, st, prev):
    return S.jobs[st.key].tile if st.kind == "job" else near_shed(prev)


def candidate_positions(S, r, j):
    """insertion points after the fixed prefix, pruned to the cheapest detours (plus the end of the route)"""
    n = len(r.stops)
    lo = min(r.fixed, n)
    pos_list = list(range(lo, n + 1))
    M = int(S.cfg["max_positions"])
    if M <= 0 or len(pos_list) <= M:
        return pos_list
    tiles, p = [], r.u.pos
    for st in r.stops:
        p = _stop_tile(S, st, p)
        tiles.append(p)
    jt = j.tile if j.kind != "place" else near_shed(j.tile)

    def detour(i):
        a = tiles[i - 1] if i > 0 else r.u.pos
        if i < n:
            return dist(a, jt) + dist(jt, tiles[i]) - dist(a, tiles[i])
        return dist(a, jt)
    best = sorted(pos_list, key=detour)[:M]
    if n not in best:
        best.append(n)
    return sorted(set(best))


def _deadlines(S, r):
    """finish-by ticks protecting the route's jobs from later insertions: keep-alive jobs (keep_by or their finish),
    pen_by jobs that meet their hour (that hour)"""
    kb = int(S.cfg["keep_by"])
    dl = {}
    for k, dn in r.ev.done.items():
        j = S.jobs.get(k)
        if j is None:
            continue
        if j.mand:
            dl[k] = max(kb, int(dn))
        by = j.extra.get("by")
        if by is not None and int(dn) <= int(by):
            dl[k] = min(dl.get(k, 99), int(by))
    return dl


def insert_job(S, j):
    """cheapest insertion over all routes and positions; returns True when placed"""
    best = None
    reason = "no_route"
    wp = float(S.cfg["wait_penalty"])
    ecw = float(S.cfg["ec_weight"])
    for r in S.routes:
        if r.u.done:
            continue
        base_end, base_w = (r.ev.end, r.ev.waits) if r.ev.ok else (r.u.t, 0)
        dl = _deadlines(S, r)
        for pos in candidate_positions(S, r, j):
            stops = build_insertion(S, r, j, pos)
            ev = eval_route(S, r, stops, strict=j.key, deadlines=dl)
            if not ev.ok:
                reason = ev.reason
                S.why_all.setdefault(j.key, Counter())[ev.reason] += 1
                continue
            cost = (ev.end - base_end) + wp * (ev.waits - base_w) + ecw * ev.done.get(j.key, ev.end)
            if best is None or cost < best[0]:
                best = (cost, r, stops, ev)
    if best is None and j.cls <= 2 and S.cfg["evict"]:
        ok = _insert_evicting(S, j)
        if ok:
            return True
    if best is None and S.by_strict and j.extra.get("by") is not None:
        S.by_strict = False                              # no slot by the hour: insert it without the deadline
        try:
            return insert_job(S, j)
        finally:
            S.by_strict = True
    if best is None:
        S.why[j.key] = reason
        return False
    S.commit(best[1], best[2], best[3])
    return True


def _route_keys(r):
    return [s.key for s in r.stops if s.kind == "job"], [i for i, s in enumerate(r.stops) if s.kind == "drop"]


def _without(S, r, drop_key):
    """the route's stops rebuilt without one job (order kept; its fixed prefix untouched)"""
    view = RouteView(r, [Stop(s.kind, s.key, s.item, s.qty) for s in r.stops[:r.fixed]])
    rounds_on = _pen_rounds_on(S)
    keys = [s.key for s in r.stops[r.fixed:] if s.kind == "job" and s.key != drop_key]
    for i, k in enumerate(keys):
        view.stops = build_insertion(S, view, S.jobs[k], len(view.stops))
        if rounds_on and S.jobs[k].extra.get("round") and (i + 1 == len(keys)
                                                           or not S.jobs[keys[i + 1]].extra.get("round")):
            view.stops = view.stops + [Stop("drop")]
    return view.stops


def _insert_evicting(S, j):
    """make room for j by removing tier-3 jobs (lowest value first) from one route; evicted jobs go back to the pool"""
    wp = float(S.cfg["wait_penalty"])
    best = None
    for r in S.routes:
        t3 = sorted((s.key for s in r.stops[r.fixed:] if s.kind == "job" and S.jobs[s.key].cls >= 3),
                    key=lambda k: S.jobs[k].value)
        removed = []
        view = RouteView(r, r.stops)
        for k3 in t3[:int(S.cfg["evict_max"])]:
            removed.append(k3)
            stops0 = _without(S, RouteView(r, view.stops), k3)
            view = RouteView(r, stops0)
            ev0 = eval_route(S, r, stops0)
            if not ev0.ok:
                continue
            view.ev = ev0
            dl = _deadlines(S, r)
            for pos in candidate_positions(S, view, j):
                stops = build_insertion(S, view, j, pos)
                ev = eval_route(S, r, stops, strict=j.key, deadlines=dl)
                if not ev.ok:
                    continue
                lost = sum(S.jobs[k].value for k in removed)
                cost = lost + (ev.end - r.ev.end) + wp * (ev.waits - r.ev.waits)
                if best is None or cost < best[0]:
                    best = (cost, r, stops, ev, list(removed))
            if best is not None and best[1] is r:
                break
    if best is None:
        return False
    S.commit(best[1], best[2], best[3])
    S.evicted.extend(best[4])
    return True


def rebuild_route(S, r, keys):
    """stops regenerated from an ordered job sequence (pickups / drops added as needed; "RET" = a drop at the shed);
    jobs that no longer fit are returned for re-insertion"""
    left = []
    for k in keys:
        if k == "RET":
            pen_drop = False
            if _pen_rounds_on(S):
                if any(r.u.inv.get(g, 0) > 0 for g in SELLABLE):
                    pen_drop = True
                for s in reversed(r.stops):
                    if s.kind in ("drop", "pick"):
                        break
                    if s.kind == "job" and s.key in S.jobs and S.jobs[s.key].kind in ("feed", "care") \
                            and _collects(S.jobs[s.key]):
                        pen_drop = True
                        break
            if pen_drop or any(r.u.inv.get(g, 0) > 0 for g in S.mg) or (r.stops and r.stops[-1].kind == "job"
                                                              and S.jobs.get(r.stops[-1].key) is not None
                                                              and S.jobs[r.stops[-1].key].kind == "money"):
                stops = [Stop(s.kind, s.key, s.item, s.qty) for s in r.stops] + [Stop("drop")]
                ev = eval_route(S, r, stops)
                if ev.ok:
                    S.commit(r, stops, ev)
            continue
        j = S.jobs.get(k)
        if j is None:
            continue
        stops = build_insertion(S, r, j, len(r.stops))
        ev = eval_route(S, r, stops)
        if ev.ok and j.kind == "feed" and not j.extra.get("buy", True):
            w_new = sum(int(o[2]) for (_, o) in ev.buys if o[0] == "BUY_PRODUCT")
            w_old = sum(int(o[2]) for (_, o) in r.ev.buys if o[0] == "BUY_PRODUCT")
            if w_new > w_old:
                ev = Eval(False, "no_wheat_buy")
        if ev.ok:
            S.commit(r, stops, ev)
        else:
            left.append(k)
    return left


def money_segments(S, units):
    """hour-0 money runs (user rule): in order of availability each unit takes the pen with the best value per hour of
    its round trip, chains a further pen on the way home when its load is small, then drops at the shed"""
    cfg = S.cfg
    left = {k for k, j in S.jobs.items() if j.kind == "money"}
    state = {u.idx: [u.pos, u.t, Counter(), []] for u in units}   # pos, t, carried, job keys (+ "RET")
    done = set()
    for _ in range(400):
        live = [u for u in units if u.idx not in done and state[u.idx][1] <= 23]
        if not live or not left and not any(state[u.idx][2] for u in live):
            break
        u = min(live, key=lambda v: (state[v.idx][1], v.idx))
        pos, t, car, seq = state[u.idx]
        carried_v = sum(n * float(S.prices.get(g, 0) or 0) for g, n in car.items())
        pick = None
        if car:
            if carried_v < cfg["chain_max_value"]:
                direct = dist(pos, near_shed(pos))
                cands = [(dist(pos, S.jobs[k].tile) + dist(S.jobs[k].tile, near_shed(S.jobs[k].tile)) - direct, -S.jobs[k].value, k)
                         for k in sorted(left)]
                cands = [c for c in cands if c[0] <= cfg["chain_detour"]]
                if cands:
                    pick = min(cands)[2]
            if pick is None:
                s = near_shed(pos)
                t += dist(pos, s) + 1
                state[u.idx] = [s, t, Counter(), seq + ["RET"]]
                continue
        else:
            best = None
            for k in sorted(left):
                j = S.jobs[k]
                eta = t + dist(pos, j.tile) + len(j.ops) + dist(j.tile, near_shed(j.tile)) + 1
                if eta > 24:
                    continue
                sc = j.value / max(1, eta - t)
                if best is None or sc > best[0]:
                    best = (sc, k)
            if best is None:
                done.add(u.idx)
                continue
            pick = best[1]
        j = S.jobs[pick]
        t += dist(pos, j.tile) + len(j.ops)
        car.update(j.goods)
        state[u.idx] = [j.tile, t, car, seq + [pick]]
        left.discard(pick)
    return {idx: st[3] for idx, st in state.items()}


def seq_to_stops(S, seq):
    stops = []
    for k in seq:
        if k == "RET":
            stops.append(Stop("drop"))
        elif k in S.jobs:
            stops.append(Stop("job", k))
    return stops


def insertion_order(S, keys):
    cfg = S.cfg
    rank = {k: i for i, k in enumerate(cfg["fund_order"])}
    pen_first = bool(int((cfg["pen_first"] or {}).get(str(S.day), 0)))

    def cash_free(j):
        return j.kind in ("water", "care", "harvest", "build")

    def key(k):
        j = S.jobs[k]
        alt = j.extra.get("alt_of")
        if alt is not None and alt in S.jobs:            # right after its feed job
            base = key(alt)
            return base[:2] + (base[2] + 1e-6,)
        if j.kind == "money":
            return (0, 0, -j.value)
        if pen_first and j.kind in ("feed", "care"):
            return (0.5, 0, -j.value)
        if j.cls == 1:
            return (1, 0, -j.value)
        if cfg["cash_free_first"] and cash_free(j):     # morning work that needs no money goes in before the purchases
            return (1.5, 0, -j.value)
        if j.kind == "plant":
            return (2, rank.get(j.crop, 50), 0)
        if j.kind == "place":
            return (2, rank.get(j.animal, 50), 0)
        if j.cls == 2:
            return (2, 60, -j.value)
        return (3, 0, -j.value / max(1, len(j.ops) + len(j.pre)))
    return sorted(keys, key=key)


def _live_bringback(S, r, seq):
    """the part of a stored bring-back still to do: its open money jobs, and its drop while goods are carried or a money
    job is still ahead of it"""
    out = []
    carrying = any(r.u.inv.get(g, 0) > 0 for g in S.mg)
    for k in seq:
        if k == "RET":
            if carrying:
                out.append("RET")
                carrying = False
        elif k in S.jobs and S.jobs[k].kind == "money":
            out.append(k)
            carrying = True
    return out


def _warm_seqs(S, prev):
    """the previous plan's job sequences; a finished stage (PLANT done, its WATER left) maps to the tile's new job"""
    seqs = {}
    dedup = bool(S.cfg["warm_dedup"])
    in_prev = {k for q in prev.values() for k in q if k != "RET"} if dedup else set()
    taken = set()                                    # warm_dedup: keys already kept by a unit
    for idx, seq in sorted(prev.items(), key=lambda kv: int(kv[0])):
        keep, seen = [], set()
        for k in seq:
            if k == "RET" or k in S.jobs:
                if dedup and k != "RET":
                    if k in taken:
                        continue
                    taken.add(k)
                keep.append(k)
            else:
                tile = _key_tile(k)
                sub = next((k2 for k2, j2 in S.jobs.items() if j2.tile == tile and k2 not in seen
                            and not (dedup and (k2 in in_prev or k2 in taken))), None)
                if sub is not None:
                    keep.append(sub)
                    taken.add(sub)
            seen.update(keep)
        seqs[int(idx)] = keep
    return seqs


def warm_global(S, rests):
    """the previous plan's remaining jobs, cash checked across all units in time order: every route is extended with its
    jobs without cash limits, then the purchases of all routes are accepted in tick order (ties: plan priority) while
    the timeline (with every drop and the land) stays funded; a job whose purchase is refused leaves its sequence"""
    snap = [(r, r.stops, r.ev) for r in S.routes]
    rank = {k: i for i, k in enumerate(insertion_order(S, [k for q in rests.values() for k in q if k != "RET"]))}
    buys = []
    S.free_cash = True
    for r in S.routes:
        keys = rests.get(r.u.idx, [])
        if not keys:
            continue
        stops = [Stop(s.kind, s.key, s.item, s.qty) for s in r.stops]
        for k in keys:
            if k == "RET":
                stops = stops + [Stop("drop")]
                continue
            stops = build_insertion(S, RouteView(r, stops), S.jobs[k], len(stops))
        ev = eval_route(S, r, stops)
        if not ev.ok:
            continue
        for (b, order), k in zip(ev.buys, ev.owners):
            buys.append((b, rank.get(k, 999), _order_cost(S, order), r.u.idx, k))
    S.free_cash = False
    for (r, stops, ev) in snap:
        r.stops, r.ev = stops, ev
    c = S.total.copy()
    refused = set()
    order_key = (lambda x: (x[1], x[0])) if S.cfg["warm_priority"] else (lambda x: (x[0], x[1]))
    for (b, _, cost, idx, k) in sorted(buys, key=order_key):
        if k in refused:
            continue
        if c.ok(b, cost):
            c.add(b, -cost, True)
        else:
            refused.add(k)
    for idx in rests:
        rests[idx] = [k for k in rests[idx] if k not in refused]
    S.why.update({k: "no_cash_warm" for k in refused if k is not None})


class RouteView:
    """a route-like view over a scratch stop list (for build_insertion)"""
    __slots__ = ("u", "stops", "fixed", "ev")

    def __init__(self, r, stops):
        self.u, self.stops, self.fixed, self.ev = r.u, stops, r.fixed, r.ev


def _order_cost(S, order):
    op, item, n = order[0], order[1], int(order[2])
    if op == "BUY_SEED":
        return float(CROPS[item]["seed"]) * n
    return S.unit_cost(item) * n


def _seq(r):
    return [s.key for s in r.stops[r.fixed:] if s.kind == "job"]


def _rebuild(S, r, seq):
    """(stops, eval) of the route rebuilt from its fixed prefix + a job sequence, or None when infeasible"""
    view = RouteView(r, [Stop(s.kind, s.key, s.item, s.qty) for s in r.stops[:r.fixed]])
    rounds_on = _pen_rounds_on(S)
    for i, k in enumerate(seq):
        j = S.jobs.get(k)
        if j is None:
            return None
        view.stops = build_insertion(S, view, j, len(view.stops))
        if rounds_on and j.extra.get("round") and (i + 1 == len(seq) or S.jobs.get(seq[i + 1]) is None
                                                   or not S.jobs[seq[i + 1]].extra.get("round")):
            view.stops = view.stops + [Stop("drop")]
    dl = _deadlines(S, r)
    ev = eval_route(S, r, view.stops, deadlines=dl)
    return (view.stops, ev) if ev.ok else None


def _rcost(ev, wp, mode="end"):
    if mode == "finish":                               # every job's finish hour: rewards parallel work (load balance)
        return sum(ev.done.values()) + wp * ev.waits
    return ev.end + wp * ev.waits


def polish(S, budget):
    """relocate moves until no improvement or the evaluation budget is spent; returns the number of moves made"""
    wp = float(S.cfg["wait_penalty"])
    reach = int(S.cfg["polish_reach"])
    pm = S.cfg["polish_obj"]
    evals, moves = 0, 0
    improved = True
    while improved and evals < budget:
        improved = False
        for ra in S.routes:
            if not ra.ev.ok:
                continue
            for k in list(_seq(ra)):
                if evals >= budget:
                    break
                if k not in S.jobs or k not in _seq(ra) or S.jobs[k].extra.get("round"):
                    continue
                jt = S.jobs[k].tile
                seqa = _seq(ra)
                res_a = _rebuild(S, ra, [x for x in seqa if x != k])
                evals += 1
                if res_a is None:
                    continue
                old_a = (ra.stops, ra.ev)
                gain_a = _rcost(old_a[1], wp, pm) - _rcost(res_a[1], wp, pm)
                S.commit(ra, res_a[0], res_a[1])
                best = None
                for rb in S.routes:
                    if not rb.ev.ok or rb.u.done:
                        continue
                    seqb = _seq(rb)
                    # stop tiles of rb near the job (prune): positions next to them, plus the end
                    tiles = [S.jobs[x].tile for x in seqb]
                    cand_pos = sorted({p for i, tl in enumerate(tiles) if dist(tl, jt) <= reach for p in (i, i + 1)} | {len(seqb)})
                    if rb is ra:
                        cand_pos = [p for p in range(len(seqb) + 1)]
                    for p in cand_pos:
                        res_b = _rebuild(S, rb, seqb[:p] + [k] + seqb[p:])
                        evals += 1
                        if res_b is None:
                            continue
                        loss_b = _rcost(res_b[1], wp, pm) - _rcost(rb.ev, wp, pm)
                        delta = loss_b - gain_a
                        if delta < -0.5 and (best is None or delta < best[0]):
                            best = (delta, rb, res_b)
                if best is not None:
                    S.commit(best[1], best[2][0], best[2][1])
                    moves += 1
                    improved = True
                else:
                    S.commit(ra, old_a[0], old_a[1])
    S.polish_log = dict(evals=evals, moves=moves)
    return moves


ROLE_OF = {"plant": "plant", "place": "build", "build": "build", "feed": "pen", "care": "pen", "water": "water",
           "harvest": "water"}


def _snake(tiles):
    """row-major snake order (alternate direction every row), quadrant by quadrant from the shed outwards"""
    def key(t):
        x, y = t
        q = (0 if y < 5 else 1, 0 if x < 5 else 1)
        return (q, y, x if y % 2 == 0 else -x)
    return sorted(tiles, key=key)


def _chunks(items, n, work):
    """cut items (in order) into n contiguous chunks of about equal work"""
    if n <= 0 or not items:
        return []
    total = sum(work(i) for i in items)
    out, cur, acc = [], [], 0.0
    per = total / n
    for it in items:
        cur.append(it)
        acc += work(it)
        if acc >= per * (len(out) + 1) - 1e-9 and len(out) < n - 1:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _route_tail(S, r):
    """(tick, tile) where a route ends"""
    if not r.ev.ok or not r.stops:
        return r.u.t, r.u.pos
    p = r.u.pos
    for st in r.stops:
        p = S.jobs[st.key].tile if st.kind == "job" and st.key in S.jobs else near_shed(p)
    return r.ev.end, p


def role_plan(S, keys):
    """assign keys (non-money jobs) to roles and sweep them into the routes; returns the keys not placed"""
    cfg = S.cfg
    by_role = {"plant": [], "build": [], "pen": [], "water": []}
    for k in keys:
        j = S.jobs[k]
        if j.extra.get("alt_of"):
            continue                                   # fallbacks only through the insertion
        by_role.setdefault(ROLE_OF.get(j.kind, "water"), []).append(k)

    def w_job(k):
        j = S.jobs[k]
        if j.kind == "plant":
            return 3.0 + len(j.pre)
        if j.kind in ("place", "build"):
            return 3.0 + len(j.pre) + 2.0 * dist(near_shed(j.tile), j.tile)
        if j.kind in ("feed", "care"):
            return len(j.ops) + 1.5
        return 2.0
    work = {r_: sum(w_job(k) for k in ks) for r_, ks in by_role.items()}
    routes = [r for r in S.routes if not r.u.done]
    tails = {r.u.idx: _route_tail(S, r) for r in routes}
    avail = {r.u.idx: max(0, 24 - tails[r.u.idx][0]) for r in routes}
    n = len(routes)
    tot = sum(work.values()) or 1.0
    want = {r_: (work[r_] / tot) * n for r_ in work}
    cnt = {r_: (max(1, int(want[r_])) if work[r_] > 0 else 0) for r_ in work}
    while sum(cnt.values()) > n:
        r_ = max((x for x in cnt if cnt[x] > 1), key=lambda x: cnt[x] - want[x], default=None)
        if r_ is None:
            break
        cnt[r_] -= 1
    while sum(cnt.values()) < n:
        r_ = max((x for x in cnt if work[x] > 0), key=lambda x: want[x] - cnt[x], default=None)
        if r_ is None:
            break
        cnt[r_] += 1
    # role chunks
    chunks = {}
    order = cfg["role_order"]
    for r_ in order:
        ks = by_role.get(r_, [])
        if not ks or not cnt.get(r_):
            continue
        if r_ == "build":
            ks = sorted(ks, key=lambda k: (dist(near_shed(S.jobs[k].tile), S.jobs[k].tile), k))
            ch = [[] for _ in range(cnt[r_])]
            for i, k in enumerate(ks):
                ch[i % cnt[r_]].append(k)
            chunks[r_] = [c for c in ch if c]
        else:
            tiles = _snake([S.jobs[k].tile for k in ks])
            pos_of = {}
            for k in ks:
                pos_of.setdefault(S.jobs[k].tile, []).append(k)
            seq = []
            for t in tiles:
                seq.extend(sorted(pos_of.pop(t, [])))
            chunks[r_] = _chunks(seq, cnt[r_], w_job)
    # workers to chunks: nearest free worker (earliest tail + distance to the chunk start)
    free = {r.u.idx: r for r in routes}
    plan_seq = {}
    for r_ in order:
        for ch in chunks.get(r_, []):
            if not free:
                break
            start = S.jobs[ch[0]].tile if r_ != "build" else near_shed(S.jobs[ch[0]].tile)
            idx = min(free, key=lambda i: (tails[i][0] + dist(tails[i][1], start), i))
            plan_seq[idx] = ch
            del free[idx]
    left = []
    by_idx = {r.u.idx: r for r in routes}
    for r_ in order:                                   # cash priority: routes evaluated role by role
        for idx, ch in plan_seq.items():
            if ROLE_OF.get(S.jobs[ch[0]].kind, "water") != r_:
                continue
            left.extend(rebuild_route(S, by_idx[idx], ch))
    placed = {s.key for r in S.routes for s in r.stops if s.kind == "job"}
    left.extend(k for k in keys if k not in placed and k not in left and not S.jobs[k].extra.get("alt_of"))
    S.role_log = dict(counts=cnt, work={k: round(v) for k, v in work.items()}, left=len(left))
    return left


def role_plan2(S, keys):
    """phase-B crew: plantings + placements in contiguous chunks for the workers nearest the block; returns keys left"""
    cfg = S.cfg
    crew_jobs = [k for k in keys if S.jobs[k].kind in ("plant", "place", "build")]
    if not crew_jobs:
        return list(keys)
    routes = [r for r in S.routes if not r.u.done]
    tails = {r.u.idx: _route_tail(S, r) for r in routes}
    t_open = S.land_tick + 1 if S.land_tick is not None else S.h
    locked_any = any(S.jobs[k].locked for k in crew_jobs)
    t0 = t_open if locked_any else S.h

    def w_job(k):
        j = S.jobs[k]
        if j.kind == "plant":
            return 3.0 + len(j.pre)
        return 3.0 + len(j.pre) + 2.0 * dist(near_shed(j.tile), j.tile)
    work = sum(w_job(k) for k in crew_jobs)
    hours = max(4, 23 - max(t0, S.h))
    n_b = max(1, min(len(routes), int(round(work * float(cfg["crew_slack"]) / hours + 0.4999))))
    places = sorted([k for k in crew_jobs if S.jobs[k].kind in ("place", "build")],
                    key=lambda k: (dist(near_shed(S.jobs[k].tile), S.jobs[k].tile), k))
    plants = [k for k in crew_jobs if S.jobs[k].kind == "plant"]
    tiles = _snake([S.jobs[k].tile for k in plants])
    by_tile = {}
    for k in plants:
        by_tile.setdefault(S.jobs[k].tile, []).append(k)
    seq = []
    for t in tiles:
        seq.extend(sorted(by_tile.pop(t, [])))
    n_places = min(n_b, max(1 if places else 0, int(round(sum(w_job(k) for k in places) / max(1.0, hours)))))
    plant_chunks = _chunks(seq, max(1, n_b - n_places) if seq else 0, w_job) if seq else []
    place_chunks = [[] for _ in range(n_places)]
    for i, k in enumerate(places):
        place_chunks[i % max(1, n_places)].append(k)
    chunks = [("build", c) for c in place_chunks if c] + [("plant", c) for c in plant_chunks if c]
    # crew = the workers nearest each chunk's start by the block's opening hour
    free = {r.u.idx: r for r in routes}
    assign = []
    for kind, ch in chunks:
        if not free:
            break
        start = near_shed(S.jobs[ch[0]].tile) if kind == "build" else S.jobs[ch[0]].tile
        idx = min(free, key=lambda i: (max(tails[i][0], t0) + dist(tails[i][1], start), i))
        assign.append((idx, kind, ch))
        del free[idx]
    left = []
    by_idx = {r.u.idx: r for r in routes}
    for kind in ("plant", "build"):                    # cash priority: seeds, then animals
        for idx, k2, ch in assign:
            if k2 == kind:
                left.extend(rebuild_route(S, by_idx[idx], ch))
    rounds_log = _pen_rounds(S, keys) if _pen_rounds_on(S) else None
    placed = {s.key for r in S.routes for s in r.stops if s.kind == "job"}
    rest = [k for k in keys if k not in placed]
    S.role_log = dict(crew=n_b, t_open=t0, work=round(work), chunks=[(i, kd, len(c)) for i, kd, c in assign],
                      left_crew=len([k for k in left if k in crew_jobs]), rounds=rounds_log)
    return rest


def _pen_rounds_on(S):
    return int(((S.cfg["pen_rounds"] or {}).get(str(S.day), 0)) or 0) > 0


def _collects(j):
    return "COLLECT_FERTILIZER" in j.ops or "HARVEST" in j.ops


def _with_round(S, r, rd, at):
    """the route with round rd (its jobs, then a drop at the shed) inserted at stop index at"""
    view = RouteView(r, [Stop(s.kind, s.key, s.item, s.qty) for s in r.stops[:at]])
    for k in rd:
        view.stops = build_insertion(S, view, S.jobs[k], len(view.stops))
    view.stops = view.stops + [Stop("drop")]
    n_new = len(view.stops)
    for s in r.stops[at:]:
        if s.kind == "job":
            if s.key in S.jobs:
                view.stops = build_insertion(S, view, S.jobs[s.key], len(view.stops))
        elif s.kind == "drop":
            view.stops = view.stops + [Stop("drop")]
    ev = eval_route(S, r, view.stops, deadlines=_deadlines(S, r))
    if not ev.ok:
        S.round_why[ev.reason] = S.round_why.get(ev.reason, 0) + 1
        S.round_dbg.append((r.u.idx, ev.reason, len(view.stops), [(s.kind, s.key or s.item) for s in view.stops[:n_new]]))
    return (view.stops, ev, n_new) if ev.ok else None


def _pen_rounds(S, keys):
    """morning pen rounds of R pens (see pen_rounds); returns a log"""
    R = int(S.cfg["pen_rounds"][str(S.day)])
    wp = float(S.cfg["wait_penalty"])
    placed_now = {s.key for r in S.routes for s in r.stops if s.kind == "job"}
    pens = [k for k in keys if k in S.jobs and k not in placed_now and S.jobs[k].kind in ("feed", "care")
            and not S.jobs[k].extra.get("alt_of")]
    by_tile = {}
    for k in pens:
        by_tile.setdefault(S.jobs[k].tile, []).append(k)
    left_t = sorted(by_tile)
    rounds = []
    while left_t:                                      # spokes: nearest to the shed, then nearest to the last pen
        cur = min(left_t, key=lambda t: (dist(near_shed(t), t), t))
        rd_t = [cur]
        left_t.remove(cur)
        while len(rd_t) < R and left_t:
            nxt = min(left_t, key=lambda t: (dist(rd_t[-1], t), dist(near_shed(t), t), t))
            rd_t.append(nxt)
            left_t.remove(nxt)
        rd = []
        for t in rd_t:
            rd.extend(sorted(by_tile[t]))
        rounds.append(rd)
    at = {r.u.idx: min(r.fixed, len(r.stops)) for r in S.routes}
    log = [("routes", {r.u.idx: (r.ev.end if r.ev.ok else None, len(r.stops), r.fixed, r.u.t, r.u.pos) for r in S.routes})]
    for rd in rounds:
        best = None
        S.round_why = {}
        S.round_dbg = []
        for r in S.routes:
            if r.u.done:
                continue
            res = _with_round(S, r, rd, at[r.u.idx])
            if res is None:
                continue
            cost = _rcost(res[1], wp) - (_rcost(r.ev, wp) if r.ev.ok and r.stops else r.u.t)
            if best is None or cost < best[0]:
                best = (cost, r, res)
        if best is None:
            log.append((None, rd, dict(S.round_why), S.round_dbg[:3]))
            continue
        _, r, (stops, ev, n_new) = best
        S.commit(r, stops, ev)
        at[r.u.idx] = n_new
        for k in rd:
            S.jobs[k].extra["round"] = True
        S.round_keys = list(getattr(S, "round_keys", [])) + list(rd)
        log.append((r.u.idx, rd, ev.done.get(rd[-1])))
    return log


def plan_day(S, units, prev, hour, E):
    """routes for every unit:
      a. bring-back days (day 6, user ruling): the hour-0 bring-back of each worker (its pens, then a drop at the shed)
         is fixed and followed as is; that worker's day plan starts after its drop;
      b. other days: the day's money jobs (produce) - kept from the previous plan, else inserted first - each with a drop;
      c. the land at the first tick the money (cash + shed sales + the drops of a / b) covers it;
      d. the rest of the previous plan (warm start, per unit in order), then every other job by cheapest insertion"""
    cfg = S.cfg
    S.routes = [Route(u) for u in units]
    by = {r.u.idx: r for r in S.routes}
    assigned = set()
    bb_day = cfg["money_first"] and S.day in [int(d) for d in cfg["bringback_days"]]
    if bb_day:
        if "bringback" not in E:
            E["bringback"] = {int(i): list(q) for i, q in money_segments(S, units).items()}
        bb = E["bringback"]
        for r in S.routes:
            seq = _live_bringback(S, r, bb.get(r.u.idx, []))
            bb[r.u.idx] = seq
            stops = seq_to_stops(S, seq)
            if stops:
                ev = eval_route(S, r, stops)
                if ev.ok:
                    S.commit(r, stops, ev)
                    r.fixed = len(stops)
                    assigned.update(k for k in seq if k != "RET")
    seqs = _warm_seqs(S, prev) if hour > 0 else {}
    if not bb_day:
        for r in S.routes:
            carrying = any(r.u.inv.get(g, 0) > 0 for g in S.mg)
            money = [k for k in seqs.get(r.u.idx, []) if k == "RET" or (k in S.jobs and S.jobs[k].kind == "money")]
            if carrying and (not money or money[0] != "RET"):
                money = ["RET"] + money
            left = rebuild_route(S, r, money)
            assigned.update(k for k in money if k != "RET" and k not in left)
        for k in insertion_order(S, [k for k, j in S.jobs.items() if j.kind == "money" and k not in assigned]):
            if insert_job(S, S.jobs[k]):
                assigned.add(k)
    S.land_dbg = dict(money=S.money, total=[round(S.total.at(t)) for t in range(S.h, 24)],
                      drops={r.u.idx: [(t, round(v)) for (t, v, s) in r.ev.events] for r in S.routes if r.ev.events})
    if S.land_q is not None:
        t0 = S.h
        if str(S.day) in (S.cfg["land_after_bb"] or {}) and int(S.cfg["land_after_bb"][str(S.day)]):
            drops = [t_ for r in S.routes for (t_, v_, s_) in r.ev.events if not s_ and v_ > 0]
            if drops:                                   # DSM day 8: the land after the bring-back's last drop
                t0 = max(t0, max(drops))
        t = S.total.earliest(t0, S.land_price)
        if t is not None:
            S.land_tick = t
            S.add_base(t, -S.land_price)
    rests = {r.u.idx: [k for k in seqs.get(r.u.idx, []) if (k == "RET" and _pen_rounds_on(S))
                       or (k != "RET" and k in S.jobs and S.jobs[k].kind != "money" and k not in assigned)]
             for r in S.routes}
    for idx in rests:                                  # pen rounds: a drop only after a job, never twice in a row
        q, out = rests[idx], []
        for k in q:
            if k == "RET" and (not out or out[-1] == "RET"):
                continue
            out.append(k)
        while out and out[-1] == "RET" and len(out) == 1:
            out.pop()
        rests[idx] = out
    kept = {k for q in rests.values() for k in q if k != "RET"}
    for idx in rests:
        rests[idx] = [k for k in rests[idx] if k == "RET" or not (S.jobs[k].extra.get("alt_of") in kept)]
    if any(rests.values()):
        warm_global(S, rests)
    for r in S.routes:
        left = rebuild_route(S, r, rests.get(r.u.idx, []))
        assigned.update(k for k in rests.get(r.u.idx, []) if k not in left)
        if not r.fixed and S.cfg["fix_first"]:
            r.fixed = 1 if r.stops else 0
    todo = [k for k in S.jobs if k not in assigned]
    if S.cfg["roles"] and hour == 0:
        placed0 = {s.key for r in S.routes for s in r.stops if s.kind == "job"}
        rp = role_plan2 if int(S.cfg["roles"]) == 2 else role_plan
        left = rp(S, [k for k in todo if S.jobs[k].kind != "money" and k not in placed0])
        E["round_keys"] = list(getattr(S, "round_keys", []))
        placed1 = {s.key for r in S.routes for s in r.stops if s.kind == "job"}
        assigned.update(placed1)
        todo = [k for k in todo if k not in placed1]
    for k in insertion_order(S, todo):
        alt = S.jobs[k].extra.get("alt_of")
        if alt is not None and alt in assigned:
            continue
        if insert_job(S, S.jobs[k]):
            assigned.add(k)
    for _ in range(3):
        back, S.evicted = S.evicted, []
        for k in insertion_order(S, [k for k in back if k in S.jobs]):
            insert_job(S, S.jobs[k])
        if not S.evicted:
            break
    budget = int(S.cfg["polish_h0"] if hour == 0 else S.cfg["polish_hour"])
    if budget > 0:
        polish(S, budget)
        placed = {s.key for r in S.routes for s in r.stops if s.kind == "job"}
        for k in insertion_order(S, [k for k in S.jobs if k not in placed]):
            alt = S.jobs[k].extra.get("alt_of")
            if alt is not None and alt in placed:
                continue
            if insert_job(S, S.jobs[k]):
                placed.add(k)
    return by


def _fib_cost(n):
    """engine hire cost of the n-th hire of the day (fib, n = hires already made today)"""
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _key_tile(k):
    idx = int("".join(ch for ch in k if ch.isdigit()) or -1)
    return (idx % 10, idx // 10) if idx >= 0 else None


# ------------------------------------------------------------------------------------------------ the step
def e68_step(obs, plan, cfg_in, E):
    e911 = (cfg_in or {}).get("e911")
    if e911 and int(obs.get("step", 0)) // 24 in [int(d) for d in e911.get("days", [9, 10])]:
        import importlib                                # days 9-11 by another executor module (full assembly)
        mod = importlib.import_module(e911.get("module", "exec_e68_mc_20260930"))
        out = mod.e68_step(obs, plan, e911.get("cfg") or {}, _E911_STATE)
        E["diag"] = _E911_STATE.get("diag")
        return out
    if (cfg_in or {}).get("playbook") or (cfg_in or {}).get("playbook_lib"):
        return pb_step(obs, plan, cfg_in, E)
    cfg = dict(DEFAULTS)
    cfg.update(cfg_in or {})
    step = int(obs.get("step", 0))
    day, hour = divmod(step, 24)
    me = int(obs.get("player", 0))
    farm = obs["farms"][me]
    priv = obs.get("private") or {}
    if E.get("day") != day:
        E.clear()
        E.update(day=day, prev={}, log=Counter(), diag={"day": day}, hours={})
        try:
            E["hands_want"] = int(plan.hands[day])
        except Exception:
            E["hands_want"] = len(farm.get("hands") or [])
    jobs = derive_jobs(obs, plan, day, cfg)
    for k in E.get("round_keys", ()):
        if k in jobs:
            jobs[k].extra["round"] = True
    pby = (cfg["pen_by"] or {}).get(str(day))
    if pby is not None and hour + 1 < int(pby):
        for j in jobs.values():
            if j.kind in ("feed", "care"):
                j.extra["by"] = int(pby)
    tiles = farm["tiles"]
    for k in [k for k, j in jobs.items() if job_done(j, tiles, day)]:
        del jobs[k]
    S = Sim(obs, plan, day, hour, cfg, jobs)
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in (farm.get("hands") or [])]
    invs = list(priv.get("inventories") or [])
    units = [Unit(i, p, hour, {k: int(v) for k, v in (invs[i] if i < len(invs) else {}).items() if v})
             for i, p in enumerate(pos)]
    n_hire = max(0, int(E["hands_want"]) - (len(pos) - 1)) if hour <= 1 else 0
    if hour == 0 and n_hire:
        hc = sum(_fib_cost(int(farm.get("hires_today", 0) or 0) + k) for k in range(n_hire))
        n_sell = sum(1 for g in SELLABLE if int((priv.get("shed") or {}).get(g, 0) or 0) > 0)
        if float(farm.get("money", 0) or 0) < hc:
            n_hire = min(n_hire, max(0, 10 - n_sell))
    # shed stock sells this tick (at hour 1 when hour 0's ten order slots go to the hires)
    if S.shed_goods:
        S.add_base(hour + 1 if (hour == 0 and cfg["hire_first_h0"] and n_hire >= 10) else hour, S.sale(S.shed_goods))
    hires = []
    if n_hire:
        occ = list(pos)
        if hour == 0 and cfg["money_first"] and cfg["farmer_h0"]:
            # the farmer's first move this hour sets his tile before the hires spawn (engine order)
            seq = money_segments(S, units[:1]).get(0, [])
            first = next((k for k in seq if k != "RET"), None)
            if first is not None:
                mv = step_toward(pos[0], S.jobs[first].tile)
                if mv:
                    occ[0] = moved(pos[0], mv)
        elif hour == 0:
            units[0].t = 1                              # the farmer holds (4,4) while the hires spawn
        for k in range(n_hire):
            s = spawn_tile(occ)
            occ.append(s)
            units.append(Unit(len(pos) + k, s, hour + 1, {}))
            hires.append(s)
    prev = {int(k): v for k, v in (E.get("prev") or {}).items()}
    if cfg["order_cap"]:
        n_sell_now = sum(1 for g in SELLABLE if int((priv.get("shed") or {}).get(g, 0) or 0) > 0)
        n_land_now = 1 if S.land_q is not None else 0     # the land may take a slot this tick
        S.buy_slots_now = max(0, 10 - len(hires) - n_sell_now - n_land_now)
    by = plan_day(S, units, prev, hour, E)
    n_hands = len(farm.get("hands") or [])
    acts = []
    for i in range(1 + n_hands):
        r = by.get(i)
        acts.append(next((a for (t, a) in r.ev.steps if t == hour), ["PASS"]) if r is not None else ["PASS"])
    E["prev"] = {r.u.idx: [s.key if s.kind == "job" else "RET" for s in r.stops if s.kind in ("job", "drop")]
                 for r in S.routes}
    seeds = Counter({k: int(v) for k, v in (priv.get("seeds") or {}).items() if v})
    ask = Counter(a[1] for a in acts if a and a[0] == "PLANT")
    for crop, n in ask.items():
        if n > seeds.get(crop, 0):                    # the atomic PLANT rule: never more PLANTs than seeds in stock
            keep = seeds.get(crop, 0)
            for i, a in enumerate(acts):
                if a and a[0] == "PLANT" and a[1] == crop:
                    if keep > 0:
                        keep -= 1
                    else:
                        acts[i] = ["PASS"]
                        E["log"]["plant_blocked"] += 1
    shed = Counter({k: int(v) for k, v in (priv.get("shed") or {}).items() if v})
    dropped = Counter()
    for i, a in enumerate(acts):
        if a and a[0] == "DROP" and i < len(invs):
            for g, n in (invs[i] or {}).items():
                dropped[g] += int(n)
    sells = [["SELL", g, shed.get(g, 0) + dropped.get(g, 0)] for g in SELLABLE if shed.get(g, 0) + dropped.get(g, 0) > 0]
    hire_orders = [["HIRE"] for _ in hires]
    land = [["BUY_LAND"]] if S.land_tick is not None and S.land_tick == hour else []
    buys = Counter()
    for r in S.routes:
        for (t, o) in r.ev.buys:
            if t == hour:
                buys[(o[0], o[1])] += int(o[2])
    pbw = (cfg["prebuy_wheat"] or {}).get(str(day))
    if pbw is not None and hour == 23:
        have = int((priv.get("shed") or {}).get("WHEAT", 0) or 0) \
            + sum(int((i or {}).get("WHEAT", 0) or 0) for i in (priv.get("inventories") or []))
        n_anim = sum(1 for row in tiles for t_ in row if isinstance(t_, dict) and t_.get("animal"))
        want = max(0, min(int(pbw), n_anim) - have - buys.get(("BUY_PRODUCT", "WHEAT"), 0))
        unit = S.unit_cost("WHEAT")
        cash_left = S.total.at(23)
        n_pb = int(min(want, max(0.0, cash_left) // max(1.0, unit)))
        if n_pb > 0:
            buys[("BUY_PRODUCT", "WHEAT")] += n_pb
            E["log"]["prebuy_wheat"] += n_pb
    order_rank = {"BUY_ANIMAL": 0, "BUY_SEED": 1, "BUY_PRODUCT": 2}
    buy_orders = [[k[0], k[1], n] for k, n in sorted(buys.items(), key=lambda kv: (order_rank[kv[0][0]], kv[0][1]))]
    hire_cost = sum(_fib_cost(int(farm.get("hires_today", 0) or 0) + k) for k in range(len(hire_orders)))
    if hour == 0 and cfg["hire_first_h0"] and S.money >= hire_cost:
        market = hire_orders + sells + land + buy_orders
    else:                                              # the sales pay for the hires (the engine runs orders by index)
        market = sells + hire_orders + land + buy_orders
    if len(market) > 10:
        E["log"]["mk_cut"] += len(market) - 10
    market = market[:10]
    lg = E["log"]
    for a in acts:
        lg["op:" + a[0]] += 1
    for o in market:
        lg[("mk:%s:%s" % (o[0], o[1])) if len(o) > 2 else ("mk:" + o[0])] += int(o[2]) if len(o) > 2 else 1
    unplaced = sorted(k for k in jobs if not any(s.kind == "job" and s.key == k for r in S.routes for s in r.stops))
    if hour == 0:
        E["diag"]["roles"] = getattr(S, "role_log", None)
        E["diag"].update(jobs=dict(Counter(j.kind for j in jobs.values())), land_q=S.land_q, land_plan_h=S.land_tick,
                         hires=len(hires), cash0=S.money, cash_proj=[round(S.total.at(t)) for t in range(hour, 24)],
                         unassigned=unplaced[:40], why={k: S.why.get(k) for k in unplaced[:40]})
        if cfg["log_plans"]:
            E["diag"]["plans"] = {r.u.idx: [(t, a) for (t, a) in r.ev.steps] for r in S.routes}
    if cfg["log_hours"]:
        E["hours"][hour] = dict(acts=[a[0][:5] + (":" + str(a[1])[:3] if len(a) > 1 else "") for a in acts],
                                market=market, land_tick=S.land_tick, land_dbg=getattr(S, "land_dbg", None), open=unplaced[:30],
                                why={k: S.why.get(k) for k in unplaced[:30]},
                                why_all={k: dict(S.why_all.get(k, {})) for k in unplaced[:30]},
                                first={r.u.idx: E["prev"].get(r.u.idx, [])[:3] for r in S.routes},
                                proj=[round(S.total.at(t)) for t in range(hour, 24)],
                                soft=[round(sum(S.total.soft[hour:t + 1])) for t in range(hour, 24)],
                                buys=[(r.u.idx, t, o) for r in S.routes for (t, o) in r.ev.buys],
                                drops=[(r.u.idx, t, round(v)) for r in S.routes for (t, v, s) in r.ev.events if not s],
                                placed=sorted(k for r in S.routes for s in r.stops if s.kind == "job" for k in [s.key]),
                                fin={s.key: r.ev.done.get(s.key) for r in S.routes for s in r.stops if s.kind == "job"},
                                jobs_all=sorted(jobs),
                                seqs={r.u.idx: E["prev"].get(r.u.idx, []) for r in S.routes},
                                ends={r.u.idx: (r.ev.end if r.ev.ok and r.stops else None) for r in S.routes},
                                why_every={k: dict(S.why_all.get(k, {})) for k in unplaced})
        E["diag"]["hours"] = E["hours"]
    E["diag"]["log"] = dict(lg)
    return {"farmer": acts[0], "hands": acts[1:], "market": market}


# ---------------------------------------------------------------------------------------------------------------------
# Playbook mode (user 2026-09-30: deterministic playbooks instead of the route planner; "if we can't control exact
# action, at least plan out routes for each hand"). A playbook gives, per day and hand, DSM's route: the tiles it visits
# in order and the commands it issued on each (scripts pb_extract.py). The executor walks each hand to its next tile,
# checks every command against the tile before issuing it (a weed gets a DIG, a command that would no-op is skipped),
# buys seeds / animals / wheat one tick before they are needed, sells the shed every tick, hires as the playbook does,
# buys the land at the playbook's land hour (retrying until it goes through). Cash safeguard (user): a purchase that
# stays unaffordable for pb_cash_wait ticks cuts the last planting from the end of that hand's route.
# ---------------------------------------------------------------------------------------------------------------------
_PB_CACHE = {}
_E911_STATE = {}
SHOP_DEMAND = {"BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
               "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"], "YARN_STORE": ["WOOL"],
               "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
               "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"], "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"]}
_SEM_LABEL = {"STRAWBERRY": "ST", "MELON": "ME", "WHEAT": "WH", "CARROT": "CA", "TOMATO": "TO", "COW": "co", "SHEEP": "sh",
              "GOOSE": "go"}


def _pb_label(t):
    if t == "LOCKED":
        return " L"
    if isinstance(t, dict):
        if t.get("animal"):
            return _SEM_LABEL.get(t["animal"], " .")
        if t.get("kind") == "PLANT":
            return _SEM_LABEL.get(t.get("crop"), " .")
    return " ."


def _pb_select_day(games, day, shops, labels, current=None, exclude=None):
    """daily re-selection (days 0-8): the revealed shops in order, the demand pattern once two are out, the closest demand,
    the closest board at the previous dusk (library dusk boards), staying on the current game on ties; day 0 (nothing
    revealed, no board yet) keeps to the games whose day-0 routes are the majority"""
    sh_me = list(shops)

    def dem(sh):
        return Counter(g for s in sh if s in SHOP_DEMAND for g in SHOP_DEMAND[s])

    def pattern(sh):
        d = dem(sh)
        return (d["STRAWBERRY"] > 0, d["WOOL"] > 0, d["CARROT"] >= 2)
    cands = [e for e in games if str(e) != str(exclude)]
    if day == 0:
        import json as _json
        sig = Counter(_json.dumps(games[e]["days"].get("0", {}).get("units")) for e in cands)
        top = sig.most_common(1)[0][0] if sig else None
        cands = [e for e in cands if _json.dumps(games[e]["days"].get("0", {}).get("units")) == top] or cands
    dm = dem(sh_me)
    n = len(sh_me)

    def key(e):
        g = games[e]
        sh = list(g["shops"])[:n]
        dg = dem(sh)
        mism = tuple(sh[i] != sh_me[i] if i < len(sh) else True for i in range(n))
        pat = (pattern(sh) != pattern(sh_me)) if n >= 2 else False
        prev = (g.get("boards") or {}).get(str(day - 1))
        bd = sum(1 for a, b in zip(prev, labels) if a != b) if (prev and day > 0) else 0
        return mism + (pat, sum(abs(dg[x] - dm[x]) for x in set(dg) | set(dm)), bd, str(e) != str(current), str(e))
    return min(cands, key=key) if cands else None


def _pb_select(games, shops, labels, exclude=None, prefer_cash=False):
    """library playbook for this world (user 2026-09-30): the same day-3 shop (same opening / handoff), the same day-6
    shop, the same demand pattern (strawberry / wool / two carrot shops), the closest demand, the closest day-5 board"""
    me = (list(shops) + [None, None])[:2]

    def dem(sh):
        return Counter(g for s in sh if s in SHOP_DEMAND for g in SHOP_DEMAND[s])

    def pattern(sh):
        d = dem(sh)
        return (d["STRAWBERRY"] > 0, d["WOOL"] > 0, d["CARROT"] >= 2)
    dm, pm = dem(me), pattern(me)

    def key(e):
        g = games[e]
        sh = (list(g["shops"]) + [None, None])[:2]
        dg = dem(sh)
        return (sh[0] != me[0], sh[1] != me[1], pattern(sh) != pm,
                sum(abs(dg[x] - dm[x]) for x in set(dg) | set(dm)),
                (lambda bd_: bd_ // 4 if prefer_cash else bd_)(sum(1 for a, b in zip(g.get("b5") or [], labels) if a != b)),
                -float(g.get("dsm_cash") or 0) if prefer_cash else 0.0, e)
    cands = [e for e in games if str(e) != str(exclude)]
    return min(cands, key=key) if cands else None


def _pb_load(path):
    if path not in _PB_CACHE:
        import json as _json
        import os as _os
        p = path
        if not _os.path.isabs(p):
            here = _os.path.dirname(_os.path.abspath(__file__))
            for base in (here, _os.path.dirname(here), _os.getcwd()):
                if _os.path.exists(_os.path.join(base, path)):
                    p = _os.path.join(base, path)
                    break
        if p.endswith(".gz"):
            import gzip as _gzip
            with _gzip.open(p, "rt", encoding="utf-8") as f:
                _PB_CACHE[path] = _json.load(f)
        else:
            with open(p) as f:
                _PB_CACHE[path] = _json.load(f)
    return _PB_CACHE[path]


def _pb_tile(tiles, p):
    return tiles[p[1]][p[0]]


def _pb_valid(op, t, inv, shed_left, day):
    """(issue, fix): issue = the command can do something now; fix = a command to issue first instead (DIG / build)"""
    k = op[0]
    if k == "PLANT":
        if t == "LOCKED":
            return "wait", None
        if isinstance(t, dict) and t.get("kind") == "WEED":
            return "fix", ["DIG"]
        if isinstance(t, dict):
            if t.get("kind") == "PLANT" and t.get("crop") == op[1] and int(t.get("planted_day", -1)) == day:
                return "skip", None                       # planted already
            if t.get("animal"):
                return "skip", None
            return "fix", ["DIG"]                         # an old crop or an empty structure
        return "ok", None
    if k == "WATER":
        return ("ok", None) if isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today") else ("skip", None)
    if k == "FERTILIZE":
        return ("ok", None) if isinstance(t, dict) and t.get("kind") == "PLANT" and inv.get("FERTILIZER", 0) > 0 else ("skip", None)
    if k == "HARVEST":
        return ("ok", None) if isinstance(t, dict) and int(t.get("yield_units", 0) or 0) > 0 else ("skip", None)
    if k == "FEED":
        ok = isinstance(t, dict) and t.get("animal") and not t.get("fed_today") and inv.get("WHEAT", 0) > 0
        return ("ok", None) if ok else ("skip", None)
    if k == "CARE":
        return ("ok", None) if isinstance(t, dict) and t.get("animal") and not t.get("cared_today") else ("skip", None)
    if k == "COLLECT_FERTILIZER":
        return ("ok", None) if isinstance(t, dict) and t.get("animal") and t.get("fertilizer_available") else ("skip", None)
    if k == "DIG":
        if t is None or t == "LOCKED":
            return "skip", None
        if isinstance(t, dict) and t.get("animal"):
            return "skip", None
        return "ok", None
    if k in ("BUILD_COOP", "BUILD_PASTURE"):
        want = "COOP" if k == "BUILD_COOP" else "PASTURE"
        if t == "LOCKED":
            return "wait", None
        if isinstance(t, dict) and t.get("kind") == want:
            return "skip", None
        if isinstance(t, dict):
            return ("fix", ["DIG"]) if not t.get("animal") else ("skip", None)
        return "ok", None
    if k == "PLACE":
        item = op[1] if len(op) > 1 else None
        if item in ANIMALS:
            want = ANIMALS[item]["structure"]
            if inv.get(item, 0) <= 0:
                return "skip", None
            if t == "LOCKED":
                return "wait", None
            if isinstance(t, dict) and t.get("kind") == want and not t.get("animal"):
                return "ok", None
            if t is None:
                return "fix", ["BUILD_" + want]
            return "skip", None
        return ("ok", None) if inv.get(item, 0) > 0 else ("skip", None)      # shed deposit
    if k == "DROP":
        return ("ok", None) if any(v > 0 for v in inv.values()) else ("skip", None)
    if k == "PICKUP":
        return "pick", None
    return "ok", None


def _pb_next_places(r, vi, oi, animal, n):
    """the tiles of the next n PLACE <animal> commands in route r after command (vi, oi)"""
    out, first = [], True
    for j in range(vi, len(r)):
        for k in range(oi + 1 if first else 0, len(r[j]["ops"])):
            o = r[j]["ops"][k]
            if o[0] == "PLACE" and len(o) > 1 and o[1] == animal:
                out.append(tuple(r[j]["tile"]))
                if len(out) >= n:
                    return out
        first = False
    return out


def _pb_next_place(r, vi, oi, animal):
    """the tile of the next PLACE <animal> in route r after command (vi, oi), or None"""
    first = True
    for j in range(vi, len(r)):
        for k in range(oi + 1 if first else 0, len(r[j]["ops"])):
            o = r[j]["ops"][k]
            if o[0] == "PLACE" and len(o) > 1 and o[1] == animal:
                return tuple(r[j]["tile"])
        first = False
    return None


def pb_step(obs, plan, cfg_in, E):
    cfg = dict(DEFAULTS)
    cfg.update(cfg_in or {})
    step = int(obs.get("step", 0))
    day, hour = divmod(step, 24)
    me = int(obs.get("player", 0))
    farm = obs["farms"][me]
    priv = obs.get("private") or {}
    tiles = farm["tiles"]
    if cfg.get("playbook_lib"):
        games = _pb_load(cfg["playbook_lib"])["games"]
        sel = E.get("pb_sel")
        daily = bool(cfg["pb_daily_select"])
        if sel is None or sel not in games or (daily and E.get("pb_sel_day") != day):
            import os as _os
            shops = list(((obs.get("town") or {}).get("unlocked_shops")) or [])
            labels = [_pb_label(tiles[k // 10][k % 10]) for k in range(100)]
            excl = _os.environ.get(cfg["pb_exclude_env"]) if cfg["pb_exclude_env"] else None
            if daily:
                sel = _pb_select_day(games, day, shops, labels, current=sel, exclude=excl)
            else:
                sel = _pb_select(games, shops, labels, excl, bool(cfg["pb_prefer_cash"]))
            E["pb_sel"] = sel
            E["pb_sel_day"] = day
        pb = games.get(sel) or {"days": {}}
    else:
        pb = _pb_load(cfg["playbook"])
    dayp = (pb.get("days") or {}).get(str(day))
    if E.get("pb_day") != day:
        keep_sel, keep_day = E.get("pb_sel"), E.get("pb_sel_day")
        E.clear()
        E.update(pb_day=day, log=Counter(), diag={"day": day, "mode": "playbook", "sel": keep_sel})
        if keep_sel is not None:
            E["pb_sel"] = keep_sel
            E["pb_sel_day"] = keep_day
        E["routes"] = {int(i): [dict(tile=tuple(v["tile"]), ops=[list(o) for o in v["ops"]], t=int(v.get("t", 0))) for v in vl]
                       for i, vl in ((dayp or {}).get("units") or {}).items()}
        E["ptr"] = {i: [0, 0] for i in E["routes"]}
        E["wait"] = Counter()
        E["claimed"] = set()                           # pb_place_check: tiles a carried / bought animal is meant for
        E["lockwait"] = Counter()
        E["land_done"] = False
        E["owned_n"] = len(list(farm.get("unlocked_quadrants") or ["NW"]))
    lg = E["log"]
    if dayp is None:
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in (farm.get("hands") or [])], "market": []}
    money = float(farm.get("money", 0) or 0)
    prices = dict((obs.get("market") or {}).get("prices") or {})
    shed = Counter({k: int(v) for k, v in (priv.get("shed") or {}).items() if v})
    seeds = Counter({k: int(v) for k, v in (priv.get("seeds") or {}).items() if v})
    invs = [Counter({k: int(v) for k, v in (i or {}).items() if v}) for i in (priv.get("inventories") or [])]
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in (farm.get("hands") or [])]

    def remaining(h):
        r_ = E["routes"].get(h) or []
        return sum(len(v["ops"]) + 1 for v in r_[E["ptr"][h][0]:]) if h in E["ptr"] else 0
    # orphan routes: hands the playbook has but the day's hires did not deliver (cash) - their visits go to the hands
    # with the least work left, merged by DSM's visit hours (a missing hand's waterings / feeds are not lost)
    if cfg["pb_orphans"] and hour >= 2 and not E.get("orphans_done"):
        E["orphans_done"] = True
        n_units = len(pos)
        for i in sorted(k for k in E["routes"] if k >= n_units):
            rest = E["routes"][i][E["ptr"][i][0]:]
            if not rest:
                continue
            host = min(range(n_units), key=lambda h: (remaining(h), h))
            if host not in E["routes"]:
                E["routes"][host], E["ptr"][host] = [], [0, 0]
            r_h = E["routes"][host]
            vi_h = E["ptr"][host][0]
            head, tail = r_h[:vi_h + 1], r_h[vi_h + 1:]
            E["routes"][host] = head + sorted(tail + [dict(v) for v in rest], key=lambda v: v.get("t", 0))
            E["routes"][i] = []
            lg["orphan_visits"] += len(rest)
    # keep-alive: late in the day a crop that dies tonight without water and is on nobody's remaining route goes to the
    # nearest hand, right after its current visit
    kah = cfg["pb_keepalive_hour"]
    if kah is not None and hour >= int(kah):
        planned = set()                            # waterings / plantings a hand reaches by hour 22 (walk + commands)
        for h, r_ in E["routes"].items():
            if h >= len(pos):
                continue
            eta, p_ = hour, pos[h]
            for j, v in enumerate(r_[E["ptr"][h][0]:]):
                eta += dist(p_, tuple(v["tile"])) + (len(v["ops"]) - (E["ptr"][h][1] if j == 0 else 0))
                p_ = tuple(v["tile"])
                if eta <= 22 and any(o[0] in ("WATER", "PLANT") for o in v["ops"]):
                    planned.add(p_)
        done_ka = E.setdefault("ka_tiles", set())
        for y_ in range(10):
            for x_ in range(10):
                t_ = tiles[y_][x_]
                if not (isinstance(t_, dict) and t_.get("kind") == "PLANT") or t_.get("watered_today"):
                    continue
                risk = int(t_.get("consecutive_unwatered", 0) or 0) >= 1 or int(t_.get("planted_day", -1)) == day
                if not risk or (x_, y_) in planned or (x_, y_) in done_ka:
                    continue
                host = min(range(len(pos)), key=lambda h: (min(remaining(h), 8) + dist(pos[h], (x_, y_)), h))
                if host not in E["routes"]:
                    E["routes"][host], E["ptr"][host] = [], [0, 0]
                r_h = E["routes"][host]
                vi_h, oi_h = E["ptr"][host]
                at = vi_h + 1 if (vi_h < len(r_h) and oi_h > 0) else vi_h
                r_h.insert(at, dict(tile=(x_, y_), ops=[["WATER"]], t=hour))
                done_ka.add((x_, y_))
                lg["keepalive_water"] += 1
    wait_max = int(cfg["pb_cash_wait"])
    # market plan of this tick: sells of the shed (dropped goods added below), hires, land
    n_hire = int((dayp.get("hires") or [0] * 24)[hour]) if hour < len(dayp.get("hires") or []) else 0
    hire_cost = sum(_fib_cost(int(farm.get("hires_today", 0) or 0) + k) for k in range(n_hire))
    owned = list(farm.get("unlocked_quadrants") or ["NW"])
    if len(owned) > E["owned_n"]:
        E["land_done"] = True                          # the day's land went through (one quadrant a day at most)
    land_q = LAND_ORDER[len(owned) - 1] if len(owned) - 1 < len(LAND_ORDER) else None
    land_price = LAND_PRICES[len(owned) - 1] if land_q is not None else 0
    land_orders = dayp.get("land_orders") or []
    want_land = bool(land_orders) and hour >= min(land_orders) and land_q is not None and not E["land_done"]

    def sale(goods):
        return sum(float(prices.get(g, 0) or 0) * n * 0.9 for g, n in goods.items() if g in SELLABLE)
    shed_sell = {g: n for g, n in shed.items() if g in SELLABLE}
    budget = money + sale(shed_sell) - hire_cost - (land_price if want_land and money + sale(shed_sell) - hire_cost >= land_price else 0)
    if cfg["pb_drop_cash"]:                            # goods the hands drop this tick are sold in the same market
        for i_, p_ in enumerate(pos):
            r_ = E["routes"].get(i_)
            if not r_ or E["ptr"][i_][0] >= len(r_):
                continue
            v_ = r_[E["ptr"][i_][0]]
            oi_ = E["ptr"][i_][1]
            if p_ != v_["tile"] or oi_ >= len(v_["ops"]):
                continue
            op_ = v_["ops"][oi_]
            inv_ = invs[i_] if i_ < len(invs) else Counter()
            if op_[0] == "DROP":
                budget += sale({g: n for g, n in inv_.items() if g in SELLABLE})
            elif op_[0] == "PLACE" and len(op_) > 1 and op_[1] in SELLABLE:
                budget += sale({op_[1]: min(int(op_[2]) if len(op_) > 2 else 1, inv_.get(op_[1], 0))})
    buys = Counter()                                   # (order, item) -> n this tick
    spent = [0.0]
    shed_left = Counter(shed)
    plants_now = Counter()

    def afford(cost):
        return budget - spent[0] - cost >= -1e-6

    def buy(kind, item, n, cost):
        buys[(kind, item)] += n
        spent[0] += cost

    def pickup_useful(i, vi, oi, animal):
        if not cfg["pb_place_check"]:
            return True
        tgt = _pb_next_place(E["routes"][i], vi, oi, animal)
        if tgt is None or tgt in E["claimed"]:
            return False
        t_ = tiles[tgt[1]][tgt[0]]
        return not (isinstance(t_, dict) and t_.get("animal"))

    def cut_last_plant(i):
        r = E["routes"].get(i) or []
        vi = E["ptr"][i][0]
        for j in range(len(r) - 1, vi, -1):
            if any(o[0] == "PLANT" for o in r[j]["ops"]):
                E["diag"].setdefault("events", []).append((hour, i, "cut", [o[1] for o in r[j]["ops"] if o[0] == "PLANT"], tuple(r[j]["tile"])))
                del r[j]
                lg["cut_plant"] += 1
                return True
        return False

    acts_by = {}
    dropped = Counter()

    def visit_t(i):
        r_ = E["routes"].get(i)
        if not r_ or E["ptr"][i][0] >= len(r_):
            return 99
        return r_[E["ptr"][i][0]].get("t", 0)
    order = sorted(range(len(pos)), key=lambda i: (visit_t(i), i)) if cfg["pb_dsm_order"] else list(range(len(pos)))
    for i in order:
        p = pos[i]
        inv = invs[i] if i < len(invs) else Counter()
        r = E["routes"].get(i)
        act = ["PASS"]
        if r is None:
            acts_by[i] = act
            lg["no_route"] += 1
            continue
        for _guard in range(12):
            vi, oi = E["ptr"][i]
            if vi >= len(r):
                lg["route_done"] += 1
                break
            v = r[vi]
            if oi >= len(v["ops"]):
                E["ptr"][i] = [vi + 1, 0]
                continue
            if p != v["tile"]:
                act = [step_toward(p, v["tile"])]
                # just in time: buy what the first command on arrival needs
                if dist(p, v["tile"]) == 1:
                    op0 = v["ops"][oi]
                    if op0[0] == "PLANT" and seeds[op0[1]] - plants_now[op0[1]] <= 0:
                        c = float(CROPS[op0[1]]["seed"])
                        if afford(c):
                            buy("BUY_SEED", op0[1], 1, c)
                    elif op0[0] == "PICKUP" and op0[1] in ANIMALS and shed_left[op0[1]] <= 0                             and pickup_useful(i, vi, oi, op0[1]):
                        c = float(ANIMALS[op0[1]]["cost"])
                        if afford(c):
                            buy("BUY_ANIMAL", op0[1], 1, c)
                    elif op0[0] == "PICKUP" and op0[1] == "WHEAT" and cfg["pb_wheat_ahead"]:
                        need = int(op0[2]) if len(op0) > 2 else 1
                        short = need - shed_left["WHEAT"] - buys.get(("BUY_PRODUCT", "WHEAT"), 0)
                        if short > 0:
                            c = short * (float(prices.get("WHEAT", 30) or 30) + 2)
                            if afford(c):
                                buy("BUY_PRODUCT", "WHEAT", short, c)
                break
            op = v["ops"][oi]
            t = _pb_tile(tiles, p)
            st, fix = _pb_valid(op, t, inv, shed_left, day)
            if st == "skip":
                lg["skip:" + op[0]] += 1
                E["ptr"][i] = [vi, oi + 1]
                continue
            if st == "wait":
                E["lockwait"][i] += 1
                if E["lockwait"][i] > int(cfg["pb_lock_wait"]):
                    lg["skip_locked"] += 1
                    E["ptr"][i] = [vi + 1, 0]
                    E["lockwait"][i] = 0
                    continue
                lg["wait_locked"] += 1
                act = ["PASS"]
                break
            if st == "fix":
                act = fix
                lg["fix:" + fix[0]] += 1
                break
            if st == "pick" and op[1] in ANIMALS and cfg["pb_multi_place"] and cfg["pb_place_check"]:
                n_req = int(op[2]) if len(op) > 2 else 1
                tg = [t_ for t_ in _pb_next_places(r, vi, oi, op[1], 99) if t_ not in E["claimed"]
                      and not (isinstance(tiles[t_[1]][t_[0]], dict) and tiles[t_[1]][t_[0]].get("animal"))][:n_req]
                if not tg and not (cfg["pb_place_free"] and shed_left[op[1]] > 0):
                    lg["skip:PICKUP_" + op[1]] += 1
                    E["ptr"][i] = [vi, oi + 1]
                    continue
                if tg and len(tg) < n_req:
                    op = ["PICKUP", op[1], len(tg)]              # only as many as there are free structures
                    v["ops"][oi] = op
            elif st == "pick" and op[1] in ANIMALS and not (cfg["pb_place_free"] and shed_left[op[1]] > 0)                     and not pickup_useful(i, vi, oi, op[1]):
                lg["skip:PICKUP_" + op[1]] += 1
                E["ptr"][i] = [vi, oi + 1]
                continue
            if st == "pick":
                item, n = op[1], int(op[2]) if len(op) > 2 else 1
                have = shed_left[item]
                if have >= n or (item not in ANIMALS and item != "WHEAT" and have > 0):
                    act = ["PICKUP", item, min(n, have)]
                    shed_left[item] -= min(n, have)
                    if item in ANIMALS and cfg["pb_place_check"]:
                        free_t = [t_ for t_ in _pb_next_places(r, vi, oi, item, 99) if t_ not in E["claimed"]
                                  and not (isinstance(tiles[t_[1]][t_[0]], dict) and tiles[t_[1]][t_[0]].get("animal"))]
                        for tgt in free_t[:(min(n, have) if cfg["pb_multi_place"] else 1)]:
                            E["claimed"].add(tgt)
                    E["ptr"][i] = [vi, oi + 1]
                    break
                short = n - have
                c = short * (float(ANIMALS[item]["cost"]) if item in ANIMALS else float(prices.get(item, 30) or 30) + 2)
                if item in ANIMALS or item == "WHEAT":
                    if afford(c):
                        buy("BUY_ANIMAL" if item in ANIMALS else "BUY_PRODUCT", item, short, c)
                        E["wait"][i] = 0
                        if have > 0 and item == "WHEAT":
                            act = ["PICKUP", item, have]  # take what is there, the rest next tick
                            shed_left[item] -= have
                            v["ops"][oi] = ["PICKUP", item, short]
                        else:
                            act = ["PASS"]
                        lg["jit_wait"] += 1
                        break
                    E["wait"][i] += 1
                    if E["wait"][i] > wait_max or have > 0:
                        if have > 0:
                            act = ["PICKUP", item, have]
                            shed_left[item] -= have
                        lg["pick_short"] += 1
                        E["ptr"][i] = [vi, oi + 1]
                        E["wait"][i] = 0
                        break
                    act = ["PASS"]
                    lg["cash_wait"] += 1
                    E["diag"].setdefault("events", []).append((hour, i, "cash_wait", item, round(budget - spent[0]), round(c)))
                    break
                lg["skip:PICKUP"] += 1
                E["ptr"][i] = [vi, oi + 1]
                continue
            if op[0] == "PLANT" and cfg["pb_no_late_plant"] and hour >= 23:
                lg["skip_late_plant"] += 1                 # no water left today: the seedling would be a weed tonight
                E["ptr"][i] = [vi, oi + 1]
                continue
            if op[0] == "PLANT":
                crop = op[1]
                if seeds[crop] - plants_now[crop] <= 0:
                    c = float(CROPS[crop]["seed"])
                    if afford(c):
                        buy("BUY_SEED", crop, 1, c)
                        E["wait"][i] = 0
                        act = ["PASS"]
                        lg["jit_wait"] += 1
                        break
                    E["wait"][i] += 1
                    if E["wait"][i] > wait_max:              # cash safeguard: drop the last planting of this route
                        E["wait"][i] = 0
                        if not cut_last_plant(i):
                            lg["cut_plant"] += 1
                            E["ptr"][i] = [vi + 1, 0]    # this is the last one: skip it
                            continue
                    act = ["PASS"]
                    lg["cash_wait"] += 1
                    E["diag"].setdefault("events", []).append((hour, i, "cash_wait", op[1], round(budget - spent[0]), c))
                    break
                plants_now[crop] += 1
            act = list(op)
            if op[0] == "DROP":
                for g, n in inv.items():
                    dropped[g] += n
            elif op[0] == "PLACE" and op[1] not in ANIMALS:
                dropped[op[1]] += min(int(op[2]) if len(op) > 2 else 1, inv.get(op[1], 0))
                act = ["PLACE", op[1], min(int(op[2]) if len(op) > 2 else 1, inv.get(op[1], 0))]
            E["ptr"][i] = [vi, oi + 1]
            # just in time: the next command on this tile needs a purchase
            nxt = v["ops"][oi + 1] if oi + 1 < len(v["ops"]) else None
            if nxt is not None and nxt[0] == "PLANT" and seeds[nxt[1]] - plants_now[nxt[1]] <= 0:
                c = float(CROPS[nxt[1]]["seed"])
                if afford(c):
                    buy("BUY_SEED", nxt[1], 1, c)
            break
        lg["op:" + act[0]] += 1
        acts_by[i] = act
    acts = [acts_by.get(i, ["PASS"]) for i in range(len(pos))]
    # market: sells (shed + this tick's drops), hires, land, purchases; the engine runs orders by index
    sells = [["SELL", g, shed.get(g, 0) + dropped.get(g, 0)] for g in SELLABLE if shed.get(g, 0) + dropped.get(g, 0) > 0]
    hire_orders = [["HIRE"] for _ in range(n_hire)]
    land = [["BUY_LAND"]] if want_land else []
    order_rank = {"BUY_ANIMAL": 0, "BUY_SEED": 1, "BUY_PRODUCT": 2}
    buy_orders = [[k[0], k[1], n] for k, n in sorted(buys.items(), key=lambda kv: (order_rank[kv[0][0]], kv[0][1]))]
    if money >= hire_cost:
        market = hire_orders + sells + land + buy_orders
    else:
        market = sells + hire_orders + land + buy_orders
    if len(market) > 10:
        lg["mk_cut"] += len(market) - 10
    market = market[:10]
    if any(o[0] == "BUY_LAND" for o in market):
        lg["land_order"] += 1
    for o in market:
        lg[("mk:%s:%s" % (o[0], o[1])) if len(o) > 2 else ("mk:" + o[0])] += int(o[2]) if len(o) > 2 else 1
    E["diag"]["log"] = dict(lg)
    return {"farmer": acts[0], "hands": acts[1:], "market": market}

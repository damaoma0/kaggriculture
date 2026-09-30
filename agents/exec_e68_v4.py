"""E68 - the days 6-8 executor (user 2026-09-30: "for days 6-8 and 9-11 we need separate executor. For 6 we plan in all
money generating goods to be brought back immediately then do other work"; "DSM plans for bringing in - selling -
buying seeds - go out - plant. We are not modeling this.").

It replaces KB115LT2 on the configured days and plays the tiler's day plan (TilePlanView: plant[d], animals_by_day[d],
struct_by_day[d], land_day, hands[d]) with an explicit cash chain:
  1. money runs first: every pen's animal produce (HARVEST) and collectable fertilizer (COLLECT_FERTILIZER) is picked up
     and brought straight back to a shed tile (DROP) and sold in that tick (market orders run after unit actions; SELLs
     come before buys in the order list, so the proceeds fund that tick's purchases). A unit carrying produce worth more
     than chain_max_value goes straight home; smaller loads may take a further pen on the way;
  2. a cash timeline for the rest of the day (current cash + projected sales of the scheduled drops - purchases): the
     land is bought at the first tick it is affordable, then every seed / animal / feed-wheat purchase is made at the
     latest possible tick (the tick before its PLANT / PICKUP) when the timeline can fund it;
  3. the required work (user ruling: maximal production - every production-affecting job is required): placements
     (pick the animal up at the shed, build, place), plantings (harvest or dig first, PLANT, WATER), keep-alive and
     yield-window waterings, feed + care, ripe one-time crop harvests. A unit standing on a shed tile takes the jobs
     that start with a shed pickup first (placements, then feed rounds); otherwise the job it can start soonest.
Greedy list schedule simulated to the end of the day, re-planned every hour from the observed state; each unit keeps
its previous job sequence as a commitment (the first job still open is kept). Engine-exact (kaggriculture 1.32.7): one
step or one op an hour, pickups / drops on a shed-access tile, a seedling dies unless watered on its planting day, all
PLANTs of a crop fail in a tick that asks for more than the seed stock, hires spawn on the least-occupied shed tile
(after the unit actions of the hour) and act from the next hour.
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
    "money_goods": {"6": ["WOOL", "MILK", "EGG", "FERTILIZER"], "7": ["WOOL", "MILK", "EGG"],
                    "8": ["WOOL", "MILK", "EGG"]},   # ... for these goods on each day; other goods are
                               # collected during the pen's feed / care visit and sold when the unit passes the shed
    "feed_buy": {"6": "keep", "7": "all", "8": "all"},   # wheat bought for keep-alive feeds only ("keep") or all feeds
    "chain_detour": 1,         # a money run takes a further pen when that adds <= this many walking hours ...
    "chain_max_value": 300.0,  # ... and the load carried is worth less than this (produce goes straight home)
    "v_plan": 400.0,           # plantings / placements
    "v_build": 200.0,          # a structure the plan builds ahead of its animal
    "v_keep": 1000.0,          # keep-alive water / feed
    "window_promote": 150.0,   # yield-window waterings worth at least this join the plan tier (melons)
    "feed_batch": {"6": 6, "7": 3, "8": 3},   # most wheat picked up for one feed round (small rounds bring the
                               # collected fertilizer back to the shed more often: dropped before the next pickup)
    "fund": 1,                 # funding pass: purchase jobs funded in ROI order within the day's projected budget
    "fund_order": ["WHEAT", "CARROT", "STRAWBERRY", "MELON", "TOMATO", "COW", "GOOSE", "SHEEP"],
    "feed_new": 0,             # feed animals placed today
    "care": 1,                 # CARE with every FEED
    "window_water": 1,         # yield-window waterings of one-time crops
    "harvest_crops": 1,        # ripe one-time crops
    "shed_first": 1,           # a unit on a shed tile takes pickup jobs (placements, feed rounds) first
    "tiers": 1,                # keep-alive jobs, then plan jobs (placements / plantings / builds / valuable waterings),
                               # then production jobs (feed + care, cheap waterings, harvests)
    "farmer_h0": 1,            # the farmer works from hour 0 (hire spawns predicted after his move)
    "hire_first_h0": 1,        # hires before SELL orders at hour 0
    "keep_wheat": 1,           # never sell wheat (feed)
    "wheat_buy_pad": 1.0,      # price pad per unit of feed wheat bought
    "near_k": 16,              # candidates simulated per decision
    "log_plans": 0,            # keep the hour-0 per-unit plan in the diagnostics
    "log_hours": 0,            # keep each hour's first actions / open plan jobs / reasons
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
    """projected cash after each tick's market (ticks h..23)"""

    def __init__(self, money, h):
        self.h = h
        self.base = float(money)
        self.delta = [0.0] * 25

    def at(self, t):
        return self.base + sum(self.delta[self.h:t + 1])

    def add(self, t, v):
        self.delta[max(t, self.h)] += v

    def ok(self, t, cost):
        run = self.base + sum(self.delta[self.h:t])
        for k in range(t, 24):
            run += self.delta[k]
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
    struct_today = _plan_field(plan, "struct_by_day", day)
    mg = set((cfg["money_goods"] or {}).get(str(day), MONEY_GOODS)) if cfg["money_first"] else set()
    fbuy = (cfg["feed_buy"] or {}).get(str(day), "all")
    jobs = {}
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
                    if "FERTILIZER" in mg:
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
                    jobs["F%d" % idx] = Job("F%d" % idx, "feed", (x, y), service + ["FEED"] + care_op, 1 if mand else 3, v,
                                            mand=mand, extra={"buy": mand or fbuy == "all"})
                elif service or care_op:
                    jobs["C%d" % idx] = Job("C%d" % idx, "care", (x, y), service + care_op, 3, pv)
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


# ------------------------------------------------------------------------------------------------ scheduling
class Sim:
    def __init__(self, obs, plan, day, hour, cfg, jobs):
        me = int(obs.get("player", 0))
        self.farm = obs["farms"][me]
        self.priv = obs.get("private") or {}
        self.day, self.h, self.cfg, self.jobs = day, hour, cfg, jobs
        self.tiles = self.farm["tiles"]
        self.market_inv = dict((obs.get("market") or {}).get("inventory") or {})
        self.prices = dict((obs.get("market") or {}).get("prices") or {})
        self.cash = Cash(float(self.farm.get("money", 0) or 0), hour)
        self.shed = Counter({k: int(v) for k, v in (self.priv.get("shed") or {}).items() if v})
        self.seeds = Counter({k: int(v) for k, v in (self.priv.get("seeds") or {}).items() if v})
        self.buys = []           # (tick, order)
        self.sold = Counter()    # projected units we sell today (price walk)
        self.income = []         # (tick, item, n, value)
        self.unassigned = set(jobs)
        owned = list(self.farm.get("unlocked_quadrants") or ["NW"])
        self.land_q, self.land_price, self.land_tick, self.land_done = None, 0, None, False
        nxt = LAND_ORDER[len(owned) - 1] if len(owned) - 1 < len(LAND_ORDER) else None
        try:
            if nxt is not None and int(plan.land_day.get(nxt, 99)) <= day:
                self.land_q, self.land_price = nxt, LAND_PRICES[len(owned) - 1]
        except Exception:
            pass
        self.seed_res = Counter()
        self.animal_res = Counter()
        self.wheat_res = 0
        self.why = {}
        self.units = []
        self.unfunded = []
        self.mg = set((cfg["money_goods"] or {}).get(str(day), MONEY_GOODS)) if cfg["money_first"] else set()

    def project_shed(self, first_tick):
        goods = {g: n for g, n in self.shed.items() if g in SELLABLE and n > 0}
        if goods:
            self.sell_at(first_tick, goods)

    def buy(self, t, order, cost):
        self.buys.append((t, order))
        self.cash.add(t, -cost)

    def sell_at(self, t, goods):
        v = 0.0
        for item, n in goods.items():
            if n <= 0 or item not in MARKET or (item == "WHEAT" and self.cfg["keep_wheat"]):
                continue
            vv = sale_value(item, n, int(self.market_inv.get(item, I0)) + self.sold[item])
            self.sold[item] += n
            v += vv
            self.income.append((t, item, n, vv))
        self.cash.add(t, v)

    def fix_land(self):
        """land first: bought at the first tick the projected cash covers it (usable from the next tick)"""
        if self.land_q is None or self.land_done:
            return
        self.land_done = True
        t = self.cash.earliest(self.h, self.land_price)
        if t is not None:
            self.land_tick = t
            self.cash.add(t, -self.land_price)

    def land_ready(self):
        if self.land_q is None:
            return None
        self.fix_land()
        return None if self.land_tick is None else self.land_tick + 1


def _walk(u, to, steps):
    while u.pos != to:
        mv = step_toward(u.pos, to)
        steps.append((u.t, [mv]))
        u.pos = moved(u.pos, mv)
        u.t += 1


def _wait(u, until, steps):
    while u.t < until:
        steps.append((u.t, ["PASS"]))
        u.t += 1


def shed_start(u, job):
    """the job starts with a pickup at the shed (an animal not carried, or wheat for a feed round)"""
    return (job.kind == "place" and u.inv.get(job.animal, 0) <= 0) or (job.kind == "feed" and u.inv.get("WHEAT", 0) <= 0)


def _shed_drop(u, steps, drops):
    """at a shed tile before a pickup: DROP carried goods first (they sell in that tick)"""
    goods = {g: n for g, n in u.inv.items() if n > 0 and g in MARKET and g != "WHEAT"}
    if goods:
        steps.append((u.t, ["DROP"]))
        drops.append((u.t, goods))
        for g in goods:
            del u.inv[g]
        u.t += 1


def _tile_ops(S, u, job, steps):
    """the job's ops at its tile, in order, with their inventory effects"""
    x, y = job.tile
    t_ = S.tiles[y][x]
    for op in job.ops:
        steps.append((u.t, [op]))
        u.t += 1
        if op == "FEED":
            u.inv["WHEAT"] -= 1
        elif op == "COLLECT_FERTILIZER":
            u.inv["FERTILIZER"] += 1
        elif op == "HARVEST" and isinstance(t_, dict):
            if t_.get("animal"):
                u.inv[ANIMALS[t_["animal"]]["product"]] += int(t_.get("yield_units", 0) or 0)
            elif t_.get("crop"):
                u.inv[t_["crop"]] += int(t_.get("yield_units", 0) or 0)


def try_job(S, u0, job):
    """simulate job for a copy of u0: (unit_after, steps, purchases, waits, drops) or a reason string"""
    u = Unit(u0.idx, u0.pos, u0.t, u0.inv)
    steps, purchases, drops = [], [], []
    k = job.kind
    cfg = S.cfg
    if k == "place" and u.inv.get(job.animal, 0) <= 0:
        _walk(u, near_shed(u.pos), steps)
        _shed_drop(u, steps, drops)
        if S.shed.get(job.animal, 0) - S.animal_res[job.animal] <= 0:
            cost = ANIMALS[job.animal]["cost"]
            b = S.cash.earliest(max(u.t - 1, S.h), cost)
            if b is None or b + 1 > 23:
                return "no_cash_animal"
            purchases.append((b, ["BUY_ANIMAL", job.animal, 1], cost))
            _wait(u, b + 1, steps)
        steps.append((u.t, ["PICKUP", job.animal, 1]))
        u.inv[job.animal] += 1
        u.t += 1
    if k == "feed" and u.inv.get("WHEAT", 0) <= 0:
        _walk(u, near_shed(u.pos), steps)
        _shed_drop(u, steps, drops)
        open_feeds = sum(1 for kk in S.unassigned if S.jobs[kk].kind == "feed")
        spare = sum(v.inv.get("WHEAT", 0) for v in S.units if v.idx != u0.idx)
        fb = cfg["feed_batch"]
        fb = int(fb.get(str(S.day), 6)) if isinstance(fb, dict) else int(fb)
        n_want = max(1, min(fb, open_feeds - spare))
        have = max(0, S.shed.get("WHEAT", 0) - S.wheat_res)
        n_buy = max(0, n_want - have) if job.extra.get("buy", True) else 0
        if n_buy > 0:
            unit_px = float(S.prices.get("WHEAT", 30) or 30) + float(cfg["wheat_buy_pad"])
            b = S.cash.earliest(max(u.t - 1, S.h), n_buy * unit_px)
            if b is None or b + 1 > 23:
                n_buy = 0
            else:
                purchases.append((b, ["BUY_PRODUCT", "WHEAT", n_buy], n_buy * unit_px))
                _wait(u, b + 1, steps)
        n_pick = min(have, n_want) + n_buy
        if n_pick <= 0:
            return "no_wheat"
        steps.append((u.t, ["PICKUP", "WHEAT", n_pick]))
        u.inv["WHEAT"] += n_pick
        u.t += 1
    _walk(u, job.tile, steps)
    if job.locked:
        ready = S.land_ready()
        if ready is None:
            return "no_land"
        _wait(u, ready, steps)
    for op in job.pre:
        steps.append((u.t, [op]))
        if op == "HARVEST":
            x, y = job.tile
            t_ = S.tiles[y][x]
            if isinstance(t_, dict) and t_.get("crop"):
                u.inv[t_["crop"]] += int(t_.get("yield_units", 0) or 0)
        u.t += 1
    if k == "plant":
        if S.seeds.get(job.crop, 0) - S.seed_res[job.crop] <= 0:
            cost = CROPS[job.crop]["seed"]
            b = S.cash.earliest(max(u.t - 1, S.h), cost)
            if b is None or b + 1 > 22:
                return "no_cash_seed"
            purchases.append((b, ["BUY_SEED", job.crop, 1], cost))
            _wait(u, b + 1, steps)
        steps.append((u.t, ["PLANT", job.crop]))
        u.t += 1
        steps.append((u.t, ["WATER"]))
        u.t += 1
    elif k == "place":
        steps.append((u.t, ["PLACE", job.animal]))
        u.inv[job.animal] -= 1
        u.t += 1
    else:
        if k == "feed" and u.inv.get("WHEAT", 0) <= 0:
            return "no_wheat"
        _tile_ops(S, u, job, steps)
    if u.t > 24:
        return "late"
    waits = sum(1 for (_, a) in steps if a[0] == "PASS")
    return u, steps, purchases, waits, drops


def apply_job(S, u, job, res):
    u2, steps, purchases, _, drops = res
    bought_animal = any(o[0] == "BUY_ANIMAL" for (_, o, _) in purchases)
    if job.kind == "place" and u.inv.get(job.animal, 0) <= 0 and not bought_animal:
        S.animal_res[job.animal] += 1
    if job.kind == "plant" and not any(o[0] == "BUY_SEED" for (_, o, _) in purchases):
        S.seed_res[job.crop] += 1
    if job.kind == "feed":
        bought = sum(int(o[2]) for (_, o, _) in purchases if o[0] == "BUY_PRODUCT")
        for (_, a) in steps:
            if a[0] == "PICKUP" and a[1] == "WHEAT":
                S.wheat_res += max(0, int(a[2]) - bought)
    for (b, order, cost) in purchases:
        S.buy(b, order, cost)
    for (t, goods) in drops:
        S.sell_at(t, goods)
    u.steps.extend(steps)
    u.pos, u.t, u.inv = u2.pos, u2.t, u2.inv
    u.jobs.append(job.key)
    S.unassigned.discard(job.key)


def carried_value(S, u):
    return sum(n * float(S.prices.get(g, 0) or 0) for g, n in u.inv.items() if g in S.mg)


def carrying_money(S, u):
    """carries goods that are brought home at once today (the day's money goods)"""
    return any(u.inv.get(g, 0) > 0 for g in S.mg)


def return_drop(S, u):
    """walk to the nearest shed tile and DROP everything carried; the goods sell in that tick"""
    steps = []
    _walk(u, near_shed(u.pos), steps)
    if u.t > 23:
        u.steps.extend(steps)
        u.done = True
        return
    steps.append((u.t, ["DROP"]))
    S.sell_at(u.t, {g: n for g, n in u.inv.items() if n > 0})
    u.inv = Counter()
    u.t += 1
    u.steps.extend(steps)
    u.jobs.append("RET")


def next_money(S, u):
    """money run choice: carrying -> a pen near the way home (small loads only) else home; not carrying -> the best
    pen by value per hour of the round trip; None when no money job is left"""
    cfg = S.cfg
    money_left = [k for k in S.unassigned if S.jobs[k].kind == "money"]
    if carrying_money(S, u):
        if carried_value(S, u) >= cfg["chain_max_value"]:
            return "RET"
        direct = dist(u.pos, near_shed(u.pos))
        best, bt = None, None
        for k in money_left:
            j = S.jobs[k]
            extra = dist(u.pos, j.tile) + dist(j.tile, near_shed(j.tile)) - direct
            if extra <= cfg["chain_detour"] and u.t + dist(u.pos, j.tile) + len(j.ops) + dist(j.tile, near_shed(j.tile)) <= 23 \
                    and (bt is None or (extra, -j.value) < bt):
                best, bt = k, (extra, -j.value)
        return best if best is not None else "RET"
    best, bs = None, None
    for k in money_left:
        j = S.jobs[k]
        eta = u.t + dist(u.pos, j.tile) + len(j.ops) + dist(j.tile, near_shed(j.tile)) + 1
        if eta > 24:
            continue
        sc = j.value / max(1, eta - u.t)
        if bs is None or sc > bs:
            best, bs = k, sc
    return best


def choose_work(S, u):
    """tiers: keep-alive (1), plan (2: placements, plantings, builds, valuable waterings), production (3). Within a tier,
    on a shed tile the pickup jobs first (placements before feed rounds), otherwise the job whose first productive action
    comes soonest (walking + waiting), ties by value. When the best job must wait (land / cash), a job of a later tier that
    fits in the wait goes first."""
    cfg = S.cfg
    carried = [a for a in ANIMALS if u.inv.get(a, 0) > 0]
    tiers = {}
    for k in S.unassigned:
        j = S.jobs[k]
        if j.kind == "money":
            continue
        if carried and not (j.kind == "place" and j.animal in carried):
            continue
        tiers.setdefault(j.cls if cfg["tiers"] else 1, []).append(j)
    if not tiers:
        return None
    at_shed = u.pos in SHED
    K = int(cfg["near_k"])

    def first_loc(j):
        return near_shed(u.pos) if shed_start(u, j) else j.tile

    def best_of(cands, max_dur=None):
        pool = sorted(cands, key=lambda j_: dist(u.pos, first_loc(j_)))[:K]
        if at_shed and cfg["shed_first"]:
            pool = [j for j in cands if shed_start(u, j)][:K] + pool
        best, seen = None, set()
        for j in pool:
            if j.key in seen:
                continue
            seen.add(j.key)
            r = try_job(S, u, j)
            if isinstance(r, str):
                S.why[j.key] = r
                continue
            if max_dur is not None and r[0].t - u.t > max_dur:
                continue
            t_first = next((t for (t, a) in r[1] if a[0] not in MOVES and a[0] != "DROP"), r[0].t)
            shed_pref = 0 if (at_shed and cfg["shed_first"] and shed_start(u, j)) else 1
            kind_rank = {"place": 0, "feed": 1}.get(j.kind, 2) if shed_pref == 0 else 0
            sc = (shed_pref, kind_rank, t_first - u.t + r[3], -j.value, r[0].t)
            if best is None or sc < best[0]:
                best = (sc, j, r)
        return best
    order = sorted(tiers)
    for i, c in enumerate(order):
        best = best_of(tiers[c])
        if best is None:
            continue
        waits = best[2][3]
        if waits > 0:
            for c2 in order[i + 1:]:
                alt = best_of(tiers[c2], max_dur=waits)
                if alt is not None:
                    return alt[1], alt[2]
        return best[1], best[2]
    return None


def fund_jobs(S):
    """the day's purchase jobs in ROI order (seeds of cheap crops first, then dearer seeds, then animals) are kept while
    the projected end-of-day cash (after the money runs and the land) covers them; the rest are dropped for today.
    Keep-alive feeds keep their wheat; optional feed wheat is funded last."""
    cfg = S.cfg
    budget = S.cash.at(23)
    stock_seed = Counter(S.seeds)
    stock_anim = Counter({a: S.shed.get(a, 0) for a in ANIMALS})
    for u in S.units:
        for a in ANIMALS:
            stock_anim[a] += u.inv.get(a, 0)
    rank = {k: i for i, k in enumerate(cfg["fund_order"])}
    need = []
    for k in list(S.unassigned):
        j = S.jobs[k]
        if j.kind == "plant":
            need.append((rank.get(j.crop, 99), dist(near_shed(j.tile), j.tile), k, "seed", j.crop))
        elif j.kind == "place":
            need.append((rank.get(j.animal, 99), dist(near_shed(j.tile), j.tile), k, "anim", j.animal))
    dropped = []
    for (_, _, k, what, item) in sorted(need):
        if what == "seed":
            if stock_seed[item] > 0:
                stock_seed[item] -= 1
                continue
            cost = CROPS[item]["seed"]
        else:
            if stock_anim[item] > 0:
                stock_anim[item] -= 1
                continue
            cost = ANIMALS[item]["cost"]
        if budget - cost >= 0:
            budget -= cost
        else:
            S.unassigned.discard(k)
            dropped.append(k)
    S.unfunded = dropped


def schedule(S, units, prev):
    """greedy list schedule; prev = {unit idx: previous job sequence}: the first job of it still open stays with the unit"""
    S.units = units
    for u in units:
        seq = prev.get(u.idx) or []
        for k in seq:
            if k == "RET":
                if carrying_money(S, u):
                    return_drop(S, u)
                    break
                continue
            if k in S.unassigned:
                r = try_job(S, u, S.jobs[k])
                if not isinstance(r, str):
                    apply_job(S, u, S.jobs[k], r)
                break
    if S.cfg["money_first"]:
        paused = set()
        for _ in range(4000):
            live = [u for u in units if not u.done and u.t <= 23 and u.idx not in paused]
            if not live:
                break
            u = min(live, key=lambda v: (v.t, v.idx))
            c = next_money(S, u)
            if c is None:
                paused.add(u.idx)
            elif c == "RET":
                return_drop(S, u)
            else:
                r = try_job(S, u, S.jobs[c])
                if isinstance(r, str):
                    S.unassigned.discard(c)
                else:
                    apply_job(S, u, S.jobs[c], r)
    S.fix_land()
    if S.cfg["fund"]:
        fund_jobs(S)
    for _ in range(4000):
        live = [u for u in units if not u.done and u.t <= 23]
        if not live:
            break
        u = min(live, key=lambda v: (v.t, v.idx))
        if carrying_money(S, u) or not S.cfg["money_first"]:
            c = next_money(S, u)
            if c == "RET" or (c is None and carrying_money(S, u)):
                return_drop(S, u)
                continue
            if c is not None:
                r = try_job(S, u, S.jobs[c])
                if isinstance(r, str):
                    S.unassigned.discard(c)
                else:
                    apply_job(S, u, S.jobs[c], r)
                continue
        c = choose_work(S, u)
        if c is None:
            u.done = True
            continue
        apply_job(S, u, c[0], c[1])
    return {u.idx: u for u in units}


# ------------------------------------------------------------------------------------------------ the step
def e68_step(obs, plan, cfg_in, E):
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
    tiles = farm["tiles"]
    for k in [k for k, j in jobs.items() if job_done(j, tiles, day)]:
        del jobs[k]
    S = Sim(obs, plan, day, hour, cfg, jobs)
    pos = [tuple(farm["farmer"])] + [tuple(h) for h in (farm.get("hands") or [])]
    n_hire0 = max(0, int(E["hands_want"]) - (len(pos) - 1)) if hour <= 1 else 0
    S.project_shed(hour + 1 if (hour == 0 and cfg["hire_first_h0"] and n_hire0 >= 10) else hour)
    invs = list(priv.get("inventories") or [])
    units = [Unit(i, p, hour, {k: int(v) for k, v in (invs[i] if i < len(invs) else {}).items() if v})
             for i, p in enumerate(pos)]
    prev = {int(k): v for k, v in (E.get("prev") or {}).items()}
    want = int(E["hands_want"])
    n_hire = max(0, want - (len(pos) - 1)) if hour <= 1 else 0
    if n_hire:
        # the live units decide this hour's action first; the hires spawn after the unit actions (engine order)
        occ = []
        if hour == 0 and not cfg["farmer_h0"]:
            units[0].steps.append((0, ["PASS"]))
            units[0].t = 1
        else:
            for u in units:                           # a unit's first move this hour sets its position for the spawn
                c = next_money(S, u) if cfg["money_first"] else None
                if c and c != "RET":
                    r = try_job(S, u, S.jobs[c])
                    if not isinstance(r, str):
                        apply_job(S, u, S.jobs[c], r)
        for u in units:
            p = u.pos
            for (t, a) in u.steps:
                if t == hour and a[0] in DIRS:
                    p = moved(tuple(pos[u.idx]), a[0])
            occ.append(p if any(t == hour for (t, _) in u.steps) else tuple(pos[u.idx]))
        hires = []
        for k in range(n_hire):
            s = spawn_tile(occ)
            occ.append(s)
            units.append(Unit(len(pos) + k, s, hour + 1, {}))
            hires.append(s)
    else:
        hires = []
    by_idx = schedule(S, units, prev)
    n_hands = len(farm.get("hands") or [])
    acts = []
    for i in range(1 + n_hands):
        u = by_idx.get(i)
        acts.append(next((act for (t, act) in u.steps if t == hour), ["PASS"]) if u is not None else ["PASS"])
    E["prev"] = {u.idx: list(u.jobs) for u in by_idx.values()}
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
    for (t, o) in S.buys:
        if t == hour:
            buys[(o[0], o[1])] += int(o[2])
    order_rank = {"BUY_ANIMAL": 0, "BUY_SEED": 1, "BUY_PRODUCT": 2}
    buy_orders = [[k[0], k[1], n] for k, n in sorted(buys.items(), key=lambda kv: (order_rank[kv[0][0]], kv[0][1]))]
    if hour == 0 and cfg["hire_first_h0"]:
        market = hire_orders + sells + land + buy_orders
    else:
        market = sells + hire_orders + land + buy_orders
    market = market[:10]
    lg = E["log"]
    for a in acts:
        lg["op:" + a[0]] += 1
    for o in market:
        lg[("mk:%s:%s" % (o[0], o[1])) if len(o) > 2 else ("mk:" + o[0])] += int(o[2]) if len(o) > 2 else 1
    if hour == 0:
        E["diag"].update(jobs=dict(Counter(j.kind for j in jobs.values())), land_q=S.land_q, land_plan_h=S.land_tick,
                         hires=len(hires), cash0=float(farm.get("money", 0) or 0),
                         cash_proj=[round(S.cash.at(t)) for t in range(hour, 24)],
                         income_proj=[(t, i, n, round(v)) for (t, i, n, v) in S.income][:40],
                         unassigned=sorted(S.unassigned)[:40], why={k: S.why.get(k) for k in sorted(S.unassigned)[:40]},
                         unfunded=sorted(S.unfunded)[:40])
        if cfg["log_plans"]:
            E["diag"]["plans"] = {u.idx: [(t, a) for (t, a) in u.steps] for u in units}
    if cfg["log_hours"]:
        E["hours"][hour] = dict(acts=[a[0][:5] + (":" + str(a[1])[:3] if len(a) > 1 else "") for a in acts],
                                market=market, land_tick=S.land_tick, open=sorted(k for k in S.unassigned if jobs[k].cls <= 1)[:30],
                                why={k: S.why.get(k) for k in sorted(S.unassigned)[:30]},
                                first={u.idx: u.jobs[:3] for u in by_idx.values()})
        E["diag"]["hours"] = E["hours"]
    E["diag"]["log"] = dict(lg)
    return {"farmer": acts[0], "hands": acts[1:], "market": market}

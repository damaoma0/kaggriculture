"""Kaggriculture agent, plan_v1: a day-level build order plus a daily zone-sweep executor.

Single self-contained file. Kaggle loads main.py and calls the last callable, `agent`.

Layer 1 (strategy): BUILD is a cumulative schedule of what the farm should own by each day
(animals, strawberry tiles, land, hands), taken from the public meta's converged opening and
reinvesting everything during the compounding phase. Demand tilts adjust it slightly.

Layer 2 (execution): each day the tiles that need work are split into contiguous zones, one per
unit, weighted by workload. A unit sweeps its zone doing every task on each tile, picking up its
wheat and fertilizer once at the shed. Units that finish help with unfinished zones.

Market: sell with a slippage cap from the exact price curve, dump what the town cannot absorb,
race the opponent's melon dump, liquidate on the last day.
"""
import math

# ---------------------------------------------------------------- engine constants (copied)
CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}
ANIMAL_RATE = {"GOOSE": 2.0, "COW": 1.5, "SHEEP": 4 / 3}
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
MARKET_I0 = 10000
MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "T": 450, "below_func": "hinge",  "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "T": 200, "below_func": "hinge",  "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "T": 332, "below_func": "hinge",  "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}
SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
AVG_SHOP_DRAIN = {}
for _s, _prods in SHOPS.items():
    for _p in _prods:
        AVG_SHOP_DRAIN[_p] = AVG_SHOP_DRAIN.get(_p, 0.0) + 6 * (2 if len(_prods) == 1 else 1) / len(SHOPS)
LAND_PRICES = [1000, 2000, 4000]
TURNS_PER_DAY = 24
BOARD = 10
SHED_CAP = 100
MAX_ORDERS = 10
SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}


def _shape(func, x, T=None):
    x = max(0.0, x)
    if func == "linear": return x
    if func == "sq":     return x * x
    if func == "sqrt":   return math.sqrt(x)
    if func == "log":    return math.log(1.0 + x)
    if func == "hinge":
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    return x


def market_price(item, inventory):
    p = MARKET_PARAMS[item]
    base, T = p["base"], p["T"]
    if inventory < MARKET_I0:
        amp = p["below_target"] * base / _shape(p["below_func"], T, T)
        price = base + amp * _shape(p["below_func"], MARKET_I0 - inventory, T)
    else:
        amp = p["above_target"] * base / _shape(p["above_func"], T, T)
        price = base - amp * _shape(p["above_func"], inventory - MARKET_I0, T)
    return max(1, int(round(price)))


def units_sellable(item, inventory, min_price, cap):
    n, inv = 0, inventory
    while n < cap:
        p = market_price(item, inv)
        if p < min_price:
            break
        n += 1
        if p > 1:
            inv += 1
    return n


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def step_toward(pos, target):
    dx, dy = target[0] - pos[0], target[1] - pos[1]
    if dx == 0 and dy == 0:
        return ["PASS"]
    if abs(dx) >= abs(dy):
        return ["EAST"] if dx > 0 else ["WEST"]
    return ["SOUTH"] if dy > 0 else ["NORTH"]


def nearest_shed_tile(pos):
    return min(SHED_TILES, key=lambda t: dist(pos, t))


def sweep_key(p):
    """Row-snake over the whole board: consecutive tiles in this order are board neighbours."""
    x, y = p
    return (y, x if y % 2 == 0 else BOARD - 1 - x)


# ---------------------------------------------------------------- build order (from the public meta)
def cum(schedule, day):
    """schedule: {day: value}; return value at the latest day <= day (0 before the first)."""
    v = 0
    for d in sorted(schedule):
        if d <= day:
            v = schedule[d]
    return v


BUILD = {
    "melon": 12,                                   # planted on day 0
    "cows":   {0: 2, 2: 3, 3: 4, 6: 6, 7: 8, 8: 9},
    "sheep":  {0: 2, 8: 4, 11: 5},
    "geese":  {},
    "melon_rolling": 10,     # melon tiles kept planted from day 1 to melon_last_plant_day
    "melon_last_plant_day": 19,
    "straw":  {4: 4, 5: 8, 6: 12, 7: 16, 8: 20, 11: 33},
    "land":   {6: 1, 11: 2},                       # extra quadrants unlocked by day
    "hands":  [5, 4, 4, 5, 4, 5, 8, 8, 10, 9, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12,
               12, 12, 12, 12, 12, 12, 12, 12, 12, 9],
    "wheat_opening": 7,
    "wheat_cap": 60,                               # wheat fills whatever tiles remain
    "straw_last_plant_day": 13,
    "carrot_from_day": 22,
    "carrot_last_day": 26,
    "wheat_last_day": 25,
    "animal_last_day": 20,
    "sell_frac": 0.5,
    "hold_days": 4,
}


class Planner:
    def __init__(self):
        self.zone_list = []      # zones: ordered tile lists
        self.assign = {}         # unit index -> zone index
        self.zone_day = -1
        self.target = {}         # unit index -> tile it is heading to
        self.zone_final = False  # partition done with the full crew present
        self.prev_target = {}
        self.melon_rush = False
        # opponent trade inference from public market inventory
        self.prev_inv = None
        self.prev_step = None
        self.last_orders = []
        self.opp_sold = {}     # day -> {product: units the opponent sold}
        self.opp_bought = {}   # day -> {product: units the opponent bought}

    # ------------------------------------------------------------ scan
    def scan(self, obs):
        me = obs["player"]
        farm = obs["farms"][me]
        self.opp = obs["farms"][1 - me]
        self.tiles = farm["tiles"]
        self.money = farm["money"]
        self.unlocked = farm["unlocked_quadrants"]
        priv = obs["private"]
        self.shed = dict(priv.get("shed") or {})
        self.seeds = dict(priv.get("seeds") or {})
        invs = priv.get("inventories") or [{}]
        positions = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        self.units = [{"i": i, "pos": p, "inv": dict(invs[i]) if i < len(invs) else {}}
                      for i, p in enumerate(positions)]
        self.plants, self.animals, self.structures, self.weeds, self.empty = [], [], [], [], []
        for y in range(BOARD):
            for x in range(BOARD):
                t = self.tiles[y][x]
                if t == "LOCKED":
                    continue
                if t is None:
                    self.empty.append((x, y))
                elif t.get("kind") == "PLANT":
                    self.plants.append((x, y, t))
                elif t.get("kind") == "WEED":
                    self.weeds.append((x, y))
                elif "animal" in t:
                    self.animals.append((x, y, t))
                else:
                    self.structures.append((x, y, t))
        self.n_animals = len(self.animals)
        self.crop_count, self.animal_count = {}, {}
        for _, _, t in self.plants:
            self.crop_count[t["crop"]] = self.crop_count.get(t["crop"], 0) + 1
        for _, _, t in self.animals:
            self.animal_count[t["animal"]] = self.animal_count.get(t["animal"], 0) + 1
        self.market_inv = obs["market"]["inventory"]
        self.prices = obs["market"]["prices"]
        self.shops = list(obs["town"].get("unlocked_shops") or [])

    # ------------------------------------------------------------ demand (for tilts and selling)
    def farm_supply(self, tiles):
        sup = {p: 0.0 for p in PRODUCTS}
        melons = []
        for row in tiles:
            for t in row:
                if not isinstance(t, dict):
                    continue
                if "animal" in t:
                    sup[ANIMALS[t["animal"]]["product"]] += ANIMAL_RATE[t["animal"]]
                elif t.get("kind") == "PLANT":
                    c = t["crop"]
                    if c == "MELON":
                        melons.append(t["planted_day"])
                    else:
                        sup[c] += {"STRAWBERRY": 0.35, "TOMATO": 0.33, "WHEAT": 0.8, "CARROT": 1.0}[c]
        return sup, melons

    def infer_opponent(self, step):
        """Opponent sells/buys at the previous step = inventory change - town drain - our own trades."""
        inv = dict(self.market_inv)
        if self.prev_inv is not None and self.prev_step == step - 1:
            s = step - 1
            day = s // TURNS_PER_DAY
            drain = {p: 0 for p in PRODUCTS}
            if s % 4 == 0:
                for shop in self.shops:
                    prods = SHOPS[shop]
                    for q in prods:
                        drain[q] += 2 if len(prods) == 1 else 1
            if s % 24 == 0:
                for q in PRODUCTS:
                    if q != "FERTILIZER":
                        drain[q] += 1
            mine = {p: 0 for p in PRODUCTS}
            for o in self.last_orders:
                if o and o[0] == "SELL" and o[1] in mine:
                    mine[o[1]] += int(o[2])
                elif o and o[0] == "BUY_PRODUCT" and o[1] in mine:
                    mine[o[1]] -= int(o[2])
            sold = self.opp_sold.setdefault(day, {p: 0 for p in PRODUCTS})
            bought = self.opp_bought.setdefault(day, {p: 0 for p in PRODUCTS})
            for p in PRODUCTS:
                net = inv[p] - self.prev_inv[p] + drain[p] - mine[p]
                if net > 0:
                    sold[p] += net
                elif net < 0:
                    bought[p] += -net
        self.prev_inv = inv
        self.prev_step = step

    def opp_rate(self, product, day, window=3):
        """Observed opponent sales per day over the last `window` complete days (None if unknown)."""
        days = [d for d in range(day - window, day) if d >= 0 and d in self.opp_sold]
        if len(days) < 2:
            return None
        return sum(self.opp_sold[d][product] for d in days) / len(days)

    def economics(self, day):
        days_left = max(1, 29 - day)
        drain = {p: (0.0 if p == "FERTILIZER" else 1.0) for p in PRODUCTS}
        for s in self.shops:
            prods = SHOPS[s]
            mult = 2 if len(prods) == 1 else 1
            for p in prods:
                drain[p] += 6 * mult
        opp_sup, self.opp_melons = self.farm_supply(self.opp["tiles"])
        if day >= 10:
            for p in PRODUCTS:
                r = self.opp_rate(p, day)
                if r is not None and p != "MELON":
                    opp_sup[p] = 0.5 * opp_sup[p] + 0.5 * r   # blend the tile estimate with what they actually sell
        my_sup, self.my_melons = self.farm_supply(self.tiles)
        for a in ANIMALS:
            my_sup[ANIMALS[a]["product"]] += self.shed.get(a, 0) * ANIMAL_RATE[a]
        future = {p: 0.0 for p in PRODUCTS}
        n_left = 8 - len(self.shops)
        t = (day // 3 + 1) * 3
        while n_left > 0 and t <= 27:
            for p in PRODUCTS:
                future[p] += AVG_SHOP_DRAIN.get(p, 0.0) * (29 - t)
            n_left -= 1
            t += 3
        self.drain = drain
        self.budget = {}
        for p in PRODUCTS:
            base = MARKET_PARAMS[p]["base"]
            cap_now = units_sellable(p, self.market_inv[p], BUILD["sell_frac"] * base, 600)
            self.budget[p] = (cap_now + (drain[p] - opp_sup[p] - my_sup[p]) * days_left
                              + 0.8 * future[p] - self.shed.get(p, 0))

    # ------------------------------------------------------------ targets for today
    def targets(self, day):
        t = {
            "COW": cum(BUILD["cows"], day),
            "SHEEP": cum(BUILD["sheep"], day),
            "GOOSE": cum(BUILD["geese"], day),
            "straw": cum(BUILD["straw"], day),
            "land": cum(BUILD["land"], day),
        }
        # demand tilts: do not add animals into a forecast glut; skip geese unless eggs are wanted
        # an animal repays itself from fertilizer alone within ~5 days, so the glut tilt only
        # applies late in the build phase and only to a clear glut
        if day >= 9 and self.budget["MILK"] < -60:
            t["COW"] = min(t["COW"], max(4, self.owned("COW")))
        if day >= 9 and self.budget["WOOL"] < -60:
            t["SHEEP"] = min(t["SHEEP"], max(2, self.owned("SHEEP")))
        if self.prices["EGG"] < 55 and self.budget["EGG"] < 200:
            t["GOOSE"] = 0
        if day > BUILD["animal_last_day"]:
            for a in ANIMALS:
                t[a] = 0
        return t

    def owned(self, a):
        return (self.animal_count.get(a, 0) + self.shed.get(a, 0)
                + sum(u["inv"].get(a, 0) for u in self.units))

    def planting_wanted(self, day):
        """[(crop, n)] to plant today, in priority order."""
        out = []
        melons = self.crop_count.get("MELON", 0)
        if day == 0:
            out.append(("MELON", BUILD["melon"] - melons))
        elif day <= BUILD["melon_last_plant_day"] and melons < BUILD["melon_rolling"] and day < 10:
            out.append(("MELON", min(BUILD["melon_rolling"] - melons, 4)))
        straw_have = self.crop_count.get("STRAWBERRY", 0)
        if day <= BUILD["straw_last_plant_day"]:
            n = self.targets(day)["straw"] - straw_have
            if n > 0:
                out.append(("STRAWBERRY", n))
        wheat = self.crop_count.get("WHEAT", 0)
        if day < 10:
            if wheat < BUILD["wheat_opening"]:
                out.append(("WHEAT", BUILD["wheat_opening"] - wheat))
            return out
        # filler for remaining tiles: rank by expected coins per tile-day at current prices,
        # only crops that can still finish before the season ends
        pr = self.prices
        cands = []
        if day <= BUILD["melon_last_plant_day"] and melons < BUILD["melon_rolling"] + 6:
            cands.append((6 * market_price("MELON", self.market_inv["MELON"] + 30) / 10, "MELON", 8))
        if day <= BUILD["wheat_last_day"]:
            cands.append((4.5 * pr["WHEAT"] / 5, "WHEAT", 12))
        if day <= BUILD["carrot_last_day"]:
            cands.append((3 * market_price("CARROT", self.market_inv["CARROT"] + 20) / 3, "CARROT", 12))
        cands.sort(reverse=True)
        for _, crop, n in cands:
            out.append((crop, n))
        return out

    # ------------------------------------------------------------ tasks per tile
    def tile_tasks(self, day, hour, step):
        """Return {tile: [(op, args, need)]}, tasks in the order they should be done."""
        last_day = day == 29
        tasks = {}
        fert_available = self.shed.get("FERTILIZER", 0) + sum(u["inv"].get("FERTILIZER", 0) for u in self.units)
        for x, y, t in self.plants:
            cd = CROPS[t["crop"]]
            age = day - t["planted_day"]
            yu = t.get("yield_units", 0)
            L = []
            melon_rush = t["crop"] == "MELON" and self.melon_rush and age >= 10 and (yu >= 5 or (yu >= 4 and hour >= 6))
            if melon_rush:
                L.append(("HARVEST", [], None))
            else:
                if not t["watered_today"]:
                    if not last_day:
                        L.append(("WATER", [], None))
                    elif not cd["ongoing"] and (cd["max_yield_day"] + 1) // 2 <= age < cd["max_yield_day"] and yu < cd["max_yield"]:
                        L.append(("WATER", [], None))
                if (t["crop"] == "STRAWBERRY" and age in (9, 10, 13, 14) and t.get("fertilized_until_day", -1) < day
                        and fert_available > 0 and day <= 27):
                    L.append(("FERTILIZE", [], "FERTILIZER"))
                    fert_available -= 1

                if cd["ongoing"]:
                    if yu > 0:
                        L.append(("HARVEST", [], None))
                    if t["crop"] == "STRAWBERRY" and age >= 16 and day <= 26 and not last_day:
                        L.append(("DIG", [], None))   # after the 4th production the plant only decays
                else:
                    ready = (yu >= cd["max_yield"]
                             or (age >= cd["max_yield_day"] and (t["watered_today"] or last_day or "WATER" in [o for o, _, _ in L]))
                             or step >= t["max_lifespan_step"] - 1
                             or (last_day and hour >= 16 and yu > 0))
                    if ready and yu > 0 and age >= cd["first_yield_day"]:
                        L.append(("HARVEST", [], None))
            if L:
                tasks[(x, y)] = L
        skip_collect = False
        for x, y, t in self.animals:
            L = []
            if not last_day and day > 0 and not t["fed_today"]:
                L.append(("FEED", [], "WHEAT"))
            prod = ANIMALS[t["animal"]]["product"]
            worth_care = self.prices[prod] >= 0.4 * MARKET_PARAMS[prod]["base"]
            if not last_day and not t["cared_today"] and day < 28 and worth_care:
                L.append(("CARE", [], None))
            if t.get("fertilizer_available") and day < 29 and not skip_collect:
                L.append(("COLLECT_FERTILIZER", [], None))
            if t.get("yield_units", 0) > 0:
                L.append(("HARVEST", [], None))
            if L:
                tasks[(x, y)] = L
        # animals waiting in the shed / hands -> place on structures, build if needed
        waiting = {a: self.shed.get(a, 0) + sum(u["inv"].get(a, 0) for u in self.units) for a in ANIMALS}
        used = set()
        near_empty = sorted(self.empty, key=lambda p: dist(p, (4, 4)))
        for a, n in waiting.items():
            if n <= 0:
                continue
            struct = ANIMALS[a]["structure"]
            matching = [(x, y) for x, y, t in self.structures if t.get("kind") == struct and (x, y) not in used]
            for p in matching[:n]:
                tasks[p] = [("PLACE", [a], a)]
                used.add(p)
            short = n - len(matching[:n])
            for p in [q for q in near_empty if q not in used][:short]:
                if not last_day:
                    tasks[p] = [("BUILD_" + struct, [], None), ("PLACE", [a], a)]
                    used.add(p)
        # plantings: strawberries near the shed, wheat farther out
        if not last_day:
            free = [p for p in near_empty if p not in used]
            seeds_left = dict(self.seeds)
            for crop, n in self.planting_wanted(day):
                k = min(n, seeds_left.get(crop, 0), len(free))
                if k <= 0:
                    continue
                if crop in ("WHEAT", "CARROT"):
                    chosen, free = free[-k:], free[:-k]
                else:
                    chosen, free = free[:k], free[k:]
                for p in chosen:
                    tasks[p] = [("PLANT", [crop], None), ("WATER", [], None)]
                    seeds_left[crop] -= 1
        for p in self.weeds:
            if day <= 26 or last_day is False and day <= 27:
                tasks[p] = [("DIG", [], None)]
        return tasks

    # ------------------------------------------------------------ zones
    def weight(self, L):
        return 1.0 + len(L)

    def partition(self, tasks, k, units, only_near=None):
        """Split task tiles into k contiguous zones along the sweep order, weighted by workload.
        Returns the zone list; present units are matched to zones by proximity."""
        tiles = sorted(tasks, key=sweep_key)
        if only_near is not None:
            tiles = [p for p in tiles if dist(p, (4, 4)) <= only_near]
        k = max(1, k)
        zones = [[] for _ in range(k)]
        if tiles:
            total = sum(self.weight(tasks[p]) for p in tiles)
            per = total / k
            zi, acc = 0, 0.0
            for p in tiles:
                zones[zi].append(p)
                acc += self.weight(tasks[p])
                if acc >= per and zi < k - 1:
                    zi += 1
                    acc = 0.0
        assign = {}
        remaining = list(range(k))
        for u in sorted(units, key=lambda u: u["i"]):
            if not remaining:
                break
            best = min(remaining, key=lambda z: dist(u["pos"], zones[z][0]) if zones[z] else 50)
            remaining.remove(best)
            assign[u["i"]] = best
        return zones, assign

    # ------------------------------------------------------------ execution
    def execute(self, tasks, day, hour, step):
        acts = {}
        last_day = day == 29
        units = self.units
        if self.zone_day != day:
            # provisional: the farmer alone, tiles close to the shed, no kit pickups
            self.zone_list, self.assign = self.partition(tasks, 1, units, only_near=3)
            self.zone_day, self.zone_final = day, False
        if not self.zone_final and hour >= 1:
            crew = max(len(units), BUILD["hands"][min(day, 29)] + 1)
            self.zone_list, self.assign = self.partition(tasks, crew, units)
            self.zone_final = True
        # newcomers take an unassigned zone
        for u in units:
            if u["i"] not in self.assign:
                free = [z for z in range(len(self.zone_list)) if z not in self.assign.values()]
                if free:
                    self.assign[u["i"]] = min(free, key=lambda z: dist(u["pos"], self.zone_list[z][0]) if self.zone_list[z] else 50)
        claimed = set()
        pending_tiles = {p for p, L in tasks.items() if L}
        feed_tiles = {p for p in pending_tiles if any(op == "FEED" for op, _, _ in tasks[p])}
        for u in units:
            i, pos, inv = u["i"], u["pos"], u["inv"]
            at_shed = pos in SHED_TILES
            zi = self.assign.get(i)
            zone_all = self.zone_list[zi] if zi is not None else []
            zone = [p for p in zone_all if p in pending_tiles and p not in claimed]
            carrying = sum(v for k, v in inv.items() if k in PRODUCTS)
            if last_day and carrying and hour >= 16:
                acts[i] = ["DROP"] if at_shed else step_toward(pos, nearest_shed_tile(pos))
                continue
            if inv.get("MELON", 0) >= 5 or (carrying and self.carry_value(inv) >= (350 if day < 10 else 3000)):
                acts[i] = ["DROP"] if at_shed else step_toward(pos, nearest_shed_tile(pos))
                continue
            # zone kit, only once zones are final
            if at_shed and self.zone_final and not last_day:
                need_wheat = sum(1 for p in zone for op, _, nd in tasks[p] if nd == "WHEAT")
                need_fert = sum(1 for p in zone for op, _, nd in tasks[p] if nd == "FERTILIZER")
                if need_wheat > inv.get("WHEAT", 0) and self.shed.get("WHEAT", 0) > 0:
                    n = min(self.shed["WHEAT"], need_wheat - inv.get("WHEAT", 0) + 1)
                    self.shed["WHEAT"] -= n
                    inv["WHEAT"] = inv.get("WHEAT", 0) + n
                    acts[i] = ["PICKUP", "WHEAT", n]
                    continue
                if need_fert > inv.get("FERTILIZER", 0) and self.shed.get("FERTILIZER", 0) > 0:
                    n = min(self.shed["FERTILIZER"], need_fert - inv.get("FERTILIZER", 0))
                    self.shed["FERTILIZER"] -= n
                    inv["FERTILIZER"] = inv.get("FERTILIZER", 0) + n
                    acts[i] = ["PICKUP", "FERTILIZER", n]
                    continue
                for a in ANIMALS:
                    if self.shed.get(a, 0) > 0 and inv.get(a, 0) == 0 and any(nd == a for p in zone for _, _, nd in tasks[p]):
                        self.shed[a] -= 1
                        inv[a] = 1
                        acts[i] = ["PICKUP", a, 1]
                        break
                if i in acts:
                    continue
            target = None
            # finish the tile we stand on before walking anywhere
            if pos in pending_tiles and pos not in claimed and self.can_do_something(tasks[pos], inv):
                target = pos
            # keep heading to last turn's target while it still needs us
            prev = self.target.get(i)
            if target is None and prev is not None and prev in pending_tiles and prev not in claimed                     and self.can_do_something(tasks[prev], inv) and (prev in zone or prev in feed_tiles):
                target = prev
            # a wheat holder feeds: own zone's hungry animals first, then any (from mid-morning)
            if target is None and inv.get("WHEAT", 0) > 0:
                mine = [p for p in zone if p in feed_tiles]
                anyf = [p for p in feed_tiles if p not in claimed] if hour >= 6 else []
                cand = mine or anyf
                if cand:
                    target = min(cand, key=lambda p: dist(pos, p))
            if target is None:
                doable = [p for p in zone if self.can_do_something(tasks[p], inv)]
                if doable:
                    target = min(doable, key=lambda p: (self.tile_prio(p), dist(pos, p)))
                else:
                    others = [p for p in pending_tiles if p not in claimed and self.can_do_something(tasks[p], inv)]
                    if others:
                        target = min(others, key=lambda p: (self.tile_prio(p), dist(pos, p), p))
                    elif zone:
                        acts[i] = step_toward(pos, nearest_shed_tile(pos)) if not at_shed else ["PASS"]
                        continue
            self.target[i] = target
            if target is None:
                if carrying and hour >= 20 and not at_shed:
                    acts[i] = step_toward(pos, nearest_shed_tile(pos))
                elif carrying and at_shed:
                    acts[i] = ["DROP"]
                else:
                    acts[i] = ["PASS"]
                continue
            claimed.add(target)
            if pos == target:
                L = tasks[target]
                idx = next(k for k, t in enumerate(L) if not t[2] or inv.get(t[2], 0) > 0)
                op, args, need = L[idx]
                acts[i] = [op] + list(args)
                tasks[target] = L[:idx] + L[idx + 1:]
                if need:
                    inv[need] -= 1
            else:
                acts[i] = step_toward(pos, target)
        return acts

    def straw_fert_due(self, day):
        return sum(1 for _, _, t in self.plants if t["crop"] == "STRAWBERRY"
                   and (day - t["planted_day"]) in (9, 10, 13, 14) and t.get("fertilized_until_day", -1) < day)

    def straw_fert_need(self, day):
        return sum(1 for _, _, t in self.plants if t["crop"] == "STRAWBERRY"
                   and (day - t["planted_day"]) in (7, 8, 9, 11, 12, 13))

    def tile_prio(self, p):
        t = self.tiles[p[1]][p[0]]
        if isinstance(t, dict):
            if "animal" in t or t.get("crop") in ("STRAWBERRY", "MELON"):
                return 0
            if t.get("kind") in ("COOP", "PASTURE"):
                return 0
            if t.get("kind") == "WEED":
                return 2
            return 1
        return 1  # empty tile: planting

    def can_do_something(self, L, inv):
        return any((not nd) or inv.get(nd, 0) > 0 for _, _, nd in L)

    def carry_value(self, inv):
        return sum(v * self.prices.get(k, 0) for k, v in inv.items() if k in PRODUCTS)

    # ------------------------------------------------------------ market
    def sell_orders(self, day, hour):
        last_day = day == 29
        final = last_day and hour >= 16
        days_left = max(1, 29 - day)
        wheat_reserve = 0 if last_day else self.n_animals * (4 if 9 <= day <= 22 and self.prices["WHEAT"] <= 44 else 1) + 3
        upcoming = sum(1 for _, _, t in self.plants if t["crop"] == "STRAWBERRY"
                       and (day - t["planted_day"]) in (7, 8, 9, 11, 12, 13))
        fert_reserve = 0 if day >= 27 else min(upcoming, 16)
        orders = []
        for item in PRODUCTS:
            have = self.shed.get(item, 0)
            if item == "WHEAT":
                have -= wheat_reserve
            elif item == "FERTILIZER":
                have -= fert_reserve
            if have <= 0:
                continue
            base = MARKET_PARAMS[item]["base"]
            if final:
                n = have
            else:
                frac = BUILD["sell_frac"] if day < 28 else 0.2
                n = units_sellable(item, self.market_inv[item], frac * base, have)
                keep = 0 if item == "MELON" else min(12, self.drain[item] * min(BUILD["hold_days"], days_left))
                n = min(have, max(n, int(have - keep)))
            if n > 0:
                orders.append(["SELL", item, n])
        orders.sort(key=lambda o: -self.prices.get(o[1], 0) * o[2])
        if hour >= 20 and not last_day:
            carried = sum(v for u in self.units for k, v in u["inv"].items() if k in PRODUCTS)
            planned = {o[1]: o[2] for o in orders}
            projected = sum(self.shed.values()) + carried - sum(planned.values())
            if projected > SHED_CAP - 4:
                excess = projected - (SHED_CAP - 4)
                # sell the cheapest items first; a discarded unit is worth nothing. Wheat kept for
                # feed goes last (it can be rebought at hour 0).
                order = sorted(PRODUCTS, key=lambda it: self.prices.get(it, 0)) + ["WHEAT_RESERVE"]
                for item in order:
                    if excess <= 0:
                        break
                    if item == "WHEAT_RESERVE":
                        item, extra = "WHEAT", wheat_reserve
                    else:
                        extra = 0
                    if item in ANIMALS:
                        continue
                    avail = self.shed.get(item, 0) - planned.get(item, 0) - (wheat_reserve if item == "WHEAT" else 0) + extra
                    if avail <= 0:
                        continue
                    n = min(avail, excess)
                    planned[item] = planned.get(item, 0) + n
                    excess -= n
                orders = [["SELL", it, n] for it, n in planned.items() if n > 0]
                orders.sort(key=lambda o: -self.prices.get(o[1], 0) * o[2])
        return orders

    def market_orders(self, day, hour):
        last_day = day == 29
        if last_day and hour >= 16:
            self.last_orders = self.sell_orders(day, hour)[:MAX_ORDERS]
            return self.last_orders
        sells = self.sell_orders(day, hour)
        money = self.money + sum(self.prices[o[1]] * o[2] * 0.7 for o in sells[:2])
        buys = []
        T = self.targets(day)
        if day == 0 and hour == 0:
            # explicit opening: everything reinvested, plus tomorrow's feed
            return [["BUY_SEED", "MELON", BUILD["melon"]], ["BUY_ANIMAL", "COW", T["COW"]],
                    ["BUY_ANIMAL", "SHEEP", T["SHEEP"]], ["BUY_SEED", "WHEAT", BUILD["wheat_opening"]],
                    ["BUY_PRODUCT", "WHEAT", T["COW"] + T["SHEEP"] + 1]] + [["HIRE"]] * BUILD["hands"][0]

        # hires
        if hour <= 1 and not last_day:
            want = BUILD["hands"][min(day, 29)]
            if self.melon_day:
                want = 12
            have = len(self.units) - 1
            cap = 9 if self.melon_day else (8 if hour == 0 else 7)
            for _ in range(min(want - have, cap)):
                buys.append(["HIRE"])

        # feed for today
        pending = sum(self.shed.get(a, 0) for a in ANIMALS)
        wheat_now = market_price("WHEAT", self.market_inv["WHEAT"] - 1)
        days_ahead = 1
        if 6 <= day <= 22 and wheat_now <= 40:
            days_ahead = 4 if day >= 9 else 2
        shed_room = SHED_CAP - sum(self.shed.values()) - 20
        need_feed = min((self.n_animals + pending) * days_ahead, max(self.n_animals + pending, shed_room)) + (3 if day == 0 else 2)
        have_wheat = self.shed.get("WHEAT", 0) + sum(u["inv"].get("WHEAT", 0) for u in self.units)
        if not last_day and have_wheat < need_feed:
            price = market_price("WHEAT", self.market_inv["WHEAT"] - 1)
            n = min(need_feed - have_wheat, int(money // (price + 3)))
            if n > 0:
                buys.append(["BUY_PRODUCT", "WHEAT", n])
                money -= n * (price + 3)

        # land
        n_extra = len(self.unlocked) - 1
        if n_extra < T["land"] and n_extra < 2:
            cost = LAND_PRICES[n_extra]
            if money >= cost:
                buys.append(["BUY_LAND"])
                money -= cost

        # animals (cash permitting; cows before sheep before geese)
        if pending < 3:
            feed_price = market_price("WHEAT", self.market_inv["WHEAT"] - 1) + 3
            for a in ("COW", "SHEEP", "GOOSE"):
                have = self.owned(a)
                n = T[a] - have
                cost = ANIMALS[a]["cost"]
                k = 0
                while k < n and k < 2 and money >= cost + 0.5 * (self.n_animals + pending + k + 1) * feed_price:
                    k += 1
                    money -= cost
                if k:
                    buys.append(["BUY_ANIMAL", a, k])

        # seeds for today's plantings
        free_tiles = len(self.empty) + len(self.weeds)
        for crop, n in self.planting_wanted(day):
            n = min(n, free_tiles)
            have = self.seeds.get(crop, 0)
            buy = n - have
            cost = CROPS[crop]["seed"]
            if crop == "MELON" and day > 0:
                buy = min(buy, 4)
                if any(T[a] - self.owned(a) > 0 for a in ("COW", "SHEEP")) and day < 9:
                    buy = min(buy, int((money - 400) // cost))
            if crop == "STRAWBERRY":
                buy = min(buy, 5)
                animals_due = sum(max(0, T[a] - self.owned(a)) for a in ("COW", "SHEEP"))
                if animals_due > 0 and day < 9:
                    buy = min(buy, int((money - 400) // cost))  # animals first in the build phase
            elif crop == "WHEAT":
                buy = min(buy, 12)
            buy = min(buy, int(money // cost))
            if buy > 0:
                buys.append(["BUY_SEED", crop, buy])
                money -= buy * cost
            free_tiles -= n

        # fertilizer for strawberries due today
        due = sum(1 for _, _, t in self.plants if t["crop"] == "STRAWBERRY"
                  and (day - t["planted_day"]) in (9, 13) and t.get("fertilized_until_day", -1) < day)
        fp = market_price("FERTILIZER", self.market_inv["FERTILIZER"] - 1)
        wheat_due = sum(1 for _, _, t in self.plants if t["crop"] == "WHEAT"
                        and (day - t["planted_day"]) == 2 and t.get("fertilized_until_day", -1) < day)
        if due and day <= 27:
            have = self.shed.get("FERTILIZER", 0) + sum(u["inv"].get("FERTILIZER", 0) for u in self.units)
            if fp <= 0.7 * self.prices["STRAWBERRY"]:
                n = min(due - have, int((money - 100) // (fp + 3)), 12)
                if n > 0:
                    buys.append(["BUY_PRODUCT", "FERTILIZER", n])

        orders = (sells[:2] + buys + sells[2:])[:MAX_ORDERS]
        self.last_orders = orders
        return orders

    # ------------------------------------------------------------ main
    def act(self, obs):
        step = int(obs.get("step", obs["day"] * TURNS_PER_DAY + obs["hour"]))
        day, hour = step // TURNS_PER_DAY, step % TURNS_PER_DAY
        self.scan(obs)
        self.infer_opponent(step)
        self.economics(day)
        self.melon_day = any(day - d >= 10 for d in self.my_melons)
        if hour == 0:
            self.melon_rush = False
        if self.melon_day and sum(1 for d in self.opp_melons if day - d >= 10) >= 6:
            self.melon_rush = True
        tasks = self.tile_tasks(day, hour, step)
        acts = self.execute(tasks, day, hour, step)
        orders = self.market_orders(day, hour)
        n_hands = len(self.units) - 1
        return {
            "farmer": acts.get(0, ["PASS"]),
            "hands": [acts.get(i + 1, ["PASS"]) for i in range(n_hands)],
            "market": orders,
        }


_P = None


def agent(obs):
    global _P
    try:
        step = int(obs.get("step", 0))
        if _P is None or step == 0:
            _P = Planner()
        return _P.act(obs)
    except Exception:
        try:
            hands = obs["farms"][int(obs.get("player", 0))].get("hands") or []
        except Exception:
            hands = []
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []}

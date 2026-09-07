"""Greedy closed-loop Kaggriculture agent, v2: demand-aware production and selling.

Single self-contained file. Kaggle loads main.py and calls the last callable, `agent`.

v2 over v1:
  * a per-product demand model: town/shop drain, the exact price curve, the opponent's visible
    supply and our own pipeline give an "absorbable units" budget per product;
  * animals and strawberries are bought only when the budget and payback support them;
  * selling: sell above a price threshold, and dump stock the market cannot recover in time;
  * melon race: fertilize melons at age 6 so they reach full yield at age 8 and sell before the
    opponent's day-10 dump; harvested melons go straight to the shed and are sold at once;
  * land is cash-gated; production is labor-capped.
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
# steady-state units/day with daily CARE: 1 + interval per production
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
# expected units/day one random shop draw adds to each product's drain
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
PREMIUM = ("MELON", "STRAWBERRY", "MILK", "WOOL")


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
    """Units that can be sold from `inventory` before the quote drops below min_price."""
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


# ---------------------------------------------------------------- plan parameters
PLAN = {
    "melon_tiles": 12,
    "melon_last_day": 1,
    "opening_cows": 2,
    "opening_sheep": 2,
    "target_animals": {"COW": 8, "SHEEP": 6, "GOOSE": 0},
    "opening_wheat": 7,
    "opening_hands": 6,
    "max_hands": 12,
    "labor_budget": 165,        # 4.0 per animal + 1.2 per plant must stay under this
    "strawberry_per_day": 4,
    "animal_cash_priority_day": 12,  # until then seeds must leave cash for the next animal
    "sell_frac": 0.5,           # routine sells only above this fraction of base price
    "hold_days": 4,             # keep at most this many days of town drain in stock
    "land_cash": [1400, 3500],  # money needed before buying NE, SW
    "animal_last_day": 20,
    "max_animals": 20,
    "max_geese": 6,
    "strawberry_last_day": 15,
    "strawberry_first_day": 3,
    "strawberry_spec_tiles": 24,  # baseline strawberry field unless a glut is forecast
    "wheat_last_day": 25,
    "carrot_last_day": 26,
}


class Controller:
    WEIGHT = {"W": 0.0, "F": 0.0, "H": 0.5, "C": 0.5, "CF": 2.0, "P": -2.0, "B": -2.0,
              "PL": 0.0, "D": 4.0, "FZ": -2.0, "DR": -3.0}

    def __init__(self):
        self.prev_job = {}
        self.want_hands = PLAN["opening_hands"]

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
        self.seeds_orig = dict(self.seeds)
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
        self.crop_count = {}
        for _, _, t in self.plants:
            self.crop_count[t["crop"]] = self.crop_count.get(t["crop"], 0) + 1
        self.animal_count = {}
        for _, _, t in self.animals:
            self.animal_count[t["animal"]] = self.animal_count.get(t["animal"], 0) + 1
        self.market_inv = obs["market"]["inventory"]
        self.prices = obs["market"]["prices"]
        self.shops = list(obs["town"].get("unlocked_shops") or [])

    # ------------------------------------------------------------ demand model
    def farm_supply(self, farm, day):
        """Expected units/day of each product a farm will produce from now on, plus melon lumps."""
        sup = {p: 0.0 for p in PRODUCTS}
        melons = []
        for row in farm["tiles"]:
            for t in row:
                if not isinstance(t, dict):
                    continue
                if "animal" in t:
                    a = t["animal"]
                    sup[ANIMALS[a]["product"]] += ANIMAL_RATE[a]
                elif t.get("kind") == "PLANT":
                    c = t["crop"]
                    if c == "MELON":
                        melons.append(t["planted_day"])
                    elif c == "STRAWBERRY":
                        sup[c] += 0.25
                    elif c == "TOMATO":
                        sup[c] += 0.33
                    elif c == "WHEAT":
                        sup[c] += 0.8
                    elif c == "CARROT":
                        sup[c] += 1.0
        return sup, melons

    def economics(self, day):
        days_left = max(1, 29 - day)
        drain = {p: (0.0 if p == "FERTILIZER" else 1.0) for p in PRODUCTS}
        for s in self.shops:
            prods = SHOPS[s]
            mult = 2 if len(prods) == 1 else 1
            for p in prods:
                drain[p] += 6 * mult
        opp_sup, opp_melons = self.farm_supply(self.opp, day)
        my_sup, my_melons = self.farm_supply({"tiles": self.tiles}, day)
        for a in ANIMALS:
            my_sup[ANIMALS[a]["product"]] += self.shed.get(a, 0) * ANIMAL_RATE[a]
        self.drain, self.opp_sup, self.my_sup = drain, opp_sup, my_sup
        self.opp_melons, self.my_melons = opp_melons, my_melons
        # expected drain from shops not yet unlocked: one draw every 3 days, up to 8 instances
        future = {p: 0.0 for p in PRODUCTS}
        n_left = 8 - len(self.shops)
        t = (day // 3 + 1) * 3
        while n_left > 0 and t <= 27:
            for p in PRODUCTS:
                future[p] += AVG_SHOP_DRAIN.get(p, 0.0) * (29 - t)
            n_left -= 1
            t += 3
        self.budget = {}
        for p in PRODUCTS:
            base = MARKET_PARAMS[p]["base"]
            cap_now = units_sellable(p, self.market_inv[p], PLAN["sell_frac"] * base, 600)
            self.budget[p] = (cap_now + (drain[p] - opp_sup[p] - my_sup[p]) * days_left
                              + 0.8 * future[p] - self.shed.get(p, 0))

    def tiles_reserved_for_animals(self, day):
        """Empty tiles to hold back from planting so target animals still have room."""
        if day > PLAN["animal_last_day"]:
            return 0
        unmet = 0
        for a in ("COW", "SHEEP"):
            if self.budget.get(ANIMALS[a]["product"], 0) < -10:
                continue  # demand tilt will not buy these; do not hold tiles for them
            have = self.animal_count.get(a, 0) + self.shed.get(a, 0)
            unmet += max(0, PLAN["target_animals"][a] - have)
        return max(0, min(unmet, 4) - len(self.structures))

    def animal_targets_met(self):
        for a in ("COW", "SHEEP"):
            if self.animal_count.get(a, 0) + self.shed.get(a, 0) < PLAN["target_animals"][a]:
                return False
        return True

    def labor_used(self):
        # an animal costs 3 visits/day plus ~1.5 for the wheat tiles that feed it
        return 4.0 * self.n_animals + 1.2 * len(self.plants)

    # ------------------------------------------------------------ jobs
    def build_jobs(self, day, hour, step):
        P = PLAN
        jobs = []
        last_day = day == 29
        fert_stock = self.shed.get("FERTILIZER", 0) + sum(u["inv"].get("FERTILIZER", 0) for u in self.units)
        for x, y, t in self.plants:
            cd = CROPS[t["crop"]]
            age = day - t["planted_day"]
            yu = t.get("yield_units", 0)
            rush_ok = False
            rush_ok = self.melon_rush and age >= 10 and (yu >= 5 or (yu >= 4 and hour >= 6))
            if t["crop"] == "MELON" and rush_ok:
                pass  # no watering: harvest immediately
            elif not t["watered_today"]:
                if not last_day:
                    prio = 0.0 if t["consecutive_unwatered"] >= 1 else 1.0
                    if t["crop"] == "MELON" and self.melon_day and age >= 10:
                        prio = 0.4
                    jobs.append(dict(prio=prio, pos=(x, y), act=["WATER"], need=None, key=("W", x, y)))
                elif not cd["ongoing"] and (cd["max_yield_day"] + 1) // 2 <= age < cd["max_yield_day"] and yu < cd["max_yield"]:
                    jobs.append(dict(prio=1.0, pos=(x, y), act=["WATER"], need=None, key=("W", x, y)))
            # fertilizer: melons at the race age, strawberries once producing
            if not last_day and t.get("fertilized_until_day", -1) < day and fert_stock > 0:
                if t["crop"] == "STRAWBERRY" and age in (9, 10, 13, 14) and day <= 27:
                    jobs.append(dict(prio=3.0, pos=(x, y), act=["FERTILIZE"], need="FERTILIZER", key=("FZ", x, y)))
                    fert_stock -= 1
            if cd["ongoing"]:
                if yu > 0:
                    jobs.append(dict(prio=2.0, pos=(x, y), act=["HARVEST"], need=None, key=("H", x, y)))
            else:
                ready = (yu >= cd["max_yield"]
                         or (age >= cd["max_yield_day"] and (t["watered_today"] or last_day))
                         or step >= t["max_lifespan_step"] - 1
                         or (last_day and hour >= 16 and yu > 0)
                         or (t["crop"] == "MELON" and rush_ok))
                if ready and yu > 0 and age >= cd["first_yield_day"]:
                    prio = 0.3 if t["crop"] == "MELON" else 2.0
                    jobs.append(dict(prio=prio, pos=(x, y), act=["HARVEST"], need=None, key=("H", x, y)))
        for x, y, t in self.animals:
            if not last_day and not t["fed_today"]:
                prio = 0.0 if t["consecutive_unfed"] >= 1 else 1.0
                jobs.append(dict(prio=prio, pos=(x, y), act=["FEED"], need="WHEAT", key=("F", x, y)))
            if t.get("yield_units", 0) > 0:
                jobs.append(dict(prio=2.0, pos=(x, y), act=["HARVEST"], need=None, key=("H", x, y)))
            if not last_day and not t["cared_today"] and day < 28:
                jobs.append(dict(prio=3.0, pos=(x, y), act=["CARE"], need=None, key=("C", x, y)))
            if t.get("fertilizer_available") and day < 29:
                jobs.append(dict(prio=4.0, pos=(x, y), act=["COLLECT_FERTILIZER"], need=None, key=("CF", x, y)))

        waiting = {}
        for a in ANIMALS:
            n = self.shed.get(a, 0) + sum(u["inv"].get(a, 0) for u in self.units)
            if n:
                waiting[a] = n
        used = set()
        for a, n in waiting.items():
            struct = ANIMALS[a]["structure"]
            matching = [(x, y) for x, y, t in self.structures if t.get("kind") == struct and (x, y) not in used]
            for (x, y) in matching[:n]:
                jobs.append(dict(prio=0.5, pos=(x, y), act=["PLACE", a], need=a, key=("P", x, y)))
                used.add((x, y))
            short = n - len(matching[:n])
            if short > 0 and not last_day:
                for (x, y) in [p for p in self.empty_near() if p not in used][:short]:
                    jobs.append(dict(prio=0.5, pos=(x, y), act=["BUILD_" + struct], need=None, key=("B", x, y)))
                    used.add((x, y))

        if not last_day:
            free = [p for p in self.empty_near() if p not in used]
            keep = self.tiles_reserved_for_animals(day)
            if keep:
                free = free[:max(0, len(free) - keep)]
            for crop, n in self.planting_plan(day):
                avail = self.seeds.get(crop, 0)
                k = min(n, avail, len(free))
                for (x, y) in free[:k]:
                    prio = 0.5 if crop == "MELON" else 2.5
                    jobs.append(dict(prio=prio, pos=(x, y), act=["PLANT", crop], need=None, key=("PL", x, y)))
                free = free[k:]
        for (x, y) in self.weeds:
            jobs.append(dict(prio=4.5 if day <= 26 else 8.0, pos=(x, y), act=["DIG"], need=None, key=("D", x, y)))
        return jobs

    def empty_near(self):
        return sorted(self.empty, key=lambda p: dist(p, (4, 4)))

    def planting_plan(self, day):
        """[(crop, n)] in priority order, given demand budget and labor."""
        P = PLAN
        out = []
        labor_room = P["labor_budget"] - self.labor_used()
        melons = self.crop_count.get("MELON", 0)
        if day <= P["melon_last_day"] and melons < P["melon_tiles"]:
            out.append(("MELON", P["melon_tiles"] - melons))
        wheat = self.crop_count.get("WHEAT", 0)
        target_wheat = P["opening_wheat"] if day < 6 else math.ceil(self.n_animals * 1.6) + 4
        target_wheat = min(target_wheat, wheat + max(0, int(labor_room / 1.2)))
        if day <= P["wheat_last_day"] and wheat < target_wheat:
            out.append(("WHEAT", target_wheat - wheat))
            labor_room -= 1.2 * (target_wheat - wheat)
        straw = self.crop_count.get("STRAWBERRY", 0)
        if P["strawberry_first_day"] <= day <= P["strawberry_last_day"] and labor_room > 4:
            units_per_tile = 1.6 * sum(1 for a in (10, 12, 14, 16) if day + a <= 29)  # fertilized ~1.6x
            n_demand = int(self.budget["STRAWBERRY"] // max(1, units_per_tile))
            target = P["strawberry_spec_tiles"] if self.budget["STRAWBERRY"] > -20 else 0
            n = max(n_demand, target - straw)
            n = min(n, int(labor_room / 1.2), P["strawberry_per_day"])
            if n > 0:
                out.append(("STRAWBERRY", n))
        if day <= P["carrot_last_day"] and labor_room > 4:
            if self.prices["CARROT"] >= 38 and self.budget["CARROT"] > 12:
                out.append(("CARROT", min(int(labor_room / 1.2), 12)))
        if day <= P["wheat_last_day"] and labor_room > 4:
            out.append(("WHEAT", min(int(labor_room / 1.2), 12)))
        return out

    # ------------------------------------------------------------ assignment
    def assign(self, jobs, day, hour, step):
        acts = {}
        taken_tiles = set()
        last_day = day == 29
        late = hour >= 16
        unfed = [j for j in jobs if j["act"][0] == "FEED"]
        wheat_carried = sum(u["inv"].get("WHEAT", 0) for u in self.units)
        uncovered = max(0, len(unfed) - wheat_carried)
        expected_units = max(len(self.units), self.want_hands + 1)
        shed_wheat = self.shed.get("WHEAT", 0)
        by_key = {j["key"]: j for j in jobs}
        jobs_at = {}
        for j in jobs:
            jobs_at.setdefault(j["pos"], []).append(j)
        holders = []
        standing = []
        others = []
        # pass 0: a unit standing on a tile with doable work keeps that tile
        for u in self.units:
            doable = [j for j in jobs_at.get(u["pos"], [])
                      if not (j["need"] and u["inv"].get(j["need"], 0) <= 0)]
            if doable and u["pos"] not in taken_tiles:
                taken_tiles.add(u["pos"])
                self.prev_job[u["i"]] = min(doable, key=lambda j: (self.WEIGHT[j["key"][0]], j["prio"]))["key"]
                standing.append(u)
        # pass 1: units keep the tile they were walking to
        for u in self.units:
            if u in standing:
                continue
            pk = self.prev_job.get(u["i"])
            j = by_key.get(pk) if pk else None
            if j is not None and j["pos"] not in taken_tiles and not (j["need"] and u["inv"].get(j["need"], 0) <= 0 and self.shed.get(j["need"], 0) <= 0):
                taken_tiles.add(j["pos"])
                holders.append(u)
            else:
                others.append(u)
        holders = standing + holders
        order = holders + sorted(others, key=lambda u: -u["inv"].get("WHEAT", 0))
        for u in order:
            i, pos, inv = u["i"], u["pos"], u["inv"]
            at_shed = pos in SHED_TILES
            carrying = sum(v for k, v in inv.items() if k in PRODUCTS)
            carry_value = sum(v * self.prices.get(k, 0) for k, v in inv.items() if k in PRODUCTS)
            if last_day and carrying and hour >= 16:
                acts[i] = ["DROP"] if at_shed else step_toward(pos, nearest_shed_tile(pos))
                continue
            best, best_score = None, None
            prev_key = self.prev_job.get(i)
            if at_shed and not last_day and inv.get("FERTILIZER", 0) == 0 and (inv.get("WHEAT", 0) > 0 or uncovered <= 0 or hour > 4):
                fz_due = sum(1 for j in jobs if j["key"][0] == "FZ")
                have_f = self.shed.get("FERTILIZER", 0)
                if fz_due > 0 and have_f > 0:
                    n = max(1, min(have_f, math.ceil(fz_due / expected_units) + 1))
                    self.shed["FERTILIZER"] = have_f - n
                    inv["FERTILIZER"] = n
                    acts[i] = ["PICKUP", "FERTILIZER", n]
                    continue
            cands = list(jobs)
            if carry_value >= (350 if day < 10 else 1200) or inv.get("MELON", 0) >= 5:
                st = nearest_shed_tile(pos)
                cands.append(dict(prio=1.0, pos=st, act=["DROP"], need=None, key=("DR", st[0], st[1])))
            held = by_key.get(prev_key) if u in holders else None
            for j in cands:
                if j["pos"] in taken_tiles and j["key"][0] != "DR" and j is not held:
                    continue
                need = j["need"]
                d = dist(pos, j["pos"])
                if need and inv.get(need, 0) <= 0:
                    if self.shed.get(need, 0) <= 0:
                        continue
                    st = nearest_shed_tile(pos)
                    d = dist(pos, st) + dist(st, j["pos"]) + 1
                if d > 23 - hour:
                    continue
                w = self.WEIGHT[j["key"][0]]
                if j["key"][0] == "DR":
                    w = -8.0 if inv.get("MELON", 0) >= 5 else -5.0
                if j["prio"] == 0.0:
                    w -= 50
                elif j["prio"] <= 0.5:
                    w -= 4
                elif late and j["key"][0] in ("W", "F"):
                    w -= 10
                if j["key"] == prev_key:
                    w -= 1.5
                if d == 0 and j["key"][0] in ("C", "CF", "H", "FZ", "W", "F"):
                    w -= 2.5           # finish everything on this tile before walking
                score = (d + w, j["prio"])
                if best_score is None or score < best_score:
                    best, best_score = j, score
            self.prev_job[i] = best["key"] if best else None
            if best is None:
                if carrying and (at_shed or dist(pos, nearest_shed_tile(pos)) <= 3):
                    acts[i] = ["DROP"] if at_shed else step_toward(pos, nearest_shed_tile(pos))
                else:
                    acts[i] = ["PASS"]
                continue
            if best["key"][0] != "DR":
                taken_tiles.add(best["pos"])
            need = best["need"]
            if need and inv.get(need, 0) <= 0:
                if at_shed:
                    if need == "WHEAT":
                        n = max(1, min(shed_wheat, math.ceil(uncovered / expected_units) + 1))
                        shed_wheat -= n
                        uncovered = max(0, uncovered - n)
                        self.shed["WHEAT"] = shed_wheat
                    elif need == "FERTILIZER":
                        n = max(1, min(self.shed.get("FERTILIZER", 0), 4))
                        self.shed["FERTILIZER"] = self.shed.get("FERTILIZER", 0) - n
                    else:
                        n = 1
                        self.shed[need] = self.shed.get(need, 0) - 1
                    acts[i] = ["PICKUP", need, n]
                    inv[need] = inv.get(need, 0) + n
                else:
                    acts[i] = step_toward(pos, nearest_shed_tile(pos))
                continue
            if pos == best["pos"]:
                acts[i] = list(best["act"])
                op = best["act"][0]
                if op == "PLANT":
                    c = best["act"][1]
                    self.seeds[c] = self.seeds.get(c, 0) - 1
                elif op in ("FEED", "FERTILIZE", "PLACE"):
                    inv[need] -= 1
                elif op == "DROP":
                    for k in list(inv):
                        if k in PRODUCTS:
                            self.shed[k] = self.shed.get(k, 0) + inv.pop(k)
            else:
                acts[i] = step_toward(pos, best["pos"])
        return acts

    # ------------------------------------------------------------ market
    def sell_orders(self, day, hour):
        P = PLAN
        last_day = day == 29
        final = last_day and hour >= 20
        days_left = max(1, 29 - day)
        wheat_reserve = 0 if last_day else self.n_animals + 3
        fert_reserve = 0 if day >= 27 else self.fert_reserve(day)
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
            if final or (last_day and hour >= 16):
                n = have
            else:
                frac = P["sell_frac"] if day < 28 else 0.2
                n = units_sellable(item, self.market_inv[item], frac * base, have)
                # dump what the market can't absorb in time: keep only a few days of drain
                keep = self.drain[item] * min(P["hold_days"], days_left)
                if item == "MELON":
                    keep = 0
                n = max(n, int(have - keep))
                n = min(n, have)
            if n > 0:
                orders.append(["SELL", item, n])
        # highest value first, in case the slot cap bites
        orders.sort(key=lambda o: -self.prices.get(o[1], 0) * o[2])
        return orders

    def fert_reserve(self, day):
        """Fertilizer to keep for the melon race and strawberries."""
        upcoming = sum(1 for _, _, t in self.plants if t["crop"] == "STRAWBERRY"
                       and 7 <= (day - t["planted_day"]) <= 13)
        return min(upcoming, 24) if day <= 26 else 0

    def market_orders(self, obs, day, hour, step):
        P = PLAN
        orders = []
        money = self.money
        last_day = day == 29
        days_left = 29 - day
        if last_day and hour >= 16:
            return self.sell_orders(day, hour)[:MAX_ORDERS]

        # hires at hour 0/1
        if hour <= 1 and not last_day:
            work = self.labor_used() + len(self.empty) * 0.5 + len(self.weeds)
            max_hands = P["max_hands"] + (1 if day >= 10 else 0)
            want = min(max_hands, max(P["opening_hands"] if day == 0 else 3, math.ceil(work / 8)))
            if self.melon_day:
                want = P["max_hands"]
            self.want_hands = want
            have_hands = len(self.units) - 1
            cap = 9 if self.melon_day else (5 if hour == 0 else 7)
            for _ in range(min(want - have_hands, cap)):
                orders.append(["HIRE"])

        # feed shortfall first (cheap, critical)
        pending = sum(self.shed.get(a, 0) for a in ANIMALS)
        if not last_day:
            need_feed = self.n_animals + pending
            have_wheat = self.shed.get("WHEAT", 0) + sum(u["inv"].get("WHEAT", 0) for u in self.units)
            if have_wheat < need_feed:
                n = need_feed - have_wheat
                price = market_price("WHEAT", self.market_inv["WHEAT"] - 1)
                n = min(n, int(money // (price + 5)))
                if n > 0:
                    orders.append(["BUY_PRODUCT", "WHEAT", n])
                    money -= n * (price + 5)

        sells = self.sell_orders(day, hour)
        for o in sells:
            money += self.prices[o[1]] * o[2] * 0.7

        # land
        n_extra = len(self.unlocked) - 1
        if n_extra < 2 and 2 <= day <= 20:
            cost = LAND_PRICES[n_extra]
            cramped = len(self.empty) <= 2 and money >= cost + 300
            if (money >= P["land_cash"][n_extra] or cramped) and self.labor_used() < P["labor_budget"] - 15:
                orders.append(["BUY_LAND"])
                money -= cost

        # fertilizer for strawberries at their fertilize ages
        due = sum(1 for _, _, t in self.plants if t["crop"] == "STRAWBERRY"
                  and (day - t["planted_day"]) in (9, 13) and t.get("fertilized_until_day", -1) < day)
        if due and day <= 27:
            have = self.shed.get("FERTILIZER", 0) + sum(u["inv"].get("FERTILIZER", 0) for u in self.units)
            fp = market_price("FERTILIZER", self.market_inv["FERTILIZER"] - 1)
            if fp <= 0.7 * self.prices["STRAWBERRY"]:
                n = min(due - have, int((money - 200) // (fp + 3)), 12)
                if n > 0:
                    orders.append(["BUY_PRODUCT", "FERTILIZER", n])
                    money -= n * (fp + 3)

        # animals
        if day <= P["animal_last_day"] and pending < 2 and not last_day:
            if day == 0:
                for a, want in (("COW", P["opening_cows"]), ("SHEEP", P["opening_sheep"])):
                    have = self.animal_count.get(a, 0) + self.shed.get(a, 0)
                    n = want - have
                    cost = ANIMALS[a]["cost"]
                    if n > 0 and money >= n * cost + 100:
                        orders.append(["BUY_ANIMAL", a, n])
                        money -= n * cost
            else:
                labor_room = P["labor_budget"] - self.labor_used() - 4.0 * pending
                tile_room = min(len(self.empty) + len(self.structures) - pending,
                                P["max_animals"] - self.n_animals - pending)
                wheat_p = self.prices["WHEAT"]
                cands = []
                for a, spec in ANIMALS.items():
                    prod = spec["product"]
                    prod_days = days_left - spec["first_yield_day"]
                    if prod_days < 5:
                        continue
                    units = ANIMAL_RATE[a] * prod_days
                    price_est = min(self.prices[prod], MARKET_PARAMS[prod]["base"]) * 0.8
                    fert_value = min(days_left, 15) * max(10, min(45, self.prices["FERTILIZER"] * 0.5))
                    profit = units * price_est + fert_value - spec["cost"] - days_left * (wheat_p + 8)
                    have = self.animal_count.get(a, 0) + self.shed.get(a, 0)
                    target = P["target_animals"][a]
                    # tilt: a clear forecast glut lowers the target, strong demand raises it
                    if self.budget[prod] < -units:
                        target = min(target, have)          # stop adding
                    elif self.budget[prod] > 3 * units and (a != "GOOSE" or self.prices["EGG"] >= 60):
                        target += 2
                    if have >= target or profit < 200:
                        continue
                    cands.append((profit, a, units))
                cands.sort(reverse=True)
                bought = 0
                for _, a, units in cands:
                    cost = ANIMALS[a]["cost"]
                    reserve = 60 + 15 * self.n_animals
                    k = 0
                    while k < 2 and bought < 2 and money >= cost + reserve and labor_room >= 4.5 and tile_room > 0:
                        k += 1; bought += 1
                        money -= cost; labor_room -= 4.5; tile_room -= 1
                        self.budget[ANIMALS[a]["product"]] -= units
                    if k:
                        orders.append(["BUY_ANIMAL", a, k])

        # seeds
        free_tiles = max(0, len(self.empty) - self.tiles_reserved_for_animals(day))
        for crop, n in self.planting_plan(day):
            n = min(n, free_tiles)
            if n <= 0:
                continue
            have = self.seeds_orig.get(crop, 0)
            buy = n - have
            cost = CROPS[crop]["seed"]
            if crop == "MELON":
                buy = min(buy, int((money - 100) // cost))
            elif crop == "STRAWBERRY":
                # do not starve the early animal build-up
                floor = 350 if (day <= P["animal_cash_priority_day"] and not self.animal_targets_met()) else 250
                if self.prices["STRAWBERRY"] >= MARKET_PARAMS["STRAWBERRY"]["base"]:
                    floor = 120  # strawberries in scarcity pay as well as animals
                buy = min(buy, int((money - floor) // cost), P["strawberry_per_day"])
            else:
                buy = min(buy, int((money - 250) // cost), 10)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                money -= buy * cost
            free_tiles -= n

        # cash from the two biggest sells first, then purchases, then the rest of the sells
        orders = sells[:2] + orders + sells[2:]
        return orders[:MAX_ORDERS]

    # ------------------------------------------------------------ main
    def act(self, obs):
        step = int(obs.get("step", obs["day"] * TURNS_PER_DAY + obs["hour"]))
        day, hour = step // TURNS_PER_DAY, step % TURNS_PER_DAY
        self.scan(obs)
        self.economics(day)
        # melon rush: opponent melons will be dumpable today or tomorrow -> harvest ours now
        self.melon_day = any(day - d >= 10 for d in self.my_melons)
        # opponent will dump melons today too -> skip watering, harvest at 5 and sell first
        if hour == 0 or not hasattr(self, "melon_rush"):
            self.melon_rush = False
        if self.melon_day and sum(1 for d in self.opp_melons if day - d >= 10) >= 6:
            self.melon_rush = True   # latched for the rest of the day
        jobs = self.build_jobs(day, hour, step)
        acts = self.assign(jobs, day, hour, step)
        orders = self.market_orders(obs, day, hour, step)
        n_hands = len(self.units) - 1
        return {
            "farmer": acts.get(0, ["PASS"]),
            "hands": [acts.get(i + 1, ["PASS"]) for i in range(n_hands)],
            "market": orders,
        }


_CTL = None


def agent(obs):
    global _CTL
    try:
        step = int(obs.get("step", 0))
        if _CTL is None or step == 0:
            _CTL = Controller()
        return _CTL.act(obs)
    except Exception:
        try:
            hands = obs["farms"][int(obs.get("player", 0))].get("hands") or []
        except Exception:
            hands = []
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in hands], "market": []}

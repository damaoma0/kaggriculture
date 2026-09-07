"""Greedy closed-loop Kaggriculture agent, v1.

Single self-contained file (Kaggle loads main.py and calls the last callable, `agent`).

Design:
  * every turn, build a list of jobs on my farm (water, feed, harvest, care, plant, build, place,
    dig, drop) with a priority, then assign each unit (farmer + hands) the best reachable job by
    (priority, distance) and either act on it or walk one step toward it;
  * market orders: sell surplus with a slippage cap computed from the engine's exact price curve,
    then buy land / animals / seeds / feed / hands according to a simple staged plan;
  * survival invariants come first: unwatered plants and unfed animals are always the top jobs.
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
LAND_PRICES = [1000, 2000, 4000]
TURNS_PER_DAY = 24
BOARD = 10
SHED_CAP = 100
MAX_ORDERS = 10
LAST_STEP = 718  # actions at step 719 never execute


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


def units_sellable(item, inventory, min_price, have, cap):
    """How many units can be sold before the quoted price drops below min_price."""
    n = 0
    inv = inventory
    while n < have and n < cap:
        p = market_price(item, inv)
        if p < min_price:
            break
        n += 1
        if p > 1:
            inv += 1
    return n


SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]


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
    "melon_tiles": 16,
    "melon_last_day": 1,
    "opening_cows": 2,
    "opening_sheep": 0,
    "target_cows": 8,
    "target_sheep": 6,
    "animal_last_day": 18,
    "wheat_per_animal": 1.5,
    "min_wheat_tiles": 4,
    "wheat_last_day": 25,
    "filler_crop": "CARROT",
    "filler_last_day": 26,
    "strawberry_tiles": 16,
    "strawberry_last_day": 13,
    "max_hands": 12,
    "sell_frac": 0.55,          # do not sell below this fraction of base price
    "sell_chunk": 40,           # max units of one product per turn
    "land_reserve": 600,
}


class Controller:
    def __init__(self):
        self.prev_job = {}   # unit index -> job key it was pursuing last turn

    # ------------------------------------------------------------ helpers
    def scan(self, obs):
        me = obs["player"]
        farm = obs["farms"][me]
        self.tiles = farm["tiles"]
        self.money = farm["money"]
        self.unlocked = farm["unlocked_quadrants"]
        self.priv = obs["private"]
        self.shed = dict(self.priv.get("shed") or {})
        self.seeds = dict(self.priv.get("seeds") or {})
        self.seeds_orig = dict(self.seeds)
        invs = self.priv.get("inventories") or [{}]
        positions = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        self.units = []
        for i, pos in enumerate(positions):
            inv = dict(invs[i]) if i < len(invs) else {}
            self.units.append({"i": i, "pos": pos, "inv": inv})
        self.hires_today = farm["hires_today"]

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

    # ------------------------------------------------------------ jobs
    def build_jobs(self, day, hour, step):
        jobs = []  # dict(prio, pos, act, need, key)
        last_day = day == 29
        for x, y, t in self.plants:
            cd = CROPS[t["crop"]]
            age = day - t["planted_day"]
            if not t["watered_today"] and not last_day:
                prio = 0.0 if t["consecutive_unwatered"] >= 1 else 1.0
                jobs.append(dict(prio=prio, pos=(x, y), act=["WATER"], need=None, key=("W", x, y)))
            if not t["watered_today"] and last_day and not cd["ongoing"] and age < cd["max_yield_day"]:
                # last-day watering still adds a unit inside the bonus window
                if (cd["max_yield_day"] + 1) // 2 <= age:
                    jobs.append(dict(prio=1.0, pos=(x, y), act=["WATER"], need=None, key=("W", x, y)))
            yu = t.get("yield_units", 0)
            if cd["ongoing"]:
                if yu > 0:
                    jobs.append(dict(prio=2.0, pos=(x, y), act=["HARVEST"], need=None, key=("H", x, y)))
            else:
                ready = (yu >= cd["max_yield"]
                         or (age >= cd["max_yield_day"] and (t["watered_today"] or last_day))
                         or step >= t["max_lifespan_step"] - 1
                         or (last_day and hour >= 18 and yu > 0))
                if ready and yu > 0 and age >= cd["first_yield_day"]:
                    jobs.append(dict(prio=2.0, pos=(x, y), act=["HARVEST"], need=None, key=("H", x, y)))
        for x, y, t in self.animals:
            if not last_day and not t["fed_today"]:
                prio = 0.0 if t["consecutive_unfed"] >= 1 else 1.0
                jobs.append(dict(prio=prio, pos=(x, y), act=["FEED"], need="WHEAT", key=("F", x, y)))
            if t.get("yield_units", 0) > 0:
                jobs.append(dict(prio=2.0, pos=(x, y), act=["HARVEST"], need=None, key=("H", x, y)))
            if not last_day and not t["cared_today"] and day < 28:
                jobs.append(dict(prio=3.0, pos=(x, y), act=["CARE"], need=None, key=("C", x, y)))
            if t.get("fertilizer_available"):
                jobs.append(dict(prio=4.0, pos=(x, y), act=["COLLECT_FERTILIZER"], need=None, key=("CF", x, y)))

        # animals waiting in shed or in hands -> empty structures / build pastures
        waiting = {}
        for a in ANIMALS:
            n = self.shed.get(a, 0) + sum(u["inv"].get(a, 0) for u in self.units)
            if n:
                waiting[a] = n
        empty_structs = [(x, y, t) for x, y, t in self.structures]
        for a, n in waiting.items():
            struct = ANIMALS[a]["structure"]
            matching = [(x, y) for x, y, t in empty_structs if t.get("kind") == struct]
            for (x, y) in matching[:n]:
                jobs.append(dict(prio=0.5, pos=(x, y), act=["PLACE", a], need=a, key=("P", x, y)))
            short = n - len(matching)
            if short > 0 and not last_day:
                for (x, y) in self.pick_empty(short):
                    jobs.append(dict(prio=0.5, pos=(x, y), act=["BUILD_" + struct], need=None, key=("B", x, y)))

        # planting
        if not last_day:
            plants_wanted = self.planting_plan(day)
            used = set(j["pos"] for j in jobs if j["key"][0] == "B")
            free = [p for p in self.empty if p not in used]
            free.sort(key=lambda p: dist(p, (4, 4)))
            for crop, n in plants_wanted:
                avail = self.seeds.get(crop, 0)
                for (x, y) in free[:min(n, avail)]:
                    jobs.append(dict(prio=5.5, pos=(x, y), act=["PLANT", crop], need=None, key=("PL", x, y)))
                free = free[min(n, avail):]
        for (x, y) in self.weeds:
            jobs.append(dict(prio=4.5 if day <= 26 else 8.0, pos=(x, y), act=["DIG"], need=None, key=("D", x, y)))
        return jobs

    def pick_empty(self, n, prefer_far=False):
        cand = list(self.empty)
        cand.sort(key=lambda p: dist(p, (4, 4)), reverse=prefer_far)
        return cand[:n]

    def planting_plan(self, day):
        """Return [(crop, n_to_plant), ...] in priority order."""
        P = PLAN
        out = []
        melons = self.crop_count.get("MELON", 0)
        if day <= P["melon_last_day"] and melons < P["melon_tiles"]:
            out.append(("MELON", P["melon_tiles"] - melons))
        wheat = self.crop_count.get("WHEAT", 0)
        target_wheat = max(P["min_wheat_tiles"], math.ceil(self.n_animals * P["wheat_per_animal"]))
        if day <= P["wheat_last_day"] and wheat < target_wheat:
            out.append(("WHEAT", target_wheat - wheat))
        straw = self.crop_count.get("STRAWBERRY", 0)
        if 8 <= day <= P["strawberry_last_day"] and straw < P["strawberry_tiles"]:
            out.append(("STRAWBERRY", P["strawberry_tiles"] - straw))
        if day <= P["filler_last_day"]:
            out.append((P["filler_crop"], 99))
        return out

    # ------------------------------------------------------------ assignment
    # Walking is the dominant cost, so jobs are scored as distance + weight, where the weight
    # says how far it is worth walking for that job class relative to a routine feed/water.
    WEIGHT = {"W": 0.0, "F": 0.0, "H": 0.5, "C": 1.0, "CF": 1.5, "P": -2.0, "B": -2.0, "PL": 2.0, "D": 4.0}

    def assign(self, jobs, day, hour, step):
        acts = {}
        taken_tiles = set()
        last_day = day == 29
        late = hour >= 16
        unfed = [j for j in jobs if j["act"][0] == "FEED"]
        wheat_carried = sum(u["inv"].get("WHEAT", 0) for u in self.units)
        uncovered = max(0, len(unfed) - wheat_carried)
        expected_units = max(len(self.units), getattr(self, "want_hands", 3) + 1)
        shed_wheat = self.shed.get("WHEAT", 0)
        order = sorted(self.units, key=lambda u: -u["inv"].get("WHEAT", 0))
        for u in order:
            i, pos, inv = u["i"], u["pos"], u["inv"]
            at_shed = pos in SHED_TILES
            carrying = sum(v for k, v in inv.items() if k in PRODUCTS)
            if last_day and carrying and hour >= 16:
                acts[i] = ["DROP"] if at_shed else step_toward(pos, nearest_shed_tile(pos))
                continue
            best, best_score = None, None
            prev_key = self.prev_job.get(i)
            for j in jobs:
                if j["pos"] in taken_tiles:
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
                if j["prio"] == 0.0:
                    w -= 50            # dies tonight
                elif late and j["key"][0] in ("W", "F"):
                    w -= 10            # must still be done today
                if j["key"] == prev_key:
                    w -= 0.6           # sticky
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
            taken_tiles.add(best["pos"])
            need = best["need"]
            if need and inv.get(need, 0) <= 0:
                if at_shed:
                    if need == "WHEAT":
                        n = max(1, min(shed_wheat, math.ceil(uncovered / expected_units) + 1))
                        shed_wheat -= n
                        uncovered = max(0, uncovered - n)
                        self.shed["WHEAT"] = shed_wheat
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
                if best["act"][0] == "PLANT":
                    c = best["act"][1]
                    self.seeds[c] = self.seeds.get(c, 0) - 1
                elif best["act"][0] == "FEED":
                    inv["WHEAT"] -= 1
                elif best["act"][0] == "PLACE":
                    inv[need] -= 1
            else:
                acts[i] = step_toward(pos, best["pos"])
        return acts

    # ------------------------------------------------------------ market
    def market_orders(self, obs, day, hour, step, jobs):
        P = PLAN
        orders = []
        money = self.money
        inv_mkt = obs["market"]["inventory"]
        last_day = day == 29
        final = last_day and hour >= 20

        # --- hires (hour 0 and 1 to fit within 10 orders)
        if hour <= 1 and not last_day:
            work = self.n_animals * 3 + len(self.plants) * 1.3 + len(self.empty) * 1.5 + len(self.weeds)
            want = min(P["max_hands"], max(3, math.ceil(work / 12)))
            self.want_hands = want
            have_hands = len(self.units) - 1
            for _ in range(min(want - have_hands, 6)):
                orders.append(["HIRE"])

        # --- sells
        wheat_reserve = 0 if last_day else self.n_animals * 2 + 2
        for item in PRODUCTS:
            have = self.shed.get(item, 0)
            if item == "WHEAT":
                have -= wheat_reserve
            if have <= 0:
                continue
            base = MARKET_PARAMS[item]["base"]
            if final:
                n = have
            else:
                n = units_sellable(item, inv_mkt[item], P["sell_frac"] * base, have, P["sell_chunk"])
            if n > 0 and len(orders) < MAX_ORDERS - 3:
                orders.append(["SELL", item, n])
        if final:
            return [o for o in orders if o[0] == "SELL"][:MAX_ORDERS]

        # --- land
        n_extra = len(self.unlocked) - 1
        if n_extra < 2 and 1 <= day <= 20:
            cost = LAND_PRICES[n_extra]
            if money >= cost + P["land_reserve"]:
                orders.append(["BUY_LAND"])
                money -= cost

        # --- animals
        cows = sum(1 for _, _, t in self.animals if t["animal"] == "COW") + self.shed.get("COW", 0)
        sheep = sum(1 for _, _, t in self.animals if t["animal"] == "SHEEP") + self.shed.get("SHEEP", 0)
        pending = self.shed.get("COW", 0) + self.shed.get("SHEEP", 0)
        if day <= P["animal_last_day"] and pending < 2:
            if day == 0:
                wants = [("COW", P["opening_cows"] - cows), ("SHEEP", P["opening_sheep"] - sheep)]
            else:
                wants = [("COW", P["target_cows"] - cows), ("SHEEP", P["target_sheep"] - sheep)]
                # keep ratio: alternate
                if sheep * P["target_cows"] < cows * P["target_sheep"]:
                    wants.reverse()
            wheat_need = math.ceil((self.n_animals + pending + 2) * P["wheat_per_animal"])
            room_tiles = len(self.empty) + len(self.structures) - max(0, wheat_need - self.crop_count.get("WHEAT", 0))
            for a, n in wants:
                if n <= 0 or room_tiles <= 0:
                    continue
                cost = ANIMALS[a]["cost"]
                reserve = 200 + 30 * self.n_animals if day > 0 else 100
                k = 0
                while k < n and k < 2 and money >= cost + reserve and room_tiles > 0:
                    k += 1
                    money -= cost
                    room_tiles -= 1
                if k:
                    orders.append(["BUY_ANIMAL", a, k])
                    if day == 0:
                        break

        # --- seeds for tomorrow's / next turn's planting
        wanted = self.planting_plan(day)
        free_tiles = len(self.empty)
        for crop, n in wanted:
            n = min(n, free_tiles)
            if n <= 0:
                continue
            have = self.seeds_orig.get(crop, 0)
            buy = n - have
            cost = CROPS[crop]["seed"]
            if crop == "MELON":
                buy = min(buy, int((money - 150) // cost))
            else:
                buy = min(buy, int((money - 300) // cost), 8)
            if buy > 0:
                orders.append(["BUY_SEED", crop, buy])
                money -= buy * cost
            free_tiles -= n

        # --- feed shortfall
        if not last_day:
            need_feed = self.n_animals + pending
            have_wheat = self.shed.get("WHEAT", 0) + sum(u["inv"].get("WHEAT", 0) for u in self.units)
            if have_wheat < need_feed:
                n = need_feed - have_wheat
                price = market_price("WHEAT", inv_mkt["WHEAT"] - 1)
                n = min(n, int(money // (price + 5)))
                if n > 0:
                    orders.insert(0, ["BUY_PRODUCT", "WHEAT", n])
        return orders[:MAX_ORDERS]

    # ------------------------------------------------------------ main
    def act(self, obs):
        step = int(obs.get("step", obs["day"] * TURNS_PER_DAY + obs["hour"]))
        day, hour = step // TURNS_PER_DAY, step % TURNS_PER_DAY
        self.scan(obs)
        jobs = self.build_jobs(day, hour, step)
        acts = self.assign(jobs, day, hour, step)
        orders = self.market_orders(obs, day, hour, step, jobs)
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

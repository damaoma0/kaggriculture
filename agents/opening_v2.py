"""Growth opening controller. Research baseline, not a finished 30-day agent.

No recorded actions or legacy planner are used. Targets describe a farm layout;
workers choose legal jobs from the current observation. The experiment harness
can construct OpeningPolicy with alternative opening configurations.
"""

DEFAULT = {
    "cash_crop": "WHEAT", "harvest_age": 4, "hands": 6,
    "animals": ["COW", "COW", "SHEEP", "SHEEP"],
    "melons": 8, "strawberries": 0, "strawberry_day": 4,
    "land_day": 99, "land_buffer": 700,
}
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
SEED_COST = {"WHEAT": 10, "CARROT": 20, "MELON": 80, "STRAWBERRY": 100, "TOMATO": 50}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def move(pos, goal):
    if pos[0] != goal[0]:
        return ["EAST" if pos[0] < goal[0] else "WEST"]
    if pos[1] != goal[1]:
        return ["SOUTH" if pos[1] < goal[1] else "NORTH"]
    return ["PASS"]


class OpeningPolicy:
    def __init__(self, config=None):
        self.config = dict(DEFAULT, **(config or {}))
        self.targets = {}
        self.day = -1

    def layout(self, farm, day):
        # NW slots stay stable when NE is purchased. Animal pens are closest
        # to the starting shed access point; premium crops follow them.
        coords = sorted(((x, y) for y in range(5) for x in range(5)),
                        key=lambda p: (distance(p, (4, 4)), p[1], p[0]))
        if "NE" in farm["unlocked_quadrants"]:
            coords += sorted(((x, y) for y in range(5) for x in range(5, 10)),
                             key=lambda p: (distance(p, (5, 4)), p[1], p[0]))
        layout = {}
        cfg = self.config
        for i, pos in enumerate(coords):
            if i < len(cfg["animals"]):
                layout[pos] = cfg["animals"][i]
            elif i < len(cfg["animals"]) + cfg["melons"]:
                layout[pos] = "MELON"
            elif (day >= cfg["strawberry_day"] and
                  i < len(cfg["animals"]) + cfg["melons"] + cfg["strawberries"]):
                layout[pos] = "STRAWBERRY"
            else:
                layout[pos] = cfg["cash_crop"]
        return layout

    def __call__(self, obs):
        cfg = self.config
        day, hour = obs["day"], obs["hour"]
        if self.day != day or obs["step"] == 0:
            self.targets = {}
            self.day = day
        farm = obs["farms"][obs["player"]]
        private = obs["private"]
        tiles = farm["tiles"]
        layout = self.layout(farm, day)
        stocks = dict(private["shed"])
        seeds = dict(private["seeds"])
        positions = [farm["farmer"], *farm["hands"]]
        inventories = private["inventories"]
        claims = set()
        actions = []

        def to_shed(pos):
            return min(SHED, key=lambda p: distance(pos, p))

        def job(pos, inv, target, desired):
            x, y = target
            tile = tiles[y][x]
            d = distance(pos, target)
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                age = day - tile["planted_day"]
                crop = tile["crop"]
                due = {"WHEAT": cfg["harvest_age"], "CARROT": min(3, cfg["harvest_age"]),
                       "MELON": 10, "STRAWBERRY": 10, "TOMATO": 8}.get(crop, 99)
                bonus_start = {"WHEAT": 2, "CARROT": 2, "MELON": 6}.get(crop, 99)
                peak = {"WHEAT": 4, "CARROT": 3, "MELON": 6}.get(crop, 99)
                # Take today's yield bonus before harvesting a one-time crop.
                bonus = bonus_start <= age <= {"WHEAT": 4, "CARROT": 3, "MELON": 12}.get(crop, -1) and tile["yield_units"] < peak
                if not tile["watered_today"] and (tile["consecutive_unwatered"] >= 1 or bonus):
                    return 24 if age >= due else (18 if tile["consecutive_unwatered"] >= 1 else 12), ["WATER"]
                if age >= due and tile["yield_units"]:
                    return 24, ["HARVEST"]
                return None
            if desired in ANIMAL_COST:
                if isinstance(tile, dict) and tile.get("animal"):
                    if not tile["fed_today"]:
                        if inv.get("WHEAT", 0):
                            return 22, ["FEED"]
                        if stocks.get("WHEAT", 0) > 0:
                            return 21, ["PICKUP", "WHEAT", min(2, stocks["WHEAT"]) ]
                    if tile.get("yield_units", 0):
                        return 17, ["HARVEST"]
                    if not tile["cared_today"]:
                        return 15, ["CARE"]
                    if tile["fertilizer_available"]:
                        return 14, ["COLLECT_FERTILIZER"]
                    return None
                if hour + d + 4 >= 24:
                    return None
                if inv.get(desired, 0):
                    if tile is None:
                        return 19, ["BUILD_COOP" if desired == "GOOSE" else "BUILD_PASTURE"]
                    if tile.get("kind") == "WEED":
                        return 19, ["DIG"]
                    return 19, ["PLACE", desired, 1]
                if stocks.get(desired, 0):
                    return 19, ["PICKUP", desired, 1]
                return None
            if hour + d + 3 >= 24:
                return None
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                if seeds.get(desired, 0):
                    return 5, ["DIG"]
            if tile is None and seeds.get(desired, 0):
                return 7, ["PLANT", desired]
            return None

        # Reserve in-flight assignments across turns. Without this, a nearer
        # worker can repeatedly steal another worker's destination.
        owners = {}
        for idx, target in list(self.targets.items()):
            if idx < len(positions) and target in layout and job(positions[idx], inventories[idx], target, layout[target]):
                owners[target] = idx
            else:
                del self.targets[idx]

        for idx, pos in enumerate(positions):
            inv = inventories[idx]
            carried_animal = any(inv.get(a, 0) for a in ANIMAL_COST)
            goods = sum(n for item, n in inv.items() if item not in ANIMAL_COST and item != "WHEAT")
            if tuple(pos) in SHED and not carried_animal and (goods or inv.get("WHEAT", 0) > 2):
                actions.append(["DROP"])
                continue
            choices = []
            for target, desired in layout.items():
                if target in claims:
                    continue
                if target in owners and owners[target] != idx:
                    continue
                if carried_animal and not inv.get(desired, 0):
                    continue
                task = job(pos, inv, target, desired)
                if not task:
                    continue
                priority, operation = task
                goal = to_shed(pos) if operation[0] == "PICKUP" else target
                travel = distance(pos, goal)
                if operation[0] == "PICKUP":
                    travel += distance(goal, target)
                # Finish work underfoot and keep assignments stable in transit.
                score = priority - 2 * travel + (7 if tuple(pos) == target else 0)
                score += 100 if self.targets.get(idx) == target else 0
                choices.append((score, target, goal, operation))
            if choices:
                _, target, goal, operation = max(choices, key=lambda c: c[0])
                claims.add(target)
                self.targets[idx] = target
                if tuple(pos) != goal:
                    actions.append(move(pos, goal))
                else:
                    actions.append(operation)
                    if operation[0] == "PICKUP":
                        stocks[operation[1]] -= operation[2]
                    elif operation[0] == "PLANT":
                        seeds[operation[1]] -= 1
            elif any(inv.values()) and not carried_animal:
                goal = to_shed(pos)
                actions.append(["DROP"] if tuple(pos) == goal else move(pos, goal))
            else:
                actions.append(["PASS"])

        market = []
        cash = farm["money"]
        animal_count = len(cfg["animals"])
        # Sales are requested against observed shed stock. Do not budget their
        # proceeds before execution, because simultaneous trades change prices.
        for item, amount in private["shed"].items():
            keep = animal_count * 2 if item == "WHEAT" else 0
            if item not in ANIMAL_COST and amount > keep:
                market.append(["SELL", item, amount - keep])
        if len(farm["hands"]) < cfg["hands"] and hour < 12:
            a, b = 1, 1
            for _ in range(farm["hires_today"]):
                a, b = b, a + b
            if cash >= a:
                market.append(["HIRE"])
                cash -= a
        owned_wheat = stocks.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in inventories)
        wanted = max(0, animal_count * 2 - owned_wheat)
        if wanted and cash >= (obs["market"]["prices"]["WHEAT"] + 5) * wanted:
            market.append(["BUY_PRODUCT", "WHEAT", wanted])
            cash -= (obs["market"]["prices"]["WHEAT"] + 5) * wanted
        for animal in dict.fromkeys(cfg["animals"]):
            alive = sum(1 for row in tiles for t in row if isinstance(t, dict) and t.get("animal") == animal)
            owned = alive + private["shed"].get(animal, 0) + sum(inv.get(animal, 0) for inv in inventories)
            wanted = cfg["animals"].count(animal) - owned
            count = min(wanted, max(0, int((cash - 80) // ANIMAL_COST[animal])))
            if count > 0:
                market.append(["BUY_ANIMAL", animal, count])
                cash -= ANIMAL_COST[animal] * count
        if (day >= cfg["land_day"] and "NE" not in farm["unlocked_quadrants"]
                and cash >= 1000 + cfg["land_buffer"]):
            market.append(["BUY_LAND"])
            cash -= 1000
        needed = {}
        for (x, y), crop in layout.items():
            tile = tiles[y][x]
            if crop in SEED_COST and (tile is None or isinstance(tile, dict) and tile.get("kind") == "WEED"):
                needed[crop] = needed.get(crop, 0) + 1
        for crop in sorted(needed, key=lambda c: c != "MELON"):
            count = min(8, needed[crop] - private["seeds"].get(crop, 0), max(0, int((cash - 50) // SEED_COST[crop])))
            if count > 0:
                market.append(["BUY_SEED", crop, count])
                cash -= SEED_COST[crop] * count
        return {"farmer": actions[0], "hands": actions[1:], "market": market[:10]}


GROWTH_DEFAULT = {
    "cows": 8, "sheep": 4, "initial_animals": 4,
    "grow_day": 2, "grow_every": 1, "melons": 12, "strawberries": 18,
    "strawberry_day": 3, "land_day": 3, "land_buffer": 100,
    "hands": 8, "late_hands": 10, "late_hands_day": 5,
    "cash_crop": "WHEAT", "harvest_age": 4,
}


class GrowthOpening(OpeningPolicy):
    def __init__(self, config=None):
        self.growth = dict(GROWTH_DEFAULT, **(config or {}))
        c, s = self.growth["cows"], self.growth["sheep"]
        self.herd = []
        # Alternate additions so later sheep are not all deferred behind cows.
        while c or s:
            if c:
                self.herd.append("COW")
                c -= 1
            if s:
                self.herd.append("SHEEP")
                s -= 1
        super().__init__()

    def layout(self, farm, day):
        coords = []
        for quadrant, x0, y0, shed in (("NW", 0, 0, (4,4)), ("NE", 5, 0, (5,4)), ("SW", 0, 5, (4,5))):
            if quadrant in farm["unlocked_quadrants"]:
                coords += sorted(((x, y) for y in range(y0, y0+5) for x in range(x0, x0+5)),
                                 key=lambda p: (distance(p, shed), p[1], p[0]))
        layout = {}
        cfg = self.growth
        for i, pos in enumerate(coords):
            if i < len(self.herd):
                if i < len(self.config["animals"]):
                    layout[pos] = self.herd[i]
                # Future pens are reserved, so expanding the herd never moves
                # the melon/strawberry target locations under existing crops.
            elif i < len(self.herd) + cfg["melons"]:
                layout[pos] = "MELON"
            elif i < len(self.herd) + cfg["melons"] + cfg["strawberries"]:
                if day >= cfg["strawberry_day"]:
                    layout[pos] = "STRAWBERRY"
            else:
                layout[pos] = cfg["cash_crop"]
        return layout

    def __call__(self, obs):
        cfg = self.growth
        extra = max(0, (obs["day"] - cfg["grow_day"]) // cfg["grow_every"] + 1)
        size = min(len(self.herd), cfg["initial_animals"] + extra)
        self.config.update({k: cfg[k] for k in ("cash_crop", "harvest_age", "melons", "strawberries", "strawberry_day", "land_day", "land_buffer")})
        self.config["animals"] = self.herd[:size]
        self.config["hands"] = cfg["hands"] if obs["day"] < cfg["late_hands_day"] else cfg["late_hands"]
        return super().__call__(obs)


# Frozen after the full-season shortlist comparison. Keep experiment defaults
# unchanged so named candidates remain reproducible.
SELECTED_GROWTH = dict(GROWTH_DEFAULT, cows=4, sheep=4)
_growth_policy = None


def agent(obs):
    global _growth_policy
    if _growth_policy is None or obs["step"] == 0:
        _growth_policy = GrowthOpening(SELECTED_GROWTH)
    return _growth_policy(obs)

"""Minimum maintenance that still gives FULL production, measured with the official engine (1.32.7).

Part A -- pure Python, no engine import (copy into a single-file agent if wanted):
    required_actions(kind, state, day, hour=8, fertilize=False) -> {action: units lost if skipped today}
    remaining_value(kind, state, day, price, ...) -> (remaining units, maintenance visit-days)
    remaining_value_detail(...) -> dict with the plan and a cost breakdown
  `state` is the engine's tile dict (PLANT or animal tile). The model is an exact day-level copy of
  data/kaggriculture.py (WATER/FERTILIZE/HARVEST/FEED/CARE, _decay_plants, _daily_refresh_*), checked
  against the engine on random states by the experiments below. Future days are solved by DP:
  maximise units harvested by the end of the season (step 718 = day 29 hour 22 is the last executed
  action; the last end-of-day refresh is day 28), tie-break fewest visit-days, fewest action turns,
  earliest tile release.

Part B -- experiments (python scripts/min_maintenance.py): single-tile schedules driven through the
  engine's own functions (_new_plant/_new_animal, _apply_unit_action, _decay_plants,
  _daily_refresh_plants/_animals) step by step, plus two tiny scripted real games (kaggle_environments)
  that confirm one crop and one animal schedule end to end. Writes results/fresh/min_maintenance/.
"""
import copy
import importlib.util
import itertools
import json
import math
import os
import random
import sys
import time

TURNS = 24
LAST_STEP = 718          # last executed action (episodeSteps 720; DONE fires after step 718)
LAST_DAY = LAST_STEP // TURNS          # 29
LAST_REFRESH_DAY = LAST_DAY - 1        # 28: the day-29 refresh (step 719) never runs

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
BASE_PRICE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
              "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}


# ----------------------------------------------------------------------------------------------
# Part A: pure model
# ----------------------------------------------------------------------------------------------
def _kind_of(kind, state):
    if kind:
        return kind
    if isinstance(state, dict):
        return state.get("crop") or state.get("animal")
    return None


def _to_tuple(kind, state):
    """Engine tile dict -> hashable model state (None if nothing alive on the tile)."""
    if not isinstance(state, dict):
        return None
    if kind in CROPS:
        if state.get("kind") != "PLANT":
            return None
        return (int(state["planted_day"]), int(state["consecutive_unwatered"]), int(state["yield_units"]),
                int(state.get("fertilized_until_day", -1)), int(state["max_lifespan_step"]),
                bool(state["watered_today"]))
    if kind in ANIMALS:
        if "animal" not in state:
            return None
        return (int(state["placed_day"]), int(state["consecutive_unfed"]), int(state.get("pending_care_bonus", 0)),
                int(state["yield_units"]), bool(state["fed_today"]), bool(state["cared_today"]))
    return None


def new_plant_state(crop, day):
    cd = CROPS[crop]
    return {"kind": "PLANT", "crop": crop, "planted_day": day, "watered_today": False,
            "consecutive_unwatered": 1, "yield_units": 0 if cd["ongoing"] else 1,
            "max_lifespan_step": (-1 if cd["ongoing"] else (day + cd["max_yield_day"] + 1) * TURNS),
            "fertilized_until_day": -1}


def new_animal_state(animal, day):
    return {"kind": ANIMALS[animal]["structure"], "animal": animal, "placed_day": day, "yield_units": 0,
            "consecutive_unfed": 0, "fed_today": False, "cared_today": False,
            "fertilizer_available": False, "pending_care_bonus": 0}


def _decay(yu, mls, s0, s1):
    """_decay_plants over steps s0..s1-1 (after each step's actions). None = became a weed."""
    if mls < 0:
        return yu
    for s in range(max(s0, mls), s1):
        if (s - mls) % 2 == 0:
            yu -= 1
            if yu <= 0:
                return None
    return yu


def crop_day(crop, st, day, water, fert, harvest, hour):
    """One day on a crop tile; actions at `hour` in the order FERTILIZE, WATER, HARVEST.
    Returns (state or None (weed) or 'GONE' (harvested one-time crop), units harvested)."""
    cd = CROPS[crop]
    planted, cu, yu, fud, mls, wt = st
    base = day * TURNS
    end = min(base + TURNS, LAST_STEP + 1)
    yu = _decay(yu, mls, base, base + hour)
    if yu is None:
        return None, 0
    if fert:
        fud = max(fud, day + 2)
    if water and not wt:
        wt = True
        if not cd["ongoing"]:
            age = day - planted
            if (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]:
                yu = min(cd["max_yield"], yu + (2 if fud >= day else 1))
    units = 0
    if harvest and yu > 0 and day - planted >= cd["first_yield_day"]:
        units, yu = yu, 0
        if not cd["ongoing"]:
            return "GONE", units
    yu = _decay(yu, mls, base + hour, end)
    if yu is None:
        return None, units
    if day > LAST_REFRESH_DAY:
        return (planted, cu, yu, fud, mls, wt), units
    was = wt
    cu = 0 if was else cu + 1
    if cu >= 2:
        return None, units
    if cd["ongoing"]:
        dsf = day + 1 - planted - cd["first_yield_day"]
        if dsf >= 0 and dsf % cd["interval"] == 0:
            pc = dsf // cd["interval"] + 1
            if pc <= cd["max_yield"]:
                yu = min(cd["max_yield"], yu + (2 if (was and fud >= day) else 1))
                if pc == cd["max_yield"]:
                    mls = (day + 2) * TURNS
    return (planted, cu, yu, fud, mls, False), units


def animal_day(animal, st, day, feed, care, harvest):
    """One day on an animal tile. Returns (state or None (escaped), units harvested)."""
    a = ANIMALS[animal]
    placed, cu, pend, yu, ft, ct = st
    ft = ft or feed
    ct = ct or care
    units = 0
    if harvest and yu > 0:
        units, yu = yu, 0
    if day > LAST_REFRESH_DAY:
        return (placed, cu, pend, yu, ft, ct), units
    cu = 0 if ft else cu + 1
    if cu >= 2:
        return None, units
    dsf = day + 1 - placed - a["first_yield_day"]
    if dsf >= 0 and dsf % a["interval"] == 0:
        yu = min(a["max_held"], yu + 1 + (pend if ft else 0))
        pend = 0
    if ct and ft:
        pend += 1
    return (placed, cu, pend, yu, False, False), units


class _Solver:
    """DP over the rest of the season for one tile. Value tuple:
    (econ, units, -visit_days, -turns, -release_day)."""

    def __init__(self, kind, fertilize=False, price=1.0, wheat_price=0.0, fert_price=0.0,
                 visit_cost=0.0, turn_cost=0.0, future_hour=8):
        self.kind = kind
        self.is_crop = kind in CROPS
        self.fertilize = fertilize
        self.price, self.wheat_price, self.fert_price = price, wheat_price, fert_price
        self.visit_cost, self.turn_cost = visit_cost, turn_cost
        self.future_hour = future_hour
        self.memo = {}

    def combos(self, st, day):
        out = []
        if self.is_crop:
            planted, cu, yu, fud, mls, wt = st
            can_h = yu > 0 and day - planted >= CROPS[self.kind]["first_yield_day"]
            for w in ((0, 1) if not wt else (0,)):
                for f in ((0, 1) if self.fertilize else (0,)):
                    for h in ((0, 1) if can_h else (0,)):
                        out.append((w, f, h))
        else:
            placed, cu, pend, yu, ft, ct = st
            for f in ((0, 1) if not ft else (0,)):
                for c in ((0, 1) if not ct else (0,)):
                    for h in ((0, 1) if yu > 0 else (0,)):
                        out.append((f, c, h))
        return out

    def step(self, st, day, combo, hour):
        if self.is_crop:
            w, f, h = combo
            st2, u = crop_day(self.kind, st, day, w, f, h, hour)
            turns = w + f + h
            econ = u * self.price - f * self.fert_price
        else:
            f, c, h = combo
            st2, u = animal_day(self.kind, st, day, f, c, h)
            turns = f + c + h
            econ = u * self.price - f * self.wheat_price
        visits = 1 if turns else 0
        econ -= visits * self.visit_cost + turns * self.turn_cost
        release = day if st2 == "GONE" else 0
        return st2, (round(econ, 9), u, -visits, -turns, -release)

    def value(self, st, day):
        if st is None or st == "GONE" or day > LAST_DAY:
            return (0, 0, 0, 0, 0), None
        key = (st, day)
        if key in self.memo:
            return self.memo[key]
        best = None
        for combo in self.combos(st, day):
            st2, v = self.step(st, day, combo, self.future_hour)
            fut, _ = self.value(st2, day + 1)
            tot = tuple(a + b for a, b in zip(v, fut))
            if best is None or tot > best[0]:
                best = (tot, (combo, st2))
        self.memo[key] = best
        return best

    def today(self, st, day, hour, must=None, forbid=None):
        """Best total from `day` with today's actions at `hour`, optionally forcing/forbidding one
        action index. Returns (value tuple, combo) or (None, None)."""
        best = (None, None)
        for combo in self.combos(st, day):
            if must is not None and not combo[must]:
                continue
            if forbid is not None and combo[forbid]:
                continue
            st2, v = self.step(st, day, combo, hour)
            fut, _ = self.value(st2, day + 1)
            tot = tuple(a + b for a, b in zip(v, fut))
            if best[0] is None or tot > best[0]:
                best = (tot, combo)
        return best

    def plan(self, st, day, hour):
        """Optimal plan from (st, day): list of (day, [actions]) with units harvested."""
        names = ("WATER", "FERTILIZE", "HARVEST") if self.is_crop else ("FEED", "CARE", "HARVEST")
        out = []
        tot, combo = self.today(st, day, hour)
        if combo is None:
            return out
        d, s, c, hr = day, st, combo, hour
        while s is not None and s != "GONE" and d <= LAST_DAY and c is not None:
            s2, v = self.step(s, d, c, hr)
            acts = [n for n, x in zip(names, c) if x]
            if acts:
                out.append((d, acts, v[1]))
            d += 1
            s = s2
            hr = self.future_hour
            if s is None or s == "GONE" or d > LAST_DAY:
                break
            _, nxt = self.value(s, d)
            c = nxt[0] if nxt else None
        return out


def required_actions(kind, state, day, hour=8, fertilize=False, future_hour=8):
    """Per-tile maintenance values for TODAY: {action: units lost if that action is skipped today,
    with every other action (today and later) chosen optimally}. Units are the tile's own product
    (COLLECT_FERTILIZER: fertilizer units). Actions already done today are omitted. A value of 0
    means it can safely wait. `fertilize` lets the plan use FERTILIZE (today and later)."""
    kind = _kind_of(kind, state)
    st = _to_tuple(kind, state)
    out = {}
    if st is None:
        return out
    S = _Solver(kind, fertilize=fertilize, future_hour=future_hour)
    names = ("WATER", "FERTILIZE", "HARVEST") if kind in CROPS else ("FEED", "CARE", "HARVEST")
    for i, name in enumerate(names):
        if name == "FERTILIZE" and not fertilize:
            continue
        w, _ = S.today(st, day, hour, must=i)
        if w is None:
            continue
        wo, _ = S.today(st, day, hour, forbid=i)
        out[name] = max(0, w[1] - (wo[1] if wo is not None else 0))
    if kind in ANIMALS and state.get("fertilizer_available"):
        out["COLLECT_FERTILIZER"] = 1   # does not accumulate: skipping it today loses it
    return out


def remaining_value_detail(kind, state, day, price=None, hour=8, fertilize=False, wheat_price=0.0,
                           fert_price=0.0, visit_cost=0.0, turn_cost=0.0, future_hour=8):
    kind = _kind_of(kind, state)
    st = _to_tuple(kind, state)
    if price is None:
        price = BASE_PRICE.get(kind, BASE_PRICE.get(ANIMALS.get(kind, {}).get("product"), 1))
    res = {"kind": kind, "day": day, "units": 0, "visits": 0, "turns": 0, "waters": 0, "ferts": 0,
           "feeds": 0, "cares": 0, "harvests": 0, "net_value": 0.0, "plan": []}
    if st is None:
        return res
    S = _Solver(kind, fertilize=fertilize, price=price, wheat_price=wheat_price, fert_price=fert_price,
                visit_cost=visit_cost, turn_cost=turn_cost, future_hour=future_hour)
    tot, _ = S.today(st, day, hour)
    if tot is None:
        return res
    plan = S.plan(st, day, hour)
    res.update(units=tot[1], visits=-tot[2], turns=-tot[3], net_value=tot[0], plan=plan)
    for _, acts, _u in plan:
        for a in acts:
            key = {"WATER": "waters", "FERTILIZE": "ferts", "FEED": "feeds", "CARE": "cares",
                   "HARVEST": "harvests"}[a]
            res[key] += 1
    return res


def remaining_value(kind, state, day, price=None, **kw):
    """(expected remaining units under minimum maintenance until the last executed step, the
    visit-days that requires). With price/wheat_price/visit_cost/turn_cost given, the DP instead
    maximises units*price - feeds*wheat_price - visits*visit_cost - turns*turn_cost (so 0 units
    means: abandon). Deterministic engine, so 'expected' = exact given optimal maintenance."""
    d = remaining_value_detail(kind, state, day, price=price, **kw)
    return d["units"], d["visits"]


# ----------------------------------------------------------------------------------------------
# Part B: experiments with the engine's own functions
# ----------------------------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "fresh", "min_maintenance")


def load_engine():
    """The installed engine module (it reads its JSON spec at import), asserted byte-identical to
    data/kaggriculture.py."""
    import hashlib
    import kaggle_environments.envs.kaggriculture.kaggriculture as E
    with open(E.__file__, "rb") as f:
        a = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
    with open(os.path.join(ROOT, "data", "kaggriculture.py"), "rb") as f:
        b = hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
    assert a == b, "installed engine differs from data/kaggriculture.py"
    E.SHA256 = a
    return E


class Harness:
    """One tile on a 1x1 farm, driven through the engine functions step by step."""

    def __init__(self, E, tile, feed_stock=999):
        self.E = E
        self.farm = {"tiles": [[tile]], "farmer": [0, 0], "hands": [], "money": 0.0}
        inv = {"FERTILIZER": 999}
        if feed_stock:
            inv["WHEAT"] = feed_stock
        self.private = {"shed": {}, "seeds": {c: 99 for c in E.CROPS}, "inventories": [inv]}

    @property
    def tile(self):
        return self.farm["tiles"][0][0]

    def act(self, op, day, product=None):
        inv = self.private["inventories"][0]
        before = inv.get(product, 0) if product else 0
        self.E._apply_unit_action(self.farm, self.private, 0, op, 1, day, TURNS)
        return (inv.get(product, 0) - before) if product else 0

    def run_day(self, day, acts, product):
        """acts: {hour: [op, ...]}. Returns units of `product` gained by HARVEST/COLLECT today."""
        got = 0
        for hour in range(TURNS):
            step = day * TURNS + hour
            if step > LAST_STEP:
                break
            for op in acts.get(hour, []):
                got += self.act(op, day, product)
            self.E._decay_plants(self.farm, step)
            if hour == TURNS - 1:
                self.E._daily_refresh_plants(self.farm, day, TURNS)
                self.E._daily_refresh_animals(self.farm, day)
        return got


def tile_desc(t):
    if t is None:
        return "EMPTY"
    if isinstance(t, dict) and t.get("kind") == "WEED":
        return "WEED"
    if isinstance(t, dict) and "animal" not in t and t.get("kind") in ("COOP", "PASTURE"):
        return "ESCAPED"
    return "ALIVE"


# ---------------- crops ----------------
def crop_meta(crop):
    cd = CROPS[crop]
    if cd["ongoing"]:
        last_ref = cd["first_yield_day"] - 1 + (cd["max_yield"] - 1) * cd["interval"]
        return {"water_days": list(range(0, last_ref + 1)), "last_prod_refresh_age": last_ref,
                "final_age": last_ref + 1,
                "prod_refresh_ages": [cd["first_yield_day"] - 1 + k * cd["interval"] for k in range(cd["max_yield"])]}
    return {"water_days": list(range(0, cd["max_yield_day"] + 1)), "final_age": cd["max_yield_day"],
            "window": [(cd["max_yield_day"] + 1) // 2, cd["max_yield_day"]]}


def sim_crop(E, crop, water_days, fert_days=(), harvest=None, P=0, end_age=None):
    """Engine run of one crop planted at day P (ages = day - P). harvest: dict age -> hour, or
    'daily' (hour 20 every day, captures production without cap losses). Returns summary."""
    cd = CROPS[crop]
    h = Harness(E, None, feed_stock=0)
    h.act(["PLANT", crop], P)
    meta = crop_meta(crop)
    end_age = meta["final_age"] + 2 if end_age is None else end_age
    total, events, death = 0, [], None
    for age in range(0, end_age + 1):
        day = P + age
        if day > LAST_DAY:
            break
        acts = {}
        if age in fert_days:
            acts.setdefault(1, []).append(["FERTILIZE"])
        if age in water_days:
            acts.setdefault(2, []).append(["WATER"])
        if harvest == "daily":
            acts.setdefault(20, []).append(["HARVEST"])
        elif harvest and age in harvest:
            acts.setdefault(harvest[age], []).append(["HARVEST"])
        got = h.run_day(day, acts, crop)
        if got:
            events.append((age, got))
            total += got
        d = tile_desc(h.tile)
        if d != "ALIVE":
            if d == "WEED":
                death = age
            break
    return {"units": total, "harvests": events, "died_age": death}


def enum_crop(E, crop, fert_days=()):
    """DFS over every watering subset (prefix-shared, engine functions). One-time crops: harvest
    right after the day's watering on any age in [first_yield_day, max_yield_day]; ongoing crops:
    harvest daily at hour 20 to measure production. Returns list of leaves."""
    cd = CROPS[crop]
    meta = crop_meta(crop)
    leaves = []
    h0 = Harness(E, None, feed_stock=0)
    h0.act(["PLANT", crop], 0)
    start = h0.tile

    def run(tile, day, water, harvest_hour):
        h = Harness(E, copy.deepcopy(tile), feed_stock=0)
        acts = {}
        if day in fert_days:
            acts.setdefault(1, []).append(["FERTILIZE"])
        if water:
            acts.setdefault(2, []).append(["WATER"])
        if harvest_hour is not None:
            acts.setdefault(harvest_hour, []).append(["HARVEST"])
        got = h.run_day(day, acts, crop)
        return h.tile, got

    if cd["ongoing"]:
        last = meta["final_age"]

        def rec(tile, day, wset, units, prods):
            if day == last:   # final harvest day: no watering needed
                t2, got = run(tile, day, 0, 3)
                leaves.append({"water": wset, "units": units + got, "prod": prods + ([(day, got)] if got else []),
                               "died": None})
                return
            for w in (1, 0):
                t2, got = run(tile, day, w, 20)
                ws = wset + [day] if w else wset
                pr = prods + ([(day, got)] if got else [])
                if tile_desc(t2) != "ALIVE":
                    leaves.append({"water": ws, "units": units + got, "prod": pr, "died": day})
                    continue
                rec(t2, day + 1, ws, units + got, pr)
        rec(start, 0, [], 0, [])
    else:
        top = cd["max_yield_day"]

        def rec(tile, day, wset):
            for w in (1, 0):
                ws = wset + [day] if w else wset
                if day >= cd["first_yield_day"]:
                    t2, got = run(tile, day, w, 3)
                    leaves.append({"water": ws, "units": got, "harvest_age": day, "died": None})
                if day == top:
                    continue
                t2, got = run(tile, day, w, None)
                if tile_desc(t2) != "ALIVE":
                    leaves.append({"water": ws, "units": 0, "harvest_age": None, "died": day})
                    continue
                rec(t2, day + 1, ws)
        rec(start, 0, [])
    return leaves


def analyse_crop(E, crop, fert_days=()):
    cd = CROPS[crop]
    meta = crop_meta(crop)
    leaves = enum_crop(E, crop, fert_days)
    alive = [l for l in leaves if l["died"] is None or cd["ongoing"]]
    if cd["ongoing"]:
        ref = next(l for l in leaves if l["water"] == meta["water_days"])
        full = [l for l in leaves if l["units"] == ref["units"] and l["prod"] == ref["prod"]]
    else:
        # reference: daily watering, harvest at the earliest age with the maximum reachable units
        daily = [l for l in leaves if l["died"] is None and l["water"] == list(range(0, l["harvest_age"] + 1))]
        mx = max(l["units"] for l in daily)
        ref = min((l for l in daily if l["units"] == mx), key=lambda l: l["harvest_age"])
        full = [l for l in leaves if l["died"] is None and l["units"] == ref["units"]
                and l["harvest_age"] == ref["harvest_age"]]
    nmin = min(len(l["water"]) for l in full)
    mins = [l["water"] for l in full if len(l["water"]) == nmin]
    canon = sorted(mins, key=lambda w: (-sum(1 for d in w if d % 2 == 0), w))[0]
    # marginal value of each watering in the canonical minimum schedule
    marg = []
    for d in canon:
        ws = [x for x in canon if x != d]
        harv = "daily" if cd["ongoing"] else {ref["harvest_age"]: 3}
        strict = sim_crop(E, crop, ws, fert_days, harv, end_age=meta["final_age"])
        strict = {"units": strict["units"], "died": strict["died_age"]}
        others = [l for l in leaves if d not in l["water"] and (cd["ongoing"] or l["died"] is None)]
        best_u = max(l["units"] for l in others) if others else 0
        best_n = min(len(l["water"]) for l in others if l["units"] == best_u) if others else 0
        marg.append({"age": d, "strict_units_lost": ref["units"] - strict["units"],
                     "strict_died_age": strict["died"],
                     "repaired_units_lost": ref["units"] - best_u,
                     "repaired_extra_waterings": best_n - nmin})
    res = {"crop": crop, "fert_days": list(fert_days), "ref_units": ref["units"],
           "ref_waterings": len(ref["water"]), "min_waterings": nmin, "n_min_schedules": len(mins),
           "min_schedules": mins[:40], "canonical_min": canon, "marginal": marg,
           "n_leaves": len(leaves)}
    if cd["ongoing"]:
        res["production"] = ref["prod"]
    else:
        res["harvest_age"] = ref["harvest_age"]
    return res


def crop_harvest_timing(E, crop, water_days, fert_days=()):
    cd = CROPS[crop]
    meta = crop_meta(crop)
    out = {}
    if not cd["ongoing"]:
        rows = []
        for age in range(cd["first_yield_day"], cd["max_yield_day"] + 3):
            for hour in ([3] if age <= cd["max_yield_day"] else [0, 1, 2, 3, 4, 6, 8, 10, 12, 16, 23]):
                r = sim_crop(E, crop, [a for a in water_days if a <= age], fert_days, {age: hour},
                             end_age=age)
                rows.append({"age": age, "hour": hour, "units": r["units"], "died_age": r["died_age"]})
        out["harvest_at"] = rows
    else:
        last = meta["final_age"]
        # minimal harvest sets given the watering schedule
        span = list(range(cd["first_yield_day"], last + 2))
        full = sim_crop(E, crop, water_days, fert_days, "daily")["units"]
        best = None
        for k in range(1, len(span) + 1):
            for hs in itertools.combinations(span, k):
                r = sim_crop(E, crop, water_days, fert_days, {a: 3 for a in hs})
                if r["units"] == full:
                    best = list(hs) if best is None else best
                    out.setdefault("min_harvest_sets", []).append(list(hs))
            if best is not None:
                break
        out["full_units"] = full
        out["min_harvests"] = len(best)
        # cost of skipping each harvest of the first minimal set
        skip = []
        for a in best:
            hs = [x for x in best if x != a]
            r = sim_crop(E, crop, water_days, fert_days, {x: 3 for x in hs})
            skip.append({"age": a, "units_lost": full - r["units"]})
        out["skip_harvest"] = skip
        # final harvest delay
        rows = []
        prev = [x for x in best if x != best[-1]]
        for age in (last, last + 1, last + 2):
            for hour in ([3] if age == last else [0, 1, 2, 3, 4, 6, 8, 12, 23]):
                hs = {x: 3 for x in prev}
                hs[age] = hour
                r = sim_crop(E, crop, water_days, fert_days, hs, end_age=age)
                rows.append({"age": age, "hour": hour, "units": r["units"]})
        out["final_harvest_at"] = rows
    return out


# ---------------- animals ----------------
def animal_engine_dp(E, animal, P, feed_hour=1, care_hour=2, harvest_hour=3):
    """Exhaustive DP over daily {FEED, CARE, HARVEST} from placement day P to the season end,
    every transition executed by the engine's own functions. Objective: max units harvested,
    then fewest visit-days, then fewest turns, then fewest feeds."""
    product = ANIMALS[animal]["product"]
    memo = {}

    def build(key):
        cu, pend, yu = key
        t = E._new_animal(animal, P)
        t.update(consecutive_unfed=cu, pending_care_bonus=pend, yield_units=yu)
        return t

    def trans(key, day, combo):
        f, c, hv = combo
        h = Harness(E, build(key))
        acts = {}
        if f:
            acts.setdefault(feed_hour, []).append(["FEED"])
        if c:
            acts.setdefault(care_hour, []).append(["CARE"])
        if hv:
            acts.setdefault(harvest_hour, []).append(["HARVEST"])
        got = h.run_day(day, acts, product)
        t = h.tile
        if "animal" not in t:
            return None, got
        return (t["consecutive_unfed"], t["pending_care_bonus"], t["yield_units"]), got

    def V(key, day):
        if key is None or day > LAST_DAY:
            return (0, 0, 0, 0), None
        mk = (key, day)
        if mk in memo:
            return memo[mk]
        best = None
        for combo in itertools.product((0, 1), repeat=3):
            if combo[2] and key[2] == 0:
                continue
            k2, got = trans(key, day, combo)
            turns = sum(combo)
            v = (got, -(1 if turns else 0), -turns, -combo[0])
            fut, _ = V(k2, day + 1)
            tot = tuple(a + b for a, b in zip(v, fut))
            if best is None or tot > best[0]:
                best = (tot, (combo, k2))
        memo[mk] = best
        return best

    start = (0, 0, 0)
    tot, _ = V(start, P)
    plan, key, day = [], start, P
    while key is not None and day <= LAST_DAY:
        _, (combo, k2) = V(key, day)
        plan.append((day, combo))
        key, day = k2, day + 1
    return {"units": tot[0], "visits": -tot[1], "turns": -tot[2], "feeds": -tot[3], "plan": plan}


def sim_animal(E, animal, P, feeds, cares, harvests, collect_days=()):
    """Engine run of an explicit schedule (sets of days). Returns units, fertilizer and fate."""
    product = ANIMALS[animal]["product"]
    h = Harness(E, E._new_animal(animal, P))
    units, fert, events, fate = 0, 0, [], None
    for day in range(P, LAST_DAY + 1):
        acts = {}
        if day in feeds:
            acts.setdefault(1, []).append(["FEED"])
        if day in cares:
            acts.setdefault(2, []).append(["CARE"])
        if day in harvests:
            acts.setdefault(3, []).append(["HARVEST"])
        got = h.run_day(day, acts, product) if not collect_days else None
        if collect_days:
            got = 0
            # interleave a fertilizer collection at hour 4
            if day in collect_days:
                acts.setdefault(4, []).append(["COLLECT_FERTILIZER"])
            inv = h.private["inventories"][0]
            fb = inv.get("FERTILIZER", 0)
            got = h.run_day(day, acts, product)
            fert += inv.get("FERTILIZER", 0) - fb
        if got:
            events.append((day, got))
            units += got
        if "animal" not in h.tile:
            fate = day
            break
    return {"units": units, "events": events, "escaped_day": fate, "fertilizer": fert}


def production_days(animal, P):
    a = ANIMALS[animal]
    return [d for d in range(P, LAST_REFRESH_DAY + 1)
            if d + 1 - P - a["first_yield_day"] >= 0 and (d + 1 - P - a["first_yield_day"]) % a["interval"] == 0]


# ---------------- verification ----------------
def verify_pure_vs_engine(E, n=4000, seed=7):
    rng = random.Random(seed)
    bad = []
    for i in range(n):
        if rng.random() < 0.55:
            crop = rng.choice(list(CROPS))
            cd = CROPS[crop]
            P = rng.randint(0, 20)
            day = P + rng.randint(0, 17)
            if day > LAST_DAY:
                continue
            t = E._new_plant(crop, P, TURNS)
            t["consecutive_unwatered"] = rng.choice([0, 1])
            t["yield_units"] = rng.randint(0 if cd["ongoing"] else 1, cd["max_yield"])
            if cd["ongoing"] and day - P < cd["first_yield_day"]:
                t["yield_units"] = 0   # engine invariant (avoids its immature-harvest warning)
            t["fertilized_until_day"] = rng.choice([-1, day - 1, day, day + 1, day + 2])
            if cd["ongoing"] and rng.random() < 0.3:
                t["max_lifespan_step"] = (day + rng.randint(-1, 1)) * TURNS
            t["watered_today"] = rng.random() < 0.2
            w, f, hv = rng.randint(0, 1), rng.randint(0, 1), rng.randint(0, 1)
            hour = rng.randint(0, 23)
            st = _to_tuple(crop, t)
            s2, u = crop_day(crop, st, day, w, f, hv, hour)
            h = Harness(E, copy.deepcopy(t), feed_stock=0)
            acts = {}
            for op, on in ((["FERTILIZE"], f), (["WATER"], w), (["HARVEST"], hv)):
                if on:
                    acts.setdefault(hour, []).append(op)
            got = h.run_day(day, acts, crop)
            et = h.tile
            if et is None:
                es = "GONE"
            elif et.get("kind") == "WEED":
                es = None
            else:
                es = _to_tuple(crop, et)
            if (es, got) != (s2, u):
                bad.append({"crop": crop, "tile": t, "day": day, "acts": [w, f, hv, hour], "engine": [es, got],
                            "model": [s2, u]})
        else:
            an = rng.choice(list(ANIMALS))
            a = ANIMALS[an]
            P = rng.randint(0, 25)
            day = P + rng.randint(0, 12)
            if day > LAST_DAY:
                continue
            t = E._new_animal(an, P)
            t["consecutive_unfed"] = rng.choice([0, 1])
            t["pending_care_bonus"] = rng.randint(0, 8)
            t["yield_units"] = rng.randint(0, a["max_held"])
            t["fed_today"] = rng.random() < 0.2
            t["cared_today"] = rng.random() < 0.2
            fd, ca, hv = rng.randint(0, 1), rng.randint(0, 1), rng.randint(0, 1)
            st = _to_tuple(an, t)
            s2, u = animal_day(an, st, day, fd, ca, hv)
            h = Harness(E, copy.deepcopy(t))
            acts = {}
            for hr, (op, on) in enumerate(((["FEED"], fd), (["CARE"], ca), (["HARVEST"], hv))):
                if on:
                    acts.setdefault(hr + 1, []).append(op)
            got = h.run_day(day, acts, a["product"])
            et = h.tile
            es = _to_tuple(an, et) if "animal" in et else None
            if (es, got) != (s2, u):
                bad.append({"animal": an, "tile": t, "day": day, "acts": [fd, ca, hv], "engine": [es, got],
                            "model": [s2, u]})
    return {"trials": n, "mismatches": len(bad), "examples": bad[:5]}


def real_game_checks():
    """Two tiny scripted games through kaggle_environments (the real interpreter)."""
    from kaggle_environments import make
    results = {}

    # Game A: fertilised wheat, waterings at ages {0,2,3,4}, fertilise at age 2, harvest age 4.
    def wheat_agent(obs, cfg=None):
        step = obs["step"]
        d, hr = divmod(step, TURNS)
        act = {"farmer": ["PASS"], "hands": [], "market": []}
        if step == 0:
            act["market"] = [["BUY_SEED", "WHEAT", 1], ["BUY_PRODUCT", "FERTILIZER", 1]]
        elif d == 0 and hr == 1:
            act["farmer"] = ["PLANT", "WHEAT"]
        elif d == 0 and hr == 2:
            act["farmer"] = ["WATER"]
        elif d == 2 and hr == 1:
            act["farmer"] = ["PICKUP", "FERTILIZER", 1]
        elif d == 2 and hr == 2:
            act["farmer"] = ["FERTILIZE"]
        elif d in (2, 3, 4) and hr == 3:
            act["farmer"] = ["WATER"]
        elif d == 4 and hr == 4:
            act["farmer"] = ["HARVEST"]
        return act

    # Game B: sheep placed day 0 on the spawn tile, the DP minimum schedule for P=0.
    E = load_engine()
    dp = animal_engine_dp(E, "SHEEP", 0)
    sched = {d: c for d, c in dp["plan"]}
    n_feed = sum(c[0] for c in sched.values())

    def sheep_agent(obs, cfg=None):
        step = obs["step"]
        d, hr = divmod(step, TURNS)
        act = {"farmer": ["PASS"], "hands": [], "market": []}
        if step == 0:
            act["farmer"] = ["BUILD_PASTURE"]
            act["market"] = [["BUY_ANIMAL", "SHEEP", 1], ["BUY_PRODUCT", "WHEAT", n_feed]]
            return act
        if d == 0 and hr == 1:
            act["farmer"] = ["PICKUP", "SHEEP", 1]
            return act
        if d == 0 and hr == 2:
            act["farmer"] = ["PLACE", "SHEEP"]
            return act
        c = sched.get(d, (0, 0, 0))
        base = 3 if d == 0 else 1
        if hr == base and c[0]:
            act["farmer"] = ["PICKUP", "WHEAT", 1]
        elif hr == base + 1 and c[0]:
            act["farmer"] = ["FEED"]
        elif hr == base + 2 and c[1]:
            act["farmer"] = ["CARE"]
        elif hr == base + 3 and c[2]:
            act["farmer"] = ["HARVEST"]
        return act

    def pass_agent(obs, cfg=None):
        return {"farmer": ["PASS"], "hands": [], "market": []}

    for name, agent, product in (("wheat_fert_age2_water_0234", wheat_agent, "WHEAT"),
                                 ("sheep_P0_dp_min", sheep_agent, "WOOL")):
        env = make("kaggriculture", debug=True)
        env.run([agent, pass_agent])
        priv = env.state[0].observation.private
        shed = priv["shed"].get(product, 0)
        inv = sum(i.get(product, 0) for i in priv["inventories"])
        tile = env.state[0].observation.farms[0]["tiles"][4][4]
        results[name] = {"shed": shed, "unit_inventory": inv, "total": shed + inv,
                         "steps": len(env.steps), "final_tile": tile,
                         "status": [s.status for s in env.state]}
    results["sheep_P0_dp_min"]["dp_units"] = dp["units"]
    results["sheep_P0_dp_min"]["wheat_bought"] = n_feed
    results["sheep_P0_dp_min"]["wool_total"] = results["sheep_P0_dp_min"]["total"]
    return results


# ---------------- main ----------------
def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    E = load_engine()
    R = {"engine": os.path.join("data", "kaggriculture.py"), "last_step": LAST_STEP,
         "last_refresh_day": LAST_REFRESH_DAY}
    R["verify_pure_vs_engine"] = verify_pure_vs_engine(E)
    print("verify", R["verify_pure_vs_engine"]["mismatches"], "mismatches", flush=True)

    # ---- crops ----
    crops = {}
    for crop in CROPS:
        cd = CROPS[crop]
        meta = crop_meta(crop)
        rows = {}
        rows["none"] = analyse_crop(E, crop, ())
        days = meta["water_days"]
        fsets = [(a,) for a in days]
        if cd["ongoing"]:
            # fertiliser acts on ongoing crops only through the production refresh (d..d+2), so
            # days before the first production refresh - 2 cannot matter (singles above show it)
            lo = meta["prod_refresh_ages"][0] - 2
            fsets += list(itertools.combinations([d for d in days if d >= lo], 2))
        fres = []
        for fs in fsets:
            r = analyse_crop(E, crop, fs)
            fres.append({"fert_days": list(fs), "ref_units": r["ref_units"], "min_waterings": r["min_waterings"],
                         "ref_waterings": r["ref_waterings"], "timing": r.get("harvest_age", r.get("production"))})
        mx = max(f["ref_units"] for f in fres)
        bestf = [f for f in fres if f["ref_units"] == mx]
        nf = min(len(f["fert_days"]) for f in bestf)
        bestf = [f for f in bestf if len(f["fert_days"]) == nf]
        nw = min(f["min_waterings"] for f in bestf)
        bestf_min = [f for f in bestf if f["min_waterings"] == nw]
        # also: best single fertiliser (ongoing crops)
        singles = [f for f in fres if len(f["fert_days"]) == 1]

        def visit_count(an, tm):
            hsets = tm.get("min_harvest_sets") or [[an["harvest_age"]]]
            best = None
            for hs in hsets:
                for ws in an["min_schedules"]:
                    days = set(ws) | set(an["fert_days"]) | set(hs)
                    n = len(days)
                    turns = len(ws) + len(an["fert_days"]) + len(hs)
                    if best is None or n < best["visits"]:
                        best = {"visits": n, "turns": turns, "water": ws, "harvest": list(hs)}
            return best

        rows["timing_unfert"] = crop_harvest_timing(E, crop, rows["none"]["canonical_min"])
        rows["unfert_min_visits"] = visit_count(rows["none"], rows["timing_unfert"])
        best_plan = None
        for cand in bestf_min:
            an = analyse_crop(E, crop, tuple(cand["fert_days"]))
            tm = crop_harvest_timing(E, crop, an["canonical_min"], tuple(cand["fert_days"]))
            vc = visit_count(an, tm)
            if best_plan is None or (vc["visits"], vc["turns"]) < (best_plan[2]["visits"], best_plan[2]["turns"]):
                best_plan = (an, tm, vc)
        rows["fert_best"], rows["timing_fert"], rows["fert_min_visits"] = best_plan
        chosen = rows["fert_best"]["fert_days"]
        rows["fert_best_all_plans"] = bestf_min
        rows["fert_single_by_day"] = [{"day": f["fert_days"][0], "units": f["ref_units"],
                                       "min_waterings": f["min_waterings"]} for f in singles]
        # pure-model DP check (units, waterings) for the same plans
        S = remaining_value_detail(crop, new_plant_state(crop, 0), 0, price=1, hour=2, future_hour=3)
        rows["pure_dp_unfert"] = {"units": S["units"], "waters": S["waters"], "visits": S["visits"],
                                  "plan": S["plan"]}
        Sf = remaining_value_detail(crop, new_plant_state(crop, 0), 0, price=1, hour=2, future_hour=3,
                                    fertilize=True, fert_price=1e-3)
        rows["pure_dp_fert"] = {"units": Sf["units"], "waters": Sf["waters"], "ferts": Sf["ferts"],
                                "visits": Sf["visits"], "plan": Sf["plan"]}
        # planting-day table (pure DP; checked against engine sims for the unfert canonical schedule)
        pt = []
        for P in range(0, LAST_DAY + 1):
            u = remaining_value_detail(crop, new_plant_state(crop, P), P, price=1, hour=2, future_hour=3)
            uf = remaining_value_detail(crop, new_plant_state(crop, P), P, price=1, hour=2, future_hour=3,
                                        fertilize=True, fert_price=1e-3)
            pt.append({"P": P, "units": u["units"], "visits": u["visits"], "waters": u["waters"],
                       "units_fert": uf["units"], "ferts": uf["ferts"]})
        rows["planting_table"] = pt
        full_u = rows["none"]["ref_units"]
        full_f = rows["fert_best"]["ref_units"]
        rows["last_P_full"] = max([r["P"] for r in pt if r["units"] >= full_u], default=None)
        rows["last_P_full_fert"] = max([r["P"] for r in pt if r["units_fert"] >= full_f], default=None)
        rows["last_P_any"] = max([r["P"] for r in pt if r["units"] >= 1], default=None)
        # engine check of the canonical schedule planted late
        if rows["last_P_full"] is not None:
            P = rows["last_P_full"]
            canon = rows["none"]["canonical_min"]
            harv = ("daily" if cd["ongoing"] else {rows["none"]["harvest_age"]: 3})
            chk = sim_crop(E, crop, canon, (), harv, P=P)
            rows["late_engine_check"] = {"P": P, "units": chk["units"], "harvests": chk["harvests"]}
        if crop == "MELON":
            # fertilise at age 6 (covers 6,7,8) and keep the plain every-other-day survival pattern
            rows["fert6_every_other_day"] = sim_crop(E, "MELON", [0, 2, 4, 6, 8, 10], (6,), {10: 3})
            rows["unfert_every_other_day_to_12"] = sim_crop(E, "MELON", [0, 2, 4, 6, 8, 10, 12], (), {12: 3})
        if crop == "WHEAT":
            rows["three_waterings"] = {"0_2_3_harvest3": sim_crop(E, "WHEAT", [0, 2, 3], (), {3: 3}),
                                       "0_2_4_harvest4": sim_crop(E, "WHEAT", [0, 2, 4], (), {4: 3})}
        crops[crop] = rows
        print(crop, "done", round(time.time() - t0, 1), "s", flush=True)
    R["crops"] = crops

    # ---- animals ----
    animals = {}
    for an, a in ANIMALS.items():
        rows = {}
        pdays = production_days(an, 0)
        dp = animal_engine_dp(E, an, 0)
        feeds = {d for d, c in dp["plan"] if c[0]}
        cares = {d for d, c in dp["plan"] if c[1]}
        harvs = {d for d, c in dp["plan"] if c[2]}
        allD = set(range(0, LAST_DAY + 1))
        ref = sim_animal(E, an, 0, allD, allD, allD)
        feedonly = sim_animal(E, an, 0, allD, set(), allD)
        eod = set(range(0, LAST_DAY + 1, 2)) | {1}
        survive = sim_animal(E, an, 0, set(range(1, LAST_DAY + 1, 2)), set(), allD)
        mn = sim_animal(E, an, 0, feeds, cares, harvs)
        rows["production_refresh_days_P0"] = pdays
        rows["dp_min"] = {"units": dp["units"], "visits": dp["visits"], "turns": dp["turns"],
                          "feeds": sorted(feeds), "cares": sorted(cares), "harvests": sorted(harvs),
                          "engine_replay_units": mn["units"]}
        rows["reference_daily_feed_care_harvest"] = {"units": ref["units"], "visits": 30, "turns": 90,
                                                     "feeds": 30}
        rows["feed_daily_no_care"] = {"units": feedonly["units"]}
        rows["survival_feeds_only_odd_days"] = {"units": survive["units"], "escaped": survive["escaped_day"],
                                                "feeds": len(range(1, LAST_DAY + 1, 2))}
        # pure DP agreement for every placement day
        agree = []
        for P in range(0, LAST_DAY + 1):
            e = animal_engine_dp(E, an, P)
            p = remaining_value_detail(an, new_animal_state(an, P), P, price=1)
            agree.append({"P": P, "engine_units": e["units"], "engine_visits": e["visits"],
                          "engine_feeds": e["feeds"], "engine_turns": e["turns"],
                          "pure_units": p["units"], "pure_visits": p["visits"], "pure_feeds": p["feeds"],
                          "pure_cares": p["cares"], "pure_harvests": p["harvests"]})
        rows["placement_table"] = agree
        # marginal value of each feed / care in the min schedule (strict skip)
        marg = []
        for d in sorted(feeds | cares):
            r = {"day": d, "production_day": d in pdays}
            if d in feeds:
                s = sim_animal(E, an, 0, feeds - {d}, cares, harvs)
                r["skip_feed_units_lost"] = mn["units"] - s["units"]
                r["skip_feed_escaped"] = s["escaped_day"]
            if d in cares:
                s = sim_animal(E, an, 0, feeds, cares - {d}, harvs)
                r["skip_care_units_lost"] = mn["units"] - s["units"]
            marg.append(r)
        rows["marginal"] = marg
        # harvest skip costs
        hs = []
        for d in sorted(harvs):
            s = sim_animal(E, an, 0, feeds, cares, harvs - {d})
            hs.append({"day": d, "units_lost": mn["units"] - s["units"]})
        rows["skip_harvest"] = hs
        # fertilizer collection: daily vs every other day (non-accumulation)
        f_daily = sim_animal(E, an, 0, allD, allD, allD, collect_days=allD)
        f_alt = sim_animal(E, an, 0, allD, allD, allD, collect_days=set(range(0, LAST_DAY + 1, 2)))
        rows["collect_fertilizer"] = {"daily_collect_total": f_daily["fertilizer"],
                                      "every_other_day_total": f_alt["fertilizer"]}
        # payback: base prices, wheat 25 per feed, labour free / 5 per visit
        pay = []
        for P in range(0, LAST_DAY + 1):
            price = BASE_PRICE[a["product"]]
            row = {"P": P}
            for tag, vc in (("labour0", 0.0), ("labour10", 10.0)):
                d0 = remaining_value_detail(an, new_animal_state(an, P), P, price=price, wheat_price=25,
                                            visit_cost=vc)
                row[tag] = {"units": d0["units"], "feeds": d0["feeds"], "visits": d0["visits"],
                            "net": d0["net_value"], "profit": round(d0["net_value"] - a["cost"], 1)}
            full = remaining_value_detail(an, new_animal_state(an, P), P, price=1)
            row["full_units"] = full["units"]
            row["full_feeds"] = full["feeds"]
            row["full_net_base"] = full["units"] * price - full["feeds"] * 25 - a["cost"]
            pay.append(row)
        rows["payback"] = pay
        rows["last_P_payback_full_min_maint"] = max([r["P"] for r in pay if r["full_net_base"] > 0], default=None)
        rows["last_P_payback_best_labour0"] = max([r["P"] for r in pay if r["labour0"]["profit"] > 0], default=None)
        rows["last_P_payback_best_labour10"] = max([r["P"] for r in pay if r["labour10"]["profit"] > 0], default=None)
        animals[an] = rows
        print(an, "done", round(time.time() - t0, 1), "s", flush=True)
    R["animals"] = animals

    # ---- required_actions examples ----
    ex = {}
    ex["WHEAT_age1_after_planting_water"] = required_actions("WHEAT", dict(new_plant_state("WHEAT", 0),
                                                            consecutive_unwatered=0), 1)
    ex["WHEAT_age2"] = required_actions("WHEAT", dict(new_plant_state("WHEAT", 0), consecutive_unwatered=1), 2)
    ex["SHEEP_day5_prod_day"] = required_actions("SHEEP", dict(new_animal_state("SHEEP", 0),
                                                 pending_care_bonus=5), 5)
    ex["SHEEP_day6_bank0"] = required_actions("SHEEP", dict(new_animal_state("SHEEP", 0), yield_units=6), 6)
    ex["COW_day1"] = required_actions("COW", new_animal_state("COW", 0), 1)
    ex["COW_day6_bank5"] = required_actions("COW", dict(new_animal_state("COW", 0), pending_care_bonus=5), 6)
    R["required_actions_examples"] = ex

    if "--no-game" not in sys.argv:
        try:
            R["real_game_checks"] = real_game_checks()
        except Exception as exc:  # keep the synthetic results if the env call fails
            R["real_game_checks"] = {"error": repr(exc)}
    R["runtime_s"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "min_maintenance.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    write_markdown(R)
    print("wrote", os.path.join(OUT, "min_maintenance.json"), R["runtime_s"], "s")


def write_markdown(R):
    L = ["# Minimum maintenance for full production (engine 1.32.7, measured)", "",
         "Generated by `scripts/min_maintenance.py` from `min_maintenance.json`. Ages are days since planting /",
         "placement. Visits = tile-days with at least one action; turns = action turns on the tile (travel excluded).",
         "Reference = daily watering (crops) or daily FEED+CARE (animals), same harvest days as the minimum.",
         f"Pure model vs engine: {R['verify_pure_vs_engine']['mismatches']} mismatches in "
         f"{R['verify_pure_vs_engine']['trials']} random single-day transitions.", "",
         "## Crops (one plant, planted day 0)", "",
         "| crop | plan | units | ref visits / turns | min visits / turns | units per min visit | labour saved (visits) |",
         "|---|---|---|---|---|---|---|"]
    for crop, r in R["crops"].items():
        cd = CROPS[crop]
        for tag, key, vkey in (("unfert", "none", "unfert_min_visits"), ("fert", "fert_best", "fert_min_visits")):
            a = r[key]
            v = r[vkey]
            n_f = len(a["fert_days"])
            h = len(v["harvest"])
            ref_visits = a["ref_waterings"] + (1 if cd["ongoing"] else 0)
            ref_turns = a["ref_waterings"] + n_f + h
            min_visits, min_turns = v["visits"], v["turns"]
            plan = ("no fertiliser" if not n_f else "fertilise age " + "+".join(map(str, a["fert_days"]))) + \
                f"; water {v['water']}; harvest {v['harvest']}"
            L.append(f"| {crop} | {plan} | {a['ref_units']} | {ref_visits} / {ref_turns} | {min_visits} / {min_turns} | "
                     f"{a['ref_units'] / min_visits:.2f} | {ref_visits - min_visits} |")
    L +=["", "Minimum watering sets found by exhaustive engine enumeration (canonical one shown):", ""]
    for crop, r in R["crops"].items():
        for key in ("none", "fert_best"):
            a = r[key]
            L.append(f"- {crop} {('fert ' + str(a['fert_days'])) if a['fert_days'] else 'unfert'}: "
                     f"{a['canonical_min']} ({a['n_min_schedules']} equivalent sets); "
                     + ("harvest age " + str(a.get('harvest_age')) if not CROPS[crop]['ongoing'] else
                        "production " + str(a.get('production'))))
    L += ["", "Marginal value of each watering in the canonical minimum (strict skip, nothing else changed; "
          "`died` = plant turns to weed; `repaired` = best reachable if that day is skipped but other days may be added):", "",
          "| crop | plan | age: units lost strict (repaired) |", "|---|---|---|"]
    for crop, r in R["crops"].items():
        for key in ("none", "fert_best"):
            a = r[key]
            cells = []
            for m in a["marginal"]:
                cells.append(f"{m['age']}: {m['strict_units_lost']}{'†' if m['strict_died_age'] is not None else ''}"
                             f" ({m['repaired_units_lost']})")
            L.append(f"| {crop} | {'fert ' + str(a['fert_days']) if a['fert_days'] else 'unfert'} | {'; '.join(cells)} |")
    L += ["", "† = the skip kills the plant (two unwatered days in a row).", "",
          "Planting-day limits (season end: last action step 718 = day 29; harvest on day 29 must still be carried to the shed and sold that day):", "",
          "| crop | last planting day for the full harvest (unfert / fert) | last planting day for any harvest |", "|---|---|---|"]
    for crop, r in R["crops"].items():
        L.append(f"| {crop} | {r['last_P_full']} / {r['last_P_full_fert']} | {r['last_P_any']} |")
    L += ["", "## Animals (placed day 0, season to step 718)", "",
          "| animal | units min | ref visits / turns | min visits / turns | feeds (wheat) | units per min turn | no-care units (feed every other day) |",
          "|---|---|---|---|---|---|---|"]
    for an, r in R["animals"].items():
        d = r["dp_min"]
        ref_turns = 60 + len(d["harvests"])
        L.append(f"| {an} | {d['units']} | 30 / {ref_turns} | {d['visits']} / {d['turns']} | {len(d['feeds'])} | "
                 f"{d['units'] / d['turns']:.2f} | {r['survival_feeds_only_odd_days']['units']} |")
    L += ["", "Marginal value (units lost by skipping exactly one action in the minimum schedule):", "",
          "| animal | FEED non-production day | FEED production day | FEED first production day | CARE any useful day | skipped scheduled HARVEST |",
          "|---|---|---|---|---|---|"]
    for an, r in R["animals"].items():
        m = r["marginal"]
        pd = r["production_refresh_days_P0"]
        nonp = sorted({x.get("skip_feed_units_lost") for x in m if not x["production_day"] and "skip_feed_units_lost" in x})
        prod = sorted({x.get("skip_feed_units_lost") for x in m if x["production_day"] and x["day"] not in (pd[0], pd[-1])
                       and "skip_feed_units_lost" in x})
        first = [x.get("skip_feed_units_lost") for x in m if x["day"] == pd[0]]
        care = sorted({x.get("skip_care_units_lost") for x in m if "skip_care_units_lost" in x})
        hv = sorted({x["units_lost"] for x in r["skip_harvest"]})
        L.append(f"| {an} | {nonp} | {prod} | {first} | {care} | {hv} |")
    L += ["", "Payback by placement day P (base prices, wheat 25 per feed, animal price, labour free; `labour10` = 10 per visit-day):", "",
          "| animal | P | units | feeds | visits | profit (labour 0) | profit (labour 10) |", "|---|---|---|---|---|---|---|"]
    for an, r in R["animals"].items():
        for row in r["payback"]:
            if row["P"] % 3 == 0 or row["P"] in (r["last_P_payback_best_labour0"], r["last_P_payback_best_labour10"]):
                L.append(f"| {an} | {row['P']} | {row['full_units']} | {row['full_feeds']} | {row['labour0']['visits']} | "
                         f"{row['labour0']['profit']:.0f} | {row['labour10']['profit']:.0f} |")
        L.append(f"| {an} | last P paying back | | | | {r['last_P_payback_best_labour0']} | {r['last_P_payback_best_labour10']} |")
    rg = R.get("real_game_checks", {})
    if rg:
        L += ["", "## Real-game confirmation (kaggle_environments interpreter)", ""]
        for k, v in rg.items():
            if isinstance(v, dict):
                L.append(f"- {k}: " + ", ".join(f"{kk}={vv}" for kk, vv in v.items() if kk != "final_tile"))
            else:
                L.append(f"- {k}: {v}")
    with open(os.path.join(OUT, "min_maintenance.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    if "--md-only" in sys.argv:
        with open(os.path.join(OUT, "min_maintenance.json")) as f:
            write_markdown(json.load(f))
    else:
        main()

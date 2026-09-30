"""Smoke test of the time-based path-partition executor (user 2026-09-30): "from a DSM world, prefixed 11 days
deterministic, semantic planning and tiling by DSM, our latest executor [= the executor on the new search algorithm]
with early bring-in runs, strawberry yarn and milk price fixes."

Stack, per DSM-new world (results/fresh/semantic_h2h_20260929/study/recordings_d4q9):
- steps 0-263 (days 0-10): DSM's recorded actions (exact handover at the day-11 dawn);
- the opponent plays its recorded actions throughout, with its logged weed spawns and exact purchase credit (the
  harness's leader_weeds / leader_credit_exact, so its frozen plan stays valid);
- days 11-29, our seat: DSM's own plan and tiling for the day (what DSM planted / harvested / built / placed where that
  day and its crew size, read from DSM's continuation of the same world) executed by
  * the time-based partition (scripts/path_partition_20260930.py): mandatory / non-mandatory / slack hours per tile,
    one path per worker from the shed (mandatory <= day, + non-mandatory target, all >= day + 1), cut slack then
    non-mandatory by value, fewest tiles walked; useless jobs never listed;
  * early bring-in legs, planned before everyone else: the farmer (from hour 0) and the first hand collect
    strawberries, wool, milk (and melons due today) and drop them at the shed by bring_cap hours;
  * price fix: SELL orders put STRAWBERRY, WOOL, MILK first in the order list (the engine fills orders by index, so the
    front sells at the higher prices; sd_sell_front), everything else after; wheat kept as feed stock;
  * wheat for today's feeds / seeds for today's plantings / animals for today's placements bought at hour 0; tomorrow's
    feed wheat at hour 18 (keeping tomorrow's hire wages);
  * paths fixed at hour 0; a worker behind schedule cuts its slack, then its non-mandatory jobs, lowest value first.

usage: tpp_smoke_20260930.py EP [--tag a] [--crew dsm|demand] [--bring 2] [--bring-cap 8] [--days 11-29]"""
import argparse
import gzip
import json
import sys
import time
import traceback
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import path_partition_20260930 as PP  # noqa: E402

STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"
HARNESS = STUDY / "candidates/d9e68b115518441/harness"
GAMES = ROOT / "results/fresh/dsm4q_d9_20260930/games"
OUT = ROOT / "results/fresh/tpp_smoke_20260930"
SHED = PP.SHED
FRONT = ("STRAWBERRY", "WOOL", "MILK")
BACK = ("MELON", "EGG", "TOMATO", "CARROT", "FERTILIZER")
MOVE = {(0, -1): "NORTH", (0, 1): "SOUTH", (1, 0): "EAST", (-1, 0): "WEST"}
PREFIX = 264
OP_ORDER = {"DIG": 0, "WATER_W": 1, "HARVEST_C": 2, "BUILD": 3, "PLACE": 4, "PLANT": 5, "WATER_SEED": 6,
            "COLLECT_FERTILIZER": 7, "HARVEST": 8, "FEED": 9, "FEED+CARE": 9, "CARE": 10, "FERTILIZE": 11, "WATER": 12}


class Job(PP.Job):
    __slots__ = ("arg", "key")

    def __init__(self, tile, op, cls, hours, value, needs=None, arg=None, key=None):
        super().__init__(tile, op, cls, hours, value, needs)
        self.arg, self.key = arg, key or op


# --------------------------------------------------------------------------------------------- DSM's plan per day
def dsm_plans(ep):
    """DSM's semantic plan and tiling for each day 11-29 of world ep, from DSM's own continuation (the day cache of
    path_partition_20260930): plantings, one-time harvests, builds, placements and the crew size"""
    games = json.loads(gzip.open(PP.CACHE, "rt", encoding="utf-8").read())
    g = games[ep]
    plans = {}
    for ds, D in g["days"].items():
        day = int(ds)
        dawn, dusk = D["dawn"], D["dusk"]
        plan = dict(plant={}, harvest=set(), build={}, place={}, dig=set(),
                    units=max(len(s["pos"]) for s in D["steps"]))
        for i in range(100):
            a, b = dawn[i], dusk[i]
            tile = (i % 10, i // 10)
            if isinstance(b, dict) and b.get("kind") == "PLANT" and int(b.get("planted_day", -1)) == day:
                plan["plant"][tile] = b["crop"]
            if isinstance(b, dict) and b.get("kind") in ("COOP", "PASTURE") and not (
                    isinstance(a, dict) and a.get("kind") == b.get("kind")):
                plan["build"][tile] = b["kind"]
            if isinstance(b, dict) and b.get("animal") and int(b.get("placed_day", -1)) == day:
                plan["place"][tile] = b["animal"]
        for stp in D["steps"]:
            for pos, cmd in zip(stp["pos"], stp["cmd"]):
                if not cmd:
                    continue
                t = tuple(pos)
                a = dawn[t[1] * 10 + t[0]]
                if cmd[0] == "HARVEST" and isinstance(a, dict) and a.get("kind") == "PLANT" and \
                        a.get("crop") in ("WHEAT", "CARROT", "MELON"):
                    plan["harvest"].add(t)
                if cmd[0] == "DIG":
                    plan["dig"].add(t)
        plans[day] = plan
    return plans


# --------------------------------------------------------------------------------------------------- job model
def plan_jobs(board, plan, day, prices, CR, AN, fix=0, care_n=0, sb_fert=0, animal_slack=0, fert_use=0, stock_f=0):
    """the day's jobs on OUR board under DSM's plan (engine rules as path_partition_20260930.day_jobs, with the plan
    in place of DSM's dusk)"""
    fert_p = prices.get("FERTILIZER", 80.0)
    jobs, useless = [], Counter()
    for i in range(100):
        a = board[i]
        tile = (i % 10, i // 10)
        if a == "LOCKED":
            continue
        crop_p = plan["plant"].get(tile)
        if a is None or (isinstance(a, dict) and a.get("kind") == "WEED"):
            if crop_p:
                if isinstance(a, dict):
                    jobs.append(Job(tile, "DIG", "M", 1, 0.0))
                jobs.append(Job(tile, "PLANT", "M", 1, 0.0, needs=("seed", crop_p), arg=crop_p))
                jobs.append(Job(tile, "WATER", "M", 1, 0.0, key="WATER_SEED"))
            elif tile in plan["build"]:
                if isinstance(a, dict):
                    jobs.append(Job(tile, "DIG", "M", 1, 0.0))
                jobs.append(Job(tile, "BUILD", "M", 1, 0.0, arg=plan["build"][tile]))
                if tile in plan["place"]:
                    jobs.append(Job(tile, "PLACE", "M", 1, 0.0, needs=("item", plan["place"][tile]),
                                    arg=plan["place"][tile]))
            elif isinstance(a, dict):
                useless["dig_no_replant"] += 1
            continue
        kind = a.get("kind")
        if kind in ("COOP", "PASTURE") and not a.get("animal"):
            if tile in plan["place"]:
                jobs.append(Job(tile, "PLACE", "M", 1, 0.0, needs=("item", plan["place"][tile]), arg=plan["place"][tile]))
            continue
        if kind == "PLANT" and fix and tile in plan["build"]:
            # (smoke b, world 115518441 day 15: DSM harvested / dug the crop and built a pasture for two new sheep)
            cd = CR[a["crop"]]
            yu = int(a.get("yield_units", 0) or 0)
            if yu > 0 and (cd["ongoing"] or day - int(a["planted_day"]) >= cd["first_yield_day"]):
                jobs.append(Job(tile, "HARVEST", "M", 1, yu * prices.get(a["crop"], 0.0), key="HARVEST_C", arg=a["crop"]))
                if cd["ongoing"]:
                    jobs.append(Job(tile, "DIG", "M", 1, 0.0))
            else:
                jobs.append(Job(tile, "DIG", "M", 1, 0.0))
            jobs.append(Job(tile, "BUILD", "M", 1, 0.0, arg=plan["build"][tile]))
            if tile in plan["place"]:
                jobs.append(Job(tile, "PLACE", "M", 1, 0.0, needs=("item", plan["place"][tile]), arg=plan["place"][tile]))
            continue
        if kind == "PLANT":
            cd = CR[a["crop"]]
            age = day - int(a["planted_day"])
            yu = int(a.get("yield_units", 0) or 0)
            price = prices.get(a["crop"], 0.0)
            fert_until = int(a.get("fertilized_until_day", -1))
            if not cd["ongoing"]:
                window = (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"] and yu < cd["max_yield"]
                ripe = age >= cd["first_yield_day"] and yu > 0
                maxed = yu >= cd["max_yield"] or age >= cd["max_yield_day"]
                if ripe and (tile in plan["harvest"] or maxed):
                    if window and not a.get("watered_today"):
                        bonus = 2 if fert_until >= day else 1
                        jobs.append(Job(tile, "WATER", "N", 1, min(bonus, cd["max_yield"] - yu) * price, key="WATER_W"))
                    jobs.append(Job(tile, "HARVEST", "M", 1, yu * price, key="HARVEST_C", arg=a["crop"]))
                    if crop_p:
                        jobs.append(Job(tile, "PLANT", "M", 1, 0.0, needs=("seed", crop_p), arg=crop_p))
                        jobs.append(Job(tile, "WATER", "M", 1, 0.0, key="WATER_SEED"))
                    continue
                if crop_p and tile in plan["dig"]:           # DSM dug this crop and replanted: follow it
                    jobs += [Job(tile, "DIG", "M", 1, 0.0), Job(tile, "PLANT", "M", 1, 0.0, needs=("seed", crop_p), arg=crop_p),
                             Job(tile, "WATER", "M", 1, 0.0, key="WATER_SEED")]
                    continue
                if int(a.get("consecutive_unwatered", 0)) >= 1:
                    jobs.append(Job(tile, "WATER", "M", 1, 0.0))
                elif window:
                    bonus = 2 if fert_until >= day else 1
                    jobs.append(Job(tile, "WATER", "N", 1, min(bonus, cd["max_yield"] - yu) * price))
                else:
                    jobs.append(Job(tile, "WATER", "S", 1, 1.0))
                if fert_until < day:
                    wd = sum(1 for n in range(day, min(day + 3, PP.LAST_DAY + 1))
                             if (cd["max_yield_day"] + 1) // 2 <= n - int(a["planted_day"]) <= cd["max_yield_day"])
                    gain = min(wd, max(0, cd["max_yield"] - yu - wd)) * price
                    if gain > fert_p:
                        jobs.append(Job(tile, "FERTILIZE", "N", 1, gain - fert_p, needs=("item", "FERTILIZER")))
                continue
            nights = PP._plant_prod_nights(a, day, CR)
            tonight = bool(nights) and nights[0] == day
            if crop_p and tile in plan["dig"]:               # DSM dug this ongoing crop and replanted
                if yu > 0:
                    jobs.append(Job(tile, "HARVEST", "M", 1, yu * price, key="HARVEST_C", arg=a["crop"]))
                jobs += [Job(tile, "DIG", "M", 1, 0.0), Job(tile, "PLANT", "M", 1, 0.0, needs=("seed", crop_p), arg=crop_p),
                         Job(tile, "WATER", "M", 1, 0.0, key="WATER_SEED")]
                continue
            if yu > 0:
                add = 2 if fert_until >= day else 1
                if (tonight and yu + add > cd["max_yield"]) or (fix and (not nights or day >= PP.LAST_DAY)):
                    # full and producing tonight; (fix, 2026-09-30 smoke a: 90 strawberries decayed on the plant) no
                    # production left - the plant decays from tomorrow - or the last day
                    jobs.append(Job(tile, "HARVEST", "M", 1, yu * price, arg=a["crop"]))
                elif fix:                                     # goods to sell: non-mandatory at their value
                    jobs.append(Job(tile, "HARVEST", "N", 1, yu * price, arg=a["crop"]))
                else:
                    jobs.append(Job(tile, "HARVEST", "S", 1, 0.1 * yu * price, arg=a["crop"]))
            if not nights:
                useless["water_no_production_left"] += 1
                continue
            # (arm f, smoke e: 30 strawberry production nights lost their fertilizer bonus - fertilize jobs were cut in an
            # overloaded non-mandatory list) a strawberry producing tonight is watered and fertilized today: deadline tonight
            prio = bool(sb_fert) and tonight and price > fert_p
            if int(a.get("consecutive_unwatered", 0)) >= 1:
                jobs.append(Job(tile, "WATER", "M", 1, 0.0))
            elif tonight and (fert_until >= day or prio):
                jobs.append(Job(tile, "WATER", "M" if prio else "N", 1, price))
            else:
                jobs.append(Job(tile, "WATER", "S", 1, 1.0))
            if fert_until < day:
                k = sum(1 for n in nights if n <= day + 2)
                if k * price > fert_p:
                    jobs.append(Job(tile, "FERTILIZE", "M" if prio else "N", 1, k * price - fert_p,
                                    needs=("item", "FERTILIZER")))
            continue
        if a.get("animal"):
            prod = AN[a["animal"]]["product"]
            price = prices.get(prod, 0.0)
            nights = PP._animal_prod_nights(a, day, AN)
            tonight = bool(nights) and nights[0] == day
            bank = int(a.get("pending_care_bonus", 0) or 0)
            yu = int(a.get("yield_units", 0) or 0)
            if yu > 0:
                if (tonight and yu + 1 + bank > AN[a["animal"]]["max_held"]) or (fix and day >= PP.LAST_DAY):
                    jobs.append(Job(tile, "HARVEST", "M", 1, yu * price, arg=prod))
                elif fix and not animal_slack:
                    jobs.append(Job(tile, "HARVEST", "N", 1, yu * price, arg=prod))
                else:
                    jobs.append(Job(tile, "HARVEST", "S", 1, 0.1 * yu * price, arg=prod))
            if a.get("fertilizer_available") and day < PP.LAST_DAY:
                jobs.append(Job(tile, "COLLECT_FERTILIZER", "N", 1, fert_p))
            later = [n for n in nights if n > day] if tonight else nights
            fed = None
            if int(a.get("consecutive_unfed", 0)) >= 1:
                if nights:
                    jobs.append(Job(tile, "FEED", "M", 1, 0.0, needs=("item", "WHEAT")))
                    fed = "M"
                else:
                    useless["feed_no_production_left"] += 1
            elif tonight and bank > 0:
                jobs.append(Job(tile, "FEED", "N", 1, bank * price, needs=("item", "WHEAT")))
                fed = "N"
            if later:
                cc = "N" if care_n else "S"                   # (smoke b: care as slack -> wool 36 vs DSM 92)
                if fed:
                    jobs.append(Job(tile, "CARE", cc, 1, price))
                else:
                    jobs.append(Job(tile, "FEED+CARE", cc, 2, price, needs=("item", "WHEAT")))
    supply = sum(1 for j in jobs if j.op == "COLLECT_FERTILIZER") + (int(stock_f) if fert_use else 0)
    fz = sorted([j for j in jobs if j.op == "FERTILIZE"], key=lambda j: (j.cls != "M", -j.value))
    if fert_use and fz:
        # (arm g, smoke e: collections valued at the ~$35 sale price were cut first from day 16, the next mornings found
        # 1-7 fertilizer and 8-16 fertilize jobs a day went without) a collection is worth what the fertilizer buys: the
        # median gain of today's fertilize jobs (a strawberry production), at least the sale price
        use = sorted(j.value + fert_p for j in fz)[len(fz) // 2]
        for j in jobs:
            if j.op == "COLLECT_FERTILIZER":
                j.value = max(j.value, use)
    if len(fz) > supply:
        drop = set(fz[supply:])
        useless["fertilize_no_supply"] += len(drop)
        jobs = [j for j in jobs if j not in drop]
    return jobs, useless


# ------------------------------------------------------------------------------------------------------- executor
def dist(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def step_toward(p, q):
    if p[0] != q[0]:
        return MOVE[((1 if q[0] > p[0] else -1), 0)]
    return MOVE[(0, (1 if q[1] > p[1] else -1))]


def cmd_of(j):
    if j.op == "PLANT":
        return [["PLANT", j.arg]]
    if j.op == "PLACE":
        return [["PLACE", j.arg]]
    if j.op == "BUILD":
        return [["BUILD_COOP" if j.arg == "COOP" else "BUILD_PASTURE"]]
    if j.op == "FEED+CARE":
        return [["FEED"], ["CARE"]]
    return [[j.op]]


def valid(c, t, inv, seeds):
    """would command c change anything on tile t with this inventory (arm d, 2026-09-30: smoke c spent ~9 hours a day on
    no-op commands - fertilize with nothing in hand, harvest of an emptied tile, ...)"""
    op = c[0]
    if op == "WATER":
        return isinstance(t, dict) and t.get("kind") == "PLANT" and not t.get("watered_today")
    if op == "HARVEST":
        return isinstance(t, dict) and int(t.get("yield_units", 0) or 0) > 0
    if op == "FEED":
        return isinstance(t, dict) and bool(t.get("animal")) and not t.get("fed_today") and int(inv.get("WHEAT", 0) or 0) > 0
    if op == "CARE":
        return isinstance(t, dict) and bool(t.get("animal")) and not t.get("cared_today")
    if op == "COLLECT_FERTILIZER":
        return isinstance(t, dict) and bool(t.get("animal")) and bool(t.get("fertilizer_available"))
    if op == "FERTILIZE":
        return isinstance(t, dict) and t.get("kind") == "PLANT" and int(inv.get("FERTILIZER", 0) or 0) > 0
    if op == "PLANT":
        return t is None and int((seeds or {}).get(c[1], 0) or 0) > 0
    if op == "DIG":
        return t is not None and t != "LOCKED" and not (isinstance(t, dict) and t.get("animal"))
    if op in ("BUILD_COOP", "BUILD_PASTURE"):
        return t is None
    if op == "PLACE":
        want = "COOP" if c[1] == "GOOSE" else "PASTURE"
        return isinstance(t, dict) and t.get("kind") == want and not t.get("animal") and int(inv.get(c[1], 0) or 0) > 0
    return True


def bring_back_legs(jobs, units, cfg):
    """user rules (2026-09-28 melon rule, 2026-09-29 early harvest): melons first - water in the window, harvest, back at
    the shed by hour 8 if the melon can make it alone, else by 12 (never later: then normal harvesting); a hand takes
    several melons only if all stay on time, otherwise more hands go. Then strawberries, wool and milk the same way,
    back by front_deadline (extra hands allowed). The farmer acts from hour 0, hands from hour 1. Returns
    [(slot, [(tile, jobs)], leg hours)] and the jobs taken off the pool."""
    taken, legs = set(), []
    slot_next = [0]
    max_b = int(cfg.get("max_bring", 6))

    def pre(j):
        return [x for x in jobs if x.tile == j.tile and x.key == "WATER_W"] if j.key == "HARVEST_C" else []

    def build(items, deadline_of):
        while True:
            left = [j for j in items if j not in taken]
            if not left or slot_next[0] >= min(units, max_b):
                return
            slot = slot_next[0]
            start = 0 if slot == 0 else 1
            pos, t, leg, dl = PP.near_shed(left[0].tile), start, [], 99
            while True:
                best = None
                for j in left:
                    if j in taken or any(j is x for _, js in leg for x in js):
                        continue
                    w = 1 + len(pre(j))
                    arrive = t + dist(pos, j.tile)
                    back = arrive + w + dist(j.tile, PP.near_shed(j.tile)) + 1
                    d_ = min(dl, deadline_of(j, start))
                    if d_ is None or back > d_:
                        continue
                    key_ = (dist(pos, j.tile), -j.value)
                    if best is None or key_ < best[0]:
                        best = (key_, j, arrive + w, d_)
                if best is None:
                    break
                _, j, t, dl = best
                pos = j.tile
                leg.append((j.tile, pre(j) + [j]))
            if not leg:
                return
            for _, js in leg:
                taken.update(js)
            t += dist(pos, PP.near_shed(pos)) + 1
            legs.append((slot, leg, t - start))
            slot_next[0] += 1

    def melon_deadline(j, start):
        alone = start + dist(PP.near_shed(j.tile), j.tile) + 1 + len(pre(j)) + dist(j.tile, PP.near_shed(j.tile)) + 1
        return 8 if alone <= 8 else (12 if alone <= 12 else -1)
    mel = sorted([j for j in jobs if j.op == "HARVEST" and j.key == "HARVEST_C" and j.arg == "MELON"],
                 key=lambda j: dist(PP.near_shed(j.tile), j.tile))
    build(mel, melon_deadline)
    if cfg.get("sb_bring"):
        # (arm f, smoke e: path workers picked strawberries at hours 14-15, they sold the next day and 20 were lost in the
        # midnight dump) every strawberry harvest is a priority bring-back, back at the shed by sb_deadline
        sb = sorted([j for j in jobs if j.op == "HARVEST" and j.arg == "STRAWBERRY" and j.key != "HARVEST_C"],
                    key=lambda j: dist(PP.near_shed(j.tile), j.tile))
        build(sb, lambda j, start: int(cfg.get("sb_deadline", 20)))
    fr = sorted([j for j in jobs if j.op == "HARVEST" and j.arg in FRONT and j.key != "HARVEST_C"
                 and (j.cls == "M" or not cfg.get("animal_slack") or (cfg.get("sb_morning") and j.arg == "STRAWBERRY"))],
                key=lambda j: (-j.value, dist(PP.near_shed(j.tile), j.tile)))
    build(fr, lambda j, start: int(cfg.get("front_deadline", 10)))
    return legs, taken


class Worker:
    """one worker's day: pickups at the shed, then its stops (tile, jobs) in path order; bring-in legs end with a DROP"""

    def __init__(self, slot, T, stops, pick, bring=None):
        self.slot, self.T, self.stops, self.pick, self.bring = slot, T, stops, pick, bring
        self.queue = []                                   # the current stop's commands
        self.log = Counter()

    def remaining(self, pos):
        h = len(self.pick) + len(self.queue)
        p = pos
        for tile, js in self.stops:
            h += dist(p, tile) + sum(j.hours for j in js)
            p = tile
        return h


class TPPAgent:
    def __init__(self, plans, cfg, CR, AN):
        self.plans, self.cfg, self.CR, self.AN = plans, cfg, CR, AN
        self.diag_drop = 0
        self.day = None
        self.workers = {}
        self.diag = {}
        self.buy_left = Counter()

    def old_legs(self, jobs, units):
        """arms a-d: the farmer and the first hand, nearest first, back by bring_cap"""
        prod = [j for j in jobs if j.op == "HARVEST" and (j.arg in FRONT or (j.key == "HARVEST_C" and j.arg == "MELON"))]
        taken = set()
        legs = []
        for slot in range(min(int(self.cfg["bring"]), units)):
            start_h = 0 if slot == 0 else 1
            cap = int(self.cfg["bring_cap"]) - start_h
            pos, t_, leg = SHED[0], 0, []
            while True:
                cand = [j for j in prod if j not in taken]
                if not cand:
                    break
                j = min(cand, key=lambda j: (dist(pos, j.tile), -j.value))
                pre = [x for x in jobs if x.tile == j.tile and x.key == "WATER_W"] if j.key == "HARVEST_C" else []
                need = dist(pos, j.tile) + 1 + len(pre) + dist(j.tile, PP.near_shed(j.tile)) + 1
                if t_ + need > cap:
                    break
                t_ += dist(pos, j.tile) + 1 + len(pre)
                pos = j.tile
                leg.append((j.tile, pre + [j]))
                taken.add(j)
                taken.update(pre)
            if not leg:
                break
            t_ += dist(pos, PP.near_shed(pos)) + 1
            legs.append((slot, leg, t_))
        return legs, taken

    # -- hour 0: the day's plan
    def new_day(self, obs, day):
        me = int(obs["player"])
        farm, priv = obs["farms"][me], obs.get("private") or {}
        board = [t for row in farm["tiles"] for t in row]
        prices = {g: float(v) for g, v in (obs["market"]["prices"] or {}).items()}
        plan = self.plans.get(day) or dict(plant={}, harvest=set(), build={}, place={}, dig=set(), units=13)
        stock_f = int((priv.get("shed") or {}).get("FERTILIZER", 0) or 0)
        jobs, useless = plan_jobs(board, plan, day, prices, self.CR, self.AN, int(self.cfg.get("fix", 0)),
                                  int(self.cfg.get("care_n", 0)), int(self.cfg.get("sb_fert", 0)),
                                  int(self.cfg.get("animal_slack", 0)), int(self.cfg.get("fert_use", 0)), stock_f)
        units = int(plan["units"]) if self.cfg["crew"] == "dsm" else int(plan["units"])
        # early bring-in legs (farmer from hour 0, then the first hands from hour 1): strawberries, wool, milk and
        # today's melon harvests, nearest first, back at the shed by bring_cap
        if self.cfg.get("bb_mode"):
            legs, taken = bring_back_legs(jobs, units, self.cfg)
        else:
            legs, taken = self.old_legs(jobs, units)
        pool = [j for j in jobs if j not in taken]
        tjobs = {}
        for j in pool:
            tjobs.setdefault(j.tile, []).append(j)
        T_list = []
        for slot in range(units):
            T = 24 if slot == 0 else 23
            leg = next((l_ for l_ in legs if l_[0] == slot), None)
            T_list.append(T - (leg[2] if leg else 0))
        order = sorted(range(units), key=lambda s: -T_list[s])
        plans_ = PP.partition(tjobs, units, [T_list[s] for s in order]) if tjobs else []
        self.workers = {}
        f_left = stock_f
        for k, q in enumerate(plans_):
            slot = order[k]
            stops = []
            for t in q["seq"]:
                js = sorted([j for j in tjobs.get(t, []) if j in q["keep"]], key=lambda j: OP_ORDER.get(j.key, 12))
                if js:
                    stops.append((t, js))
            kept = [j for _, js in stops for j in js]
            n_w = sum(1 for j in kept if j.needs == ("item", "WHEAT"))
            n_fz = sum(1 for j in kept if j.op == "FERTILIZE") - (0 if self.cfg.get("fix") else
                                                                   sum(1 for j in kept if j.op == "COLLECT_FERTILIZER"))
            if self.cfg.get("fert_use"):
                # what the path needs from the shed: the deepest shortfall of (collected - applied) along its order;
                # fertilize jobs the shed cannot cover are dropped now (nobody walks to a plant with nothing in hand)
                while True:
                    bal, need = 0, 0
                    for _, js in stops:
                        for j in js:
                            bal += 1 if j.op == "COLLECT_FERTILIZER" else (-1 if j.op == "FERTILIZE" else 0)
                            need = max(need, -bal)
                    if need <= f_left:
                        break
                    fzs = [(j, t) for t, js in stops for j in js if j.op == "FERTILIZE"]
                    j0, t0 = min(fzs, key=lambda x: (x[0].cls == "M", x[0].value))
                    for t, js in stops:
                        if j0 in js:
                            js.remove(j0)
                    self.diag_drop += 1
                stops = [(t, js) for t, js in stops if js]
                kept = [j for _, js in stops for j in js]
                n_fz = need
                f_left -= need
            an = Counter(j.arg for j in kept if j.op == "PLACE")
            pick = ([["PICKUP", "WHEAT", n_w]] if n_w else []) + ([["PICKUP", "FERTILIZER", n_fz]] if n_fz > 0 else []) \
                + [["PICKUP", a_, n_] for a_, n_ in an.items()]
            leg = next((l_ for l_ in legs if l_[0] == slot), None)
            w = Worker(slot, q["T"], stops, pick, bring=leg[1] if leg else None)
            self.workers[slot] = w
        for slot, leg, _ in legs:
            if slot not in self.workers:
                self.workers[slot] = Worker(slot, 0, [], [], bring=leg)
        # purchases for the day: seeds for the plantings, wheat for the feeds, animals for the placements
        need = Counter()
        for j in jobs:
            if j.op == "PLANT":
                need[("BUY_SEED", j.arg)] += 1
            if j.op == "PLACE":
                need[("BUY_ANIMAL", j.arg)] += 1
        seeds = Counter({k: int(v) for k, v in (priv.get("seeds") or {}).items()})
        shed = Counter({k: int(v) for k, v in (priv.get("shed") or {}).items()})
        for (op, it), n in list(need.items()):
            have = seeds[it] if op == "BUY_SEED" else shed[it]
            need[(op, it)] = max(0, n - have)
        feeds = sum(1 for j in jobs if j.needs == ("item", "WHEAT"))
        need[("BUY_PRODUCT", "WHEAT")] = max(0, feeds - shed["WHEAT"])
        self.buy_left = +need
        self.diag[day] = dict(M=sum(j.hours for j in jobs if j.cls == "M"), N=sum(j.hours for j in jobs if j.cls == "N"),
                              S=sum(j.hours for j in jobs if j.cls == "S"), useless=dict(useless), units=units,
                              legs=[(s, len(l), t) for s, l, t in legs],
                              walk=sum(q["walk"] for q in plans_), cut_N=sum(j.hours for q in plans_ for j in q["cut"] if j.cls == "N"),
                              cut_S=sum(j.hours for q in plans_ for j in q["cut"] if j.cls == "S"),
                              m_over=sum(max(0, q["m_time"] - q["T"]) for q in plans_), plan=dict(
                                  plant=len(plan["plant"]), harvest=len(plan["harvest"]), place=len(plan["place"]),
                                  build=len(plan["build"])), log=Counter())

    # -- one unit's command this hour
    def unit_cmd(self, w, pos, hour, inv, day, shed=None, tiles=None, seeds=None):
        lg = self.diag[day]["log"]
        pre = bool(self.cfg.get("precheck")) and tiles is not None
        here = tiles[pos[1]][pos[0]] if tiles is not None else None

        def first_valid(queue):
            while queue:
                c = queue.pop(0)
                if not pre or valid(c, here, inv, seeds):
                    return c
                lg["skip:" + c[0]] += 1
            return None
        # bring-in leg first
        if w.bring is not None:
            if w.bring:
                tile, js = w.bring[0]
                if tuple(pos) != tile:
                    return [step_toward(pos, tile)]
                if not w.queue:
                    w.queue = [c for j in js for c in cmd_of(j)]
                c = first_valid(w.queue)
                if not w.queue:
                    w.bring.pop(0)
                if c is None:
                    return self.unit_cmd(w, pos, hour, inv, day, shed, tiles, seeds)
                lg["bring_op"] += 1
                return c
            s_ = PP.near_shed(pos)
            if tuple(pos) != s_:
                return [step_toward(pos, s_)]
            w.bring = None
            lg["bring_drop"] += 1
            return ["DROP"]
        if self.cfg.get("fix") and day >= PP.LAST_DAY:
            s_ = PP.near_shed(pos)
            if hour + dist(pos, s_) >= 21 and not w.log.get("final_drop"):
                if tuple(pos) != s_:
                    return [step_toward(pos, s_)]
                w.log["final_drop"] += 1
                w.stops, w.queue, w.pick = [], [], []
                lg["final_drop"] += 1
                return ["DROP"]
            if w.log.get("final_drop"):
                return ["PASS"]
        # shed pickups before the path
        if w.pick:
            if tuple(pos) in SHED:
                it = w.pick[0][1]
                if (shed or {}).get(it, 0) <= 0 and hour <= 1:
                    lg["wait_pickup"] += 1            # bought this hour, in the shed next hour
                    return ["PASS"]
                if pre and (shed or {}).get(it, 0) <= 0:
                    w.pick.pop(0)
                    lg["skip:PICKUP"] += 1
                    return self.unit_cmd(w, pos, hour, inv, day, shed, tiles, seeds)
                return w.pick.pop(0)
            return [step_toward(pos, PP.near_shed(pos))]
        if w.queue:
            c = first_valid(w.queue)
            if c is not None:
                return c
        # behind schedule: cut slack, then non-mandatory, lowest value first
        left = 24 - hour
        if w.remaining(pos) > left:
            cands = sorted([(j, k) for k, (_, js) in enumerate(w.stops) for j in js if j.cls != "M"],
                           key=lambda x: ({"S": 0, "N": 1}[x[0].cls], x[0].value))
            for j, k in cands:
                if w.remaining(pos) <= left:
                    break
                w.stops[k][1].remove(j)
                lg["cut_" + j.cls] += 1
            w.stops = [(t, js) for t, js in w.stops if js]
        if not w.stops:
            carried = sum(int(v or 0) for it, v in (inv or {}).items() if it in FRONT + BACK + ("WHEAT",))
            if self.cfg.get("eve_drop") and carried >= int(self.cfg.get("eve_drop_min", 3)) and hour <= 22:
                # (arm i: strawberries picked in the afternoon rode the midnight dump - sold a day late and 27 lost when
                # the shed overflowed) a worker whose path is done takes its goods home in its leftover hours
                s_ = PP.near_shed(pos)
                if tuple(pos) != s_:
                    if hour + dist(pos, s_) <= 22:
                        lg["eve_walk"] += 1
                        return [step_toward(pos, s_)]
                else:
                    lg["eve_drop"] += 1
                    return ["DROP"]
            lg["idle"] += 1
            return ["PASS"]
        tile, js = w.stops[0]
        if tuple(pos) != tile:
            return [step_toward(pos, tile)]
        w.queue = [c for j in js for c in cmd_of(j)]
        w.stops.pop(0)
        c = first_valid(w.queue)
        if c is None:                                     # nothing left to do here: on to the next stop this hour
            return self.unit_cmd(w, pos, hour, inv, day, shed, tiles, seeds)
        return c

    def market(self, obs, day, hour, n_hire):
        me = int(obs["player"])
        farm, priv = obs["farms"][me], obs.get("private") or {}
        shed = Counter({k: int(v) for k, v in (priv.get("shed") or {}).items() if v})
        orders = []
        an = sum(1 for row in farm["tiles"] for t in row if isinstance(t, dict) and t.get("animal"))
        fix = int(self.cfg.get("fix", 0))
        keep_f = int(self.cfg.get("fert_keep", 20)) if fix and day < PP.LAST_DAY else 0
        for g in FRONT + BACK:                            # price fix: strawberry, wool, milk at the front
            n = shed[g] - (keep_f if g == "FERTILIZER" else 0)
            if n > 0:
                orders.append(["SELL", g, n])
        keep_w = (an + 5 if day < PP.LAST_DAY else 0) if fix else 2 * an + 10
        if self.cfg.get("room") and hour == 23:
            # (arm d: the midnight dump of every worker's inventory overflowed the 100 shed and discarded 24 melons and
            # ~29 strawberries in smoke c) keep only what fits beside tonight's dump; tomorrow's feed is bought at hour 0
            room = 95 - sum(int(v or 0) for i in (priv.get("inventories") or []) for v in (i or {}).values())
            keep_w = max(0, min(keep_w, room))
            keep_f = max(0, min(keep_f, room - keep_w))
            orders = [o for o in orders if o[1] != "FERTILIZER"]
            if shed["FERTILIZER"] > keep_f:
                orders.append(["SELL", "FERTILIZER", shed["FERTILIZER"] - keep_f])
        if shed["WHEAT"] > keep_w:                        # (fix: one day of feed; smoke a kept two and the shed clogged)
            orders.append(["SELL", "WHEAT", shed["WHEAT"] - keep_w])
        money = float(farm.get("money", 0) or 0)
        buys = []
        if self.cfg.get("cash_first"):
            return self._market_cash_first(obs, day, hour, n_hire, farm, priv, shed, orders, an, money)
        if hour <= 12:
            for (op, it), n in sorted(self.buy_left.items(), key=lambda kv: ({"BUY_ANIMAL": 0, "BUY_SEED": 1, "BUY_PRODUCT": 2}[kv[0][0]], kv[0][1])):
                if n > 0:
                    buys.append([op, it, n])
        if hour == 18:                                    # tomorrow's feed wheat, keeping tomorrow's hire wages
            have = shed["WHEAT"] + sum(int((i or {}).get("WHEAT", 0) or 0) for i in (priv.get("inventories") or []))
            want = max(0, an - have)
            nxt = self.plans.get(day + 1)
            wages = sum(_fib(k) for k in range(int(nxt["units"]) - 1)) if nxt else 0
            wp = float(obs["market"]["prices"].get("WHEAT", 40) or 40)
            n = min(want, int(max(0.0, money - wages - 300) // (wp * 1.3)))
            if n > 0:
                buys.append(["BUY_PRODUCT", "WHEAT", n])
        hires = [["HIRE"]] * n_hire
        out = (orders[:3] + hires + orders[3:] + buys)[:10]
        for o in out:
            if o[0].startswith("BUY") and hour != 18:
                self.buy_left[(o[0], o[1])] = 0            # bought once (a failed buy is not retried)
        return out

    def _market_cash_first(self, obs, day, hour, n_hire, farm, priv, shed, orders, an, money):
        """(2026-09-30 full stack, router world 115524856: the plan's 44 plantings a day took the last dollar on days 12-13,
        no feed wheat could be bought and 11 new animals escaped; the planner's 4th quadrant was never bought) buys in the
        order feed wheat, land, seeds, animals, within the cash left after today's hires and a reserve for tomorrow's crew;
        what cannot be paid this hour waits for a later one (until hour 12); land when the plan's target exceeds what we own"""
        wp = float(obs["market"]["prices"].get("WHEAT", 40) or 40)
        plan = self.plans.get(day) or {}
        units_ = int(plan.get("units", 13) or 13)
        hired = int(farm.get("hires_today", 0) or 0)
        today_wages = sum(_fib(hired + k) for k in range(n_hire))
        reserve = sum(_fib(k) for k in range(max(0, units_ - 1))) + float(self.cfg.get("cash_reserve", 100))
        budget = money - today_wages - reserve
        buys = []
        cost = {"BUY_PRODUCT": lambda it: wp * 1.3, "BUY_SEED": lambda it: float(self.CR[it]["seed"]),
                "BUY_ANIMAL": lambda it: float(self.AN[it]["cost"])}
        rank = {"BUY_PRODUCT": 0, "BUY_SEED": 2, "BUY_ANIMAL": 3}
        items = sorted(((k, n) for k, n in self.buy_left.items() if n > 0), key=lambda kv: (rank[kv[0][0]], kv[0][1]))
        owned = len(farm.get("unlocked_quadrants") or ["NW"])
        target = int(plan.get("land_target", 0) or 0)
        land_done = self.diag.get(day, {}).get("land_ordered")
        wheat_first = [kv for kv in items if kv[0][0] == "BUY_PRODUCT"]
        rest = [kv for kv in items if kv[0][0] != "BUY_PRODUCT"]
        if hour <= 12:
            for (op, it), n in wheat_first:
                k = min(n, int(max(0.0, budget) // cost[op](it)))
                if k > 0:
                    buys.append([op, it, k])
                    budget -= k * cost[op](it)
                    self.buy_left[(op, it)] -= k
        if self.cfg.get("buy_land") and target > owned and not land_done and owned - 1 < 3:
            price = (1000, 2000, 4000)[owned - 1]
            if budget >= price:
                buys.append(["BUY_LAND"])
                budget -= price
                self.diag[day]["land_ordered"] = hour
                self.diag[day]["log"]["buy_land"] += 1
        if hour <= 12:
            for (op, it), n in rest:
                k = min(n, int(max(0.0, budget) // cost[op](it)))
                if k > 0:
                    buys.append([op, it, k])
                    budget -= k * cost[op](it)
                    self.buy_left[(op, it)] -= k
                elif n > 0:
                    self.diag[day]["log"]["buy_wait:" + op] += 1
        if hour == 18:                                    # tomorrow's feed wheat, keeping tomorrow's hire wages
            have = shed["WHEAT"] + sum(int((i or {}).get("WHEAT", 0) or 0) for i in (priv.get("inventories") or []))
            want = max(0, an - have)
            n = min(want, int(max(0.0, money - reserve - 200) // (wp * 1.3)))
            if n > 0:
                buys.append(["BUY_PRODUCT", "WHEAT", n])
        hires = [["HIRE"]] * n_hire
        out = (orders[:3] + hires + orders[3:] + buys)[:10]
        # only the buys that fit under the 10-order cap were placed: the rest go back to the pending counts (fix, first
        # cash-first runs lost the seeds cut at hour 0 behind the hires and never retried them)
        kept = {id(o) for o in out}
        for o in buys:
            if id(o) not in kept:
                if o[0] == "BUY_LAND":
                    self.diag[day].pop("land_ordered", None)
                elif hour <= 12:
                    self.buy_left[(o[0], o[1])] += int(o[2])
        return out

    def act(self, obs, t):
        day, hour = divmod(t, 24)
        me = int(obs["player"])
        farm, priv = obs["farms"][me], obs.get("private") or {}
        if day != self.day:
            self.day = day
            self.new_day(obs, day)
        pos = [tuple(farm["farmer"])] + [tuple(h) for h in (farm.get("hands") or [])]
        invs = list(priv.get("inventories") or [])
        if hour == 23:                                    # what rides the midnight dump, and the shed before it
            carry = Counter()
            for i_ in invs:
                for it, n in (i_ or {}).items():
                    carry[it] += int(n or 0)
            self.diag[day]["carry23"] = dict(carry)
            self.diag[day]["shed23"] = {k: int(v) for k, v in (priv.get("shed") or {}).items() if v}
        shed = {k: int(v) for k, v in (priv.get("shed") or {}).items()}
        cmds = []
        for i, p in enumerate(pos):
            w = self.workers.get(i)
            if w is None:
                cmds.append(["PASS"])
                continue
            try:
                cmds.append(self.unit_cmd(w, p, hour, invs[i] if i < len(invs) else {}, day, shed, farm["tiles"],
                                          priv.get("seeds") or {}))
            except Exception:
                self.diag[day]["log"]["error"] += 1
                cmds.append(["PASS"])
        units = int(self.diag[day]["units"])
        n_hire = max(0, units - len(pos)) if hour <= 1 else 0
        market = self.market(obs, day, hour, n_hire)
        return {"farmer": cmds[0], "hands": cmds[1:], "market": market}


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# ------------------------------------------------------------------------------------------------------------ run
def run(a):
    import semantic_h2h_20260929 as SH
    sys.path.insert(0, str(HARNESS))
    import tape_vs_bench as TV
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    CR, AN = PP._engine_tables()
    ep = a.ep
    rec = json.loads(gzip.decompress((STUDY / f"recordings_d4q9/{ep}.json.gz").read_bytes()))
    seat, lead = int(rec["seat"]), 1 - int(rec["seat"])
    SH._leader_credit_exact(lead, json.loads((ROOT / f"results/fresh/semantic_h2h_20260929/leader_commits/d4q9-{ep}.json")
                                             .read_text())["steps"])
    spawns = json.loads((GAMES / f"d4q9-{ep}.dsm.result.spawns.json").read_text())[lead]
    agent = TPPAgent(dsm_plans(ep), dict(crew=a.crew, bring=a.bring, bring_cap=a.bring_cap, fix=a.fix,
                                         fert_keep=a.fert_keep, care_n=a.care_n, precheck=a.precheck, room=a.room,
                                         bb_mode=a.bb_mode, max_bring=a.max_bring, front_deadline=a.front_deadline,
                                         sb_fert=a.sb_fert, animal_slack=a.animal_slack, sb_bring=a.sb_bring,
                                         sb_deadline=a.sb_deadline, fert_use=a.fert_use, sb_morning=a.sb_morning,
                                         eve_drop=a.eve_drop), CR, AN)
    tiles, lookup, frames = [], {}, []

    def tid(t):
        v = {k: t[k] for k in PP_TILE_KEYS if k in t} if isinstance(t, dict) else t
        key = json.dumps(v, sort_keys=True, separators=(",", ":"))
        if key not in lookup:
            lookup[key] = len(tiles)
            tiles.append(v)
        return lookup[key]
    om = E._process_market

    def pm(state, env, *x, **k):
        obs = state[0].observation
        farm = obs.farms[seat]
        act = state[seat].action
        frames.append(dict(t=int(obs.step), m=[int(obs.farms[seat]["money"]), int(obs.farms[lead]["money"])],
                           u=[list(farm["farmer"])] + [list(h) for h in farm["hands"]],
                           b=[tid(t) for row in farm["tiles"] for t in row],
                           sh={g: int(v) for g, v in dict(state[seat].observation.private["shed"]).items() if int(v or 0)},
                           a=deepcopy(act) if isinstance(act, dict) else None,
                           p=[int(obs.market["prices"].get(g, 0)) for g in PP.GOODS],
                           s=list(obs.town["unlocked_shops"]), q=len(farm.get("unlocked_quadrants") or [])))
        return om(state, env, *x, **k)
    E._process_market = pm
    discards = Counter()
    od = E._drop_inventories_to_shed

    def drop_count(private, capacity, *x, **k):
        # the midnight dump discards what does not fit in the shed: count ours by item and day
        if private is env_state_private[0]:
            before = Counter()
            for inv in private["inventories"]:
                for it, n in inv.items():
                    before[it] += int(n)
            shed0 = Counter({kk: int(v) for kk, v in private["shed"].items()})
            r = od(private, capacity, *x, **k)
            shed1 = Counter({kk: int(v) for kk, v in private["shed"].items()})
            for it, n in before.items():
                lost = n - (shed1[it] - shed0[it])
                if lost > 0:
                    discards[(day_now[0], it)] += lost
            return r
        return od(private, capacity, *x, **k)
    env_state_private, day_now = [None], [0]
    E._drop_inventories_to_shed = drop_count
    errors = []

    def ours(obs, t):
        env_state_private[0] = env.state[seat].observation.private if env.state else None
        day_now[0] = t // 24
        if t < PREFIX:
            return deepcopy(rec["our_actions"][t]) if rec["our_actions"][t] else {"farmer": ["PASS"], "hands": [], "market": []}
        try:
            return agent.act(obs, t)
        except Exception:
            errors.append((t, traceback.format_exc()))
            return {"farmer": ["PASS"], "hands": [], "market": []}

    def opp(obs, t):
        x = rec["opp_actions"][t] if t < len(rec["opp_actions"]) else None
        return deepcopy(x) if x else {"farmer": ["PASS"], "hands": [], "market": []}
    env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 100000}, info={"seed": rec["seed"]})
    players = [ours, opp] if seat == 0 else [opp, ours]
    t0 = time.time()
    try:
        res = TV._play(E, env, players, seat, rec["shops"], spawns, lead, lead)
    finally:
        E._process_market = om
        E._drop_inventories_to_shed = od
    final = res["final"]
    OUT.mkdir(parents=True, exist_ok=True)
    key = f"tpp{a.tag}.p{PREFIX}"
    g = dict(tiles=tiles, frames=frames, cash=final[seat], opp_cash=final[lead], margin=final[seat] - final[lead],
             daily=res["daily"], shops=rec["shops"][30], seat=seat, errors=[e[1][-600:] for e in errors[:5]],
             diag={str(d): {k: (dict(v) if isinstance(v, Counter) else v) for k, v in x.items()} for d, x in agent.diag.items()})
    with gzip.open(GAMES / f"d4q9-{ep}.{key}.game.json.gz", "wt", encoding="utf-8") as f:
        json.dump(g, f, separators=(",", ":"), default=list)
    dsm = json.loads(gzip.open(GAMES / f"d4q9-{ep}.dsm.game.json.gz", "rt", encoding="utf-8").read())
    print(f"world {ep} seat {seat}: ours {final[seat]:.0f} vs DSM's own continuation {dsm['cash']:.0f} "
          f"({final[seat] - dsm['cash']:+.0f}); opponent {final[lead]:.0f} (vs DSM game {dsm['opp_cash']:.0f}); "
          f"margin {final[seat] - final[lead]:+.0f} (DSM {dsm['margin']:+.0f}); {len(errors)} agent errors; {time.time() - t0:.0f}s")
    s = seat
    print("day | cash ours / DSM | jobs M N S | legs | walk | cut N S (plan) | on-the-fly cut N S | idle | errors")
    for d in range(11, 30):
        x = agent.diag.get(d)
        if not x:
            continue
        lg = x["log"]
        print(f" {d:2d} | {res['daily'][s][d]['money']:7.0f} / {dsm['daily'][s][d]['money']:7.0f} | {x['M']:3.0f} {x['N']:3.0f} {x['S']:3.0f} | "
              f"{x['legs']} | {x['walk']:3d} | {x['cut_N']:2.0f} {x['cut_S']:3.0f} | {lg.get('cut_N', 0):2d} {lg.get('cut_S', 0):2d} | "
              f"{lg.get('idle', 0):3d} | {lg.get('error', 0)}")
    lost = Counter()
    for (d_, it), n in discards.items():
        lost[it] += n
    print("discarded at the midnight dump (shed full), days 11-29:", dict(lost),
          "| by day:", {d_: dict((it, n) for (dd_, it), n in discards.items() if dd_ == d_) for d_ in sorted({k[0] for k in discards})})
    g["discards"] = {f"{d_}:{it}": n for (d_, it), n in discards.items()}
    if errors:
        print("first error:", errors[0][1][-1500:])


PP_TILE_KEYS = ("kind", "crop", "animal", "yield_units", "planted_day", "placed_day", "fertilized_until_day",
                "watered_today", "fed_today", "cared_today", "pending_care_bonus", "max_lifespan_step")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("--tag", default="a")
    ap.add_argument("--crew", default="dsm")
    ap.add_argument("--bring", type=int, default=2)
    ap.add_argument("--bring-cap", dest="bring_cap", type=int, default=8)
    ap.add_argument("--fix", type=int, default=1)
    ap.add_argument("--fert-keep", dest="fert_keep", type=int, default=20)
    ap.add_argument("--care-n", dest="care_n", type=int, default=1)
    ap.add_argument("--precheck", type=int, default=1)
    ap.add_argument("--room", type=int, default=1)
    ap.add_argument("--bb-mode", dest="bb_mode", type=int, default=1)
    ap.add_argument("--max-bring", dest="max_bring", type=int, default=6)
    ap.add_argument("--front-deadline", dest="front_deadline", type=int, default=10)
    ap.add_argument("--sb-fert", dest="sb_fert", type=int, default=1)
    ap.add_argument("--animal-slack", dest="animal_slack", type=int, default=1)
    ap.add_argument("--sb-bring", dest="sb_bring", type=int, default=1)
    ap.add_argument("--sb-deadline", dest="sb_deadline", type=int, default=20)
    ap.add_argument("--fert-use", dest="fert_use", type=int, default=1)
    ap.add_argument("--sb-morning", dest="sb_morning", type=int, default=1)
    ap.add_argument("--eve-drop", dest="eve_drop", type=int, default=1)
    a = ap.parse_args()
    run(a)


if __name__ == "__main__":
    main()

"""Hand plan for days 0-5 (user 2026-09-29: "manually plan the first 6 days to fix the opening issues"), in the form the
current leader plays it (DSM submission 56619023, rated 3027; digest: scripts/opening_digest_20260929.py):

  days 0-2  fixed: 2 cows / 3 sheep on pens next to the shed (44 34 43 42 24), 6 melons placed close (33 23 32 41 40 14)
            + 2 on day 1, 12 wheat (a cash crop sold on days 2-4); every morning the pens' fertilizer is carried to the
            shed by hour 1-7 and sold at once (the day's first cash); animals fed on day 0.
  days 3-5  branch on the first revealed shop (visible on day 3): a milk shop (Pizza / Ice Cream / Smoothie) -> the COW
            branch (cows on 12 / 21, one bought each of days 2-4), otherwise the STRAWBERRY branch (strawberries there).

The unit jobs are the recorded commands of one representative game per branch; the MARKET is generated here, not
replayed (a raw replay failed in 3 of 5 other worlds: a purchase a few coins short knocked out the placements after it):
hires as planned, fertilizer and planned wheat sales as the shed allows, and the animals / seeds / feed wheat the NEXT
step's commands need, most urgent first, within the actual cash. The caller owns strategy from step 144.

usage (library): make_opening() -> object with act(obs, configuration) for steps 0..143"""
from __future__ import annotations

import gzip
import json
from collections import Counter
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "data/semantic_strategy/opening_plan_dsm56619023.json.gz"
MILK_SHOPS = ("PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP")
ANIMALS = ("COW", "SHEEP", "GOOSE")
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"COW": 400, "SHEEP": 500, "GOOSE": 300}


def _units(action):
    return [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]


class OpeningPlan:
    def __init__(self, path=LIB):
        with gzip.open(path, "rt", encoding="utf-8") as h:
            lib = json.load(h)
        self.branches = lib["branches"]            # name -> [144 actions]
        self.fills = lib.get("fills") or {}        # name -> per step [[op, item, units], ...] as filled in DSM's game
        self.branch = "strawberry"
        self.history = []
        self.stats = Counter()

    def _plan(self, t):
        return self.branches[self.branch][t] if t < len(self.branches[self.branch]) else {}

    def act(self, obs, configuration=None):
        t = int(obs["step"])
        if not 0 <= t < 144:
            raise ValueError("Opening is defined only for steps 0 through 143; hand off on day 6.")
        if t == 72:                                # day 3: the first shop is visible (recorded only: the two recorded
            # schedules differ in their day 0-2 details, so a switch lands one schedule on the other's farm; one
            # schedule is played throughout and the day-6 policy chooses cows vs strawberries from the shops)
            shops = [s if isinstance(s, str) else s.get("name") for s in obs.get("town", {}).get("unlocked_shops", [])]
            self.history.append(dict(day=3, branch=self.branch, first_shop=shops[:1]))
        plan = self._plan(t)
        nxt = self._plan(t + 1) if t + 1 < 144 else {}
        me = int(obs["player"])
        farm = obs["farms"][me]
        private = obs.get("private") or {}
        shed = Counter(private.get("shed") or {})
        seeds = Counter(private.get("seeds") or {})
        carried = Counter()
        for inv in private.get("inventories") or []:
            carried.update(inv or {})
        cash = float(farm.get("money", 0))
        prices = (obs.get("market") or {}).get("prices") or {}
        # the planned unit commands of this step (their shed pickups this step come out of the shed before the market)
        cmds = _units(plan)
        for c in cmds:
            if c and c[0] == "PICKUP" and len(c) > 2:
                shed[c[1]] -= int(c[2])
        if self.fills:
            # DSM's recorded order list, positions kept (both players' orders run position by position in lockstep:
            # a sale moved behind the hires changed its price and drifted the replay); in its own world this is exact.
            # Guards in the spare slots only when the next step's pickups / plantings would come up short.
            rec = [list(o) for o in (plan.get("market") or []) if o][:10]
            bought = Counter()
            for o in rec:
                if len(o) >= 3 and o[0] in ("BUY_ANIMAL", "BUY_PRODUCT", "BUY_SEED"):
                    bought[(o[0], o[1])] += int(o[2])
            guard = []
            need_wheat = sum(int(c[2]) if len(c) > 2 else 1 for c in _units(nxt) if c and c[0] == "PICKUP" and c[1] == "WHEAT")
            short_w = need_wheat - max(0, shed.get("WHEAT", 0)) - bought[("BUY_PRODUCT", "WHEAT")]
            if short_w > 0:
                guard.append(["BUY_PRODUCT", "WHEAT", int(short_w)])
            plant = Counter(c[1] for c in _units(nxt) if c and c[0] == "PLANT")
            for crop, n in plant.items():
                short_s = n - seeds.get(crop, 0) - bought[("BUY_SEED", crop)]
                if short_s > 0:
                    guard.append(["BUY_SEED", crop, int(short_s)])
            self.stats["guards"] += len(guard)
            self.stats["steps"] += 1
            return dict(farmer=cmds[0], hands=cmds[1:], market=(rec + guard)[:10])
        orders = [list(o) for o in (plan.get("market") or []) if o and o[0] == "HIRE"]
        sells = []
        if shed.get("FERTILIZER", 0) > 0:          # the day's first cash: all fertilizer in the shed, now
            sells.append(["SELL", "FERTILIZER", int(shed["FERTILIZER"])])
            cash += shed["FERTILIZER"] * float(prices.get("FERTILIZER", 90)) * 0.9
        planned_wheat_sale = sum(int(o[2]) for o in (plan.get("market") or []) if o and o[:2] == ["SELL", "WHEAT"])
        need_wheat = sum(int(c[2]) if len(c) > 2 else 1 for c in _units(nxt) if c and c[0] == "PICKUP" and c[1] == "WHEAT")
        if planned_wheat_sale:
            k = min(planned_wheat_sale, max(0, shed.get("WHEAT", 0) - need_wheat))
            if k > 0:
                sells.append(["SELL", "WHEAT", int(k)])
                cash += k * float(prices.get("WHEAT", 25)) * 0.9
        # needs of the next step, most urgent first: animals picked up, feed wheat picked up, seeds planted
        buys = []
        avail = Counter({k: max(0, v) for k, v in shed.items()})
        want = Counter()
        for c in _units(nxt):                      # each pickup reserves shed stock; only the rest is bought
            if c and c[0] == "PICKUP" and len(c) > 2 and c[1] in ANIMALS:
                take = min(avail[c[1]], int(c[2]))
                avail[c[1]] -= take
                want[c[1]] += int(c[2]) - take
        for sp in ANIMALS:
            if want[sp] > 0:
                buys.append(["BUY_ANIMAL", sp, int(want[sp])])
        wheat_miss = need_wheat - max(0, shed.get("WHEAT", 0))
        if wheat_miss > 0:
            buys.append(["BUY_PRODUCT", "WHEAT", int(wheat_miss)])
        plant = Counter(c[1] for c in _units(nxt) if c and c[0] == "PLANT")
        plant.update(c[1] for c in cmds if c and c[0] == "PLANT")
        for crop, n in plant.items():
            miss = n - seeds.get(crop, 0)
            if miss > 0:
                buys.append(["BUY_SEED", crop, int(miss)])
        out = (orders + sells + buys)[:10]
        self.stats["steps"] += 1
        return dict(farmer=cmds[0], hands=cmds[1:], market=out)

    __call__ = act


def make_opening():
    return OpeningPlan()

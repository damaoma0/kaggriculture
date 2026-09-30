"""Validate scripts/fragments/sem_maintenance.py against the official engine (1.32.7).

Every transition runs through the engine's own functions (_apply_unit_action, _decay_plants,
_daily_refresh_plants/_animals) on a 10x10 all-unlocked farm; the policy under test sees only the
engine tile dicts through maintenance_jobs(obs, 0, ...).
  A. model cross-check vs scripts/min_maintenance.py (random states)
  B. single tiles: every crop x planting day x {unfert, fert-free, auto}, every animal x placement day:
     JOBS (do exactly the job list at hour 8) vs MAX (daily water/fert/feed/care, harvest daily or at
     the crop's max age). Units, visit-days, turns, inputs.
  C. small mixed farm (13 assets incl. late / never-productive ones), same comparison
  D. 20 skip spot-checks: skip one job on one day, then keep following the jobs: realised loss vs value
  E. end of life: last maintenance day vs brute-force last useful day; abandonment log verdicts
  F. timing
Writes results/fresh/sem_maintenance/validate.json and prints a summary.
"""
import json
import os
import random
import sys
import time
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "fragments"))
import min_maintenance as MM  # noqa: E402
import sem_maintenance as SM  # noqa: E402

OUT = os.path.join(ROOT, "results", "fresh", "sem_maintenance")
ACT_HOUR = 8
PRICES = dict(SM.SM_BASE_PRICE)
MAINT = ("WATER", "FEED", "CARE", "FERTILIZE")


class Farm:
    def __init__(self, E):
        self.E = E
        self.farm = E._new_farm(10, 0)
        for y in range(10):
            for x in range(10):
                self.farm["tiles"][y][x] = None
        self.priv = {"shed": {}, "seeds": {c: 999 for c in E.CROPS},
                     "inventories": [{"WHEAT": 10 ** 6, "FERTILIZER": 10 ** 6}]}
        self.got = Counter()
        self.used = Counter()
        self.visits = set()
        self.mvisits = set()
        self.turns = Counter()
        self.noop = 0
        self.last_maint_day = {}

    def act(self, x, y, op, day, count=True):
        self.farm["farmer"] = [x, y]
        inv = self.priv["inventories"][0]
        before = dict(inv)
        t0 = self.farm["tiles"][y][x]
        t0 = dict(t0) if isinstance(t0, dict) else t0
        self.E._apply_unit_action(self.farm, self.priv, 0, [op], 10, day, 24)
        t1 = self.farm["tiles"][y][x]
        changed = t0 != t1
        for k in set(before) | set(inv):
            d = inv.get(k, 0) - before.get(k, 0)
            if d > 0:
                self.got[k] += d
                changed = True
            elif d < 0:
                self.used[k] -= d
                changed = True
        if count:
            if not changed:
                self.noop += 1
            self.visits.add((x, y, day))
            self.turns[op] += 1
            if op in MAINT:
                self.mvisits.add((x, y, day))
                self.last_maint_day[(x, y)] = day

    def end_step(self, step):
        self.E._decay_plants(self.farm, step)
        if step % 24 == 23:
            self.E._daily_refresh_plants(self.farm, step // 24, 24)
            self.E._daily_refresh_animals(self.farm, step // 24)

    def obs(self, step):
        return {"step": step, "farms": [self.farm], "market": {"prices": PRICES}}


def econ(F, prices=PRICES):
    v = 0.0
    for k, n in F.got.items():
        v += n * prices[k]
    v -= F.used.get("WHEAT", 0) * prices["WHEAT"] + F.used.get("FERTILIZER", 0) * prices["FERTILIZER"]
    return v


def max_actions(F, day):
    """Daily maximum maintenance: every live tile, every action."""
    acts = []
    for y, row in enumerate(F.farm["tiles"]):
        for x, t in enumerate(row):
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                cd = SM.SM_CROPS[t["crop"]]
                age = day - t["planted_day"]
                if F.max_fert:
                    acts.append((x, y, "FERTILIZE"))
                acts.append((x, y, "WATER"))
                if age >= cd["first_yield_day"] and (cd["ongoing"] or age >= cd["max_yield_day"] or day == 29):
                    acts.append((x, y, "HARVEST"))
            elif "animal" in t:
                acts += [(x, y, "FEED"), (x, y, "CARE"), (x, y, "HARVEST")]
                if F.collect:
                    acts.append((x, y, "COLLECT_FERTILIZER"))
    return acts


def run(E, setup, policy, fert="auto", skip=None, cutoff=None, collect=True, prices=PRICES, log=None,
        record=None):
    """setup: list of (day, x, y, kind). policy 'jobs' | 'max'. skip = (day, (x, y), cmd).
    cutoff = day from which only HARVEST / COLLECT jobs are executed."""
    F = Farm(E)
    F.max_fert = fert is True
    F.collect = collect
    by_day = {}
    for d, x, y, k in setup:
        by_day.setdefault(d, []).append((x, y, k))
    timings = []
    for step in range(0, SM.SM_LAST_STEP + 1):
        day, hour = divmod(step, 24)
        if hour == 0:
            for x, y, k in by_day.get(day, []):
                if k in SM.SM_CROPS:
                    F.farm["farmer"] = [x, y]
                    E._apply_unit_action(F.farm, F.priv, 0, ["PLANT", k], 10, day, 24)
                else:
                    F.farm["tiles"][y][x] = E._new_animal(k, day)
        if hour == ACT_HOUR:
            if policy == "max":
                for x, y, op in max_actions(F, day):
                    F.act(x, y, op, day)
            else:
                t0 = time.perf_counter()
                jobs = SM.maintenance_jobs(F.obs(step), 0, prices=prices, fertilize=fert, log=log, collect=collect)
                timings.append(time.perf_counter() - t0)
                if not collect:
                    jobs = [j for j in jobs if j["cmd"] != "COLLECT_FERTILIZER"]
                if record is not None:
                    record[day] = jobs
                for j in sorted(jobs, key=lambda j: (j["tile"], j["order"])):
                    if skip and skip[0] == day and skip[1] == j["tile"] and skip[2] == j["cmd"]:
                        continue
                    if cutoff is not None and day >= cutoff and j["cmd"] not in ("HARVEST", "COLLECT_FERTILIZER"):
                        continue
                    F.act(j["tile"][0], j["tile"][1], j["cmd"], day)
        F.end_step(step)
    return {"units": {k: v for k, v in F.got.items()}, "used": dict(F.used), "visits": len(F.visits),
            "maint_visits": len(F.mvisits), "turns": dict(F.turns), "n_turns": sum(F.turns.values()),
            "econ": round(econ(F, dict(prices, FERTILIZER=0) if fert is True else prices), 1), "noop": F.noop, "last_maint_day": F.last_maint_day,
            "timings": timings}


def products(u):
    return {k: v for k, v in u.items() if k != "FERTILIZER"}


# ------------------------------------------------------------------ A
def part_a(n=3000, seed=11):
    rng = random.Random(seed)
    bad, cnt = [], 0
    for _ in range(n):
        if rng.random() < 0.55:
            crop = rng.choice(list(MM.CROPS))
            cd = MM.CROPS[crop]
            P = rng.randint(0, 25)
            day = P + rng.randint(0, 14)
            if day > 29:
                continue
            t = MM.new_plant_state(crop, P)
            t["consecutive_unwatered"] = rng.choice([0, 1])
            t["yield_units"] = rng.randint(0 if cd["ongoing"] else 1, cd["max_yield"])
            if cd["ongoing"] and day - P < cd["first_yield_day"]:
                t["yield_units"] = 0
            t["fertilized_until_day"] = rng.choice([-1, day - 1, day, day + 1])
            fert = rng.random() < 0.5
            ra = MM.required_actions(crop, t, day, hour=0, fertilize=fert)
            rv = MM.remaining_value(crop, t, day, price=1, hour=0, fertilize=fert)[0]
            p = SM.sm_tile_plan(crop, t, day, 0, price=1, input_price=0, fert_ok=fert)
        else:
            an = rng.choice(list(MM.ANIMALS))
            a = MM.ANIMALS[an]
            P = rng.randint(0, 27)
            day = P + rng.randint(0, 12)
            if day > 29:
                continue
            t = MM.new_animal_state(an, P)
            t["consecutive_unfed"] = rng.choice([0, 1])
            t["pending_care_bonus"] = rng.randint(0, 6)
            t["yield_units"] = rng.randint(0, a["max_held"])
            ra = MM.required_actions(an, t, day, hour=0)
            rv = MM.remaining_value(an, t, day, price=1, hour=0)[0]
            p = SM.sm_tile_plan(an, t, day, 0, price=1, input_price=0)
        cnt += 1
        mine = {k: (p["repairs"][k][1] if k in p["repairs"] else v) for k, v in p["units_lost"].items()}
        mine = {k: v for k, v in mine.items() if v}
        theirs = {k: v for k, v in ra.items() if v and k != "COLLECT_FERTILIZER"}
        if mine != theirs or p["units"] != rv:
            bad.append({"state": t, "day": day, "mine": mine, "theirs": theirs})
    return {"cases": cnt, "disagreements": len(bad), "examples": bad[:3]}


# ------------------------------------------------------------------ B
def part_b(E):
    rows = []
    for crop in SM.SM_CROPS:
        for P in (0, 2, 5, 9, 13, 16, 19, 22, 25, 27):
            for mode in ("unfert", "fert", "auto"):
                fert = {"unfert": False, "fert": True, "auto": "auto"}[mode]
                setup = [(P, 2, 2, crop)]
                j = run(E, setup, "jobs", fert=fert)
                m = run(E, setup, "max", fert=(fert is True))
                rows.append({"asset": crop, "P": P, "mode": mode,
                             "units_jobs": products(j["units"]).get(crop, 0),
                             "units_max": products(m["units"]).get(crop, 0),
                             "visits_jobs": j["maint_visits"], "visits_max": m["maint_visits"],
                             "turns_jobs": j["n_turns"], "turns_max": m["n_turns"],
                             "fert_jobs": j["used"].get("FERTILIZER", 0), "fert_max": m["used"].get("FERTILIZER", 0),
                             "econ_jobs": j["econ"], "econ_max": m["econ"], "noop": j["noop"]})
    for an, a in SM.SM_ANIMALS.items():
        for P in (0, 3, 6, 10, 14, 18, 21, 23, 25, 27):
            for collect in (False, True):
                setup = [(P, 2, 2, an)]
                j = run(E, setup, "jobs", collect=collect)
                m = run(E, setup, "max", collect=collect)
                rows.append({"asset": an, "P": P, "mode": "collect" if collect else "plain",
                             "units_jobs": j["units"].get(a["product"], 0),
                             "units_max": m["units"].get(a["product"], 0),
                             "fert_collected_jobs": j["units"].get("FERTILIZER", 0),
                             "fert_collected_max": m["units"].get("FERTILIZER", 0),
                             "visits_jobs": j["maint_visits"], "visits_max": m["maint_visits"],
                             "all_visits_jobs": j["visits"], "all_visits_max": m["visits"],
                             "turns_jobs": j["n_turns"], "turns_max": m["n_turns"],
                             "wheat_jobs": j["used"].get("WHEAT", 0), "wheat_max": m["used"].get("WHEAT", 0),
                             "econ_jobs": j["econ"], "econ_max": m["econ"], "noop": j["noop"]})
    return rows


# ------------------------------------------------------------------ C
SMALL_FARM = [
    (0, 0, 0, "STRAWBERRY"), (0, 1, 0, "STRAWBERRY"), (2, 2, 0, "TOMATO"), (3, 3, 0, "MELON"),
    (1, 0, 1, "WHEAT"), (6, 0, 1, "WHEAT"), (11, 0, 1, "CARROT"), (14, 1, 1, "STRAWBERRY"),
    (2, 0, 2, "SHEEP"), (5, 1, 2, "COW"), (8, 2, 2, "GOOSE"), (18, 3, 2, "SHEEP"),
    (20, 0, 3, "STRAWBERRY"), (24, 1, 3, "MELON"), (26, 2, 3, "WHEAT"), (25, 3, 3, "COW"),
]


def part_c(E):
    out = {}
    for mode, fert in (("unfert", False), ("fert", True), ("auto", "auto")):
        j = run(E, SMALL_FARM, "jobs", fert=fert, collect=False)
        m = run(E, SMALL_FARM, "max", fert=(fert is True), collect=False)
        out[mode] = {"units_jobs": products(j["units"]), "units_max": products(m["units"]),
                     "visits_jobs": j["maint_visits"], "visits_max": m["maint_visits"],
                     "all_visits_jobs": j["visits"], "all_visits_max": m["visits"],
                     "turns_jobs": j["turns"], "turns_max": m["turns"],
                     "used_jobs": j["used"], "used_max": m["used"], "econ_jobs": j["econ"], "econ_max": m["econ"],
                     "noop": j["noop"], "max_call_ms": round(1000 * max(j["timings"]), 2)}
    return out


# ------------------------------------------------------------------ D
def part_d(E, n=20, seed=5):
    rng = random.Random(seed)
    cases = []
    tries = 0
    while len(cases) < n and tries < 400:
        tries += 1
        r = rng.random()
        if r < 0.3:
            setup, fert = SMALL_FARM, rng.choice([False, True, "auto"])
        else:
            k = rng.choice(list(SM.SM_CROPS) + list(SM.SM_ANIMALS))
            setup, fert = [(rng.randint(0, 22), 2, 2, k)], rng.choice([False, True, "auto"])
        rec = {}
        base = run(E, setup, "jobs", fert=fert, collect=False, record=rec)
        days = [d for d, js in rec.items() if js]
        if not days:
            continue
        d = rng.choice(days)
        j = rng.choice(rec[d])
        sk = run(E, setup, "jobs", fert=fert, collect=False, skip=(d, j["tile"], j["cmd"]))
        loss = round(base["econ"] - sk["econ"], 1)
        cases.append({"setup": "small_farm" if setup is SMALL_FARM else setup[0][3] + "@" + str(setup[0][0]),
                      "fert": fert, "day": d, "tile": j["tile"], "cmd": j["cmd"], "kind": j["kind"],
                      "reason": j["reason"], "value": j["value"], "realised_loss": loss, "repair": j.get("repair"),
                      "match": abs(loss - j["value"]) <= 0.05 * j["price"] + 0.01})
    return cases


# ------------------------------------------------------------------ E
def part_e(E):
    rows = []
    kinds = [("SHEEP", P) for P in (0, 5, 12, 18, 22, 24)] + [("COW", P) for P in (0, 7, 15, 20, 23)] + \
            [("GOOSE", P) for P in (0, 10, 20, 24, 26)] + [("STRAWBERRY", P) for P in (0, 8, 14, 18, 20)] + \
            [("TOMATO", P) for P in (4, 15, 20, 22)] + [("MELON", P) for P in (10, 18, 20)] + \
            [("WHEAT", P) for P in (20, 26, 28)]
    for k, P in kinds:
        setup = [(P, 2, 2, k)]
        log = []
        full = run(E, setup, "jobs", fert=False, collect=False, log=log)
        last_job = full["last_maint_day"].get((2, 2))
        units_full = sum(products(full["units"]).values())
        # brute force: smallest cutoff day c with the same units
        c_min = None
        for c in range(P, 31):
            r = run(E, setup, "jobs", fert=False, collect=False, cutoff=c)
            if sum(products(r["units"]).values()) == units_full:
                c_min = c
                break
        rows.append({"asset": k, "P": P, "units": units_full, "last_maint_job_day": last_job,
                     "last_useful_day_bruteforce": (None if c_min is None or c_min == P and last_job is None
                                                    else c_min - 1),
                     "stops_right": (last_job is None and (c_min is None or c_min <= P)) or last_job == c_min - 1,
                     "log": [{kk: e[kk] for kk in ("day", "verdict", "reason", "productions_so_far", "forfeited_units")}
                             for e in log]})
    # an 'error' case: eggs cheap, wheat dear -> feeding a young goose does not pay
    log = []
    prices = dict(PRICES, EGG=20, WHEAT=60)
    r = run(E, [(10, 2, 2, "GOOSE")], "jobs", collect=False, prices=prices, log=log)
    rows.append({"asset": "GOOSE (EGG 20, WHEAT 60)", "P": 10, "units": sum(products(r["units"]).values()),
                 "wheat": r["used"].get("WHEAT", 0), "log": log})
    return rows


# ------------------------------------------------------------------ F
def part_f():
    import copy
    E = MM.load_engine()
    # a full farm: 25 NW + 20 more tiles, mixed ages, animals
    rng = random.Random(3)
    farm = E._new_farm(10, 0)
    kinds = list(SM.SM_CROPS) + list(SM.SM_ANIMALS)
    for y in range(10):
        for x in range(10):
            if (x, y) in SM.SM_SHED_ACCESS:
                continue
            k = rng.choice(kinds)
            P = rng.randint(0, 14)
            farm["tiles"][y][x] = E._new_plant(k, P, 24) if k in SM.SM_CROPS else E._new_animal(k, P)
    out = {}
    for day in (14, 15, 16):
        obs = {"step": day * 24, "farms": [farm], "market": {"prices": PRICES}}
        SM._SM_SOLVERS.clear()
        SM._SM_PLAN_CACHE.clear()
        t0 = time.perf_counter()
        jobs = SM.maintenance_jobs(obs, 0)
        cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        SM._SM_PLAN_CACHE.clear()
        SM.maintenance_jobs(obs, 0)
        warm_memo = time.perf_counter() - t0
        t0 = time.perf_counter()
        for _ in range(10):
            SM.maintenance_jobs(obs, 0)
        warm = (time.perf_counter() - t0) / 10
        out[day] = {"tiles": 96, "jobs": len(jobs), "cold_ms": round(cold * 1000, 1),
                    "warm_solver_ms": round(warm_memo * 1000, 2), "warm_cached_ms": round(warm * 1000, 2)}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    E = MM.load_engine()
    R = {}
    t = time.time()
    R["A_crosscheck"] = part_a()
    print("A", R["A_crosscheck"]["cases"], "cases,", R["A_crosscheck"]["disagreements"], "disagreements", flush=True)
    R["B_single"] = part_b(E)
    bad = [r for r in R["B_single"] if r["units_jobs"] != r["units_max"] and r["mode"] != "auto"]
    print("B", len(R["B_single"]), "runs; unit shortfalls vs max (non-auto):", len(bad), round(time.time() - t), "s", flush=True)
    R["C_farm"] = part_c(E)
    print("C", json.dumps({k: (v["units_jobs"] == v["units_max"], v["visits_jobs"], v["visits_max"]) for k, v in R["C_farm"].items()}), flush=True)
    R["D_skip"] = part_d(E)
    print("D", sum(c["match"] for c in R["D_skip"]), "/", len(R["D_skip"]), "match", flush=True)
    R["E_eol"] = part_e(E)
    print("E", sum(1 for r in R["E_eol"] if r.get("stops_right")), "/", sum(1 for r in R["E_eol"] if "stops_right" in r), "stop right", flush=True)
    R["F_timing"] = part_f()
    print("F", R["F_timing"], flush=True)
    with open(os.path.join(OUT, "validate.json"), "w") as f:
        json.dump(R, f, indent=1, default=str)
    print("wrote", os.path.join(OUT, "validate.json"), round(time.time() - t), "s")


if __name__ == "__main__":
    main()

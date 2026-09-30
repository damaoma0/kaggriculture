"""Time-based path partition for the post-day-11 solver (user design 2026-09-30), checked offline on DSM's own farms.

User design: every tile's work for the day is split into MANDATORY, NON-MANDATORY and SLACK hours (1 op = 1 hour, 1 tile
walked = 1 hour). Each ordinary worker gets one path of adjacent tiles from the shed such that
    mandatory + walking <= day length (hard), mandatory + non-mandatory + walking <= day length (target),
    everything including slack >= day length + 1 (never idle);
over budget, cut by priority (slack, then non-mandatory) and then by value (lowest first). Early-morning bring-backers
plan their first leg before everyone else; their path budget loses the return trip and the walk from the shed to the
second leg's start. Objective under the constraints (user: "could be total tiles walked"): fewest tiles walked.
Jobs that change nothing within the season are not jobs at all (user: "absolutely useless jobs ... shouldn't even
pollute the slack list"): e.g. care without a feed that day, water on a crop harvested today / with no production
left, harvests of crops still growing (loses yield), digging weeds nobody replants, anything paying after day 29.

Engine facts used (kaggriculture.py 1.32.7): units start the day on the four shed-access tiles (4,4) (5,4) (4,5) (5,5)
(the farmer at hour 0, hires act from the hour after the hire); PICKUP only there, one item type per action, no
inventory cap; any tile is walkable; FEED needs wheat in hand; a harvested one-time crop leaves the tile empty
(replant = HARVEST, PLANT, WATER on one visit); a weed needs DIG before PLANT; a new plant starts one dry day down.

usage: path_partition_20260930.py cache [--workers 2]       replay DSM's 43 games -> dawn / dusk / units per day
       path_partition_20260930.py run [--days 11-28] [--detail EP:DAY]"""
import argparse
import gzip
import json
import math
import statistics as st
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"
CASES = ROOT / "results/fresh/dsm4q_d9_20260930/cases.json"
CACHE = ROOT / "results/fresh/path_partition_20260930/dsm_days.json.gz"
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = ("NORTH", "SOUTH", "EAST", "WEST")
LAST_DAY = 29


# ----------------------------------------------------------------------------------------------------------- cache
def _flat(tiles):
    return [json.loads(json.dumps(t)) for row in tiles for t in row]


def _replay(case):
    sys.path.insert(0, str(ROOT / "scripts"))
    import upkeep_engine as UE
    rec = json.loads(gzip.decompress((STUDY / case["file"]).read_bytes()))
    seat = int(rec["seat"])
    w = UE.World(rec["seed"], rec["shops"][30])
    E = w.E
    dusk = {}
    om = E._process_market

    def pm(state, env, *a, **k):
        t = int(state[0].observation.step)
        if t % 24 == 23 and t // 24 >= 11:
            dusk[t // 24] = _flat(state[0].observation.farms[seat]["tiles"])
        return om(state, env, *a, **k)
    E._process_market = pm
    days = {}
    try:
        while w.t < 720:
            t = w.t
            d = t // 24
            if d >= 11:
                if t % 24 == 0:
                    days[d] = dict(dawn=_flat(w.farms[seat]["tiles"]), steps=[],
                                   prices={g: float(w.market["prices"].get(g, 0)) for g in GOODS},
                                   shed=dict(w.private(seat)["shed"]))
                f = w.farms[seat]
                acts = [None, None]
                acts[seat] = UE.tape_action(rec["our_actions"], t)
                acts[1 - seat] = UE.tape_action(rec["opp_actions"], t)
                a = acts[seat] or {}
                days[d]["steps"].append(dict(pos=[list(f["farmer"])] + [list(h) for h in f["hands"]],
                                             cmd=[a.get("farmer")] + list(a.get("hands") or []),
                                             market=a.get("market") or []))
            else:
                acts = [UE.tape_action(rec["our_actions"] if s == seat else rec["opp_actions"], t) for s in range(2)]
            w.step(acts)
    finally:
        E._process_market = om
    for d in days:
        days[d]["dusk"] = dusk.get(d)
    return case["episode"], dict(money=float(w.farms[seat]["money"]), reward=float(rec["rewards"][seat]), days=days)


def cache(a):
    cases = json.loads(CASES.read_text("utf-8"))["cases"]
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(_replay, cases))
    ok = {ep: g for ep, g in rows if abs(g["money"] - g["reward"]) < 1.0}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(CACHE, "wt", encoding="utf-8") as f:
        json.dump(ok, f, separators=(",", ":"))
    print(f"{len(rows)} DSM games replayed, {len(ok)} reproduce the recorded cash -> {CACHE}")


# ------------------------------------------------------------------------------------------------------ job model
def _engine_tables():
    sys.path.insert(0, str(ROOT / "scripts"))
    import upkeep_engine as UE
    E = UE.engine()
    return E.CROPS, E.ANIMALS


class Job:
    __slots__ = ("tile", "op", "cls", "hours", "value", "needs")

    def __init__(self, tile, op, cls, hours, value, needs=None):
        self.tile, self.op, self.cls, self.hours, self.value, self.needs = tile, op, cls, hours, value, needs

    def __repr__(self):
        return f"{self.op}@{self.tile}:{self.cls}"


def _animal_prod_nights(t, day, AN):
    """production nights n >= day (the refresh at the end of day n) up to the last useful night"""
    sp = AN[t["animal"]]
    out = []
    for n in range(day, LAST_DAY):                         # a unit produced on night n sells on day n + 1 <= 29
        dsf = n + 1 - int(t["placed_day"]) - sp["first_yield_day"]
        if dsf >= 0 and dsf % sp["interval"] == 0:
            out.append(n)
    return out


def _plant_prod_nights(t, day, CR):
    cd = CR[t["crop"]]
    out = []
    for n in range(day, LAST_DAY):
        dsf = n + 1 - int(t["planted_day"]) - cd["first_yield_day"]
        if dsf >= 0 and dsf % cd["interval"] == 0 and dsf // cd["interval"] + 1 <= cd["max_yield"]:
            out.append(n)
    return out


def day_jobs(dawn, dusk, day, prices, CR, AN, shed=None):
    """per-tile jobs for one day. The day's PLAN (which one-time crops are harvested, which tiles planted) is DSM's own
    decision that day (a routing check, not a plan check); everything else follows the engine state and rules."""
    fert_p = prices.get("FERTILIZER", 80.0)
    jobs = []
    useless = Counter()
    for i in range(100):
        a, b = dawn[i], dusk[i]
        tile = (i % 10, i // 10)
        planted = isinstance(b, dict) and b.get("kind") == "PLANT" and int(b.get("planted_day", -1)) == day
        if a == "LOCKED":
            continue
        if a is None or (isinstance(a, dict) and a.get("kind") == "WEED"):
            if planted:
                if isinstance(a, dict):
                    jobs.append(Job(tile, "DIG", "M", 1, 0.0))
                jobs.append(Job(tile, "PLANT", "M", 1, 0.0, needs=("seed", b["crop"])))
                jobs.append(Job(tile, "WATER", "M", 1, 0.0))
            elif isinstance(a, dict):
                useless["dig_no_replant"] += 1
            continue
        if a.get("kind") == "PLANT":
            cd = CR[a["crop"]]
            age = day - int(a["planted_day"])
            yu = int(a.get("yield_units", 0) or 0)
            price = prices.get(a["crop"], 0.0)
            same = isinstance(b, dict) and b.get("kind") == "PLANT" and b.get("crop") == a["crop"] \
                and b.get("planted_day") == a["planted_day"]
            if not cd["ongoing"]:
                window = (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"] and yu < cd["max_yield"]
                if not same:                                  # harvested today (DSM's plan)
                    if window and not a.get("watered_today"):
                        bonus = 2 if int(a.get("fertilized_until_day", -1)) >= day else 1
                        jobs.append(Job(tile, "WATER", "N", 1, min(bonus, cd["max_yield"] - yu) * price))
                    jobs.append(Job(tile, "HARVEST", "M", 1, yu * price))
                    if planted:
                        jobs.append(Job(tile, "PLANT", "M", 1, 0.0, needs=("seed", b["crop"])))
                        jobs.append(Job(tile, "WATER", "M", 1, 0.0))
                    continue
                if int(a.get("consecutive_unwatered", 0)) >= 1:
                    jobs.append(Job(tile, "WATER", "M", 1, 0.0))
                elif window:
                    bonus = 2 if int(a.get("fertilized_until_day", -1)) >= day else 1
                    jobs.append(Job(tile, "WATER", "N", 1, min(bonus, cd["max_yield"] - yu) * price))
                else:
                    jobs.append(Job(tile, "WATER", "S", 1, 1.0))    # dry-counter reset only: moves tomorrow's water
                if int(a.get("fertilized_until_day", -1)) < day:
                    wd = sum(1 for n in range(day, min(day + 3, LAST_DAY + 1))
                             if (cd["max_yield_day"] + 1) // 2 <= n - int(a["planted_day"]) <= cd["max_yield_day"])
                    gain = min(wd, max(0, cd["max_yield"] - yu - wd)) * price   # +1 extra a watered window day
                    if gain > fert_p:
                        jobs.append(Job(tile, "FERTILIZE", "N", 1, gain - fert_p, needs=("item", "FERTILIZER")))
                    else:
                        useless["fertilize_below_fert_price"] += 1
                continue
            # ongoing crop (strawberry / tomato)
            nights = _plant_prod_nights(a, day, CR)
            tonight = bool(nights) and nights[0] == day
            if yu > 0:
                add = 2 if (int(a.get("fertilized_until_day", -1)) >= day) else 1
                if tonight and yu + add > cd["max_yield"]:
                    jobs.append(Job(tile, "HARVEST", "M", 1, yu * price))   # full and producing tonight
                else:
                    jobs.append(Job(tile, "HARVEST", "S", 1, 0.1 * yu * price))
            if not nights and yu == 0:
                useless["water_no_production_left"] += 1
                continue
            if int(a.get("consecutive_unwatered", 0)) >= 1 and nights:
                jobs.append(Job(tile, "WATER", "M", 1, 0.0))
            elif tonight and int(a.get("fertilized_until_day", -1)) >= day:
                jobs.append(Job(tile, "WATER", "N", 1, price))
            elif nights:
                jobs.append(Job(tile, "WATER", "S", 1, 1.0))
            if nights and int(a.get("fertilized_until_day", -1)) < day:
                k = sum(1 for n in nights if n <= day + 2)
                if k * price > fert_p:
                    jobs.append(Job(tile, "FERTILIZE", "N", 1, k * price - fert_p, needs=("item", "FERTILIZER")))
                else:
                    useless["fertilize_below_fert_price"] += 1
            continue
        if a.get("animal"):
            if not (isinstance(b, dict) and b.get("animal") == a["animal"]):
                continue
            prod = AN[a["animal"]]["product"]
            price = prices.get(prod, 0.0)
            nights = _animal_prod_nights(a, day, AN)
            tonight = bool(nights) and nights[0] == day
            bank = int(a.get("pending_care_bonus", 0) or 0)
            yu = int(a.get("yield_units", 0) or 0)
            if yu > 0:
                if tonight and yu + 1 + bank > AN[a["animal"]]["max_held"]:
                    jobs.append(Job(tile, "HARVEST", "M", 1, yu * price))
                else:
                    jobs.append(Job(tile, "HARVEST", "S", 1, 0.1 * yu * price))
            if a.get("fertilizer_available") and day < LAST_DAY:
                jobs.append(Job(tile, "COLLECT_FERTILIZER", "N", 1, fert_p))
            later = [n for n in nights if n > day] if tonight else nights   # the night a care today pays on
            if int(a.get("consecutive_unfed", 0)) >= 1:
                if nights:
                    jobs.append(Job(tile, "FEED", "M", 1, 0.0, needs=("item", "WHEAT")))
                    fed = "M"
                else:
                    useless["feed_no_production_left"] += 1
                    fed = None
            elif tonight and bank > 0:
                jobs.append(Job(tile, "FEED", "N", 1, bank * price, needs=("item", "WHEAT")))
                fed = "N"
            else:
                fed = None
            if later:
                if fed:
                    jobs.append(Job(tile, "CARE", "S", 1, price))          # banks +1 for a production still to come
                else:
                    jobs.append(Job(tile, "FEED+CARE", "S", 2, price, needs=("item", "WHEAT")))
            else:
                useless["care_no_production_left"] += 1
            continue
    supply = sum(1 for j in jobs if j.op == "COLLECT_FERTILIZER")   # the shed stock is sold at hour 0 (DSM)
    fz = sorted([j for j in jobs if j.op == "FERTILIZE"], key=lambda j: -j.value)
    if len(fz) > supply:                                  # no fertilizer for the rest: not a job today
        drop = set(fz[supply:])
        useless["fertilize_no_supply"] += len(drop)
        jobs = [j for j in jobs if j not in drop]
    return jobs, useless


def bringback_legs(D):
    """DSM's early-morning bring-back legs: a unit that harvests and then drops at the shed (DROP, or PLACE of goods on a
    shed-access tile) by hour 12. Returns {unit: dict(start, end, ops=[(tile, op)])} and each unit's first hour."""
    first, legs = {}, {}
    for h, stp in enumerate(D["steps"]):
        for u, (pos, cmd) in enumerate(zip(stp["pos"], stp["cmd"])):
            first.setdefault(u, h)
            if u in legs and legs[u].get("end") is not None:
                continue
            L = legs.setdefault(u, dict(start=first[u], end=None, ops=[], harvested=False))
            if not cmd:
                continue
            op = cmd[0]
            if op in ("HARVEST", "WATER", "FEED", "CARE", "COLLECT_FERTILIZER", "FERTILIZE", "PLANT", "DIG"):
                L["ops"].append((tuple(pos), op))
                L["harvested"] |= op == "HARVEST"
            elif op in ("DROP", "PLACE") and tuple(pos) in SHED and L["harvested"] and h <= 12 and (
                    op == "DROP" or cmd[1] not in ("COW", "SHEEP", "GOOSE")):
                L["end"] = h
    return {u: L for u, L in legs.items() if L.get("end") is not None}, first


# ------------------------------------------------------------------------------------------------------- partition
def dist(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def near_shed(p):
    return min(SHED, key=lambda s: dist(s, p))


def path_time(seq, tjobs, keep):
    """hours of a path: shed pickups (wheat / fertilizer beyond what its pens yield), walking from the nearest
    shed-access tile through the tiles in order, and the kept jobs"""
    if not seq:
        return 0, 0
    need_w = any(j.needs == ("item", "WHEAT") for t in seq for j in tjobs[t] if j in keep)
    n_fz = sum(1 for t in seq for j in tjobs[t] if j in keep and j.op == "FERTILIZE")
    n_cf = sum(1 for t in seq for j in tjobs[t] if j in keep and j.op == "COLLECT_FERTILIZER")
    pick = int(need_w) + int(n_fz > n_cf)
    walk = dist(near_shed(seq[0]), seq[0]) + sum(dist(seq[k], seq[k + 1]) for k in range(len(seq) - 1))
    work = sum(j.hours for t in seq for j in tjobs[t] if j in keep)
    return pick + walk + work, walk


def order_path(tiles):
    """open path from the shed: nearest-neighbour from the tile closest to the shed, then 2-opt on the walk"""
    if not tiles:
        return []
    rest = set(tiles)
    cur = min(rest, key=lambda t: (dist(near_shed(t), t), t))
    seq = [cur]
    rest.discard(cur)
    while rest:
        cur = min(rest, key=lambda t: (dist(cur, t), dist(near_shed(t), t), t))
        seq.append(cur)
        rest.discard(cur)

    def walk(s):
        return dist(near_shed(s[0]), s[0]) + sum(dist(s[k], s[k + 1]) for k in range(len(s) - 1))
    best = walk(seq)
    improved = True
    while improved:
        improved = False
        for i in range(len(seq) - 1):
            for j in range(i + 1, len(seq)):
                cand = seq[:i] + seq[i:j + 1][::-1] + seq[j + 1:]
                w = walk(cand)
                if w < best:
                    seq, best, improved = cand, w, True
    return seq


def fit(seq, tjobs, T):
    """keep every mandatory job, then non-mandatory and slack by class and value while the path fits T; drop
    slack-only tiles that end up with nothing kept (their walk is saved)"""
    alljobs = [j for t in seq for j in tjobs[t]]
    keep = set(alljobs)
    order = sorted([j for j in alljobs if j.cls != "M"], key=lambda j: ({"S": 0, "N": 1}[j.cls], j.value))
    cut = []
    s = list(seq)
    for j in order:
        tm, _ = path_time(s, tjobs, keep)
        if tm <= T:
            break
        keep.discard(j)
        cut.append(j)
        s2 = [t for t in s if any(x in keep for x in tjobs[t])] or s[:1]
        if len(s2) != len(s):
            s = order_path(s2)
    for j in sorted(cut, key=lambda j: ({"N": 0, "S": 1}[j.cls], -j.value)):   # put back what still fits
        keep.add(j)
        s2 = s if j.tile in s else order_path(s + [j.tile])
        if path_time(s2, tjobs, keep)[0] <= T:
            s = s2
            cut.remove(j)
        else:
            keep.discard(j)
    tm, walk = path_time(s, tjobs, keep)
    return dict(seq=s, keep=keep, cut=cut, time=tm, walk=walk)


def plan_group(g, tjobs, T):
    full = order_path(g)
    p_ = fit(full, tjobs, T)
    p_.update(group=list(g), T=T)
    p_["m_time"] = path_time(p_["seq"], tjobs, {j for t in p_["seq"] for j in tjobs[t] if j.cls == "M"})[0]
    p_["all_time"] = path_time(full, tjobs, {j for t in full for j in tjobs[t]})[0]
    return p_


def score(plans):
    """the user's order: no mandatory over the day, no non-mandatory cut, every path >= day + 1 with slack, then walk"""
    return (sum(max(0, q["m_time"] - q["T"]) for q in plans),
            sum(j.hours for q in plans for j in q["cut"] if j.cls == "N"),
            sum(max(0, q["T"] + 1 - q["all_time"]) for q in plans),
            sum(q["walk"] for q in plans))


def improve(plans, tjobs, passes=6):
    """shift boundary tiles between neighbouring sectors (the sweep is circular) while the score improves"""
    plans = list(plans)
    best = score(plans)
    K = len(plans)
    for _ in range(passes):
        better = False
        for k in range(K if K > 2 else K - 1):
            k2 = (k + 1) % K
            for move in ("a->b", "b->a"):
                ga, gb = list(plans[k]["group"]), list(plans[k2]["group"])
                if move == "a->b" and len(ga) > 1:
                    gb.insert(0, ga.pop())
                elif move == "b->a" and len(gb) > 1:
                    ga.append(gb.pop(0))
                else:
                    continue
                qa, qb = plan_group(ga, tjobs, plans[k]["T"]), plan_group(gb, tjobs, plans[k2]["T"])
                trial = list(plans)
                trial[k], trial[k2] = qa, qb
                sc = score(trial)
                if sc < best:
                    plans, best, better = trial, sc, True
        if not better:
            break
    return plans


def partition(tjobs, K, T_list):
    """sweep the work tiles by angle around the shed into K contiguous sectors of balanced load, one open path each"""
    tiles = [t for t in tjobs if tjobs[t]]
    if not tiles:
        return []
    ang = lambda t: (math.atan2(t[1] - 4.5, t[0] - 4.5), dist(near_shed(t), t))  # noqa: E731
    tiles.sort(key=ang)
    load = {t: sum(j.hours for j in tjobs[t] if j.cls in ("M", "N")) + 1.2 for t in tiles}
    total = sum(load.values())
    cum_T = [sum(T_list[:k + 1]) / sum(T_list) for k in range(len(T_list))]   # sector k's share ~ its budget
    cands = []
    for rot in range(0, len(tiles), max(1, len(tiles) // 12)):   # where the sweep starts matters: try rotations
        seqs = tiles[rot:] + tiles[:rot]
        groups, cur, acc, gi = [], [], 0.0, 0
        for t in seqs:
            cur.append(t)
            acc += load[t]
            if acc >= total * cum_T[gi] and len(groups) < K - 1:
                groups.append(cur)
                cur, gi = [], gi + 1
        groups.append(cur)
        plans = [plan_group(g, tjobs, T) for g, T in zip(groups, T_list)]
        cands.append((score(plans), plans))
    cands.sort(key=lambda c: c[0])
    best = None
    for sc, plans in cands[:3]:                          # local search on the three best sweeps
        plans = improve(plans, tjobs)
        if best is None or score(plans) < best[0]:
            best = (score(plans), plans)
    return best[1]


def run(a):
    CR, AN = _engine_tables()
    games = json.loads(gzip.open(CACHE, "rt", encoding="utf-8").read())
    d0, d1 = [int(x) for x in a.days.split("-")]
    rows = []
    detail = tuple(a.detail.split(":")) if a.detail else None
    for ep, g in games.items():
        for ds, D in g["days"].items():
            day = int(ds)
            if not (d0 <= day <= d1) or not D.get("dusk"):
                continue
            jobs, useless = day_jobs(D["dawn"], D["dusk"], day, D["prices"], CR, AN, D.get("shed"))
            legs, first = bringback_legs(D) if a.bringback else ({}, {u: (0 if u == 0 else 1) for u in range(30)})
            done_bb = Counter((t, op) for L in legs.values() for (t, op) in L["ops"])
            bb_jobs = 0
            for j in list(jobs):                          # the bring-back legs' own work is theirs, planned first
                key_ = [(j.tile, o) for o in j.op.split("+")]
                if any(done_bb[k_] > 0 for k_ in key_):
                    for k_ in key_:
                        if done_bb[k_] > 0:
                            done_bb[k_] -= 1
                    jobs.remove(j)
                    bb_jobs += 1
            tjobs = {}
            for j in jobs:
                tjobs.setdefault(j.tile, []).append(j)
            # DSM that day: units, walking, idle
            units = max(len(s["pos"]) for s in D["steps"])
            moves = sum(1 for s in D["steps"] for c in s["cmd"] if c and c[0] in MOVES)
            idle = sum(1 for s in D["steps"] for c in s["cmd"] if not c or c[0] == "PASS")
            M = sum(j.hours for j in jobs if j.cls == "M")
            N = sum(j.hours for j in jobs if j.cls == "N")
            S = sum(j.hours for j in jobs if j.cls == "S")
            # DSM's units: hours on the farm today minus the bring-back leg (the second leg's walk out is in the path)
            T_dsm = [24 - first.get(u, 1) - ((legs[u]["end"] - legs[u]["start"] + 1) if u in legs else 0)
                     for u in range(units)]
            res = {}
            for K in range(max(4, units - 3), units + 2):
                T_list = (T_dsm + [23] * K)[:K] if K >= units else sorted(T_dsm, reverse=True)[:K]
                plans = partition(tjobs, K, T_list)
                res[K] = dict(m_over=sum(max(0.0, p_["m_time"] - p_["T"]) for p_ in plans),
                              walk=sum(p_["walk"] for p_ in plans),
                              cut_n=sum(j.hours for p_ in plans for j in p_["cut"] if j.cls == "N"),
                              cut_s=sum(j.hours for p_ in plans for j in p_["cut"] if j.cls == "S"),
                              short=sum(1 for p_ in plans if p_["all_time"] < p_["T"] + 1),
                              idle=sum(max(0.0, p_["T"] - p_["all_time"]) for p_ in plans),
                              plans=plans)
            kmin = next((K for K in sorted(res) if res[K]["m_over"] == 0 and res[K]["cut_n"] == 0), None)
            rows.append(dict(ep=ep, day=day, units=units, moves=moves, idle=idle, M=M, N=N, S=S, useless=dict(useless),
                             kmin=kmin, at_units=res.get(units), bb=len(legs), bb_jobs=bb_jobs,
                             bb_hours=sum(L["end"] - L["start"] + 1 for L in legs.values())))
            if detail and ep == detail[0] and day == int(detail[1]):
                r = res.get(units)
                print(f"\n{ep} day {day}: DSM {units} units, {moves} moves; jobs M {M} N {N} S {S} h; useless {dict(useless)}")
                for k, p_ in enumerate(r["plans"]):
                    kept = p_["keep"]
                    print(f"  worker {k}: {len(p_['seq'])} tiles, walk {p_['walk']}, time {p_['time']}/{p_['T']} (all work "
                          f"{p_['all_time']}), M {sum(j.hours for j in kept if j.cls == 'M')} N {sum(j.hours for j in kept if j.cls == 'N')}"
                          f" S {sum(j.hours for j in kept if j.cls == 'S')}, cut {[repr(j) for j in p_['cut']][:6]} | path {p_['seq']}")
    by = {}
    for r in rows:
        by.setdefault((r["day"] - 11) // 5, []).append(r)
    print(f"{len(rows)} DSM game-days; per game-day means")
    print("days   | jobs M / N / S (h) | DSM units, moves | ours at DSM's crew: walk, N cut, S cut, M over | "
          "fewest workers with no M over and no N cut | paths short of 25h")
    for k in sorted(by):
        rs = by[k]
        m = lambda f: st.mean(f(r) for r in rs)  # noqa: E731
        print(f"{min(r['day'] for r in rs)}-{max(r['day'] for r in rs)}  | {m(lambda r: r['M']):5.1f} / {m(lambda r: r['N']):5.1f} / "
              f"{m(lambda r: r['S']):5.1f} | {m(lambda r: r['units']):5.1f}, {m(lambda r: r['moves']):6.1f} | "
              f"{m(lambda r: r['at_units']['walk'] if r['at_units'] else 0):6.1f}, {m(lambda r: r['at_units']['cut_n'] if r['at_units'] else 0):4.1f}, "
              f"{m(lambda r: r['at_units']['cut_s'] if r['at_units'] else 0):5.1f}, {m(lambda r: r['at_units']['m_over'] if r['at_units'] else 0):4.1f} | "
              f"{m(lambda r: r['kmin'] if r['kmin'] else r['units'] + 3):5.1f} (none within DSM+2 in {sum(1 for r in rs if not r['kmin'])}) | "
              f"{m(lambda r: r['at_units']['short'] if r['at_units'] else 0):4.1f}")
    print("idle hours at DSM's crew (paths whose whole work, slack included, ends before the day): "
          + ", ".join(f"days {min(r['day'] for r in rs)}-{max(r['day'] for r in rs)} {st.mean(r['at_units']['idle'] for r in rs if r['at_units']):.1f}"
                      for rs in (by[k] for k in sorted(by))))
    u = Counter()
    for r in rows:
        u.update(r["useless"])
    print(f"bring-back legs (DSM's own, planned first): {st.mean(r['bb'] for r in rows):.1f} units a day, "
          f"{st.mean(r['bb_hours'] for r in rows):.1f} unit-hours, {st.mean(r['bb_jobs'] for r in rows):.1f} jobs taken off the pool")
    print("useless jobs filtered, per game-day: " + ", ".join(f"{k} {v / len(rows):.1f}" for k, v in u.most_common()))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cache")
    c.add_argument("--workers", type=int, default=2)
    r = sub.add_parser("run")
    r.add_argument("--days", default="11-28")
    r.add_argument("--detail", default="")
    r.add_argument("--bringback", type=int, default=1)
    a = ap.parse_args()
    {"cache": cache, "run": run}[a.cmd](a)


if __name__ == "__main__":
    main()

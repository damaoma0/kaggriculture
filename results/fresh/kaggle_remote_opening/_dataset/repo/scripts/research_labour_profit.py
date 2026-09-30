"""Exact-engine, fixed-production labour/delivery research on recorded games.

This is an OFFLINE experiment. Recorded daily jobs and a hindsight feasibility
filter are supplied to every selector. 'oracle' also sees future opponent trades.
No variant is a deployable online agent or a proof of global optimality.

Run with the project Python; --help documents reproducible bounded workloads.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import io
import json
import gzip
import random
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/labour_profit"
SHED = ((4, 4), (5, 4), (4, 5), (5, 5))
MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "WEST": (-1, 0), "EAST": (1, 0)}
OUTPUTS = {"CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"}
PASS = {"farmer": ["PASS"], "hands": [], "market": []}
E = None


def engine():
    global E
    if E is None:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle_environments.envs.kaggriculture import kaggriculture
        E = kaggriculture
    return E


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items() if v != 0}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def walk(a, b):
    return ([["EAST" if b[0] > a[0] else "WEST"]] * abs(b[0] - a[0])
            + [["SOUTH" if b[1] > a[1] else "NORTH"]] * abs(b[1] - a[1]))


class Simulator:
    """Use the unmodified official interpreter, omitting framework history copies.

    Counters observe successful transactions. Physical events are captured only
    while extracting a baseline production plan. No prices or yields are emulated.
    """
    def __init__(self, game):
        engine()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle_environments import make
            env = make("kaggriculture", configuration={"episodeSteps": 720}, info={"seed": game["seed"]})
            env.reset()
        self.initial = deepcopy(env.state)
        self.env = SimpleNamespace(configuration=env.configuration, info=env.info, done=False)
        self.game = game
        self.old_commit = E._commit_unit
        self.old_unit = E._apply_unit_action
        self.old_hire = E._do_hire
        self.old_land = E._do_buy_land
        self.events = []
        self.work = []
        self.capture = False
        self.seats = {}
        self.t = 0

    def __enter__(self):
        def commit(op, item, price, farm, private, market, shed_capacity=100):
            ok = self.old_commit(op, item, price, farm, private, market, shed_capacity)
            if ok:
                self.events.append((self.t, self.seats[id(farm)], op, item, price))
            return ok

        def unit(farm, private, idx, action, *args, **kwargs):
            if not self.capture or not action or action[0] in MOVES or action[0] == "PASS":
                return self.old_unit(farm, private, idx, action, *args, **kwargs)
            pos = E._farmer_position(farm, idx)
            if pos is None:
                return self.old_unit(farm, private, idx, action, *args, **kwargs)
            pos = tuple(pos)
            before = deepcopy((farm["tiles"][pos[1]][pos[0]], private))
            result = self.old_unit(farm, private, idx, action, *args, **kwargs)
            after = (farm["tiles"][pos[1]][pos[0]], private)
            if before != after:
                a = before[1]["inventories"][idx]
                b = private["inventories"][idx]
                delta = {p: b.get(p, 0) - a.get(p, 0) for p in set(a) | set(b)}
                self.work.append(dict(t=self.t, seat=self.seats[id(farm)], unit=idx,
                                      pos=pos, cmd=list(action), delta=delta))
            return result

        def atomic(fn, label):
            def call(farm, *args, **kwargs):
                before = farm["money"]
                result = fn(farm, *args, **kwargs)
                if before != farm["money"]:
                    self.events.append((self.t, self.seats[id(farm)], label, "", before - farm["money"]))
                return result
            return call

        E._commit_unit, E._apply_unit_action = commit, unit
        E._do_hire, E._do_buy_land = atomic(self.old_hire, "HIRE"), atomic(self.old_land, "BUY_LAND")
        return self

    def __exit__(self, *args):
        E._commit_unit, E._apply_unit_action = self.old_commit, self.old_unit
        E._do_hire, E._do_buy_land = self.old_hire, self.old_land

    def run(self, initial, start, stop, actions, capture=False, snapshots=False, advance=False, quota=None,
            reference=None, advance_items=None):
        state = deepcopy(initial)
        self.events, self.work, self.capture = [], [], capture
        states = {}
        sold = Counter()
        remaining = Counter(quota or {})
        due = Counter()
        scheduled = defaultdict(Counter)
        if reference is not None:
            for t, s, op, p, _ in reference["events"]:
                if s == self.game["seat"] and op == "SELL":
                    scheduled[t][p] += 1
        advance_items = OUTPUTS if advance_items is None else set(advance_items)
        for t in range(start, stop):
            self.t = t
            self.seats = {id(f): i for i, f in enumerate(state[0].observation.farms)}
            # The framework normally advances this field outside interpreter.
            # Set it before snapshots as well as before action evaluation.
            for seat in range(2):
                state[seat].observation.step = t
            if snapshots:
                states[t] = deepcopy(state)
            for seat in range(2):
                state[seat].action = deepcopy(actions[seat][t] or PASS)
            ours = self.game["seat"]
            if advance:
                # Execute our physical commands on a private copy to know what
                # is legally available for this turn's market (public opponent
                # actions are NOT needed for this availability calculation).
                farm = deepcopy(state[0].observation.farms[ours])
                private = deepcopy(state[ours].observation.private)
                act = state[ours].action
                cmds = [act.get("farmer") or ["PASS"], *(act.get("hands") or [])]
                demands = Counter(c[1] for c in cmds if c and c[0] == "PLANT" and len(c) > 1)
                for u, c in enumerate(cmds):
                    if c[0] == "PLANT" and demands[c[1]] > private["seeds"].get(c[1], 0):
                        continue
                    self.old_unit(farm, private, u, c, 10, t // 24, 24, 100)
                market = []
                for order in (act.get("market") or [])[:10]:
                    if order and order[0] == "SELL" and order[1] in OUTPUTS:
                        continue
                    market.append(order)
                available = private["shed"]
                extra_available = available
                if reference is not None:
                    due.update(scheduled[t])
                    ref = reference["snapshots"][t]
                    ref_farm = deepcopy(ref[0].observation.farms[ours])
                    ref_private = deepcopy(ref[ours].observation.private)
                    ref_act = actions[ours][t] if t >= start + 24 else self.reference_actions[ours][t]
                    ref_cmds = [ref_act.get("farmer") or ["PASS"], *(ref_act.get("hands") or [])]
                    demands = Counter(c[1] for c in ref_cmds if c and c[0] == "PLANT" and len(c) > 1)
                    for u, c in enumerate(ref_cmds):
                        if c[0] == "PLANT" and demands[c[1]] > ref_private["seeds"].get(c[1], 0):
                            continue
                        self.old_unit(ref_farm, ref_private, u, c, 10, t // 24, 24, 100)
                    extra_available = {p: max(0, available.get(p, 0) - ref_private["shed"].get(p, 0)) for p in OUTPUTS}
                    # Retain original market-order positions for scheduled sales.
                    # Only quantities made newly accessible by changed delivery
                    # routes may be sold ahead of that schedule.
                    market = []
                    requested = Counter()
                    for order in (act.get("market") or [])[:10]:
                        if order and order[0] == "SELL" and order[1] in OUTPUTS:
                            p = order[1]
                            n = min(int(order[2]) if len(order) > 2 else 1,
                                    max(0, due[p] - sold[p] - requested[p]))
                            market.append(["SELL", p, n])
                            requested[p] += n
                        else:
                            market.append(order)
                # Larger current marginal value first. Same rule in every arm.
                items = sorted(OUTPUTS, key=lambda p: (-E.market_price(p, state[0].observation.market["inventory"][p]), p))
                for p in items:
                    if p not in advance_items:
                        continue
                    reserved = requested[p] if reference is not None else 0
                    n = min(extra_available.get(p, 0), remaining[p] - reserved,
                            available.get(p, 0) - reserved)
                    if n > 0 and len(market) < 10:
                        market.append(["SELL", p, n])
                act["market"] = market
            mark = len(self.events)
            E.interpreter(state, self.env)
            for _, s, op, item, _ in self.events[mark:]:
                if s == ours and op == "SELL":
                    sold[item] += 1
                    remaining[item] -= 1
            if (t + 1) % 24 == 0:
                state[0].observation.town.unlocked_shops[:] = self.game["shops"][min(30, (t + 1) // 24)]
        for seat in range(2):
            state[seat].observation.step = stop
        return dict(state=state, events=list(self.events), work=list(self.work), snapshots=states,
                    money=[f["money"] for f in state[0].observation.farms], sold=dict(sold))


def economic(events, seat):
    rev, spend, units = Counter(), Counter(), Counter()
    for t, s, op, item, price in events:
        if s != seat:
            continue
        if op == "SELL":
            rev[item] += price
            units[item] += 1
        else:
            spend[op + (":" + item if item else "")] += price
    return dict(revenue=dict(rev), spend=dict(spend), units=dict(units))


def equivalent(base, trial, seat):
    """Strong continuation contract, independently for each 48-hour block.

    Both farms, both private inventories/seeds, successful trade quantities,
    and terminal market inventory must agree. Money and removed hire payments
    may differ. Thus discarded harvest, failed inputs, or damaged opponent
    production cannot masquerade as a labour/profit improvement.
    """
    a, b = base["state"], trial["state"]
    for s in (0, 1):
        fa, fb = deepcopy(a[0].observation.farms[s]), deepcopy(b[0].observation.farms[s])
        fa.pop("money", None)
        fb.pop("money", None)
        if fa != fb:
            return "farm"
        if clean(a[s].observation.private) != clean(b[s].observation.private):
            return "private"
    if a[0].observation.market != b[0].observation.market:
        return "market"
    def quantities(events):
        return Counter((s, op, item) for _, s, op, item, _ in events if op not in ("HIRE", "BUY_LAND"))
    if quantities(base["events"]) != quantities(trial["events"]):
        return "trades"
    return None


@dataclass
class Job:
    id: int
    pos: tuple
    cmds: list
    deltas: list
    release: int
    today: bool
    original: int


def extract(base, seat, start):
    """Keep first two hours (including spawn geometry) and route from hour 2.

    Successful tile operations are the fixed production plan; original no-ops
    and inventory transport are not production requirements. Purchase-dependent
    jobs retain their recorded release times. Engine validation enforces all
    remaining cross-worker, tile, cash and inventory dependencies.
    """
    stop = start + 24
    cut = base["snapshots"][start + 2]
    farm = cut[0].observation.farms[seat]
    private = cut[seat].observation.private
    positions = [tuple(farm["farmer"]), *map(tuple, farm["hands"])]
    units = {u: (2, p, dict(private["inventories"][u])) for u, p in enumerate(positions)}
    events = [w for w in base["work"] if w["seat"] == seat and start <= w["t"] < stop]
    frozen = {w["unit"] for w in events if w["t"] < start + 2 and w["cmd"][0] not in ("PICKUP", "DROP")}
    routes = {u: [] for u in units}
    jobs = []
    last_drop = {u: max((w["t"] for w in events if w["unit"] == u and w["pos"] in SHED
                       and w["cmd"][0] in ("DROP", "PLACE")), default=-1) for u in units}
    for u in units:
        cur = None
        for w in events:
            if w["unit"] != u or w["t"] < start + 2:
                continue
            op = w["cmd"][0]
            if op in ("PICKUP", "DROP") or (op == "PLACE" and w["pos"] in SHED):
                cur = None
                continue
            if cur is None or cur.pos != w["pos"]:
                cur = Job(len(jobs), w["pos"], [], [], 2, False, u)
                jobs.append(cur)
                routes[u].append(cur.id)
            cur.cmds.append(w["cmd"])
            cur.deltas.append(w["delta"])
            if op in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE"):
                cur.release = max(cur.release, w["t"] - start - len(cur.cmds) + 1)
            if op in ("HARVEST", "COLLECT_FERTILIZER") and w["t"] < last_drop[u]:
                cur.today = True
    # Routes that establish crops/animals depend on intraday purchases and tile
    # precedence. Keep them executable exactly as recorded in this prototype.
    locked = {u for u, route in routes.items() if any(any(c[0] in ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE")
                                                       for c in jobs[j].cmds) for j in route)}
    return units, routes, jobs, frozen, locked


def tile_values(initial, seat, jobs):
    """Heuristic ranking, not an accounting valuation or optional-job selector.

    All jobs remain mandatory. Value governs insertion priority only; avoiding
    a death gets high priority and a saleable harvest gets its public spot value.
    Engine validation and the actual profit comparison decide acceptance.
    """
    obs = initial[0].observation
    prices = obs.market["prices"]
    values = {}
    for job in jobs:
        tile = obs.farms[seat]["tiles"][job.pos[1]][job.pos[0]]
        value = 1.0
        for cmd, delta in zip(job.cmds, job.deltas):
            value += sum(max(0, n) * prices.get(p, 0) for p, n in delta.items())
            if not isinstance(tile, dict):
                continue
            if cmd[0] == "WATER":
                value += 10000 if tile.get("consecutive_unwatered", 0) else prices.get(tile.get("crop"), 100)
            elif cmd[0] in ("FEED", "CARE") and tile.get("animal"):
                value += prices[E.ANIMALS[tile["animal"]]["product"]]
                if cmd[0] == "FEED" and tile.get("consecutive_unfed", 0):
                    value += 10000
        values[job.id] = value
    return values


def compile_route(unit, route, jobs, delivery="recorded"):
    t, pos, initial = unit
    inv = Counter(initial)
    commands = []
    segments = []
    last = max((i for i, j in enumerate(route) if jobs[j].today), default=-1)
    if delivery == "early":
        # Return after the last sellable harvest, even when the tape used the
        # automatic midnight return. Extra trips remain an explicit labour cost.
        last = max(last, max((i for i, j in enumerate(route)
                             if any(any(p in OUTPUTS and n > 0 for p, n in delta.items())
                                    for delta in jobs[j].deltas)), default=-1))
    if last >= 0:
        segments.append((route[:last + 1], True))
        if route[last + 1:]:
            segments.append((route[last + 1:], False))
    else:
        segments.append((route, False))
    for segment, drop in segments:
        balances, need = Counter(inv), Counter()
        for j in segment:
            for delta in jobs[j].deltas:
                balances.update(delta)
                for p, n in balances.items():
                    need[p] = max(need[p], -n)
        pickups = {p: n for p, n in need.items() if n > 0}
        if pickups:
            home = min(SHED, key=lambda q: (distance(pos, q), q))
            commands += walk(pos, home)
            t += distance(pos, home)
            pos = home
            for p, n in sorted(pickups.items()):
                commands.append(["PICKUP", p, n])
                t += 1
                inv[p] += n
        for j in segment:
            job = jobs[j]
            commands += walk(pos, job.pos)
            t += distance(pos, job.pos)
            pos = job.pos
            if job.release > t:
                commands += [["PASS"]] * (job.release - t)
                t = job.release
            commands += job.cmds
            t += len(job.cmds)
            for delta in job.deltas:
                inv.update(delta)
        if drop:
            home = min(SHED, key=lambda q: (distance(pos, q), q))
            commands += walk(pos, home) + [["DROP"]]
            t += distance(pos, home) + 1
            pos = home
            inv.clear()
    return t, commands


def arrange(units, original, jobs, frozen, seed, rounds=80, locked=(), values=None):
    """Bounded deterministic relocation/2-opt and suffix-hand elimination.

    Removing a suffix of hires keeps surviving hand indices and spawn tiles.
    Save multiple crew sizes: shortest/minimum-crew and high-delivery-value plans
    need not coincide. Resource feasibility is checked by the engine, not assumed.
    """
    rng = random.Random(seed)
    cache = {}
    def cost(u, route):
        key = u, tuple(route)
        if key not in cache:
            cache[key] = compile_route(units[u], route, jobs)[0]
        return cache[key]
    routes = deepcopy(original)
    for u, route in routes.items():
        if u in locked:
            continue
        improved = True
        while improved:
            improved = False
            for i in range(len(route)):
                for k in range(i + 1, len(route)):
                    candidate = route[:i] + route[i:k + 1][::-1] + route[k + 1:]
                    if cost(u, candidate) < cost(u, route):
                        route = candidate
                        improved = True
            routes[u] = route
    candidates = [("shorter", deepcopy(routes)), ("original_jobs", deepcopy(original))]
    # Try several randomized complete assignments for each removable suffix.
    for remove in (1, 2, 3):
        keep = len(units) - remove
        gone = set(range(keep, len(units)))
        if keep < 1 or gone & (set(frozen) | set(locked)):
            continue
        best = None
        for attempt in range(12):
            trial = {u: list(routes[u]) for u in range(keep)}
            pool = [j for u in sorted(gone) for j in routes[u]]
            if attempt:
                available = [u for u in trial if u not in locked]
                for u in rng.sample(available, min(3, len(available))):
                    if trial[u]:
                        k = rng.randrange(len(trial[u]))
                        pool.append(trial[u].pop(k))
                rng.shuffle(pool)
            okay = True
            while pool:
                opts = []
                for j in pool:
                    insertions = []
                    for u, route in trial.items():
                        if u in locked:
                            continue
                        for k in range(len(route) + 1):
                            c = cost(u, route[:k] + [j] + route[k:])
                            if c <= 24:
                                insertions.append((c - cost(u, route), c, u, k))
                    insertions.sort()
                    if not insertions:
                        okay = False
                        break
                    regret = insertions[1][0] - insertions[0][0] if len(insertions) > 1 else 100
                    opts.append((-regret, insertions[0], j))
                if not okay:
                    break
                _, (_, _, u, k), j = min(opts)
                trial[u].insert(k, j)
                pool.remove(j)
            if okay:
                score = sum(cost(u, r) for u, r in trial.items())
                if best is None or score < best[0]:
                    best = score, trial
        if best:
            candidates.append((f"minus{remove}", best[1]))
    # Reassign one job at a time at full crew size to consolidate delivery slack.
    trial = deepcopy(routes)
    for _ in range(rounds):
        us = [u for u in trial if trial[u] and u not in locked]
        if not us:
            break
        u = rng.choice(us)
        v = rng.choice([u for u in trial if u not in locked])
        if u == v:
            continue
        i = rng.randrange(len(trial[u]))
        j = trial[u][i]
        left = trial[u][:i] + trial[u][i + 1:]
        opts = [(cost(v, trial[v][:k] + [j] + trial[v][k:]), k) for k in range(len(trial[v]) + 1)]
        c, k = min(opts)
        if max(c, cost(u, left)) <= 24 and c + cost(u, left) < cost(u, trial[u]) + cost(v, trial[v]):
            trial[u], trial[v] = left, trial[v][:k] + [j] + trial[v][k:]
    candidates.append(("relocate", trial))
    harvest_first = deepcopy(routes)
    for u in harvest_first:
        if u not in locked:
            harvest_first[u].sort(key=lambda j: -sum(n for delta in jobs[j].deltas for p, n in delta.items() if p in OUTPUTS))
    candidates.append(("harvest_first", harvest_first))
    # User-proposed tile value / incremental travel+service heuristic, compared
    # with a distance-only construction. Keep every job; do not drop low-value
    # work to manufacture a cheaper but different production plan.
    for remove in (0, 1, 2):
        keep = len(units) - remove
        gone = set(range(keep, len(units)))
        if keep < 1 or gone & (set(frozen) | set(locked)):
            continue
        for method in ("distance", "tile_value"):
            trial = {u: list(original[u]) if u in locked else [] for u in range(keep)}
            pool = [j for u, route in original.items() if u not in locked for j in route]
            while pool:
                options = []
                for j in pool:
                    for u, route in trial.items():
                        if u in locked:
                            continue
                        for k in range(len(route) + 1):
                            c = cost(u, route[:k] + [j] + route[k:])
                            if c <= 24:
                                extra = max(1, c - cost(u, route))
                                value = (values or {}).get(j, 1) if method == "tile_value" else 1
                                options.append((-value / extra, c, u, k, j))
                if not options:
                    break
                _, _, u, k, j = min(options)
                trial[u].insert(k, j)
                pool.remove(j)
            if not pool:
                candidates.append((f"{method}_minus{remove}", trial))
    return candidates


def prefix_actions(original, start, worker_ids):
    """Remove chosen hire orders and remap surviving workers, retaining slots."""
    acts = list(original)
    ids = sorted(worker_ids)
    hires = 0
    for t in range(start, start + 24):
        source = original[t] or PASS
        a = deepcopy(source)
        market = []
        for order in (a.get("market") or [])[:10]:
            if order and order[0] == "HIRE":
                hires += 1
                if hires not in ids:
                    # Preserve the order slot: later simultaneous trades must
                    # not move to a different slot merely because a hire went.
                    market.append(["SELL", "WHEAT", 0])
                    continue
            market.append(order)
        a["market"] = market
        raw = [source.get("farmer") or ["PASS"], *(source.get("hands") or [])]
        a["farmer"] = raw[0]
        a["hands"] = [raw[u] if u < len(raw) else ["PASS"] for u in ids if u > 0]
        acts[t] = a
    return acts


def actions_for(original, start, routes, units, jobs, delivery, locked=()):
    acts = prefix_actions(original, start, routes)
    compiled = {}
    for u, route in routes.items():
        if u in locked:
            continue
        finish, commands = compile_route(units[u], route, jobs, delivery)
        if finish > 24:
            return None
        compiled[u] = commands
    for t in range(start, start + 24):
        a = acts[t]
        if t >= start + 2:
            idx = t - start - 2
            raw = [a.get("farmer") or ["PASS"], *(a.get("hands") or [])]
            cmds = [(raw[u] if u < len(raw) else ["PASS"]) if u in locked
                    else compiled[u][idx] if idx < len(compiled[u]) else ["PASS"] for u in routes]
            a["farmer"], a["hands"] = cmds[0], cmds[1:]
        acts[t] = a
    return acts


def remove_any_worker(sim, initial, actions, start, units, routes, jobs, frozen):
    """Recalculate real spawn positions after removing any suitable hand.

    Marginal cost is the final Fibonacci hire cost regardless of which worker's
    task bundle is reassigned. This avoids the suffix-only model's blind spot.
    """
    seat = sim.game["seat"]
    eligible = sorted((u for u in units if u and u not in frozen),
                      key=lambda u: sum(len(jobs[j].cmds) for j in routes[u]))[:6]
    result = []
    for gone in eligible:
        ids = sorted(set(units) - {gone})
        pair = list(actions)
        pair[seat] = prefix_actions(actions[seat], start, ids)
        cut = sim.run(initial, start, start + 2, pair)["state"]
        farm, private = cut[0].observation.farms[seat], cut[seat].observation.private
        positions = [farm["farmer"], *farm["hands"]]
        if len(positions) != len(ids):
            continue
        actual = {u: (2, tuple(positions[i]), dict(private["inventories"][i])) for i, u in enumerate(ids)}
        cache = {}
        def cost(u, route):
            key = u, tuple(route)
            if key not in cache:
                cache[key] = compile_route(actual[u], route, jobs)[0]
            return cache[key]
        seed_routes = {u: list(routes[u]) for u in ids}
        for u in ids:
            route = seed_routes[u]
            for _ in range(2):
                for i in range(len(route)):
                    for k in range(i + 1, len(route)):
                        candidate = route[:i] + route[i:k + 1][::-1] + route[k + 1:]
                        if cost(u, candidate) < cost(u, route):
                            route = candidate
            seed_routes[u] = route
        rng = random.Random(sim.game["episode"] + start + gone)
        for attempt in range(6):
            trial = deepcopy(seed_routes)
            pool = list(routes[gone])
            if attempt:
                for u in rng.sample(ids, min(3, len(ids))):
                    if trial[u]:
                        pool.append(trial[u].pop(rng.randrange(len(trial[u]))))
                rng.shuffle(pool)
            # Ruin routes that do not fit after their changed spawn position.
            for u in ids:
                while trial[u] and cost(u, trial[u]) > 24:
                    pool.append(trial[u].pop())
            while pool:
                options = []
                for j in pool:
                    placements = []
                    for u, route in trial.items():
                        for k in range(len(route) + 1):
                            c = cost(u, route[:k] + [j] + route[k:])
                            if c <= 24:
                                placements.append((c - cost(u, route), c, u, k))
                    if not placements:
                        options = []
                        break
                    placements.sort()
                    regret = placements[1][0] - placements[0][0] if len(placements) > 1 else 100
                    options.append((-regret, placements[0], j))
                if not options:
                    break
                _, (_, _, u, k), j = min(options)
                trial[u].insert(k, j)
                pool.remove(j)
            if not pool:
                result.append((f"remove_worker{gone}_try{attempt}", trial, set(), actual))
                break
    return result


def forecast_value(initial, events, seat, supply_scale=1.0):
    """Fixed public-board forecast: no future shops/trades/private rival state.

    Current held rival output is spread over 24 hours, plus visible animal output
    at uncared production rate. This is intentionally a simple frozen baseline.
    Own successful trade quantities come from the offline feasibility filter.
    """
    obs = initial[0].observation
    inv = dict(obs.market["inventory"])
    shops = obs.town["unlocked_shops"]
    flow = Counter()
    for row in obs.farms[1 - seat]["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("animal"):
                data = E.ANIMALS[tile["animal"]]
                flow[data["product"]] += tile.get("yield_units", 0) / 24 + 1 / data["interval"] / 24
            elif tile.get("kind") == "PLANT":
                c = tile["crop"]
                if obs.day - tile["planted_day"] >= E.CROPS[c]["first_yield_day"]:
                    flow[c] += tile.get("yield_units", 0) / 24
    grouped = defaultdict(list)
    for event in events:
        if event[1] == seat:
            grouped[event[0]].append(event)
    score = 0
    for t in range(obs.step, max(grouped, default=obs.step) + 1):
        for _, _, op, p, price in grouped[t]:
            if op == "SELL":
                quote = E.market_price(p, inv[p], obs.market.get("params"))
                score += quote
                inv[p] += quote > 1
            elif op == "BUY_PRODUCT":
                score -= E.market_price(p, inv[p] - 1, obs.market.get("params"))
                inv[p] -= 1
            else:
                score -= price
        for p in inv:
            inv[p] += supply_scale * flow[p]
            if t % 4 == 0:
                inv[p] -= sum((2 if len(E.SHOPS[s]) == 1 else 1) for s in shops if p in E.SHOPS[s])
            if t % 24 == 0 and p != "FERTILIZER":
                inv[p] -= 1
    return score


def block(sim, initial, actions, start, stop, rounds):
    seat = sim.game["seat"]
    base = sim.run(initial, start, stop, actions, capture=True, snapshots=True)
    units, routes, jobs, frozen, locked = extract(base, seat, start)
    # Late hires cannot be represented by the fixed hour-2 worker pool.
    late_hires = any(op and op[0] == "HIRE" for a in actions[seat][start + 2:start + 24]
                     for op in ((a or {}).get("market") or [])[:10])
    values = tile_values(initial, seat, jobs)
    plans = [] if late_hires else [(name, plan, locked, units) for name, plan in
                                   arrange(units, routes, jobs, frozen, sim.game["episode"] + start, rounds, locked, values)]
    if locked and not late_hires:
        plans += [("flex_" + name, plan, set(), units) for name, plan in
                  arrange(units, routes, jobs, frozen, sim.game["episode"] + start, rounds, (), values)]
    if not late_hires:
        plans += remove_any_worker(sim, initial, actions, start, units, routes, jobs, frozen)
    summary = dict(day=start // 24, jobs=len(jobs), hands=len(units) - 1, rejected=Counter(),
                   candidates=[], late_hires=late_hires)
    valid = [("baseline", base, actions, False)]
    quota = base["sold"]
    # Sales-only control isolates changed sale timing/order from physical routes.
    variants = [("sales_only", actions, True, None)]
    for name, plan, fixed, starts in plans:
        for delivery in ("recorded", "early"):
            own = actions_for(actions[seat], start, plan, starts, jobs, delivery, fixed)
            if own is None:
                summary["rejected"]["route_over_24"] += 1
                continue
            pair = list(actions)
            pair[seat] = own
            if delivery == "early":
                variants.append((name + ":deliver_wait", pair, False, None))
                variants.append((name + ":" + delivery, pair, "delivery", OUTPUTS))
                for p in ("MILK", "WOOL", "MELON", "STRAWBERRY"):
                    if any(any(delta.get(p, 0) > 0 for delta in j.deltas) for j in jobs):
                        variants.append((name + ":early_" + p, pair, "delivery", {p}))
            else:
                variants.append((name + ":" + delivery, pair, False, None))
    sim.reference_actions = actions
    seen = set()
    for name, pair, advance, items in variants:
        digest = sha256(json.dumps([pair[seat][start:start + 24], advance, sorted(items or [])], sort_keys=True).encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        trial = sim.run(initial, start, stop, pair, advance=advance, quota=quota,
                        reference=base if advance == "delivery" else None, advance_items=items)
        reason = equivalent(base, trial, seat)
        if reason:
            summary["rejected"][reason] += 1
            continue
        valid.append((name, trial, pair, advance))
    base_ec = economic(base["events"], seat)
    baseline_forecasts = [forecast_value(initial, base["events"], seat, scale) for scale in (0, 1, 2)]
    records = []
    for name, trial, pair, advance in valid:
        ec = economic(trial["events"], seat)
        gain = trial["money"][seat] - base["money"][seat]
        wage = base_ec["spend"].get("HIRE", 0) - ec["spend"].get("HIRE", 0)
        forecast = [forecast_value(initial, trial["events"], seat, scale) - b
                    for scale, b in zip((0, 1, 2), baseline_forecasts)]
        revenue = sum(ec["revenue"].values()) - sum(base_ec["revenue"].values())
        other = sum(base_ec["spend"].values()) - sum(ec["spend"].values()) - wage
        assert gain == wage + revenue + other
        row = dict(name=name, gain=gain, wage=wage, revenue=revenue, input_saving=other,
                   forecast=statistics.mean(forecast), robust=min(forecast), advance=advance,
                   sold=ec["units"], opponent_gain=trial["money"][1 - seat] - base["money"][1 - seat])
        row["same_sale_schedule"] = Counter((t, s, op, p) for t, s, op, p, _ in trial["events"] if s == seat and op == "SELL") == Counter(
            (t, s, op, p) for t, s, op, p, _ in base["events"] if s == seat and op == "SELL")
        records.append(row)
    # Baseline first wins ties. Wage-only ranks staffing savings with original
    # sale timing; oracle measures the best tested candidate, not a true ceiling.
    selections = {
        "wage": max(range(len(records)), key=lambda i: records[i]["wage"] if not records[i]["advance"] and records[i]["same_sale_schedule"] else -1e9),
        "early": next((i for i, r in enumerate(records) if r["name"] == "sales_only"), 0),
        "forecast": max(range(len(records)), key=lambda i: records[i]["forecast"] if records[i]["name"] != "sales_only" else -1e9),
        "robust": max(range(len(records)), key=lambda i: records[i]["robust"] if records[i]["name"] != "sales_only" else -1e9),
        "oracle": max(range(len(records)), key=lambda i: records[i]["gain"] if records[i]["name"] != "sales_only" else -1e9),
    }
    for family in ("distance", "tile_value"):
        selections[family] = max(range(len(records)), key=lambda i:
                                 records[i]["forecast"] if i == 0 or family in records[i]["name"] else -1e9)
    summary["candidates"] = records
    summary["selected"] = {k: records[i] for k, i in selections.items()}
    summary["rejected"] = dict(summary["rejected"])
    return base, valid, selections, summary


def load_game(path):
    game = json.load(gzip.open(path, "rt", encoding="utf-8"))
    actions = [None, None]
    actions[game["seat"]] = game["our_actions"]
    actions[1 - game["seat"]] = game["opp_actions"]
    return game, actions


def run_game(path, rounds=80, days=None, chain=False):
    game, actions = load_game(path)
    t0 = time.perf_counter()
    selected_days = days or list(range(3, 28, 2))
    with Simulator(game) as sim:
        original = sim.run(sim.initial, 0, 719, actions, snapshots=True)
        assert original["money"] == game["rewards"], (game["episode"], original["money"], game["rewards"])
        rows = []
        for day in selected_days:
            start, stop = day * 24, (day + 2) * 24
            _, _, _, row = block(sim, original["snapshots"][start], actions, start, stop, rounds)
            rows.append(row)
        chained = {}
        if chain:
            # Chaining re-extracts from each arm's CURRENT state and validates
            # against that state's unchanged-tape continuation. No summing of
            # independent counterfactuals is presented as an actual season gain.
            for mode in ("wage", "forecast", "oracle"):
                state, cursor, all_events, choices = sim.initial, 0, [], []
                for day in selected_days:
                    start, stop = day * 24, (day + 2) * 24
                    if cursor < start:
                        result = sim.run(state, cursor, start, actions)
                        state = result["state"]
                        all_events += result["events"]
                    _, valid, selections, row = block(sim, state, actions, start, stop, rounds)
                    choice = valid[selections[mode]]
                    state = choice[1]["state"]
                    all_events += choice[1]["events"]
                    choices.append(row["selected"][mode])
                    cursor = stop
                result = sim.run(state, cursor, 719, actions)
                all_events += result["events"]
                ec = economic(all_events, game["seat"])
                assert result["money"][game["seat"]] == 3000 + sum(ec["revenue"].values()) - sum(ec["spend"].values())
                chained[mode] = dict(final=result["money"], gain=result["money"][game["seat"]] - game["rewards"][game["seat"]],
                                     economics=ec, choices=choices,
                                     final_contract=equivalent(original, dict(result, events=all_events), game["seat"]))
        baseline_ec = economic(original["events"], game["seat"])
        assert original["money"][game["seat"]] == 3000 + sum(baseline_ec["revenue"].values()) - sum(baseline_ec["spend"].values())
    return dict(episode=game["episode"], seat=game["seat"], submission=game.get("submission"), opponent=game.get("opponent"),
                source=str(Path(path).relative_to(ROOT)), source_sha256=sha256(Path(path).read_bytes()).hexdigest(),
                baseline=game["rewards"], baseline_economics=baseline_ec,
                blocks=rows, chained=chained, seconds=time.perf_counter() - t0)


def summarize(rows):
    results = {}
    for mode in ("wage", "early", "distance", "tile_value", "forecast", "robust", "oracle"):
        totals = [sum(b["selected"][mode]["gain"] for b in r["blocks"]) for r in rows]
        rng = random.Random(421)
        boots = sorted(statistics.mean(rng.choices(totals, k=len(totals))) for _ in range(4000))
        results[mode] = dict(mean_opportunity=statistics.mean(totals), median=statistics.median(totals),
                             minimum=min(totals), maximum=max(totals),
                             episode_bootstrap_95=[boots[100], boots[3899]],
                             wage=statistics.mean(sum(b["selected"][mode]["wage"] for b in r["blocks"]) for r in rows),
                             revenue=statistics.mean(sum(b["selected"][mode]["revenue"] for b in r["blocks"]) for r in rows),
                             positive_blocks=sum(b["selected"][mode]["gain"] > 0 for r in rows for b in r["blocks"]),
                             negative_blocks=sum(b["selected"][mode]["gain"] < 0 for r in rows for b in r["blocks"]))
    for mode in ("wage", "forecast", "oracle"):
        seq = [r["chained"][mode] for r in rows if mode in r["chained"]]
        if seq:
            results[mode]["chained"] = dict(n=len(seq), mean_gain=statistics.mean(r["gain"] for r in seq),
                                            min_gain=min(r["gain"] for r in seq), max_gain=max(r["gain"] for r in seq),
                                            final_contract_failures=sum(r["final_contract"] is not None for r in seq))
    return dict(episodes=len(rows), blocks=sum(len(r["blocks"]) for r in rows), selectors=results,
                rejections=dict(sum((Counter(b["rejected"]) for r in rows for b in r["blocks"]), Counter())),
                valid_candidates=sum(len(b["candidates"]) - 1 for r in rows for b in r["blocks"]),
                total_seconds=sum(r["seconds"] for r in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--rounds", type=int, default=80)
    parser.add_argument("--days", help="Comma-separated zero-based days (3..27); disjoint 48-hour windows.")
    parser.add_argument("--chain", action="store_true")
    parser.add_argument("--tag", default="pilot")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--panel", default="data/ladder_panel", help="Folder of subfolders containing compact tapes.")
    args = parser.parse_args()
    paths = sorted((ROOT / args.panel).glob("*/*.json.gz"))
    # Deduplicate whole episodes across submission folders before splitting.
    paths = list({p.stem.split('.')[0]: p for p in paths}.values())
    random.Random(20260921).shuffle(paths)
    paths = paths[args.offset:args.offset + args.count]
    days = [int(d) for d in args.days.split(",")] if args.days else None
    if days:
        assert days == sorted(set(days)) and all(3 <= d <= 27 for d in days)
        assert all(b - a >= 2 for a, b in zip(days, days[1:]))
    folder = OUT / args.tag
    folder.mkdir(parents=True, exist_ok=True)
    manifest = dict(arguments=vars(args), paths=[str(p.relative_to(ROOT)) for p in paths],
                    script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                    engine_sha256=sha256(Path(engine().__file__).read_bytes()).hexdigest(),
                    information="Fixed hindsight daily production jobs; all selectors use hindsight feasibility validation. Only oracle ranks by future realized profit.")
    manifest_path = folder / "manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        assert old == manifest, "Frozen experiment differs; choose a new --tag."
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2))
    rows = []
    pending = []
    for path in paths:
        target = folder / (path.name.split('.')[0] + ".json")
        if target.exists():
            rows.append(json.loads(target.read_text()))
        else:
            pending.append(path)
    def save(row):
        rows.append(row)
        (folder / f"{row['episode']}.json").write_text(json.dumps(row, indent=2))
        print(json.dumps(dict(episode=row["episode"], seconds=round(row["seconds"], 2),
                              gains={m: sum(b["selected"][m]["gain"] for b in row["blocks"])
                                     for m in ("wage", "early", "forecast", "oracle")})), flush=True)
    if args.workers > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_game, str(p), args.rounds, days, args.chain) for p in pending]
            for future in as_completed(futures):
                save(future.result())
    else:
        for path in pending:
            save(run_game(str(path), args.rounds, days, args.chain))
    summary = summarize(rows)
    (folder / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

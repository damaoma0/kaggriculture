"""Coordinate-free batch placement for the DSM semantic tile-plan experiment.

The caller owns the chronological occupancy/release ledger.  This module sees
only today's public/synthetic state, today's requested species, and explicitly
available tile IDs.  It never receives a future reference board or episode ID.

``assign_tiles(day, requests, available_tiles, state, config=None)`` returns one
tile per request, in the input order.  Requests are already expanded to count=1
and can be species strings or dictionaries with kind/crop/animal/species.  State
is a tile -> dict mapping; released_kind identifies the occupant just released.
All 100 tiles are legitimate planting sites, including the four shed squares.

The deterministic objective combines modest service-distance cost, reuse of a
released same-species site, compact same-day cohorts, and weak sector workload
balance.  Greedy starts followed by exact improving reassignment/swap moves
minimize that objective; this is a heuristic, not a claim of route optimality.
"""

from collections import defaultdict


VARIANTS = {
    "distance": dict(distance=1.0, cluster=0.0, balance=0.0, reuse=0.0,
                     fertilizer=0.0, anchor=0.0, starts=1, rounds=1),
    "cohort": dict(distance=0.6, cluster=1.2, balance=0.10, reuse=1.5,
                   fertilizer=0.12, anchor=0.35, starts=3, rounds=4),
    "reuse": dict(distance=0.35, cluster=0.8, balance=0.08, reuse=4.0,
                  fertilizer=0.08, anchor=0.25, starts=3, rounds=4),
}

# Approximate daily visits, not predicted cash or information from DSM upkeep.
SERVICE = {"WHEAT": .85, "CARROT": 1.0, "MELON": .65,
           "STRAWBERRY": .70, "TOMATO": .90, "GOOSE": 1.15,
           "COW": 1.15, "SHEEP": 1.15, "COOP": 1.0, "PASTURE": 1.0}
CROPS = {"WHEAT", "CARROT", "MELON", "STRAWBERRY", "TOMATO"}
ANIMALS = {"GOOSE", "COW", "SHEEP"}
DIST = tuple(tuple(abs(a % 10 - b % 10) + abs(a // 10 - b // 10)
                   for b in range(100)) for a in range(100))
SHED_DISTANCE = tuple(min(DIST[t][s] for s in (44, 45, 54, 55))
                      for t in range(100))
SECTOR = tuple((t % 10 >= 5) + 2 * (t // 10 >= 5) for t in range(100))


def _kind(value):
    if isinstance(value, str):
        return value.upper()
    if not isinstance(value, dict):
        return ""
    return str(value.get("crop") or value.get("animal") or value.get("species")
               or value.get("kind") or "").upper()


def _birth(value, default=-99):
    if not isinstance(value, dict):
        return default
    for k in ("planted_day", "placed_day", "birth_day", "birth"):
        if value.get(k) is not None:
            return int(value[k])
    return default


def _config(config):
    if config is None:
        return dict(VARIANTS["cohort"])
    if isinstance(config, str):
        return dict(VARIANTS[config])
    result = dict(VARIANTS[config.get("variant", "cohort")])
    result.update(config)
    # Accept explicit weight suffixes without forcing the caller's naming.
    for key in ("distance", "cluster", "balance", "reuse", "fertilizer", "anchor"):
        if key + "_w" in config:
            result[key] = float(config[key + "_w"])
    return result


def assign_tiles(day, requests, available_tiles, state, config=None):
    """Return a feasible distinct assignment aligned with expanded requests.

    Available slots are a hard constraint; no live tile is freed here.  Raises
    ValueError if there are too few slots, duplicate slots, or malformed inputs.
    The input objects are not mutated.  Reproducible irrespective of input dict
    insertion order.  ``return_details`` optionally returns (tiles, diagnostics).
    """
    cfg = _config(config)
    slots = sorted(int(t) for t in available_tiles)
    if len(slots) != len(set(slots)) or any(t < 0 or t >= 100 for t in slots):
        raise ValueError("available_tiles must contain distinct tile IDs 0..99")
    if len(slots) < len(requests):
        raise ValueError("insufficient available tiles for requested cohort counts")
    kinds = [_kind(r) for r in requests]
    if any(not k for k in kinds):
        raise ValueError("each request must identify a crop, animal, or structure")
    if any(isinstance(r, dict) and int(r.get("count", 1)) != 1 for r in requests):
        raise ValueError("requests must be expanded to count=1")
    if not requests:
        return ([], {"objective": 0.0}) if cfg.get("return_details") else []
    state = {int(t): s for t, s in state.items()}
    slotset = set(slots)
    n = len(requests)
    loads = [SERVICE.get(k, .8) for k in kinds]
    groups = defaultdict(list)
    for i, k in enumerate(kinds):
        groups[k].append(i)
    peers = [tuple(j for j in groups[k] if j != i) for i, k in enumerate(kinds)]
    pairweight = [float(cfg["cluster"]) / max(1, len(groups[k]) - 1) for k in kinds]
    pens = sorted(t for t, s in state.items() if t not in slotset and _kind(s) in ANIMALS)
    baseload = [0.0] * 4
    anchors = defaultdict(list)
    for t, s in state.items():
        if t in slotset:
            continue
        k = _kind(s)
        if k in SERVICE:
            baseload[SECTOR[t]] += SERVICE[k]
        if _birth(s) == int(day):
            anchors[k].append(t)

    # Linear costs use only the current state.  Plant slots released today retain
    # their old species in released_kind, permitting local harvest/replant chains.
    linear = []
    for i, k in enumerate(kinds):
        row = {}
        for t in slots:
            s = state.get(t) or {}
            released = str(s.get("released_kind") or "").upper() if isinstance(s, dict) else ""
            cost = float(cfg["distance"]) * loads[i] * SHED_DISTANCE[t]
            if released == k:
                cost -= float(cfg["reuse"])
            if k in CROPS and pens:
                cost += float(cfg["fertilizer"]) * min(DIST[t][p] for p in pens)
            if anchors[k]:
                near = sorted(DIST[t][a] for a in anchors[k])[:2]
                cost += float(cfg["anchor"]) * sum(near) / len(near)
            row[t] = cost
        linear.append(row)

    # A small normalized quadratic load term discourages concentrating every new
    # job in one already-busy sector.  Exact route labor remains the executor's job.
    balance_w = float(cfg["balance"]) / max(1.0, (sum(baseload) + sum(loads)) / 4)

    def objective(a):
        value = sum(linear[i][t] for i, t in enumerate(a))
        for ids in groups.values():
            for ii, i in enumerate(ids):
                value += pairweight[i] * sum(DIST[a[i]][a[j]] for j in ids[ii + 1:])
        sectors = list(baseload)
        for i, t in enumerate(a):
            sectors[SECTOR[t]] += loads[i]
        return value + balance_w * sum(x * x for x in sectors)

    orders = [sorted(range(n), key=lambda i: (-loads[i], -len(groups[kinds[i]]), kinds[i], i)),
              sorted(range(n), key=lambda i: (len(groups[kinds[i]]), -loads[i], kinds[i], i)),
              list(range(n))]
    unique_orders = []
    for order in orders:
        if order not in unique_orders:
            unique_orders.append(order)
    best, bestvalue = None, float("inf")
    evaluations = 0
    for order in unique_orders[:max(1, int(cfg.get("starts", 3)))]:
        a = [None] * n
        free = set(slots)
        sectors = list(baseload)
        for i in order:
            def insertion(t):
                q, load = SECTOR[t], loads[i]
                return (linear[i][t]
                        + pairweight[i] * sum(DIST[t][a[j]] for j in peers[i] if a[j] is not None)
                        + balance_w * (2 * sectors[q] * load + load * load), t)
            t = min(free, key=insertion)
            a[i] = t
            free.remove(t)
            sectors[SECTOR[t]] += loads[i]
        # Coordinate descent examines all empty slots, then swaps between species.
        # Deltas are exact for this objective and require only same-cohort peers.
        for _ in range(max(0, int(cfg.get("rounds", 4)))):
            changed = False
            for i in order:
                old, qo, load = a[i], SECTOR[a[i]], loads[i]
                oldpair = sum(DIST[old][a[j]] for j in peers[i])
                def replace_delta(t):
                    qn = SECTOR[t]
                    d = linear[i][t] - linear[i][old]
                    d += pairweight[i] * (sum(DIST[t][a[j]] for j in peers[i]) - oldpair)
                    if qo != qn:
                        d += balance_w * (2 * load * (sectors[qn] - sectors[qo]) + 2 * load * load)
                    return d
                choices = [(replace_delta(t), t) for t in sorted(free)]
                evaluations += len(choices)
                if choices:
                    delta, new = min(choices)
                    if delta < -1e-9:
                        a[i] = new
                        free.remove(new)
                        free.add(old)
                        sectors[qo] -= load
                        sectors[SECTOR[new]] += load
                        changed = True
            for i in range(n):
                for j in range(i + 1, n):
                    if kinds[i] == kinds[j]:
                        continue
                    x, y = a[i], a[j]
                    delta = linear[i][y] + linear[j][x] - linear[i][x] - linear[j][y]
                    delta += pairweight[i] * sum(DIST[y][a[k]] - DIST[x][a[k]] for k in peers[i])
                    delta += pairweight[j] * sum(DIST[x][a[k]] - DIST[y][a[k]] for k in peers[j])
                    qx, qy = SECTOR[x], SECTOR[y]
                    dl = loads[j] - loads[i]
                    if qx != qy:
                        delta += balance_w * (2 * dl * (sectors[qx] - sectors[qy]) + 2 * dl * dl)
                    evaluations += 1
                    if delta < -1e-9:
                        a[i], a[j] = y, x
                        sectors[qx] += dl
                        sectors[qy] -= dl
                        changed = True
            if not changed:
                break
        value = objective(a)
        if (value, tuple(a)) < (bestvalue, tuple(best or [101] * n)):
            best, bestvalue = list(a), value
    if cfg.get("return_details"):
        return best, {"objective": bestvalue, "evaluations": evaluations,
                      "variant": cfg.get("variant", "custom"), "requests": n,
                      "available": len(slots)}
    return best


# The interface name requested in the initial design discussion.
allocate = assign_tiles

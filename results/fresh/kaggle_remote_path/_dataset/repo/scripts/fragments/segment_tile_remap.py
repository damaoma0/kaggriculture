"""Portable coordinate remapping for a recorded three-day segment node.

Only tile identity is transferred.  Worker positions, routes, shop history and
donor actions are intentionally absent from this helper.
"""
from copy import deepcopy


def _tile(farm, pos):
    try:
        x, y = int(pos[0]), int(pos[1])
        rows = farm.get("tiles", [])
        return rows[y][x]
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def _coords(farm):
    return [(x, y) for y, row in enumerate(farm.get("tiles", []))
            for x, _ in enumerate(row)]


def _same_day(a, b, key):
    return a.get(key) == b.get(key)


def _matches(donor, live):
    if donor is None:
        return live is None
    if donor == "LOCKED":
        return live == "LOCKED"
    if donor == "WEED":
        return live == "WEED" or (isinstance(live, dict) and live.get("kind") == "WEED")
    if not isinstance(donor, dict) or not isinstance(live, dict):
        return donor == live
    dk, lk = donor.get("kind"), live.get("kind")
    if dk != lk:
        return False
    if dk == "WEED":
        return True
    if donor.get("crop") is not None and donor.get("crop") != live.get("crop"):
        return False
    if donor.get("animal") is not None and donor.get("animal") != live.get("animal"):
        return False
    if dk in ("PLANT", "COOP", "PASTURE"):
        # Empty structures remain empty; an incumbent animal is never replaced.
        if dk in ("COOP", "PASTURE") and bool(donor.get("animal")) != bool(live.get("animal")):
            return False
        for key in ("planted_day", "placed_day"):
            if key in donor and not _same_day(donor, live, key):
                return False
    return True


def _farm_from_observation(observation):
    player = int(observation.get("player", 0))
    return observation["farms"][player]


def _ss_remap(observation, node):
    """Return a deep-cloned node remapped to the live farm, or ``None``.

    The donor-to-live assignment covers every coordinate referenced by a job,
    is one-to-one, and is reused for all jobs in the three-day window.
    """
    if not isinstance(node, dict) or not isinstance(observation, dict):
        return None
    try:
        live_farm = _farm_from_observation(observation)
        donor_farm = node["start_farm"]
        jobs = node.get("jobs", [])
    except (KeyError, TypeError, ValueError):
        return None
    donor_positions = set()
    for job in jobs:
        try:
            pos = job.get("tile")
            if pos is not None:
                donor_positions.add((int(pos[0]), int(pos[1])))
        except (AttributeError, TypeError, ValueError):
            return None
    candidates = {}
    for dpos in sorted(donor_positions, key=lambda p: (p[1], p[0])):
        dtile = _tile(donor_farm, dpos)
        candidates[dpos] = [lpos for lpos in _coords(live_farm)
                            if _matches(dtile, _tile(live_farm, lpos))]
        if not candidates[dpos]:
            return None
    # Constrain the scarce identities first, then choose nearest coordinates.
    order = sorted(donor_positions, key=lambda p: (len(candidates[p]), p[1], p[0]))
    used = set(); mapping = {}
    for dpos in order:
        options = [p for p in candidates[dpos] if p not in used]
        if not options:
            return None
        chosen = min(options, key=lambda p: (abs(p[0] - dpos[0]) + abs(p[1] - dpos[1]), p[1], p[0]))
        mapping[dpos] = chosen
        used.add(chosen)
    adapted = deepcopy(node)
    adapted["start_farm"] = deepcopy(live_farm)
    adapted.pop("start", None)  # any donor signature is stale after remapping
    for job in adapted.get("jobs", []):
        if job.get("tile") is not None:
            job["tile"] = list(mapping[(int(job["tile"][0]), int(job["tile"][1]))])
    adapted["_tile_remap"] = {f"{x},{y}": list(mapping[(x, y)]) for x, y in sorted(mapping)}
    adapted["_tile_remap_distance"] = sum(abs(x - mapping[(x, y)][0]) + abs(y - mapping[(x, y)][1])
                                           for x, y in mapping)
    return adapted


"""Extract compact, replay-backed three-day UMG continuation segments.

This is a historical library for state matching.  It is deliberately not a
route compiler: `portable_tile_jobs` omit movement and worker identities, and
the recorded 72-step action route is diagnostics only.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results" / "fresh" / "cumulative_planning"
OUT = ROOT / "results" / "fresh" / "segment_stitch"
SUBMISSION = 56266758
DAYS = (12, 15, 18, 21, 24, 27)
TILE_OPS = {"PLANT", "HARVEST", "WATER", "FEED", "CARE", "FERTILIZE", "BUILD_COOP",
            "BUILD_PASTURE", "DIG", "PLACE", "COLLECT_FERTILIZER"}
RESOURCE_OPS = {"PICKUP", "DROP"}
MOVES = {"NORTH", "SOUTH", "EAST", "WEST", "PASS"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value):
    """JSON clone also prevents later accidental mutation of replay data."""
    return copy.deepcopy(value)


def native_snapshot(obs, seat):
    """Fields visible to a player at the segment start; excludes future town."""
    return {"step": obs.get("step"), "day": obs.get("day"), "hour": obs.get("hour"),
            "player": obs.get("player", seat), "farm": clean(obs["farms"][seat]),
            "private": clean(obs.get("private", {})), "market": clean(obs.get("market", {})),
            "shops_visible": clean(obs.get("town", {}).get("unlocked_shops", []))}


def end_snapshot(obs, seat):
    return {"step": obs.get("step"), "day": obs.get("day"), "hour": obs.get("hour"),
            "farm": clean(obs["farms"][seat]), "private": clean(obs.get("private", {}))}


def tile(obs, seat, pos):
    if pos is None:
        return None
    x, y = pos
    if not (0 <= x < 10 and 0 <= y < 10):
        return None
    return obs["farms"][seat]["tiles"][y][x]


def tile_signature(value):
    """Compact state comparison payload for a portable job, not a full tile clone."""
    if value is None: return "EMPTY"
    if value == "LOCKED": return "LOCKED"
    if not isinstance(value, dict):
        return str(value)
    keep = ("kind", "crop", "animal", "yield_units", "planted_day", "placed_day",
            "watered_today", "fed_today", "cared_today", "fertilizer_available",
            "fertilized_until_day", "pending_care_bonus", "consecutive_unfed")
    # A stable compact token avoids copying full per-tile objects for hundreds
    # of thousands of jobs; full farms remain in the node snapshots.
    return "|".join(f"{k}={value[k]}" for k in keep if k in value)


def actors(obs_step, action_step, seat):
    """Yield command and pre-action coordinate, without retaining worker id."""
    obs = obs_step[seat]["observation"]
    # Kaggle replay action at t+1 was issued from observation t.
    action = action_step[seat].get("action", {})
    farm = obs["farms"][seat]
    yield action.get("farmer", ["PASS"]), farm.get("farmer")
    for command, pos in zip(action.get("hands", []), farm.get("hands", [])):
        yield command, pos


def changed(before, after):
    return before != after


def semantic_success(op, before, after, hour):
    """State-delta success flag from raw snapshots (not inferred movement)."""
    # Daily resets can erase watered/fed/cared flags after an hour-23 command.
    # Retain a meaningful requested job as unresolved rather than calling it a
    # failed action from a lossy midnight snapshot.
    if hour == 23 and op in {"WATER", "FEED", "CARE", "FERTILIZE"}:
        return None if isinstance(before, dict) else False
    if before is None and after is None:
        return False
    if op == "PLANT":
        return isinstance(after, dict) and after.get("kind") == "PLANT" and changed(before, after)
    if op == "WATER":
        return isinstance(after, dict) and after.get("watered_today") is True and changed(before, after)
    if op == "FERTILIZE":
        return isinstance(after, dict) and changed(before, after)
    if op == "FEED":
        return isinstance(after, dict) and after.get("fed_today") is True and changed(before, after)
    if op == "CARE":
        return isinstance(after, dict) and changed(before, after)
    if op == "HARVEST":
        return isinstance(before, dict) and (before.get("kind") == "PLANT" or before.get("animal")) and changed(before, after)
    if op == "COLLECT_FERTILIZER":
        return isinstance(before, dict) and before.get("fertilizer_available") is True and changed(before, after)
    if op == "BUILD_COOP":
        return isinstance(after, dict) and after.get("kind") == "COOP" and changed(before, after)
    if op == "BUILD_PASTURE":
        return isinstance(after, dict) and after.get("kind") == "PASTURE" and changed(before, after)
    return changed(before, after)


def delta_inventory(before, after):
    b = before.get("private", {}).get("shed", {})
    a = after.get("private", {}).get("shed", {})
    return {k: a.get(k, 0) - b.get(k, 0) for k in sorted(set(a) | set(b)) if a.get(k, 0) != b.get(k, 0)}


def jobs_for_window(replay, seat, start_step, end_step):
    jobs, resources, route, per_day = [], [], [], defaultdict(Counter)
    for step_i in range(start_step, end_step):
        now = replay["steps"][step_i]
        after = replay["steps"][min(step_i + 1, len(replay["steps"]) - 1)]
        obs, next_obs = now[seat]["observation"], after[seat]["observation"]
        day = step_i // 24 - start_step // 24
        hour = step_i % 24
        route.append(clean(after[seat].get("action", {})))
        for cmd, pos in actors(now, after, seat):
            if not cmd:
                continue
            op = cmd[0]
            pre, post = tile(obs, seat, pos), tile(next_obs, seat, pos)
            if op in TILE_OPS:
                ok = semantic_success(op, pre, post, hour)
                job = {"day": day, "hour": hour, "tile": list(pos) if pos is not None else None,
                       "cmd": clean(cmd), "requested": True, "successful": ok,
                       "pre_tile": tile_signature(pre), "post_tile": tile_signature(post)}
                # Declared inputs/effects, not an attempt to reconstruct path logistics.
                if op == "PLANT" and len(cmd) > 1:
                    job["required_seed"] = {cmd[1]: 1}
                    if ok: per_day[day][cmd[1]] += 0  # explicit crop has no immediate output
                if op == "HARVEST" and ok is True and isinstance(pre, dict):
                    product = pre.get("crop") or {"GOOSE": "EGG", "COW": "MILK", "SHEEP": "WOOL"}.get(pre.get("animal"), "UNKNOWN")
                    job["effect"] = {product: pre.get("yield_units", 0)}
                    per_day[day][product] += pre.get("yield_units", 0)
                if op == "COLLECT_FERTILIZER" and ok is True:
                    job["effect"] = {"FERTILIZER": 1}
                    per_day[day]["FERTILIZER"] += 1
                jobs.append(job)
            elif op in RESOURCE_OPS:
                resources.append({"day": day, "hour": hour, "cmd": clean(cmd), "requested": True,
                                  "successful": bool(changed(pre, post)),
                                  "tile": list(pos) if pos is not None else None,
                                  "shed_delta_at_step": delta_inventory(obs, next_obs)})
    assert len(route) == end_step - start_step
    return jobs, resources, route, {str(k): dict(v) for k, v in per_day.items()}


def raw_map():
    paths = list((DATA / "raw_replays").glob("episode-*-replay.json"))
    return {int(p.name.split("-")[1]): p for p in paths}


def rich_games():
    found = []
    for path in (DATA / "dataset_train.json", DATA / "dataset_test.json"):
        data = read(path)
        found.extend(g for g in data["games"] if int(g.get("submission", -1)) == SUBMISSION)
    assert len(found) == 105, len(found)
    assert len({(g["episode"], g["seat"]) for g in found}) == 105
    return found, data["products"]


def segment_for(game, replay, products, day):
    seat = int(game["seat"])
    start, end = day * 24, min((day + 3) * 24, 719)
    assert len(replay["steps"]) == 720
    start_obs = replay["steps"][start][seat]["observation"]
    end_obs = replay["steps"][end][seat]["observation"]
    assert start_obs["day"] == day and start_obs["hour"] == 0
    jobs, resources, route, per_day = jobs_for_window(replay, seat, start, end)
    rich = game["segments"][day // 3]
    assert rich["days"][0] == day, (game["episode"], day, rich["days"])
    produced = {p: int(rich["output"].get(p, 0)) for p in products}
    start_state, end_state = native_snapshot(start_obs, seat), end_snapshot(end_obs, seat)
    # Flat, selector-facing node.  It contains no later shop information or raw routes.
    requested_counts = dict(Counter(j["cmd"][0] for j in jobs))
    # Keep requested jobs unless snapshots prove a no-op.  This avoids dropping
    # useful maintenance work at midnight where the daily reset masks success.
    portable_jobs = [j for j in jobs if j["successful"] is not False]
    successful_counts = dict(Counter(j["cmd"][0] for j in portable_jobs if j["successful"] is True))
    node = {"id": f"{game['episode']}:{seat}:d{day}", "episode": game["episode"], "seat": seat,
            "submission": SUBMISSION, "day": day, "span": 3,
            "start_farm": start_state["farm"], "start_private": start_state["private"],
            "start_market": start_state["market"], "start_shops": start_state["shops_visible"],
            "start_clock": {k: start_state[k] for k in ("step", "day", "hour", "player")},
            "end_farm": end_state["farm"], "end_private": end_state["private"],
            "end_clock": {k: end_state[k] for k in ("step", "day", "hour")},
            "output": produced, "planted": clean(rich.get("planted", {})),
            "jobs": portable_jobs, "requested_tilework_counts": requested_counts,
            "successful_tilework_counts": successful_counts, "resource_inputs": resources,
            "resource_cost": {k: sum(j.get("required_seed", {}).get(k, 0) for j in portable_jobs)
                              for k in products if any(k in j.get("required_seed", {}) for j in portable_jobs)},
            "daily_action_derived_output": per_day,
            "daily_action_output_note": "Harvest/fertilizer-only diagnostic; exact output is authoritative and includes animal production."}
    return node, route


def sum_daily_output(node, products):
    total = Counter()
    for values in node["daily_action_derived_output"].values():
        total.update(values)
    return {p: int(total[p]) for p in products}


def main():
    games, products = rich_games()
    raws = raw_map()
    OUT.mkdir(parents=True, exist_ok=True)
    entries, diagnostics, missing, audits = [], {}, [], []
    for game in games:
        ep = int(game["episode"])
        path = Path(game.get("source_raw", ""))
        if not path.exists():
            path = raws.get(ep)
        if path is None or not path.exists():
            missing.append({"episode": ep, "seat": game["seat"], "source_raw": game.get("source_raw")})
            continue
        replay = read(path)
        for day in DAYS:
            entry, route = segment_for(game, replay, products, day)
            expected = {p: int(game["segments"][day // 3]["output"].get(p, 0)) for p in products}
            assert entry["output"] == expected
            entries.append(entry)
            diagnostics[entry["id"]] = {"route_template_diagnostic": route}
            derived = sum_daily_output(entry, products)
            audits.append({"library_id": entry["id"], "serialized_rich_output_match": True,
                           "action_derived_output": derived,
                           "action_derived_matches_rich": derived == expected,
                           "jobs": len(entry["jobs"]), "route_steps": len(route)})
    manifest = {"schema_version": 1, "submission": SUBMISSION, "products": products, "days": list(DAYS),
                "requested_games": len(games), "segments": len(entries), "missing_raw": missing,
                "job_schema": {"day": "relative 0..2", "hour": "recorded 0..23", "tile": "[x,y] or null",
                               "cmd": "recorded command", "requested": "action was issued", "successful": "pre/post tile-state delta check"},
                "limitations": ["Portable jobs are historical coordinates and require current-state eligibility checks before use.",
                                "Route templates are separate diagnostics; they are not compiler-ready routes.",
                                "Start snapshots exclude later shop reveals.",
                                "Daily action-derived output excludes animal production; recorded_production is exact authoritative segment output."]}
    lib = {"schema_version": 1, "manifest": manifest, "segments": entries}
    # Stream the large library: building a second 100MB JSON string can exceed
    # the desktop worker memory limit even though the compact artifact itself
    # is valid and useful at runtime.
    library_path = OUT / "library.json"
    temporary = library_path.with_suffix(".json.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(lib, handle, separators=(",", ":"), ensure_ascii=False)
    (OUT / "route_template_diagnostics.json").write_text(json.dumps(diagnostics, separators=(",", ":")), encoding="utf-8")
    digest = hashlib.sha256()
    with temporary.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    manifest["library_sha256"] = digest.hexdigest()
    manifest["audit_sample"] = audits[:10]
    manifest["all_serialized_rich_output_matches"] = len(audits) == len(entries)
    manifest["action_derived_output_exact_matches"] = sum(a["action_derived_matches_rich"] for a in audits)
    manifest["action_derived_output_note"] = "Independent pre/post action reconstruction; mismatches are retained because daily refresh and ambiguous midnight effects are not silently imputed."
    temporary.replace(library_path)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"segments": len(entries), "missing": len(missing), "bytes": library_path.stat().st_size,
                      "jobs": sum(len(e["jobs"]) for e in entries)}))


if __name__ == "__main__":
    main()

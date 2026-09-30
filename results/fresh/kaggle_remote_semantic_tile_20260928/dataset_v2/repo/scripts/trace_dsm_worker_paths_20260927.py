"""Trace actual DSM worker actions, read-only replay of the 40 recorded worlds.

Outputs are deliberately separate from existing executor analyses.  The official
engine receives the saved actions of BOTH players; a wrapper around its unit-action
function observes immediate effects, before market processing or midnight refresh.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import upkeep_engine as UE

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "results/fresh/dsm_worker_paths_20260927"
PANEL = ROOT / "results/fresh/threads_20260928/panel_dsm40b.txt"
SELECTED = {112602061, 112604454}
MOVES = {"NORTH", "SOUTH", "EAST", "WEST"}
ANIMALS = {"GOOSE", "COW", "SHEEP"}
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}
LABELS = {"WH": "WHEAT", "CA": "CARROT", "TO": "TOMATO", "ST": "STRAWBERRY",
          "ME": "MELON", "GO": "GOOSE", "CO": "COW", "SH": "SHEEP",
          "WE": "WEED", "PA": "PASTURE", "CP": "COOP", "--": "EMPTY", "XX": "LOCKED"}
CODES = {v: k for k, v in LABELS.items()}
SCHEMA = {
    "event": ["hour", "xBefore", "yBefore", "requestedCommand", "tileBeforeCode",
              "immediateInventoryDeltaOrNull", "positionAfterUnitAction", "effect01"],
    "unit": "0 is farmer; 1..N are hands in hire order, reset each day",
    "day": "zero-based engine day; only days 11 through 28 are traced",
    "board": "100 morning tile codes, indexed y*10+x; events record the actual pre-action tile independently",
    "effect": "1 if immediate position/tile/inventory/shed/seeds/money changed; measured before market and midnight",
    "noops": "non-PASS requested actions with effect 0; PASS is idle, not a noop",
    "metrics": "work/move/shed/idle partition requested commands; effectiveWork and actualMoves require effect 1",
    "boundary": "719 action transitions (steps 0..718), 720 recorded states; official engine declares DONE at step 718",
}


def tile_code(tile):
    if tile is None:
        return "--"
    if tile == "LOCKED":
        return "XX"
    return CODES[tile.get("animal") or tile.get("crop") or tile["kind"]]


def category(command, position):
    op = command[0]
    if op in MOVES:
        return "move"
    if op == "PASS":
        return "idle"
    if op in ("PICKUP", "DROP") or (op == "PLACE" and tuple(position) in SHED
                                       and len(command) > 1 and command[1] not in ANIMALS):
        return "shed"
    return "work"


def normalize(command):
    return copy.deepcopy(command) if isinstance(command, list) and command else ["PASS"]


def delta(before, after):
    return {key: after.get(key, 0) - before.get(key, 0)
            for key in sorted(set(before) | set(after)) if after.get(key, 0) != before.get(key, 0)} or None


def noop_reason(command, allowed, tile, inventory, before_pos):
    op = command[0]
    if command != allowed:
        return "engine_replaced_command_atomic_seed_check"
    if op in MOVES:
        return "move_outside_board"
    if op == "WATER" and isinstance(tile, dict) and tile.get("watered_today"):
        return "already_watered_today"
    if op == "FEED":
        if isinstance(tile, dict) and tile.get("fed_today"):
            return "already_fed_today"
        if not inventory.get("WHEAT"):
            return "no_carried_wheat"
    if op == "CARE" and isinstance(tile, dict) and tile.get("cared_today"):
        return "already_cared_today"
    if op == "COLLECT_FERTILIZER" and isinstance(tile, dict) and not tile.get("fertilizer_available"):
        return "no_fertilizer_available"
    if op == "HARVEST" and (not isinstance(tile, dict) or not tile.get("yield_units")):
        return "no_yield"
    if op == "FERTILIZE" and not inventory.get("FERTILIZER"):
        return "no_carried_fertilizer"
    if op in ("DROP", "PICKUP") and tuple(before_pos) not in SHED:
        return "not_at_shed"
    return "no_immediate_state_change"


def route_metrics(worker):
    events = worker["events"]
    metrics = Counter({key: 0 for key in ("work", "move", "shed", "idle", "noops", "effectiveWork", "actualMoves")})
    ops = Counter()
    work_positions = []
    work_hours = []
    stations = []
    for e in events:
        h, x, y, cmd, _, _, end_pos, effect = e
        kind = category(cmd, (x, y))
        metrics[kind] += 1
        ops[cmd[0]] += 1
        metrics["noops"] += int(cmd[0] != "PASS" and effect == 0)
        metrics["effectiveWork"] += int(kind == "work" and effect == 1)
        metrics["actualMoves"] += int([x, y] != end_pos)
        if kind == "work":
            work_positions.append((x, y))
            work_hours.append(h)
            if stations and stations[-1][0] == y * 10 + x and stations[-1][2] == h - 1:
                stations[-1][2] = h
                stations[-1][3] += 1
            else:
                stations.append([y * 10 + x, h, h, 1])
    metrics["present"] = len(events)
    metrics["uniqueWorkTiles"] = len(set(work_positions))
    metrics["workVisits"] = len(stations)
    metrics["lastWorkHour"] = max(work_hours) if work_hours else -1
    metrics["firstWorkHour"] = min(work_hours) if work_hours else -1
    metrics["tailIdle"] = sum(e[0] > metrics["lastWorkHour"] and e[3][0] == "PASS" for e in events)
    worker["metrics"] = dict(metrics)
    worker["ops"] = dict(ops)
    worker["stations"] = stations  # [tile, firstHour, lastHour, consecutiveWorkCommands]
    assert len(events) == 24 - worker["startHour"], (worker["unit"], worker["startHour"], len(events))
    assert [e[0] for e in events] == list(range(worker["startHour"], 24))
    assert metrics["present"] == sum(metrics[k] for k in ("work", "move", "shed", "idle"))


def trace_world(game):
    team, episode = map(int, game.split(":"))
    tape = UE.load_tape(team, episode)
    engine = UE.engine()
    world = UE.World(tape["seed"], tape["shops"])
    seat = tape["seat"]
    days = []
    noops = []
    context = {}
    original_apply = engine._apply_unit_action
    action_count = len(tape["actions"])
    assert action_count == len(tape["opp_actions"]) == 719

    def observed_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity=100):
        if not context or farm is not context["farm"] or idx not in context["workers"]:
            return original_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
        p0 = list(engine._farmer_position(farm, idx))
        tile0 = copy.deepcopy(farm["tiles"][p0[1]][p0[0]])
        inv0 = dict(engine._farmer_inventory(private, idx))
        shed0, seeds0 = dict(private["shed"]), dict(private["seeds"])
        money0 = farm["money"]
        command = context["commands"][idx]
        result = original_apply(farm, private, idx, action, board_size, day, turns_per_day, shed_capacity)
        p1 = list(engine._farmer_position(farm, idx))
        inv1 = engine._farmer_inventory(private, idx)
        effect = int(p1 != p0 or farm["tiles"][p0[1]][p0[0]] != tile0 or inv1 != inv0
                     or private["shed"] != shed0 or private["seeds"] != seeds0 or farm["money"] != money0)
        event = [context["hour"], *p0, command, tile_code(tile0), delta(inv0, inv1), p1, effect]
        context["workers"][idx]["events"].append(event)
        if command[0] != "PASS" and not effect:
            noops.append({"episode": episode, "day": day, "unit": idx, "hour": context["hour"],
                          "command": command, "position": p0, "target": tile_code(tile0),
                          "reason": noop_reason(command, action, tile0, inv0, p0)})
        return result

    engine._apply_unit_action = observed_apply
    workers = None
    try:
        for step in range(action_count):
            day, hour = divmod(step, 24)
            own = UE.tape_action(tape["actions"], step)
            if 11 <= day <= 28:
                farm = world.farms[seat]
                if hour == 0:
                    workers = {}
                    days.append({"day": day, "board": [tile_code(t) for row in farm["tiles"] for t in row],
                                 "workers": workers})
                unit_count = 1 + len(farm["hands"])
                raw_hands = own.get("hands") if isinstance(own.get("hands"), list) else []
                commands = [normalize(own.get("farmer"))] + [normalize(raw_hands[i]) if i < len(raw_hands)
                                                             else ["PASS"] for i in range(unit_count - 1)]
                # Explicit missing PASS commands are behavior-identical; they let the hook account for every worker hour.
                own["farmer"] = commands[0]
                own["hands"] = commands[1:] + raw_hands[unit_count - 1:]
                for unit in range(unit_count):
                    workers.setdefault(unit, {"unit": unit, "startHour": hour, "events": []})
                context.update(farm=farm, workers=workers, commands=commands, hour=hour)
            else:
                context.clear()
            actions = [None, None]
            actions[seat], actions[1 - seat] = own, UE.tape_action(tape["opp_actions"], step)
            world.step(actions)
    finally:
        engine._apply_unit_action = original_apply
    actual = [float(f["money"]) for f in world.farms]
    expected = [float(v) for v in tape["rewards"]]
    terminal = [s.status for s in world.state]
    verified = {"ok": actual == expected and terminal == ["DONE", "DONE"], "actual": actual,
                "recorded": expected, "actionSteps": action_count, "terminal": terminal}
    for day in days:
        day["workers"] = list(day["workers"].values())
        for worker in day["workers"]:
            route_metrics(worker)
    assert verified["ok"], (episode, verified)
    return {"episode": episode, "team": team, "seat": seat, "verified": verified, "days": days}, noops


def aggregate(worlds):
    groups = {"hands": {"totals": Counter(), "ops": Counter()}, "farmer": {"totals": Counter(), "ops": Counter()}}
    per_world = []
    keys = ("work", "move", "shed", "idle", "noops", "effectiveWork", "actualMoves", "present",
            "uniqueWorkTiles", "workVisits", "tailIdle")
    for world in worlds:
        local = {group: Counter() for group in groups}
        for day in world["days"]:
            for worker in day["workers"]:
                group = "farmer" if worker["unit"] == 0 else "hands"
                values = {key: worker["metrics"][key] for key in keys}
                values["workerDays"] = 1
                values["workingWorkerDays"] = int(worker["metrics"]["work"] > 0)
                groups[group]["totals"].update(values)
                groups[group]["ops"].update(worker["ops"])
                local[group].update(values)
        per_world.append({"episode": world["episode"], **local})
    for group in groups.values():
        c = group["totals"]
        group["perWorld"] = {key: round(val / len(worlds), 4) for key, val in c.items()}
        group["perWorkerDay"] = {key: round(val / c["workerDays"], 4) for key, val in c.items()}
        group["workPerVisit"] = round(c["work"] / c["workVisits"], 4)
        group["movesPerWork"] = round(c["move"] / c["work"], 4)
    return groups, per_world


def save_new(path, payload):
    with path.open("x", encoding="utf-8") as file:
        json.dump(payload, file, separators=(",", ":"), ensure_ascii=False)
    return path.stat().st_size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in ("traces.json", "summary.json", "viewer_data.json"):
        if (args.out / name).exists():
            raise SystemExit(f"Refusing to overwrite {args.out / name}")
    games = PANEL.read_text(encoding="utf-8").replace(",", " ").split()
    assert len(games) == 40 and len(set(games)) == 40
    started = time.perf_counter()
    worlds, noops = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for world, errors in pool.map(trace_world, games):
            worlds.append(world)
            noops.extend(errors)
            print(f"verified {world['episode']} {world['verified']['actual']} days={len(world['days'])} noops={len(errors)}", flush=True)
    groups, per_world = aggregate(worlds)
    common = {"schema": SCHEMA, "labels": LABELS}
    size_traces = save_new(args.out / "traces.json", {**common, "worlds": worlds})
    viewer_worlds = [w for w in worlds if w["episode"] in SELECTED]
    size_viewer = save_new(args.out / "viewer_data.json", {**common, "worlds": viewer_worlds})
    summary = {**common, "worldCount": len(worlds), "verifiedCount": sum(w["verified"]["ok"] for w in worlds),
               "verification": [{"episode": w["episode"], **w["verified"]} for w in worlds],
               "groups": groups, "perWorld": per_world, "noops": noops,
               "noopReasons": dict(Counter(e["reason"] for e in noops)),
               "files": {"tracesBytes": size_traces, "viewerBytes": size_viewer},
               "seconds": round(time.perf_counter() - started, 2),
               "provenance": {"panel": str(PANEL), "engine": str(UE.ENGINE_PATH),
                              "engineSHA256": hashlib.sha256(UE.ENGINE_PATH.read_bytes()).hexdigest(),
                              "scriptSHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    save_new(args.out / "summary.json", summary)
    print(json.dumps({"worlds": len(worlds), "verified": summary["verifiedCount"], "seconds": summary["seconds"],
                      "tracesBytes": size_traces, "viewerBytes": size_viewer, "handsPerWorld": groups["hands"]["perWorld"],
                      "farmerPerWorld": groups["farmer"]["perWorld"], "noopReasons": summary["noopReasons"]}), flush=True)


if __name__ == "__main__":
    main()

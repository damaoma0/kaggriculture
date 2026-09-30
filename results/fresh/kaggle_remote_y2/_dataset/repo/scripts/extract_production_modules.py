"""Extract short, completed midgame crop modules from leader replay snapshots.

The output is intentionally replay-derived: an event is kept only when the next
snapshot shows the command's tile-local effect.  This makes `requested` (the
leader command) distinct from `executed` (the observed effect) without relying
on a future shop unlock or a substitute agent.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAYS = ROOT / "data" / "leaders_20260917"
AGENTS = ROOT / "results" / "fresh" / "leader_segments" / "episode_agents.json"
OUT = ROOT / "results" / "fresh" / "production_modules" / "extracted.json"
LEADERS = {"56266758": "UMG56266758", "56216119": "Majkel56216119"}
CROPS = {"WHEAT", "CARROT", "TOMATO"}


def tile_at(obs, pos):
    if not pos:
        return None
    x, y = pos
    rows = obs["farms"][obs["player"]]["tiles"]
    return rows[y][x] if 0 <= y < len(rows) and 0 <= x < len(rows[y]) else None


def crop(tile):
    return tile.get("crop") if isinstance(tile, dict) and tile.get("kind") == "PLANT" else None


def crop_state(tile):
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return None
    return {k: tile.get(k) for k in ("crop", "planted_day", "yield_units", "watered_today",
                                     "fertilized_until_day", "consecutive_unwatered", "max_lifespan_step")}


def workers(farm):
    yield "farmer", farm.get("farmer")
    for i, pos in enumerate(farm.get("hands", [])):
        yield f"hand:{i}", pos


def action_for(action, worker):
    if worker == "farmer":
        items = action.get("farmer") or []
    else:
        i = int(worker.split(":")[1])
        hands = action.get("hands") or []
        items = hands[i] if i < len(hands) else []
    # A worker has one command array, e.g. ["WATER"] or ["MOVE", "UP"].
    # Some malformed replay actions use nested arrays; preserve those as requests.
    if isinstance(items, list) and items and isinstance(items[0], str):
        return [items]
    return list(items) if isinstance(items, list) else []


def visible_shops(obs):
    return list(obs.get("town", {}).get("unlocked_shops", []))


def effective(op, before, after, planted_crop):
    """Conservative tile-local execution test; false marks a requested no-op."""
    a, b = crop_state(before), crop_state(after)
    if op == "PLANT":
        return crop(after) == planted_crop and crop(before) != planted_crop
    if op == "HARVEST":
        return crop(before) == planted_crop and crop(after) != planted_crop
    if op == "WATER":
        return crop(before) == planted_crop and crop(after) == planted_crop and not a.get("watered_today") and b.get("watered_today")
    if op == "FERTILIZE":
        return crop(before) == planted_crop and crop(after) == planted_crop and a.get("fertilized_until_day") != b.get("fertilized_until_day")
    return False


def leader_episodes():
    mapping = json.loads(AGENTS.read_text(encoding="utf-8"))
    by_episode = defaultdict(list)
    for sub, episodes in mapping.items():
        if sub not in LEADERS:
            continue
        for row in episodes:
            for agent in row["agents"]:
                if str(agent["sub"]) == sub:
                    by_episode[int(row["id"])].append((sub, int(agent["idx"])))
    return by_episode


def extract_replay(path, targets):
    replay = json.loads(path.read_text(encoding="utf-8"))
    episode = int(replay["info"]["EpisodeId"])
    modules = []
    # Snapshot t is pre-action state; its action resides on record t + 1.
    for submission, seat in targets:
        active = {}
        for t in range(len(replay["steps"]) - 1):
            pre = replay["steps"][t][seat]["observation"]
            post = replay["steps"][t + 1][seat]["observation"]
            action = replay["steps"][t + 1][seat].get("action") or {}
            farm = pre["farms"][seat]
            for worker, pos in workers(farm):
                if not pos:
                    continue
                before, after = tile_at(pre, pos), tile_at(post, pos)
                commands = action_for(action, worker)
                for command_index, command in enumerate(commands):
                    if not command or not isinstance(command[0], str):
                        continue
                    op = command[0]
                    key = (tuple(pos), crop(before))
                    # A successful planting starts the tile's new crop life.
                    if op == "PLANT" and crop(after) in CROPS and effective(op, before, after, crop(after)):
                        c = crop(after)
                        active[tuple(pos)] = dict(
                            leader=LEADERS[submission], submission=int(submission), episode=episode, seat=seat,
                            crop=c, plantingStep=t, plantingDay=pre["day"], plantingHour=pre["hour"], tile=list(pos),
                            visible_shops_at_planting=visible_shops(pre), events=[dict(
                                step=t, day=pre["day"], hour=pre["hour"], day_offset=0, worker=worker,
                                command_index=command_index, command=command, requested=True, executed=True,
                                pre_crop=crop_state(before), post_crop=crop_state(after))], observations=[])
                        continue
                    record = active.get(tuple(pos))
                    if not record or crop(before) != record["crop"]:
                        continue
                    is_effective = effective(op, before, after, record["crop"])
                    # No-effect duplicate visits are deliberately excluded from modules: the
                    # executor needs semantic work, not a replayed worker idle command.
                    if op in ("WATER", "FERTILIZE", "HARVEST") and is_effective:
                        record["events"].append(dict(step=t, day=pre["day"], hour=pre["hour"],
                            day_offset=pre["day"] - record["plantingDay"], worker=worker,
                            command_index=command_index, command=command, requested=True, executed=is_effective,
                            pre_crop=crop_state(before), post_crop=crop_state(after)))
                    if op == "HARVEST" and is_effective:
                        inv0 = pre["private"].get("inventories", [])
                        inv1 = post["private"].get("inventories", [])
                        wi = 0 if worker == "farmer" else int(worker.split(":")[1]) + 1
                        gained = max(0, (inv1[wi].get(record["crop"], 0) if wi < len(inv1) else 0) -
                                         (inv0[wi].get(record["crop"], 0) if wi < len(inv0) else 0))
                        record.update(endStep=t, endDay=pre["day"], endHour=pre["hour"],
                                      duration_days=pre["day"] - record["plantingDay"],
                                      verified_harvest_units=gained, actual_harvest_total=gained,
                                      harvest_verified=gained > 0)
                        modules.append(record)
                        active.pop(tuple(pos), None)
            # Daily state observations make growth and care outcomes consumable by a route compiler.
            for pos, record in list(active.items()):
                state = crop_state(tile_at(post, pos))
                if state and (not record["observations"] or record["observations"][-1]["day"] != post["day"]):
                    record["observations"].append(dict(step=t + 1, day=post["day"], hour=post["hour"],
                        day_offset=post["day"] - record["plantingDay"], crop=state))
    return modules


def main():
    targets = leader_episodes()
    all_modules = []
    for path in sorted(REPLAYS.glob("episode-*-replay.json")):  # one raw replay at a time
        episode = int(path.name.split("-")[1])
        if episode in targets:
            all_modules.extend(extract_replay(path, targets[episode]))
    candidates = [m for m in all_modules if m["crop"] in {"WHEAT", "CARROT"} and m["duration_days"] <= 6
                  and 12 <= m["plantingDay"] <= 21 and m["harvest_verified"]]
    # Give each leader at least two simple, short cycles, then prefer shortest carrot/wheat cycles.
    chosen = []
    for leader in LEADERS.values():
        chosen.extend(sorted((m for m in candidates if m["leader"] == leader),
                             key=lambda m: (m["duration_days"], m["crop"] != "CARROT", m["plantingStep"]))[:2])
    seen = {(m["episode"], m["seat"], tuple(m["tile"]), m["plantingStep"]) for m in chosen}
    # Balance sources so the first experiment can mix both leaders.
    for leader in LEADERS.values():
        for m in sorted((m for m in candidates if m["leader"] == leader),
                        key=lambda m: (m["duration_days"], m["crop"] != "CARROT", m["plantingStep"])):
            k = (m["episode"], m["seat"], tuple(m["tile"]), m["plantingStep"])
            if k not in seen and sum(x["leader"] == leader for x in chosen) < 20:
                chosen.append(m); seen.add(k)
    payload = dict(schema_version=1, source="leader replay snapshots; no future shops included",
                   selection="completed WHEAT/CARROT cycles planted days 12..21, duration <= 6 days; no-effect visits removed; capped at 40",
                   modules=chosen)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(dict(modules=len(chosen), by_leader={x: sum(m["leader"] == x for m in chosen) for x in LEADERS.values()},
                          crops={x: sum(m["crop"] == x for m in chosen) for x in ("WHEAT", "CARROT")})))


if __name__ == "__main__":
    main()

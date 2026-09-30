"""Extract dated production events from compact tapes and verified replay windows.

Compact actions record requests, not success. Rich segment jobs carry before/after
tile evidence. This script keeps those evidence levels separate and never labels
an unserviced animal as an intentional retirement.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_tapes"
TAPES = ROOT / "data/mg_tapes"
SEGMENTS = ROOT / "results/fresh/segment_stitch/library.json"
ANIMALS = {"GOOSE", "COW", "SHEEP"}


def add(counter, day, product):
    counter[f"{day}:{product}"] += 1


def compact_profile(tape):
    plants, placements, animal_orders = Counter(), Counter(), Counter()
    for hour, action in enumerate(tape["actions"]):
        day = hour // 24
        for cmd in [action.get("farmer") or [], *(action.get("hands") or [])]:
            if len(cmd) >= 2 and cmd[0] == "PLANT":
                add(plants, day, cmd[1])
            elif len(cmd) >= 2 and cmd[0] == "PLACE" and cmd[1] in ANIMALS:
                add(placements, day, cmd[1])
        for cmd in action.get("market") or []:
            if len(cmd) >= 3 and cmd[0] == "BUY_ANIMAL":
                animal_orders[f"{day}:{cmd[1]}"] += int(cmd[2])
    counts = []
    for board in tape["boards"]:
        labels = [row[i:i + 2] for row in board for i in range(0, len(row), 2)]
        counts.append(dict(Counter(x for x in labels if x not in (" .", " L", " w"))))
    return dict(episode=tape["episode"], submission=tape["submission"],
                seat=tape["seat"], shops=[list(x) for x in tape["shops"]],
                requested_plants=dict(plants), requested_placements=dict(placements),
                requested_animal_orders=dict(animal_orders), realized_day_start_counts=counts)


def crop_from_sig(signature):
    if not isinstance(signature, str):
        return None
    for field in signature.split("|"):
        if field.startswith("crop="):
            return field[5:]
    return None


def animal_from_sig(signature):
    if not isinstance(signature, str):
        return None
    for field in signature.split("|"):
        if field.startswith("animal="):
            return field[7:]
    return None


def live_tiles(farm):
    for y, row in enumerate(farm["tiles"]):
        for x, tile in enumerate(row):
            if isinstance(tile, dict):
                yield (x, y), tile


def rich_profile(node):
    plants, placements, feed, care, unresolved = (Counter() for _ in range(5))
    transitions = []
    last_crop = {xy: t["crop"] for xy, t in live_tiles(node["start_farm"]) if t.get("crop")}
    starting_animals = {xy: t["animal"] for xy, t in live_tiles(node["start_farm"]) if t.get("animal")}
    service = defaultdict(set)
    for job in node["jobs"]:
        cmd = job["cmd"]
        if not cmd:
            continue
        op, day, ok = cmd[0], int(job["day"]), job["successful"]
        xy = tuple(job["tile"]) if job.get("tile") is not None else None
        if ok is None:
            unresolved[op] += 1
        if ok is not True:
            continue
        if op == "HARVEST" and xy is not None:
            before = crop_from_sig(job.get("pre_tile"))
            if before:
                last_crop[xy] = before
        if op == "PLANT" and len(cmd) > 1 and crop_from_sig(job.get("post_tile")) == cmd[1]:
            add(plants, day, cmd[1])
            if xy is not None:
                old = last_crop.get(xy)
                if old and old != cmd[1]:
                    transitions.append(dict(day=node["day"] + day, tile=list(xy),
                                            from_crop=old, to_crop=cmd[1]))
                last_crop[xy] = cmd[1]
        elif op == "PLACE" and len(cmd) > 1 and cmd[1] in ANIMALS and animal_from_sig(job.get("post_tile")) == cmd[1]:
            add(placements, day, cmd[1])
        elif op in ("FEED", "CARE") and xy is not None:
            add(feed if op == "FEED" else care, day, starting_animals.get(xy, "NEW"))
            if xy in starting_animals:
                service[xy].add((day, op))
    end_animals = {xy: t["animal"] for xy, t in live_tiles(node["end_farm"]) if t.get("animal")}
    existing_animal_service = []
    for xy, species in sorted(starting_animals.items()):
        existing_animal_service.append(dict(tile=list(xy), animal=species,
                                            fed_on=[node["day"] + d for d in range(3) if (d, "FEED") in service[xy]],
                                            cared_on=[node["day"] + d for d in range(3) if (d, "CARE") in service[xy]],
                                            survives_at_end=end_animals.get(xy) == species))
    return dict(id=node["id"], episode=node["episode"], day=node["day"],
                start_shops=node["start_shops"],
                successful_plants=dict(plants), successful_placements=dict(placements),
                successful_feed=dict(feed), successful_care=dict(care),
                unresolved_midnight_actions=dict(unresolved),
                crop_transitions=transitions,
                starting_animal_service=existing_animal_service,
                recorded_output=node["output"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    compact = []
    for folder in sorted(TAPES.iterdir()):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json.gz")):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                compact.append(compact_profile(json.load(handle)))
    with SEGMENTS.open(encoding="utf-8") as handle:
        rich = [rich_profile(node) for node in json.load(handle)["segments"]]
    by_episode = {t["episode"]: t for t in compact}
    assert len(by_episode) == len(compact) == 584
    checked_plant_events = checked_placements = 0
    for segment in rich:
        tape = by_episode[segment["episode"]]
        for field, target in (("successful_plants", "requested_plants"),
                              ("successful_placements", "requested_placements")):
            for key, n in segment[field].items():
                relative_day, product = key.split(":", 1)
                absolute_key = f"{segment['day'] + int(relative_day)}:{product}"
                assert n <= tape[target].get(absolute_key, 0), (segment["id"], key, n, tape[target].get(absolute_key))
                if field == "successful_plants":
                    checked_plant_events += n
                else:
                    checked_placements += n
    examples = [dict(id=x["id"], transition=t) for x in rich for t in x["crop_transitions"]
                if t["from_crop"] == "WHEAT" and t["to_crop"] == "STRAWBERRY"]
    summary = dict(compact_tapes=len(compact), verified_segments=len(rich),
                   verified_plant_events=sum(sum(x["successful_plants"].values()) for x in rich),
                   verified_animal_placements=sum(sum(x["successful_placements"].values()) for x in rich),
                   verified_crop_transitions=sum(len(x["crop_transitions"]) for x in rich),
                   compact_request_bounds_verified=dict(plants=checked_plant_events, placements=checked_placements),
                   wheat_to_strawberry_examples=examples[:8],
                   animal_retirement_identifiable=False,
                   evidence="Compact commands are requests; rich successes are before/after tile changes. Missing future service is observational, not inferred intent.")
    (OUT / "compact_profiles.json").write_text(json.dumps(compact, separators=(",", ":")), encoding="utf-8")
    (OUT / "verified_segments.json").write_text(json.dumps(rich, separators=(",", ":")), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

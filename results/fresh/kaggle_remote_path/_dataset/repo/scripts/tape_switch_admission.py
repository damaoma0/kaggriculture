"""Offline, information-safe transition audit for Mother-Goose route tapes.

This is a diagnostic admission check, not a complete switching executor.  It
uses only the live day-boundary board and recorded actions of two candidate
tapes.  Shops after the decision day are not read.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import gzip
import json

from fragments.tape_calendar import _tc_simulate, _tc_visits

ROOT = Path(__file__).resolve().parents[1]
ANIMALS = {"COW", "SHEEP", "GOOSE"}
SERVICE = {"FEED", "CARE", "HARVEST", "COLLECT_FERTILIZER", "WATER", "FERTILIZE"}


def load_tape(episode: int | str) -> dict:
    for submission in ("56266758", "56266899"):
        path = ROOT / "data" / "mg_tapes" / submission / f"{episode}.json.gz"
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                return json.load(stream)
    raise FileNotFoundError(episode)


def scheduled_visits(tape: dict, day: int, days: int = 2) -> dict:
    start, stop = day * 24, min(718, (day + days) * 24 - 1)
    actions = tape["actions"]
    return _tc_visits(_tc_simulate(lambda step: actions[step], start, stop, [(4, 4)]))


def audit_switch(live_assets: list, incumbent: dict, candidate: dict, day: int) -> dict:
    """Score obligations left behind and commands aimed at the wrong tile type."""
    live = {(int(x), int(y)): item for x, y, item, *_ in live_assets}
    current_visits = scheduled_visits(incumbent, day)
    proposed_visits = scheduled_visits(candidate, day)
    lost = []
    for (x, y), item in live.items():
        old_ops = Counter(c[0] for _, _, c in current_visits.get((x, y), ()) if c)
        new_ops = Counter(c[0] for _, _, c in proposed_visits.get((x, y), ()) if c)
        if item in ANIMALS:
            if old_ops["FEED"] and not new_ops["FEED"]:
                lost.append({"tile": [x, y], "asset": item, "obligation": "FEED",
                             "current": old_ops["FEED"], "candidate": 0})
            if old_ops["HARVEST"] and not new_ops["HARVEST"]:
                lost.append({"tile": [x, y], "asset": item, "obligation": "HARVEST",
                             "current": old_ops["HARVEST"], "candidate": 0})
        elif any(old_ops[op] for op in ("WATER", "FERTILIZE", "HARVEST")) and not any(
                new_ops[op] for op in ("WATER", "FERTILIZE", "HARVEST")):
            lost.append({"tile": [x, y], "asset": item, "obligation": "CROP_SERVICE",
                         "current": sum(old_ops[op] for op in ("WATER", "FERTILIZE", "HARVEST")), "candidate": 0})

    def wrong_targets(visits):
        wrong = []
        # Only the first day can be compared directly with today's board;
        # later construction and harvest can change it.
        for (x, y), rows in visits.items():
            asset = live.get((x, y))
            for step, unit, command in rows:
                if step >= (day + 1) * 24 or not command:
                    continue
                op = command[0]
                wanted = "animal" if op in ("FEED", "CARE", "COLLECT_FERTILIZER") else (
                    "crop" if op in ("WATER", "FERTILIZE") else None)
                if wanted == "animal" and asset not in ANIMALS or wanted == "crop" and asset not in live_crop_types:
                    wrong.append({"step": step, "unit": unit, "tile": [x, y],
                                  "command": command, "actual_asset": asset})
        return wrong

    live_crop_types = set(live.values()) - ANIMALS
    old_wrong = wrong_targets(current_visits)
    new_wrong = wrong_targets(proposed_visits)
    orphan_animals = [row for row in lost if row["asset"] in ANIMALS and row["obligation"] == "FEED"]
    return {
        "day": day, "incumbent_episode": incumbent["episode"], "candidate_episode": candidate["episode"],
        "live_asset_count": len(live), "lost_obligations": lost,
        "orphan_animals": len(orphan_animals),
        "incumbent_wrong_first_day": len(old_wrong), "candidate_wrong_first_day": len(new_wrong),
        "incremental_wrong_first_day": len(new_wrong) - len(old_wrong),
        "candidate_wrong_examples": new_wrong[:20],
        "admit_raw_switch": not orphan_animals and not lost and len(new_wrong) <= len(old_wrong) + 2,
    }


def main():
    import sys
    source = Path(sys.argv[1])
    probe = json.loads(source.read_text(encoding="utf-8"))
    day = probe["switch_day"]
    snapshot = next(row for row in probe["control_trace"]["day_start"] if row["day"] == day)
    result = audit_switch(snapshot["board"], load_tape(probe["tape_before_switch"]),
                          load_tape(probe["target_tape"]), day)
    out = source.with_name(source.stem + "-admission.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "day", "incumbent_episode", "candidate_episode", "live_asset_count",
        "orphan_animals", "incumbent_wrong_first_day", "candidate_wrong_first_day",
        "incremental_wrong_first_day", "admit_raw_switch",
    )}, indent=2))
    print("lost obligations:", Counter((r["asset"], r["obligation"]) for r in result["lost_obligations"]))


if __name__ == "__main__":
    main()

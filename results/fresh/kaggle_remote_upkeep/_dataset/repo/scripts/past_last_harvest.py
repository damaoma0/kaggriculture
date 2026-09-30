"""How much maintenance do 3000+ leaders spend on assets that can no longer
produce anything harvestable before the season ends?

For every WATER/FEED/CARE/FERTILIZE action recorded in
`data/leader_semantics/<team_id>/<episode>.json.gz` as having taken effect on
tile T on day D, we identify the asset instance (crop or animal, with its
start day) that was live on T at day D, then ask whether that instance still
has ANY production landing at or before day 28 (the last day whose end-of-day
production can be harvested, since day 29 has no following day to harvest
into) that the action could still influence:

  - CARE: a production strictly AFTER day D (CARE banks a bonus for the NEXT
    production; care on the last production day is wasted).
  - FEED / WATER / FERTILIZE: a production ON OR AFTER day D (a same-day
    FEED/WATER/FERTILIZE can still contribute to that day's production).

Actions that fail this test are "past the last reachable harvest": a
stop-when-nothing-left-to-produce agent would skip them.

Asset production-day schedules (day = instance start_day + age), per the
project's PRODUCTION RULES brief for this task:
  GOOSE       age 4, then every day
  COW         age 8, then every 2 days
  SHEEP       age 6, then every 3 days
  STRAWBERRY  ages 10, 12, 14, 16 (ongoing, decays after)
  TOMATO      ages 8, 9, 10, 11 (ongoing, decays after)
  MELON       one-time, age 10 only
  WHEAT       one-time bonus window, ages 2-4
  CARROT      one-time bonus window, ages 2-3

Asset instances are anchored using 'planted' (crop, exact day, exact tile)
and 'animals.placed' (tile, exact day; species is not recorded directly and
is resolved by reading the animal letter off the NEXT day's board, since
'planted'/'placed' are correctly-dated fields but do not carry animal
species). Day 0's board is empty/locked in all 260 games in this corpus, so
every asset instance in the data originates from a recorded planting/
placement event; there is no left-censoring to worry about. A tile's active
instance for a maintenance action on day D is the most recent planted/placed
event on that tile with start_day <= D.

FERTILIZE has no separate rule spelled out in the task brief; it is grouped
with FEED/WATER ("on or after day D") since it also buffs that same day's
production bonus. This is a stated assumption, not a rule quoted verbatim
from the environment doc.

Usage:
    .venv/Scripts/python.exe scripts/past_last_harvest.py
Writes:
    results/fresh/past_last_harvest/past_last_harvest.json
    results/fresh/past_last_harvest/past_last_harvest.md
"""
from __future__ import annotations

import gzip
import json
import glob
import os
import statistics
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_GLOB = os.path.join(ROOT, "data", "leader_semantics", "*", "*.json.gz")
OUT_DIR = os.path.join(ROOT, "results", "fresh", "past_last_harvest")

LAST_HARVESTABLE_DAY = 28  # end-of-day-28 production is the last one that can still be harvested (day 29 exists to harvest it)
LAST_DAY = 29

MAINT_TYPES = ("WATER", "FEED", "CARE", "FERTILIZE")
ANIMAL_LETTER = {"sh": "SHEEP", "co": "COW", "go": "GOOSE"}
ANIMAL_KINDS = {"SHEEP", "COW", "GOOSE"}
CROP_KINDS = {"STRAWBERRY", "TOMATO", "MELON", "WHEAT", "CARROT"}


def production_days(asset_type: str, start_day: int) -> list[int]:
    """Calendar days (0..29) on which `asset_type` planted/placed on
    `start_day` produces, per the task's age schedule, filtered to those
    landing at or before LAST_HARVESTABLE_DAY (later ones aren't harvestable)."""
    if asset_type == "GOOSE":
        ages = range(4, LAST_DAY - start_day + 1)
    elif asset_type == "COW":
        ages = range(8, LAST_DAY - start_day + 1, 2)
    elif asset_type == "SHEEP":
        ages = range(6, LAST_DAY - start_day + 1, 3)
    elif asset_type == "STRAWBERRY":
        ages = [10, 12, 14, 16]
    elif asset_type == "TOMATO":
        ages = [8, 9, 10, 11]
    elif asset_type == "MELON":
        ages = [10]
    elif asset_type == "WHEAT":
        ages = [2, 3, 4]
    elif asset_type == "CARROT":
        ages = [2, 3]
    else:
        ages = []
    days = [start_day + a for a in ages]
    return [d for d in days if 0 <= d <= LAST_HARVESTABLE_DAY]


def is_wasted(asset_type: str, start_day: int, action_day: int, action_type: str) -> bool:
    days = production_days(asset_type, start_day)
    if action_type == "CARE":
        return not any(d > action_day for d in days)
    return not any(d >= action_day for d in days)  # FEED, WATER, FERTILIZE


def resolve_animal_species(days, placed_day: int, tile: int) -> str | None:
    """Look at the board on placed_day+1, +2, +3 to find the animal letter
    that landed on `tile` (placed_day itself reflects the day-start board,
    i.e. BEFORE that day's PLACE took effect)."""
    for lookahead in (1, 2, 3):
        d = placed_day + lookahead
        if d >= len(days):
            break
        label = days[d]["board"][tile]
        letter = label.strip()
        if letter in ANIMAL_LETTER:
            return ANIMAL_LETTER[letter]
        if letter not in ("", "L") and letter.islower() is False and lookahead == 1:
            # something else grew there already (e.g. re-planted) - species unresolved
            break
    return None


def build_instances(days) -> dict[int, list[tuple[int, str]]]:
    """tile -> sorted [(start_day, asset_type), ...] built from 'planted'
    and 'animals.placed' events (both correctly dated per the README)."""
    events = defaultdict(list)
    unresolved_animals = 0
    for d, day in enumerate(days):
        for crop, tiles in day.get("planted", {}).items():
            for t in tiles:
                events[t].append((d, crop))
        for t in day.get("animals", {}).get("placed", []):
            species = resolve_animal_species(days, d, t)
            if species is None:
                unresolved_animals += 1
                continue
            events[t].append((d, species))
    for t in events:
        events[t].sort(key=lambda e: e[0])
    return events, unresolved_animals


def active_instance(events_for_tile, action_day: int):
    active = None
    for start_day, asset_type in events_for_tile:
        if start_day <= action_day:
            active = (start_day, asset_type)
        else:
            break
    return active


def main():
    files = sorted(glob.glob(DATA_GLOB))
    if not files:
        raise SystemExit(f"no files found under {DATA_GLOB}")

    # ---- per-corpus accumulators ----
    n_games = 0
    games_by_team = Counter()
    team_names = defaultdict(Counter)

    # wasted-action tallies: keyed at multiple granularities, always as
    # (sum-across-games) so we can later divide by game counts for means.
    wasted_by_type = Counter()                 # type -> count
    wasted_by_kind = Counter()                 # asset kind -> count
    wasted_by_day = Counter()                  # day -> count
    wasted_by_type_day = Counter()             # (type, day) -> count
    wasted_by_kind_day = Counter()             # (kind, day) -> count
    wasted_by_type_kind = Counter()            # (type, kind) -> count
    wasted_by_team_type = Counter()            # (team, type) -> count
    wasted_by_team_kind = Counter()            # (team, kind) -> count
    wasted_by_team = Counter()                 # team -> count
    wasted_by_team_day = Counter()             # (team, day) -> count

    total_by_type = Counter()                  # all actions (wasted or not) by type
    total_by_team = Counter()

    move_count_by_day = Counter()
    working_count_by_day = Counter()

    maint_days20_29_total = 0
    wasted_days20_29_total = 0
    wasted_days20_29_by_team = Counter()
    maint_days20_29_by_team = Counter()

    wheat_wasted_total = 0
    wheat_wasted_by_team = Counter()

    unmatched_actions = 0
    unresolved_animal_placements_total = 0

    # animals fed on days 27-29 whose next production is after day 28
    fed_27_29_actions_total = 0
    fed_27_29_wasted_actions = 0
    fed_27_29_instances = set()          # (episode, tile, start_day) global-unique via episode id
    fed_27_29_wasted_instances = set()

    per_game_wasted_totals = []  # for overall per-game distribution stats

    for path in files:
        team_id = os.path.basename(os.path.dirname(path))
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
        n_games += 1
        games_by_team[team_id] += 1
        team_names[team_id][data["meta"]["team"]] += 1
        episode = data["meta"]["episode"]

        days = data["days"]
        events_by_tile, unresolved = build_instances(days)
        unresolved_animal_placements_total += unresolved

        game_wasted = 0

        for d, day in enumerate(days):
            cc = day.get("labour", {}).get("command_counts", {})
            move_count_by_day[d] += cc.get("MOVE", 0)
            working_count_by_day[d] += sum(v for k, v in cc.items() if k != "MOVE")

            maint = day.get("maintenance", {})
            day_maint_count = sum(len(maint.get(t, [])) for t in MAINT_TYPES)
            if 20 <= d <= 29:
                maint_days20_29_total += day_maint_count
                maint_days20_29_by_team[team_id] += day_maint_count

            for action_type in MAINT_TYPES:
                tiles = maint.get(action_type, [])
                total_by_type[action_type] += len(tiles)
                total_by_team[team_id] += len(tiles)
                for tile in tiles:
                    inst = active_instance(events_by_tile.get(tile, []), d)
                    if inst is None:
                        unmatched_actions += 1
                        continue
                    start_day, asset_type = inst
                    wasted = is_wasted(asset_type, start_day, d, action_type)
                    kind = asset_type

                    if action_type == "FEED" and kind in ANIMAL_KINDS and 27 <= d <= 29:
                        fed_27_29_actions_total += 1
                        fed_27_29_instances.add((episode, tile, start_day))
                        if wasted:
                            fed_27_29_wasted_actions += 1
                            fed_27_29_wasted_instances.add((episode, tile, start_day))

                    if not wasted:
                        continue

                    game_wasted += 1
                    wasted_by_type[action_type] += 1
                    wasted_by_kind[kind] += 1
                    wasted_by_day[d] += 1
                    wasted_by_type_day[(action_type, d)] += 1
                    wasted_by_kind_day[(kind, d)] += 1
                    wasted_by_type_kind[(action_type, kind)] += 1
                    wasted_by_team_type[(team_id, action_type)] += 1
                    wasted_by_team_kind[(team_id, kind)] += 1
                    wasted_by_team[team_id] += 1
                    wasted_by_team_day[(team_id, d)] += 1

                    if 20 <= d <= 29:
                        wasted_days20_29_total += 1
                        wasted_days20_29_by_team[team_id] += 1

                    if action_type == "FEED" and kind in ANIMAL_KINDS:
                        wheat_wasted_total += 1
                        wheat_wasted_by_team[team_id] += 1

        per_game_wasted_totals.append(game_wasted)

    # ---- MOVE-to-working ratio per day (corpus-wide) ----
    move_ratio_by_day = {}
    for d in range(30):
        w = working_count_by_day.get(d, 0)
        move_ratio_by_day[d] = (move_count_by_day.get(d, 0) / w) if w else 0.0

    # unit-hours: for each wasted action on day d, 1 step for the action + move_ratio_by_day[d] walking steps
    unit_hours_by_day = {d: wasted_by_day.get(d, 0) * (1 + move_ratio_by_day[d]) for d in range(30)}
    unit_hours_total = sum(unit_hours_by_day.values())

    OUT_DIR_local = OUT_DIR
    os.makedirs(OUT_DIR_local, exist_ok=True)

    result = {
        "games": n_games,
        "games_by_team": dict(games_by_team),
        "team_names": {k: dict(v) for k, v in team_names.items()},
        "unmatched_actions": unmatched_actions,
        "unresolved_animal_placements": unresolved_animal_placements_total,
        "wasted_by_type_total": dict(wasted_by_type),
        "wasted_by_type_per_game": {k: v / n_games for k, v in wasted_by_type.items()},
        "total_actions_by_type": dict(total_by_type),
        "wasted_share_by_type": {
            k: (wasted_by_type[k] / total_by_type[k]) if total_by_type.get(k) else None
            for k in MAINT_TYPES
        },
        "wasted_by_kind_total": dict(wasted_by_kind),
        "wasted_by_kind_per_game": {k: v / n_games for k, v in wasted_by_kind.items()},
        "wasted_by_day_total": {str(d): wasted_by_day.get(d, 0) for d in range(30)},
        "wasted_by_day_per_game": {str(d): wasted_by_day.get(d, 0) / n_games for d in range(30)},
        "wasted_by_type_and_day_total": {f"{t}|{d}": wasted_by_type_day.get((t, d), 0)
                                          for t in MAINT_TYPES for d in range(30) if wasted_by_type_day.get((t, d), 0)},
        "wasted_by_kind_and_day_total": {f"{k}|{d}": wasted_by_kind_day.get((k, d), 0)
                                          for k in (CROP_KINDS | ANIMAL_KINDS) for d in range(30) if wasted_by_kind_day.get((k, d), 0)},
        "wasted_by_type_and_kind_total": {f"{t}|{k}": wasted_by_type_kind.get((t, k), 0)
                                           for t in MAINT_TYPES for k in (CROP_KINDS | ANIMAL_KINDS) if wasted_by_type_kind.get((t, k), 0)},
        "wheat_wasted_total": wheat_wasted_total,
        "wheat_wasted_per_game": wheat_wasted_total / n_games,
        "move_ratio_by_day": {str(d): move_ratio_by_day[d] for d in range(30)},
        "move_count_by_day": {str(d): move_count_by_day.get(d, 0) for d in range(30)},
        "working_count_by_day": {str(d): working_count_by_day.get(d, 0) for d in range(30)},
        "unit_hours_wasted_total": unit_hours_total,
        "unit_hours_wasted_per_game": unit_hours_total / n_games,
        "unit_hours_by_day": {str(d): unit_hours_by_day[d] for d in range(30)},
        "maintenance_days20_29_total": maint_days20_29_total,
        "wasted_days20_29_total": wasted_days20_29_total,
        "wasted_share_of_maintenance_days20_29": (
            wasted_days20_29_total / maint_days20_29_total if maint_days20_29_total else None
        ),
        "fed_27_29": {
            "actions_total": fed_27_29_actions_total,
            "actions_wasted": fed_27_29_wasted_actions,
            "distinct_animal_instances_fed": len(fed_27_29_instances),
            "distinct_animal_instances_wasted": len(fed_27_29_wasted_instances),
        },
        "per_game_wasted_distribution": {
            "mean": statistics.mean(per_game_wasted_totals),
            "median": statistics.median(per_game_wasted_totals),
            "min": min(per_game_wasted_totals),
            "max": max(per_game_wasted_totals),
            "stdev": statistics.pstdev(per_game_wasted_totals),
        },
        "by_team": {},
    }

    for team_id, n in games_by_team.items():
        team_wasted_type = {t: wasted_by_team_type.get((team_id, t), 0) for t in MAINT_TYPES}
        team_wasted_kind = {k: wasted_by_team_kind.get((team_id, k), 0) for k in (CROP_KINDS | ANIMAL_KINDS) if wasted_by_team_kind.get((team_id, k), 0)}
        team_unit_hours = sum(
            wasted_by_team_day.get((team_id, d), 0) * (1 + move_ratio_by_day[d]) for d in range(30)
        )
        result["by_team"][team_id] = {
            "team_names": dict(team_names[team_id]),
            "games": n,
            "wasted_total": wasted_by_team.get(team_id, 0),
            "wasted_per_game": wasted_by_team.get(team_id, 0) / n,
            "wasted_by_type_total": team_wasted_type,
            "wasted_by_type_per_game": {t: v / n for t, v in team_wasted_type.items()},
            "wasted_by_kind_total": team_wasted_kind,
            "wasted_by_kind_per_game": {k: v / n for k, v in team_wasted_kind.items()},
            "total_actions_total": total_by_team.get(team_id, 0),
            "total_actions_per_game": total_by_team.get(team_id, 0) / n,
            "wheat_wasted_total": wheat_wasted_by_team.get(team_id, 0),
            "wheat_wasted_per_game": wheat_wasted_by_team.get(team_id, 0) / n,
            "unit_hours_wasted_total": team_unit_hours,
            "unit_hours_wasted_per_game": team_unit_hours / n,
            "maintenance_days20_29_total": maint_days20_29_by_team.get(team_id, 0),
            "wasted_days20_29_total": wasted_days20_29_by_team.get(team_id, 0),
            "wasted_share_of_maintenance_days20_29": (
                wasted_days20_29_by_team.get(team_id, 0) / maint_days20_29_by_team.get(team_id, 0)
                if maint_days20_29_by_team.get(team_id, 0) else None
            ),
        }

    json_path = os.path.join(OUT_DIR_local, "past_last_harvest.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    write_markdown(result, os.path.join(OUT_DIR_local, "past_last_harvest.md"))
    print(f"wrote {json_path}")
    print(f"games={n_games} wasted_total={sum(wasted_by_type.values())} "
          f"wasted_per_game={sum(wasted_by_type.values())/n_games:.2f} "
          f"unmatched={unmatched_actions} unresolved_animal_placements={unresolved_animal_placements_total}")


def write_markdown(result, path):
    lines = []
    lines.append("# Maintenance past the last reachable harvest\n")
    lines.append(f"Corpus: {result['games']} leader games across {len(result['games_by_team'])} teams "
                 f"(`data/leader_semantics/`).\n")
    lines.append(f"Unmatched maintenance actions (no planted/placed anchor found): {result['unmatched_actions']}. "
                 f"Unresolved animal-placement species lookups: {result['unresolved_animal_placements']}.\n")

    lines.append("## Overall wasted actions by type (mean per game / total)\n")
    lines.append("| Type | Total | Per game | Share of all such actions |")
    lines.append("|---|---:|---:|---:|")
    for t in MAINT_TYPES:
        total = result["wasted_by_type_total"].get(t, 0)
        per_game = result["wasted_by_type_per_game"].get(t, 0.0)
        share = result["wasted_share_by_type"].get(t)
        share_s = f"{share*100:.1f}%" if share is not None else "n/a"
        lines.append(f"| {t} | {total} | {per_game:.2f} | {share_s} |")
    lines.append("")

    lines.append("## Overall wasted actions by asset kind (mean per game / total)\n")
    lines.append("| Kind | Total | Per game |")
    lines.append("|---|---:|---:|")
    for k, v in sorted(result["wasted_by_kind_total"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} | {result['wasted_by_kind_per_game'][k]:.3f} |")
    lines.append("")

    lines.append("## Wasted actions by day of season (total across corpus)\n")
    lines.append("| Day | Wasted actions | Per game |")
    lines.append("|---:|---:|---:|")
    for d in range(30):
        tot = result["wasted_by_day_total"][str(d)]
        if tot == 0:
            continue
        lines.append(f"| {d} | {tot} | {result['wasted_by_day_per_game'][str(d)]:.3f} |")
    lines.append("")

    lines.append("## Cost estimates\n")
    lines.append(f"- Wheat wasted on FEED past last reachable harvest: {result['wheat_wasted_total']} total, "
                 f"{result['wheat_wasted_per_game']:.2f} per game (1 wheat per wasted FEED).")
    lines.append(f"- Estimated unit-hours wasted (1 step/action + corpus per-day MOVE:working ratio for walking): "
                 f"{result['unit_hours_wasted_total']:.1f} total, {result['unit_hours_wasted_per_game']:.3f} per game.")
    lines.append(f"- Share of ALL maintenance actions (WATER+FEED+CARE+FERTILIZE) in days 20-29 that are past the "
                 f"last reachable harvest: {result['wasted_share_of_maintenance_days20_29']*100:.1f}% "
                 f"({result['wasted_days20_29_total']} of {result['maintenance_days20_29_total']}).")
    fed = result["fed_27_29"]
    lines.append(f"- FEED actions on animals on days 27-29 whose next production falls after day 28: "
                 f"{fed['actions_wasted']} of {fed['actions_total']} FEED actions "
                 f"({fed['distinct_animal_instances_wasted']} of {fed['distinct_animal_instances_fed']} distinct animal instances).")
    pgd = result["per_game_wasted_distribution"]
    lines.append(f"- Per-game wasted-action count: mean {pgd['mean']:.2f}, median {pgd['median']:.1f}, "
                 f"stdev {pgd['stdev']:.2f}, range {pgd['min']}-{pgd['max']}.\n")

    tk = result["wasted_by_type_and_kind_total"]
    water_onetime = tk.get("WATER|WHEAT", 0) + tk.get("WATER|CARROT", 0) + tk.get("WATER|MELON", 0)
    water_ongoing = tk.get("WATER|STRAWBERRY", 0) + tk.get("WATER|TOMATO", 0)
    water_total = result["wasted_by_type_total"].get("WATER", 0)
    lines.append("## IMPORTANT CAVEAT: most wasted WATER is survival watering on an unharvested crop\n")
    lines.append(
        "Because `maintenance` only records actions that actually took effect, every 'wasted' WATER action "
        "in this report is on a tile that is still a *live, unharvested* plant (a harvested/weeded tile "
        "cannot flip a WATER flag). Splitting WATER's waste by kind: "
        f"{water_onetime} of {water_total} ({water_onetime/water_total*100:.1f}%) are on one-time crops "
        "(WHEAT/CARROT/MELON) past their yield-bonus window but still standing with accumulated, unharvested "
        f"yield on the tile; another {water_ongoing} ({water_ongoing/water_total*100:.1f}%) are on ongoing "
        "crops (STRAWBERRY/TOMATO) past their last scheduled production but already in the post-schedule decay "
        "phase, still holding un-harvested units. For both cases, a plant tile still turns to weed after 2 "
        "consecutive unwatered days regardless of production status (docs/environment.md), which would destroy "
        "the standing, unharvested yield outright. A literal 'stop maintaining once next production is beyond "
        "day 28' rule is therefore only a clean, no-downside saving when the tile has ALSO already been "
        "harvested (in which case it wouldn't need watering anyway and wouldn't appear here); applied to a "
        "still-standing crop it would need to be paired with either an immediate harvest or acceptance of that "
        "crop's loss. The same logic applies more weakly to FEED: an animal 2 consecutive days unfed escapes, "
        "which would also drop any of its own unharvested product bank. FERTILIZE and CARE have no survival "
        "role (only WATER/FEED do), so their wasted counts ("
        f"{result['wasted_by_type_total'].get('FERTILIZE', 0)} and {result['wasted_by_type_total'].get('CARE', 0)} "
        "total) are the cleanest, closest-to-unambiguous savings in this report.\n"
    )

    lines.append("## By team (per game)\n")
    lines.append("| Team folder | Team name(s) | Games | Wasted/game | WATER | FEED | CARE | FERTILIZE | Wheat/game | Unit-hrs/game | Share days20-29 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for team_id, t in sorted(result["by_team"].items(), key=lambda kv: -kv[1]["wasted_per_game"]):
        names = ",".join(t["team_names"].keys())
        wt = t["wasted_by_type_per_game"]
        share = t["wasted_share_of_maintenance_days20_29"]
        share_s = f"{share*100:.1f}%" if share is not None else "n/a"
        lines.append(f"| {team_id} | {names} | {t['games']} | {t['wasted_per_game']:.2f} | "
                     f"{wt.get('WATER',0):.2f} | {wt.get('FEED',0):.2f} | {wt.get('CARE',0):.2f} | "
                     f"{wt.get('FERTILIZE',0):.2f} | {t['wheat_wasted_per_game']:.2f} | "
                     f"{t['unit_hours_wasted_per_game']:.3f} | {share_s} |")
    lines.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


if __name__ == "__main__":
    main()

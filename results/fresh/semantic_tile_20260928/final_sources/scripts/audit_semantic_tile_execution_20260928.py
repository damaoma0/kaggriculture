"""Read-only execution audit of semantic tile plans and preserved game ledgers.

Example:
  python scripts/audit_semantic_tile_execution_20260928.py --plans plans.json
    --runs result-root-a result-root-b --arm ST28COHORT --baseline-arm ST28EXACT

The ledger records harvested output, not all production or capped lost yield.
Animal exits are classified by conformity to the intended retirement schedule;
an exit outside that schedule is a diagnostic, not automatically a harmful act.
No games are run, no policy or recorded result is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL_CROP = {"WH": "WHEAT", "CA": "CARROT", "TO": "TOMATO", "ST": "STRAWBERRY", "ME": "MELON"}
ANIMALS = {"COW", "SHEEP", "GOOSE"}
FARM_OPS = {"WATER", "FEED", "CARE", "FERTILIZE", "HARVEST", "COLLECT_FERTILIZER", "DIG", "PLANT", "BUILD_COOP", "BUILD_PASTURE"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def counter(value):
    return Counter({str(k): float(v) for k, v in (value or {}).items() if isinstance(v, (int, float))})


def as_days(ledger):
    value = ledger.get("days", [])
    return [value.get(str(d), {}) for d in range(30)] if isinstance(value, dict) else value


def actual_board(row):
    board = row.get("board_list")
    if board is None:
        return None
    assert len(board) == 100, "Ledger board_list is not a full farm"
    return ["EMPTY" if kind == "WEED" else kind for kind in board]


def planned_board(plan, day):
    """Disambiguate 'co' using structure + animal histories, never label alone."""
    raw = plan["board"][day]
    structures = {int(t): k for t, k in plan["struct_by_day"][max(0, day - 1)].items()}
    animals = {int(t): k for t, k in plan["animals_by_day"][max(0, day - 1)].items()}
    result = []
    for tile, label in enumerate(raw):
        if label in LABEL_CROP:
            result.append(LABEL_CROP[label])
        elif label == " L":
            result.append("LOCKED")
        elif label in (" .", " w"):
            result.append("EMPTY")
        elif tile in animals:
            result.append(animals[tile])
        elif tile in structures:
            result.append("S_" + structures[tile])
        elif label in ("sh", "go"):
            result.append({"sh": "SHEEP", "go": "GOOSE"}[label])
        else:
            result.append("UNKNOWN:" + str(label))
    return result


def event_matches(plan, days, handoff=11, max_lateness=6):
    """Exact-day matches first, then nearest earlier unmatched same-tile cohort.

    This attributes observed successful plantings; it never treats requested
    PLANT commands as successful. Unmatched final-window events are censored.
    """
    requested, actual = [], []
    for day in range(handoff, min(plan["n"], len(days))):
        requested.extend({"day": day, "tile": int(t), "crop": crop} for t, crop in plan["plant"][day].items())
        actual.extend({"day": day, "tile": int(row[0]), "crop": str(row[1])} for row in days[day].get("plants", []))
    unmatched = set(range(len(requested)))
    used_actual, matched = set(), []
    for exact_only in (True, False):
        for ai, observed in enumerate(actual):
            if ai in used_actual:
                continue
            choices = [pi for pi in unmatched if requested[pi]["tile"] == observed["tile"]
                       and requested[pi]["crop"] == observed["crop"]
                       and 0 <= observed["day"] - requested[pi]["day"] <= (0 if exact_only else max_lateness)]
            if not choices:
                continue
            pi = max(choices, key=lambda idx: requested[idx]["day"])
            unmatched.remove(pi)
            used_actual.add(ai)
            matched.append({**requested[pi], "actual_day": observed["day"], "delay": observed["day"] - requested[pi]["day"]})
    missing = [{**requested[i], "terminal_window_censored": requested[i]["day"] + max_lateness >= min(plan["n"], len(days))}
               for i in sorted(unmatched)]
    extra = [row for ai, row in enumerate(actual) if ai not in used_actual]
    return {"planned": len(requested), "successful": len(actual),
            "on_time": sum(row["delay"] == 0 for row in matched), "late": sum(row["delay"] > 0 for row in matched),
            "unmatched_planned": len(missing), "unmatched_actual": len(extra),
            "missing_by_crop": dict(Counter(row["crop"] for row in missing)),
            "late_by_crop": dict(Counter(row["crop"] for row in matched if row["delay"] > 0)),
            "missed_before_terminal_window": sum(not row["terminal_window_censored"] for row in missing),
            "max_lateness_match_window": max_lateness,
            "late_events": [row for row in matched if row["delay"] > 0], "unmatched_planned_events": missing,
            "unmatched_actual_events": extra}


def retirement_audit(plan, days, handoff=11):
    intended, observed = [], []
    for day in range(handoff, min(plan["n"] - 1, len(days) - 1)):
        before = plan["animals_by_day"][day - 1]
        after = plan["animals_by_day"][day]
        for tile, species in before.items():
            if after.get(tile) != species:
                intended.append({"day": day, "tile": int(tile), "species": species, "first_unfed_day": day - 1})
        b0, b1 = actual_board(days[day]), actual_board(days[day + 1])
        if b0 is not None and b1 is not None:
            observed.extend({"day": day, "tile": tile, "species": species}
                            for tile, species in enumerate(b0) if species in ANIMALS and b1[tile] != species)
    free = set(range(len(intended)))
    classified = []
    for event in observed:
        matching = [i for i in free if intended[i]["tile"] == event["tile"] and intended[i]["species"] == event["species"]
                    and abs(intended[i]["day"] - event["day"]) <= 2]
        if matching:
            idx = min(matching, key=lambda i: abs(intended[i]["day"] - event["day"]))
            free.remove(idx)
            delta = event["day"] - intended[idx]["day"]
            classified.append({**event, "classification": "planned_same_day" if delta == 0 else "planned_timing_drift",
                               "planned_day": intended[idx]["day"], "day_delta": delta})
        else:
            classified.append({**event, "classification": "outside_tile_plan"})
    first_day_checks = []
    for event in intended:
        # Start of the exit day is end of the first unfed day, still occupied.
        board = actual_board(days[event["day"]])
        if board is not None:
            first_day_checks.append({**event, "physically_present_after_first_unfed_day": board[event["tile"]] == event["species"]})
    species_day_matches = sum((Counter((r["day"], r["species"]) for r in observed)
                               & Counter((r["day"], r["species"]) for r in intended)).values())
    return {"planned_exits": len(intended), "observed_exits": len(observed),
            "classification_counts": dict(Counter(row["classification"] for row in classified)),
            "same_species_same_day_matches_ignoring_tile": species_day_matches,
            "planned_exits_not_observed_at_matching_tile": [intended[i] for i in sorted(free)],
            "missing_after_first_unfed_day": [row for row in first_day_checks if not row["physically_present_after_first_unfed_day"]],
            "events": classified,
            "interpretation": "Plan-consistent exits include intended retirement; an outside-plan exit is not itself proof of economic harm. Per-tile feed history is absent from this ledger."}


def metrics(ledger, handoff=11):
    totals = Counter()
    products = {field: Counter() for field in ("rev", "sold", "harv", "spend", "overflow", "eff", "noeff", "died", "failed")}
    for row in as_days(ledger)[handoff:30]:
        for field in products:
            products[field].update(counter(row.get(field)))
        totals.update({"moves": int(row.get("move", 0)), "ineffective_moves": int(row.get("move_noeff", 0)),
                       "passes": int(row.get("passes", 0)), "hires": len(row.get("hires", [])),
                       "wages": float(row.get("wages", 0)), "land": float(row.get("land", 0)),
                       "unit_steps": int(row.get("unit_steps", 0)),
                       "effective_nonmovement_actions": sum(counter(row.get("eff")).values()),
                       "effective_farm_operations": sum(v for k, v in counter(row.get("eff")).items() if k in FARM_OPS)})
    own, rival = ledger.get("final"), ledger.get("opp_final")
    result = dict(totals)
    result.update(own_final=own, rival_final=rival, margin=None if own is None or rival is None else own - rival,
                  revenue=sum(products["rev"].values()), input_spend=sum(products["spend"].values()),
                  harvested_units=sum(products["harv"].values()), deleted_units=sum(products["overflow"].values()),
                  by_product={field: dict(value) for field, value in products.items()})
    return result


def difference(current, baseline):
    out = {key: current[key] - baseline[key] for key in current if key != "by_product"
           and isinstance(current[key], (int, float)) and isinstance(baseline.get(key), (int, float))}
    out["by_product"] = {}
    for field, values in current["by_product"].items():
        keys = set(values) | set(baseline["by_product"][field])
        out["by_product"][field] = {key: values.get(key, 0) - baseline["by_product"][field].get(key, 0) for key in sorted(keys)
                                     if values.get(key, 0) != baseline["by_product"][field].get(key, 0)}
    return out


def audit_world(plan, ledger, baseline=None):
    days = as_days(ledger)
    handoff = int(plan.get("planner_metadata", {}).get("handoff_day", 11))
    divergence = []
    for day in range(handoff, min(plan["n"], len(days))):
        actual = actual_board(days[day])
        if actual is None:
            divergence.append({"day": day, "board_missing": True})
            continue
        expected = planned_board(plan, day)
        wrong = [{"tile": tile, "planned": p, "actual": a} for tile, (p, a) in enumerate(zip(expected, actual)) if p != a]
        p_count, a_count = Counter(expected), Counter(actual)
        differences = {kind: a_count[kind] - p_count[kind] for kind in sorted(set(p_count) | set(a_count)) if a_count[kind] != p_count[kind]}
        divergence.append({"day": day, "wrong_tiles": len(wrong), "type_count_l1": sum(abs(v) for v in differences.values()),
                           "planned_type_counts": dict(p_count), "actual_type_counts": dict(a_count),
                           "actual_minus_planned_type_counts": differences, "tiles": wrong,
                           "planned_hires": plan["hands"][day], "actual_hires": len(days[day].get("hires", [])),
                           "planned_plants": dict(Counter(plan["plant"][day].values())), "successful_plants": days[day].get("plant", {})})
    summary = metrics(ledger, handoff)
    engine = ledger.get("engine_audit")
    full_daily_coverage = len(days) >= plan["n"] and all(row.get("cash") is not None for row in days[handoff:plan["n"]])
    engine_verified = bool(engine and engine.get("statuses") == ["DONE", "DONE"] and engine.get("steps") == 720)
    result = {"metrics": summary, "daily_plan_execution": divergence,
              "full_daily_coverage": full_daily_coverage, "engine_completion_verified": engine_verified,
              "quality_summary_eligible": full_daily_coverage and engine_verified,
              "first_missing_cash_day": next((d for d in range(handoff, min(plan["n"], len(days))) if days[d].get("cash") is None), None),
              "plantings": event_matches(plan, days, handoff), "retirements": retirement_audit(plan, days, handoff),
              "type_error_tile_days": sum(row.get("wrong_tiles", 0) for row in divergence),
              "count_error_l1_days": sum(row.get("type_count_l1", 0) for row in divergence),
              "engine_audit": ledger.get("engine_audit"), "cash_audit": ledger.get("cash_audit")}
    if baseline is not None:
        base_metrics = metrics(baseline, handoff)
        base_days = as_days(baseline)
        base_engine = baseline.get("engine_audit")
        result["paired_quality_summary_eligible"] = bool(result["quality_summary_eligible"] and base_engine
            and base_engine.get("statuses") == ["DONE", "DONE"] and base_engine.get("steps") == 720
            and len(base_days) >= plan["n"] and all(row.get("cash") is not None for row in base_days[handoff:plan["n"]]))
        result["baseline_metrics"] = base_metrics
        result["versus_baseline"] = difference(summary, base_metrics)
    return result


def discover(roots, arm):
    files = set()
    for root in map(Path, roots):
        if root.is_file():
            files.add(root)
        else:
            files.update(root.glob(f"**/ledgers/{arm}/*.json"))
            if root.name == arm and root.parent.name == "ledgers":
                files.update(root.glob("*.json"))
    rows, duplicates = {}, []
    for path in sorted(files):
        ledger = read(path)
        episode = str(ledger.get("episode", path.stem))
        if not ledger.get("days"):
            continue
        content = json.dumps({key: ledger.get(key) for key in ("days", "final", "opp_final")}, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(content.encode()).hexdigest()
        if episode in rows:
            old = rows[episode]
            if old[2] != digest:
                raise ValueError(f"Conflicting immutable ledgers for {arm}/{episode}: {old[0]} and {path}")
            duplicates.append(str(path.resolve()))
            continue
        rows[episode] = (str(path.resolve()), ledger, digest)
    return rows, duplicates


def summarize(worlds):
    aggregate = {"games": len(worlds),
                 "full_daily_coverage_games": sum(w["full_daily_coverage"] for w in worlds.values()),
                 "engine_verified_complete_games": sum(w["engine_completion_verified"] for w in worlds.values()),
                 "performance_summary_games": sum(w["quality_summary_eligible"] for w in worlds.values()),
                 "paired_performance_summary_games": sum(w.get("paired_quality_summary_eligible", False) for w in worlds.values())}
    for category in ("metrics", "versus_baseline"):
        eligibility = "quality_summary_eligible" if category == "metrics" else "paired_quality_summary_eligible"
        rows = [world[category] for world in worlds.values() if category in world and world.get(eligibility)]
        numeric = sorted(set().union(*(set(row) for row in rows)) - {"by_product"}) if rows else []
        aggregate[category] = {key: sum(float(row.get(key) or 0) for row in rows) / len(rows) for key in numeric} if rows else {}
        if rows:
            fields = {field for row in rows for field in row["by_product"]}
            aggregate[category]["by_product"] = {}
            for field in sorted(fields):
                sums = Counter()
                for row in rows:
                    sums.update(row["by_product"].get(field, {}))
                aggregate[category]["by_product"][field] = {key: value / len(rows) for key, value in sorted(sums.items())}
    aggregate["mean_wrong_tile_days"] = sum(w["type_error_tile_days"] for w in worlds.values()) / max(1, len(worlds))
    aggregate["mean_type_count_l1_days"] = sum(w["count_error_l1_days"] for w in worlds.values()) / max(1, len(worlds))
    for field in ("planned", "successful", "on_time", "late", "unmatched_planned", "unmatched_actual", "missed_before_terminal_window"):
        aggregate["plant_" + field] = sum(w["plantings"][field] for w in worlds.values())
    retirement_counts = Counter()
    for world in worlds.values():
        retirement_counts.update(world["retirements"]["classification_counts"])
    aggregate["retirement_classifications"] = dict(retirement_counts)
    return aggregate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--baseline-arm")
    parser.add_argument("--episodes", default="")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    plans = read(args.plans)
    ledgers, duplicates = discover(args.runs, args.arm)
    baseline, baseline_duplicates = discover(args.runs, args.baseline_arm) if args.baseline_arm else ({}, [])
    selected = set(args.episodes.split(",")) if args.episodes else set(ledgers)
    worlds, missing_plan = {}, []
    for episode, (path, ledger, digest) in ledgers.items():
        if episode not in selected:
            continue
        if episode not in plans:
            missing_plan.append(episode)
            continue
        worlds[episode] = audit_world(plans[episode], ledger, baseline[episode][1] if episode in baseline else None)
        worlds[episode].update(ledger_path=path, ledger_content_sha256=digest)
        if episode in baseline:
            worlds[episode]["baseline_ledger_path"] = baseline[episode][0]
    output = {"arm": args.arm, "baseline_arm": args.baseline_arm, "summary": summarize(worlds), "worlds": worlds,
              "duplicate_identical_ledgers": duplicates, "duplicate_identical_baselines": baseline_duplicates,
              "missing_plan_episodes": missing_plan,
              "measurement_limits": ["Only harvested output is observed; production generation and yield-cap losses are not logged.",
                                     "Performance aggregates require all daily cash observations plus verified DONE/DONE engine completion; incomplete/unverified records remain in diagnostics only.",
                                     "WEED and EMPTY are equivalent for planned tile-type comparisons.",
                                     "No end-of-season midnight is executed, so D29 animal exits/physical EOD are censored.",
                                     "An animal exit is not labelled economically harmful merely because it occurred.",
                                     "Plant matches use same tile and crop, exact day first then up to six days late."]}
    destination = args.out or ROOT / "results/fresh/semantic_tile_20260928" / f"execution_audit_{args.arm}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"path": str(destination), "summary": output["summary"]}, indent=2))


if __name__ == "__main__":
    main()

"""Summarize complete or in-progress crop-cohort benchmark results.

Headline means use complete two-seat seed clusters.  Partial seat pairs remain
visible as diagnostics but are never silently promoted to independent samples.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean


DEFAULT_INPUT = Path(
    r"C:\Users\xyygl\Documents\kaggriculture\results\fresh\crop_cohorts\discovery"
)
TELEMETRY_LABELS = {
    "plot_commitments": "plot takeovers",
    "inventory_delta_harvest_units": "inventory-delta harvest units",
    "plant_failures": "plant failures",
    "missing_plants": "missing plants",
    "seed_orders": "seed units requested",
    "borrowed_hands": "borrowed hands",
    "overridden_commands": "overridden commands",
    "sales_requested": "sale units requested",
    "overlay_errors": "overlay errors",
    "planting_cycles": "confirmed planting cycles",
    "confirmed_harvest_units": "confirmed harvest units",
    "expired_unharvested_yield": "expired unharvested yield",
    "seed_purchases_requested": "seed units requested",
    "changed_crop_commands": "changed crop commands",
    "contract_errors": "contract errors",
    "overnight_auto_drop_harvests": "overnight harvests",
    "overnight_auto_drop_units": "overnight harvest units",
    "carrot_sale_units_requested": "carrot sale units requested",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def policy_name(policy: dict) -> str:
    return Path(policy["path"]).stem.removeprefix("v45_cohort_")


def own_ledger(row: dict) -> dict:
    return row["ledger"][int(row["job"]["seat"])]


def number(mapping: dict, key: str) -> float:
    return float(mapping.get(key, 0))


def telemetry(stats: dict) -> tuple[str, dict[str, float]]:
    """Normalize field names without conflating the two overlays' semantics."""
    commitments = stats.get("commitments")
    native_fields = {
        "harvest_units", "expired_unharvested_yield", "seedpurchases",
        "changedcommands", "contract_errors",
    }
    if native_fields & set(stats) or isinstance(commitments, (int, float)):
        return "native_crop_swap_v1", {
            "planting_cycles": number(stats, "commitments"),
            "confirmed_harvest_units": number(stats, "harvest_units"),
            "expired_unharvested_yield": number(stats, "expired_unharvested_yield"),
            "seed_purchases_requested": number(stats, "seedpurchases"),
            "changed_crop_commands": number(stats, "changedcommands"),
            "contract_errors": number(stats, "contract_errors"),
            "overnight_auto_drop_harvests": number(stats, "overnight_auto_drop_harvests"),
            "overnight_auto_drop_units": number(stats, "overnight_auto_drop_units"),
            "carrot_sale_units_requested": number(stats, "carrotsellrequests"),
        }
    if isinstance(commitments, list):
        return "borrowed_route_cohort_v1", {
            "plot_commitments": float(len(commitments)),
            "inventory_delta_harvest_units": number(stats, "harvested_units"),
            "plant_failures": number(stats, "plant_failures"),
            "missing_plants": number(stats, "missing_plants"),
            "seed_orders": number(stats, "seed_orders"),
            "borrowed_hands": number(stats, "borrowed_hands"),
            "overridden_commands": number(stats, "commands"),
            "sales_requested": number(stats, "sales_requested"),
            "overlay_errors": number(stats, "errors"),
        }
    return "unknown", {
        "raw_" + str(key): float(value)
        for key, value in stats.items() if isinstance(value, (int, float))
    }


def matched_pair(candidate: dict, baseline: dict) -> dict:
    candidate_ledger, baseline_ledger = own_ledger(candidate), own_ledger(baseline)
    stats = candidate.get("candidate_stats") or {}
    telemetry_schema, telemetry_values = telemetry(stats)
    active_keys = ("planting_cycles", "changed_crop_commands", "seed_purchases_requested",
                   "carrot_sale_units_requested", "plot_commitments", "overridden_commands",
                   "seed_orders", "sales_requested")
    active_overlay = any(telemetry_values.get(key, 0) != 0 for key in active_keys)
    same_shops = candidate.get("shops", {}).get("realized") == baseline.get("shops", {}).get("realized")
    exact_identity = (
        candidate.get("final", {}).get("cash") == baseline.get("final", {}).get("cash")
        and candidate.get("ledger") == baseline.get("ledger")
        and same_shops
    )
    commitments = stats.get("commitments") if isinstance(stats.get("commitments"), list) else []
    crops = sorted({str(item.get("crop")) for item in commitments if item.get("crop")})
    products = sorted(
        set(candidate_ledger.get("sold_units", {})) | set(baseline_ledger.get("sold_units", {}))
        | set(candidate_ledger.get("revenue", {})) | set(baseline_ledger.get("revenue", {}))
    )
    sales = {}
    for crop in products:
        baseline_units = number(baseline_ledger.get("sold_units", {}), crop)
        candidate_units = number(candidate_ledger.get("sold_units", {}), crop)
        baseline_revenue = number(baseline_ledger.get("revenue", {}), crop)
        candidate_revenue = number(candidate_ledger.get("revenue", {}), crop)
        sales[crop] = {
            "baseline_units": baseline_units,
            "cohort_units": candidate_units,
            "unit_delta": candidate_units - baseline_units,
            "baseline_revenue": baseline_revenue,
            "cohort_revenue": candidate_revenue,
            "revenue_delta": candidate_revenue - baseline_revenue,
        }
    return {
        "opponent": candidate["job"]["opponent"],
        "seed": int(candidate["job"]["seed"]),
        "seat": int(candidate["job"]["seat"]),
        "cash_delta": candidate["final"]["policy_cash"] - baseline["final"]["policy_cash"],
        "margin_delta": candidate["final"]["margin"] - baseline["final"]["margin"],
        "candidate_margin": candidate["final"]["margin"],
        "baseline_margin": baseline["final"]["margin"],
        "hire_spend_delta": (
            number(candidate_ledger.get("spend", {}), "HIRE")
            - number(baseline_ledger.get("spend", {}), "HIRE")
        ),
        "land_spend_delta": (
            number(candidate_ledger.get("spend", {}), "BUY_LAND")
            - number(baseline_ledger.get("spend", {}), "BUY_LAND")
        ),
        "commitment_crops": crops,
        "telemetry_schema": telemetry_schema,
        "telemetry": telemetry_values,
        "active_overlay": active_overlay,
        "exact_outcome_ledger_shop_identity": exact_identity,
        "same_realized_shops": same_shops,
        "telemetry_errors": sum(
            value for key, value in telemetry_values.items() if "error" in key
        ),
        "sales": sales,
    }


def average_sales(rows: list[dict]) -> dict:
    products = sorted({crop for row in rows for crop in row["sales"]})
    result = {}
    for crop in products:
        keys = ("baseline_units", "cohort_units", "unit_delta",
                "baseline_revenue", "cohort_revenue", "revenue_delta")
        result[crop] = {
            key: mean(row["sales"].get(crop, {}).get(key, 0) for row in rows)
            for key in keys
        }
    return result


def outcome_record(values) -> dict:
    values = list(values)
    return {
        "wins": sum(value > 0 for value in values),
        "ties": sum(value == 0 for value in values),
        "losses": sum(value < 0 for value in values),
    }


def summarize_pairs(pairs: list[dict], expected_clusters: list[tuple[str, int]]) -> dict:
    grouped = defaultdict(list)
    for pair in pairs:
        grouped[(pair["opponent"], pair["seed"])].append(pair)

    clusters, partial = [], []
    for key in expected_clusters:
        seats = sorted(grouped.get(key, []), key=lambda row: row["seat"])
        if {row["seat"] for row in seats} != {0, 1}:
            partial.append({"opponent": key[0], "seed": key[1],
                            "matched_seats": [row["seat"] for row in seats]})
            continue
        scalar_keys = ("cash_delta", "margin_delta", "candidate_margin", "baseline_margin",
                       "hire_spend_delta", "land_spend_delta")
        cluster = {"opponent": key[0], "seed": key[1], "seats": [0, 1]}
        cluster.update({key_name: mean(row[key_name] for row in seats) for key_name in scalar_keys})
        cluster["commitment_crops"] = sorted(
            {crop for row in seats for crop in row["commitment_crops"]}
        )
        schemas = sorted({row["telemetry_schema"] for row in seats})
        telemetry_keys = sorted({metric for row in seats for metric in row["telemetry"]})
        cluster["telemetry_schema"] = schemas[0] if len(schemas) == 1 else "mixed:" + ",".join(schemas)
        cluster["telemetry"] = {
            metric: mean(row["telemetry"].get(metric, 0) for row in seats)
            for metric in telemetry_keys
        }
        cluster["sales"] = average_sales(seats)
        clusters.append(cluster)

    result = {
        "expected_seed_clusters": len(expected_clusters),
        "complete_seed_clusters": len(clusters),
        "partial_or_missing_seed_clusters": partial,
        "matched_seat_pairs": len(pairs),
        "expected_seat_pairs": 2 * len(expected_clusters),
        "complete_clusters": clusters,
        "partial_pair_means_diagnostic_only": None,
        "cluster_means": None,
        "activity": {
            "active_overlay_games": sum(pair["active_overlay"] for pair in pairs),
            "zero_action_games": sum(not pair["active_overlay"] for pair in pairs),
            "zero_action_exact_identity_games": sum(
                not pair["active_overlay"] and pair["exact_outcome_ledger_shop_identity"]
                for pair in pairs
            ),
            "zero_action_nonidentity_games": sum(
                not pair["active_overlay"] and not pair["exact_outcome_ledger_shop_identity"]
                for pair in pairs
            ),
            "active_game_mean_cash_delta_diagnostic_only": (
                mean(pair["cash_delta"] for pair in pairs if pair["active_overlay"])
                if any(pair["active_overlay"] for pair in pairs) else None
            ),
            "active_game_mean_margin_delta_diagnostic_only": (
                mean(pair["margin_delta"] for pair in pairs if pair["active_overlay"])
                if any(pair["active_overlay"] for pair in pairs) else None
            ),
        },
        "same_realized_shops": {
            "same": sum(pair["same_realized_shops"] for pair in pairs),
            "different": sum(not pair["same_realized_shops"] for pair in pairs),
            "rate": (mean(pair["same_realized_shops"] for pair in pairs) if pairs else None),
        },
        "telemetry_error_total": sum(pair["telemetry_errors"] for pair in pairs),
        "telemetry_error_games": sum(pair["telemetry_errors"] != 0 for pair in pairs),
        "worst_matched_game": None,
    }
    if pairs:
        worst_margin = min(pairs, key=lambda row: row["margin_delta"])
        worst_cash = min(pairs, key=lambda row: row["cash_delta"])
        result["worst_matched_game"] = {
            "margin_delta": {key: worst_margin[key] for key in
                             ("opponent", "seed", "seat", "margin_delta", "cash_delta")},
            "cash_delta": {key: worst_cash[key] for key in
                           ("opponent", "seed", "seat", "margin_delta", "cash_delta")},
        }
        result["partial_pair_means_diagnostic_only"] = {
            "cash_delta": mean(row["cash_delta"] for row in pairs),
            "margin_delta": mean(row["margin_delta"] for row in pairs),
        }
    if clusters:
        scalar_keys = ("cash_delta", "margin_delta", "candidate_margin", "baseline_margin",
                       "hire_spend_delta", "land_spend_delta")
        schemas = sorted({cluster["telemetry_schema"] for cluster in clusters})
        telemetry_keys = sorted({metric for cluster in clusters for metric in cluster["telemetry"]})
        result["cluster_means"] = {
            **{key: mean(cluster[key] for cluster in clusters) for key in scalar_keys},
            "telemetry_schema": schemas[0] if len(schemas) == 1 else "mixed:" + ",".join(schemas),
            "telemetry": {
                metric: mean(cluster["telemetry"].get(metric, 0) for cluster in clusters)
                for metric in telemetry_keys
            },
            "actual_candidate_win_tie_loss": outcome_record(
                cluster["candidate_margin"] for cluster in clusters
            ),
            "paired_delta_win_tie_loss": outcome_record(
                cluster["margin_delta"] for cluster in clusters
            ),
            "baseline_win_tie_loss": outcome_record(
                cluster["baseline_margin"] for cluster in clusters
            ),
            "sales_by_crop": average_sales(clusters),
            "worst_seed_by_margin_delta": min(
                ({"opponent": cluster["opponent"], "seed": cluster["seed"],
                  "margin_delta": cluster["margin_delta"],
                  "candidate_margin": cluster["candidate_margin"]}
                 for cluster in clusters),
                key=lambda row: row["margin_delta"],
            ),
            "minimum_cluster_cash_delta": min(cluster["cash_delta"] for cluster in clusters),
            "minimum_cluster_margin_delta": min(cluster["margin_delta"] for cluster in clusters),
        }
    return result


def pool_opponents_by_seed(pairs: list[dict], opponents: list[str], seeds: list[int]) -> dict:
    """Average opponents and seats within a seed; require the full requested block."""
    grouped = defaultdict(list)
    for pair in pairs:
        grouped[pair["seed"]].append(pair)
    complete, incomplete = [], []
    expected_keys = {(opponent, seat) for opponent in opponents for seat in (0, 1)}
    for seed in seeds:
        rows = grouped.get(seed, [])
        present = {(row["opponent"], row["seat"]) for row in rows}
        if present != expected_keys:
            incomplete.append({"seed": seed, "present_games": len(rows),
                               "expected_games": len(expected_keys)})
            continue
        complete.append({
            "seed": seed,
            "cash_delta": mean(row["cash_delta"] for row in rows),
            "margin_delta": mean(row["margin_delta"] for row in rows),
            "candidate_margin": mean(row["candidate_margin"] for row in rows),
            "active_overlay_games": sum(row["active_overlay"] for row in rows),
            "zero_action_games": sum(not row["active_overlay"] for row in rows),
        })
    return {
        "definition": "mean over all requested opponents and both seats within each seed",
        "complete_seeds": complete,
        "incomplete_seeds": incomplete,
        "mean_cash_delta": mean(row["cash_delta"] for row in complete) if complete else None,
        "mean_margin_delta": mean(row["margin_delta"] for row in complete) if complete else None,
        "delta_win_tie_loss": outcome_record(row["margin_delta"] for row in complete),
        "worst_seed": min(complete, key=lambda row: row["margin_delta"]) if complete else None,
    }


def load_panel(input_dir: Path) -> tuple[dict, list[dict], list[dict]]:
    manifest = read_json(input_dir / "manifest.json")
    valid, problems = [], []
    for path in sorted((input_dir / "games").glob("*.json")):
        try:
            row = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            problems.append({"path": str(path), "error": f"unreadable JSON: {exc}"})
            continue
        if row.get("status") != "ok":
            problems.append({"path": str(path), "error": row.get("error", "status is not ok")})
            continue
        try:
            job = row["job"]
            assert job["policy_id"] and job["opponent"]
            assert int(job["seat"]) in (0, 1)
            assert "policy_cash" in row["final"] and "margin" in row["final"]
            assert len(row["ledger"]) == 2
        except (AssertionError, KeyError, TypeError, ValueError) as exc:
            problems.append({"path": str(path), "error": f"invalid successful row: {exc}"})
            continue
        valid.append(row)
    return manifest, valid, problems


def analyze(input_dir: Path) -> dict:
    manifest, rows, problems = load_panel(input_dir)
    policies = manifest["policies"]
    baseline = next(policy for policy in policies if policy["kind"] == "baseline")
    candidates = [policy for policy in policies if policy["kind"] == "candidate"]
    opponents = list(manifest["opponents"])
    seeds = [int(seed) for seed in manifest["seeds"]]
    expected_keys = {
        (policy["id"], opponent, seed, seat)
        for policy in policies for opponent in opponents for seed in seeds for seat in (0, 1)
    }
    index, duplicates = {}, []
    for row in rows:
        job = row["job"]
        key = (job["policy_id"], job["opponent"], int(job["seed"]), int(job["seat"]))
        if key in index:
            duplicates.append(key)
        index[key] = row
    present_expected = set(index) & expected_keys
    unexpected = sorted(set(index) - expected_keys)

    variants = {}
    total_complete_clusters = 0
    for candidate in candidates:
        pairs = []
        for opponent in opponents:
            for seed in seeds:
                for seat in (0, 1):
                    candidate_row = index.get((candidate["id"], opponent, seed, seat))
                    baseline_row = index.get((baseline["id"], opponent, seed, seat))
                    if candidate_row and baseline_row:
                        pairs.append(matched_pair(candidate_row, baseline_row))
        by_opponent = {}
        for opponent in opponents:
            opponent_pairs = [pair for pair in pairs if pair["opponent"] == opponent]
            by_opponent[opponent] = summarize_pairs(
                opponent_pairs, [(opponent, seed) for seed in seeds]
            )
        overall = summarize_pairs(pairs, [(opponent, seed) for opponent in opponents for seed in seeds])
        total_complete_clusters += overall["complete_seed_clusters"]
        variants[policy_name(candidate)] = {
            "policy_id": candidate["id"],
            "path": candidate["path"],
            "by_opponent": by_opponent,
            "overall": overall,
            "pooled_opponents_by_seed": pool_opponents_by_seed(pairs, opponents, seeds),
        }

    expected_variant_clusters = len(candidates) * len(opponents) * len(seeds)
    complete = len(present_expected) == len(expected_keys) and not problems and not duplicates
    return {
        "status": "COMPLETE_DIAGNOSTIC" if complete else "INCOMPLETE_DIAGNOSTIC",
        "input": str(input_dir),
        "progress": {
            "valid_expected_games": len(present_expected),
            "expected_games": len(expected_keys),
            "manifest_expected_games": manifest.get("games"),
            "complete_variant_opponent_seed_clusters": total_complete_clusters,
            "expected_variant_opponent_seed_clusters": expected_variant_clusters,
            "missing_games": len(expected_keys - present_expected),
            "failed_or_malformed": problems,
            "duplicate_keys": duplicates,
            "unexpected_keys": unexpected,
        },
        "unit_of_analysis": (
            "Each opponent-seed cluster averages seats 0 and 1. Seat results are paired "
            "replicates, not independent samples."
        ),
        "outcome_definition": {
            "actual_candidate_win_tie_loss": "sign of candidate margin versus its opponent",
            "paired_delta_win_tie_loss": "sign of candidate-minus-baseline margin delta",
        },
        "interpretation_warnings": [
            "This is a diagnostic panel; incomplete snapshots must not be used for selection.",
            "missing_plants increments when a managed tile is first observed as WEED on a later "
            "day. It can represent natural crop expiry as well as a watering failure/death.",
            "commitments count scheduled plot takeovers, while plant_failures checks whether a "
            "requested plant exists on the following turn.",
            "sales_requested is agent telemetry; sold units and revenue come from successful "
            "engine ledger transactions.",
            "Native-swap commitments count confirmed planting cycles, not unique plots. Its "
            "harvest_units counter confirms disappearance of a ripe managed crop after a harvest "
            "request; it is not the borrowed-route overlay's inventory-delta counter.",
            "Native-swap expired_unharvested_yield is a separate observed-yield counter and is "
            "not aliased to borrowed-route missing_plants.",
        ],
        "variants": variants,
    }


def fmt(value, decimals=1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def wtl(record: dict | None) -> str:
    if not record:
        return "—"
    return f"{record['wins']}/{record['ties']}/{record['losses']}"


def telemetry_text(means: dict) -> str:
    schema = means.get("telemetry_schema")
    values = means.get("telemetry") or {}
    if not schema or not values:
        return "—"
    rendered = "; ".join(
        f"{TELEMETRY_LABELS.get(key, key)}={fmt(value)}" for key, value in values.items()
    )
    return f"{schema}: {rendered}"


def markdown(report: dict) -> str:
    progress = report["progress"]
    lines = [
        "# Crop cohort diagnostic snapshot",
        "",
        f"**{report['status']}** — {progress['valid_expected_games']}/{progress['expected_games']} "
        f"expected games are valid; {progress['complete_variant_opponent_seed_clusters']}/"
        f"{progress['expected_variant_opponent_seed_clusters']} candidate/opponent/seed clusters "
        "have both seats.",
        "",
        "Headline means below use only complete two-seat seed clusters. `Actual W/T/L` is the "
        "candidate's margin against the opponent; `Delta W/T/L` is candidate-minus-baseline "
        "margin. Those are deliberately different outcomes.",
        "",
        "| Variant | Opponent | Pairs | Clusters | Δ cash | Δ margin | Actual W/T/L | Delta W/T/L | Δ HIRE | Δ LAND | Telemetry (schema-specific means) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for variant, data in report["variants"].items():
        for opponent, summary in data["by_opponent"].items():
            means = summary["cluster_means"] or {}
            lines.append(
                f"| {variant} | {opponent} | {summary['matched_seat_pairs']}/"
                f"{summary['expected_seat_pairs']} | {summary['complete_seed_clusters']}/"
                f"{summary['expected_seed_clusters']} | {fmt(means.get('cash_delta'))} | "
                f"{fmt(means.get('margin_delta'))} | "
                f"{wtl(means.get('actual_candidate_win_tie_loss'))} | "
                f"{wtl(means.get('paired_delta_win_tie_loss'))} | "
                f"{fmt(means.get('hire_spend_delta'))} | {fmt(means.get('land_spend_delta'))} | "
                f"{telemetry_text(means)} |"
            )

    lines += [
        "",
        "## Activity and integrity",
        "",
        "A zero-action game has no cohort command, seed, or sale request. Identity additionally "
        "requires equal final cash, full ledgers, and realized shops.",
        "",
        "| Variant | Opponent | Active | Zero action | Zero identity | Zero nonidentity | Same shops | Telemetry errors | Worst game Δ margin |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, data in report["variants"].items():
        for opponent, summary in data["by_opponent"].items():
            activity, shops = summary["activity"], summary["same_realized_shops"]
            worst = summary["worst_matched_game"]
            lines.append(
                f"| {variant} | {opponent} | {activity['active_overlay_games']} | "
                f"{activity['zero_action_games']} | {activity['zero_action_exact_identity_games']} | "
                f"{activity['zero_action_nonidentity_games']} | {shops['same']}/"
                f"{shops['same'] + shops['different']} | {summary['telemetry_error_total']:.0f} "
                f"in {summary['telemetry_error_games']} games | "
                f"{fmt(worst['margin_delta']['margin_delta'] if worst else None)} |"
            )

    lines += ["", "## Opponent-pooled seed means", "",
              "Only seeds with every requested opponent and both seats are included.", "",
              "| Variant | Seed | Δ cash | Δ margin | Active games | Zero-action games |",
              "|---|---:|---:|---:|---:|---:|"]
    for variant, data in report["variants"].items():
        pooled = data["pooled_opponents_by_seed"]
        if not pooled["complete_seeds"]:
            lines.append(f"| {variant} | — | — | — | — | — |")
        for row in pooled["complete_seeds"]:
            lines.append(f"| {variant} | {row['seed']} | {fmt(row['cash_delta'])} | "
                         f"{fmt(row['margin_delta'])} | {row['active_overlay_games']} | "
                         f"{row['zero_action_games']} |")

    lines += [
        "",
        "## Successful output sales",
        "",
        "Mean units and revenue per complete opponent-seed cluster. Rows include products whose "
        "units or revenue changed, plus the crop named by each variant.",
        "",
        "| Variant | Crop | Baseline units | Cohort units | Δ units | Baseline revenue | Cohort revenue | Δ revenue |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, data in report["variants"].items():
        means = data["overall"]["cluster_means"] or {}
        sales = means.get("sales_by_crop", {})
        named_crop = "CARROT" if "carrot" in variant.lower() else "TOMATO"
        selected = {
            crop: row for crop, row in sales.items()
            if crop == named_crop or row["unit_delta"] or row["revenue_delta"]
        }
        if not selected:
            lines.append(f"| {variant} | — | — | — | — | — | — | — |")
        for crop, row in selected.items():
            lines.append(
                f"| {variant} | {crop} | {fmt(row['baseline_units'])} | "
                f"{fmt(row['cohort_units'])} | {fmt(row['unit_delta'])} | "
                f"{fmt(row['baseline_revenue'])} | {fmt(row['cohort_revenue'])} | "
                f"{fmt(row['revenue_delta'])} |"
            )

    lines += [
        "",
        "> `missing_plants` is not a clean death counter: it can include natural expiry when a "
        "managed crop becomes WEED, as well as missed-care death.",
        "",
        "> Native-swap `commitments` means confirmed planting cycles, not unique plots. "
        "`harvest_units` and `expired_unharvested_yield` retain their native-swap definitions and "
        "are not merged with the borrowed-route counters.",
    ]
    if progress["failed_or_malformed"]:
        lines += ["", f"> Failed or malformed result files: {len(progress['failed_or_malformed'])}."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="benchmark directory containing manifest.json and games/")
    parser.add_argument("--json-out", type=Path,
                        help="optional path for the detailed machine-readable summary")
    parser.add_argument("--markdown-out", type=Path,
                        help="optional path for the concise Markdown report")
    args = parser.parse_args()
    input_dir = args.input.resolve()
    report = analyze(input_dir)
    rendered = markdown(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()

"""Build a KB115LT tile-plan input from anonymous daily farm changes.

Example (build only, no gameplay or submission):
  python scripts/build_semantic_tile_stack_20260928.py --inputs semantic_inputs.json --out plans.json

The importable make_plan API receives one semantic world. Coordinates are allowed
only in the observed opening and handoff state. Future daily input is the strict
count-only schema; source tile identities, source worker routes, and opponent
data are not used. The default passed the local DSM40 oracle-input gate:
26/40 wins, paired margin +151.575 versus exact tiling (regression p=.667).
See docs/semantic_tile_planner_20260928.md for the scope and runtime limits.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from semantic_tile_allocator_20260928 import VARIANTS
from semantic_tile_inputs_20260928 import assert_coordinate_free_days, strict_input
from semantic_tile_lifetimes_20260928 import solve_lifetimes
from semantic_tile_planner_20260928 import compile_plan
from semantic_tile_polish_20260928 import polish_plan

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_SHA256 = "2ebe94ece8ef48bf0058e620b5803c11050de7e663a63f4f41522f0758186ee0"
TILE_PLAN_FIELDS = ("n", "plant", "events", "struct_by_day", "animals_by_day", "board",
                    "harv_tiles", "removals", "land_day", "hands", "cum_sold")

# Frozen KB115LT recipe from the mission's immutable first bundle. This module
# never reads a mutable experiment spec to choose production settings.
KB115LT_RECIPE = {
    "agent": "agents/mgt_lead_kb115lt.py",
    "base": "K5b",
    "cfg": {
        "sd_tier_log_v": 1, "sd_tier_anim_harv": 1, "sd_tier_anim_c": 1,
        "sd_tier_anim_c_minv": 150.0, "sd_tier_feed_bank": 1,
        "sd_final_sell_all": 1, "sd_tier_access_drop": 1, "sd_tier_turnaround": 1,
        "sd_tier_anim_harv_end": 29, "sd_tier_spawn_h2": 1, "sd_bank_stop": 1000000000.0,
        "sd_maint_floor": {"MILK": 60, "WOOL": 100, "EGG": 45},
        "sd_tier_dump_fix": 1, "sd_tier_copy_returns": 0, "sd_tier_access_keep": 1,
        "sd_tier_copy_returns_end": 22, "sd_tier_spawn_buffer": 1,
        "sd_books_sell": ["STRAWBERRY", "WOOL", "MILK", "EGG", "TOMATO", "CARROT", "FERTILIZER", "WHEAT"],
        "sd_books_cap": 1, "sd_tier_dawn": 3, "sd_tier_dawn_shape": "learned",
        "sd_maint_floor_trail": 48, "sd_maint_floor_stat": "mean", "sd_wheat_pick_now": 1,
        "sd_tier_dump_defer": 1, "sd_books_batch": 8, "sd_books_minpx": 5,
        "sd_books_walk": 1, "sd_keep_alive_guard": 1, "sd_keep_alive_guard_min": 1,
        "sd_books_cap_free": 1, "sd_books_h0_slots": 2, "sd_tier_spawn_remap": 1,
        "sd_books_h0_lot": 0, "sd_harvest_follow_dsm": [], "sd_harvest_follow_keep": 0,
        "sd_tier_path_collect": 1, "sd_tier_path_collect_detour": 1,
        "sd_tier_deliver_skip": 1, "sd_tier_deliver_skip_min": 5,
        "sd_tier_deliver_skip_collects": 1, "sd_books_even": ["STRAWBERRY"],
        "sd_exact_retire": 1, "sd_exact_site": 2, "sd_exact_retire_prefeed": 1,
        "sd_books_source": "pace", "sd_clean": 1, "sd_tp_iface": 1,
        "sd_books_pace_map": "results/fresh/threads_20260928/dsm_sell_pace_folds.json",
    },
}


def _validate_boundary(semantic):
    """Keep coordinates and cohort identities inside the observed prefix."""
    try:
        n, handoff = semantic["n"], semantic["handoff_day"]
        if type(n) is not int or type(handoff) is not int or not 0 <= handoff < n:
            raise ValueError("Require integer 0 <= handoff_day < n")
        days, opening = semantic["days"], semantic["opening_plan"]
        if len(days) != n or any(row["day"] != day for day, row in enumerate(days)):
            raise ValueError("days must have exactly n entries in day order")
        if any(type(row["hands"]) is not int or row["hands"] < 0 for row in days):
            raise ValueError("Daily hands must be nonnegative integers")
        for field in ("plant", "struct_by_day", "animals_by_day", "harv_tiles", "removals", "hands", "cum_sold"):
            if len(opening[field]) != handoff:
                raise ValueError(f"opening_plan.{field} must stop before the handoff")
        if len(opening["board"]) != handoff + 1 or any(len(row) != 100 for row in opening["board"]):
            raise ValueError("opening_plan.board needs 100-cell boards through the handoff morning only")
        if any(type(event[0]) is not int or not 0 <= event[0] < handoff for event in opening["events"]):
            raise ValueError("opening_plan.events contains an unobserved future event")
        if any(type(day) is not int or not 0 <= day < handoff for day in opening.get("land_day", {}).values()):
            raise ValueError("opening_plan.land_day contains an unobserved future purchase")
        initial = semantic["initial_state"]
        if initial.get("day", handoff) != handoff:
            raise ValueError("initial_state must be the handoff morning")
        observed_board = initial.get("board", opening["board"][handoff])
        if len(observed_board) != 100:
            raise ValueError("initial_state.board must contain the observed100 cells")
        for tile, label in enumerate(observed_board):
            cell = initial["tiles"].get(str(tile), initial["tiles"].get(tile, {}))
            if (label == " L") != bool(cell.get("locked")):
                raise ValueError("Observed locked squares must have matching explicit locked flags")
        for tile, cell in initial["tiles"].items():
            if str(int(tile)) != str(tile) or not 0 <= int(tile) < 100:
                raise ValueError("Initial tile indices must be integers from 0 to 99")
            for field in ("planted_day", "placed_day"):
                if field in cell and (type(cell[field]) is not int or not 0 <= cell[field] < handoff):
                    raise ValueError("initial_state contains an unobserved future cohort")
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Malformed semantic handoff/prefix structure") from exc


def make_plan(semantic, variant="reuse", polish_rounds=0, *, mode="strict"):
    """Compile one independent plan without consulting any source recording.

    Strict mode discards copied ongoing-crop first-harvest counts even if present
    in a legacy input, then derives its own first-harvest markers from anonymous
    crop clocks. Expanded diagnostic mode must be explicitly requested.
    The caller's input is preserved. Zero polishing rounds returns the unpolished
    compiler output, including physical end-of-day boards and retirement markers.
    """
    if variant not in VARIANTS:
        raise ValueError(f"Unknown placement variant: {variant!r}")
    if isinstance(polish_rounds, bool) or not isinstance(polish_rounds, int) or polish_rounds < 0:
        raise ValueError("polish_rounds must be a nonnegative integer")
    if mode not in ("strict", "expanded"):
        raise ValueError("mode must be strict or expanded")
    _validate_boundary(semantic)
    try:
        if mode == "strict":
            semantic = strict_input(semantic)
        assert_coordinate_free_days(semantic)
    except (AssertionError, KeyError, TypeError) as exc:
        raise ValueError("Daily semantic input must contain only the count-based schema") from exc
    lifetimes = solve_lifetimes(semantic, use_first_harvest_counts=mode == "expanded")
    plan = compile_plan(semantic, variant=variant, lifetimes=lifetimes,
                        use_first_harvest_counts=mode == "expanded")
    if polish_rounds:
        plan, _ = polish_plan(plan, rounds=polish_rounds)
    return plan


def make_spec(plan_file, *, arm="ST28STACK", variant="reuse", polish_rounds=0, mode="strict"):
    """Return the frozen executor recipe with only its tile-plan file changed."""
    recipe = copy.deepcopy(KB115LT_RECIPE)
    recipe["cfg"]["sd_tp_file"] = Path(plan_file).resolve().as_posix()
    recipe["label"] = (f"{arm}: {mode} semantic lifetimes, {variant} placement, "
                       f"{polish_rounds} suffix-polish rounds on frozen KB115LT")
    return {arm: recipe}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True, help="One semantic world or an episode-to-world JSON mapping")
    parser.add_argument("--out", type=Path, required=True, help="Destination TilePlanView JSON")
    parser.add_argument("--spec", type=Path, help="Destination spec; defaults to <out>.spec.json")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="reuse")
    parser.add_argument("--polish-rounds", type=int, default=0)
    parser.add_argument("--mode", choices=("strict", "expanded"), default="strict",
                        help="Expanded diagnostics use copied ongoing-crop first-harvest counts")
    parser.add_argument("--arm", default="ST28STACK")
    args = parser.parse_args()
    spec_path = args.spec or args.out.with_suffix(".spec.json")
    if len({args.inputs.resolve(), args.out.resolve(), spec_path.resolve()}) != 3:
        parser.error("Input semantics, output plans, and output spec must be different files")
    # Verify the executor identity before writing a runnable benchmark spec.
    source = ROOT / KB115LT_RECIPE["agent"]
    actual_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual_hash != EXECUTOR_SHA256:
        raise RuntimeError(f"Frozen KB115LT executor changed: {actual_hash}")
    inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
    single = "initial_state" in inputs
    worlds = {"single": inputs} if single else inputs.get("worlds", inputs)
    if not worlds:
        raise ValueError("No semantic worlds supplied")
    plans = {str(ep): make_plan(semantic, args.variant, args.polish_rounds, mode=args.mode) for ep, semantic in worlds.items()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plans["single"] if single else plans, separators=(",", ":")), encoding="utf-8")
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(make_spec(args.out, arm=args.arm, variant=args.variant,
                                            polish_rounds=args.polish_rounds, mode=args.mode), indent=2), encoding="utf-8")
    print(json.dumps(dict(worlds=len(plans), plans=str(args.out.resolve()), spec=str(spec_path.resolve()),
                          variant=args.variant, polish_rounds=args.polish_rounds, mode=args.mode,
                          executor_sha256=actual_hash, plans_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest())))


if __name__ == "__main__":
    main()

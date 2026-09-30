"""Compile frozen nearest-continuation targets into paired aggregate plans.

The input is ``results/fresh/tape_gap_plans/local_transfer.json`` with:
``{cases:[{episode,seat,day,checkpoint,source,targets,baseline_targets}]}``.
No donor actions are read here.  The transfer only changes the short timed
output target; both modes begin from the actual checkpoint cohorts.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from cumulative_plan_solver import compile_checkpoint, checkpoint_to_snapshot

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "results/fresh/tape_gap_plans/local_transfer.json"
DEFAULT_OUT = ROOT / "results/fresh/tape_gap_plans/pilot"


def _policy(checkpoint):
    obs = checkpoint["observation"]
    prices = obs.get("market", {}).get("prices", {})
    day = int(checkpoint.get("day", obs["day"]))
    return {
        "hire_schedule": {str(d): 11 for d in range(day, 30)},
        "travel_fraction": 0.30,
        "animal_purchase_budget": {"GOOSE": 2, "COW": 2, "SHEEP": 2},
        "require_primary_animal_output": True,
        "seed_purchase_budget": {p: 1000 for p in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")},
        "feed_purchase_budget": 1000,
        "fertilizer_budget": 1000,
        "resource_prices": {p: prices[p] for p in ("WHEAT", "FERTILIZER") if p in prices},
        "procurement_cash_budget": int(obs["farms"][int(obs.get("player", 0))].get("money", 0)),
        "solver_time_limit": 5,
        "mip_rel_gap": 0.0,
        "freeze_existing": True,
    }


def _target_key(t): return int(t["day"]), t["product"]


def corrected_targets(baseline, transfer):
    """Replace supplied short targets, then enforce cumulative monotonicity only across deadlines."""
    out = {_target_key(t): dict(t) for t in baseline}
    for t in transfer:
        key = _target_key(t)
        out[key] = dict(t)
    result = []
    for product in sorted({p for _, p in out}):
        prior = 0
        for key in sorted(k for k in out if k[1] == product):
            row = out[key]; row["units"] = max(prior, int(row["units"])); prior = row["units"]
            result.append(row)
    return sorted(result, key=_target_key)


def materialize_tiles(case, mode, plan, snapshot):
    from report_cumulative_plans import materialize
    adapter = {"episode": case["episode"], "day": case["day"], "snapshot": snapshot,
               "modes": {mode: plan}}
    return materialize(adapter, mode)


def _change(before, after):
    def count(plan, key):
        total = Counter()
        for row in plan.get("daily", {}).values(): total.update(row.get(key, {}))
        return dict(total)
    def output(plan):
        total = Counter()
        for r in plan.get("three_day_output", []): total.update(r.get("output", {}))
        return dict(total)
    def work(plan): return sum(r.get("workload", 0) for r in plan.get("daily", {}).values())
    return {"plant_counts": {"forecast": count(before, "plant"), "residual_transfer": count(after, "plant")},
            "herd_counts": {"forecast": count(before, "buy_animal"), "residual_transfer": count(after, "buy_animal")},
            "output": {"forecast": output(before), "residual_transfer": output(after)},
            "workload": {"forecast": work(before), "residual_transfer": work(after)},
            "procurement": {"forecast": before.get("procurement", {}), "residual_transfer": after.get("procurement", {})}}


def selected_cases(cases):
    picked, per_day = [], Counter()
    for case in cases:
        d = int(case["day"])
        if len(picked) >= 10 or per_day[d] >= 2: continue
        picked.append(case); per_day[d] += 1
    return picked


def compile_case(case):
    checkpoint = case["checkpoint"]; policy = _policy(checkpoint)
    baseline_targets = [dict(t) for t in case["baseline_targets"]]
    transfer_targets = corrected_targets(baseline_targets, case["targets"])
    forecast = compile_checkpoint(checkpoint, baseline_targets, **policy)
    residual = compile_checkpoint(checkpoint, transfer_targets, **policy)
    snapshot = checkpoint_to_snapshot(checkpoint); snapshot.update(policy)
    def status(plan):
        quotes = policy["resource_prices"]
        procurement = plan.get("procurement", {})
        return {"aggregate_feasible": plan["aggregate_feasible"], "routing_feasible": plan["routing_feasible"],
                "solver": plan["solver"], "cost_certificate": {"hire_cost": plan["labor"]["total_hire_cost"],
                "procurement_cost": sum(procurement.get(p, 0) * quotes.get(p, 0) for p in procurement),
                "procurement": procurement}}
    return {
        "episode": case["episode"], "seat": case["seat"], "day": case["day"], "source": case.get("source"),
        "snapshot": snapshot, "policy": policy,
        "modes": {"forecast": {"targets": baseline_targets, "plan": forecast, "status": status(forecast), "tile_assignments": materialize_tiles(case, "forecast", forecast, snapshot)},
                  "residual_transfer": {"targets": transfer_targets, "plan": residual, "status": status(residual), "tile_assignments": materialize_tiles(case, "residual_transfer", residual, snapshot)}},
        "comparison": _change(forecast, residual),
        "routing_note": "Neither mode is a live execution claim; tile assignments omit routing and later reuse.",
    }


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--input", type=Path, default=DEFAULT_INPUT); ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ns = ap.parse_args()
    if not ns.input.exists(): raise SystemExit(f"waiting for transfer input: {ns.input}")
    data = json.loads(ns.input.read_text(encoding="utf-8")); cases = selected_cases(data["cases"])
    ns.out.mkdir(parents=True, exist_ok=True); summary = []
    for case in cases:
        result = compile_case(case); tag = f"{case['episode']}_s{case['seat']}_d{case['day']}"
        (ns.out / f"{tag}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        summary.append({"file": f"{tag}.json", "episode": case["episode"], "seat": case["seat"], "day": case["day"],
                        "forecast_feasible": result["modes"]["forecast"]["plan"]["aggregate_feasible"],
                        "transfer_feasible": result["modes"]["residual_transfer"]["plan"]["aggregate_feasible"],
                        "comparison": result["comparison"]})
    (ns.out / "summary.json").write_text(json.dumps({"input": str(ns.input), "case_count": len(summary), "cases": summary,
        "note": "Aggregate planning only; no live executor or routing validation."}, indent=2), encoding="utf-8")
    print(json.dumps({"compiled_cases": len(summary), "out": str(ns.out)}, indent=2))

if __name__ == "__main__": main()

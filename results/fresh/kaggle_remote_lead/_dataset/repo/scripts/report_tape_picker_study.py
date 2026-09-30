"""Summarize frozen, natural-seed tape-picker matches with seed-cluster intervals."""
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import json
import random
import statistics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/fresh/tape_picker_study_20260923"


def read_panel(name):
    folder = BASE / name
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, relative in manifest["source_paths"].items():
        if sha256((ROOT / relative).read_bytes()).hexdigest() != manifest["source_hashes"][name]:
            raise RuntimeError(f"{name}: frozen source hash mismatch")
    files = list((folder / "games").glob("*.json"))
    rows = [json.loads(path.read_text()) for path in files]
    expected = {(a, o, s, seat) for a in manifest["agents"]
                for o in manifest["opponents"] for s in manifest["seeds"]
                for seat in (0, 1)}
    seen = {(r["agent"], r["opponent"], r["seed"], r["seat"]) for r in rows}
    errors = []
    if len(rows) != len(seen) or seen != expected:
        errors.append({"missing": sorted(expected - seen), "unexpected": sorted(seen - expected)})
    for r in rows:
        if not r.get("completed") or r.get("errors") or r.get("statuses") != ["DONE", "DONE"]:
            errors.append((r["agent"], r["opponent"], r["seed"], r["seat"], "incomplete"))
            continue
        if (r.get("own_sha256") != manifest["source_hashes"][r["agent"]] or
                r.get("opponent_sha256") != manifest["source_hashes"][r["opponent"]]):
            errors.append((r["agent"], r["opponent"], r["seed"], r["seat"], "hash"))
        if r.get("actions") != 719 or r.get("states") != 720 or not r.get("ledger_verified"):
            errors.append((r["agent"], r["opponent"], r["seed"], r["seat"], "invalid_horizon"))
        for seat, cash in ((r["seat"], r["cash"]), (1-r["seat"], r["opponent_cash"])):
            ledger = r["daily"][seat][-1]
            if cash != 3000 + sum(ledger["revenue"].values()) - sum(ledger["spend"].values()):
                errors.append((r["agent"], r["opponent"], r["seed"], r["seat"], "ledger"))
    if errors:
        raise RuntimeError(f"{name}: {errors[:6]}")
    return rows


def interval(rows, metric):
    by_seed = defaultdict(list)
    for row in rows:
        by_seed[row["seed"]].append(row)
    groups = list(by_seed.values())
    rng = random.Random(20260923)
    samples = []
    for _ in range(10000):
        picked = [rng.choice(groups) for _ in groups]
        values = [metric(row) for group in picked for row in group]
        samples.append(statistics.mean(values))
    samples.sort()
    return [round(samples[250], 1), round(samples[9749], 1)]


def summary(rows):
    margins = [r["margin"] for r in rows]
    telemetry = [r.get("agent_reports", {}).get("own", {}) for r in rows]
    return {"games": len(rows), "seeds": len({r["seed"] for r in rows}),
            "wins": sum(m > 0 for m in margins), "ties": sum(m == 0 for m in margins),
            "losses": sum(m < 0 for m in margins),
            "mean_margin": round(statistics.mean(margins), 1),
            "mean_margin_ci": interval(rows, lambda r: r["margin"]),
            "mean_cash": round(statistics.mean(r["cash"] for r in rows), 1),
            "worst_margin": min(margins),
            "max_call_seconds": round(max(r["timing"]["own"]["max_seconds"] for r in rows), 4),
            "calls_over_1s": sum(r["timing"]["own"]["over_1s"] for r in rows),
            "router_errors": sum(t.get("_MGT_REPORT", {}).get("router_errors", 0) for t in telemetry),
            "overlay_errors": sum(t.get("_SHP_REPORT", {}).get("errors", 0) for t in telemetry)}


def paired(arms, a, b):
    left = {(r["seed"], r["seat"]): r for r in arms[a]}
    right = {(r["seed"], r["seat"]): r for r in arms[b]}
    if left.keys() != right.keys():
        raise RuntimeError(f"unpaired {a}, {b}")
    delta = [dict(seed=key[0], seat=key[1], margin=left[key]["margin"]-right[key]["margin"],
                  cash=left[key]["cash"]-right[key]["cash"],
                  win_change=int(left[key]["margin"] > 0)-int(right[key]["margin"] > 0))
             for key in sorted(left)]
    margins = [r["margin"] for r in delta]
    return {"games": len(delta), "mean_margin_delta": round(statistics.mean(margins), 1),
            "margin_delta_ci": interval(delta, lambda r: r["margin"]),
            "mean_cash_delta": round(statistics.mean(r["cash"] for r in delta), 1),
            "net_win_change": sum(r["win_change"] for r in delta),
            "better": sum(m > 0 for m in margins), "same": sum(m == 0 for m in margins),
            "worse": sum(m < 0 for m in margins), "worst_delta": min(margins)}


def main():
    design = json.loads((BASE / "design.json").read_text())
    design_v2 = json.loads((BASE / "design_v2.json").read_text()) if (BASE / "design_v2.json").exists() else None
    output = {"design": design, "design_v2": design_v2, "panels": {}}
    for panel in ("baseline_v56", "baseline_direct", "development", "development_t10",
                  "holdout_v56", "holdout_direct", "holdout_m1_t10",
                  "v2_development_v56", "v2_corrected_dev_v56", "v2_development_direct",
                  "v2_v56", "v2_direct"):
        if not (BASE / panel / "manifest.json").exists():
            continue
        rows = read_panel(panel)
        groups = defaultdict(list)
        for r in rows:
            groups[(r["agent"], r["opponent"])].append(r)
        output["panels"][panel] = {"matchups": {a+"_vs_"+o: summary(rs) for (a,o),rs in groups.items()}}
        arms = {a: rs for (a,o),rs in groups.items() if o == "v56"}
        if "mgt_m1" in arms:
            output["panels"][panel]["paired_vs_m1"] = {
                a: paired(arms, a, "mgt_m1") for a in arms if a != "mgt_m1"}
        if "mgt_t10" in arms:
            output["panels"][panel]["paired_vs_t10"] = {
                a: paired(arms, a, "mgt_t10") for a in arms if a != "mgt_t10"}
    arms = {}
    for panel in ("baseline_v56", "development", "development_t10", "holdout_v56",
                  "v2_development_v56", "v2_corrected_dev_v56", "v2_v56"):
        if panel in output["panels"]:
            for r in read_panel(panel):
                if r["opponent"] == "v56":
                    arms.setdefault(panel, {}).setdefault(r["agent"], []).append(r)
    for panel, group in arms.items():
        if panel == "development" and "baseline_v56" in arms:
            merged = dict(arms["baseline_v56"], **group)
            output["panels"][panel]["paired_vs_m1"] = {
                a: paired(merged, a, "mgt_m1") for a in group}
        if panel == "development_t10" and "baseline_v56" in arms:
            merged = dict(arms["baseline_v56"], **group)
            output["panels"][panel]["paired_vs_m1"] = {
                a: paired(merged, a, "mgt_m1") for a in group}
            output["panels"][panel]["paired_vs_t10"] = {
                a: paired(merged, a, "mgt_t10") for a in group}
        if panel == "v2_corrected_dev_v56" and "v2_development_v56" in arms:
            merged = dict(arms["v2_development_v56"], **group)
            output["panels"][panel]["paired_vs_m1"] = {
                a: paired(merged, a, "mgt_m1") for a in group}
            output["panels"][panel]["paired_vs_t10"] = {
                a: paired(merged, a, "mgt_t10") for a in group}
    if "baseline_direct" in output["panels"] and "holdout_m1_t10" in output["panels"]:
        combined = read_panel("baseline_direct") + read_panel("holdout_m1_t10")
        output["combined_m1_vs_t10"] = summary(combined)
    path = BASE / "summary.json"
    path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output["panels"], indent=2))


if __name__ == "__main__":
    main()

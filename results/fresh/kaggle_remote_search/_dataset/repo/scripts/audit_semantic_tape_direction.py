"""Check whether retrieved crop edits follow revealed product-demand gaps.

This is a screening diagnostic only: it omits existing stocks, future shop
uncertainty, crop timing and economics, so alignment is not a switch proof.
"""
from collections import Counter
import json
from pathlib import Path

from audit_production_plan_fit import ROOT, load_library


OUT = ROOT / "results/fresh/semantic_tapes"
PRODUCTS = ("STRAWBERRY", "TOMATO", "WOOL", "CARROT", "MILK", "EGG", "WHEAT")
CROPS = ("STRAWBERRY", "TOMATO", "CARROT", "WHEAT", "MELON")


def plant_counts(profile, day):
    counts = Counter()
    for key, amount in profile["requested_plants"].items():
        when, crop = key.split(":", 1)
        if day <= int(when) < day + 3:
            counts[crop] += amount
    return counts


def main():
    ns, library = load_library()
    tape = {t["ep"]: t for t in library["tapes"]}
    profiles = {p["episode"]: p for p in json.loads((OUT / "compact_profiles.json").read_text(encoding="utf-8"))}
    audit = json.loads((OUT / "retrieval_audit.json").read_text(encoding="utf-8"))
    queries = {(q["episode"], q["day"]): q for q in json.loads(
        (ROOT / "results/fresh/production_plan_fit/audit.json").read_text(encoding="utf-8"))["rows"]}
    findings = []
    counts = Counter()
    for row in audit["rows"]:
        current_ep = row["current"]["episode"]
        candidate_ep = row["plan_edit_8"]["episode"]
        if current_ep == candidate_ep:
            continue
        day = row["day"]
        shops = queries[(row["episode"], day)]["shops"]
        k = len(shops)
        actual_vec = ns["_mgt_vec"](shops, k)
        current_vec = tape[current_ep]["vec"][k]
        candidate_vec = tape[candidate_ep]["vec"][k]
        current_plants = plant_counts(profiles[current_ep], day)
        candidate_plants = plant_counts(profiles[candidate_ep], day)
        demand_gap = {p: actual_vec[i] - current_vec[i] for i, p in enumerate(PRODUCTS)}
        plant_delta = {p: candidate_plants[p]-current_plants[p] for p in CROPS}
        for crop in CROPS:
            edit = plant_delta[crop]
            if not edit:
                continue
            gap = demand_gap.get(crop, 0)
            counts["aligned" if edit*gap > 0 else "opposed" if edit*gap < 0 else "zero_gap"] += 1
        targeted_tomato_swap = (demand_gap["TOMATO"] > 0 and demand_gap["WHEAT"] < 0 and
                                  plant_delta["TOMATO"] > 0 and plant_delta["WHEAT"] < 0)
        if targeted_tomato_swap:
            counts["targeted_tomato_swap"] += 1
        findings.append(dict(episode=row["episode"], day=day, seat=row["seat"],
                             current_episode=current_ep, candidate_episode=candidate_ep,
                             actual_demand=actual_vec, current_demand=current_vec,
                             candidate_demand=candidate_vec, demand_gap=demand_gap,
                             plant_delta=plant_delta, targeted_tomato_swap=targeted_tomato_swap,
                             history_improvement=row["current"]["history"]-row["plan_edit_8"]["history"]))
    out = dict(switches=len(findings), crop_edit_direction_counts=dict(counts),
               targeted_tomato_swaps=[f for f in findings if f["targeted_tomato_swap"]],
               case_111291994=next(f for f in findings if f["episode"] == 111291994 and f["day"] == 21),
               limitation="Revealed-demand alignment is necessary evidence for a demand-driven label, but not proof of profitable planting; stocks and future markets are omitted.")
    (OUT / "direction_audit.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"switches": out["switches"], "direction_counts": out["crop_edit_direction_counts"],
                      "targeted_tomato_swap_examples": [{k: f[k] for k in ("episode", "day", "seat", "demand_gap", "plant_delta")}
                                                       for f in out["targeted_tomato_swaps"][:5]],
                      "case_111291994": {k: out["case_111291994"][k] for k in ("demand_gap", "plant_delta")}}, indent=2))


if __name__ == "__main__":
    main()

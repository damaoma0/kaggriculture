"""Offline retrieval frontier for dated production plans, not a playing policy.

At recorded m1 checkpoints, compare all 584 donor tapes using only revealed
shops and current assets. Plan edit distances use requested compact commands;
they describe how different a continuation is, not whether it is executable.
"""
from collections import Counter
import json
from pathlib import Path
from statistics import mean

from audit_production_plan_fit import LABELS, ROOT, load_library


OUT = ROOT / "results/fresh/semantic_tapes"
ANIMALS = ("go", "co", "sh")


def distance(a, b):
    return sum(abs(a.get(k, 0) - b.get(k, 0)) for k in a.keys() | b.keys())


def window_counts(profile, field, day):
    return Counter({k: v for k, v in profile[field].items()
                    if day <= int(k.split(":", 1)[0]) < day + 3})


def summarize(rows, mode):
    return dict(n=len(rows), changed=sum(r[mode]["episode"] != r["current"]["episode"] for r in rows),
                improved_history=sum(r[mode]["history"] < r["current"]["history"] - 1e-8 for r in rows),
                mean_history=mean(r[mode]["history"] for r in rows),
                mean_current_demand=mean(r[mode]["current_demand"] for r in rows),
                mean_asset_gap=mean(r[mode]["asset_gap"] for r in rows),
                mean_animal_shortfall=mean(r[mode]["animal_shortfall"] for r in rows),
                mean_dated_plant_edit=mean(r[mode]["plant_edit"] for r in rows),
                mean_place_edit=mean(r[mode]["place_edit"] for r in rows))


def main():
    ns, library = load_library()
    profiles = {p["episode"]: p for p in json.loads((OUT / "compact_profiles.json").read_text(encoding="utf-8"))}
    assert len(profiles) == len(library["tapes"]) == 584
    rich_ids = {p["episode"] for p in json.loads((OUT / "verified_segments.json").read_text(encoding="utf-8"))}
    audit = json.loads((ROOT / "results/fresh/production_plan_fit/audit.json").read_text(encoding="utf-8"))
    rows = []
    modes = {"count_only": (0, None, None),
             "plan_edit_4": (4, 4, 0),
             "plan_edit_8": (4, 8, 0),
             "plan_edit_16": (4, 16, 0),
             "plan_edit_8_relaxed_herd": (4, 8, 2)}
    for query in audit["rows"]:
        day, shops, own = query["day"], query["shops"], Counter(query["own_assets"])
        current_ep = query["current"]["episode"]
        current_profile = profiles[current_ep]
        current_plants = window_counts(current_profile, "requested_plants", day)
        current_places = window_counts(current_profile, "requested_placements", day)
        vectors = [ns["_mgt_vec"](shops, j) for j in range(9)]
        k = len(shops)
        candidates = []
        for tape in library["tapes"]:
            ep = tape["ep"]
            profile = profiles[ep]
            common = 0
            for a, b in zip(shops, tape["shops"]):
                if a != b:
                    break
                common += 1
            native_score = ns["_mgt_distance"](vectors, shops, tape, k)
            history = native_score + .01 * common
            current_demand = sum(w * abs(x-y) for w, x, y in zip(
                ns["_MGT_W"], vectors[k], tape["vec"][k]))
            counts = tape["counts"][day]
            asset_gap = sum(abs(own[p] - counts[p]) for p in LABELS)
            animal_shortfall = sum(max(0, own[p] - counts[p]) for p in ANIMALS)
            plants = window_counts(profile, "requested_plants", day)
            places = window_counts(profile, "requested_placements", day)
            candidates.append(dict(episode=ep, native_score=native_score, history=history,
                                   current_demand=current_demand,
                                   asset_gap=asset_gap, animal_shortfall=animal_shortfall,
                                   plant_edit=distance(plants, current_plants),
                                   place_edit=distance(places, current_places)))
        # Physical compatibility is deliberately not treated as semantic fit.
        # A real switch still needs a whole-farm compiler and preflight.
        cur = next(c for c in candidates if c["episode"] == current_ep)
        assert abs(cur["history"] - query["current"]["history_distance"]) < 1e-8
        assert cur["asset_gap"] == query["current"]["asset_count_l1"]
        key = lambda c: (c["native_score"], c["asset_gap"], c["episode"] != current_ep, c["episode"])
        row = dict(episode=query["episode"], seat=query["seat"], day=day,
                   current=cur, position_free=min(candidates, key=key))
        for name, (asset_slack, plant_budget, animal_slack) in modes.items():
            allowed = [c for c in candidates if c["asset_gap"] <= cur["asset_gap"] + asset_slack
                       and (plant_budget is None or c["plant_edit"] <= plant_budget)
                       and (animal_slack is None or c["animal_shortfall"] <= cur["animal_shortfall"] + animal_slack)]
            assert allowed
            row[name] = min(allowed, key=key)
        rich = [c for c in candidates if c["episode"] in rich_ids
                and c["episode"] != current_ep
                and c["asset_gap"] <= cur["asset_gap"] + 4
                and c["plant_edit"] <= 8
                and c["animal_shortfall"] <= cur["animal_shortfall"]
                and c["native_score"] <= cur["native_score"] - 2]
        row["rich_semantic"] = min(rich, key=key) if rich else cur
        rows.append(row)
    assert len(rows) == 430
    summary = {mode: summarize(rows, mode) for mode in ("current", "position_free", *modes, "rich_semantic")}
    examples = sorted((r for r in rows if r["plan_edit_8"]["episode"] != r["current"]["episode"]),
                      key=lambda r: r["current"]["history"] - r["plan_edit_8"]["history"], reverse=True)[:8]
    result = dict(protocol=dict(checkpoints=430, episodes=86, candidates=584, rich_candidate_episodes=len(rich_ids),
                                revealed_input_only=True,
                                rules={k: dict(asset_slack=a, plant_edit_budget=p, additional_animal_shortfall=m)
                                       for k, (a, p, m) in modes.items()},
                                limitations=["Dated planting and placement edits count requested commands, not successful execution.",
                                             "Asset count gap omits age, care bank, held yield, and inventory.",
                                             "These are exhaustive retrieval-fit comparisons, not game outcomes or an economic transition cost.",
                                             "A semantic compiler would still need to preserve and service every live cohort."]),
                  summary=summary, examples=examples, rows=rows)
    (OUT / "retrieval_audit.json").write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(dict(summary=summary, example=examples[:1]), indent=2))


if __name__ == "__main__":
    main()

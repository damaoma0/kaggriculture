"""Project constrained semantic donor calendars from real m1 checkpoints.

This is a three-day official-mechanics feasibility probe, not a full-game
counterfactual. Both incumbent and candidate calendars are compiled on the
same actual observation with the existing state-based labor/job compiler.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time

from fragments.continuation_calendar import adapt_calendar
from fragments.continuation_projection import check_window
from fragments import continuation_executor as executor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_tapes/handoff_probe.json"
ANIMALS = {"GOOSE", "COW", "SHEEP"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def donor_window(profile, day):
    jobs = []
    for field, op in (("requested_plants", "PLANT"),
                      ("requested_placements", "PLACE")):
        for key, n in sorted(profile[field].items()):
            absolute, product = key.split(":", 1)
            absolute = int(absolute)
            if not day <= absolute < day + 3:
                continue
            if op == "PLACE" and product not in ANIMALS:
                continue
            jobs.extend({"day": absolute-day, "cmd": [op, product], "pre_tile": "EMPTY"}
                        for _ in range(n))
    return {"id": f"compact:{profile['episode']}:d{day}", "day": day, "jobs": jobs}


def herd(farm):
    return Counter(t.get("animal") for row in farm["tiles"] for t in row
                   if isinstance(t, dict) and t.get("animal"))


def assets(farm):
    return Counter(t.get("crop") or t.get("animal") for row in farm["tiles"] for t in row
                   if isinstance(t, dict) and (t.get("crop") or t.get("animal")))


def project(obs, profile):
    node = adapt_calendar(obs, donor_window(profile, obs["day"]))
    node["hire_to"] = 12
    executor.set_deadline(time.perf_counter() + .6)
    started = time.perf_counter()
    try:
        result = check_window(obs, node, executor)
    except executor.PlanningBudgetExceeded:
        result = {"ok": False, "failure": {"reason": "planning_budget"}}
    finally:
        executor.set_deadline(None)
    row = {"ok": bool(result["ok"]), "seconds": time.perf_counter() - started,
           "requested_plant_jobs": sum(j["cmd"][0] == "PLANT" for j in node["jobs"]),
           "calendar_slack": node["calendar_slack"]}
    if result["ok"]:
        end = result["end_observation"]
        farm = end["farms"][obs["player"]]
        row.update(cash=farm["money"], output=result["output"],
                   assets=dict(assets(farm)), herd=dict(herd(farm)),
                   actions=len(result["actions"]))
    else:
        row["failure"] = result["failure"]
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    audit = read(ROOT / "results/fresh/semantic_tapes/retrieval_audit.json")
    profiles = {x["episode"]: x for x in read(ROOT / "results/fresh/semantic_tapes/compact_profiles.json")}
    games = {g["episode"]: g for g in read(ROOT / "results/fresh/tape_gap_plans/dataset_primary.json")["games"]}
    queries = [r for r in audit["rows"] if r["current"]["episode"] != r["plan_edit_8"]["episode"]]
    if args.limit:
        queries = queries[:args.limit]
    rows = []
    for query in queries:
        day = query["day"]
        obs = games[query["episode"]]["checkpoints"][str(day)]["observation"]
        assert obs["player"] == query["seat"]
        initial_herd = herd(obs["farms"][obs["player"]])
        current = project(obs, profiles[query["current"]["episode"]])
        alternative = project(obs, profiles[query["plan_edit_8"]["episode"]])
        for arm in (current, alternative):
            arm["starting_herd_preserved"] = bool(arm["ok"] and all(
                arm["herd"].get(p, 0) >= n for p, n in initial_herd.items()))
        rows.append(dict(query_episode=query["episode"], seat=query["seat"], day=day,
                         incumbent_episode=query["current"]["episode"],
                         candidate_episode=query["plan_edit_8"]["episode"],
                         demand_history=(query["current"]["history"], query["plan_edit_8"]["history"]),
                         current=current, alternative=alternative))
        print(json.dumps({"case": len(rows), "episode": query["episode"], "day": day,
                          "current_ok": current["ok"], "candidate_ok": alternative["ok"],
                          "candidate_failure": alternative.get("failure", {}).get("reason")}), flush=True)
    summary = dict(queries=len(rows), current_feasible=sum(x["current"]["ok"] for x in rows),
                   candidate_feasible=sum(x["alternative"]["ok"] for x in rows),
                   both_feasible=sum(x["current"]["ok"] and x["alternative"]["ok"] for x in rows),
                   candidate_preserves_starting_herd=sum(x["alternative"]["starting_herd_preserved"] for x in rows),
                   max_seconds=max((max(x["current"]["seconds"], x["alternative"]["seconds"]) for x in rows), default=0),
                   protocol="Both calendars adapted and compiled from the same actual checkpoint; no rival trades or new weeds in projection. Not a cash-optimality or full-season test.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

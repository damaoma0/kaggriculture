"""Recheck full donor day-15 calendar with a longer offline compiler budget."""
import json
from pathlib import Path
import time

from fragments.continuation_calendar import adapt_calendar
from fragments.continuation_projection import check_window
from fragments import continuation_executor as executor
from probe_semantic_handoff import ROOT, donor_window


OUT = ROOT / "results/fresh/semantic_tapes/directional_full_calendar_probe.json"
EPISODE, DAY = 111289863, 15


def main():
    profiles = {x["episode"]:x for x in json.loads((ROOT / "results/fresh/semantic_tapes/compact_profiles.json").read_text(encoding="utf-8"))}
    game = next(x for x in json.loads((ROOT / "results/fresh/tape_gap_plans/dataset_primary.json").read_text(encoding="utf-8"))["games"]
                if x["episode"] == EPISODE)
    obs = game["checkpoints"][str(DAY)]["observation"]
    rows = {}
    for label, donor in (("incumbent",109593970),("retrieved",110025609)):
        node = adapt_calendar(obs,donor_window(profiles[donor],DAY))
        node["hire_to"] = 12
        executor.set_deadline(time.perf_counter()+5.0)
        started=time.perf_counter()
        try:
            result=check_window(obs,node,executor)
        except executor.PlanningBudgetExceeded:
            result={"ok":False,"failure":{"reason":"planning_budget"}}
        finally:
            executor.set_deadline(None)
        rows[label]={"donor":donor,"seconds":time.perf_counter()-started,
                     "ok":bool(result["ok"]),"failure":result.get("failure"),
                     "requested_jobs":node["jobs"],"calendar_slack":node["calendar_slack"],
                     "actions":result.get("actions"),"output":result.get("output")}
        print(label,rows[label]["ok"],rows[label]["seconds"],rows[label]["failure"],flush=True)
    OUT.write_text(json.dumps({"episode":EPISODE,"day":DAY,"rows":rows},indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()

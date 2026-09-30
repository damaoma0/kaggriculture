"""Run the fixed 12-node native segment gate against executor v3."""
import hashlib
import json
import sys
from pathlib import Path

import fragments.segment_job_executor_v3 as executor
import validate_segment_executor as validator
from check_segment_v3 import sales

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/segment_stitch/native_validation_v3.json"


def save(rows, nodes):
    accepted = [a for r in rows for a in r["attempts"] if a.get("started") and not a.get("rejected_window")]
    exact = [a for a in accepted if not a.get("output_difference")]
    payload = {"schema_version": 1, "complete": len(rows) == len(nodes),
               "library_sha256": hashlib.sha256(validator.LIBRARY.read_bytes()).hexdigest(),
               "executor_module": "scripts/fragments/segment_job_executor_v3.py",
               "executor_sha256": hashlib.sha256((ROOT / "scripts/fragments/segment_job_executor_v3.py").read_bytes()).hexdigest(),
               "design": "12 deterministic native donor windows; v3 injected explicitly; own executor, PASS rival, source shops conditioned only after each day; 11 workers then 12/13 only if whole window rejects.",
               "rows": rows,
               "summary": {"requested": len(nodes), "completed_rows": len(rows),
                           "whole_window_accepted": len(accepted), "exact_output": len(exact),
                           "tile_state_exact": sum(not a.get("end_tile_state_differences") for a in accepted),
                           "errors": sum(any("error" in a for a in r["attempts"]) for r in rows)}}
    temporary = OUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(OUT)


def main():
    # run_node imports this canonical module name lazily; bind it to the tested
    # v3 code so the artifact hash and executable implementation agree.
    sys.modules["fragments.segment_job_executor"] = executor
    validator.add_capacity_sales = sales
    validator.OUT = OUT
    validator.EXECUTOR_HASH_PATH = ROOT / "scripts/fragments/segment_job_executor_v3.py"
    nodes = validator.selected_nodes(validator.read(validator.LIBRARY)["segments"])
    raws, rows = validator.raw_lookup(), []
    for node in nodes:
        attempts = []
        try:
            for workers in (11, 12, 13):
                row = validator.run_node(node, raws[int(node["episode"])], workers)
                attempts.append(row)
                if row.get("started") and not row.get("rejected_window"):
                    break
        except Exception as exc:
            attempts.append({"started": False, "hire_to": 11, "error": repr(exc)})
        rows.append({"id": node["id"], "attempts": attempts})
        save(rows, nodes)
        print(node["id"], attempts[-1].get("rejected_window"), attempts[-1].get("output_difference"), flush=True)
    save(rows, nodes)
    print(json.dumps(validator.read(OUT)["summary"]))


if __name__ == "__main__": main()

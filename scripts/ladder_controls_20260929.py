"""Exact replays (source controls: both recorded action streams, recorded weeds) of chosen ladder cases through the
frozen harness, to inspect our live agent's real games with the same ledgers as every panel game. One process per game.

usage: ladder_controls_20260929.py CASE_ID[,CASE_ID...] [--out results/fresh/semantic_h2h_20260929/ladder_controls]"""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import semantic_h2h_20260929 as SH  # noqa: E402

H = ROOT / "results/fresh/semantic_h2h_20260929"

if __name__ == "__main__":
    ids = sys.argv[1].split(",")
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else H / "ladder_controls"
    out.mkdir(parents=True, exist_ok=True)
    cases = [c for c in json.loads((H / "ladder_cases.json").read_text())["cases"] if c["id"] in ids]
    harness = H / "study/candidates/n18/harness"
    jobs = [dict(study=str(H / "study"), case=c, kind="source_control", output=str(out / f"{c['id']}.json"), candidate="n18",
                 leader_weeds=True) for c in cases if not (out / f"{c['id']}.json").exists()]
    with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
        for r in pool.map(SH._worker, [(str(harness), j, True) for j in jobs]):
            print(r.get("case", {}).get("id"), "cash match", r.get("recorded_cash_match"), "margin", r.get("margin"), flush=True)

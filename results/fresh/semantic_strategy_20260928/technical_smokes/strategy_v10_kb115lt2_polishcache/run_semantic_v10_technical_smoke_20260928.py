"""One immutable normal-budget live06 technical smoke, not a strength panel."""
import json
from pathlib import Path
import sys

DIRECTORY = Path(__file__).resolve().parent
MANIFEST = json.loads((DIRECTORY / "manifest.json").read_text(encoding="utf-8"))
STUDY = Path(MANIFEST["study"])
CANDIDATE = MANIFEST["candidate"]
FROZEN = STUDY / "candidates" / CANDIDATE
sys.path.insert(0, str(FROZEN / "harness"))
import semantic_strategy_gate_20260928 as G


def main():
    import psutil
    free = psutil.virtual_memory().available / 2**30
    if free < 3.3:
        raise RuntimeError(f"Insufficient memory for live opponent: {free:.3f}GiB")
    G.verify_files(DIRECTORY, MANIFEST["files"])
    assert G.sha(FROZEN / "manifest.json") == MANIFEST["candidate_manifest_sha256"]
    assert G.sha(STUDY / "protocol.json") == MANIFEST["protocol_sha256"]
    case = next(row for row in G.read(STUDY / "protocol.json")["development"]["live"] if row["id"] == "live-06")
    assert case == MANIFEST["case"]
    output = STUDY / "runs" / CANDIDATE / "development/live/live-06.json"
    assert not output.exists(), "Never rerun an existing outcome"
    job = dict(study=str(STUDY), candidate=CANDIDATE, case=case, kind="live", output=str(output),
               harness_extension=dict(root=str(DIRECTORY), files=MANIFEST["files"]))
    print(f"One normal-budget technical smoke, free RAM {free:.3f}GiB", flush=True)
    print(json.dumps(G.play_job(job), indent=2), flush=True)
    print(json.dumps(G.report(STUDY, CANDIDATE, "development", "live"), indent=2), flush=True)


if __name__ == "__main__":
    main()

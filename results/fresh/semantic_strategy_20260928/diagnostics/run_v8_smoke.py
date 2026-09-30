"""Run only the first predeclared development case with the frozen V8 harness.

The output occupies its normal panel slot and will be reused by a later full-panel
run. This separate driver is hash-bound through the harness extension mechanism.
It changes no engine, policy, case-selection, or eligibility rule.
"""
import hashlib
import json
from pathlib import Path
import sys

STUDY = Path(__file__).resolve().parents[1]
CANDIDATE = "strategy_v8_kb115lt2_readiness"
FROZEN = STUDY / "candidates" / CANDIDATE
sys.path.insert(0, str(FROZEN / "harness"))
import semantic_strategy_gate_20260928 as G

def main():
    import psutil
    free = psutil.virtual_memory().available / 2**30
    if free < 3.3:
        raise RuntimeError(f"Need 3.3GiB before live V9 warmup; only {free:.3f}GiB free")
    manifest = G.read(FROZEN / "manifest.json")
    G.verify_files(FROZEN / "project", manifest["files"])
    G.verify_files(FROZEN / "harness", manifest["harness_files"])
    protocol = G.read(STUDY / "protocol.json")
    assert G.sha(STUDY / "protocol.json") == manifest["protocol_sha256"]
    case = protocol["development"]["live"][0]
    output = STUDY / "runs" / CANDIDATE / "development/live" / (case["id"] + ".json")
    assert not output.exists(), "Never silently repeat an existing smoke outcome"
    driver = Path(__file__).resolve()
    job = dict(study=str(STUDY), candidate=CANDIDATE, case=case, kind="live", output=str(output),
               harness_extension=dict(root=str(driver.parent), files={driver.name: G.sha(driver)}))
    print(f"One frozen development game, free RAM {free:.3f}GiB", flush=True)
    print(json.dumps(G.play_job(job), indent=2), flush=True)
    print(json.dumps(G.report(STUDY, CANDIDATE, "development", "live"), indent=2), flush=True)

if __name__ == "__main__":
    main()

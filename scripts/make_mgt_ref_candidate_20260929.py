"""Make the study's packaged live opponent (MGT = mgt_v9lite, study/opponent/pkg) a candidate of its own, so the frozen
harness can seat it in the recorded-leader panels as a reference arm (how MGT itself does against DSM / MMPQ, under the
same upper / lower bounds as the semantic stack). Harness files are copied from a semantic candidate; the project is
the opponent package byte for byte (entry main.py, 185 files hashed as the protocol hashes them).

usage: make_mgt_ref_candidate_20260929.py [--id mgt_ref] [--harness-from n17]"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="mgt_ref")
    ap.add_argument("--harness-from", default="n17")
    a = ap.parse_args()
    protocol = json.loads((STUDY / "protocol.json").read_text())
    src_c = STUDY / "candidates" / a.harness_from
    dst = STUDY / "candidates" / a.id
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src_c / "harness", dst / "harness")
    pkg = STUDY / "opponent/pkg"
    files = {}
    for rel, digest in protocol["opponent"]["files"].items():
        s_ = pkg / rel
        assert sha(s_) == digest, rel
        (dst / "project" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(s_, dst / "project" / rel)
        files[rel] = digest
    m = json.loads((src_c / "manifest.json").read_text())
    m.update(candidate_id=a.id, entry="main.py", files=files, training_episodes=[],
             derived_from=dict(note="MGT reference arm: the study's packaged opponent (mgt_v9lite) as a candidate",
                               opponent=protocol["opponent"]["name"]))
    for k in list(m["harness_files"]):
        assert m["harness_files"][k] == sha(dst / "harness" / k), k
    (dst / "manifest.json").write_text(json.dumps(m, indent=1), encoding="utf-8")
    print(a.id, "<- study opponent", protocol["opponent"]["name"], len(files), "files")


if __name__ == "__main__":
    main()

"""Assemble a semantic-stack candidate as a multi-file Kaggle agent archive (NOT a submission by itself).

  package_semantic_ship_20260929.py <candidate> <out_dir>
      -> <out_dir>/pkg/ (the unpacked agent), <out_dir>/submission.tar.gz, <out_dir>/MANIFEST.json

pkg/ = the candidate's frozen project folder (results/fresh/semantic_h2h_20260929/study/candidates/<c>/project: exactly
the files its manifest hashes; the frozen harness already checks that a game imports nothing else) + main.py.
main.py follows the rules that got the packaged V9-lite through Kaggle's official runner (package_v9lite_main.py):
package root from sys.path / /kaggle_simulations/agent / cwd, gzip fallback for libraries Kaggle may unpack, no
threads, the entry is the LAST callable in the file."""
import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"

MAIN = '''"""Semantic stack submission entry (main.py of a multi-file Kaggle agent archive; builder
scripts/package_semantic_ship_20260929.py). Candidate: %(cand)s. The strategy is the frozen project under this folder:
agents/semantic_strategy_20260928.py (opening days 0-5, semantic policy, tile compiler, executor)."""
import gzip as _sg_gzip
import importlib.util as _sg_util
import sys as _sg_sys
from pathlib import Path as _SgPath

_SG_ENTRY = "agents/semantic_strategy_20260928.py"
_SG_MARK = "results/fresh/semantic_strategy_20260928/candidate_config.json"


def _sg_root():
    cands = [_SgPath(__file__).resolve().parent] if "__file__" in globals() else []
    cands += [_SgPath(p) for p in reversed(_sg_sys.path) if p]
    cands += [_SgPath("/kaggle_simulations/agent"), _SgPath.cwd(), *_SgPath.cwd().parents]
    for d in cands:
        try:
            if (d / _SG_ENTRY).exists() and (d / _SG_MARK).exists():
                return d.resolve()
        except OSError:
            continue
    raise RuntimeError("semantic agent: package files not found next to main.py")


_SG_ROOT = _sg_root()
_sg_gz_open = _sg_gzip.open


def _sg_gz_fallback(filename, mode="rb", *args, **kwargs):
    if isinstance(filename, (str, _SgPath)):
        p = _SgPath(filename)
        if p.suffix == ".gz" and not p.exists() and p.with_suffix("").exists():
            if "t" in mode:
                return open(p.with_suffix(""), "r", encoding=kwargs.get("encoding") or "utf-8")
            return open(p.with_suffix(""), "rb")
    return _sg_gz_open(filename, mode, *args, **kwargs)


_sg_gzip.open = _sg_gz_fallback
_sg_spec = _sg_util.spec_from_file_location("_semantic_strategy_entry", _SG_ROOT / _SG_ENTRY)
_SG = _sg_util.module_from_spec(_sg_spec)
_sg_sys.modules["_semantic_strategy_entry"] = _SG
_sg_spec.loader.exec_module(_SG)


def semantic_ship_agent(observation, configuration=None):
    return _SG.agent(observation, configuration)
'''


def main():
    cand, out = sys.argv[1], Path(sys.argv[2]).resolve()
    src = STUDY / "candidates" / cand
    manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    pkg = out / "pkg"
    shutil.rmtree(pkg, ignore_errors=True)
    pkg.mkdir(parents=True)
    for rel, digest in manifest["files"].items():
        s_ = src / "project" / rel
        assert hashlib.sha256(s_.read_bytes()).hexdigest() == digest, rel
        (pkg / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(s_, pkg / rel)
    (pkg / "main.py").write_text(MAIN % dict(cand=cand), encoding="utf-8", newline="\n")
    files = sorted(p for p in pkg.rglob("*") if p.is_file())
    hashes = {p.relative_to(pkg).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    tar = out / "submission.tar.gz"
    with tarfile.open(tar, "w:gz") as t:
        for p in files:
            t.add(p, arcname=p.relative_to(pkg).as_posix())
    (out / "MANIFEST.json").write_text(json.dumps(dict(
        candidate=cand, candidate_manifest_sha256=hashlib.sha256((src / "manifest.json").read_bytes()).hexdigest(),
        files=hashes, archive_sha256=hashlib.sha256(tar.read_bytes()).hexdigest(),
        archive_mb=round(tar.stat().st_size / 1e6, 2), status="research package; NOT submitted"), indent=1),
        encoding="utf-8")
    print(f"{len(files)} files, archive {tar.stat().st_size / 1e6:.2f} MB -> {tar}")


if __name__ == "__main__":
    main()

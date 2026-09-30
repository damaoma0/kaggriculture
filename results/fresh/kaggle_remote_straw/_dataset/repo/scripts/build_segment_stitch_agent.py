"""Build standalone segment-stitch variants from the frozen mgt_m1 source.

The large replay-backed library is compressed into the generated agent.  The
executor is evaluated in a private namespace so its helper names cannot alter
the baseline mgt_m1 chassis.  Building is deterministic and performs only
syntax/loader checks; it does not run an engine match.
"""
import base64
import hashlib
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "agents" / "mgt_m1.py"
LIBRARY = ROOT / "results" / "fresh" / "segment_stitch" / "library.json"
EXECUTOR = ROOT / "scripts" / "fragments" / "segment_job_executor.py"
SELECTOR = ROOT / "scripts" / "fragments" / "segment_stitch_selector.py"
REMAPPER = ROOT / 'scripts/fragments/segment_tile_remap.py'


def build(name, state_only=False):
    baseline = BASELINE.read_text(encoding="utf-8")
    library = json.loads(LIBRARY.read_text(encoding="utf-8"))
    segments = library.get("segments", [])
    if not segments:
        raise RuntimeError("segment library is empty")
    # Diagnostics, raw logistics and historical private endpoints are not
    # runtime inputs. Keep only the portable production and compatibility data.
    segments = [{k: n[k] for k in ('id', 'day', 'start_farm', 'start_private', 'end_farm', 'output', 'jobs')} for n in segments]
    for node in segments:
        node['jobs'] = [{k: j[k] for k in ('day', 'hour', 'tile', 'cmd', 'pre_tile', 'effect') if k in j} for j in node['jobs']]
    blob = base64.b85encode(zlib.compress(json.dumps(segments, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)).decode("ascii")
    executor_source = EXECUTOR.read_text(encoding="utf-8")
    selector_source = SELECTOR.read_text(encoding="utf-8")
    selector_source = selector_source.replace("__SS_LIBRARY__", "_SS_JSON.loads(_SS_ZLIB.decompress(_SS_B64.b85decode(_SS_LIBRARY_BLOB)))")
    selector_source = selector_source.replace("__SS_STATE_ONLY__", repr(bool(state_only)))
    append = "\n\n# Segment stitch extension; baseline agent and mgt_kaggle_entry remain intact.\n"
    append += "import base64 as _SS_B64, json as _SS_JSON, zlib as _SS_ZLIB\n"
    append += f"_SS_LIBRARY_BLOB = {blob!r}\n"
    append += f"_SS_EXECUTOR_SOURCE = {executor_source!r}\n_SS_EXECUTOR = {{}}\nexec(_SS_EXECUTOR_SOURCE, _SS_EXECUTOR)\n"
    append += f"_SS_REMAP_NS = {{}}\nexec({REMAPPER.read_text(encoding='utf-8')!r}, _SS_REMAP_NS)\n_ss_remap = _SS_REMAP_NS['_ss_remap']\n"
    append += "_SS_BASELINE = mgt_kaggle_entry\n"
    append += selector_source + "\n"
    out = ROOT / "agents" / f"{name}.py"
    out.write_text(baseline + append, encoding="utf-8")
    source = out.read_text(encoding="utf-8")
    compile(source, str(out), "exec")
    from kaggle_environments.agent import get_last_callable
    entry = get_last_callable(source, path=str(out))
    if getattr(entry, "__name__", "") != "segment_stitch_entry":
        raise RuntimeError(f"loader selected {getattr(entry, '__name__', entry)!r}")
    print(json.dumps({"agent": str(out), "state_only": state_only, "segments": len(segments),
                      "library_blob_bytes": len(blob), "file_bytes": out.stat().st_size,
                      "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}))


def main():
    names = sys.argv[1:] or ["mgt_segment_stitch", "mgt_segment_state"]
    allowed = {"mgt_segment_stitch": False, "mgt_segment_state": True}
    for name in names:
        if name not in allowed:
            raise SystemExit(f"unknown variant {name}")
        build(name, allowed[name])


if __name__ == "__main__":
    main()

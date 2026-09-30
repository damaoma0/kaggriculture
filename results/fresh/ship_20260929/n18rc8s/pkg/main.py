"""Semantic stack submission entry (main.py of a multi-file Kaggle agent archive; builder
scripts/package_semantic_ship_20260929.py). Candidate: n18rc8s. The strategy is the frozen project under this folder:
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

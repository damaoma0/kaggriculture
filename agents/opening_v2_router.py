"""Local research agent: selected growth opening, public router from day 9.

Loads sibling files; this is not a standalone Kaggle submission bundle.
The router replays coordinates, so this splice includes layout mismatch effects.
"""
import importlib.util
from pathlib import Path


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_opening = None
_router = None


def agent(obs):
    global _opening, _router
    if _opening is None or obs["step"] == 0:
        _opening = _load("hybrid_growth", "opening_v2.py")
        _router = _load("hybrid_router", "public/tschinkel_router_v31.py")
    if obs["step"] < 216:
        return _opening.agent(obs)
    return _router.agent(obs)

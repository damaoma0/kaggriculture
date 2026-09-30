"""Local research entry point; the archive has its own portable bootstrap."""
import sys
from pathlib import Path

_candidates=([Path(__file__).resolve().parents[1]] if '__file__' in globals() else [])
_candidates += [Path.cwd(),*Path.cwd().parents]
_root=next(p for p in _candidates if (p/'scripts/semantic_farm/policy.py').exists())
if str(_root/'scripts') not in sys.path:sys.path.insert(0,str(_root/'scripts'))
from semantic_farm.policy import SemanticFarm
_policy=None


def agent(observation,configuration=None):
    global _policy
    if _policy is None or observation['step']==0:_policy=SemanticFarm()
    return _policy(observation)

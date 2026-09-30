"""Research entry point; package with package_semantic_farm.py for isolation."""
import sys
from pathlib import Path
_root=Path(__file__).resolve().parents[1]
if str(_root/'scripts') not in sys.path:sys.path.insert(0,str(_root/'scripts'))
from semantic_farm.policy import SemanticFarm
_policy=None


def agent(observation,configuration=None):
    global _policy
    if _policy is None or observation['step']==0:_policy=SemanticFarm()
    return _policy(observation)

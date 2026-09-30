import sys
from pathlib import Path
_roots=([Path(__file__).resolve().parent] if '__file__' in globals() else [])+[Path('/kaggle_simulations/agent'),Path.cwd()]
_root=next(p for p in _roots if (p/'data/semantic_farm/model.json').exists())
sys.path.insert(0,str(_root/'scripts'))
from semantic_farm.policy import SemanticFarm
_agent=None
def semantic_farm_agent(observation,configuration=None):
    global _agent
    if _agent is None or observation['step']==0: _agent=SemanticFarm()
    return _agent(observation)

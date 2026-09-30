import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'scripts'))
from semantic_farm.policy import SemanticFarm
_agent=None
def semantic_farm_agent(observation,configuration=None):
    global _agent
    if _agent is None or observation['step']==0: _agent=SemanticFarm()
    return _agent(observation)

"""Bundle the public six-day router and the experimentally isolated sales adapter."""
import ast,json
from hashlib import sha256
from pathlib import Path
from market_corpus import ROOT,PATHS
from audit_router_advantage import OUT

def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    text=Path(E.__file__).read_text(encoding='utf-8');tree=ast.parse(text)
    funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    needed=set();constants=set()
    def visit(name):
        if name in needed:return
        needed.add(name)
        for n in ast.walk(funcs[name]):
            if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load):
                if n.id in funcs:visit(n.id)
                elif n.id.isupper() and hasattr(E,n.id):constants.add(n.id)
    visit('_apply_unit_action')
    source=PATHS['sixday'].read_text(encoding='utf-8').split("if __name__ == '__main__':")[0]
    source+='\n# Research addition: sell accessible milk/wool omitted by route orders.\n'
    source+='# Source/provenance and evaluation: docs/production_research.md\n'
    source+='# Deterministic unit projection below is extracted from the installed official\n# Kaggriculture 1.32.7 engine, using its default board/day/storage configuration.\n'
    source+='import copy\n_reference_agent = agent\ndel agent\n'
    for name in sorted(constants):source+=f'{name} = {getattr(E,name)!r}\n'
    for name in sorted(needed,key=lambda n:funcs[n].lineno):source+='\n'+ast.get_source_segment(text,funcs[name])+'\n'
    source+='''
def agent(observation, configuration=None):
    action = _reference_agent(observation, configuration)
    farm = copy.deepcopy(observation['farms'][observation['player']])
    private = copy.deepcopy(observation['private'])
    for i, order in enumerate([action['farmer'], *action['hands']]):
        _apply_unit_action(farm, private, i, order, 10, observation['day'], 24)
    for item in ('MILK', 'WOOL'):
        planned = sum(int(o[2]) for o in action['market'] if o[0] == 'SELL' and o[1] == item)
        extra = private['shed'].get(item, 0) - planned
        if extra > 0:
            existing = next((o for o in action['market'] if o[0] == 'SELL' and o[1] == item), None)
            if existing is not None:
                existing[2] += extra
            elif len(action['market']) < 10:
                action['market'].append(['SELL', item, extra])
    return action


if __name__ == '__main__':
    import sys
    for line in sys.stdin:
        if line.strip():
            request = json.loads(line)
            print(json.dumps(agent(request.get('observation', request), request.get('configuration'))), flush=True)
'''
    path=ROOT/'agents/production_candidate.py';path.write_text(source,encoding='utf-8')
    result={'candidate':str(path.relative_to(ROOT)),'sha256':sha256(path.read_bytes()).hexdigest(),
      'reference':str(PATHS['sixday'].relative_to(ROOT)),'reference_sha256':sha256(PATHS['sixday'].read_bytes()).hexdigest(),
      'engine_projection_functions':sorted(needed),'constants':sorted(constants),'status':'Awaiting fresh confirmation; not submitted.'}
    (OUT/'candidate_build.json').write_text(json.dumps(result,indent=2));print(result)

if __name__=='__main__':main()

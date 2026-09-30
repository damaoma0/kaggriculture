"""Bundle the selected ordering policy with stdlib-only engine helpers."""
import ast,json,sys,subprocess
from hashlib import sha256
from pathlib import Path
from market_corpus import load,PATHS
from research_adaptive_order import ROOT,OUT,BASE


def definitions(path,names):
    source=path.read_text(encoding='utf-8');tree=ast.parse(source)
    found={node.name:ast.get_source_segment(source,node) for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
    return '\n\n'.join(found[name] for name in names)


def main():
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    sys.path.insert(0,str(ROOT/'agents'))
    from adaptive_market_order import AdaptiveOrder
    from available_market_order import AvailabilityOrder
    mode=json.loads((OUT/'selection.json').read_text())['mode'];assert mode in ('available','static','clock','visible')
    original=Path(E.__file__).read_text(encoding='utf-8');tree=ast.parse(original)
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)};needed=set();constants={'PRODUCTS','SHOPS','ANIMALS'}
    def visit(name):
        if name in needed:return
        needed.add(name)
        for node in ast.walk(functions[name]):
            if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load):
                if node.id in functions:visit(node.id)
                elif node.id.isupper() and hasattr(E,node.id):constants.add(node.id)
    for name in ('market_price','_daily_refresh_animals'):visit(name)
    engine='import math\n'+'\n'.join(f'{name}={getattr(E,name)!r}' for name in sorted(constants))+'\n'
    engine+='\n\n'.join(ast.get_source_segment(original,functions[name]) for name in sorted(needed,key=lambda n:functions[n].lineno))
    policy=definitions(ROOT/'agents/market_forecast.py',['demand','consumption'])+'\n\n'
    policy+=definitions(ROOT/'agents/opponent_sales.py',['project','DeliveryModel'])+'\n\n'
    policy+=definitions(ROOT/'agents/adaptive_market_order.py',['execute_trade','priority_value','FlowModel','AdaptiveOrder'])
    policy+='\n\n'+definitions(ROOT/'agents/available_market_order.py',['AvailabilityOrder'])
    source=BASE.read_text(encoding='utf-8').split("if __name__ == '__main__':")[0]
    source+='\n# Adaptive order research: docs/adaptive_market_order.md\n'
    source+='''
_base_priority_agent=agent
del agent
import collections
import types
_engine_scope={}
'''
    source+=f'exec({engine!r},_engine_scope)\n'
    source+="_engine_scope['_apply_unit_action']=_apply_unit_action\n"
    source+="_policy_scope={'E':types.SimpleNamespace(**{k:v for k,v in _engine_scope.items() if k!='__builtins__'}),'deepcopy':copy.deepcopy,'deque':collections.deque,'Counter':collections.Counter,'GOODS':('MILK','WOOL')}\n"
    source+=f'exec({policy!r},_policy_scope)\n_ADAPTIVE_MODE={mode!r}\n'
    source+='''
_adaptive_policy=None
def agent(observation,configuration=None):
    global _adaptive_policy
    if _adaptive_policy is None or observation['step']==0:
        base=types.SimpleNamespace(agent=_base_priority_agent)
        _adaptive_policy=_policy_scope['AvailabilityOrder'](base) if _ADAPTIVE_MODE=='available' else _policy_scope['AdaptiveOrder'](base,_ADAPTIVE_MODE)
    return _adaptive_policy.agent(observation)

if __name__=='__main__':
    import sys
    for line in sys.stdin:
        if line.strip():
            request=json.loads(line)
            print(json.dumps(agent(request.get('observation',request),request.get('configuration'))),flush=True)
'''
    target=ROOT/'agents/adaptive_order_candidate.py';target.write_text(source,encoding='utf-8')
    for code in (source,engine,policy):
        for node in ast.walk(ast.parse(code)):
            if isinstance(node,ast.Import):assert all(a.name.split('.')[0] in sys.stdlib_module_names for a in node.names)
            if isinstance(node,ast.ImportFrom):assert node.module.split('.')[0] in sys.stdlib_module_names
    turns=0;initial=None
    for seed,opponent in ((120000,'sixday'),(120001,'pasture')):
        candidate=load(f'adaptive_packaged_{seed}',target)
        assert [k for k,v in vars(candidate).items() if callable(v)][-1]=='agent'
        base=load(f'adaptive_parity_{seed}',BASE)
        reference=AvailabilityOrder(base) if mode=='available' else AdaptiveOrder(base,mode)
        other=load(f'adaptive_parity_other_{seed}',PATHS[opponent])
        def act(obs):
            nonlocal initial,turns
            if initial is None:initial=json.loads(json.dumps(obs))
            expected=reference.agent(obs);actual=candidate.agent(obs)
            assert actual==expected,(seed,obs['step']);turns+=1;return actual
        def rival(obs):return other.agent(obs)
        env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720});env.run([act,rival])
        assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    cli=subprocess.run([sys.executable,str(target)],input=json.dumps({'observation':initial})+'\n',text=True,capture_output=True,check=True)
    assert json.loads(cli.stdout)==load('adaptive_cli_reference',target).agent(initial)
    result={'mode':mode,'candidate':str(target.relative_to(ROOT)),'sha256':sha256(target.read_bytes()).hexdigest(),'parity_actions':turns,
      'parity_games':2,'stdlib_only':True,'cli':'passed','engine_functions':sorted(needed),'status':'Parity passed; confirmation required before promotion.'}
    (OUT/'package.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()

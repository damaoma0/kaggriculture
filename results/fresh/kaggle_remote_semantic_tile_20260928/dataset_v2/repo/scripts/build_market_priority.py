"""Package the priority-only control; do not overwrite the selected agent."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'agents'))
from market_corpus import load,PATHS
from opponent_sales import OpponentPolicy
from research_opponent_sales import OUT


def main():
    source=ROOT/'agents/production_selected.py'
    assert sha256(source.read_bytes()).hexdigest()=='4e5ef404f1d4065a523fbc0d7c46597599350adfd7b66532f65e9fe961efc74d'
    text=source.read_text(encoding='utf-8')
    before,after=text.rsplit('    return action',1)
    text=before+"    action['market'].sort(key=lambda order: 0 if order[0] == 'SELL' and order[1] in ('MILK', 'WOOL') else 1)\n    return action"+after
    target=ROOT/'agents/market_priority_candidate.py'
    target.write_text(text,encoding='utf-8')
    imports={n.names[0].name.split('.')[0] if isinstance(n,ast.Import) else n.module.split('.')[0]
             for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.Import,ast.ImportFrom))}
    assert imports<=sys.stdlib_module_names,imports-sys.stdlib_module_names
    from kaggle_environments import make
    checks=0;initial=None
    for seed,opponent in ((120000,'sixday'),(120001,'pasture')):
        reference=OpponentPolicy(load(f'priority_reference_{seed}',source),'priority')
        candidate=load(f'priority_packaged_{seed}',target)
        assert [k for k,v in vars(candidate).items() if callable(v)][-1]=='agent'
        other=load(f'priority_opponent_{seed}',PATHS[opponent])
        def act(obs):
            nonlocal checks,initial
            if initial is None:initial=json.loads(json.dumps(obs))
            expected=reference.act(obs);actual=candidate.agent(obs)
            assert expected==actual,(seed,obs['step'])
            checks+=1
            return actual
        def rival(obs):return other.agent(obs)
        env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
        env.run([act,rival])
        assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    response=subprocess.run([sys.executable,str(target)],input=json.dumps({'observation':initial})+'\n',text=True,capture_output=True,check=True)
    fresh=load('priority_cli_reference',target)
    assert json.loads(response.stdout)==fresh.agent(initial)
    result={'candidate':str(target.relative_to(ROOT)),'sha256':sha256(target.read_bytes()).hexdigest(),
      'status':'packaged control; promotion requires evaluation','parity_turns':checks,'parity_games':2,'stdlib_imports':sorted(imports),
      'cli':'passed','agent_last_callable':True}
    (OUT/'priority_package.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))


if __name__=='__main__':main()

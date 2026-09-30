"""Embed the frozen forecast and native planner in a standalone agent."""
import json
from hashlib import sha256
from market_corpus import ROOT

def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    base=ROOT/'agents/v45_our_selected.py'
    assert sha256(base.read_bytes()).hexdigest()=='88cb37b9a35434f4edb89a6dfa7c51a2681d21c12ebaa94c3a2dd5ad18650059'
    folder=ROOT/'results/fresh/event_prices';assert json.loads((folder/'summary.json').read_text(encoding='utf-8'))['forecast_gate_passed']
    modelpath=folder/'models.json'
    assert sha256(modelpath.read_bytes()).hexdigest()==json.loads((folder/'model_freeze.json').read_text(encoding='utf-8'))['sha256']
    models=json.loads(modelpath.read_text(encoding='utf-8'))['models']
    models={k:v for k,v in models.items() if k.split('/')[0] in ('WHEAT','CARROT') and k.endswith('/event')}
    feature=(ROOT/'agents/event_price_forecast.py').read_text(encoding='utf-8').replace('from kaggle_environments.envs.kaggriculture import kaggriculture as E','')
    text=base.read_text(encoding='utf-8')
    start=text.index('def _r68_joint_plans(');end=text.index('\nagent=globals()',start)
    joint=text[start:end].replace('def _r68_joint_plans(', 'def _event_joint_candidate(')
    original="value=sum(n*max(1,_r37_market_price(item,obs['market']['inventory'][item]+all_units[item]+n)-2) for item,n in units.items())"
    assert joint.count(original)==1
    joint=joint.replace(original,'value=_event_route_value(obs,action,path,targets,i,all_units,units)')
    extras='\nfrom types import SimpleNamespace as _EventConstants\n'
    extras+='_EVENT_NS={"E":_EventConstants(**'+repr(dict(CROPS=E.CROPS,ANIMALS=E.ANIMALS,SHOPS=E.SHOPS))+')}\n'
    extras+='exec('+repr(feature)+',_EVENT_NS)\n_EVENT_COEFFICIENTS='+repr(models)+'\n'
    extras+=joint+'\n'+(ROOT/'agents/event_input_overlay.py').read_text(encoding='utf-8')
    path=ROOT/'agents/v45_event_candidate.py';path.write_text(text+extras,encoding='utf-8')
    print(path,sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':main()

"""Freeze the validation winner before evaluating untouched test scenarios."""
import json
from statistics import mean
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/shop_grid'


def main():
    rows=json.loads((OUT/'validate.json').read_text())
    assert len(rows)==128
    learned=json.loads((OUT/'learned.json').read_text())
    names=('public-router','growth-control','shop-fixed','shop-adaptive')
    scores={n:mean(r['margin'] for r in rows if r['name']==n) for n in names}
    name=max(names,key=lambda n:scores[n])
    configs={'public-router':{'default':'router'},'growth-control':{'cows':4,'sheep':4},'shop-fixed':learned['fixed'],'shop-adaptive':learned['adaptive']}
    selection={'name':name,'config':configs[name],'validation_mean_margins':scores,'criterion':'Highest validation mean final cash margin; test panel not inspected'}
    if (OUT/'selection.json').exists():
        assert json.loads((OUT/'selection.json').read_text())==selection
    else:
        assert not (OUT/'test.json').exists(), 'Freeze selection before testing'
        (OUT/'selection.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
    source='''"""Selected local opening, frozen before the shop-grid test panel.

Research opening only; requires sibling modules. Evaluation switches both
farms to the common replanting controller at step 216.
"""
import importlib.util
from pathlib import Path

NAME = %s
CONFIG = %s
_policy = None


def agent(obs):
    global _policy
    if _policy is None or obs["step"] == 0:
        filename = "opening_v2.py" if NAME == "growth-control" else "shop_opening.py"
        spec = importlib.util.spec_from_file_location("selected_opening_module", Path(__file__).with_name(filename))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _policy = module.GrowthOpening(CONFIG) if NAME == "growth-control" else module.ShopOpening(CONFIG)
    return _policy(obs)
'''%(repr(name),repr(configs[name]))
    (ROOT/'agents/opening_v3.py').write_text(source,encoding='utf-8')
    print(json.dumps(selection,indent=2))


if __name__=='__main__':main()

"""Fit refinements and adaptive policies on training only; freeze validation winner."""
import argparse
import json
from statistics import mean
from research_midgame import OUT,ROOT


def groups(rows):
    return {n:[r for r in rows if r['name']==n] for n in sorted({r['name'] for r in rows})}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=('refine','shortlist','select'),required=True);args=ap.parse_args()
    train=json.loads((OUT/'train.json').read_text());assert len(train)==240
    if args.stage=='refine':
        g=groups(train);eligible=[n for n in g if n not in ('router','legacy','no-branches')]
        best=max(eligible,key=lambda n:mean(r['margin'] for r in g[n]));cfg=g[best][0]['config']
        variants={'refine-base':cfg}
        for crop in ('CARROT','TOMATO','STRAWBERRY'):variants['refine-'+crop.lower()]=dict(cfg,replant=crop)
        variants['refine-land']=dict(cfg,land=True)
        variants['refine-reserve100']=dict(cfg,reserve=100)
        variants['refine-reserve600']=dict(cfg,reserve=600)
        variants['refine-stop18']=dict(cfg,stop_day=18)
        variants['refine-sell10']=dict(cfg,sell_floor=10)
        (OUT/'refinements.json').write_text(json.dumps(variants,indent=2),encoding='utf-8')
        print('Refining',best,json.dumps(cfg));return
    refine=json.loads((OUT/'refine.json').read_text());assert len(refine)==144
    combined=train+refine;g=groups(combined)
    if args.stage=='shortlist':
        names=[n for n in g if n not in ('router','legacy','no-branches')]
        best=max(names,key=lambda n:mean(r['margin'] for r in g[n]))
        adaptive={}
        for yarn,key in ((True,'yarn'),(False,'other')):
            pick=max(g,key=lambda n:.5*mean(r['margin'] for r in g[n] if r['yarn']==yarn)+.5*mean(r['margin'] for r in g[n]))
            adaptive[key]={'name':pick,'config':g[pick][0]['config']}
        shortlist={best:g[best][0]['config'],'adaptive':adaptive}
        (OUT/'shortlist.json').write_text(json.dumps(shortlist,indent=2),encoding='utf-8')
        print(json.dumps(shortlist,indent=2));return
    rows=json.loads((OUT/'validate.json').read_text());assert len(rows)==160
    vg=groups(rows)
    score={n:mean(r['margin'] for r in rs) for n,rs in vg.items()}
    best=max(score,key=lambda n:(score[n],n=='router'))
    selected={'name':best,'config':vg[best][0]['config'],'validation_mean_margin':score,'criterion':'Mean paired final cash margin, equal weighting of full-router and legacy-maintenance opponents; ties retain the router. Frozen before testing.'}
    p=OUT/'selection.json'
    if p.exists():assert json.loads(p.read_text())==selected
    else:
        assert not (OUT/'test.json').exists()
        p.write_text(json.dumps(selected,indent=2),encoding='utf-8')
    source='''"""Frozen local research policy: public-router opening then selected midgame.

Requires workspace sibling modules and the installed game engine.
"""
import importlib.util
from pathlib import Path
from kaggle_environments.envs.kaggriculture import kaggriculture as E

KIND = %s
CONFIG = %s
_router = None
_tail = None


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def agent(obs):
    global _router,_tail
    if _router is None or obs['step']==0:
        _router=load('frozen_router',Path(__file__).parent/'public/tschinkel_router_v31.py')
        _tail=None
    if obs['step']<216:return _router.agent(obs)
    if _tail is None:
        kind,cfg=KIND,CONFIG
        if kind=='adaptive':
            branch=cfg['yarn' if 'YARN_STORE' in obs['town']['unlocked_shops'] else 'other']
            kind,cfg=branch['name'],branch['config']
        if kind in ('router','no-branches'):
            if kind=='no-branches':_router.DECISIONS=()
            _tail=_router.agent
        elif kind=='legacy':
            module=load('frozen_legacy',Path(__file__).parents[1]/'scripts/evaluate_boards.py')
            _tail=module.continuation('replant',10,obs,E)
        else:
            module=load('frozen_mid',Path(__file__).with_name('midgame_v1.py'))
            _tail=module.Midgame(obs,cfg)
    return _tail(obs)
'''%(repr(best),repr(selected['config']))
    (ROOT/'agents/midgame_selected.py').write_text(source,encoding='utf-8')
    print(json.dumps(selected,indent=2))


if __name__=='__main__':main()

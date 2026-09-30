"""Frozen local research policy: public-router opening then selected midgame.

Requires workspace sibling modules and the installed game engine.
"""
import importlib.util
from pathlib import Path
from kaggle_environments.envs.kaggriculture import kaggriculture as E

KIND = 'router'
CONFIG = {}
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

"""Causal, precompiled coherent-V5 opening adapter, strictly for days 0 through 5.

Historical successful input quantities are compiled once. Runtime consumes only
the supplied observation and fixed historical policy data. Physical work is
projected on a private copy with verbatim official engine unit-action helpers.
The caller owns strategy/tiling from step 144 onward.
"""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
import gzip
import json
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1] / 'data/semantic_strategy/opening_v5_contracts_20260928.json.gz'
_CACHE = None


def _contracts(path):
    global _CACHE
    if path == CONTRACTS and _CACHE is not None:
        return _CACHE
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        data = json.load(handle)
    if path == CONTRACTS:
        _CACHE = data
    return data


class Opening:
    def __init__(self, contracts_path=None):
        data = _contracts(Path(contracts_path) if contracts_path is not None else CONTRACTS)
        # Chassis copies each emitted action. Only per-route derived metadata is
        # written while loading; sharing immutable action data avoids copying
        # 63k historical action trees for every new policy instance.
        library = {'actions': data['library']['actions'], 'tapes': [dict(t) for t in data['library']['tapes']]}
        self.ns = {'__name__': 'semantic_strategy_opening_core', '_MGT_LIB': library}
        exec(compile(data['core_source'], 'precompiled_coherent_opening_core', 'exec'), self.ns)
        self.ns['_MGT_CFG']['default_route'] = data['default_route']
        self.chassis = self.ns['_MGT_IMPL'].chassis
        self.work_ns = {}
        exec(compile(data['work_source'], 'opening_exact_work_helpers', 'exec'), self.work_ns)
        self.history = []
        self.stats = Counter()

    def after_work(self, obs, action):
        farm = deepcopy(obs['farms'][int(obs['player'])])
        private = deepcopy(obs['private'])
        commands = [action.get('farmer') or ['PASS'], *(action.get('hands') or [])]
        demand = Counter(c[1] for c in commands if c and c[0] == 'PLANT')
        blocked = {crop for crop, n in demand.items() if n > private['seeds'].get(crop, 0)}
        for index, cmd in enumerate(commands):
            if cmd and cmd[0] == 'PLANT' and cmd[1] in blocked:
                continue
            self.work_ns['_apply_unit_action'](farm, private, index, cmd, 10, int(obs['day']), 24, 100)
        return private

    def act(self, obs, configuration=None):
        step = int(obs['step'])
        if not 0 <= step < 144:
            raise ValueError('Opening is defined only for steps 0 through 143; hand off on day 6.')
        action = self.ns['mgt_kaggle_entry'](obs, configuration)
        route = self.chassis.players[int(obs['player'])]['route']
        upcoming = self.chassis.routes[route][step + 1]
        commands = [upcoming.get('farmer') or ['PASS'], *(upcoming.get('hands') or [])]
        private = self.after_work(obs, action)
        original = action.get('market', [])
        market = [list(o) for o in original if o]
        # Preserve V3 -> V4 -> V5 order, including inert market queue slots.
        # V3: first-day wheat procurement and imminent seed top-up.
        if step < 24:
            market = [o for o in market if not (len(o) >= 3 and o[1] == 'WHEAT' and o[0] in ('SELL', 'BUY_PRODUCT'))]
            need = sum(int(c[2]) if len(c) > 2 else 1 for c in commands if c and c[0] == 'PICKUP' and c[1] == 'WHEAT')
            q = max(0, need - private['shed'].get('WHEAT', 0))
            if q:
                market = [o for o in market if len(o) < 3 or o[2] > 0]
                if len(market) < 10:
                    market.append(['BUY_PRODUCT', 'WHEAT', q])
        needs = Counter(c[1] for c in commands if c and c[0] == 'PLANT')
        for crop, required in needs.items():
            purchases = sum(o[2] for o in market if len(o) >= 3 and o[:2] == ['BUY_SEED', crop])
            extra = max(0, required - private['seeds'].get(crop, 0) - purchases)
            if not extra:
                continue
            old = next((o for o in market if o[:2] == ['BUY_SEED', crop]), None)
            if old:
                old[2] += extra
            else:
                market = [o for o in market if len(o) < 3 or o[2] > 0]
                if len(market) < 10:
                    market.append(['BUY_SEED', crop, extra])
        # V4: retain only seeds needed for the next physical planting.
        market = [o for o in market if o and o[0] != 'BUY_SEED']
        for crop, required in needs.items():
            q = max(0, required - private['seeds'].get(crop, 0))
            if q:
                market = [o for o in market if len(o) < 3 or o[2] > 0]
                if len(market) < 10:
                    market.append(['BUY_SEED', crop, q])
        # V5: exact post-work wheat procurement through the second day.
        if step < 48:
            market = [o for o in market if o and not (len(o) >= 3 and o[1] == 'WHEAT' and o[0] in ('SELL', 'BUY_PRODUCT'))]
            need = sum(int(c[2]) if len(c) > 2 else 1 for c in commands if c and c[0] == 'PICKUP' and c[1] == 'WHEAT')
            q = max(0, need - private['shed'].get('WHEAT', 0))
            if q:
                market = [o for o in market if len(o) < 3 or o[2] > 0]
                if len(market) < 10:
                    market.append(['BUY_PRODUCT', 'WHEAT', q])
        if step % 24 == 0:
            self.history.append(dict(day=step // 24, historical_route=route))
        return dict(action, market=market)

    __call__ = act


def make_opening(contracts_path=None):
    return Opening(contracts_path)

"""Continuation feasibility across three public-cohort rival-sale scenarios."""
from copy import deepcopy
import rival_trajectory_model_v3 as M
from coherent_switch_v6 import ContractPolicy, make_policy as previous_policy


class MarketGuardPolicy(ContractPolicy):
    def __init__(self):
        super().__init__(probe=True)
        self.active_world = None
        self.world_key = None
        self.worlds = []
        original = self.projector.namespace['interpreter']

        def interpreter(states, env):
            world = self.active_world
            if world is not None:
                step = int(states[0].observation.step)
                own = self.active_seat
                rival = states[1-own]
                farm = states[0].observation.farms[1-own]
                farm['money'] = 10_000_000
                if step % 24 == 0:
                    predicted = world['farms'][step//24]
                    farm['tiles'] = deepcopy(predicted['tiles'])
                    farm['unlocked_quadrants'] = deepcopy(predicted['unlocked_quadrants'])
                flows = world['hourly'].get(step, {})
                rival.observation.private['shed'] = {p:n for p,n in flows.items() if n>0}
                rival.action = dict(farmer=['PASS'],hands=[],market=[
                    ['SELL' if n>0 else 'BUY_PRODUCT',p,abs(n)] for p,n in flows.items() if n])
            return original(states, env)

        self.projector.namespace['interpreter'] = interpreter

    def probe(self, obs, route):
        key = (int(obs['player']), int(obs['step']))
        if self.world_key != key:
            self.worlds = [M.world(obs, i) for i in (0,2,4)]
            self.world_key = key
        self.active_seat = int(obs['player'])
        rows = []
        try:
            for world in self.worlds:
                self.active_world = world
                row = super().probe(obs, route)
                rows.append(dict(row, donor=world['donor']))
        finally:
            self.active_world = None
        return dict(failed_hires=max(r.get('failed_hires',0) for r in rows),
                    failed_spending=max(r.get('failed_spending',0) for r in rows),
                    cash=min(r['cash'] for r in rows),
                    lost=sorted(set(a for r in rows for a in r['lost'])), scenarios=rows)


def make_policy(arm):
    if arm == 'market_guard':return MarketGuardPolicy()
    return previous_policy(arm)

"""Research continuation contracts and short physical feasibility probes.

Reads only the current observation and recorded donor plans. Probes freeze the
revealed shops, use a PASS rival, and never access evaluation worlds or seeds.
They are feasibility heuristics, not profit forecasts.
"""
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import time

from coherent_opening_v5 import SemanticInputPolicy, make_policy as previous_policy
from coherent_opening_policy import PASS


class ContractPolicy(SemanticInputPolicy):
    def __init__(self, probe=False):
        super().__init__(bank=True)
        self.probe_enabled = probe
        self.chassis.router = self.router
        self.shadow = self.ns['make_agent'](self.chassis.routes,
            router=lambda obs, step, state: self.shadow_route,
            **self.ns['_MGT_CFG']['settings']).chassis
        self.shadow._future_sells = self.chassis._future_sells
        self.probe_counts = Counter()
        self.probe_farm = None
        engine = self.projector.namespace
        old_hire, old_commit = engine['_do_hire'], engine['_commit_unit']

        def hire(farm, private, *args, **kwargs):
            before = farm['hires_today']
            result = old_hire(farm, private, *args, **kwargs)
            if farm is self.probe_farm and farm['hires_today'] == before:
                self.probe_counts['failed_hires'] += 1
            return result

        def commit(op, item, price, farm, private, *args, **kwargs):
            result = old_commit(op, item, price, farm, private, *args, **kwargs)
            if farm is self.probe_farm and not result and op != 'SELL':
                self.probe_counts['failed_spending'] += 1
            return result

        engine['_do_hire'], engine['_commit_unit'] = hire, commit

    @staticmethod
    def identity(tile):
        if not isinstance(tile, dict):
            return None
        if tile.get('crop') in ('STRAWBERRY', 'MELON'):
            return tile['crop'], tile.get('planted_day')
        if tile.get('animal'):
            return tile['animal'], tile.get('placed_day')
        return None

    def assets(self, farm):
        return {(x, y, self.identity(tile)) for y, row in enumerate(farm['tiles'])
                for x, tile in enumerate(row) if self.identity(tile) is not None}

    def state_cost(self, farm, private, trace, day):
        donor = trace['daily'][day]
        cost = 0.0
        for live_row, ref_row in zip(farm['tiles'], donor['farm']['tiles']):
            for live, ref in zip(live_row, ref_row):
                if not isinstance(live, dict) or not isinstance(ref, dict):
                    continue
                if self.ns['_mgt_label'](live) != self.ns['_mgt_label'](ref):
                    continue
                for field in ('planted_day', 'placed_day'):
                    if field in ref and field in live:
                        cost += min(3, abs(live[field] - ref[field])) * 2.0
                cost += min(3, abs(live.get('yield_units', 0) - ref.get('yield_units', 0))) * .5
                for field in ('consecutive_unwatered', 'consecutive_unfed', 'consecutive_uncared'):
                    cost += max(0, live.get(field, 0) - ref.get(field, 0)) * 2.0
        # Held source seed is a real prerequisite, whereas its bank balance can
        # contain unnecessary savings. Only charge for missing input inventory.
        seed_prices = {'WHEAT':10, 'CARROT':20, 'TOMATO':50, 'MELON':80, 'STRAWBERRY':100}
        cost += sum(max(0, n-private['seeds'].get(p, 0))*seed_prices.get(p, 0)
                    for p, n in donor['private']['seeds'].items()) / 100.0
        return cost

    def probe(self, obs, route):
        start = int(obs['step']); own = int(obs['player'])
        states = self.projector.state(obs)
        self.probe_farm = states[0].observation.farms[own]
        self.probe_counts = Counter()
        self.shadow_route = route
        self.shadow.players = deepcopy(self.chassis.players)
        self.shadow.players[own]['last_step'] = start-1
        self.shadow.players[own]['route'] = route
        self.shadow.players[own]['router_state']['route'] = route
        conf = self.projector.structify(dict(episodeSteps=720, boardSize=10, turnsPerDay=24,
            shedCapacity=100, maxMarketOrdersPerTurn=10, farmHandCostMult=1,
            townShopUnlockInterval=10000, townShopSellInterval=4,
            townCenterSellInterval=24, weedSpawnChance=0))
        env = SimpleNamespace(done=False, info={'seed':0}, configuration=conf)
        initial = self.assets(self.probe_farm)
        # Include the next morning's first three turns, where the failed-hire
        # cascade in the qualification case began.
        stop = min(719, (start//24+1)*24+3)
        try:
            for step in range(start, stop):
                for state in states:
                    state.observation.step = step
                states[own].action = self.shadow.act(states[own].observation)
                states[1-own].action = deepcopy(PASS)
                self.projector.namespace['interpreter'](states, env)
            return dict(self.probe_counts, cash=self.probe_farm['money'],
                        lost=sorted(initial-self.assets(self.probe_farm)), steps=stop-start)
        finally:
            self.probe_farm = None
            self.shadow.players.clear()

    def router(self, obs, step, state):
        ns = self.ns
        current = state.setdefault('route', ns['_MGT_CFG']['default_route'])
        if step % 24 or step < 72 or step > 28*24:
            return current
        day = step//24; own = int(obs['player'])
        farm = obs['farms'][own]
        board = ns['_mgt_labels'](ns['_mgt_board'](farm))
        shops = obs['town']['unlocked_shops']
        vectors = [ns['_mgt_vec'](shops, j) for j in range(9)]
        live_animals = [j for j, label in enumerate(board) if label in ns['_MGT_ANIMAL_LABELS']]
        ranked = []
        for route, tape in enumerate(ns['_MGT_TAPES']):
            mismatch = ns['_mgt_hamming'](board, tape['lab'][day])
            if mismatch > 8 and route != current:
                continue
            score = ns['_mgt_distance'](vectors, shops, tape, len(shops)) + mismatch
            if mismatch > 8: score += 4
            score += 4*sum(tape['lab'][day][j] not in ns['_MGT_ANIMAL_LABELS'] and
                           tape['lab'][min(29,day+2)][j] not in ns['_MGT_ANIMAL_LABELS']
                           for j in live_animals)
            contract = self.state_cost(farm, obs['private'], self.references[route], day)
            ranked.append(dict(route=route, score=score+contract, state_cost=contract,
                               mismatches=mismatch))
        ranked.sort(key=lambda row:(row['score'], row['route']!=current, row['mismatches'], row['route']))
        selected = ranked[0]['route']
        probes = []
        started = time.perf_counter()
        if self.probe_enabled and selected != current:
            # Keep the incumbent in the compared set. No new candidate outside
            # the normal physical-neighborhood gate is admitted here.
            options = ranked[:4]
            if current not in [r['route'] for r in options]:
                options.append(next(r for r in ranked if r['route']==current))
            by_route = {r['route']:self.probe(obs, r['route']) for r in options}
            base_lost = {tuple(x) for x in by_route[current]['lost']}
            for row in options:
                p = by_route[row['route']]
                added_loss = len({tuple(x) for x in p['lost']}-base_lost)
                penalty = 12*p.get('failed_hires',0) + min(10,p.get('failed_spending',0)) + 8*added_loss
                probes.append(dict(row, probe=p, added_asset_losses=added_loss,
                                   guarded_score=row['score']+penalty))
            selected = min(probes, key=lambda r:(r['guarded_score'],r['route']!=current,
                                                 r['mismatches'],r['route']))['route']
        state['route'] = selected
        self.stats['contract_decisions'] += 1
        self.stats['probe_rollouts'] += len(probes)
        self.stats['contract_switches'] += selected != current
        self.history.append(dict(event='contract_selection', step=step, incumbent=current,
            selected=selected, shortlist=ranked[:5], probes=probes, seconds=time.perf_counter()-started))
        return selected


def make_policy(arm):
    if arm == 'contracts': return ContractPolicy(False)
    if arm == 'guarded': return ContractPolicy(True)
    return previous_policy(arm)

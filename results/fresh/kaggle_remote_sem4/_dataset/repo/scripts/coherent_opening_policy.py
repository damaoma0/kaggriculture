"""Research-only coherent DSM family with successful orders and funding repair.

The forecast receives only the current observation and the chosen donor plan.
It uses a PASS rival, no new shops or weeds, and never receives the evaluation
seed, opponent private state or unrevealed shop sequence.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import gzip
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'results/fresh/coherent_opening_20260924_01a0'
SEED_COST = {'WHEAT':10, 'CARROT':20, 'MELON':80, 'STRAWBERRY':100, 'TOMATO':50}
ANIMAL_COST = {'COW':400, 'SHEEP':500, 'GOOSE':300}
PASS = {'farmer':['PASS'], 'hands':[], 'market':[]}


def load_entry(path):
    from kaggle_environments.agent import get_last_callable
    return get_last_callable(path.read_text(encoding='utf-8'), path=str(path))


def _load_traces():
    folder = OUT/'extraction/full'
    index = json.loads((folder/'index.json').read_text(encoding='utf-8'))
    paths = [folder/row['path'] for row in index if row.get('team') == 'DSM']
    if not paths:
        raise FileNotFoundError(f'No verified full-season traces in {folder}')
    result = {}
    for path in paths:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            trace = json.load(handle)
        if trace.get('team') != 'DSM':
            continue
        result.setdefault(int(trace['episode']), []).append(trace)
    return result


def normalised_actions(original, trace):
    """Keep sale requests in place; remove unsuccessful spending only."""
    fills = trace['market_success_by_order']
    assert len(original) == len(fills) == 719
    output = []
    for t, action in enumerate(original):
        new = deepcopy(action)
        market = []
        for index, order in enumerate((action.get('market') or [])[:10]):
            if not order:
                market.append(['SELL','WHEAT',0])
            elif order[0] == 'SELL':
                market.append(list(order))
            elif index < len(fills[t]) and fills[t][index]:
                filled = fills[t][index]
                assert filled[0] == order[0], (t,index,order,filled)
                market.append(list(filled))
            else:
                # Keep the lockstep market queue position. Removing a failed
                # order can alter later prices against the other player's queue.
                market.append(['SELL','WHEAT',0])
        new['market'] = market
        output.append(new)
    return output


class Projection:
    """Private interpreter copy: projections cannot enter the evaluation ledger."""
    def __init__(self):
        from kaggle_environments.envs.kaggriculture import kaggriculture as installed
        self.namespace = {'__file__':installed.__file__, '__name__':'coherent_private_engine'}
        exec(compile(Path(installed.__file__).read_text(encoding='utf-8'), installed.__file__, 'exec'), self.namespace)
        from kaggle_environments.utils import structify
        self.structify = structify
        self.credit = 0
        self.seat_farm = None
        original_hire = self.namespace['_do_hire']
        def hire(farm, private, board_size, mult=1):
            if farm is self.seat_farm:
                cost = self.namespace['_hire_cost'](farm['hires_today'], mult)
                short = max(0, cost-farm['money'])
                self.credit += short
                farm['money'] += short  # Forecast credit measures the deficit; never a live-game action.
            return original_hire(farm, private, board_size, mult)
        self.namespace['_do_hire'] = hire

    def state(self, obs):
        own = int(obs['player'])
        copied = deepcopy(obs)
        states = []
        for seat in (0,1):
            private = copied['private'] if seat == own else self.namespace['_new_private']()
            if seat != own:
                private['inventories'] = [{} for _ in range(len(copied['farms'][seat]['hands'])+1)]
            observation = dict(copied, player=seat, private=private)
            states.append(self.structify(dict(observation=observation, action=deepcopy(PASS), status='ACTIVE', reward=None)))
        for key in ('farms','market','town'):
            states[1].observation[key] = states[0].observation[key]
        return states

    def deficit(self, obs, first, tape, stop):
        states = self.state(obs)
        own = int(obs['player'])
        self.seat_farm = states[0].observation.farms[own]
        self.credit = 0
        env = SimpleNamespace(done=False, info={'seed':0}, configuration=self.structify(dict(
            episodeSteps=720, boardSize=10, turnsPerDay=24, shedCapacity=100,
            maxMarketOrdersPerTurn=10, farmHandCostMult=1, townShopUnlockInterval=10000,
            townShopSellInterval=4, townCenterSellInterval=24, weedSpawnChance=0)))
        start = int(obs['step'])
        for t in range(start, min(719, stop)):
            for s in states:
                s.observation.step = t
            states[own].action = deepcopy(first if t == start else tape[t])
            states[1-own].action = deepcopy(PASS)
            self.namespace['interpreter'](states, env)
        return self.credit

    def projected_shed(self, obs, action):
        farm = deepcopy(obs['farms'][int(obs['player'])])
        private = deepcopy(obs['private'])
        commands = [action.get('farmer') or ['PASS'], *(action.get('hands') or [])]
        demand = Counter(c[1] for c in commands if c and c[0] == 'PLANT')
        blocked = {c for c,n in demand.items() if n > private['seeds'].get(c,0)}
        for index, cmd in enumerate(commands):
            if cmd and cmd[0] == 'PLANT' and cmd[1] in blocked:
                continue
            self.namespace['_apply_unit_action'](farm, private, index, cmd, 10, int(obs['day']), 24, 100)
        return private['shed']


class CoherentPolicy:
    def __init__(self, funded=False):
        self.entry = load_entry(ROOT/'agents/mgt_dsm_a.py')
        self.ns = self.entry.__globals__
        self.chassis = self.ns['_MGT_IMPL'].chassis
        traces = _load_traces()
        self.references = {}
        for route, tape in enumerate(self.ns['_MGT_TAPES']):
            options = traces[int(tape['ep'])]
            # Self-play episodes contain two seats. Physical commands identify
            # the source even though the compiled agent already trimmed hires.
            current = self.chassis.routes[route]
            def distance(trace):
                return sum((a.get('farmer'),a.get('hands')) != (b.get('farmer'),b.get('hands'))
                           for a,b in zip(current,trace['actions']))
            trace = min(options, key=distance)
            assert distance(trace) == 0, (route,tape['ep'],'source action mismatch')
            actions = normalised_actions(trace['actions'], trace)
            self.chassis.routes[route] = actions
            self.ns['_MGT_ROUTES'][route] = actions
            self.references[route] = trace
        self.chassis._future_sells.clear()
        self.funded = funded
        self.projector = Projection() if funded else None
        self.stats = Counter()
        self.history = []

    def _route(self, obs):
        return self.chassis.players[int(obs['player'])]['route']

    def _stop(self, tape, step):
        next_day = step//24+1
        hires = [t for t in range(next_day*24,min(719,next_day*24+12))
                 if any(o and o[0]=='HIRE' for o in tape[t].get('market',[]))]
        return min(719, max(hires,default=next_day*24+1)+1)

    def _free_sell(self, obs, action, tape, stop):
        stock = self.projector.projected_shed(obs, action)
        planned = Counter()
        need = Counter()
        step = int(obs['step'])
        for order in action.get('market',[]):
            if order[0]=='SELL': planned[order[1]] += int(order[2])
        for t in range(step,min(stop,len(tape))):
            a = action if t == step else tape[t]
            for cmd in [a.get('farmer') or ['PASS'], *(a.get('hands') or [])]:
                if cmd and cmd[0]=='FEED': need['WHEAT'] += 1
                elif cmd and cmd[0]=='FERTILIZE': need['FERTILIZER'] += 1
        # The whole remaining horizon's feed is protected; no forecast harvest
        # or purchase is credited when deciding what existing feed is free.
        prices = obs['market']['prices']
        free = {p:max(0,n-planned[p]-need[p]) for p,n in stock.items()
                if p in prices and prices[p]>1}
        return sorted(((prices[p],p,n) for p,n in free.items() if n), reverse=True)

    def __call__(self, obs, configuration=None):
        action = self.entry(obs, configuration)
        if int(obs['step']) % 24 == 0:
            route = self._route(obs)
            trace = self.references[route]
            reference = next(row for row in trace['daily'] if row['day'] == int(obs['day']))
            farm = obs['farms'][int(obs['player'])]
            label = lambda tile: (tile.get('kind'), tile.get('crop'), tile.get('animal')) if isinstance(tile,dict) else tile
            tiles = [(live, donor) for lr,dr in zip(farm['tiles'],reference['farm']['tiles']) for live,donor in zip(lr,dr)]
            mismatch = sum(label(live) != label(donor) for live,donor in tiles)
            ages = sum(isinstance(live,dict) and isinstance(donor,dict) and label(live)==label(donor)
                       and (live.get('planted_day'),live.get('placed_day')) != (donor.get('planted_day'),donor.get('placed_day'))
                       for live,donor in tiles)
            self.history.append(dict(event='route',step=int(obs['step']),route=route,
                episode=trace['episode'],source_seat=trace['seat'],tile_mismatches=mismatch,cohort_mismatches=ages))
        if not self.funded or int(obs['day'])>11:
            return action
        step = int(obs['step'])
        market = [list(o) for o in action.get('market',[]) if o]
        spending = any(o[0] in ('BUY_ANIMAL','BUY_LAND','BUY_SEED','BUY_PRODUCT','HIRE') for o in market)
        if not spending:
            return action
        route = self._route(obs)
        tape = self.chassis.routes[route]
        stop = self._stop(tape,step)
        gap = self.projector.deficit(obs,action,tape,stop)
        self.stats['projections'] += 1
        if gap <= 0:
            return action
        original_gap = gap
        changes = []
        # Release saleable output before capital orders; preserve existing feed.
        for price,item,quantity in self._free_sell(obs,action,tape,stop):
            q = min(quantity, max(1,int((gap+price-1)//price)))
            existing = next((o for o in market if o[0]=='SELL' and o[1]==item),None)
            if existing:
                existing[2] += q
            elif len(market)<10:
                market.insert(0,['SELL',item,q])
            else:
                continue
            market.sort(key=lambda o: 0 if o[0]=='SELL' else 1)
            action = dict(action,market=deepcopy(market))
            changes.append(['early_sale',item,q])
            gap = self.projector.deficit(obs,action,tape,stop)
            self.stats['projections'] += 1
            if gap<=0: break
        # Pilot guard: if output is insufficient, reserve wages by cancelling
        # discretionary purchases. Cohort effects must pass the development gate.
        if gap>0:
            for order in reversed(market):
                if order[0] not in ('BUY_ANIMAL','BUY_LAND','BUY_SEED'):
                    continue
                while gap>0 and (order[0]=='BUY_LAND' or order[2]>0):
                    if order[0]=='BUY_LAND':
                        order[:] = ['DEFERRED']
                        changes.append(['cancelled_land'])
                    else:
                        order[2] -= 1
                        changes.append(['cancelled_buy',order[0],order[1],1])
                    trial = [o for o in market if o[0]!='DEFERRED' and (len(o)<3 or o[2]>0)]
                    action = dict(action,market=deepcopy(trial))
                    gap = self.projector.deficit(obs,action,tape,stop)
                    self.stats['projections'] += 1
                    if order[0]=='DEFERRED': break
                if gap<=0: break
        self.stats['funding_interventions'] += 1
        self.stats['unresolved_projected_hire_deficits'] += int(gap>0)
        self.history.append(dict(event='funding',step=step,route=route,initial_gap=original_gap,remaining_gap=gap,changes=changes))
        return action


def make_policy(arm):
    if arm=='baseline': return load_entry(ROOT/'agents/mgt_m1.py')
    if arm=='dsm': return load_entry(ROOT/'agents/mgt_dsm_a.py')
    if arm=='normalized': return CoherentPolicy(False)
    if arm=='funded': return CoherentPolicy(True)
    raise ValueError(arm)

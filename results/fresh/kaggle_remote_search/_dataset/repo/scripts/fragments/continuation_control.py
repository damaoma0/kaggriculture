"""Verified continuation ownership and state-based recovery after activation."""
from collections import Counter
from copy import deepcopy
from types import SimpleNamespace
import time
import fragments.continuation_executor as executor
import fragments.continuation_projection as projection
from fragments.continuation_calendar import adapt_calendar


def physical_mismatch(expected, obs):
    farm = obs['farms'][obs['player']]
    ef = expected['farms'][expected['player']]
    if farm['farmer'] != ef['farmer'] or farm['hands'] != ef['hands']: return 'worker_positions'
    if obs['private']['inventories'] != expected['private']['inventories']: return 'worker_inventory'
    for y, row in enumerate(ef['tiles']):
        for x, tile in enumerate(row):
            actual = farm['tiles'][y][x]
            if tile == actual: continue
            if tile is None and isinstance(actual, dict) and actual.get('kind') == 'WEED': continue
            return 'tile_state'
    # Quoted sales may change with a rival's order; purchased inputs must fill.
    for key in ('seeds', 'shed'):
        for p, n in expected['private'][key].items():
            if obs['private'][key].get(p, 0) < n: return 'input_shortfall'
    return None


def _observation_node(obs, donor, maintenance=False):
    node = adapt_calendar(obs, donor, maintenance=maintenance)
    # Recovery never tries to create workers after the hiring window.
    node['hire_to'] = max(1, len(obs['farms'][obs['player']]['hands']) + 1) if obs['hour'] > 1 else 12
    return node


def emergency_action(obs):
    """Best-effort existing-asset care from live positions; no tape fallback."""
    E = projection._CP_ENGINE
    farm, private = obs['farms'][obs['player']], obs['private']
    day, hour = obs['day'], obs['hour']
    tasks, feed_need = [], 0
    for y, row in enumerate(farm['tiles']):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict): continue
            pos = x, y
            if tile.get('kind') == 'PLANT':
                if not tile.get('watered_today') and day < 29 and (tile.get('consecutive_unwatered', 0) or tile.get('planted_day') == day):
                    tasks.append((0, pos, ['WATER']))
                p = tile['crop']
                if tile.get('yield_units', 0) and day - tile['planted_day'] >= E.CROPS[p]['first_yield_day']:
                    tasks.append((2, pos, ['HARVEST']))
            if tile.get('animal'):
                animal = E.ANIMALS[tile['animal']]
                future = any(d - tile['placed_day'] >= animal['first_yield_day'] and
                             (d - tile['placed_day'] - animal['first_yield_day']) % animal['interval'] == 0
                             for d in range(day + 1, 30))
                if future and not tile.get('fed_today'):
                    feed_need += 1; tasks.append((0, pos, ['FEED']))
                if tile.get('yield_units', 0): tasks.append((1, pos, ['HARVEST']))
                if future and not tile.get('cared_today'): tasks.append((3, pos, ['CARE']))
                if tile.get('fertilizer_available'): tasks.append((4, pos, ['COLLECT_FERTILIZER']))
    positions = [farm['farmer']] + farm['hands']
    commands, taken = [], set()
    for u, rawpos in enumerate(positions):
        pos = tuple(rawpos); inv = private['inventories'][u]
        shed = executor._nearest_shed(pos, len(farm['tiles']))
        distance_home = executor._distance(pos, shed)
        cargo = sum(n for p, n in inv.items() if p != 'WHEAT')
        if cargo and (cargo >= 6 or 23 - hour <= distance_home + 1):
            commands.append(executor._walk(pos, shed)[0] if pos != shed else ['DROP']); continue
        options = []
        for i, (priority, target, cmd) in enumerate(tasks):
            if target in taken: continue
            needs_pickup = cmd[0] == 'FEED' and not inv.get('WHEAT', 0)
            distance = executor._distance(pos, target)
            if needs_pickup: distance = distance_home + 1 + executor._distance(shed, target)
            options.append((priority * 4 + distance, i, needs_pickup))
        if not options:
            commands.append(executor._walk(pos, shed)[0] if cargo and pos != shed else ['DROP'] if cargo else ['PASS']); continue
        _, index, pickup = min(options)
        _, target, cmd = tasks[index]; taken.add(target)
        if pickup:
            commands.append(executor._walk(pos, shed)[0] if pos != shed else ['PICKUP', 'WHEAT', 1])
        else: commands.append(executor._walk(pos, target)[0] if pos != target else cmd)
    orders = []
    if hour <= 1:
        budget = farm['money']
        for n in range(len(farm['hands']), 10):
            cost = E._hire_cost(n)
            if budget < cost + 100: break
            orders.append(['HIRE']); budget -= cost
    feed_stock = private['shed'].get('WHEAT', 0) + sum(i.get('WHEAT', 0) for i in private['inventories'])
    if feed_need > feed_stock and len(orders) < 10: orders.append(['BUY_PRODUCT', 'WHEAT', feed_need - feed_stock])
    state = {'start_day': day, 'issued': set(), 'jobs': [
        {'id': i, 'day': 0, 'cmd': ['FEED']} for i in range(feed_need)]}
    return projection.sale_action(obs, state, {'farmer': commands[0], 'hands': commands[1:], 'market': orders})


class ContinuationController:
    def __init__(self):
        self.active = False
        self.expected = None
        self.actions = {}
        self.report = {'activations': 0, 'recoveries': [], 'rejections': [], 'emergency_steps': 0,
                       'maintenance_days': 0, 'maintenance_rejections': [], 'decisions': []}

    def maintenance(self, obs, span=3):
        old = executor.set_deadline(None)
        executor.set_deadline(min(old, time.perf_counter() + .45) if old is not None else time.perf_counter() + .45)
        try:
            return self._maintenance(obs, span)
        except executor.PlanningBudgetExceeded:
            return {'ok': False, 'failure': {'reason': 'planning_budget'}}
        finally:
            executor.set_deadline(old)

    def _maintenance(self, obs, span):
        if span > 1:
            outer = executor.set_deadline(None)
            executor.set_deadline(min(outer, time.perf_counter() + .2) if outer is not None else time.perf_counter() + .2)
            try:
                for cap in (8, 4):
                    node = adapt_calendar(obs, None, maintenance=True, sustain_cap=cap)
                    node['span'] = span; node['hire_to'] = 12
                    result = projection.check_window(obs, node, executor)
                    if result['ok']: return result
            except executor.PlanningBudgetExceeded:
                pass  # Keep part of the outer budget for essential upkeep.
            finally:
                executor.set_deadline(outer)
        node = adapt_calendar(obs, None, maintenance=True)
        node['span'] = 1
        node['jobs'] = [j for j in node['jobs'] if j['day'] == 0]
        for workers in (11, 12, 13):
            node['hire_to'] = workers
            result = projection.check_window(obs, node, executor)
            if result['ok']: return result
        return result

    def propose(self, obs, donor):
        old = executor.set_deadline(time.perf_counter() + .45)
        try:
            return self._propose(obs, donor)
        except executor.PlanningBudgetExceeded:
            self.report['rejections'].append({'step': obs['step'], 'donor': donor['id'], 'failure': {'reason': 'planning_budget'}})
            return False
        finally:
            executor.set_deadline(old)

    def _propose(self, obs, donor):
        node = _observation_node(obs, donor)
        result = projection.check_window(obs, node, executor)
        if not result['ok']:
            self.report['rejections'].append({'step': obs['step'], 'donor': donor['id'], 'failure': result['failure']})
            return False
        # An accepted prefix must leave at least an executable next-day upkeep
        # policy. Later donor selection may abstain without reviving an old tape.
        if result['end_observation']['step'] < 719:
            continuation = self.maintenance(result['end_observation'], span=1)
            if not continuation['ok']:
                self.report['rejections'].append({'step': obs['step'], 'donor': donor['id'],
                    'failure': {'reason': 'terminal_upkeep_infeasible', 'detail': continuation['failure']}})
                return False
        self.actions = {obs['step'] + i: a for i, a in enumerate(result['actions'])}
        self.active = True; self.expected = None
        self.report['activations'] += 1
        self.report['decisions'].append({'day': obs['day'], 'donor': donor['id'], 'output': result['output'],
                                         'calendar_slack': node['calendar_slack']})
        return True

    def action(self, obs):
        if self.expected is not None:
            mismatch = physical_mismatch(self.expected, obs)
            if mismatch:
                self.report['recoveries'].append({'step': obs['step'], 'reason': mismatch})
                self.actions = {}
        action = self.actions.pop(obs['step'], None)
        if action is None:
            if obs['hour'] == 0:
                result = self.maintenance(obs)
                if result['ok']:
                    self.report['maintenance_days'] += (len(result['actions']) + 23) // 24
                    self.actions = {obs['step'] + i: a for i, a in enumerate(result['actions'])}
                    action = self.actions.pop(obs['step'])
                else:
                    self.report['maintenance_rejections'].append({'day': obs['day'], 'failure': result['failure']})
            if action is None:
                self.report['emergency_steps'] += 1
                action = emergency_action(obs)
        else:
            # Refuse a crop batch if a price change prevented its seed purchase.
            commands = [action.get('farmer', ['PASS'])] + action.get('hands', [])
            required = Counter(c[1] for c in commands if c and c[0] == 'PLANT')
            bad = any(n > obs['private']['seeds'].get(p, 0) for p, n in required.items())
            _, after, changes, _, overflow = projection.physical_step(obs, action)
            for u, cmd in enumerate(commands):
                if cmd[0] in ('PLANT', 'BUILD_COOP', 'BUILD_PASTURE', 'PLACE', 'HARVEST', 'FEED', 'FERTILIZE'):
                    bad |= u >= len(changes) or not changes[u]
                if cmd[0] == 'PICKUP':
                    bad |= after['inventories'][u].get(cmd[1], 0) - obs['private']['inventories'][u].get(cmd[1], 0) < cmd[2]
            if bad or overflow:
                self.report['recoveries'].append({'step': obs['step'], 'reason': 'action_precondition'})
                self.actions = {}; action = emergency_action(obs)
        self.expected, _ = projection.project_step(obs, action)
        return action

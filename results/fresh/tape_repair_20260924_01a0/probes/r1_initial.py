"""Research: costed three-day repairs of V9's rejected tape transitions.

The live policy consumes only observation and native memory. Repaired targets
come from our own first-scenario simulation, never the evaluated future.
Original V9 finalists retain their full evaluation budget. At most two failed
transitions get repairs, and one repaired finalist gets eight-scenario testing.
"""
from collections import Counter
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import statistics
import time

import value_tape_search_v9 as B

V, F, assess = B.V, B.F, B.B.assess
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


def unpack(route):
    if isinstance(route, (tuple, list)):
        return route[0], tuple(tuple(a) for a in route[1])
    return route, ()


class TransitionRepair:
    """Small service adapter reusing the native funded, hidden-worker executor."""

    def __init__(self, entry):
        self.ns = entry.__globals__
        self.original = {k: self.ns[k] for k in
                         ('agent', '_shp_topups', '_shp_work', '_shp_apply_cull')}
        self.targets = {}
        self.until = -1
        self.stats = Counter()
        self.ns['agent'] = self.act
        self.ns['_shp_topups'] = self.topups
        self.ns['_shp_work'] = self.work
        self.ns['_shp_apply_cull'] = self.cull

    def activate(self, assets=(), until=-1):
        self.targets = {(a[0], a[1]): tuple(a) for a in assets}
        self.until = until if until is not None else -1
        self.stats.clear()

    def matching(self, obs):
        if int(obs['step']) >= self.until:
            return {}
        farm = obs['farms'][int(obs['player'])]
        found = {}
        for pos, asset in self.targets.items():
            x, y = pos
            tile = farm['tiles'][y][x]
            if not isinstance(tile, dict):
                continue
            species = tile.get('animal') or tile.get('crop')
            birth = tile.get('placed_day') if tile.get('animal') else tile.get('planted_day')
            if (species, birth) == asset[2:]:
                found[pos] = tile
        return found

    def topups(self, state, obs, tape, day):
        rows = self.original['_shp_topups'](state, obs, tape, day)
        targets = self.matching(obs)
        if not targets:
            return rows
        additions = {}
        for pos, tile in targets.items():
            if pos in state.get('tiles', ()):
                continue  # The native flock already has mandatory servicing.
            ops = set()
            if tile.get('animal'):
                if not tile.get('fed_today') and tile.get('consecutive_unfed', 0) >= 1:
                    ops.add('FEED')
                if ops and tile.get('yield_units', 0):
                    ops.add('HARVEST')
            elif not tile.get('watered_today') and tile.get('consecutive_unwatered', 0) >= 1:
                ops.add('WATER')
            if ops:
                additions[pos] = ops
        result = []
        for value, pos, ops in rows:
            if pos in additions:
                ops = set(ops) | additions.pop(pos)
                value += 1_000_000  # Feasibility priority, not an estimated profit.
            result.append((value, pos, ops))
        result.extend((1_000_000, pos, ops) for pos, ops in additions.items())
        self.stats['service_tasks_proposed'] += len(additions)
        return result

    def cull(self, state, obs, action):
        protected = self.matching(obs)
        if protected and state.get('culled'):
            state['culled'] = set(state['culled']) - set(protected)
        return self.original['_shp_apply_cull'](state, obs, action)

    def work(self, state, obs, idx, role, step):
        targets = self.matching(obs)
        crop_jobs = [pos for pos, ops in (role.get('ops') or {}).items()
                     if 'WATER' in ops and pos in targets
                     and targets[pos].get('crop') and not targets[pos].get('watered_today')]
        if crop_jobs:
            farm = obs['farms'][int(obs['player'])]
            pos = tuple(farm['hands'][idx - 1])
            inv = obs['private']['inventories'][idx]
            # Let the native executor load reserved feed before leaving the shed,
            # and finish survival-critical animal work before optional travel.
            feeding = [p for p, ops in (role.get('ops') or {}).items() if 'FEED' in ops
                       and isinstance(farm['tiles'][p[1]][p[0]], dict)
                       and not farm['tiles'][p[1]][p[0]].get('fed_today')]
            if not feeding:
                target = min(crop_jobs, key=lambda p: (self.ns['_shp_dist'](pos, p), p))
                if pos == target:
                    self.stats['water_attempts'] += 1
                    return ['WATER']
                return self.ns['_shp_walk'](pos, target)
        return self.original['_shp_work'](state, obs, idx, role, step)

    def act(self, obs, configuration=None):
        action = self.original['agent'](obs, configuration)
        targets = self.matching(obs)
        if not targets:
            return action
        farm = obs['farms'][int(obs['player'])]
        positions = [farm['farmer'], *farm['hands']]
        commands = [list(action.get('farmer') or ['PASS']),
                    *[list(c or ['PASS']) for c in action.get('hands', [])]]
        changed = False
        for i, (pos, cmd) in enumerate(zip(positions, commands)):
            tile = targets.get(tuple(pos))
            if tile is None or cmd[0] not in ('DIG', 'PASS'):
                continue
            replacement = ['PASS']
            if tile.get('crop') and not tile.get('watered_today'):
                replacement = ['WATER']
            elif tile.get('animal') and not tile.get('fed_today'):
                if obs['private']['inventories'][i].get('WHEAT', 0):
                    replacement = ['FEED']
            if cmd[0] == 'DIG' or replacement != ['PASS']:
                commands[i] = replacement
                self.stats['suppressed_digs' if cmd[0] == 'DIG' else 'idle_service'] += 1
                changed = True
        return dict(action, farmer=commands[0], hands=commands[1:]) if changed else action


def install(entry):
    ns = entry.__globals__
    if '_TRANSITION_REPAIR_R1' not in ns:
        ns['_TRANSITION_REPAIR_R1'] = TransitionRepair(entry)
    return ns['_TRANSITION_REPAIR_R1']


def commit(entry, selection, until, native_router):
    route, targets = unpack(selection)
    install(entry).activate(targets, until)
    chassis = entry.__globals__['_MGT_IMPL'].chassis
    chassis.router = native_router
    if route is not None:
        def committed(obs, step, memory):
            if step < until:
                memory['route'] = route
                return route
            return native_router(obs, step, memory)
        chassis.router = committed


class Runtime(B.Runtime):
    def __init__(self):
        super().__init__()
        self.repair = install(self.entry)

    def reset(self, memory=None, route=None, until=None):
        plain, targets = unpack(route)
        entry = super().reset(memory, plain, until)
        self.repair.activate(targets, until)
        return entry

    def rollout(self, obs, memory, route, world, until=None, protected=None):
        result = super().rollout(obs, memory, route, world, until, protected)
        if unpack(route)[1]:
            result['repair_stats'] = dict(self.repair.stats)
        return result


@lru_cache(maxsize=1)
def runtime():
    return Runtime()


def choose(obs, memory, *, count=7, keep=2, max_repairs=2, budget_seconds=None):
    started = time.perf_counter()
    deadline = None if budget_seconds is None else started + max(0, budget_seconds)
    runner = runtime()
    assert not runner.busy
    runner.busy = True
    runner.rollout_impl.__globals__['_deadline'] = deadline
    predictions, rejected, shortlisted, repair_shortlisted = {}, {}, [], []
    candidates, worlds, timed_out = [], [], False
    existing = V.asset_keys(obs['farms'][int(obs['player'])])
    until = min(719, (int(obs['day']) + 3) * 24)

    def extend(route, indices):
        pred = predictions.setdefault(route, [])
        for index in indices:
            if deadline is not None and time.perf_counter() >= deadline:
                raise B.B.SearchDeadline()
            protected = None if route is None else existing & set(map(tuple, predictions[None][index]['survives']))
            p = runner.rollout(obs, memory, route, worlds[index], until, protected)
            if p.get('early_rejection'):
                rejected[route] = dict(scenario=index, assets=p['missing'], boundary_step=p['boundary_step'])
                return
            assert len(pred) == index
            pred.append(p)

    def score(rows):
        return sorted((assess(c, predictions[c['route']], predictions[None], existing)
                       for c in rows if c['route'] not in rejected and predictions.get(c['route'])),
                      key=lambda r: r['risk_score'], reverse=True)

    try:
        runner.prepare(obs)
        candidates = runner.shortlist(obs, memory, count)
        originals = candidates[1:]
        try:
            worlds = [runner.world_batch.world(obs, i) for i in range(8)]
            extend(None, [0])
            for c in originals:
                extend(c['route'], [0])
            shortlist = [r for r in score(originals) if not r['protection_failures']][:keep]
            shortlisted = [r['route'] for r in shortlist]
            repairs = []
            eligible = sorted((c for c in originals if c['route'] in rejected
                               and len(rejected[c['route']]['assets']) <= 6),
                              key=lambda c: (len(rejected[c['route']]['assets']), c['distance'], c['hamming']))
            for c in eligible[:max_repairs]:
                targets = tuple(tuple(a) for a in rejected[c['route']]['assets'])
                key = (c['route'], targets)
                repaired = dict(c, route=key, base_route=c['route'], repair_assets=targets,
                                name='repair_then_commit_until_next_reveal')
                repairs.append(repaired)
                candidates.append(repaired)
                extend(key, [0])
            repair_screen = [r for r in score(repairs) if not r['protection_failures']][:2]
            repair_shortlisted = [r['route'] for r in repair_screen]
            if shortlisted or repair_shortlisted:
                extend(None, range(1, 4))
                for route in shortlisted + repair_shortlisted:
                    extend(route, range(1, 4))
                native_final = [r for r in score([c for c in originals if c['route'] in shortlisted])
                                if not r['protection_failures'] and r['risk_score'] > 0][:2]
                repair_final = [r for r in score([c for c in repairs if c['route'] in repair_shortlisted])
                                if not r['protection_failures'] and r['risk_score'] > 0][:1]
                if native_final or repair_final:
                    extend(None, range(4, 8))
                    for c in native_final + repair_final:
                        extend(c['route'], range(4, 8))
        except B.B.SearchDeadline:
            timed_out = True
        rows = []
        for c in candidates:
            route = c['route']
            pred = predictions.get(route, [])
            row = (assess(c, pred, predictions[None][:len(pred)], existing) if pred else
                   dict(c, predictions=[], protection_failures=[]))
            if route in rejected:
                row['protection_failures'].append(rejected[route])
                row['early_rejection'] = 'protected_cohort_missing_at_commitment_boundary'
            row['fully_evaluated'] = len(pred) == 8 and route not in rejected
            row['admitted'] = bool(row.get('admitted') and row['fully_evaluated'])
            row['strict_admitted'] = bool(row.get('strict_admitted') and row['fully_evaluated'])
            rows.append(row)
        allowed = [r for r in rows if r['admitted']]
        selected = max(allowed, key=lambda r: r['risk_score']) if allowed else rows[0]
        return selected['route'], dict(
            day=int(obs['day']), selected=selected['route'], selected_episode=selected['episode'],
            candidates=rows, until=until, timed_out=timed_out, budget_seconds=budget_seconds,
            shortlisted=shortlisted, repair_shortlisted=repair_shortlisted,
            worlds=[dict(index=w['index'], shops=w['shops'][29], donor=w['donor']) for w in worlds],
            seconds=time.perf_counter() - started, simulated_turns=runner.simulated_turns,
            rollouts=runner.rollouts, pruned_rollouts=runner.pruned_rollouts,
            source_sha256=V.SOURCE_SHA256, planner_sha256=PLANNER_SHA256,
            protocol='V9 original finalists plus at most two repaired transitions; one repaired eight-world finalist. Same protection/economic admission. Three-day repairs from own simulated missing assets.')
    finally:
        runner.rollout_impl.__globals__['_deadline'] = None
        runner.busy = False


if __name__ == '__main__':
    raise SystemExit('Import choose(observation, own_memory); use commit() to execute its selection.')

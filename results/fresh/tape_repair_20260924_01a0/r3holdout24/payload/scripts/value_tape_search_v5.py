"""V4 decisions with reused immutable tapes and cheaper isolated snapshots.

No scenario or candidate is dropped. Frozen V1/V2 functions are instantiated
with explicit local dependencies, so the live agent and official live engine
are never patched. One runtime is used serially per process; parallel searches
must use separate processes. The native agent source remains unchanged.
"""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from types import FunctionType, SimpleNamespace
import time

import rival_trajectory_model_v3 as M
import value_tape_search as V
import value_tape_search_v2 as V2
from value_tape_search_v3 import assess
from test_labour_selfplay import project_input

PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


def observation_copy(value):
    """Copy the JSON observation tree into ordinary dictionaries.

    Agent inputs are JSON values, not engine objects. Avoid reconstructing the
    framework's dict subclasses at every node; still give the agent an entirely
    separate input. Tuples are preserved for locally constructed test inputs.
    """
    if isinstance(value, dict):
        return {k: observation_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [observation_copy(v) for v in value]
    if isinstance(value, tuple):
        return tuple(observation_copy(v) for v in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f'Non-JSON observation value: {type(value)}')


def semantic_memory(memory):
    """Omit derived process-local tape caches from the portable input digest.

    Do not omit any production plan, cash, inventory, or pending job. The cal
    table is a pure tape/day function; inplace.tape is written but never read
    in this source version. Its clock, queue, and plan are all retained.
    """
    result = deepcopy(memory)
    for player in (0, 1):
        state = result['_SHP_STATES'].get(player)
        if state is None:
            continue
        state.pop('cal', None)
        if state.get('inplace') is not None:
            state['inplace'].pop('tape', None)
    return result


class Runtime:
    def __init__(self):
        self.entry = V.fresh_agent()
        self.ns = self.entry.__globals__
        self.chassis = self.ns['_MGT_IMPL'].chassis
        self.router = self.chassis.router
        self.busy = False
        self.rollouts = 0
        self.reset_seconds = 0.0
        # Local injection, rather than mutation of imported module globals.
        dependencies = dict(V2.rollout.__globals__)
        dependencies.update(V=SimpleNamespace(fresh_agent=self.reset,
            isolated_engine=V.isolated_engine, asset_keys=V.asset_keys),
            project_input=self.project, deepcopy=observation_copy)
        self.rollout_impl = FunctionType(V2.rollout.__code__, dependencies,
            'reused_official_rollout', V2.rollout.__defaults__)
        dependencies = dict(V.shortlist.__globals__)
        dependencies.update(fresh_agent=self.reset, deepcopy=observation_copy)
        self.shortlist = FunctionType(V.shortlist.__code__, dependencies,
            'reused_shortlist', V.shortlist.__defaults__)

    def reset(self, memory=None, route=None, until=None):
        started = time.perf_counter()
        self.chassis.players = deepcopy(memory['players']) if memory else {}
        self.chassis.diagnostics = {'layer_fallbacks': 0, 'entry_fallbacks': 0}
        # _future_sells is pure immutable tape data and can remain cached.
        for key in V.MEMORY_KEYS:
            value = self.ns[key]
            value.clear()
            incoming = deepcopy(memory[key]) if memory else ({} if isinstance(value, dict) else [])
            if isinstance(value, list):
                value.extend(incoming)
            else:
                value.update(incoming)
        self.ns['_SHP_NUM'].clear()
        # Foreign integer object IDs are not portable cache identities.
        for player in (0, 1):
            state = self.ns['_SHP_STATES'].get(player)
            if state is not None:
                state.pop('cal', None)
        self.chassis.router = self.router
        if route is not None:
            parent = self.router
            def committed(obs, step, state):
                if step < until:
                    state['route'] = route
                    return route
                return parent(obs, step, state)
            self.chassis.router = committed
        self.reset_seconds += time.perf_counter() - started
        return self.entry

    def prepare(self, obs):
        self.observation = obs
        public, state = project_input(obs)
        self.environment = public.env
        self.initial = state
        self.rollouts = 0
        self.reset_seconds = 0.0

    def project(self, obs):
        assert obs is self.observation, 'A new observation requires prepare()'
        # A single deepcopy preserves the official shared farm/market aliases.
        return SimpleNamespace(env=deepcopy(self.environment)), deepcopy(self.initial)

    def rollout(self, obs, memory, route, world, until=None):
        self.rollouts += 1
        return self.rollout_impl(obs, memory, route, world, until)


@lru_cache(maxsize=1)
def runtime():
    return Runtime()


def choose(obs, memory, *, count=7):
    started = time.perf_counter()
    runner = runtime()
    assert not runner.busy, 'Use one search at a time per process'
    runner.busy = True
    try:
        runner.prepare(obs)
        candidates = runner.shortlist(obs, memory, count)
        setup_seconds = time.perf_counter() - started
        existing = V.asset_keys(obs['farms'][int(obs['player'])])
        world_start = time.perf_counter()
        worlds = [M.world(obs, i) for i in range(8)]
        world_seconds = time.perf_counter() - world_start
        predictions = {c['route']: [runner.rollout(obs, memory, c['route'], w)
            for w in worlds[:4]] for c in candidates}
        base = predictions[None][:4]
        screen = [assess(c, predictions[c['route']], base, existing) for c in candidates]
        finalists = sorted((r for r in screen if r['route'] is not None
            and not r['protection_failures'] and r['risk_score'] > 0),
            key=lambda r: r['risk_score'], reverse=True)[:2]
        active = {None, *[r['route'] for r in finalists]}
        if finalists:
            for route in active:
                predictions[route].extend(runner.rollout(obs, memory, route, w) for w in worlds[4:])
        rows = []
        for c in candidates:
            pred = predictions[c['route']]
            row = assess(c, pred, predictions[None][:len(pred)], existing)
            row['fully_evaluated'] = len(pred) == 8
            row['admitted'] = row['admitted'] and row['fully_evaluated']
            row['strict_admitted'] = row['strict_admitted'] and row['fully_evaluated']
            rows.append(row)
        allowed = [r for r in rows if r['admitted']]
        strict = [r for r in rows if r['strict_admitted']]
        chosen = max(allowed, key=lambda r: r['risk_score']) if allowed else rows[0]
        strict_chosen = max(strict, key=lambda r: r['risk_score']) if strict else rows[0]
        digest = sha256(json.dumps(V.canonical([obs, semantic_memory(memory)]),
            sort_keys=True, default=str).encode()).hexdigest()
        decision = dict(day=int(obs['day']), selected=chosen['route'], selected_episode=chosen['episode'],
            strict_selected=strict_chosen['route'], candidates=rows,
            worlds=[dict(index=w['index'], shops=w['shops'][29], donor=w['donor']) for w in worlds],
            seconds=time.perf_counter()-started, until=min(719, (int(obs['day'])+3)*24),
            source_sha256=V.SOURCE_SHA256, planner_sha256=PLANNER_SHA256, model_sha256=M.MODEL_SHA256,
            input_sha256=digest, input_digest_version='semantic_memory_v1',
            timings=dict(setup=setup_seconds, worlds=world_seconds, agent_resets=runner.reset_seconds),
            rollouts=runner.rollouts,
            protocol='V4 candidate, scenario, physics and admission rules; reusable private agent, immutable tape caches, copied JSON observation trees. No approximate rollout or pruned world.')
        return chosen['route'], decision
    finally:
        runner.busy = False

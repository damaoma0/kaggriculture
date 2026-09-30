"""V6 with exact early rejection by the existing cohort-protection rule.

A missing protected cohort at the commitment boundary makes admission
impossible under V4's rule. Stop that rollout and its remaining worlds. Do not
use partial profit, partial hire counts, or approximate value as a rejection.
"""
import ast
from functools import lru_cache
from hashlib import sha256
import inspect
import json
from pathlib import Path
import time

import value_tape_search_v6 as B

F = B.F
V, M, assess = F.V, F.M, F.assess
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


class Runtime(B.Runtime):
    def __init__(self):
        super().__init__()
        tree = ast.parse(inspect.getsource(F.V2.rollout))
        borrowed = guarded = 0
        guard = ast.parse('''
if _required_assets:
    missing = _required_assets - surviving
    if missing:
        return dict(early_rejection=True, survives=sorted(surviving),
                    missing=sorted(missing), boundary_step=t+1)
''').body[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'entry':
                arg = node.args[0]
                assert isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == 'deepcopy'
                node.args[0] = arg.args[0]
                borrowed += 1
            if isinstance(node, ast.If) and any(isinstance(s, ast.Assign) and
                    any(isinstance(t, ast.Name) and t.id == 'surviving' for t in s.targets) for s in node.body):
                node.body.append(guard)
                guarded += 1
        assert borrowed == guarded == 1
        namespace = dict(self.rollout_impl.__globals__, _required_assets=set())
        exec(compile(ast.fix_missing_locations(tree), '<cohort_guarded_rollout>', 'exec'), namespace)
        self.rollout_impl = namespace['rollout']

    def prepare(self, obs):
        super().prepare(obs)
        self.pruned_rollouts = 0
        self.simulated_turns = 0

    def rollout(self, obs, memory, route, world, until=None, protected=None):
        self.rollout_impl.__globals__['_required_assets'] = protected or set()
        try:
            result = super().rollout(obs, memory, route, world, until)
        finally:
            self.rollout_impl.__globals__['_required_assets'] = set()
        self.pruned_rollouts += bool(result.get('early_rejection'))
        self.simulated_turns += result.get('boundary_step', 719) - int(obs['step'])
        return result


@lru_cache(maxsize=1)
def runtime():
    return Runtime()


def choose(obs, memory, *, count=7):
    started = time.perf_counter()
    runner = runtime()
    assert not runner.busy
    runner.busy = True
    try:
        runner.prepare(obs)
        candidates = runner.shortlist(obs, memory, count)
        existing = V.asset_keys(obs['farms'][int(obs['player'])])
        worlds = [M.world(obs, i) for i in range(8)]
        predictions = {None: [runner.rollout(obs, memory, None, w) for w in worlds[:4]]}
        rejected = {}

        def extend(route, indices):
            pred = predictions.setdefault(route, [])
            for i in indices:
                protected = existing & set(map(tuple, predictions[None][i]['survives']))
                result = runner.rollout(obs, memory, route, worlds[i], protected=protected)
                if result.get('early_rejection'):
                    rejected[route] = dict(scenario=i, assets=result['missing'],
                        boundary_step=result['boundary_step'])
                    return
                pred.append(result)

        for c in candidates:
            if c['route'] is not None:
                extend(c['route'], range(4))
        base = predictions[None][:4]
        screen = [assess(c, predictions[c['route']], base, existing)
            for c in candidates if c['route'] not in rejected]
        finalists = sorted((r for r in screen if r['route'] is not None
            and not r['protection_failures'] and r['risk_score'] > 0),
            key=lambda r:r['risk_score'], reverse=True)[:2]
        if finalists:
            predictions[None].extend(runner.rollout(obs, memory, None, w) for w in worlds[4:])
            for row in finalists:
                extend(row['route'], range(4, 8))
        rows = []
        for c in candidates:
            route = c['route']
            pred = predictions[route]
            if route in rejected:
                row = dict(c, predictions=pred, fully_evaluated=False, admitted=False,
                    strict_admitted=False, protection_failures=[rejected[route]],
                    early_rejection='protected_cohort_missing_at_commitment_boundary')
            else:
                row = assess(c, pred, predictions[None][:len(pred)], existing)
                row['fully_evaluated'] = len(pred) == 8
                row['admitted'] = row['admitted'] and row['fully_evaluated']
                row['strict_admitted'] = row['strict_admitted'] and row['fully_evaluated']
            rows.append(row)
        admitted = [r for r in rows if r['admitted']]
        strict = [r for r in rows if r['strict_admitted']]
        chosen = max(admitted, key=lambda r:r['risk_score']) if admitted else rows[0]
        strict_chosen = max(strict, key=lambda r:r['risk_score']) if strict else rows[0]
        digest = sha256(json.dumps(V.canonical([obs, F.semantic_memory(memory)]),
            sort_keys=True, default=str).encode()).hexdigest()
        decision = dict(day=int(obs['day']), selected=chosen['route'], selected_episode=chosen['episode'],
            strict_selected=strict_chosen['route'], candidates=rows,
            worlds=[dict(index=w['index'], shops=w['shops'][29], donor=w['donor']) for w in worlds],
            seconds=time.perf_counter()-started, until=min(719, (int(obs['day'])+3)*24),
            source_sha256=V.SOURCE_SHA256, planner_sha256=PLANNER_SHA256, model_sha256=M.MODEL_SHA256,
            input_sha256=digest, input_digest_version='semantic_memory_v1', rollouts=runner.rollouts,
            pruned_rollouts=runner.pruned_rollouts, simulated_turns=runner.simulated_turns,
            protocol='V4 selection and risk rules; V6 exact physics and borrowed observation. Stop a candidate only when a protected cohort is absent at the commitment boundary in any required world. Rejected candidate profits are not estimated.')
        return chosen['route'], decision
    finally:
        runner.busy = False

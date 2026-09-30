"""One exact scout world per candidate, then expand at most two candidates.

Scouting is approximate search: an excluded route might win in other worlds.
Admission is unchanged and always requires eight complete paired forecasts.
Optional deadlines abort rollouts, restore engine hooks, and admit only fully
checked candidates. Unfinished forecasts never acquire estimated profits.
"""
import ast
from functools import lru_cache
from hashlib import sha256
import inspect
import json
from pathlib import Path
import time

import value_tape_search_v7 as B

V, F, M, assess = B.V, B.F, B.M, B.assess
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


class SearchDeadline(Exception):
    pass


class Runtime(B.Runtime):
    def __init__(self):
        super().__init__()
        tree = ast.parse(inspect.getsource(F.V2.rollout))
        guard = ast.parse('''
if _required_assets:
    missing = _required_assets - surviving
    if missing:
        return dict(early_rejection=True, survives=sorted(surviving),
                    missing=sorted(missing), boundary_step=t+1)
''').body[0]
        deadline = ast.parse('''
if _deadline is not None and (t-start) % 8 == 0 and _clock() >= _deadline:
    raise _SearchDeadline()
''').body[0]
        borrowed = guarded = timed = 0
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
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == 't':
                node.body.insert(0, deadline)
                timed += 1
        assert borrowed == guarded == timed == 1
        namespace = dict(self.rollout_impl.__globals__, _required_assets=set(),
            _deadline=None, _clock=time.perf_counter, _SearchDeadline=SearchDeadline)
        exec(compile(ast.fix_missing_locations(tree), '<scouting_rollout>', 'exec'), namespace)
        self.rollout_impl = namespace['rollout']


@lru_cache(maxsize=1)
def runtime():
    return Runtime()


def choose(obs, memory, *, count=7, keep=2, budget_seconds=None):
    started = time.perf_counter()
    deadline = None if budget_seconds is None else started+max(0, budget_seconds)
    runner = runtime()
    assert not runner.busy
    runner.busy = True
    runner.rollout_impl.__globals__['_deadline'] = deadline
    worlds, predictions, rejected, shortlisted = [], {}, {}, []
    candidates, scout_order, timed_out = [], [], False
    rank_seconds = 0.0

    def check_time():
        if deadline is not None and time.perf_counter() >= deadline:
            raise SearchDeadline()

    def extend(route, indices):
        pred = predictions.setdefault(route, [])
        for i in indices:
            check_time()
            protected = None if route is None else existing & set(map(tuple, predictions[None][i]['survives']))
            result = runner.rollout(obs, memory, route, worlds[i], protected=protected)
            if result.get('early_rejection'):
                rejected[route] = dict(scenario=i, assets=result['missing'], boundary_step=result['boundary_step'])
                return
            assert i == len(pred)
            pred.append(result)

    try:
        runner.prepare(obs)
        candidates = runner.shortlist(obs, memory, count)
        existing = V.asset_keys(obs['farms'][int(obs['player'])])
        try:
            for i in range(8):
                check_time()
                worlds.append(M.world(obs, i))
            extend(None, [0])
            for c in candidates[1:]:
                extend(c['route'], [0])
            start_rank = time.perf_counter()
            scout = [assess(c, predictions[c['route']], predictions[None], existing)
                for c in candidates[1:] if c['route'] not in rejected]
            # A full-season failed hire in world0 is already an exact veto.
            scout_order = sorted((r for r in scout if not r['protection_failures']),
                key=lambda r: r['risk_score'], reverse=True)
            shortlisted = [r['route'] for r in scout_order[:keep]]
            rank_seconds = time.perf_counter()-start_rank
            if shortlisted:
                extend(None, range(1, 4))
                for route in shortlisted:
                    extend(route, range(1, 4))
                screened = [assess(c, predictions[c['route']], predictions[None], existing)
                    for c in candidates[1:] if c['route'] in shortlisted and c['route'] not in rejected]
                finalists = sorted((r for r in screened if not r['protection_failures'] and r['risk_score'] > 0),
                    key=lambda r: r['risk_score'], reverse=True)[:2]
                if finalists:
                    extend(None, range(4, 8))
                    for c in finalists:
                        extend(c['route'], range(4, 8))
        except SearchDeadline:
            timed_out = True
        rows = []
        for c in candidates:
            route = c['route']
            pred = predictions.get(route, [])
            if pred:
                row = assess(c, pred, predictions[None][:len(pred)], existing)
            else:
                row = dict(c, predictions=[], protection_failures=[])
            if route in rejected:
                row['protection_failures'].append(rejected[route])
                row['early_rejection'] = 'protected_cohort_missing_at_commitment_boundary'
            row['fully_evaluated'] = len(pred) == 8 and route not in rejected
            row['admitted'] = bool(row.get('admitted') and row['fully_evaluated'])
            row['strict_admitted'] = bool(row.get('strict_admitted') and row['fully_evaluated'])
            row['scouted'] = bool(pred)
            row['expanded'] = route in shortlisted
            rows.append(row)
        allowed = [r for r in rows if r['admitted']]
        strict = [r for r in rows if r['strict_admitted']]
        chosen = max(allowed, key=lambda r:r['risk_score']) if allowed else rows[0]
        strict_chosen = max(strict, key=lambda r:r['risk_score']) if strict else rows[0]
        decision = dict(day=int(obs['day']), selected=chosen['route'], selected_episode=chosen['episode'],
            strict_selected=strict_chosen['route'], candidates=rows, until=min(719, (int(obs['day'])+3)*24),
            worlds=[dict(index=w['index'], shops=w['shops'][29], donor=w['donor']) for w in worlds],
            seconds=time.perf_counter()-started, source_sha256=V.SOURCE_SHA256,
            planner_sha256=PLANNER_SHA256, model_sha256=M.MODEL_SHA256,
            scout_order=[dict(route=r['route'], score=r['risk_score']) for r in scout_order],
            shortlisted=shortlisted, keep=keep, timed_out=timed_out, budget_seconds=budget_seconds,
            rank_seconds=rank_seconds, rollouts=runner.rollouts, pruned_rollouts=runner.pruned_rollouts,
            simulated_turns=runner.simulated_turns,
            input_sha256=sha256(json.dumps(V.canonical([obs, F.semantic_memory(memory)]),
                sort_keys=True, default=str).encode()).hexdigest(), input_digest_version='semantic_memory_v1',
            protocol='One exact full-season scout per candidate in scenario0; expand top2 even if scout profit is negative; four-world margin screen and unchanged eight-world cash/risk/cohort admission. Approximate candidate search. Commit three days, then native routing. Optional deadline admits only complete eight-world candidates.')
        return chosen['route'], decision
    finally:
        runner.rollout_impl.__globals__['_deadline'] = None
        runner.busy = False


if __name__ == '__main__':
    raise SystemExit('Research selector: import choose(obs, own_memory).')

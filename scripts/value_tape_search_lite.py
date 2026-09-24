"""V9-lite: the V9 value selector (scripts/value_tape_search_v9.py, unchanged) at a fraction of its search cost.

Same private runtime, same official-engine rollouts, same rival worlds, same cohort guard and the same V3 admission
rule (no protection failure, own expected cash > 0, mean - 0.5 SD > final_min, downside >= -max(500, .25*mean)).
What is cut (all parameters, defaults = the recommended setting):
  * count     : shortlist length incl. the native row (V9: 7). The shortlist order is V9's own, so count=k is a prefix.
  * skip_native_commit : do not roll out a candidate whose route is the router's own choice at this reveal
                (committing to the route the native router just picked differs from native only if the router
                would switch again inside the three days).
  * scout_min : a candidate is expanded only if its exact world-0 (scout) margin gain exceeds this (V9 expands its
                top 2 even when negative).
  * max_hamming : drop shortlisted tapes whose board label distance to ours exceeds this (V9: no limit beyond its
                own 8/14/24 tolerance groups).
  * keep      : at most this many scouted candidates are expanded (V9: 2).
  * lazy_keep : expand the next kept candidate only if the previous one was not admitted (V9 expands both and takes
                the better risk score).
  * worlds    : number of rival/shop worlds a candidate must complete to be admitted (V9: 8; worlds 0..worlds-1,
                the same world objects V9 builds for those indices).
  * final_min : risk-score floor for admission (V9: 350).
  * budget_seconds : cooperative deadline as V8/V9 (only fully evaluated candidates are admitted).
No outcome is estimated for an unfinished candidate; a cut can only make the selector keep the native route more often
or pick among fewer alternatives.
"""
from hashlib import sha256
from pathlib import Path
import time

import value_tape_search_v9 as N

B8 = N.B                      # value_tape_search_v8 (V8 choose/Runtime, SearchDeadline)
V, F, assess = B8.V, B8.F, B8.assess
SearchDeadline = B8.SearchDeadline
runtime = N.runtime
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
DEFAULTS = dict(count=7, keep=2, lazy_keep=True, worlds=4, scout_min=350.0, final_min=350.0, skip_native_commit=True,
                max_hamming=12)


def _admit(row, n_worlds, final_min):
    row['fully_evaluated'] = len(row.get('predictions') or []) == n_worlds and not row.get('early_rejection')
    ok = (row['fully_evaluated'] and not row['protection_failures'] and row['risk_score'] > final_min
          and row['minimum_margin'] >= -max(500, .25*max(0, row['mean_margin']))
          and sum(row['cash_deltas'])/len(row['cash_deltas']) > 0)
    row['admitted'] = bool(ok)
    return row


def choose(obs, memory, *, count=7, keep=2, lazy_keep=True, worlds=4, scout_min=350.0, final_min=350.0,
           skip_native_commit=True, max_hamming=12, budget_seconds=None):
    started = time.perf_counter()
    deadline = None if budget_seconds is None else started + max(0, budget_seconds)
    runner = runtime()
    assert not runner.busy
    runner.busy = True
    runner.rollout_impl.__globals__['_deadline'] = deadline
    W = max(1, int(worlds))
    world_list, predictions, rejected = [], {}, {}
    candidates, scout, shortlisted, skipped = [], [], [], []
    timed_out, native_route = False, None
    stage_seconds = {}

    def check_time():
        if deadline is not None and time.perf_counter() >= deadline:
            raise SearchDeadline()

    def extend(route, indices):
        pred = predictions.setdefault(route, [])
        for i in indices:
            if route in rejected:
                return
            check_time()
            protected = None if route is None else existing & set(map(tuple, predictions[None][i]['survives']))
            result = runner.rollout(obs, memory, route, world_list[i], protected=protected)
            if result.get('early_rejection'):
                rejected[route] = dict(scenario=i, assets=result['missing'], boundary_step=result['boundary_step'])
                return
            assert i == len(pred)
            pred.append(result)

    try:
        t0 = time.perf_counter()
        runner.prepare(obs)
        candidates = runner.shortlist(obs, memory, count)
        # the shortlist ran the native agent on this observation: its route is the router's choice at this reveal
        native_route = runner.chassis.players[int(obs['player'])]['route']
        existing = V.asset_keys(obs['farms'][int(obs['player'])])
        stage_seconds['shortlist'] = time.perf_counter() - t0
        try:
            alternatives = [c for c in candidates[1:]
                            if not (skip_native_commit and c['route'] == native_route) and c['hamming'] <= max_hamming]
            skipped = [c['route'] for c in candidates[1:] if c not in alternatives]
            # worlds are built lazily (world i depends only on the observation and i): a decision with no
            # alternative builds none, one with no positive scout builds only world 0
            t0 = time.perf_counter()
            if alternatives:
                world_list.append(N.M.world(obs, 0))
            stage_seconds['worlds'] = time.perf_counter() - t0
            t0 = time.perf_counter()
            if alternatives:
                extend(None, [0])
                for c in alternatives:
                    extend(c['route'], [0])
            stage_seconds['scout'] = time.perf_counter() - t0
            scout = [assess(c, predictions[c['route']], predictions[None], existing)
                     for c in alternatives if c['route'] not in rejected and predictions.get(c['route'])]
            order = sorted((r for r in scout if not r['protection_failures'] and r['mean_margin'] > scout_min),
                           key=lambda r: r['risk_score'], reverse=True)
            shortlisted = [r['route'] for r in order[:keep]]
            t0 = time.perf_counter()
            if shortlisted and W > 1:
                for i in range(1, W):
                    check_time()
                    world_list.append(N.M.world(obs, i))
                stage_seconds['worlds'] += time.perf_counter() - t0
                extend(None, range(1, W))
                for route in shortlisted:
                    extend(route, range(1, W))
                    if lazy_keep and route not in rejected:
                        c = next(c for c in alternatives if c['route'] == route)
                        if _admit(assess(c, predictions[route], predictions[None][:len(predictions[route])],
                                         existing), W, final_min)['admitted']:
                            break
            stage_seconds['expand'] = time.perf_counter() - t0
        except SearchDeadline:
            timed_out = True
        rows = []
        for c in candidates:
            route = c['route']
            pred = predictions.get(route, []) if route is not None else []
            if route is not None and pred:
                row = assess(c, pred, predictions[None][:len(pred)], existing)
            else:
                row = dict(c, predictions=pred, protection_failures=[], margin_deltas=[], cash_deltas=[],
                           mean_margin=0.0, risk_score=0.0, minimum_margin=0.0)
            if route in rejected:
                row['protection_failures'].append(rejected[route])
                row['early_rejection'] = 'protected_cohort_missing_at_commitment_boundary'
            row['scouted'] = bool(pred)
            row['expanded'] = route in shortlisted
            row['skipped_native_commit'] = route in skipped
            if route is None:
                row['fully_evaluated'], row['admitted'] = True, False
            else:
                _admit(row, W, final_min)
            rows.append(row)
        allowed = [r for r in rows if r['admitted']]
        chosen = max(allowed, key=lambda r: r['risk_score']) if allowed else rows[0]
        decision = dict(day=int(obs['day']), selected=chosen['route'], selected_episode=chosen['episode'],
            candidates=rows, until=min(719, (int(obs['day'])+3)*24), native_route=native_route,
            worlds=[dict(index=w['index'], shops=w['shops'][29], donor=w['donor']) for w in world_list],
            seconds=time.perf_counter()-started, stage_seconds=stage_seconds, timed_out=timed_out,
            budget_seconds=budget_seconds, shortlisted=shortlisted, skipped=skipped,
            scout_order=[dict(route=r['route'], gain=r['mean_margin']) for r in
                         sorted(scout, key=lambda r: r['risk_score'], reverse=True)],
            params=dict(count=count, keep=keep, lazy_keep=lazy_keep, worlds=W, scout_min=scout_min, final_min=final_min,
                        skip_native_commit=skip_native_commit, max_hamming=max_hamming),
            rollouts=runner.rollouts, pruned_rollouts=runner.pruned_rollouts,
            simulated_turns=runner.simulated_turns, source_sha256=V.SOURCE_SHA256,
            planner_sha256=PLANNER_SHA256,
            protocol='V9-lite: V9 shortlist prefix, exact world-0 scout, expand only positive scouts, admission on '
                     'the first `worlds` V9 worlds with V3 rules; commit three days, then native routing.')
        return chosen['route'], decision
    finally:
        runner.rollout_impl.__globals__['_deadline'] = None
        runner.busy = False


def summarize(decision):
    """Compact, JSON-able digest of a V9 or lite decision (per-candidate per-world deltas, no rollouts)."""
    out = {k: decision.get(k) for k in ('day', 'selected', 'selected_episode', 'strict_selected', 'until',
                                         'native_route', 'shortlisted', 'skipped', 'timed_out', 'rollouts',
                                         'pruned_rollouts', 'simulated_turns', 'seconds', 'stage_seconds',
                                         'scout_order', 'params', 'rank_seconds')}
    rows = []
    for r in decision.get('candidates') or []:
        rows.append(dict(route=r.get('route'), episode=r.get('episode'), hamming=r.get('hamming'),
                         distance=r.get('distance'), deltas=r.get('margin_deltas'), cash=r.get('cash_deltas'),
                         risk=r.get('risk_score'), admitted=r.get('admitted'), full=r.get('fully_evaluated'),
                         scouted=r.get('scouted'), expanded=r.get('expanded'),
                         early=r.get('early_rejection'),
                         failures=[{k: v for k, v in f.items() if k != 'assets'} | {'n_assets': len(f.get('assets') or [])}
                                   for f in (r.get('protection_failures') or [])]))
    out['candidates'] = rows
    return out

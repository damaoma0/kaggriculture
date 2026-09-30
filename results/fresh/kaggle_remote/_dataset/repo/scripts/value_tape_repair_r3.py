"""Repair R1 plus separate tests of future shops and rival sale timing.

New repairs must beat the native V9 fallback over 16 balanced shop futures,
then satisfy the downside bound under 16 delayed-delivery stress scenarios.
Stress scenarios are not assigned probabilities or mixed into the mean.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import time

import value_tape_repair_r1 as R
from value_tape_repair_r2 import scenario_shops

V, F, B = R.V, R.F, R.B
install, commit, unpack = R.install, R.commit, R.unpack
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


def delay_sales(world, hours):
    hourly = defaultdict(Counter)
    for step, flows in world['hourly'].items():
        for product, amount in flows.items():
            delayed_step = min(718, step + hours) if amount > 0 else step
            hourly[delayed_step][product] += amount
    return dict(world, hourly={t: dict(v) for t, v in hourly.items()}, delivery_delay=hours)


def choose(obs, memory, *, count=7, keep=2, max_repairs=2, budget_seconds=18.0):
    started = time.perf_counter()
    selected, decision = R.choose(obs, memory, count=count, keep=keep,
                                  max_repairs=max_repairs, budget_seconds=budget_seconds)
    decision['initial_planner_sha256'] = decision['planner_sha256']
    decision['planner_sha256'] = PLANNER_SHA256
    decision['protocol'] += ' New repair additionally needs 16 ordinary futures and 16 separate delivery-delay stresses versus the V9 fallback; default 18s cooperative decision deadline.'
    if not unpack(selected)[1]:
        return selected, decision
    repair = next(c for c in decision['candidates'] if c['route'] == selected)
    originals = [c for c in decision['candidates'] if not c.get('repair_assets') and c['admitted']]
    fallback = max(originals, key=lambda c: c['risk_score']) if originals else decision['candidates'][0]
    predictions, bases = list(repair['predictions']), list(fallback['predictions'])
    assert len(predictions) == len(bases) == 8
    runner = R.runtime()
    assert not runner.busy
    runner.busy = True
    deadline = None if budget_seconds is None else started + max(0, budget_seconds)
    runner.rollout_impl.__globals__['_deadline'] = deadline
    existing = V.asset_keys(obs['farms'][int(obs['player'])])
    missing, timed_out, stress, extra_worlds = None, False, [], []
    validation = None

    def forecast(world):
        if deadline is not None and time.perf_counter() >= deadline:
            raise B.B.SearchDeadline()
        base = runner.rollout(obs, memory, fallback['route'], world, decision['until'])
        protected = existing & set(map(tuple, base['survives']))
        alternative = runner.rollout(obs, memory, selected, world, decision['until'], protected)
        return base, alternative

    try:
        runner.prepare(obs)
        runner.world_batch._world.__globals__['M'].scenario_shops = scenario_shops
        for i in range(8, 16):
            world = runner.world_batch.world(obs, i)
            extra_worlds.append(dict(index=i, shops=world['shops'][29], donor=world['donor']))
            base, alternative = forecast(world)
            if alternative.get('early_rejection'):
                missing = dict(scenario=i, assets=alternative['missing'])
                break
            bases.append(base)
            predictions.append(alternative)
        validation = R.assess(dict(route=selected), predictions, bases, existing)
        ordinary_complete = len(predictions) == 16 and missing is None
        if ordinary_complete and validation['admitted']:
            for i in range(8):
                world = runner.world_batch.world(obs, i)
                for hours in (6, 12):
                    base, alternative = forecast(delay_sales(world, hours))
                    if alternative.get('early_rejection'):
                        missing = dict(scenario=i, delay=hours, assets=alternative['missing'])
                        break
                    row = R.assess(dict(route=selected), [alternative], [base], existing)
                    stress.append(dict(index=i, delay=hours, margin_delta=row['mean_margin'],
                                       cash_delta=row['cash_deltas'][0],
                                       protection_failures=row['protection_failures'],
                                       baseline=base, candidate=alternative))
                    if row['protection_failures'] or row['minimum_margin'] < -validation['loss_budget']:
                        break
                if missing or (stress and (stress[-1]['protection_failures'] or
                                           stress[-1]['margin_delta'] < -validation['loss_budget'])):
                    break
    except B.B.SearchDeadline:
        timed_out = True
    finally:
        runner.rollout_impl.__globals__['_deadline'] = None
        runner.busy = False
    if validation is None:
        validation = R.assess(dict(route=selected), predictions, bases, existing)
    complete = len(predictions) == 16 and len(stress) == 16 and missing is None and not timed_out
    stress_min = min((r['margin_delta'] for r in stress), default=None)
    admitted = (complete and validation['admitted'] and stress_min >= -validation['loss_budget']
                and not any(r['protection_failures'] for r in stress))
    validation.update(admitted=bool(admitted), fully_evaluated=complete, comparator=fallback['route'],
                      baseline_predictions=bases, additional_worlds=extra_worlds, stress=stress,
                      stress_minimum_margin=stress_min, missing_cohorts=missing, timed_out=timed_out,
                      seconds=time.perf_counter()-started-decision['seconds'])
    decision['repair_validation'] = validation
    decision['rollouts'] += runner.rollouts
    decision['simulated_turns'] += runner.simulated_turns
    decision['pruned_rollouts'] += runner.pruned_rollouts
    decision['timed_out'] |= timed_out
    decision['seconds'] = time.perf_counter()-started
    if not admitted:
        selected = fallback['route']
        decision['selected'] = selected
        decision['selected_episode'] = fallback['episode']
    return selected, decision


if __name__ == '__main__':
    raise SystemExit('Import choose(observation, own_memory).')

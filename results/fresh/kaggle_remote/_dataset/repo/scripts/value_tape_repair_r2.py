"""R1 transitions with an additional 24 common futures for a proposed repair.

The comparator is the original V9 finalist at the same current state. New shop
paths are three additional independently shuffled eight-world blocks, each
balanced over shop types at every reveal. No actual future or opponent identity
is used. Native V9 selection remains available if the new repair fails.
"""
from hashlib import sha256
from pathlib import Path
import random
import statistics
import time

import value_tape_repair_r1 as R

V, F, B = R.V, R.F, R.B
install, commit, unpack = R.install, R.commit, R.unpack
PLANNER_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


def scenario_shops(obs, index):
    model = B.B.M.M
    if index < 8:
        return model.scenario_shops(obs, index)
    origin = int(obs['day'])
    shops = list(obs['town']['unlocked_shops'])
    result = {}
    for day in range(origin, 30):
        if day > origin and day in range(3, 25, 3) and len(shops) < 8:
            options = sorted(model.DEMAND)
            random.Random(72641393 + (index // 8) * 100003 + origin * 1009 + day * 9173).shuffle(options)
            shops.append(options[index % 8])
        result[day] = list(shops)
    return result


def choose(obs, memory, *, count=7, keep=2, max_repairs=2, budget_seconds=None):
    started = time.perf_counter()
    selected, decision = R.choose(obs, memory, count=count, keep=keep,
                                  max_repairs=max_repairs, budget_seconds=budget_seconds)
    decision['initial_planner_sha256'] = decision['planner_sha256']
    decision['planner_sha256'] = PLANNER_SHA256
    decision['protocol'] += ' Proposed repaired winner must additionally beat the V9 fallback over 32 common futures.'
    if not unpack(selected)[1]:
        return selected, decision
    repairs = next(c for c in decision['candidates'] if c['route'] == selected)
    originals = [c for c in decision['candidates'] if not c.get('repair_assets') and c['admitted']]
    fallback = max(originals, key=lambda c:c['risk_score']) if originals else decision['candidates'][0]
    repaired_predictions = list(repairs['predictions'])
    baseline_predictions = list(fallback['predictions'])
    assert len(repaired_predictions) == len(baseline_predictions) == 8
    runner = R.runtime()
    assert not runner.busy
    runner.busy = True
    deadline = None if budget_seconds is None else started + max(0, budget_seconds)
    runner.rollout_impl.__globals__['_deadline'] = deadline
    existing = V.asset_keys(obs['farms'][int(obs['player'])])
    missing, timed_out, worlds = None, False, []
    try:
        runner.prepare(obs)
        runner.world_batch._world.__globals__['M'].scenario_shops = scenario_shops
        for index in range(8, 32):
            if deadline is not None and time.perf_counter() >= deadline:
                raise B.B.SearchDeadline()
            world = runner.world_batch.world(obs, index)
            worlds.append(dict(index=index, shops=world['shops'][29], donor=world['donor']))
            base = runner.rollout(obs, memory, fallback['route'], world, decision['until'])
            protection = existing & set(map(tuple, base['survives']))
            repaired = runner.rollout(obs, memory, selected, world, decision['until'], protection)
            if repaired.get('early_rejection'):
                missing = dict(scenario=index, assets=repaired['missing'])
                break
            baseline_predictions.append(base)
            repaired_predictions.append(repaired)
    except B.B.SearchDeadline:
        timed_out = True
    finally:
        runner.rollout_impl.__globals__['_deadline'] = None
        runner.busy = False
    validation = R.assess(dict(route=selected), repaired_predictions, baseline_predictions, existing)
    validation['fully_evaluated'] = len(repaired_predictions) == 32 and missing is None
    validation['admitted'] = bool(validation['admitted'] and validation['fully_evaluated'])
    validation.update(comparator=fallback['route'], baseline_predictions=baseline_predictions,
                      additional_worlds=worlds, missing_cohorts=missing, timed_out=timed_out,
                      seconds=time.perf_counter()-started-decision['seconds'])
    decision['repair_validation'] = validation
    decision['rollouts'] += runner.rollouts
    decision['simulated_turns'] += runner.simulated_turns
    decision['pruned_rollouts'] += runner.pruned_rollouts
    decision['timed_out'] |= timed_out
    decision['seconds'] = time.perf_counter()-started
    if not validation['admitted']:
        selected = fallback['route']
        decision['selected'] = selected
        decision['selected_episode'] = fallback['episode']
    return selected, decision


if __name__ == '__main__':
    raise SystemExit('Import choose(observation, own_memory).')

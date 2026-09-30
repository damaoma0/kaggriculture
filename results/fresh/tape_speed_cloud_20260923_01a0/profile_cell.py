"""Run after the timing panel, never concurrently with latency measurement."""
import cProfile
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import pstats
import sys
import time

root = Path('/kaggle/working/tape_speed_01a0')
sys.path[:0] = [str(root/'scripts'), str(root/'vendor')]
import value_tape_search_v8 as planner
from kaggle_environments.utils import structify

with gzip.open(root/'checkpoints.pkl.gz', 'rb') as handle:
    point = pickle.load(handle)[0]
observation = structify(point['obs'])
started = time.perf_counter()
runner = planner.runtime()
initialization = time.perf_counter() - started
started = time.perf_counter()
runner.prepare(observation)
preparation = time.perf_counter() - started
started = time.perf_counter()
candidates = runner.shortlist(observation, point['memory'], 7)
retrieval = time.perf_counter() - started
started = time.perf_counter()
world = planner.M.world(observation, 0)
scenario = time.perf_counter() - started
started = time.perf_counter()
baseline = runner.rollout(observation, point['memory'], None, world)
baseline_wall = time.perf_counter() - started
scenario_batches = []
for repetition in range(2):
    started = time.perf_counter()
    worlds = [planner.M.world(observation, i) for i in range(8)]
    scenario_batches.append(time.perf_counter() - started)
protected = planner.V.asset_keys(observation['farms'][observation['player']]) & set(map(tuple, baseline['survives']))
profiler = cProfile.Profile()
prediction = profiler.runcall(runner.rollout, observation, point['memory'], point['expected_selected'], world, protected=protected)
stats = pstats.Stats(profiler)
rows = [dict(file=Path(k[0]).name, line=k[1], function=k[2], primitive_calls=v[0],
             calls=v[1], self_seconds=v[2], cumulative_seconds=v[3])
        for k, v in stats.stats.items()]
fingerprint = hashlib.sha256(json.dumps(planner.V.canonical(prediction), sort_keys=True, separators=(',', ':')).encode()).hexdigest()
assert fingerprint == point['expected_forecasts'][str(point['expected_selected'])][0]
result = dict(case=point['id'], initialization=initialization, preparation=preparation,
              retrieval=retrieval, scenario=scenario, baseline_rollout_wall=baseline_wall,
              eight_scenario_batches=scenario_batches,
              profiled_seconds=stats.total_tt, profiled_calls=stats.total_calls,
              top_self=sorted(rows, key=lambda r:r['self_seconds'], reverse=True)[:25],
              top_cumulative=sorted(rows, key=lambda r:r['cumulative_seconds'], reverse=True)[:30])
(root.parent/'cloud_results/profile.json').write_text(json.dumps(result, indent=2))
print('PROFILE ' + json.dumps(result), flush=True)

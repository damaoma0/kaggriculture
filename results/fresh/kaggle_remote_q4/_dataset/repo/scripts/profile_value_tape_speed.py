"""Isolated timing and cProfile evidence for the frozen V4 selector."""
import cProfile
from copy import deepcopy
import json
from pathlib import Path
import pstats
import time

import audit_value_forecast_components as A
import rival_trajectory_model_v3 as M
import value_tape_search as V
import value_tape_search_v2 as V2
import value_tape_search_v4 as V4

OUT = V.ROOT / 'results/fresh/value_tape_speed_20260923'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    context = A.context('wool')
    # Diagnostic future fields are deliberately not passed to either selector.
    obs, memory = context['observation'], context['memory']
    timings = {}
    start = time.perf_counter()
    candidates = V.shortlist(obs, memory)
    timings['shortlist'] = time.perf_counter() - start
    start = time.perf_counter()
    worlds = [M.world(obs, i) for i in range(8)]
    timings['worlds_cold'] = time.perf_counter() - start
    start = time.perf_counter()
    V.fresh_agent(memory)
    timings['fresh_agent'] = time.perf_counter() - start
    profiler = cProfile.Profile()
    profiler.enable()
    reference = V2.rollout(obs, memory, 0, worlds[0])
    profiler.disable()
    profiler.dump_stats(str(OUT / 'v4_rollout.prof'))
    with (OUT / 'v4_profile.txt').open('w', encoding='utf-8') as output:
        stats = pstats.Stats(profiler, stream=output)
        stats.sort_stats('cumulative').print_stats(55)
        stats.sort_stats('tottime').print_stats(30)
    print(json.dumps(dict(timings=timings, profile_ready=True)), flush=True)
    selected, decision = V4.choose(obs, memory)
    (OUT / 'wool_v4_reference.json').write_text(json.dumps(decision, indent=2), encoding='utf-8')
    timings['choose_v4_warm'] = decision['seconds']
    (OUT / 'profile_summary.json').write_text(json.dumps(dict(timings=timings, selected=selected,
        reference=reference, candidates=candidates), indent=2), encoding='utf-8')
    print(json.dumps(dict(timings=timings, selected=selected)), flush=True)


if __name__ == '__main__':
    main()

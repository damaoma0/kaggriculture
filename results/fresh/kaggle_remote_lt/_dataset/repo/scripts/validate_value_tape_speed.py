"""Serial V5 timing and full-forecast equality against frozen V4 references."""
from copy import deepcopy
import cProfile
import json
import pstats

import audit_value_forecast_components as A
import probe_value_tape_search as P
import rival_trajectory_model_v3 as M
import value_tape_search_v5 as F

OUT = F.V.ROOT / 'results/fresh/value_tape_speed_20260923'


def main():
    rows = []
    c = A.context('wool')
    for i in range(3):
        route, d = F.choose(c['observation'], c['memory'])
        ref = json.loads((OUT / 'wool_v4_reference.json').read_text(encoding='utf-8'))
        assert json.loads(json.dumps(d['candidates'])) == ref['candidates'] and d['worlds'] == ref['worlds']
        rows.append(dict(case='wool', repeat=i, selected=route, seconds=d['seconds'],
            rollouts=d['rollouts'], complete_forecast_equal=True, timings=d['timings']))
        print(json.dumps(rows[-1]), flush=True)
    for episode, day in ((111262874, 12), (111287532, 12)):
        game, pair = P.load(episode)
        state, memory = P.checkpoint(game, pair, day)
        obs = deepcopy(state[game['seat']].observation)
        route, d = F.choose(obs, memory)
        ref = json.loads((A.OUT / f'v4_historical/{episode}-{day}.json').read_text(encoding='utf-8'))['decision']
        # Old JSON roundtrips tuples; canonicalize both before comparing.
        same = json.loads(json.dumps(d['candidates'])) == ref['candidates']
        assert same and d['worlds'] == ref['worlds'], episode
        (OUT / f'{episode}-{day}-v5.json').write_text(json.dumps(d, indent=2), encoding='utf-8')
        rows.append(dict(case=str(episode), selected=route, seconds=d['seconds'],
            rollouts=d['rollouts'], complete_forecast_equal=True, timings=d['timings']))
        print(json.dumps(rows[-1]), flush=True)
    runner = F.runtime()
    runner.prepare(c['observation'])
    world = M.world(c['observation'], 0)
    profiler = cProfile.Profile()
    profiler.runcall(runner.rollout, c['observation'], c['memory'], 0, world)
    with (OUT / 'v5_profile.txt').open('w', encoding='utf-8') as file:
        pstats.Stats(profiler, stream=file).sort_stats('cumulative').print_stats(40)
    (OUT / 'equivalence_and_speed.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

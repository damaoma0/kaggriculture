"""Full-forecast equivalence and ownership audit for borrowed observations."""
from copy import deepcopy
import json

import audit_value_forecast_components as A
import probe_value_tape_search as P
import rival_trajectory_model_v3 as M
import value_tape_search_v5 as F
import value_tape_search_v6 as B

OUT = F.V.ROOT / 'results/fresh/value_tape_speed_20260923'


def main():
    rows = []
    context = A.context('wool')
    for i in range(3):
        _, d = B.choose(context['observation'], context['memory'])
        reference = json.loads((OUT / 'wool_v4_reference.json').read_text(encoding='utf-8'))
        assert json.loads(json.dumps(d['candidates'])) == reference['candidates']
        assert d['worlds'] == reference['worlds']
        row = dict(case='wool', repeat=i, selected=d['selected'], seconds=d['seconds'],
            rollouts=d['rollouts'], complete_forecast_equal=True, timings=d['timings'])
        rows.append(row)
        print(json.dumps(row), flush=True)
    audit = B.Runtime(audit=True)
    audit.prepare(context['observation'])
    assert audit.shortlist(context['observation'], context['memory']) == F.runtime().shortlist(
        context['observation'], context['memory'])
    for name in ('wool', 'false_positive'):
        c = A.context(name)
        obs, memory = c['observation'], c['memory']
        audit.prepare(obs)
        for route, index in ((None, 0), (c['spec']['route'], 5)):
            world = M.world(obs, index)
            expected_runner = F.runtime()
            expected_runner.prepare(obs)
            expected = expected_runner.rollout(obs, memory, route, world)
            actual = audit.rollout(obs, memory, route, world)
            assert expected == actual
    for episode, day in ((111262874, 12), (111287532, 12)):
        game, pair = P.load(episode)
        state, memory = P.checkpoint(game, pair, day)
        obs = deepcopy(state[game['seat']].observation)
        route, d = B.choose(obs, memory)
        reference = json.loads((OUT / f'{episode}-{day}-v5.json').read_text(encoding='utf-8'))
        assert json.loads(json.dumps(d['candidates'])) == reference['candidates']
        assert d['worlds'] == reference['worlds']
        audit.prepare(obs)
        world = M.world(obs, 0)
        expected_runner = F.runtime()
        expected_runner.prepare(obs)
        assert audit.rollout(obs, memory, route, world) == expected_runner.rollout(obs, memory, route, world)
        (OUT / f'{episode}-{day}-v6.json').write_text(json.dumps(d, indent=2), encoding='utf-8')
        row = dict(case=str(episode), selected=route, seconds=d['seconds'], rollouts=d['rollouts'],
            complete_forecast_equal=True, timings=d['timings'])
        rows.append(row)
        print(json.dumps(row), flush=True)
    result = dict(rows=rows, audited_turns=audit.audited_turns, planner_sha256=B.PLANNER_SHA256,
        contract='Every audited call left observations unchanged and retained no mutable observation aliases in agent memory or returned actions.')
    (OUT / 'borrowed_equivalence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(audited_turns=audit.audited_turns)), flush=True)


if __name__ == '__main__':
    main()

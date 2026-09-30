"""Read-only checks of the frozen smoke-v1 day-6 observed-prefix contract."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'results/fresh/semantic_strategy_20260928'
FROZEN = STUDY / 'candidates/smoke_v1/project'
sys.path.insert(0, str(FROZEN / 'scripts'))
from semantic_strategy_policy_20260928 import SemanticStrategyPolicy
from semantic_strategy_tiles_20260928 import observe_own, cells_from_farm, build_plan
from semantic_tile_planner_20260928 import label


def main():
    policy = SemanticStrategyPolicy(FROZEN / 'results/fresh/semantic_strategy_20260928/causal_daily_rows.json')
    index = json.loads((ROOT / 'results/fresh/coherent_opening_20260924_01a0/extraction/full/index.json').read_text())
    cases = []
    for info in index[:8]:
        path = ROOT / f'data/dsm_replays/episode-{info["episode"]}-replay.json'
        replay = json.loads(path.read_text(encoding='utf-8'))
        memory = {}
        for step in range(145):
            obs = deepcopy(replay['steps'][step][info['seat']]['observation'])
            obs['step'] = step
            observe_own(obs, memory)
        cells = cells_from_farm(obs['farms'][info['seat']])
        for tile, value in cells.items():
            if value.get('crop'):
                assert memory['observed_prefix']['plant'][value['planted_day']][tile] == value['crop']
        before = deepcopy(obs)
        proposal = policy.propose(obs, {})
        start = time.perf_counter()
        plan, _, audit = build_plan(obs, proposal, memory)
        elapsed = time.perf_counter() - start
        assert obs == before
        assert plan['board'][6] == [label(cells[str(i)]) for i in range(100)]
        assert plan['plant'][:6] == memory['observed_prefix']['plant'][:6]
        end_cells = audit['today']['tiles']
        retained = 0
        for tile, value in cells.items():
            if value.get('crop'):
                assert end_cells[tile]['crop'] == value['crop']
                assert end_cells[tile]['planted_day'] == value['planted_day']
                retained += 1
            if value.get('animal'):
                assert end_cells[tile]['animal'] == value['animal']
                assert end_cells[tile]['placed_day'] == value['placed_day']
                retained += 1
        cases.append(dict(episode=info['episode'], seat=info['seat'], retained_initial_cohorts=retained,
            compile_seconds=elapsed, warnings=plan['planner_metadata']['warnings'],
            requested_day6=proposal['today'], compiled_day6=audit['semantic_today']))
    report = dict(snapshot='smoke_v1', cases=cases, checks_passed=len(cases), games_executed=0,
        checks=['Every live initial crop birth has an observed prefix planting event.',
            'Day6 board equals actual current observation, not a donor board.',
            'All initial cohorts retain tile/type/birth through these day6 compilations.',
            'Opening planting prefix copied exactly; observations remain unchanged.'])
    (STUDY / 'day6_handoff_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(checks_passed=len(cases), max_compile_seconds=max(x['compile_seconds'] for x in cases), games_executed=0)))


if __name__ == '__main__':
    main()

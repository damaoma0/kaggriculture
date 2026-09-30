"""Complete the sole old checkpoint whose eight-world labels were absent."""
from copy import deepcopy
import json
from types import FunctionType, SimpleNamespace

import benchmark_tape_scout as B
import benchmark_value_tape_v3 as Old
import train_tape_semantic_ranker as T
import value_tape_search_v7 as Exact
import value_tape_search_v8 as Scout


def main():
    from kaggle_environments.utils import structify
    point = next(p for p in T.load_points() if p['id'] == 'v3-2761107011-1-day18')
    obs, memory = structify(point['obs']), point['memory']
    cache = B.ForecastCache(obs)
    route, scout = cache.choose(Scout, obs, memory)
    exact_route, exact = cache.choose(Exact, obs, memory)
    source = json.loads(open(point['source'], encoding='utf-8').read())
    folder = T.OUT / 'resolved_censored'
    (folder / 'v3_live').mkdir(parents=True, exist_ok=True)
    def chosen(observation, own_memory):
        assert B.digest(observation, own_memory) == B.digest(obs, memory)
        return route, deepcopy(scout)
    runner = FunctionType(Old.live_game.__code__, dict(Old.live_game.__globals__,
        V3=SimpleNamespace(choose=chosen), OUT=folder), 'resolved_case', Old.live_game.__defaults__)
    if route is None:
        result = deepcopy(source['baseline'])
    else:
        result = runner(source['spec'], True)
    report = dict(id=point['id'], old_v3_selected=point['decision']['selected'],
        scout=scout, exact=exact, selection_equal=route == exact_route,
        baseline=source['baseline'], candidate=result,
        margin_delta=result['margin']-source['baseline']['margin'],
        evidence='Completed forecasts and responsive fixed-shop evaluation of an existing development checkpoint, not a fresh-world qualification.')
    (folder / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(id=point['id'], scout=route, exact=exact_route,
        selection_equal=route == exact_route, margin_delta=report['margin_delta'])), flush=True)


if __name__ == '__main__':
    main()

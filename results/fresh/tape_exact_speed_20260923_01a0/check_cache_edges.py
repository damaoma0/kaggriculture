"""Focused packed-lane and cancellation isolation checks, outside timing."""
from copy import deepcopy
import json
import random
import time

import run_local as H


def main():
    H.verify()
    N, structify, points = H.imports()
    original = lambda a, b: sum(1 for x, y in zip(a, b) if x != y)
    packed = N.PackedHamming(original, maxsize=64)
    checks = 0
    left = ['\0\0'] * 100
    right = left.copy()
    for lane in range(100):
        for char in range(2):
            for bit in range(7):
                label = ['\0', '\0']
                label[char] = chr(1 << bit)
                right[lane] = ''.join(label)
                assert packed(left, right) == 1
                right[lane] = left[lane]
                assert packed(left, right) == 0
                checks += 2
    rng = random.Random(23819)
    for _ in range(300):
        right[:] = left
        changed = rng.sample(range(100), rng.randrange(101))
        for lane in changed:
            right[lane] = chr(rng.randrange(1, 128)) + chr(rng.randrange(128))
        assert packed(left, right) == len(changed)
        checks += 1
    assert packed.encode.cache_info().currsize <= 64
    result = dict(packed_lane_and_mutation_checks=checks, bounded_cache=True)
    # Force cancellation after a completed search, then repeat on a different
    # observation. This catches stale day/farm caches and dirty rollout hooks.
    first = points[0]
    selected, before = N.choose(structify(first['obs']), first['memory'])
    probes = []
    for budget in (0.0, 0.8):
        obs, memory = structify(deepcopy(first['obs'])), deepcopy(first['memory'])
        original_input = H.digest(N.V.canonical([obs, memory]))
        start = time.perf_counter()
        route, decision = N.choose(obs, memory, budget_seconds=budget)
        wall = time.perf_counter()-start
        assert original_input == H.digest(N.V.canonical([obs, memory]))
        assert not N.runtime().busy
        assert N.runtime().rollout_impl.__globals__['_deadline'] is None
        assert N.runtime().rollout_impl.__globals__['_required_assets'] == set()
        if route is not None:
            row = next(c for c in decision['candidates'] if c['route'] == route)
            assert row['admitted'] and row['fully_evaluated']
        else:
            assert not any(c['admitted'] for c in decision['candidates'])
        probes.append(dict(budget=budget, wall_seconds=wall, selected=route,
                           timed_out=decision['timed_out'], rollouts=decision['rollouts']))
    second = points[1]
    for p in (second, first):
        _, decision = N.choose(structify(p['obs']), p['memory'])
        forecasts = {str(c['route']):[H.digest(N.V.canonical(x)) for x in c['predictions']]
                     for c in decision['candidates']}
        for route, predictions in forecasts.items():
            for i, value in enumerate(predictions):
                expected = p['expected_forecasts'].get(route, [])
                if i < len(expected):
                    assert value == expected[i]
        assert decision['selected'] == p['expected_selected']
        if p is first:
            assert N.V.canonical(H.semantic(before)) == N.V.canonical(H.semantic(decision))
    result.update(deadline_probes=probes, post_cancellation_full_decisions_equal=True,
                  alternating_input_isolation=True, input_and_hooks_restored=True)
    H.write(H.ROOT / 'cache_edge_checks.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()

"""Warm paired wall/CPU timings so background load does not masquerade as speed."""
import json
import time

import audit_value_forecast_components as A
import rival_trajectory_model_v3 as M
import value_tape_search_v5 as F
import value_tape_search_v6 as B


def main():
    context = A.context('wool')
    obs, memory = context['observation'], context['memory']
    F.runtime()
    B.runtime()
    for i in range(8):
        M.world(obs, i)
    rows = []
    reference = None
    for label, choose in [('v5', F.choose), ('v6', B.choose), ('v6', B.choose), ('v5', F.choose)]:
        wall, cpu = time.perf_counter(), time.process_time()
        route, result = choose(obs, memory)
        timing = dict(version=label, wall=time.perf_counter()-wall, cpu=time.process_time()-cpu,
            selected=route, rollouts=result['rollouts'])
        predictions = result['candidates']
        if reference is None:
            reference = predictions
        assert predictions == reference
        rows.append(timing)
        print(json.dumps(timing), flush=True)
    path = F.V.ROOT / 'results/fresh/value_tape_speed_20260923/paired_runtime.json'
    path.write_text(json.dumps(dict(rows=rows, v5_sha256=F.PLANNER_SHA256,
        v6_sha256=B.PLANNER_SHA256, complete_forecasts_equal=True), indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

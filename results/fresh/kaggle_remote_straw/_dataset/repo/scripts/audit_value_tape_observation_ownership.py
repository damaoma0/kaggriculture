"""Ownership checks for the current V6 source, independent of speed timing."""
from copy import deepcopy
import json

import audit_value_forecast_components as A
import rival_trajectory_model_v3 as M
import value_tape_search_v6 as B


def main():
    runner = B.Runtime(audit=True)
    for name in ('wool','false_positive'):
        c=A.context(name)
        obs,memory=c['observation'],c['memory']
        before=deepcopy([obs,memory])
        runner.prepare(obs)
        runner.shortlist(obs,memory)
        for route,index in ((None,0),(c['spec']['route'],5)):
            runner.rollout(obs,memory,route,M.world(obs,index))
        assert [obs,memory]==before
    result=dict(planner_sha256=B.PLANNER_SHA256,audited_turns=runner.audited_turns,
        observations_unchanged=True,no_mutable_aliases_retained=True,
        native_sha256=B.F.V.SOURCE_SHA256)
    target=B.F.V.ROOT/'results/fresh/value_tape_speed_20260923/ownership_audit.json'
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

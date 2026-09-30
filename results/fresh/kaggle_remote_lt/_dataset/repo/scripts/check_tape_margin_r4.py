"""Admission regressions, spending failure rejection, deadline and input checks."""
from copy import deepcopy
import sys
import run_tape_margin_study as S

sys.path[:0]=[str(S.OUT/'payload/scripts'),str(S.OUT/'payload/vendor')]
import value_tape_margin_r4 as N

def main():
    old=S.read(S.FROZEN/'decisions/fresh-22-v56-candidate-d15.json')
    frozen=S.digest(old)
    winner,checks=N.select_margin(old);assert winner['route']==496
    assert S.digest(old)==frozen
    failed=deepcopy(old)
    next(c for c in failed['candidates'] if c['route']==496)['predictions'][3]['failures']['BUY_ANIMAL']=1
    winner,checks=N.select_margin(failed);assert winner['route']!=496
    assert next(c for c in checks if c['route']==496)['extra_failed_spending']
    veto=S.read(S.PREVIOUS/'r3dev/decisions/random-06-v56-candidate-d15.json')
    winner,_=N.select_margin(veto);assert winner['route'] is None,'Must not revive a failed repair'
    repair=S.read(S.FROZEN/'decisions/fresh-11-original_m1-candidate-d18.json')
    winner,_=N.select_margin(repair);assert winner['route']==repair['selected']
    regression=S.read(S.FROZEN/'decisions/fresh-12-v56-candidate-d12.json')
    winner,_=N.select_margin(regression);assert winner['route']==47,'This rule does not fix the forecast regression'
    spec=next(s for s in S.read(S.FROZEN/'design.json')['specs'] if s['id']=='fresh-22-v56')
    actions=S.read(S.FROZEN/'actions/fresh-22-v56-baseline.json')
    game=dict(seed=spec['seed'],seat=spec['seat'],shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    entry=N.V.fresh_agent();seat=spec['seat']
    with N.V.R.Simulator(game) as sim:
        state=deepcopy(sim.initial)
        for t in range(360):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            if t%24==0:state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
            assert entry(deepcopy(state[seat].observation))==actions[seat][t]
            for s in range(2):state[s].action=actions[s][t]
            N.V.R.engine().interpreter(state,sim.env)
        obs=deepcopy(state[seat].observation);obs.step=360;obs.town['unlocked_shops'][:]=game['shops'][15]
        memory=N.V.memory_of(entry)
    before=S.digest(N.V.canonical([obs,memory]))
    route,empty=N.choose(obs,memory,budget_seconds=0)
    assert route is None and empty['timed_out'] and not empty['margin_override']
    route,full=N.choose(obs,memory,budget_seconds=None)
    assert route==496 and full['margin_override'] and full['r3_selected'] is None
    assert S.digest(N.V.canonical([obs,memory]))==before
    runtime=N.R3.R.runtime();assert not runtime.busy and runtime.rollout_impl.__globals__['_deadline'] is None
    result=dict(saved_checkpoint_selects_496=True,spending_failure_blocks_override=True,
        failed_repair_remains_rejected=True,good_repair_preserved=True,known_forecast_regression_retained=True,
        zero_deadline_safe=True,same_process_deadline_recovery=True,inputs_unchanged=True,
        full_decision_seconds=full['seconds'],policy_sha256=N.PLANNER_SHA256)
    S.write(S.OUT/'functional_checks.json',result);print(S.json.dumps(result))

if __name__=='__main__':main()

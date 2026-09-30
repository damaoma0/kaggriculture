"""Functional checks of deadline recovery, public futures, and cohort identity."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from diagnose_repair_forecast import OLD, STUDY, N, replay
import value_tape_repair_r3 as R3


def main():
    spec=json.loads((OLD/'pairs/random-11-v56.json').read_text())['spec']
    # replay() captures day 15; obtain day 12 by using the original episode
    # checkpoint mechanism below, retaining the exact live prefix.
    actions=json.loads((OLD/'actions/random-11-v56-baseline.json').read_text())
    entry=N.V.fresh_agent();seat=spec['seat']
    game=dict(seed=spec['seed'],seat=seat,shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    with N.V.R.Simulator(game) as sim:
        state=deepcopy(sim.initial)
        for t in range(288):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            if t%24==0:state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
            assert entry(deepcopy(state[seat].observation))==actions[seat][t]
            for s in range(2):state[s].action=actions[s][t]
            N.V.R.engine().interpreter(state,sim.env)
        obs=deepcopy(state[seat].observation);obs.step=288
        obs.town['unlocked_shops'][:]=game['shops'][12]
        memory=N.V.memory_of(entry)
    digest=lambda x:sha256(json.dumps(N.V.canonical(x),sort_keys=True).encode()).hexdigest()
    original=digest([obs,memory])
    selected,decision=R3.choose(obs,memory,budget_seconds=0)
    assert selected is None and decision['timed_out']
    assert not N.runtime().busy and N.runtime().rollout_impl.__globals__['_deadline'] is None
    E=N.V.isolated_engine();hooks=[E._commit_unit,E._apply_unit_action,E._do_hire]
    selected,full=R3.choose(obs,memory,budget_seconds=None)
    assert selected==(582,((6,2,'SHEEP',8),)),selected
    assert full['repair_validation']['fully_evaluated'] and full['repair_validation']['admitted']
    assert [E._commit_unit,E._apply_unit_action,E._do_hire]==hooks
    assert digest([obs,memory])==original
    assert not N.runtime().busy and N.runtime().rollout_impl.__globals__['_deadline'] is None
    for group in (0,8):
        paths=[R3.scenario_shops(obs,i) for i in range(group,group+8)]
        for d in (15,18,21,24):
            assert set(Counter(p[d][-1] for p in paths).values())=={1}
            assert all(p[d][:4]==obs.town['unlocked_shops'] for p in paths)
    world=dict(hourly={360:{'MILK':3,'WHEAT':-2},718:{'MILK':4}},shops={})
    changed=R3.delay_sales(world,12)
    assert changed['hourly']=={372:{'MILK':3},360:{'WHEAT':-2},718:{'MILK':4}}
    assert world['hourly'][360]['MILK']==3
    adapter=N.TransitionRepair.__new__(N.TransitionRepair)
    adapter.targets={(0,0):(0,0,'SHEEP',8)};adapter.until=360
    fake=dict(step=300,player=0,farms=[{'tiles':[[{'animal':'SHEEP','placed_day':9}]]}])
    assert adapter.matching(fake)=={}
    fake['farms'][0]['tiles'][0][0]['placed_day']=8
    assert adapter.matching(fake)
    fake['step']=360
    assert adapter.matching(fake)=={}
    result=dict(deadline_recovery=True,engine_hooks_restored=True,inputs_unchanged=True,
                known_repair_selected=True,balanced_public_futures=True,delivery_delay_conserves_flows=True,
                cohort_birth_and_expiry_checked=True,full_decision_seconds=full['seconds'])
    (STUDY/'functional_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()

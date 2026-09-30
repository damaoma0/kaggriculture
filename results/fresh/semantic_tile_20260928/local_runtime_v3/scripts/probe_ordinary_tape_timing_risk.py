"""Post-evaluation diagnostic: apply R3's validation to one ordinary switch.

Uses only the day-12 public checkpoint and own memory during selection. This
is a diagnostic on a discovered failure, not a new qualified playing policy.
"""
from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/tape_repair_20260924_01a0'
FROZEN=OUT/'r3holdout24'
sys.path[:0]=[str(FROZEN/'payload/scripts'),str(FROZEN/'payload/vendor')]
import value_tape_repair_r3 as N


def main():
    spec=next(s for s in json.loads((FROZEN/'design.json').read_text())['specs'] if s['id']=='fresh-12-v56')
    actions=json.loads((FROZEN/'actions/fresh-12-v56-baseline.json').read_text())
    game=dict(seed=spec['seed'],seat=spec['seat'],shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    entry=N.V.fresh_agent();seat=spec['seat']
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
    source=inspect.getsource(N.choose)
    old="if not unpack(selected)[1]:"
    assert source.count(old)==1
    source=source.replace(old,"if selected is None:")
    old="not c.get('repair_assets') and c['admitted']"
    assert source.count(old)==1
    source=source.replace(old,old+" and c['route'] != selected")
    namespace=dict(N.choose.__globals__)
    exec(compile(source,'<ordinary_switch_stress_diagnostic>','exec'),namespace)
    selected,decision=namespace['choose'](obs,memory,budget_seconds=None)
    result=dict(case=spec['id'],day=12,original_selection=47,diagnostic_selection=selected,
                frozen_policy_sha256=N.PLANNER_SHA256,diagnostic_function_sha256=sha256(source.encode()).hexdigest(),
                selection_inputs='Current day-12 public observation and own memory only; actual future shops and rival actions used solely to reconstruct the past prefix.',
                note='Post-evaluation diagnosis of a fresh-panel failure. Not a new holdout or a qualified policy.',decision=decision)
    (OUT/'ordinary_timing_diagnostic.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    v=decision.get('repair_validation',{})
    print(json.dumps({**{k:v for k,v in result.items() if k!='decision'},'validation':{k:v.get(k) for k in ('mean_margin','risk_score','minimum_margin','loss_budget','stress_minimum_margin','fully_evaluated','admitted')},'seconds':decision['seconds']}),flush=True)


if __name__=='__main__':main()

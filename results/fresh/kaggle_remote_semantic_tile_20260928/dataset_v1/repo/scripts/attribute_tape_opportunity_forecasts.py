"""Offline attribution: does giving only true future shops repair the ranking?

Actual future shops are an oracle diagnostic input, never a policy feature.
Use the best cohort-preserving realized branch and the original selected branch
from the completed, frozen native-continuation audit, with three donor futures.
"""
from copy import deepcopy
import json
from pathlib import Path
import statistics
import sys
import time
import tape_opportunity_audit as A

sys.path[:0]=[str(A.FROZEN/'payload/scripts'),str(A.FROZEN/'payload/vendor')]
import value_tape_repair_r1 as N

def main(case):
    spec=next(s for s in A.read(A.OUT/'design.json')['specs'] if s['id']==case)
    audit=next(s for s in A.read(A.OUT/'audit.json')['cases'] if s['case']==case)
    assert audit['n']==audit['expected']
    actions=A.read(Path(spec['reference'])/'actions'/f'{case}-baseline.json')
    game=dict(seed=spec['seed'],seat=spec['seat'],shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    entry=N.V.fresh_agent();seat=spec['seat'];step=spec['checkpoint']
    with N.V.R.Simulator(game) as sim:
        state=deepcopy(sim.initial)
        for t in range(step):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            if t%24==0:state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
            assert entry(deepcopy(state[seat].observation))==actions[seat][t]
            for s in range(2):state[s].action=actions[s][t]
            N.V.R.engine().interpreter(state,sim.env)
        obs=deepcopy(state[seat].observation);obs.step=step
        obs.town['unlocked_shops'][:]=game['shops'][step//24]
        memory=N.V.memory_of(entry)
    candidates=A.read(A.OUT/'candidates'/f'{case}.json')
    if A.digest(N.V.canonical([obs,memory]))!=candidates['checkpoint_sha256']:
        captured={}
        H=A.load_harness()
        def capture(policy,ours,observation,spec):
            captured.update(obs=observation,memory=policy.V.memory_of(ours))
        H.collect_candidates=capture
        try:H.run_game(dict(spec,collect=True),'candidate')
        except A.CheckpointComplete:pass
        differences=[]
        def compare(a,b,path=''):
            if isinstance(a,dict) and isinstance(b,dict):
                for k in set(a)|set(b):compare(a.get(k),b.get(k),path+'/'+str(k))
            elif isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
                for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
            elif a!=b:differences.append(dict(path=path,replay=a,harness=b))
        compare(N.V.canonical([obs,memory]),N.V.canonical([captured['obs'],captured['memory']]))
        A.write(A.OUT/'attribution'/f'{case}-checkpoint-differences.json',differences)
        assert all('/_SHP_STATES/' in d['path'] and '/cal/' in d['path'] for d in differences), differences
        obs,memory=captured['obs'],captured['memory']
    # The native calendar cache is keyed by (id(tape), day), so its raw memory
    # hash is intentionally process-specific. Check actual state and reproduce
    # the complete saved first-world baseline forecast instead.
    H=A.load_harness()
    reference=A.read(Path(spec['reference'])/'arms'/f'{case}-baseline.json')
    assert all(H.physical_key(obs['farms'][s])==reference['board_keys'][s][step] for s in range(2))
    assert H.digest(obs['private'])==reference['private_keys'][seat][step]
    ids={audit['best']['id'],audit['selected']['id']}
    chosen=[r for r in candidates['rows'] if r['id'] in ids and r['route'] is not None]
    runner=N.runtime();runner.prepare(obs)
    existing=N.V.asset_keys(obs['farms'][seat])
    bases=[];predictions={c['id']:[] for c in chosen}
    for index in range(8):
        world=runner.world_batch.world(obs,index)
        bases.append(runner.rollout(obs,memory,None,world,step+72))
        if index==0:assert N.V.canonical(bases[-1])==candidates['baseline_prediction'], 'Saved public forecast changed'
        for c in chosen:
            route=c['route']
            if isinstance(route,list):route=(route[0],tuple(map(tuple,route[1])))
            predictions[c['id']].append(runner.rollout(obs,memory,route,world,step+72))
    balanced={c['id']:N.assess(dict(route=c['route']),predictions[c['id']],bases,existing) for c in chosen}
    runner.prepare(obs)
    runner.world_batch._world.__globals__['M'].scenario_shops=lambda o,i:{d:game['shops'][d] for d in range(step//24,30)}
    rows=[]
    for index in (0,2,4):
        world=runner.world_batch.world(obs,index)
        base=runner.rollout(obs,memory,None,world,step+72)
        for c in chosen:
            route=c['route']
            if isinstance(route,list):route=(route[0],tuple(map(tuple,route[1])))
            candidate=runner.rollout(obs,memory,route,world,step+72)
            rows.append(dict(id=c['id'],route=c['route'],world=index,donor=world['donor'],
                margin_delta=candidate['margin_gain']-base['margin_gain'],
                own_delta=candidate['cash_gain']-base['cash_gain'],
                rival_delta=candidate['rival_gain']-base['rival_gain'],baseline=base,candidate=candidate))
    means={c['id']:{field:statistics.mean(r[field] for r in rows if r['id']==c['id'])
                   for field in ('margin_delta','own_delta','rival_delta')} for c in chosen}
    A.write(A.OUT/'attribution'/f'{case}.json',dict(case=case,means=means,rows=rows,balanced_public_forecast=balanced,
        warning='Oracle future shops; fixed forecast rival trajectories and imperfect own rollout remain. This diagnoses shop uncertainty versus residual modeling error, and is not an implementable selector or causal isolation of rival modeling alone.'))
    print(json.dumps(dict(case=case,means=means)),flush=True)

if __name__=='__main__':main(sys.argv[1])

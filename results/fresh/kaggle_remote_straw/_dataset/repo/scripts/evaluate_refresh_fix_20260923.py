"""Frozen, outcome-independent fresh m1 panel for V9 and late-Yarn y2."""
from copy import deepcopy
from hashlib import sha256
import gzip
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/records_refresh_20260923'

def v9(ep):
    import value_tape_search_v9 as N
    import probe_value_tape_search as P
    g,pair=P.load(ep)
    R=N.V.R; E=R.engine(); seat=g['seat']
    ours=N.V.fresh_agent()
    chassis=ours.__globals__['_MGT_IMPL'].chassis
    native=chassis.router
    decisions=[]; timings=[]
    with R.Simulator(g) as sim:
        state=deepcopy(sim.initial)
        for t in range(719):
            sim.t=t
            sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            if t%24==0:state[0].observation.town['unlocked_shops'][:]=g['shops'][t//24]
            started=time.perf_counter()
            if t in (288,360,432):
                route,decision=N.choose(deepcopy(state[seat].observation),N.V.memory_of(ours))
                decisions.append(decision)
                (OUT/'v9'/f'{ep}-d{t//24}.json').write_text(json.dumps(decision,indent=2),encoding='utf8')
                chassis.router=native
                if route is not None:
                    def committed(obs,step,memory,route=route,until=decision['until']):
                        if step<until:
                            memory['route']=route
                            return route
                        return native(obs,step,memory)
                    chassis.router=committed
            state[seat].action=ours(deepcopy(state[seat].observation))
            timings.append(time.perf_counter()-started)
            if t<288:assert state[seat].action==pair[seat][t],('prefix',ep,t)
            state[1-seat].action=pair[1-seat][t]
            E.interpreter(state,sim.env)
        cash=[s.reward for s in state]
        econ=[R.economic(sim.events,s) for s in range(2)]
        for s in range(2):assert 3000+sum(econ[s]['revenue'].values())-sum(econ[s]['spend'].values())==cash[s]
    # A separate native replay checks the whole baseline, not just its prefix.
    state,memory=P.checkpoint(g,pair,12)
    base=P.evaluate(g,pair,state,memory,None,12)
    assert [base['cash'],base['rival_cash']]==[g['rewards'][seat],g['rewards'][1-seat]]
    row=dict(episode=ep,completed=True,selected=[d['selected'] for d in decisions],
             baseline=base,cash=cash[seat],rival_cash=cash[1-seat],margin=cash[seat]-cash[1-seat],
             margin_delta=cash[seat]-cash[1-seat]-base['margin'],cash_delta=cash[seat]-base['cash'],
             economics=econ,ledger_verified=True,baseline_verified=True,
             search_seconds=[timings[t] for t in (288,360,432)],
             measured_overage_used=sum(max(0,x-1) for x in timings))
    (OUT/'v9'/f'{ep}.json').write_text(json.dumps(row,indent=2),encoding='utf8')
    print(json.dumps({k:row[k] for k in ('episode','selected','margin_delta','cash_delta','measured_overage_used')}),flush=True)

def main():
    if len(sys.argv)>1:
        if sys.argv[1]=='v9':return v9(int(sys.argv[2]))
        import ladder_panel as L
        name,ep=sys.argv[1],int(sys.argv[2])
        L.OUT=OUT/'paired'
        result=L.run((name,str(ROOT/f'data/ladder_panel/56395605/{ep}.json.gz')))
        print(name,ep,result['margin'],flush=True)
        return
    manifest=json.loads((OUT/'manifest.json').read_text())
    ids=sorted(manifest['submissions']['56395605']['downloaded'])
    sample=sorted(random.Random(230926).sample(ids,min(8,len(ids))))
    paths=[ROOT/'agents/mgt_m1.py',ROOT/'agents/mgt_y2.py']+list((ROOT/'scripts').glob('value_tape_search*.py'))
    hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    design=dict(all_new_m1=ids,v9_sample=sample,hashes=hashes,
                protocol='Y2 on all newly fetched m1 games. V9 on 8 uniformly sampled fresh games, seed 230926, no outcome selection; three reveals D12/D15/D18. Recorded opponents cannot react. No parameter changes. Local timing is measured, not competition-enforced.')
    dp=OUT/'fix_design.json'
    if dp.exists():assert json.loads(dp.read_text())==design
    else:dp.write_text(json.dumps(design,indent=2),encoding='utf8')
    (OUT/'v9').mkdir(exist_ok=True)
    for name,eps in [('mgt_m1',ids),('mgt_y2',ids),('v9',sample)]:
        for ep in eps:
            target=(OUT/'v9'/f'{ep}.json') if name=='v9' else OUT/'paired'/name/f'{ep}.json'
            if target.exists():continue
            with (OUT/f'{name}-{ep}.log').open('w',encoding='utf8') as log:
                r=subprocess.run([sys.executable,__file__,name,str(ep)],stdout=log,stderr=log)
            if r.returncode:raise RuntimeError(f'{name} {ep} failed: inspect log')
            print('complete',name,ep,flush=True)

if __name__=='__main__':main()

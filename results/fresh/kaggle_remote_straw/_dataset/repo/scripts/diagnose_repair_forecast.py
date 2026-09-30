"""Hindsight attribution of the R1 failure, never an online selection rule."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import FunctionType

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'results/fresh/value_tape_wide_20260923_01a0'
STUDY = ROOT / 'results/fresh/tape_repair_20260924_01a0'
sys.path[:0] = [str(STUDY/'r1/payload/scripts'), str(STUDY/'r1/payload/vendor')]
import value_tape_repair_r1 as N


def replay(folder, case, spec, checkpoint=False):
    actions=json.loads((folder/f'actions/{case}-candidate.json').read_text())
    expected=json.loads((folder/f'arms/{case}-candidate.json').read_text())
    game=dict(seed=spec['seed'],seat=spec['seat'],shops=[spec['shops'][:min(8,d//3)] for d in range(31)])
    seat=spec['seat'];entry=N.V.fresh_agent() if checkpoint else None
    farms={};obs=memory=None
    with N.V.R.Simulator(game) as sim:
        state=deepcopy(sim.initial)
        for t in range(719):
            sim.t=t;sim.seats={id(f):s for s,f in enumerate(state[0].observation.farms)}
            for s in state:s.observation.step=t
            if t%24==0:
                state[0].observation.town['unlocked_shops'][:]=game['shops'][t//24]
                farms[t//24]=deepcopy(state[0].observation.farms[1-seat])
            if t==360 and checkpoint:
                obs=deepcopy(state[seat].observation);memory=N.V.memory_of(entry)
            if t<360 and checkpoint:
                assert entry(deepcopy(state[seat].observation))==actions[seat][t]
            for s in range(2):state[s].action=actions[s][t]
            N.V.R.engine().interpreter(state,sim.env)
        cash=[s.reward for s in state]
        assert cash==expected['cash_by_seat'],(cash,expected['cash_by_seat'])
        hourly=defaultdict(Counter)
        for t,s,op,item,value in sim.events:
            if t>=360 and s==1-seat and op in ('SELL','BUY_PRODUCT'):
                hourly[t][item]+=1 if op=='SELL' else -1
        return dict(obs=obs,memory=memory,farms=farms,hourly={t:dict(v) for t,v in hourly.items()},
                    shops={d:game['shops'][d] for d in range(15,30)},cash=cash)


def main():
    case='random-06-v56'
    spec=next(s for s in json.loads((STUDY/'r1/design.json').read_text())['specs'] if s['id']==case)
    baseline=replay(OLD,case,spec,True)
    actual_repaired=replay(STUDY/'r1',case,spec)
    obs,memory=baseline['obs'],baseline['memory']
    runner=N.runtime();runner.prepare(obs)
    selection=(408,((9,1,'TOMATO',13),))
    first_world=runner.world_batch.world(obs,0)
    runner.world_batch._world.__globals__['M'].scenario_shops=lambda o,i:baseline['shops']
    worlds=[('known_shops_model_'+str(i),runner.world_batch.world(obs,i)) for i in (0,2,4)]
    for label,source in [('known_baseline_trades',baseline),('known_candidate_trades',actual_repaired)]:
        worlds.append((label,dict(index=0,shops=source['shops'],farms=source['farms'],hourly=source['hourly'],donor={})))
    rows=[]
    for label,world in [('original_model_0',first_world)]+worlds:
        a=runner.rollout(obs,memory,None,world)
        b=runner.rollout(obs,memory,selection,world)
        rows.append(dict(world=label,own_delta=b['cash_gain']-a['cash_gain'],rival_delta=b['rival_gain']-a['rival_gain'],
                         margin_delta=b['margin_gain']-a['margin_gain'],
                         rival_net_units=dict(sum((Counter(v) for v in world['hourly'].values()),Counter())),
                         baseline=a,candidate=b))
        print(label,rows[-1]['own_delta'],rows[-1]['rival_delta'],rows[-1]['margin_delta'],flush=True)
    # This diagnostic crosses recorded supply schedules with simulated own play.
    # It does not assert those fixed schedules are a responsive rival policy.
    out=STUDY/'forecast_attribution.json'
    out.write_text(json.dumps(dict(case=case,protocol='Hindsight diagnosis; unavailable future inputs never enter chooser.',rows=rows),indent=2),encoding='utf-8')


if __name__=='__main__':main()

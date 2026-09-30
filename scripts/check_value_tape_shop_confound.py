"""Cross the two observed shop worlds for the already-selected live switch.

The route is the recorded public-only decision. Future shops are supplied only
to the evaluation environment, never to the selection policy or its memory.
"""
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
import json
import os
import traceback

import research_labour_profit as R
import value_tape_search as V
from benchmark_value_tape_search import OUT,OPPONENT

SEED=1329978515


def worker(job):
    world,mode,shops,route=job
    target=OUT/f'fixed-{world}-{mode}.json'
    row=dict(world=world,mode=mode,seed=SEED,seat=0,completed=False,selected_route=route,shops=shops)
    with target.with_suffix('.log').open('w',encoding='utf-8') as log:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            E=R.engine()
            from kaggle_environments.agent import get_last_callable
            ours=V.fresh_agent()
            rival=get_last_callable(OPPONENT.read_text(encoding='utf-8'),path=str(OPPONENT))
            game=dict(seed=SEED,seat=0,episode=0,shops=[[] for _ in range(31)])
            with R.Simulator(game) as sim:
                state=deepcopy(sim.initial)
                for t in range(719):
                    sim.t=t
                    sim.seats={id(f):i for i,f in enumerate(state[0].observation.farms)}
                    for s in state:s.observation.step=t
                    if t%24==0:
                        state[0].observation.town.unlocked_shops[:]=shops[:min(8,t//72)]
                    if t==360 and mode=='cohort':
                        chassis=ours.__globals__['_MGT_IMPL'].chassis
                        parent=chassis.router
                        def committed(obs,step,memory):
                            if step<432:
                                memory['route']=route
                                return route
                            return parent(obs,step,memory)
                        chassis.router=committed
                    state[0].action=ours(deepcopy(state[0].observation))
                    state[1].action=rival(deepcopy(state[1].observation))
                    E.interpreter(state,sim.env)
                money=[s.reward for s in state]
                economics=[R.economic(sim.events,s) for s in range(2)]
                for s in range(2):
                    assert 3000+sum(economics[s]['revenue'].values())-sum(economics[s]['spend'].values())==money[s]
                row.update(completed=True,cash=money[0],rival_cash=money[1],margin=money[0]-money[1],economics=economics)
        except Exception:
            row['error']=traceback.format_exc()
        finally:
            os.dup2(saved[0],1);os.dup2(saved[1],2)
            for fd in saved:os.close(fd)
    target.write_text(json.dumps(row,indent=2),encoding='utf-8')
    return row


def main():
    original={mode:json.loads((OUT/f'{SEED}-0-{mode}.json').read_text(encoding='utf-8')) for mode in ('baseline','cohort')}
    assert original['baseline']['shops'][:5]==original['cohort']['shops'][:5]
    route=original['cohort']['selected']
    jobs=[(world,mode,original[world]['shops'],route) for world in original for mode in original]
    results=[]
    with ProcessPoolExecutor(max_workers=2,max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(worker,job) for job in jobs]):
            row=future.result()
            print(json.dumps({k:row.get(k) for k in ('world','mode','completed','margin','error')}),flush=True)
            results.append(row)
    assert all(r['completed'] for r in results)
    lookup={(r['world'],r['mode']):r for r in results}
    rows=[]
    for world in original:
        base,candidate=lookup[world,'baseline'],lookup[world,'cohort']
        natural=lookup[world,world]
        assert (natural['cash'],natural['rival_cash'])==(original[world]['cash'],original[world]['rival_cash'])
        rows.append(dict(world=world,shops=original[world]['shops'],baseline_margin=base['margin'],
            candidate_margin=candidate['margin'],margin_delta=candidate['margin']-base['margin'],
            cash_delta=candidate['cash']-base['cash'],rival_delta=candidate['rival_cash']-base['rival_cash']))
    report=dict(seed=SEED,seat=0,selected_route=route,natural_diagonals_reproduced=True,rows=rows)
    (OUT/'fixed_shop_check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

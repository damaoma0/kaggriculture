"""Paired full-season checks of timed tasks and worker-position recovery."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import json
from statistics import mean
from evaluate_boards import ROOT, Ledger, module_at, observation, restored_env

OUT = ROOT / 'results/fresh/router_scheduler'


def run(job):
    seed, seat, perturbed, kind = job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    modules = [module_at('native'+str(i), ROOT/'agents/public/tschinkel_router_v31.py') for i in range(2)]
    prefix = make('kaggriculture', configuration={'seed':seed, 'episodeSteps':225})
    prefix.run([m.agent for m in modules])
    assert len(prefix.steps) == 225
    replay = prefix.toJSON()
    changes = []
    if perturbed:
        farm = replay['steps'][-1][0]['observation']['farms'][seat]
        positions = [farm['farmer'], *farm['hands']]
        # Same intervention in every paired run: move the first three workers
        # to another unlocked tile two Manhattan steps away, row-major tie.
        for i, pos in enumerate(positions[:3]):
            candidates = [(x,y) for y in range(10) for x in range(10)
                          if abs(x-pos[0])+abs(y-pos[1]) == 2 and farm['tiles'][y][x] != 'LOCKED']
            if candidates:
                old = list(pos);pos[:] = candidates[0]
                changes.append({'worker':i,'before':old,'after':list(pos)})
    env = restored_env(replay, 224, seed)
    scheduler = module_at('scheduled', ROOT/'agents/router_scheduler.py').Scheduler()
    # No branch occurs before turn 224; explicitly verify this assumption.
    assert all(m._A.cur == m.MAIN for m in modules)
    def ours(obs):
        return scheduler.act(obs) if kind == 'scheduler' else modules[seat].agent(obs)
    policies = [m.agent for m in modules];policies[seat] = ours
    with Ledger(E) as ledger:
        env.run(policies)
    assert len(env.steps)==720 and all(s['status'] in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in range(2):
        initial=replay['steps'][-1][0]['observation']['farms'][i]['money']
        assert env.state[i].reward == initial+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())
    row = {'seed':seed,'seat':seat,'perturbed':perturbed,'kind':kind,
           'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
           'changes':changes,'ledger':ledger.data[seat],'stats':scheduler.stats,
           'route':scheduler.router.cur if kind=='scheduler' else modules[seat]._A.cur}
    if seed == 93100:
        p=OUT/f'{seed}-{seat}-{int(perturbed)}-{kind}.json'
        p.write_text(json.dumps(env.toJSON()),encoding='utf-8')
    return row


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seeds',type=int,default=8);ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    paths=['agents/router_scheduler.py','agents/public/tschinkel_router_v31.py','data/router_work_orders.json','scripts/test_router_scheduler.py']
    hashes={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    mp=OUT/'manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==hashes,'Use a new output directory after changes'
    else:mp.write_text(json.dumps(hashes,indent=2))
    p=OUT/'results.json';rows=json.loads(p.read_text()) if p.exists() else []
    key=lambda r:(r['seed'],r['seat'],r['perturbed'],r['kind'])
    done={key(r) for r in rows}
    jobs=[(seed,seat,perturbed,kind) for seed in range(93100,93100+args.seeds) for seat in (0,1)
          for perturbed in (False,True) for kind in ('router','scheduler')]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs if j not in done]):
            r=f.result();rows.append(r)
            tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(rows,indent=2));tmp.replace(p)
            print(len(rows),'/',len(jobs),key(r),r['cash'],dict(r['stats']),flush=True)
    indexed={key(r):r for r in rows}
    for perturb in (False,True):
        deltas=[indexed[(s,i,perturb,'scheduler')]['cash']-indexed[(s,i,perturb,'router')]['cash']
                for s in range(93100,93100+args.seeds) for i in (0,1)]
        print('perturbed',perturb,'mean delta',mean(deltas),'range',min(deltas),max(deltas))


if __name__=='__main__':main()

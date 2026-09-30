"""Paired full-season checks of timed tasks and worker-position recovery."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import json
from statistics import mean
from evaluate_boards import ROOT, Ledger, module_at, observation, restored_env

OUT = ROOT / 'results/fresh/router_task_repair_final'
SCENARIOS=[(224,'normal'),(224,'permuted')]+[(d*24+h,'displaced') for d in (9,16,26) for h in (8,16,20)]


def run(job):
    seed, seat, perturbed, kind, checkpoint = job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    modules = [module_at('native'+str(i), ROOT/'agents/public/tschinkel_router_v31.py') for i in range(2)]
    prefix = make('kaggriculture', configuration={'seed':seed, 'episodeSteps':checkpoint+1})
    prefix.run([m.agent for m in modules])
    assert len(prefix.steps) == checkpoint+1
    replay = prefix.toJSON()
    changes = []
    if perturbed=='displaced':
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
    elif perturbed=='permuted':
        farm=replay['steps'][-1][0]['observation']['farms'][seat]
        positions=[farm['farmer'],*farm['hands']]
        # Reverse positions within equal-inventory groups, keeping inventory
        # attached to its original worker. Asset state remains unchanged.
        groups={}
        for i,inv in enumerate(replay['steps'][-1][seat]['observation']['private']['inventories']):
            groups.setdefault(tuple(sorted((k,v) for k,v in inv.items() if v)),[]).append(i)
        for indices in groups.values():
            old=[list(positions[i]) for i in indices]
            for i,new in zip(indices,reversed(old)):
                if positions[i]!=new:changes.append({'worker':i,'before':list(positions[i]),'after':new})
                positions[i][:]=new
    env = restored_env(replay, checkpoint, seed)
    scheduler = module_at('scheduled', ROOT/('agents/router_task_repair.py' if kind=='repair' else 'agents/router_allocator.py')).Scheduler()
    scheduler.router=modules[seat]._A
    farm_ids={};production=[Counter(),Counter()]
    def ours(obs):
        farm_ids.clear()
        return scheduler.act(obs) if kind != 'router' else modules[seat].agent(obs)
    policies = [m.agent for m in modules];policies[seat] = ours
    original=E._apply_unit_action
    def audit(f,p,i,action,*args):
        # Source routes sometimes contain commands for hands not hired in
        # this game. The engine ignores them; the observer must do likewise.
        if i>len(f['hands']):return original(f,p,i,action,*args)
        ident=farm_ids.setdefault(id(f),len(farm_ids))
        assert ident<2
        pos=f['farmer'] if i==0 else f['hands'][i-1]
        x,y=pos;tile=f['tiles'][y][x]
        watered=bool(isinstance(tile,dict) and tile.get('watered_today'))
        before=dict(p['inventories'][i])
        result=original(f,p,i,action,*args)
        if action[0]=='WATER' and not watered and isinstance(f['tiles'][y][x],dict) and f['tiles'][y][x].get('watered_today'):
            production[ident]['water_success']+=1
        if action[0]=='HARVEST':
            for item,n in p['inventories'][i].items():
                gain=n-before.get(item,0)
                if gain>0:production[ident]['harvest:'+item]+=gain
        return result
    E._apply_unit_action=audit
    try:
        with Ledger(E) as ledger:env.run(policies)
    finally:E._apply_unit_action=original
    assert len(env.steps)==720 and all(s['status'] in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in range(2):
        initial=replay['steps'][-1][0]['observation']['farms'][i]['money']
        assert env.state[i].reward == initial+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())
    row = {'seed':seed,'seat':seat,'perturbed':perturbed,'kind':kind,'checkpoint':checkpoint,
           'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
           'changes':changes,'ledger':ledger.data[seat],'stats':scheduler.stats,'production':production[seat],
           'route':scheduler.router.cur if kind!='router' else modules[seat]._A.cur}
    if seed == 95200 and seat==0 and checkpoint==224:
        p=OUT/f'{seed}-{seat}-{perturbed}-{kind}-{checkpoint}.json'
        p.write_text(json.dumps(env.toJSON()),encoding='utf-8')
    return row


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seeds',type=int,default=4);ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    paths=['agents/router_task_repair.py','agents/router_allocator.py','agents/public/tschinkel_router_v31.py','data/router_work_orders.json','scripts/test_router_task_repair.py']
    hashes={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    mp=OUT/'manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==hashes,'Use a new output directory after changes'
    else:mp.write_text(json.dumps(hashes,indent=2))
    p=OUT/'results.json';rows=json.loads(p.read_text()) if p.exists() else []
    key=lambda r:(r['seed'],r['seat'],r['perturbed'],r['kind'],r['checkpoint'])
    done={key(r) for r in rows}
    jobs=[(seed,seat,perturbed,kind,checkpoint) for seed in range(95200,95200+args.seeds) for seat in (0,1)
          for checkpoint,perturbed in SCENARIOS
          for kind in ('router','allocator','repair')]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs if j not in done]):
            try:r=f.result()
            except BaseException as exc:
                print('EVALUATION FAILED',repr(exc),flush=True);raise
            rows.append(r)
            tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(rows,indent=2));tmp.replace(p)
            print(len(rows),'/',len(jobs),key(r),r['cash'],dict(r['stats']),flush=True)
    indexed={key(r):r for r in rows}
    for checkpoint,perturb in SCENARIOS:
        deltas=[indexed[(s,i,perturb,'repair',checkpoint)]['cash']-indexed[(s,i,perturb,'allocator',checkpoint)]['cash']
                for s in range(95200,95200+args.seeds) for i in (0,1)]
        print(checkpoint,perturb,'mean delta',mean(deltas),'range',min(deltas),max(deltas))


if __name__=='__main__':main()

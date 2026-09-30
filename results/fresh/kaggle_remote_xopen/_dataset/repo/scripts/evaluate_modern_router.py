"""Frozen development/confirmation evaluation of one modern-router candidate."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
from statistics import mean
import argparse,json,random,time
from market_corpus import ROOT,load
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit
from compare_router_refresh import PATHS as PUBLIC

OUT=ROOT/'results/fresh/modern_router'
PATHS={**PUBLIC,'baseline':ROOT/'agents/modern_router_baseline.py','candidate':ROOT/'agents/modern_router_candidate.py'}

def jobs(phase):
    if phase=='smoke':return [('smoke',137999,0,'candidate','twocoins')]
    seeds=range(137000,137004) if phase=='development' else range(138000,138008)
    rivals=('v44','farmingv5','twocoins') if phase=='development' else ('v44','v45','farmingv5','twocoins')
    return [(phase,s,i,p,o) for s in seeds for i in (0,1) for p in ('baseline','candidate') for o in rivals]

def run(job):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    phase,seed,seat,policy,opponent=job
    own=load('modern_own',PATHS[policy]);rival=load('modern_rival',PATHS[opponent])
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=random.Random(seed^0xA171).choices(sorted(E.SHOPS),k=8);original=E._end_of_day
    def end(state,environment,day):
        original(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=end
    times=[]
    def call(obs):
        start=time.perf_counter();action=own.agent(obs);times.append(time.perf_counter()-start);return action
    players=[None,None];players[seat]=call;players[1-seat]=rival.agent
    try:
        with Ledger(E) as ledger:
            with WheatAudit(E,env) as audit:env.run(players)
    finally:E._end_of_day=original
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss),(job,len(env.steps),env.logs[-2:])
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    row=dict(zip(('phase','seed','seat','policy','opponent'),job))
    row.update(cash=env.state[seat].reward,opponent_cash=env.state[1-seat].reward,margin=env.state[seat].reward-env.state[1-seat].reward,
        shops=schedule,ledger=ledger.data,wheat=audit.total,max_seconds=max(times),telemetry=getattr(own.agent,'telemetry',{}),
        chassis_diagnostics=own._IMPL.chassis.diagnostics)
    dest=OUT/'games';dest.mkdir(parents=True,exist_ok=True)
    (dest/('-'.join(map(str,job))+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8')
    return {k:row[k] for k in ('phase','seed','seat','policy','opponent','margin','max_seconds')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('smoke','development','confirmation'),required=True);args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.phase!='smoke':
        paths=set(PATHS.values())|set(PUBLIC['twocoins'].parent.glob('*.py'))|{PUBLIC['twocoins'].parent/'actions.json',PUBLIC['twocoins'].parent/'settings.json',ROOT/'agents/modern_input_overlay.py',ROOT/'scripts/evaluate_modern_router.py',ROOT/'scripts/research_wheat_economy.py'}
        manifest={'jobs':jobs('development')+jobs('confirmation'),'sources':{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
            'design':'One frozen candidate; development and independent confirmation seeds; common hidden uniform shop draws with replacement; both seats. No tuning after freezing.',
            'promotion_gate':'Confirmation: positive mean paired margin; nonnegative mean paired margin against each rival; positive seed-averaged paired margin on at least 6 of 8 seeds; no fewer total wins than baseline; mean own-cash delta >= -500; no nonzero error/fallback counters; max observed call < 1 second. Otherwise retain exact V45 baseline locally. Never submit automatically.'}
        path=OUT/'manifest.json'
        if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
        else:path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs(args.phase) if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()

"""Shop-stratified discovery and fresh-seed confirmation of opening hybrids."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter
from hashlib import sha256
from statistics import mean
import argparse,json,random,time
from market_corpus import ROOT,load
from compare_router_refresh import PATHS as PUBLIC
from evaluate_boards import Ledger
from research_wheat_economy import WheatAudit

OUT=ROOT/'results/fresh/leader_hybrids'
PATHS={**PUBLIC,'baseline':ROOT/'agents/v45_event_candidate.py',**{m:ROOT/f'agents/v45_leader_{m}.py' for m in ('berries','herd','both')}}
def jobs(phase):
    if phase=='smoke':return [(phase,149998,0,p,'v45') for p in ('baseline','berries','herd','both')]
    if phase=='screen':return [(phase,s,i,p,o) for s in range(149000,149008) for i in (0,1) for p in ('baseline','berries','herd','both') for o in ('v45','twocoins')]
    selected=json.loads((OUT/'discovery_selection.json').read_text(encoding='utf-8'))['candidate']
    return [(phase,s,i,p,o) for s in range(150000,150008) for i in (0,1) for p in ('baseline',selected) for o in ('v45','twocoins','farmingv5')]

def run(job):
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    phase,seed,seat,policy,opponent=job
    own=load('opening_own',PATHS[policy]);rival=load('opening_rival',PATHS[opponent])
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    schedule=random.Random(seed^0xA171).choices(sorted(E.SHOPS),k=8)
    if phase=='screen':schedule[0]=sorted(E.SHOPS)[seed-149000]
    original=E._end_of_day
    def end(state,environment,day):
        original(state,environment,day);shops=state[0].observation.town.unlocked_shops;shops[:]=schedule[:len(shops)]
    E._end_of_day=end;snapshots=[];times=[]
    def call(obs):
        if obs['step'] in (24,72,144,192,288):
            farm=obs['farms'][seat];tiles=[t for row in farm['tiles'] for t in row if isinstance(t,dict)]
            snapshots.append(dict(step=obs['step'],cash=farm['money'],crops=dict(Counter(t['crop'] for t in tiles if t.get('crop'))),
                animals=dict(Counter(t['animal'] for t in tiles if t.get('animal'))),
                berries=[dict(x=x,y=y,birth=t['planted_day']) for y,row in enumerate(farm['tiles']) for x,t in enumerate(row) if isinstance(t,dict) and t.get('crop')=='STRAWBERRY']))
        start=time.perf_counter();a=own.agent(obs);times.append(time.perf_counter()-start);return a
    players=[None,None];players[seat]=call;players[1-seat]=rival.agent
    try:
        with Ledger(E) as ledger:
            with WheatAudit(E,env) as wheat:env.run(players)
    finally:E._end_of_day=original
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    row=dict(zip(('phase','seed','seat','policy','opponent'),job))
    row.update(cash=env.state[seat].reward,opponent_cash=env.state[1-seat].reward,margin=env.state[seat].reward-env.state[1-seat].reward,
        shops=schedule,ledger=ledger.data,wheat=wheat.total,max_seconds=max(times),telemetry=getattr(own.agent,'telemetry',{}),chassis_diagnostics=own._IMPL.chassis.diagnostics,snapshots=snapshots)
    dest=OUT/'games';dest.mkdir(parents=True,exist_ok=True);(dest/('-'.join(map(str,job))+'.json')).write_text(json.dumps(row,indent=2),encoding='utf-8')
    return {k:row[k] for k in ('phase','seed','seat','policy','opponent','margin','max_seconds','snapshots')}

def select():
    rows=[json.loads((OUT/'games'/('-'.join(map(str,j))+'.json')).read_text(encoding='utf-8')) for j in jobs('screen')]
    base={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['policy']=='baseline'}
    scores={p:mean(r['margin']-base[r['seed'],r['seat'],r['opponent']]['margin'] for r in rows if r['policy']==p) for p in ('berries','herd','both')}
    chosen=max(scores,key=scores.get);result=dict(candidate=chosen,screen_margin_gain=scores,criterion='Highest paired mean margin on eight first-shop coverage seeds; confirmation remains unseen.')
    path=OUT/'discovery_selection.json'
    if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==result
    else:path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('smoke','screen','select','confirmation'),required=True);a=parser.parse_args()
    if a.phase=='select':select();return
    OUT.mkdir(parents=True,exist_ok=True)
    if a.phase!='smoke':
        paths=set(PATHS.values())|set(PATHS['twocoins'].parent.glob('*.py'))|{PATHS['twocoins'].parent/'actions.json',PATHS['twocoins'].parent/'settings.json',ROOT/'agents/leader_opening_overlay.py',ROOT/'scripts/build_leader_hybrids.py',ROOT/'scripts/evaluate_leader_hybrids.py'}
        manifest=dict(sources={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},screen_jobs=jobs('screen'),confirmation_seeds=list(range(150000,150008)),
            design='Three frozen mechanism hybrids on submitted V45 event candidate. Eight forced first shops, both seats, two rivals for discovery. Best mean margin advances to eight fresh natural-frequency shop seeds, both seats, three rivals. No prefix splice or leader source reconstruction.',
            gate='Positive confirmation margin, nonnegative per rival, >=6/8 positive seed averages, no fewer wins, cash delta>=-500, zero execution errors/fallbacks, max call<1s. No automatic submission.')
        path=OUT/'manifest.json'
        if path.exists():assert json.loads(path.read_text(encoding='utf-8'))==json.loads(json.dumps(manifest))
        else:path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    pending=[j for j in jobs(a.phase) if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=8,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(json.dumps(f.result()),flush=True)

if __name__=='__main__':main()

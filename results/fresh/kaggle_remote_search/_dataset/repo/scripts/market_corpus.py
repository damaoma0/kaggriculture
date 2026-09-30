"""Public-state market corpus and locally verified opponent comparisons."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from hashlib import sha256
import importlib.util,json,sys
from evaluate_boards import ROOT,observation

OUT=ROOT/'results/fresh/market_research'
PATHS={'old':ROOT/'agents/public/tschinkel_router_v31.py',
       'sixday':ROOT/'data/public_candidates/thomastschinkel/extracted/main.py',
       'pasture':ROOT/'data/public_candidates/indarkarhana/extracted/agents/e776a_engine_exact_latent_pasture.py'}

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

def run(job):
    seed,seat,opponent=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    mods=[None,None];mods[seat]=load('corpus_old',PATHS['old']);mods[1-seat]=load('corpus_opp',PATHS[opponent])
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    trades=[];step=[0];old=E._commit_unit
    def commit(op,item,price,f,p,market,cap):
        before=p['shed'].get(item,0);ok=old(op,item,price,f,p,market,cap)
        if ok and op in ('SELL','BUY_PRODUCT'):
            trades.append([step[0],op,item,price])
        return ok
    # Preserve per-player attribution by wrapping the interpreter's market
    # unit commits with the money reference? Instead save aggregate trades;
    # forecasts use only shared inventory and observed town, never private data.
    def wrap(i):
        def act(o):step[0]=o['step'];return mods[i].agent(o)
        return act
    E._commit_unit=commit
    try:env.run([wrap(0),wrap(1)])
    finally:E._commit_unit=old
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    market=[{'inventory':ss[0].observation.market.inventory,'prices':ss[0].observation.market.prices,
             'shops':ss[0].observation.town.unlocked_shops} for ss in env.steps]
    checkpoints={str(t):observation(env.steps[t],seat) for t in range(216,697,24)}
    signatures=[sha256(json.dumps([ss[i].action for ss in env.steps[1:]],sort_keys=True).encode()).hexdigest() for i in range(2)]
    row={'seed':seed,'seat':seat,'opponent':opponent,'cash':env.state[seat].reward,'opponent_cash':env.state[1-seat].reward,
         'market':market,'checkpoints':checkpoints,'action_hashes':signatures,'trades':trades}
    path=OUT/'corpus'/f'{seed}-{seat}-{opponent}.json';path.write_text(json.dumps(row),encoding='utf-8')
    if seed==97000 and seat==0:(OUT/f'replay-{opponent}.json').write_text(json.dumps(env.toJSON()),encoding='utf-8')
    return {k:row[k] for k in ('seed','seat','opponent','cash','opponent_cash','action_hashes')}

def main():
    (OUT/'corpus').mkdir(parents=True,exist_ok=True)
    manifest={'engine':'installed kaggriculture; default configuration','splits':{'train':list(range(97000,97004)),'test':list(range(97004,97008))},
              'training_opponent':'sixday','held_out_family':'pasture',
              'sources':{k:{'path':str(p),'sha256':sha256(p.read_bytes()).hexdigest()} for k,p in PATHS.items()},
              'excluded':'Adaptive Route V2 contains a Linux .so without accompanying implementation source in its archive; not executed on Windows.'}
    (OUT/'corpus_manifest.json').write_text(json.dumps(manifest,indent=2))
    jobs=[(s,i,o) for s in range(97000,97008) for i in (0,1) for o in ('sixday','pasture')]
    p=OUT/'corpus_summary.json';rows=json.loads(p.read_text()) if p.exists() else []
    done={(r['seed'],r['seat'],r['opponent']) for r in rows}
    with ProcessPoolExecutor(max_workers=4,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in jobs if j not in done]):
            r=f.result();rows.append(r);p.write_text(json.dumps(rows,indent=2));print(len(rows),r,flush=True)

if __name__=='__main__':main()

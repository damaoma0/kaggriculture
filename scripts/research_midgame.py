"""Checkpointed, natural-shop midgame research with independent scenario splits."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean
from evaluate_boards import ROOT,Ledger,module_at,observation,restored_env,continuation

OUT=ROOT/'results/fresh/midgame'


def root_job(seed):
    from kaggle_environments import make
    a=module_at('ra',ROOT/'agents/public/tschinkel_router_v31.py')
    b=module_at('rb',ROOT/'agents/public/tschinkel_router_v31.py')
    env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':217})
    env.run([a.agent,b.agent])
    assert len(env.steps)==217
    replay=env.toJSON()
    p=OUT/'roots'/f'{seed}.json';p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(replay),encoding='utf-8')
    shops=replay['steps'][-1][0]['observation']['town']['unlocked_shops']
    return {'seed':seed,'path':str(p),'shops':shops,'yarn': 'YARN_STORE' in shops,'sha256':sha256(p.read_bytes()).hexdigest()}


def make_roots(workers):
    plan=OUT/'splits.json'
    if plan.exists():print('Frozen splits already exist');return
    splits={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for name,start,count in (('train',90100,16),('validate',91100,8),('test',92100,16)):
            bins={False:[],True:[]};seed=start
            while min(map(len,bins.values()))<count//2:
                for r in pool.map(root_job,range(seed,seed+12)):
                    if len(bins[r['yarn']])<count//2:bins[r['yarn']].append(r)
                seed+=12
            splits[name]=bins[False]+bins[True]
            print(name,len(splits[name]),'roots',flush=True)
    plan.write_text(json.dumps({'splits':splits,'selection':'Equal day-9 YARN_STORE presence/absence; only observed root shops used. Natural engine RNG and same seed continued throughout.'},indent=2),encoding='utf-8')


def run(job):
    name,cfg,root,seat,opponent,end_day,save=job
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    replay=json.loads(Path(root['path']).read_text())
    assert sha256(Path(root['path']).read_bytes()).hexdigest()==root['sha256']
    obs=[observation(replay['steps'][-1],i) for i in range(2)]
    native=[]
    for i in range(2):
        m=module_at('native_mid'+str(i),ROOT/'agents/public/tschinkel_router_v31.py')
        for t in range(216):assert m.agent(observation(replay['steps'][t],i))==replay['steps'][t+1][i]['action']
        native.append(m)
    mod=module_at('mid_controller',ROOT/'agents/midgame_v1.py')
    def policy(kind,config,i):
        if kind=='adaptive':
            branch=config['yarn' if 'YARN_STORE' in obs[i]['town']['unlocked_shops'] else 'other']
            return policy(branch['name'],branch['config'],i)
        if kind=='router':return native[i].agent
        if kind=='no-branches':
            native[i].DECISIONS=()
            return native[i].agent
        if kind=='legacy':return continuation('replant',10,obs[i],E)
        instance=mod.Midgame(obs[i],config)
        def call(o):return instance(o)
        return call
    ours=policy(name,cfg,seat)
    theirs=policy(opponent,{},1-seat)
    end_instances=[None,None]
    projecting=[False];real_farms={};real_private={};audit_step=[None]
    def wrap(p,i):
        def call(o):
            if audit_step[0]!=o['step']:
                audit_step[0]=o['step'];real_farms.clear();real_private.clear()
            projecting[0]=True
            try:
                if end_day is not None and o['day']>=end_day:
                    if end_instances[i] is None:end_instances[i]=mod.Midgame(o,{'replant':None,'extra_cows':0,'extra_sheep':0,'fertilizer':'sell','hands_cap':14})
                    return end_instances[i](o)
                return p(o)
            finally:projecting[0]=False
        return call
    policies=[None,None];policies[seat]=wrap(ours,seat);policies[1-seat]=wrap(theirs,1-seat)
    env=restored_env(replay,216,root['seed'])
    diagnostics=[Counter(),Counter()]
    originals={k:getattr(E,k) for k in ('_apply_unit_action','_drop_inventories_to_shed')}
    def apply(f,p,i,a,*args):
        before=(deepcopy(f),deepcopy(p)) if not projecting[0] else None
        result=originals['_apply_unit_action'](f,p,i,a,*args)
        # The new controller also projects unit actions. Count real engine
        # objects only, excluding policy-owned copies.
        if not projecting[0] and id(f) not in real_farms:
            real_farms[id(f)]=len(real_farms);real_private[id(p)]=real_farms[id(f)]
        ident=real_farms.get(id(f)) if not projecting[0] else None
        if ident is not None:
            op=a[0];diagnostics[ident]['actions:'+op]+=1
            if op not in ('PASS','NORTH','SOUTH','EAST','WEST') and before==(f,p):diagnostics[ident]['no_effect:'+op]+=1
        return result
    def drop(p,cap):
        before=sum(p['shed'].values())+sum(sum(v.values()) for v in p['inventories'])
        result=originals['_drop_inventories_to_shed'](p,cap)
        ident=real_private.get(id(p))
        if ident is not None:diagnostics[ident]['night_overflow']+=before-sum(p['shed'].values())-sum(sum(v.values()) for v in p['inventories'])
        return result
    # Transition-based audit below is always on; detailed action hooks are
    # enabled only for saved audit replays, to avoid slowing the grid.
    if save:E._apply_unit_action=apply;E._drop_inventories_to_shed=drop
    try:
        with Ledger(E) as ledger:env.run(policies)
    finally:
        for k,v in originals.items():setattr(E,k,v)
    assert len(env.steps)==720 and all(s['status'] in ('ACTIVE','DONE') for ss in env.steps for s in ss)
    cash=[s.reward for s in env.state]
    for i in range(2):assert cash[i]==obs[i]['farms'][i]['money']+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())
    for before,after in zip(env.steps[216:],env.steps[217:]):
        for i in range(2):
            for y in range(10):
                for x in range(10):
                    a=before[0].observation.farms[i]['tiles'][y][x];b=after[0].observation.farms[i]['tiles'][y][x]
                    if not isinstance(a,dict):continue
                    if a.get('animal') and not (isinstance(b,dict) and b.get('animal')):diagnostics[i]['animal_losses']+=1
                    if a.get('kind')=='PLANT' and isinstance(b,dict) and b.get('kind')=='WEED':
                        cd=E.CROPS[a['crop']]
                        expiry=a['planted_day']+(cd['first_yield_day']+3*cd['interval'] if cd['ongoing'] else cd['max_yield_day'])
                        if before[0].observation.day<expiry:diagnostics[i]['premature_crop_losses']+=1
    r={'name':name,'config':cfg,'seed':root['seed'],'shops':root['shops'],'yarn':root['yarn'],'seat':seat,'opponent':opponent,'end_day':end_day,'cash':cash[seat],'opponent_cash':cash[1-seat],'margin':cash[seat]-cash[1-seat],'ledger':ledger.data,'diagnostics':diagnostics}
    if save:
        p=Path(save);p.mkdir(parents=True,exist_ok=True)
        (p/'replay.json').write_text(json.dumps(env.toJSON()),encoding='utf-8')
        (p/'summary.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    return r


def configs(stage):
    controls={'router':{},'no-branches':{},'legacy':{}}
    if stage.startswith('audit'):return dict(controls,**{'service-10':{'hands_cap':10},'service-14':{'hands_cap':14},'service-18':{'hands_cap':18}})
    if stage=='train':
        result=dict(controls)
        for herd in ('none','cows','sheep'):
            for hands in (10,14):
                for fert in ('sell','apply'):
                    result[f'{herd}-h{hands}-{fert}']={'extra_cows':4 if herd=='cows' else 0,'extra_sheep':4 if herd=='sheep' else 0,'hands_cap':hands,'fertilizer':fert}
        return result
    if stage=='refine':return json.loads((OUT/'refinements.json').read_text())
    if stage in ('test','endgame'):
        picked=json.loads((OUT/'selection.json').read_text())
        return dict(controls,**{picked['name']:picked['config']})
    picked=json.loads((OUT/'shortlist.json').read_text())
    return dict(controls,**picked)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=('roots','audit','audit2','train','refine','validate','test','endgame'),required=True);ap.add_argument('--workers',type=int,default=8)
    args=ap.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if args.stage=='roots':make_roots(args.workers);return
    splits=json.loads((OUT/'splits.json').read_text())['splits']
    cs=configs(args.stage)
    roots=splits['train'] if args.stage in ('audit','audit2','train','refine') else splits['validate'] if args.stage in ('validate','endgame') else splits['test']
    if args.stage.startswith('audit'):roots=[roots[0],roots[1],roots[8],roots[9]]
    if args.stage=='endgame':roots=[roots[0],roots[1],roots[4],roots[5]]
    jobs=[]
    for n,c in cs.items():
        for k,root in enumerate(roots):
            for seat in ((k%2,) if args.stage in ('audit','audit2','train','refine') else (0,1)):
                for opponent in (('router','legacy') if args.stage in ('validate','test') else ('router',)):
                    for end_day in ((22,24,26) if args.stage=='endgame' else (None,)):
                        save=str(OUT/f'{args.stage}-{n}-{root["seed"]}-seat{seat}-{opponent}-{end_day}') if args.stage.startswith('audit') or args.stage=='test' and k==0 and opponent=='router' else None
                        jobs.append((n,c,root,seat,opponent,end_day,save))
    p=OUT/f'{args.stage}.json';rows=json.loads(p.read_text()) if p.exists() else []
    key=lambda r:(r['name'],r['seed'],r['seat'],r['opponent'],r['end_day'])
    done={key(r) for r in rows};pending=[j for j in jobs if (j[0],j[2]['seed'],j[3],j[4],j[5]) not in done]
    manifest={'jobs':jobs,'hashes':{str(f):sha256((ROOT/f).read_bytes()).hexdigest() for f in ('agents/midgame_v1.py','scripts/research_midgame.py','scripts/evaluate_boards.py','agents/public/tschinkel_router_v31.py')}}
    mp=OUT/f'{args.stage}-manifest.json'
    if mp.exists():assert json.loads(mp.read_text())==json.loads(json.dumps(manifest)),'Source or scenario changed; use a separate stage result'
    else:mp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Resume',len(rows),'pending',len(pending),flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):
            r=f.result();rows.append(r)
            tmp=p.with_suffix('.json.tmp');tmp.write_text(json.dumps(rows,indent=2),encoding='utf-8');tmp.replace(p)
            print(len(rows),'/',len(jobs),r['name'],r['seed'],r['seat'],r['opponent'],r['margin'],r['diagnostics'][r['seat']].get('premature_crop_losses',0),flush=True)
    for n in sorted(cs,key=lambda n:-mean(r['margin'] for r in rows if r['name']==n)):
        g=[r for r in rows if r['name']==n]
        print(n,'cash',round(mean(r['cash'] for r in g)),'margin',round(mean(r['margin'] for r in g)),'crop losses',mean(r['diagnostics'][r['seat']].get('premature_crop_losses',0) for r in g))


if __name__=='__main__':main()

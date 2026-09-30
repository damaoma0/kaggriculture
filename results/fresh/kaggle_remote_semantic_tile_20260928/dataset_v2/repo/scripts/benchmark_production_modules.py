"""Paired full-farm evaluation of frozen MGT production-module candidates.

Uses actual Kaggle loading, active opponents, natural RNG (or a recorded ladder
opponent for a separately labelled diagnostic). Each game runs in a fresh process.
"""
import argparse
import json
from pathlib import Path
from hashlib import sha256
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter,defaultdict
from statistics import mean
import random

ROOT=Path(__file__).resolve().parents[1]
OPPONENTS={'v50':ROOT/'agents/v50_public.py','v48':ROOT/'agents/v48_public.py',
           'twocoins':ROOT/'data/router_refresh_20260916/twocoins/main.py'}


def run(job):
    name,seed,seat,opponent,outpath=job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    code=(ROOT/'agents'/f'{name}.py').read_text(encoding='utf-8')
    oppcode=OPPONENTS[opponent].read_text(encoding='utf-8')
    codehash=sha256(code.encode()).hexdigest();opphash=sha256(oppcode.encode()).hexdigest()
    dest=Path(outpath)/f'{name}-{opponent}-{seed}-{seat}.json'
    old=None
    if dest.exists():
        old=json.loads(dest.read_text(encoding='utf-8'))
        if old.get('sha256')==codehash and old.get('opponent_sha256')==opphash and old.get('event_schema')==2:return old
    entry=get_last_callable(code,path=str(ROOT/'agents'/f'{name}.py'))
    opp=get_last_callable(oppcode,path=str(OPPONENTS[opponent]))
    events=[];oldinstrument=TV.instrument;observed_step=[0]
    def instrument(E,physical,seats,active,step):
        unit,work=oldinstrument(E,physical,seats,active,step)
        def wrapped(farm,private,idx,action,*args,**kwargs):
            target=active[0] and seats.get(id(farm))==seat and 11*24<=observed_step[0]<26*24 and action and action[0] in ('PLANT','HARVEST','FERTILIZE')
            pos=E._farmer_position(farm,idx) if target else None
            before=farm['tiles'][pos[1]][pos[0]] if pos else None
            beforecrop=before.get('crop') if isinstance(before,dict) else None
            inv=dict(private['inventories'][idx]) if target and idx<len(private['inventories']) else {}
            result=work(farm,private,idx,action,*args,**kwargs)
            if pos:
                after=farm['tiles'][pos[1]][pos[0]]
                delta={k:v-inv.get(k,0)for k,v in private['inventories'][idx].items() if v-inv.get(k,0)>0} if idx<len(private['inventories'])else{}
                events.append(dict(step=observed_step[0],unit=idx,tile=pos,command=action,before=beforecrop,
                                   after=after.get('crop') if isinstance(after,dict)else None,produced=delta))
            return result
        return unit,wrapped
    TV.instrument=instrument
    def ours(obs,t):
        observed_step[0]=t
        return entry(obs)
    player=[None,None];player[seat]=ours;player[1-seat]=lambda obs,t:opp(obs)
    env=make('kaggriculture',configuration={'episodeSteps':720},info={'seed':seed})
    result=TV._play(E,env,player,seat,None,None,None,seat)
    a=result['daily'][seat][-1];b=result['daily'][1-seat][-1]
    G=entry.__globals__
    actions=json.dumps(result['actions'],sort_keys=True,separators=(',',':')).encode()
    row=dict(agent=name,seed=seed,seat=seat,opponent=opponent,sha256=codehash,opponent_sha256=opphash,
             cash=result['final'][seat],opponent_cash=result['final'][1-seat],margin=result['final'][seat]-result['final'][1-seat],
             action_sha256=sha256(actions).hexdigest(),ledger={k:a[k]for k in ('revenue','spend','sold_units')},physical=a['physical'],
             opponent_physical=b['physical'],daily_cash=[d['money']for d in result['daily'][seat]],
             telemetry=G.get('_MPM_REPORT',{}),native_telemetry={k:v for k,v in G.get('_SHP_REPORT',{}).items() if isinstance(v,(int,float))},
             events=events,event_schema=2,shops=env.state[0].observation.town.unlocked_shops,
             statuses=[s.status for s in env.state],actions=len(result['actions']))
    if old and old.get('sha256')==codehash and old.get('opponent_sha256')==opphash:
        assert all(row[k]==old[k] for k in ('cash','opponent_cash','action_sha256')), 'Trace-only replay changed outcomes'
    dest.write_text(json.dumps(row,indent=2,default=str),encoding='utf-8')
    return row


def report(rows,out):
    base={(r['seed'],r['seat'],r['opponent']):r for r in rows if r['agent']=='mgt_m1'}
    groups=defaultdict(list)
    for r in rows:
        if r['agent']!='mgt_m1':groups[r['agent']].append(r)
    summary={}
    for name,rs in groups.items():
        pairs=[(r,base[(r['seed'],r['seat'],r['opponent'])])for r in rs]
        deltas=[r['margin']-b['margin']for r,b in pairs]
        cl=defaultdict(list)
        for r,b in pairs:cl[r['seed']].append(r['margin']-b['margin'])
        values=[mean(x)for x in cl.values()];rng=random.Random(172)
        boot=sorted(mean(rng.choices(values,k=len(values)))for _ in range(5000)) if values else[]
        counts=Counter()
        for r in rs:
            for k,v in r['telemetry'].items():
                if isinstance(v,(int,float)):counts[k]+=v
        summary[name]=dict(games=len(pairs),wins=sum(r['margin']>0 for r in rs),
            mean_cash_delta=mean(r['cash']-b['cash']for r,b in pairs),mean_margin_delta=mean(deltas),
            better=sum(x>0 for x in deltas),worse=sum(x<0 for x in deltas),equal=sum(x==0 for x in deltas),
            same_actions=sum(r['action_sha256']==b['action_sha256']for r,b in pairs),
            same_shops=sum(r['shops']==b['shops']for r,b in pairs),telemetry=dict(counts),
            seed_clusters=len(values),seed_cluster_bootstrap_95=[boot[125],boot[4874]]if boot else[],
            opponents={o:dict(games=sum(r['opponent']==o for r in rs),margin_delta=mean(r['margin']-b['margin']for r,b in pairs if r['opponent']==o))for o in sorted({r['opponent']for r in rs})})
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('--agents',default='mgt_m1,mgt_pm_forced,mgt_pm_value,mgt_pm_pin');p.add_argument('--seeds',default='172000,172001,172002,172003');p.add_argument('--opponents',default='v50,v48');p.add_argument('--out',default='results/fresh/production_modules/integration');p.add_argument('--workers',type=int,default=3)
    a=p.parse_args();out=ROOT/a.out;out.mkdir(parents=True,exist_ok=True)
    jobs=[(n,int(seed),seat,o,str(out))for n in a.agents.split(',')for seed in a.seeds.split(',')for seat in (0,1)for o in a.opponents.split(',')]
    manifest=dict(agents={n:sha256((ROOT/'agents'/f'{n}.py').read_bytes()).hexdigest()for n in a.agents.split(',')},seeds=a.seeds,opponents=a.opponents,jobs=len(jobs),design='Natural RNG, active opponents, both seats; no hidden future shops')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    rows=[]
    with ProcessPoolExecutor(max_workers=a.workers,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j)for j in jobs]):
            r=f.result();rows.append(r);print(json.dumps({k:r[k]for k in ('agent','seed','seat','opponent','margin')}),flush=True)
    report(rows,out)


if __name__=='__main__':main()

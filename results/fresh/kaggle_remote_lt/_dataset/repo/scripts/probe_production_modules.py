"""Full-engine feasibility probe of independently routed recorded crop modules.

This is an isolated execution test: four free plots and the main farmer are
reserved. Results are not full-farm profit comparisons or leaderboard forecasts.
"""
import json
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/production_modules/probe'


def normalize(m):
    ops=[];seen=set()
    for e in m['events']:
        if not e['executed']:continue
        key=(e['step'],tuple(e['command']))
        if key in seen:continue
        seen.add(key)
        ops.append(dict(day=e['day_offset'],command=e['command']))
    return dict(crop=m['crop'],events=ops,expected_harvest=m['verified_harvest_units'],
                source=dict(leader=m['leader'],submission=m['submission'],episode=m['episode'],tile=m['tile'],planting_day=m['plantingDay']))


def build():
    raw=json.loads((OUT.parent/'extracted.json').read_text(encoding='utf-8'))['modules']
    selected={}
    for leader in ('UMG56266758','Majkel56216119'):
        pool=[m for m in raw if m['leader']==leader and 12<=m['plantingDay']<=21 and m['harvest_verified']]
        pool.sort(key=lambda m:(m['crop']!='CARROT',m['duration_days'],m['episode'],m['plantingStep']))
        assert len(pool)>=2,(leader,len(pool))
        selected[leader]=[normalize(x) for x in pool[:2]]
    a=selected['UMG56266758'];b=selected['Majkel56216119']
    configs={'umg':a+a,'majkel':b+b,'mixed':a+b}
    template=(ROOT/'scripts/fragments/production_module_agent.py').read_text(encoding='utf-8')
    OUT.mkdir(parents=True,exist_ok=True)
    for name,modules in configs.items():
        code=template.replace('PM_MODULES = []  # populated by the experiment builder','PM_MODULES = '+repr(modules))
        (OUT/f'{name}.py').write_text(code,encoding='utf-8')
    return configs


def run(job):
    name,seed,seat=job
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    code=(OUT/f'{name}.py').read_text(encoding='utf-8')
    agent=get_last_callable(code,path=str(OUT/f'{name}.py'))
    opppath=ROOT/'agents/v50_public.py'
    opp=get_last_callable(opppath.read_text(encoding='utf-8'),path=str(opppath))
    tile_audit={str(tuple(p)):dict(plants=0,harvest=0) for p in agent.__globals__['PM_TILES']}
    instrument=TV.instrument
    def detailed(E,physical,seats,active,step):
        unit,work=instrument(E,physical,seats,active,step)
        def wrapped(farm,private,idx,action,*args,**kwargs):
            target=active[0] and seats.get(id(farm))==seat
            pos=E._farmer_position(farm,idx) if target else None
            key=str(tuple(pos)) if pos else ''
            before=farm['tiles'][pos[1]][pos[0]] if pos else None
            inv=dict(private['inventories'][idx]) if target and idx<len(private['inventories']) else {}
            result=work(farm,private,idx,action,*args,**kwargs)
            if key in tile_audit and action:
                after=farm['tiles'][pos[1]][pos[0]]
                if action[0]=='PLANT' and before is None and isinstance(after,dict) and after.get('crop'):
                    tile_audit[key]['plants']+=1
                if action[0]=='HARVEST' and idx<len(private['inventories']):
                    tile_audit[key]['harvest']+=sum(max(0,v-inv.get(k,0))for k,v in private['inventories'][idx].items())
            return result
        return unit,wrapped
    TV.instrument=detailed
    players=[None,None];players[seat]=lambda obs,t:agent(obs);players[1-seat]=lambda obs,t:opp(obs)
    env=make('kaggriculture',configuration={'episodeSteps':720},info={'seed':seed})
    res=TV._play(E,env,players,seat,None,None,None,seat)
    final=res['daily'][seat][-1];physical=final['physical'];G=agent.__globals__
    expected=Counter()
    for m in G['PM_MODULES']:expected[m['crop']]+=m['expected_harvest']
    actual={crop:physical.get('produced:'+crop,0) for crop in expected}
    report=G['PM_REPORT']
    tile_pass=all(tile_audit[str(tuple(G['PM_TILES'][i]))]==dict(plants=1,harvest=m['expected_harvest']) for i,m in enumerate(G['PM_MODULES']))
    out=dict(config=name,seed=seed,seat=seat,expected=dict(expected),actual=actual,
             successful_plants={k:v for k,v in physical.items() if k.startswith('planted:')},
             cash=final['money'],spend=final['spend'],revenue=final['revenue'],report=report,
             missing_workers=physical.get('missing_worker_commands',0),
             per_tile=tile_audit,per_tile_passed=tile_pass,
             source_sha256=sha256(code.encode()).hexdigest(),opponent_sha256=sha256(opppath.read_bytes()).hexdigest(),
             passed=tile_pass and actual==dict(expected) and not report['rejections'] and not report['missing_inputs'])
    (OUT/f'{name}-{seed}-{seat}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    return out


def main():
    configs=build()
    seeds=[171000,171001,171002,171003]
    jobs=[(n,seed,seat)for n in configs for seed in seeds for seat in (0,1)]
    rows=[]
    with ProcessPoolExecutor(max_workers=3,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j)for j in jobs]):
            r=f.result();rows.append(r);print(json.dumps({k:r[k]for k in ('config','seed','seat','passed','expected','actual')}),flush=True)
    summary=dict(design='Isolated four-plot production execution; free farmer; natural RNG; active V50 opponent; no full-farm performance claim',
                 seeds=seeds,games=len(rows),passed=sum(r['passed'] for r in rows),modules=configs,
                 results=rows)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('PASSED',summary['passed'],'/',len(rows))


if __name__=='__main__':main()

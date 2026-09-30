"""Exact daily farm counts from fresh records, alongside cached DSM farm counts."""
from collections import Counter
import gzip
import json
from pathlib import Path
import statistics as S
import research_labour_profit as R

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/fresh/records_refresh_20260923/farm_comparison'
PRODUCTS=('STRAWBERRY','SHEEP','COW')

def audit(sub,ep):
    dest=OUT/f'{ep}.json'
    if dest.exists():
        cached=json.loads(dest.read_text())
        if cached.get('version')==2:return cached
    with gzip.open(ROOT/f'data/ladder_panel/{sub}/{ep}.json.gz','rt',encoding='utf8') as f:g=json.load(f)
    seat=g['seat'];pair=[None,None];pair[seat]=g['our_actions'];pair[1-seat]=g['opp_actions']
    daily={};service=[Counter(),Counter()]
    E=R.engine()
    with R.Simulator(g) as sim:
        old=E.interpreter
        old_refresh=E._daily_refresh_animals
        def refresh(farm,day):
            side=sim.seats[id(farm)]
            idx=0 if side==seat else 1
            for row in farm['tiles']:
                for tile in row:
                    if isinstance(tile,dict) and tile.get('animal') in ('SHEEP','COW'):
                        a=tile['animal'];service[idx][a+'_days']+=1
                        service[idx][a+'_fed']+=bool(tile.get('fed_today'))
                        service[idx][a+'_cared']+=bool(tile.get('cared_today') and tile.get('fed_today'))
            return old_refresh(farm,day)
        def step(state,env):
            t=sim.t
            farms=state[0].observation.farms
            if t%24==0:
                counts=[]
                for s in (seat,1-seat):
                    c=Counter()
                    for row in farms[s]['tiles']:
                        for tile in row:
                            if isinstance(tile,dict):
                                if tile.get('crop'):c[tile['crop']]+=1
                                if tile.get('animal'):c[tile['animal']]+=1
                    counts.append(dict(c))
                daily[str(t//24)]=counts
            return old(state,env)
        E.interpreter=step
        E._daily_refresh_animals=refresh
        try:r=sim.run(sim.initial,0,719,pair)
        finally:
            E.interpreter=old
            E._daily_refresh_animals=old_refresh
    assert r['money']==g['rewards']
    result=dict(version=2,episode=ep,submission=sub,margin=g['rewards'][seat]-g['rewards'][1-seat],daily=daily,service=service,
                shops=g['shops'][29])
    dest.write_text(json.dumps(result),encoding='utf8')
    return result

def main():
    OUT.mkdir(exist_ok=True)
    manifest=json.loads((OUT.parent/'manifest.json').read_text())
    rows=[]
    for sub,st in manifest['submissions'].items():
        for ep in st['downloaded']:
            rows.append(audit(sub,ep))
    leaders=json.loads((ROOT/'results/fresh/newphase_20260923/leader_response/dsm_cache.json').read_text())
    dsm=[r['per_farm'][str(s)]['day_counts'] for r in leaders.values() for s in r['dsm_indices']]
    summary=dict(leader_farm_observations=len(dsm),groups={})
    for label,rs in [('all',rows),('m1',[r for r in rows if r['submission']=='56395605']),('losses',[r for r in rows if r['margin']<0])]:
        daily={str(day):{p:[S.mean(r['daily'][str(day)][s].get(p,0) for r in rs) for s in (0,1)]+[S.mean(r[day].get(p,0) for r in dsm)] for p in PRODUCTS} for day in (6,7,9,12,15,18,21,24)}
        audits=[json.loads((OUT.parent/'audits'/f"{r['episode']}.json").read_text()) for r in rs]
        output={p:[S.mean(a['sides'][s]['sales'].get(p,0) for a in audits) for s in (0,1)] for p in ('STRAWBERRY','WOOL','MILK')}
        service={p:[dict(days=sum(r['service'][s].get(p+'_days',0) for r in rs),
                             fed=sum(r['service'][s].get(p+'_fed',0) for r in rs),
                             cared=sum(r['service'][s].get(p+'_cared',0) for r in rs)) for s in (0,1)] for p in ('SHEEP','COW')}
        summary['groups'][label]=dict(n=len(rs),daily=daily,sold_units=output,service=service)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()

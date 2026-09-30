"""Exact recorded-action economic audit, both seats; no policy modifications."""
import sys, json, gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if sys.prefix != str(ROOT/'.venv'):
    sys.path.insert(0,str(ROOT/'.venv/Lib/site-packages'))
from collections import Counter
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor, as_completed
from research_labour_profit import Simulator, engine, economic
OUT=ROOT/'results/fresh/all_umg_m1/losses'

def run(path):
    with gzip.open(path,'rt',encoding='utf8') as f:g=json.load(f)
    eid=g['episode']; dest=OUT/f'{eid}.json'
    if dest.exists() and json.loads(dest.read_text(encoding='utf8')).get('version')==3:return eid,'cached'
    s=g['seat']; E=engine(); actions=[None,None];actions[s]=g['our_actions'];actions[1-s]=g['opp_actions']
    produced=[[Counter() for _ in range(30)] for _ in range(2)]
    low=[[Counter() for _ in range(30)] for _ in range(2)]
    dead=[Counter(),Counter()]; commands=[Counter(),Counter()];pricedays=[]
    feed=[Counter(),Counter()]; planted=[Counter(),Counter()]; consumed=[Counter(),Counter()]
    with Simulator(g) as sim:
        old=E._apply_unit_action; interp=E.interpreter; current=[None]
        def inter(state,env):
            current[0]=state[0].observation
            if sim.t%24==0: pricedays.append(dict(day=sim.t//24,shops=list(current[0].town.unlocked_shops),prices={p:E.market_price(p,current[0].market['inventory'][p]) for p in E.PRODUCTS}))
            return interp(state,env)
        def unit(farm,private,idx,action,*args,**kwargs):
            seat=sim.seats[id(farm)];op=action[0] if action else 'PASS';commands[seat][op]+=1
            if idx>=len(private['inventories']):dead[seat]['missing_worker']+=1;return old(farm,private,idx,action,*args,**kwargs)
            pos=E._farmer_position(farm,idx)
            b=deepcopy(private['inventories'][idx]); seeds=dict(private['seeds']); tile=deepcopy(farm['tiles'][pos[1]][pos[0]]) if pos else None
            result=old(farm,private,idx,action,*args,**kwargs);a=private['inventories'][idx]
            if op in ('HARVEST','COLLECT_FERTILIZER'):
                for p in E.PRODUCTS:
                    n=a.get(p,0)-b.get(p,0)
                    if n>0:
                        produced[seat][sim.t//24][p]+=n
                        if E.market_price(p,current[0].market['inventory'][p])<=E.MARKET_PARAMS[p]['base']/4:low[seat][sim.t//24][p]+=n
            if op=='FEED':
                used=b.get('WHEAT',0)-a.get('WHEAT',0);feed[seat][sim.t//24]+=used;consumed[seat]['WHEAT']+=used
            if op=='FERTILIZE':consumed[seat]['FERTILIZER']+=b.get('FERTILIZER',0)-a.get('FERTILIZER',0)
            if op=='PLANT':
                for p in E.CROPS: planted[seat][p]+=max(0,seeds.get(p,0)-private['seeds'].get(p,0))
            if op in ('PLANT','HARVEST','WATER','CARE','FEED','FERTILIZE','COLLECT_FERTILIZER','DIG') and b==a and seeds==private['seeds'] and tile==(farm['tiles'][pos[1]][pos[0]] if pos else None):dead[seat][op]+=1
            return result
        E._apply_unit_action=unit; E.interpreter=inter
        try:r=sim.run(sim.initial,0,719,actions)
        finally:E._apply_unit_action=old;E.interpreter=interp
        assert r['money']==g['rewards'],(eid,r['money'],g['rewards'])
        econ=[economic(r['events'],i) for i in range(2)]
        for i in range(2): assert 3000+sum(econ[i]['revenue'].values())-sum(econ[i]['spend'].values())==r['money'][i]
        rows=[]; daily=[]
        for p in E.PRODUCTS:
            sides=[]
            for i in (s,1-s):
                sales=[ev for ev in r['events'] if ev[1]==i and ev[2]=='SELL' and ev[3]==p]
                private=r['state'][i].observation.private
                side=dict(produced=sum(d[p] for d in produced[i]),sold=len(sales),revenue=sum(ev[4] for ev in sales),
                    avg_price=sum(ev[4] for ev in sales)/len(sales) if sales else None,
                    low_sales=sum(ev[4]<=E.MARKET_PARAMS[p]['base']/4 for ev in sales),floor_sales=sum(ev[4]==1 for ev in sales),
                    low_harvest=sum(d[p] for d in low[i]),remaining=sum(inv.get(p,0) for inv in [private.shed,*private.inventories]),
                    bought=sum(ev[1]==i and ev[2]=='BUY_PRODUCT' and ev[3]==p for ev in r['events']),consumed=consumed[i][p])
                side['discarded']=side['produced']+side['bought']-side['sold']-side['consumed']-side['remaining']
                assert side['discarded']>=0,(eid,i,p,side)
                sides.append(side)
            a,b=sides;pa=a['avg_price'] if a['avg_price'] is not None else b['avg_price'] or 0;pb=b['avg_price'] if b['avg_price'] is not None else pa
            q=(a['sold']-b['sold'])*(pa+pb)/2; price=(pa-pb)*(a['sold']+b['sold'])/2
            assert abs(q+price-a['revenue']+b['revenue'])<1e-6
            rows.append(dict(product=p,base=E.MARKET_PARAMS[p]['base'],ours=a,opponent=b,revenue_gap=a['revenue']-b['revenue'],quantity_component=q,price_component=price))
            for day in range(30):
                values=[]
                for i in(s,1-s):
                    sales=[ev for ev in r['events'] if ev[0]//24==day and ev[1]==i and ev[2]=='SELL' and ev[3]==p]
                    values.extend([produced[i][day][p],len(sales),sum(ev[4] for ev in sales),low[i][day][p]])
                daily.append(dict(day=day,product=p,opening_price=pricedays[day]['prices'][p],shops=pricedays[day]['shops'],values=values))
        hires=[]
        for seat in(s,1-s):
            asked=sum(order[0]=='HIRE' for action in actions[seat] for order in (action.get('market') or [])[:10] if isinstance(order,list) and order)
            got=sum(ev[1]==seat and ev[2]=='HIRE' for ev in r['events'])
            hires.append(dict(requested=asked,successful=got,failed=asked-got))
        doc=dict(version=3,episode=eid,seed=g['seed'],seat=s,opponent=g.get('opponent'),names=g.get('names'),created=g.get('created'),rewards=g['rewards'],margin=r['money'][s]-r['money'][1-s],products=rows,daily=daily,hires=hires,
            economies=[econ[s],econ[1-s]],commands=[commands[s],commands[1-s]],no_effect=[dead[s],dead[1-s]],planted=[planted[s],planted[1-s]],feed=[feed[s],feed[1-s]],shops=g['shops'],validated=True)
        OUT.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(doc),encoding='utf8')
    return eid,'ok'

if __name__=='__main__':
    paths=[]
    for p in (ROOT/'data/ladder_panel/56395605').glob('*.json.gz'):
        with gzip.open(p,'rt',encoding='utf8') as f:g=json.load(f)
        if g['rewards'][g['seat']]<g['rewards'][1-g['seat']]: paths.append(p)
    print('losses available',len(paths),flush=True)
    with ProcessPoolExecutor(max_workers=3) as pool:
        for n,f in enumerate(as_completed([pool.submit(run,p) for p in paths]),1):
            print(n,len(paths),f.result(),flush=True)

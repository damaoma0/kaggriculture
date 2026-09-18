"""Audit an actual ladder replay with exact engine reproduction and cash ledgers."""
from collections import Counter
from copy import deepcopy
import json
from market_corpus import ROOT,load
from evaluate_boards import Ledger,observation

OUT=ROOT/'results/fresh/qq_farming'

def main(episode=109609580, out=None):
    global OUT
    if out is not None:OUT=ROOT/out
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    r=json.loads((OUT/f'episode-{episode}-replay.json').read_text())
    env=make('kaggriculture',configuration=r['configuration'],info={'seed':r['info']['seed']})
    model=load('qq_submitted',ROOT/'agents/market_impact_selected.py')
    parity=[]
    for t in range(719):
        if model.agent(observation(r['steps'][t],0))!=r['steps'][t+1][0]['action']:parity.append(t)
    t=[0];trades=[];physical=[];cash_daily=[];unit_seat=[-1,-1]
    unit=E._apply_unit_action
    def apply(f,p,i,a,*args,**kwargs):
        if unit_seat[0]!=t[0]:unit_seat[:]=[t[0],-1]
        if i==0:unit_seat[1]+=1
        seat=unit_seat[1]
        assert seat in (0,1)
        pos=E._farmer_position(f,i)
        before=deepcopy(p['inventories'][i]) if i<len(p['inventories']) else {}
        tile=deepcopy(f['tiles'][pos[1]][pos[0]]) if pos else None
        result=unit(f,p,i,a,*args,**kwargs)
        after=p['inventories'][i] if i<len(p['inventories']) else {}
        delta={k:after.get(k,0)-before.get(k,0) for k in set(before)|set(after) if after.get(k,0)!=before.get(k,0)}
        if a[0] not in E.FARMER_MOVES and a[0]!='PASS':physical.append({'step':t[0],'seat':seat,'worker':i,'action':a,'pos':pos,'tile':tile,'delta':delta})
        return result
    def player(i):
        def act(o):t[0]=o['step'];return deepcopy(r['steps'][t[0]+1][i]['action'])
        return act
    E._apply_unit_action=apply
    try:
        with Ledger(E) as ledger:
            commit=E._commit_unit
            def trade(op,item,price,f,p,m,cap=100):
                ok=commit(op,item,price,f,p,m,cap)
                if ok:trades.append({'step':t[0],'seat':ledger.seats[id(f)],'op':op,'item':item,'price':price})
                return ok
            E._commit_unit=trade
            env.run([player(0),player(1)])
    finally:E._apply_unit_action=unit
    assert len(env.steps)==720
    mismatches=[]
    for step,(actual,expected) in enumerate(zip(env.steps,r['steps'])):
        for seat in (0,1):
            for field in ('farms','market','town','private'):
                if actual[seat].observation[field]!=expected[seat]['observation'][field]:mismatches.append([step,seat,field])
    if mismatches:
        (OUT/'reproduction_mismatches.json').write_text(json.dumps(mismatches));raise AssertionError(mismatches[:10])
    for i in (0,1):assert 3000+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==r['steps'][-1][i]['reward']
    for step in list(range(0,720,24))+[719]:
        obs=r['steps'][step][0]['observation'];row={'step':step,'cash':[f['money'] for f in obs['farms']],'shops':obs['town']['unlocked_shops'],'prices':obs['market']['prices'],'farms':[]}
        for i,f in enumerate(obs['farms']):
            tiles=[v for line in f['tiles'] for v in line if isinstance(v,dict)]
            row['farms'].append({'animals':Counter(v['animal'] for v in tiles if v.get('animal')),'crops':Counter(v['crop'] for v in tiles if v.get('crop')),'land':len(f['unlocked_quadrants']),'shed':r['steps'][step][i]['observation']['private']['shed']})
        cash_daily.append(row)
    summary={'episode':episode,'seed':r['info']['seed'],'rewards':r['rewards'],'parity_mismatches':parity,'reproduced_states':720,'ledger':ledger.data,'daily':cash_daily,
      'physical_counts':[{op:sum(x['seat']==i and x['action'][0]==op for x in physical) for op in sorted({x['action'][0] for x in physical})} for i in (0,1)],
      'harvested':[{item:sum(max(0,x['delta'].get(item,0)) for x in physical if x['seat']==i and x['action'][0] in ('HARVEST','COLLECT_FERTILIZER')) for item in E.PRODUCTS} for i in (0,1)]}
    (OUT/'audit.json').write_text(json.dumps(summary,indent=2));(OUT/'trades.json').write_text(json.dumps(trades));(OUT/'physical.json').write_text(json.dumps(physical))
    print(json.dumps({k:v for k,v in summary.items() if k!='daily'},indent=2))

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--episode',type=int,default=109609580);ap.add_argument('--out');args=ap.parse_args()
    main(args.episode,args.out)

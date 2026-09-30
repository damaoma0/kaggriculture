"""Paired, one-purchase counterfactuals; research only, no submission changes."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
from statistics import mean
import argparse,json,random,time
from market_corpus import ROOT,PATHS,load
from evaluate_boards import Ledger

OUT=ROOT/'results/fresh/demand_investment'
SELECTED=ROOT/'agents/market_impact_selected.py'

class Investment:
    def __init__(self,router,choice):
        self.router=router;self.choice=choice;self.carrier=None;self.target=None
        self.decision=None;self.events=[]

    def agent(self,o):
        # Rebuild the existing adapter after changing physical actions.
        a=self.router._reference_agent(o);t=o['step'];f=o['farms'][o['player']];p=o['private']
        E=self.router._policy_scope['E']
        if t==265:
            buys=[x for x in a['market'] if x[0]=='BUY_ANIMAL']
            assert buys==[['BUY_ANIMAL','SHEEP',1]],buys
            assert not any(v.get(s,0) for v in [p['shed'],*p['inventories']] for s in ('COW','SHEEP'))
            features={'cash':f['money'],'milk_price':o['market']['prices']['MILK'],'wool_price':o['market']['prices']['WOOL']}
            for product in ('MILK','WOOL'):
                features[product+'_demand']=sum(2 if len(E.SHOPS[s])==1 else 1 for s in o['town']['unlocked_shops'] if product in E.SHOPS[s])
                for side in (0,1):
                    features[product+('_own' if side==o['player'] else '_rival')]=sum(E.ANIMALS[tile['animal']]['product']==product for row in o['farms'][side]['tiles'] for tile in row if isinstance(tile,dict) and tile.get('animal'))
            features['demand_balance']=features['MILK_demand']-features['WOOL_demand']
            features['price_balance']=features['milk_price']-features['wool_price']
            self.decision={'features':features,'shops':list(o['town']['unlocked_shops']),'choice':self.choice}
            if self.choice=='SKIP':a['market'].remove(buys[0])
            else:buys[0][1]=self.choice
        acts=[a['farmer'],*a['hands']]
        if t>265 and self.decision:
            for i,act in enumerate(acts):
                pos=self.router._farmer_position(f,i)
                if pos is None:continue
                if self.target is None:
                    if act[:2]==['PICKUP','SHEEP'] and self.carrier is None:
                        self.carrier=i;self.events.append([t,'pickup',i,p['shed'].get(self.choice,0)])
                        if self.choice=='SKIP':act[:]=['PASS']
                        else:act[1]=self.choice
                    elif act[:2]==['PLACE','SHEEP'] and self.carrier==i:
                        self.target=tuple(pos);self.events.append([t,'place',i,list(pos),p['inventories'][i].get(self.choice,0)])
                        if self.choice=='SKIP':act[:]=['PASS']
                        else:act[1]=self.choice
                if self.choice=='SKIP' and self.target==tuple(pos) and act[0] in ('FEED','CARE'):act[:]=['PASS']
        _,pp=self.router._policy_scope['project'](o,a)
        for item in ('MILK','WOOL'):
            planned=sum(int(x[2]) for x in a['market'] if x[0]=='SELL' and x[1]==item)
            extra=pp['shed'].get(item,0)-planned
            if extra>0:
                existing=next((x for x in a['market'] if x[0]=='SELL' and x[1]==item),None)
                if existing is not None:existing[2]+=extra
                elif len(a['market'])<10:a['market'].append(['SELL',item,extra])
        a['market'].sort(key=lambda x:0 if x[0]=='SELL' and x[1] in ('MILK','WOOL') else 1)
        if t>=216:
            positions=[i for i,x in enumerate(a['market']) if x[0]=='SELL'];orders=[a['market'][i] for i in positions]
            def score(x):
                q=min(int(x[2]),pp['shed'].get(x[1],0))
                return self.router._policy_scope['priority_value'](x[1],o['market']['inventory'][x[1]],q,q,o['market'].get('params'))
            for i,x in zip(positions,sorted(orders,key=lambda x:-score(x))):a['market'][i]=x
        return a

def run(job):
    panel,seed,seat,opponent,choice=job
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    own=load('demand_own',SELECTED);other=load('demand_other',SELECTED if opponent=='selected' else PATHS[opponent])
    policy=Investment(own,choice);env=make('kaggriculture',configuration={'seed':seed,'episodeSteps':720})
    initial=[f.money for f in env.state[0].observation.farms]
    schedule=random.Random(seed^0xE31A).choices(sorted(E.SHOPS),k=8)
    if panel=='train':schedule[0]=sorted(E.SHOPS)[seed-129000]
    if panel=='stress':
        kind=(seed-131000)%4
        allowed=[s for s in sorted(E.SHOPS) if (kind!=0 or 'WOOL' not in E.SHOPS[s]) and (kind!=1 or 'MILK' not in E.SHOPS[s]) and (kind!=2 or not {'MILK','WOOL'}.intersection(E.SHOPS[s]))]
        schedule=random.Random(seed).choices(allowed,k=8)
        if kind==3:schedule=[sorted(E.SHOPS)[(seed-131000)//4]]*8
    end=E._end_of_day
    def controlled(state,environment,day):
        end(state,environment,day);revealed=state[0].observation.town.unlocked_shops;revealed[:]=schedule[:len(revealed)]
    E._end_of_day=controlled
    parity=load('demand_parity',SELECTED) if choice=='SHEEP' else None
    elapsed=[]
    def act(o):
        start=time.perf_counter();a=policy.agent(o);elapsed.append(time.perf_counter()-start)
        if parity:assert a==parity.agent(o),('adapter mismatch',o['step'])
        return a
    def rival(o):return other.agent(o)
    agents=[None,None];agents[seat]=act;agents[1-seat]=rival
    try:
        with Ledger(E) as ledger:env.run(agents)
    finally:E._end_of_day=end
    assert len(env.steps)==720 and all(s.status in ('ACTIVE','DONE') for ss in env.steps for s in ss), (len(env.steps),env.logs[-3:])
    assert policy.decision and policy.target and len(policy.events)==2,policy.events
    if choice!='SKIP':assert policy.events[0][-1]>=1 and policy.events[1][-1]>=1,policy.events
    for i in (0,1):assert initial[i]+sum(ledger.data[i]['revenue'].values())-sum(ledger.data[i]['spend'].values())==env.state[i].reward
    row=dict(zip(('panel','seed','seat','opponent','choice'),job))
    row.update(cash=env.state[seat].reward,opponent_cash=env.state[1-seat].reward,margin=env.state[seat].reward-env.state[1-seat].reward,decision=policy.decision,events=policy.events,ledger=ledger.data,shops=schedule,max_seconds=max(elapsed),parity_turns=719 if parity else 0)
    (OUT/'games'/('-'.join(map(str,job))+'.json')).write_text(json.dumps(row,indent=2))
    return {k:row[k] for k in ('panel','seed','seat','opponent','choice','margin')}

def jobs(panel):
    seeds=range(129000,129008) if panel=='train' else range(130000,130008) if panel=='test' else range(131000,131008)
    opponents=('selected','sixday') if panel=='test' else ('selected',)
    return [(panel,s,i,o,c) for s in seeds for i in (0,1) for o in opponents for c in ('SHEEP','COW','SKIP')]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('panel',choices=('train','test','stress'));ap.add_argument('--workers',type=int,default=8);args=ap.parse_args()
    (OUT/'games').mkdir(parents=True,exist_ok=True)
    pending=[j for j in jobs(args.panel) if not (OUT/'games'/('-'.join(map(str,j))+'.json')).exists()]
    with ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run,j) for j in pending]):print(f.result(),flush=True)

if __name__=='__main__':main()

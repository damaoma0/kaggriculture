"""Research-only causal market ordering. Never reads opponent private state."""
from collections import deque,Counter
from copy import deepcopy
from opponent_sales import DeliveryModel,project,E
from market_forecast import consumption


def execute_trade(item,inventory,quantity,buy=False,params=None):
    cash=0
    for _ in range(quantity):
        if buy:
            inventory-=1;cash-=E.market_price(item,inventory,params)
        else:
            price=E.market_price(item,inventory,params);cash+=price;inventory+=price>1
    return cash,inventory


def priority_value(item,inventory,ours,theirs,params=None):
    """Margin advantage of our whole lot before, versus after, the rival's.

    Rival flow is signed: positive means selling, negative means buying.
    Interpolate adjacent integer quantities rather than dropping small forecasts.
    This is a ranking heuristic, not a model of rival order positions.
    """
    def value(q):
        buy=q<0;n=abs(q)
        a,end=execute_trade(item,inventory,ours,params=params)
        b,_=execute_trade(item,end,n,buy,params)
        d,end=execute_trade(item,inventory,n,buy,params)
        c,_=execute_trade(item,end,ours,params=params)
        return (a-b)-(c-d)
    q=max(-100,min(100,theirs));low=int(q//1);fraction=q-low
    return (1-fraction)*value(low)+fraction*value(low+1)


class FlowModel:
    def __init__(self):
        self.previous=None;self.private=None;self.history=deque(maxlen=96);self.stats=Counter()

    def observe(self,obs):
        if self.previous is None:return
        old=self.previous;t=old['step'];night=(t+1)%24==0
        ambiguous=night and sum(obs['private']['shed'].values())>=100
        record={'step':t,'net':{}}
        for item in E.PRODUCTS:
            drain=consumption(t,old['town']['unlocked_shops'],item)
            before=old['market']['inventory'][item]
            after=obs['market']['inventory'][item]+drain
            # Check pre-consumption inventory too: prices may hit $1 during
            # market trading then recover in the town-consumption phase.
            known=not ambiguous and E.market_price(item,before,old['market'].get('params'))>1 and E.market_price(item,after,old['market'].get('params'))>1
            own=self.private['shed'].get(item,0)-obs['private']['shed'].get(item,0)
            if night:own+=sum(v.get(item,0) for v in self.private['inventories'])
            record['net'][item]=max(-100,min(100,after-before-own)) if known else None
            self.stats['known' if known else 'ambiguous']+=1
        self.history.append(record)

    def predict(self,step):
        result={}
        for item in E.PRODUCTS:
            all_values=[r['net'][item] for r in self.history if r['net'][item] is not None]
            same=[r['net'][item] for r in self.history if r['step']%24==step%24 and r['net'][item] is not None]
            rate=sum(all_values)/max(1,len(all_values))
            result[item]=(sum(same)+rate)/(len(same)+1)
        return result

    def commit(self,obs,private):
        self.previous={'step':obs['step'],'town':deepcopy(obs['town']),'market':deepcopy(obs['market'])}
        self.private=deepcopy(private)


class AdaptiveOrder:
    def __init__(self,base,mode='fixed'):
        self.base=base;self.mode=mode;self.flow=FlowModel();self.visible=DeliveryModel()
        self.stats=Counter();self.decisions=[];self.inferred=[]

    def agent(self,obs):
        self.flow.observe(obs)
        if self.flow.history:self.inferred.append(self.flow.history[-1])
        if self.mode=='visible':self.visible.observe(obs)
        action=self.base.agent(obs);farm,private=project(obs,action)
        self.flow.commit(obs,private)
        if self.mode=='visible':self.visible.commit(obs,private)
        if self.mode=='fixed' or obs['step']<216:return action
        positions=[i for i,o in enumerate(action['market']) if o[0]=='SELL']
        if len(positions)<2:return action
        self.stats['opportunities']+=1
        forecast=self.flow.predict(obs['step'])
        if self.mode=='visible':
            _,predicted=self.visible.predict(obs,0,'visible')
            forecast.update({p:q[0] for p,q in predicted.items()})
        orders=[action['market'][i] for i in positions];scores=[]
        for order in orders:
            item=order[1];q=min(int(order[2]),private['shed'].get(item,0))
            other=q if self.mode=='static' else forecast[item]
            scores.append(priority_value(item,obs['market']['inventory'][item],q,other,obs['market'].get('params')))
        ranked=sorted(range(len(orders)),key=lambda i:-scores[i])
        if ranked!=list(range(len(orders))):
            self.stats['reordered_turns']+=1
            self.decisions.append({'step':obs['step'],'before':orders,'after':[orders[i] for i in ranked],
              'scores':scores,'forecast':forecast})
            for position,i in zip(positions,ranked):action['market'][position]=orders[i]
        return action

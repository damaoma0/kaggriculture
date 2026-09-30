"""Short continuation probes execute the complete live agent, including overlays."""
from collections import Counter
from copy import deepcopy
from coherent_switch_v7 import MarketGuardPolicy, make_policy as previous_policy
from coherent_opening_policy import load_entry, ROOT

MEMORY_KEYS=('_SHP_STATES','_MGT_IGNORE','_MGT_HISTORY','_MGT_REPORT','_SHP_REPORT')


class CompleteShadow:
    def __init__(self, owner):
        self.owner=owner
        self.entry=load_entry(ROOT/'agents/mgt_dsm_a.py')
        self.ns=self.entry.__globals__
        for key in ('_MGT_TAPES','_MGT_ACTIONS','_MGT_CFG','_MGT_ROUTES'):
            self.ns[key]=owner.ns[key]
        self.chassis=self.ns['_MGT_IMPL'].chassis
        self.chassis.routes=owner.chassis.routes
        self.chassis._future_sells=owner.chassis._future_sells
        self.chassis.router=lambda obs,step,state:self.select(state)

    def select(self,state):
        state['route']=self.owner.shadow_route
        return self.owner.shadow_route

    @property
    def players(self):return self.chassis.players

    @players.setter
    def players(self,value):
        self.chassis.players=value
        for key in MEMORY_KEYS:
            target=self.ns[key]
            target.clear()
            if isinstance(target,list):target.extend(deepcopy(self.owner.ns[key]))
            else:target.update(deepcopy(self.owner.ns[key]))

    def act(self,obs):
        action=self.entry(obs)
        step=int(obs['step'])
        if step>=144:return action
        upcoming=self.chassis.routes[self.owner.shadow_route][step+1]
        commands=[upcoming.get('farmer') or ['PASS'],*(upcoming.get('hands') or [])]
        required=Counter(c[1] for c in commands if c and c[0]=='PLANT')
        private=self.owner.after_work(obs,action)
        market=[list(o) for o in action.get('market',[]) if o and o[0]!='BUY_SEED']
        for crop,n in required.items():
            quantity=max(0,n-private['seeds'].get(crop,0))
            if quantity:
                market=[o for o in market if len(o)<3 or o[2]>0]
                if len(market)<10:market.append(['BUY_SEED',crop,quantity])
        return dict(action,market=market)


class CompleteGuardPolicy(MarketGuardPolicy):
    def __init__(self):
        super().__init__()
        self.shadow=CompleteShadow(self)

    def __call__(self,obs,configuration=None):
        action=super().__call__(obs,configuration)
        for label,chassis in [('live',self.chassis),('shadow',self.shadow.chassis)]:
            for key,n in chassis.diagnostics.items():self.stats[label+'_'+key]=n
        return action


def make_policy(arm):
    if arm=='complete_guard':return CompleteGuardPolicy()
    return previous_policy(arm)

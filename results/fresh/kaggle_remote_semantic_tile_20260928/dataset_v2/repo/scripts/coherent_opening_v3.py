"""Causal input procurement for the shared leader opening.

Day-zero wheat is a feed input. Buy it before its scheduled pickup rather than
replaying the donor's speculative buy/sell churn. Fixed-price seeds are retried
before a scheduled planting if a previous purchase failed in our actual game.
"""
from collections import Counter
from copy import deepcopy
import coherent_opening_policy as B
import coherent_opening_v2 as V2

_raw_load=B._load_traces
_traces=None
def cached_traces():
    global _traces
    if _traces is None:_traces=_raw_load()
    return _traces
B._load_traces=cached_traces
V2._load_traces=cached_traces


class InputPolicy(V2.OpeningPolicy):
    def __init__(self):
        super().__init__(latest=True,sales=False)
        self.projector=B.Projection()

    def after_work(self,obs,action):
        farm=deepcopy(obs['farms'][int(obs['player'])]);private=deepcopy(obs['private'])
        commands=[action.get('farmer') or ['PASS'],*(action.get('hands') or [])]
        demand=Counter(c[1] for c in commands if c and c[0]=='PLANT')
        blocked={crop for crop,n in demand.items() if n>private['seeds'].get(crop,0)}
        for index,cmd in enumerate(commands):
            if cmd and cmd[0]=='PLANT' and cmd[1] in blocked:continue
            self.projector.namespace['_apply_unit_action'](farm,private,index,cmd,10,int(obs['day']),24,100)
        return private

    def __call__(self,obs,configuration=None):
        action=super().__call__(obs,configuration)
        step=int(obs['step'])
        if step>=144:return action
        route=self._route(obs);tape=self.chassis.routes[route]
        upcoming=tape[step+1]
        commands=[upcoming.get('farmer') or ['PASS'],*(upcoming.get('hands') or [])]
        private=self.after_work(obs,action)
        original=action.get('market',[])
        market=[list(o) for o in original if o]
        changes=[]
        if step<24:
            # No wheat crop can mature during day zero: every sale here is
            # reselling bought feed. Preserve only the feed pickup deadlines.
            market=[o for o in market if not(len(o)>=3 and o[1]=='WHEAT' and o[0] in ('SELL','BUY_PRODUCT'))]
            need=sum(int(c[2]) if len(c)>2 else 1 for c in commands if c and c[0]=='PICKUP' and c[1]=='WHEAT')
            quantity=max(0,need-private['shed'].get('WHEAT',0))
            if quantity:
                # Replace a zero order to respect the ten-order limit.
                market=[o for o in market if len(o)<3 or o[2]>0]
                if len(market)<10:market.append(['BUY_PRODUCT','WHEAT',quantity])
            if market!=original:changes.append(['day0_feed_procurement',quantity])
        needs=Counter(c[1] for c in commands if c and c[0]=='PLANT')
        for crop,required in needs.items():
            purchases=sum(o[2] for o in market if len(o)>=3 and o[:2]==['BUY_SEED',crop])
            extra=max(0,required-private['seeds'].get(crop,0)-purchases)
            if not extra:continue
            existing=next((o for o in market if o[:2]==['BUY_SEED',crop]),None)
            if existing:existing[2]+=extra
            else:
                market=[o for o in market if len(o)<3 or o[2]>0]
                if len(market)>=10:continue
                market.append(['BUY_SEED',crop,extra])
            changes.append(['seed_deadline_topup',crop,extra])
        if changes:
            self.stats['input_interventions']+=1
            self.history.append(dict(event='inputs',step=step,route=route,changes=changes))
            return dict(action,market=market)
        return action


def make_policy(arm):
    if arm=='latest_jit':return InputPolicy()
    return V2.make_policy(arm)

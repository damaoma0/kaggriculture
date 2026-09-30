"""Fund imminent input deadlines while retaining the recorded physical jobs."""
from collections import Counter
import json
import gzip
from coherent_opening_v3 import InputPolicy,make_policy as previous_policy
from coherent_opening_policy import OUT,normalised_actions


class DeadlinePolicy(InputPolicy):
    def __init__(self,bank=False):
        super().__init__()
        if bank:
            folder=OUT/'new_sources/traces'
            index=json.loads((folder/'index.json').read_text())
            for row in index:
                with gzip.open(folder/row['path'],'rt',encoding='utf-8') as handle:trace=json.load(handle)
                if trace['team']!='DSM':continue
                route=len(self.ns['_MGT_TAPES']);actions=normalised_actions(trace['actions'],trace)
                boards=[self.ns['_mgt_board'](d['farm']) for d in trace['daily'][:30]];shops=trace['shops_by_day'][-1]
                offset=len(self.ns['_MGT_ACTIONS']);self.ns['_MGT_ACTIONS'].extend(actions)
                self.ns['_MGT_TAPES'].append(dict(ep=trace['episode'],ids=list(range(offset,offset+719)),boards=boards,shops=shops,
                    lab=[self.ns['_mgt_labels'](b) for b in boards],vec=[self.ns['_mgt_vec'](shops,j) for j in range(9)]))
                self.chassis.routes[route]=actions;self.ns['_MGT_ROUTES'][route]=actions;self.references[route]=trace
            self.chassis._future_sells.clear()

    def __call__(self,obs,configuration=None):
        action=super().__call__(obs,configuration)
        step=int(obs['step'])
        if step>=144:return action
        route=self._route(obs);upcoming=self.chassis.routes[route][step+1]
        commands=[upcoming.get('farmer') or ['PASS'],*(upcoming.get('hands') or [])]
        required=Counter(c[1] for c in commands if c and c[0]=='PLANT')
        private=self.after_work(obs,action)
        market=[list(o) for o in action.get('market',[]) if o and o[0]!='BUY_SEED']
        purchases=[]
        for crop,n in required.items():
            q=max(0,n-private['seeds'].get(crop,0))
            if q:
                market=[o for o in market if len(o)<3 or o[2]>0]
                if len(market)<10:market.append(['BUY_SEED',crop,q]);purchases.append([crop,q])
        if market!=action.get('market',[]):
            self.history.append(dict(event='seed_deadlines',step=step,route=route,purchases=purchases))
            self.stats['seed_deadline_interventions']+=1
        return dict(action,market=market)


def make_policy(arm):
    if arm=='deadlines':return DeadlinePolicy()
    if arm=='deadlines_bank':return DeadlinePolicy(bank=True)
    return previous_policy(arm)

"""Opening input deadlines, fulfilled pickups, and optional recent tape coverage."""
import gzip
import json
from coherent_opening_v4 import DeadlinePolicy,make_policy as previous_policy
from coherent_opening_policy import OUT,normalised_actions


class SemanticInputPolicy(DeadlinePolicy):
    def __init__(self,bank=False):
        super().__init__()
        sidecar=json.loads((OUT/'new_sources/pickup_sidecar_original3.json').read_text())
        pickups={(row['episode'],row['seat']):row['records'] for row in sidecar['episodes']}
        if bank:
            folder=OUT/'new_sources/traces'
            for row in json.loads((folder/'index.json').read_text()):
                with gzip.open(folder/row['trace'],'rt',encoding='utf-8') as handle:trace=json.load(handle)
                assert trace['team']=='DSM'
                route=len(self.ns['_MGT_TAPES']);actions=normalised_actions(trace['actions'],trace)
                boards=[self.ns['_mgt_board'](d['farm']) for d in trace['daily'][:30]];shops=trace['shops_by_day'][-1]
                offset=len(self.ns['_MGT_ACTIONS']);self.ns['_MGT_ACTIONS'].extend(actions)
                self.ns['_MGT_TAPES'].append(dict(ep=trace['episode'],ids=list(range(offset,offset+719)),boards=boards,shops=shops,
                    lab=[self.ns['_mgt_labels'](b) for b in boards],vec=[self.ns['_mgt_vec'](shops,j) for j in range(9)]))
                self.chassis.routes[route]=actions;self.ns['_MGT_ROUTES'][route]=actions;self.references[route]=trace
                pickups[trace['episode'],trace['seat']]=trace['pickup_success_by_step']
        for route,trace in self.references.items():
            for row in pickups.get((trace['episode'],trace['seat']),[]):
                if row['step']>=48:continue
                action=self.chassis.routes[route][row['step']]
                cmd=action['farmer'] if row['worker']==0 else action['hands'][row['worker']-1]
                assert cmd[:2]==['PICKUP',row['item']]
                cmd[:]=['PICKUP',row['item'],row['filled']]
        self.chassis._future_sells.clear()

    def __call__(self,obs,configuration=None):
        action=super().__call__(obs,configuration)
        step=int(obs['step'])
        if step>=48:return action
        route=self._route(obs);upcoming=self.chassis.routes[route][step+1]
        commands=[upcoming.get('farmer') or ['PASS'],*(upcoming.get('hands') or [])]
        private=self.after_work(obs,action)
        market=[list(o) for o in action.get('market',[]) if o and not(len(o)>=3 and o[1]=='WHEAT' and o[0] in ('SELL','BUY_PRODUCT'))]
        need=sum(int(c[2]) if len(c)>2 else 1 for c in commands if c and c[0]=='PICKUP' and c[1]=='WHEAT')
        q=max(0,need-private['shed'].get('WHEAT',0))
        if q:
            market=[o for o in market if len(o)<3 or o[2]>0]
            if len(market)<10:market.append(['BUY_PRODUCT','WHEAT',q])
        if market!=action.get('market',[]):
            self.history.append(dict(event='feed_deadlines',step=step,route=route,quantity=q))
            self.stats['feed_deadline_interventions']+=1
        return dict(action,market=market)


def make_policy(arm):
    if arm=='semantic_inputs':return SemanticInputPolicy()
    if arm=='semantic_bank':return SemanticInputPolicy(bank=True)
    return previous_policy(arm)

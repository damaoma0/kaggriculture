"""Opening development revision: preserve capital jobs; add fresh DSM tapes."""
from copy import deepcopy
from coherent_opening_policy import CoherentPolicy, Projection, _load_traces, normalised_actions, make_policy as original_policy


class OpeningPolicy(CoherentPolicy):
    def __init__(self, latest=False, sales=False):
        super().__init__(False)
        self.sales = sales
        self.projector = Projection() if sales else None
        if latest:
            traces = [trace for options in _load_traces().values() for trace in options if trace['source']=='fresh']
            for trace in sorted(traces,key=lambda t:t['episode']):
                route = len(self.ns['_MGT_TAPES'])
                actions = normalised_actions(trace['actions'],trace)
                boards = [self.ns['_mgt_board'](d['farm']) for d in trace['daily'][:30]]
                shops = trace['shops_by_day'][-1]
                assert len(boards)==30 and len(shops)==8
                offset = len(self.ns['_MGT_ACTIONS'])
                self.ns['_MGT_ACTIONS'].extend(actions)
                self.ns['_MGT_TAPES'].append(dict(ep=trace['episode'],ids=list(range(offset,offset+719)),
                    shops=shops,boards=boards,lab=[self.ns['_mgt_labels'](b) for b in boards],
                    vec=[self.ns['_mgt_vec'](shops,j) for j in range(9)]))
                self.chassis.routes[route] = actions
                self.ns['_MGT_ROUTES'][route] = actions
                self.references[route] = trace
                # Choose the most recent available source before seeing any
                # evaluation outcome. It keeps its full same-family continuation.
                self.ns['_MGT_CFG']['default_route'] = route
            self.chassis._future_sells.clear()

    def __call__(self,obs,configuration=None):
        action = super().__call__(obs,configuration)
        if not self.sales or int(obs['day'])>11:
            return action
        market = [list(o) for o in action.get('market',[]) if o]
        if not any(o[0] in ('BUY_ANIMAL','BUY_LAND','BUY_SEED','BUY_PRODUCT','HIRE') for o in market):
            return action
        step=int(obs['step']); route=self._route(obs); tape=self.chassis.routes[route]
        stop=self._stop(tape,step)
        gap=self.projector.deficit(obs,action,tape,stop)
        self.stats['projections']+=1
        if gap<=0:return action
        original_gap=gap;changes=[]
        ordered=sorted(market,key=lambda o:0 if o[0]=='SELL' else 1)
        if ordered!=market:
            trial=dict(action,market=deepcopy(ordered))
            next_gap=self.projector.deficit(obs,trial,tape,stop);self.stats['projections']+=1
            if next_gap<gap:
                action=trial;market=ordered;gap=next_gap;changes.append(['sales_before_spending'])
        for price,item,quantity in self._free_sell(obs,action,tape,stop):
            if gap<=0:break
            q=min(quantity,max(1,int((gap+price-1)//price)))
            existing=next((o for o in market if o[0]=='SELL' and o[1]==item),None)
            if existing:existing[2]+=q
            elif len(market)<10:market.insert(0,['SELL',item,q])
            else:continue
            market.sort(key=lambda o:0 if o[0]=='SELL' else 1)
            action=dict(action,market=deepcopy(market));changes.append(['early_sale',item,q])
            gap=self.projector.deficit(obs,action,tape,stop);self.stats['projections']+=1
            if gap<=0:break
        self.stats['funding_interventions']+=bool(changes)
        self.stats['unresolved_projected_hire_deficits']+=int(gap>0)
        self.history.append(dict(event='funding',step=step,route=route,initial_gap=original_gap,remaining_gap=gap,changes=changes))
        return action


def make_policy(arm):
    if arm=='sales':return OpeningPolicy(sales=True)
    if arm=='latest':return OpeningPolicy(latest=True)
    if arm=='latest_sales':return OpeningPolicy(latest=True,sales=True)
    return original_policy(arm)

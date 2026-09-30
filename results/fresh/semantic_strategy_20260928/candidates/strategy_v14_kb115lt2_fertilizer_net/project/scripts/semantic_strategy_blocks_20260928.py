"""Optional causal three-day quantity budgets above the unchanged tiler.

This separate policy keeps each reveal's jointly predicted budget fixed, counts
observed successful establishments, and carries unfinished work within the block.
It never retrieves a target world's suffix or reads recorded episode identities.
The offline model contains fitted coefficients and anonymous D6 examples only.
"""
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path

import semantic_strategy_policy_20260928 as P


def _round(x):return max(0,int(math.floor(float(x)+.5)))


def _allocate(n,weights):
    if not n:return [0]*len(weights)
    total=sum(weights);weights=list(weights) if total else [1.]+[0.]*(len(weights)-1)
    total=sum(weights);raw=[n*w/total for w in weights];out=[int(math.floor(x)) for x in raw]
    for i in sorted(range(len(out)),key=lambda i:(-(raw[i]-out[i]),i))[:n-sum(out)]:out[i]+=1
    return out


def _held(state,species):return int(state.get('stock',{}).get(species,0))


class SemanticBlockPolicy(P.SemanticStrategyPolicy):
    """Same propose/observe API; use a separately built block-model artifact."""
    def __init__(self,model_or_path,config=None):
        self.model=(json.loads(Path(model_or_path).read_text()) if isinstance(model_or_path,(str,Path))
                    else deepcopy(model_or_path))
        self.config=deepcopy(P.DEFAULT_CONFIG);self.config.update(config or {})
        # Active-commitment accounting is part of this mode, including its
        # synthetic internal targets. It is not optional donor-survival policy.
        self.config['retirement_active_target_guard']=True
        self.species=tuple(self.model['species']);self.outputs=tuple(self.model['outputs'])

    def _features(self,state,modelled):
        dem=Counter(P.demand(state['shops_prefix']))
        if modelled:
            missing=max(0,min(8,state['day']//3)-len(state['shops_prefix']))
            for shop in P.SHOPS:
                for product,n in P.SHOPS[shop].items():dem[product]+=missing*n/len(P.SHOPS)
        own=P.cohort_counts(state['own_crop_cohorts'],'crop')+P.cohort_counts(state['own_animal_cohorts'],'species')
        return [dem[p] for p in self.model['demand_features']]+[own[s] for s in self.species]

    def _release_schedule(self,state,start,end):
        schedule={s:[0]*(end-start+1) for s in ('WHEAT','CARROT')}
        for c in state['own_crop_cohorts']:
            crop=c['crop'];birth=P._birth(c)
            if crop not in schedule or birth>=start:continue
            release=max(start,birth+self.config['release_age'][crop]);count=int(c['count'])
            if release>end:continue
            ready=count
            if (release==state['day'] and c.get('observation_day')==release
                    and release-birth==self.config['release_age'][crop]):ready=int(c.get('ready_count',count))
            schedule[crop][release-start]+=ready
            if ready<count and release+1<=end:schedule[crop][release+1-start]+=count-ready
        return schedule

    def _make_block(self,state,modelled=False):
        start=3*(state['day']//3);end=min(29,start+2);model=self.model['blocks'][str(start)]
        releases=self._release_schedule(state,start,end);example_index=None
        if start==6 and model['opening_examples']:
            examples=model['opening_examples']
            example_index=min(range(len(examples)),key=lambda i:(P.row_distance(state,
                {'day':6,'features':examples[i]['features']},self.config),i))
            ex=examples[example_index];daily=ex['daily'];pred=[sum(row[i] for row in daily) for i in range(len(self.outputs))]
            shares=[[row[i]/pred[i] if pred[i] else 1/len(daily) for i in range(len(pred))] for row in daily]
            hands=list(ex['hands']);land=list(ex['land'])
        else:
            features=self._features(state,modelled)
            x=[1.]+[(v-m)/s for v,m,s in zip(features,model['mean'],model['scale'])]
            pred=[sum(x[j]*model['coef'][j][i] for j in range(len(x))) for i in range(len(self.outputs))]
            for crop in releases:pred[self.outputs.index(crop)]+=sum(releases[crop])
            shares=model['shares'];hands=list(model['hands']);land=list(model['land'])
        totals={s:min(_round(pred[i]),max(0,_round(model['max_counts'][i]))) for i,s in enumerate(self.outputs)}
        # Previously bought but still unplaced animals are owned commitments.
        # Count them as placements, while the inherited admission credits stock
        # so neither policy nor executor needs to buy them again.
        for sp in P.ANIMALS:totals[sp]=max(totals[sp],_held(state,sp))
        schedule={str(d):dict(plant_counts={},animal_add_counts={},animal_retire_counts={},
                              hands=int(hands[d-start]),land=int(land[d-start])) for d in range(start,end+1)}
        for i,sp in enumerate(self.outputs):
            weights=[max(0,float(row[i])) for row in shares];n=totals[sp]
            if sp in releases:
                base=releases[sp]
                if n>=sum(base):counts=[a+b for a,b in zip(base,_allocate(n-sum(base),weights))]
                else:counts=_allocate(n,base)
            elif sp in P.ANIMALS and _held(state,sp):
                prepaid=min(n,_held(state,sp));counts=_allocate(n-prepaid,weights);counts[0]+=prepaid
            else:counts=_allocate(n,weights)
            field='animal_retire_counts' if sp.startswith('RETIRE_') else ('plant_counts' if sp in P.CROPS else 'animal_add_counts')
            species=sp.removeprefix('RETIRE_')
            for d,n in zip(range(start,end+1),counts):
                if n:schedule[str(d)][field][species]=n
        animals=P.cohort_counts(state['own_animal_cohorts'],'species')
        active={sp:max(0,animals[sp]-state.get('committed_retirement_counts',{}).get(sp,0)) for sp in P.ANIMALS}
        return dict(start=start,end=end,schedule=schedule,totals=totals,initial_active=active,
                    seen_births={},opening_example_index=example_index,
                    forecast_only=modelled,unrevealed_shops='uniform expectation' if modelled else 'none')

    @staticmethod
    def _observe_success(state,block):
        for kind,rows in (('crop',state['own_crop_cohorts']),('animal',state['own_animal_cohorts'])):
            counts=Counter()
            for c in rows:
                birth=P._birth(c)
                if block['start']<=birth<=min(block['end'],state['day']):
                    species=c.get('crop',c.get('species'));counts[f'{kind}|{species}|{birth}']+=int(c.get('count',1))
            for key,n in counts.items():block['seen_births'][key]=max(n,block['seen_births'].get(key,0))

    def _choice(self,state,block,history):
        self._observe_success(state,block);day=state['day']
        cumulative={k:Counter() for k in ('plant_counts','animal_add_counts','animal_retire_counts')}
        for d in range(block['start'],min(day,block['end'])+1):
            for key in cumulative:cumulative[key].update(block['schedule'][str(d)][key])
        completed={k:Counter() for k in ('crop','animal')}
        for key,n in block['seen_births'].items():
            kind,species,birth=key.split('|');completed[kind][species]+=n
        plants={sp:max(0,n-completed['crop'][sp]) for sp,n in cumulative['plant_counts'].items()}
        adds={sp:max(0,n-completed['animal'][sp]) for sp,n in cumulative['animal_add_counts'].items()}
        physical=P.cohort_counts(state['own_animal_cohorts'],'species')
        active={s:max(0,physical[s]-state.get('committed_retirement_counts',{}).get(s,0)) for s in P.ANIMALS}
        retires={}
        for sp,n in cumulative['animal_retire_counts'].items():
            goal=max(0,block['initial_active'][sp]+cumulative['animal_add_counts'][sp]-n)
            take=min(n,max(0,active[sp]-goal))
            if take:retires[sp]=take;adds.pop(sp,None)
        survivors=P.crop_survivors(state['own_crop_cohorts'],day,self.config['release_age'])
        # These are our own internally derived end counts, not a donor board.
        # They make the inherited funding/capacity admission accept exactly the
        # outstanding budget before its physical and cash limits are applied.
        target=dict(plant_counts={s:n for s,n in plants.items() if n},
            animal_add_counts={s:n for s,n in adds.items() if n},animal_retire_counts=retires,
            end_crop_counts=dict(survivors+Counter(plants)),
            end_animal_counts={s:active[s]+adds.get(s,0) for s in P.ANIMALS},
            hands=block['schedule'][str(day)]['hands'],target_land_count=block['schedule'][str(day)]['land'])
        paths,rival=P.forecast_market(state,self.config,history)
        values={s:P.cohort_value(state,s,paths,rival,self.config) for s in (*P.CROPS,*P.ANIMALS)}
        choice=self._proposal(state,dict(day=day,features={},target=target),values)
        diag=dict(requested=target,completed={k:dict(v) for k,v in completed.items()},
                  cohort_values={s:round(v,3) for s,v in values.items()})
        return choice,diag

    def propose(self,observation,memory=None):
        state=P.public_state(observation,fertilizer_details=self.config.get('forecast_fertilizer_net',False))
        day=state['day'];memory=deepcopy(memory or {})
        if not 6<=day<=29:raise ValueError('block policy begins at day6')
        physical=P.cohort_counts(state['own_animal_cohorts'],'species')
        state['committed_retirement_counts']={s:min(physical[s],max(0,int(n)))
            for s,n in memory.get('committed_retirement_counts',{}).items() if s in P.ANIMALS and int(n)>0}
        # Counts reveal intent but not the exact remaining unfed nights. Reserve
        # two further nights in the forecast; the tiler uses actual identities.
        cohorts=state['own_animal_cohorts']
        for sp,n in state['committed_retirement_counts'].items():
            for c in sorted(cohorts,key=P._birth):
                if c['species']!=sp or 'retire_day' in c or n<=0:continue
                take=min(n,c['count']);n-=take
                if take<c['count']:cohorts.append(dict(c,count=c['count']-take));c['count']=take
                c['retire_day']=day
        history={};recent=[v for key,v in memory.get('public_history',{}).items() if day-3<=int(key)<day]
        if recent:history['rival_net_daily']={p:sum(v.get('rival_harvest',{}).get(p,0) for v in recent)/len(recent) for p in P.PRODUCTS}
        if recent and self.config.get('forecast_fertilizer_net',False):history['rival_flow_kind']='harvest'
        block=memory.get('block_strategy')
        if not block or block['start']!=3*(day//3):block=self._make_block(state)
        today,detail=self._choice(state,block,history)
        memory['block_strategy']=deepcopy(block)
        forecast=[today];future=self._advance(state,today);future_block=deepcopy(block)
        if self.config['forecast']:
            while future['day']<30:
                if future['day']>future_block['end']:future_block=self._make_block(future,True)
                choice,_=self._choice(future,future_block,history);forecast.append(choice);future=self._advance(future,choice)
        diag=dict(mode='three_day_budget',block_start=block['start'],block_end=block['end'],
            totals=block['totals'],row_index=block['opening_example_index'],**detail,
            causal_features_only=True,forecast_commitment='current reveal block only; subsequent blocks are modeled',
            future_shop_assumption='uniform expectation for unrevealed shops',remaining_jobs_carry_within_block=True)
        return dict(day=day,today=today,forecast=forecast,memory=memory,diagnostics=diag,
                    replan_day=day+1,next_reveal_day=min(30,block['end']+1))

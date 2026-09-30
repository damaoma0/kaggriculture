"""Alternative rival worlds anchored to the currently visible live cohorts.

Empirical continuation is useful for rotations; current-cohort mechanics are
an independent model for long crops and animals. Using both exposes model
disagreement rather than trusting a single older opponent family.
"""
from collections import Counter,defaultdict
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import rival_trajectory_model as M

MODEL_SHA256=sha256(Path(__file__).read_bytes()).hexdigest()
COHORT_PRODUCTS={'STRAWBERRY','TOMATO','MELON','EGG','MILK','WOOL'}


def world(obs,index,*,delay=0):
    result=M.world(obs,index);day=int(obs['day'])
    ideal=M.ideal_flows(obs['farms'][1-int(obs['player'])],day)
    daily={d:Counter() for d in range(day,30)}
    hours=defaultdict(Counter)
    for t,flows in result['hourly'].items():
        for p,n in flows.items():
            daily[t//24][p]+=n
            if n>0:hours[p][t%24]+=n
    flows=defaultdict(Counter)
    carry=Counter()
    for d in range(day,30):
        for p in M.PRODUCTS:
            # Surviving cohorts have dated official-engine yield clocks.
            # Empty/short plots need an empirical later-planting continuation.
            value=ideal[d].get(p,0) if p in COHORT_PRODUCTS else .5*(ideal[d].get(p,0)+daily[d][p])
            carry[p]+=value;n=int(carry[p]);carry[p]-=n
            if not n:continue
            histogram=hours[p] or Counter({20:1})
            allocated=0;weight=0;total=sum(histogram.values())
            for h,w in sorted(histogram.items()):
                weight+=w;cumulative=round(abs(n)*weight/total)
                take=cumulative-allocated;allocated=cumulative
                if take:
                    t=min(718,d*24+h+delay)
                    flows[t][p]+=take if n>0 else -take
    result['hourly']={t:dict(c) for t,c in flows.items()}
    result['donor']=dict(result['donor'],model='current_cohort_with_empirical_rotation',delivery_delay=delay)
    return result

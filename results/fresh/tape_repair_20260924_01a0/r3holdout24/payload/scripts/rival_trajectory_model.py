"""Public-cohort nearest-neighbour sales scenarios from older verified games.

The model reads only the frozen training split. It transports a donor's
successful sale calendar, correcting aggregate quantities for visible cohort
differences. No target identity, private rival stocks, or actual future enters.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import gzip
import json
from pathlib import Path
import random

import value_tape_search as V

LIBRARY=V.ROOT/'results/fresh/value_tape_followup_20260923/rival_library'
MODEL_SHA256=sha256(Path(__file__).read_bytes()).hexdigest()
PRODUCTS=('WHEAT','CARROT','TOMATO','STRAWBERRY','MELON','EGG','MILK','WOOL','FERTILIZER')
DEMAND={'BAKERY':('EGG','WHEAT'),'PIZZA_SHOP':('MILK','TOMATO','WHEAT'),
    'BRUNCH_SPOT':('EGG','WHEAT','STRAWBERRY'),'YARN_STORE':('WOOL','WOOL'),
    'ICE_CREAM_SHOP':('STRAWBERRY','MILK','WHEAT'),'PET_CAFE':('CARROT','CARROT'),
    'SMOOTHIE_SHOP':('STRAWBERRY','MILK'),'FARMERS_MARKET':('WHEAT','CARROT','TOMATO','STRAWBERRY')}


@lru_cache(maxsize=1)
def training_library():
    manifest=json.loads((LIBRARY/'manifest.json').read_text(encoding='utf-8'))
    result=[]
    for item in manifest['games']:
        if item['split']!='train':continue
        with gzip.open(LIBRARY/f"{item['episode']}.json.gz",'rt',encoding='utf-8') as f:row=json.load(f)
        assert row['verified'] and row['split']=='train'
        result.append(row)
    assert len(result)==75
    return result


def label(tile):
    if isinstance(tile,dict):return tile.get('crop') or tile.get('animal') or tile.get('kind')
    return tile or 'EMPTY'


def board_distance(left,right):
    score=0.0
    for a,b in zip((t for row in left['tiles'] for t in row),(t for row in right['tiles'] for t in row)):
        la,lb=label(a),label(b)
        if la!=lb:
            score+=1 if la in ('WHEAT','CARROT','EMPTY','WEED') and lb in ('WHEAT','CARROT','EMPTY','WEED') else 3
        elif isinstance(a,dict) and isinstance(b,dict):
            birth='placed_day' if a.get('animal') else 'planted_day'
            score+=.2*min(6,abs(a.get(birth,0)-b.get(birth,0)))
            score+=.15*abs(a.get('yield_units',0)-b.get('yield_units',0))
            score+=.1*abs(a.get('pending_care_bonus',0)-b.get('pending_care_bonus',0))
    return score


def shop_distance(a,b):
    ca,cb=Counter(p for s in a for p in DEMAND[s]),Counter(p for s in b for p in DEMAND[s])
    return sum(abs(ca[p]-cb[p]) for p in PRODUCTS)


def scenario_shops(obs,index):
    """Eight equally weighted futures: every shop occurs once at each reveal.

    Independently shuffled columns keep duplicate shops possible within a
    world. This is stratified sampling, not knowledge of the episode RNG.
    """
    origin=int(obs['day']);shops=list(obs['town']['unlocked_shops']);result={}
    for day in range(origin,30):
        if day>origin and day in range(3,25,3) and len(shops)<8:
            options=sorted(DEMAND)
            random.Random(93231471+origin*1009+day*9173).shuffle(options)
            shops.append(options[index%8])
        result[day]=list(shops)
    return result


def ideal_flows(farm,day):
    fake={'day':day,'player':0,'farms':[{},farm]}
    return V.rival_schedule(fake,1.0)


@lru_cache(maxsize=450)
def donor_ideal(episode,day):
    donor=next(r for r in training_library() if r['episode']==episode)
    return ideal_flows(donor['farms'][day],day)


def select_donor(obs,shops,index):
    day=int(obs['day']);farm=obs['farms'][1-int(obs['player'])]
    ranked=[]
    for row in training_library():
        physical=board_distance(farm,row['farms'][day])
        revealed=shop_distance(obs['town']['unlocked_shops'],row['shops'][day])
        score=physical+.6*revealed
        ranked.append((score,row))
    ranked.sort(key=lambda x:(x[0],x[1]['episode']))
    # The future-shop term chooses among physically close continuations only.
    pool=ranked[:12]
    choices=[]
    for score,row in pool:
        future=sum(shop_distance(shops[d],row['shops'][d]) for d in range(day+3,30,3))
        choices.append((score+.25*future,row))
    choices.sort(key=lambda x:(x[0],x[1]['episode']))
    # Rotate among the closest three as opponent-behaviour uncertainty.
    score,donor=choices[(index//2)%3]
    return donor,dict(episode=donor['episode'],distance=score,
        public_board_distance=board_distance(farm,donor['farms'][day]))


def world(obs,index,*,correction=True):
    day=int(obs['day']);shops=scenario_shops(obs,index)
    donor,metadata=select_donor(obs,shops,index)
    hourly=defaultdict(Counter)
    for t,op,p in donor['trades']:
        if t>=24*day:hourly[t][p]+=1 if op=='SELL' else -1
    if correction:
        # Donor residuals represent later planting and delivery. Visible cohort
        # differences supply a bounded quantity correction in three-day blocks.
        target=ideal_flows(obs['farms'][1-int(obs['player'])],day)
        source=donor_ideal(donor['episode'],day)
        for block in range(day,30,3):
            stop=min(30,block+3)
            for p in PRODUCTS:
                delta=sum(target.get(d,{}).get(p,0)-source.get(d,{}).get(p,0) for d in range(block,stop))
                if not delta:continue
                times=[t for t in range(block*24,min(stop*24,719)) if hourly[t][p]>0]
                total=sum(hourly[t][p] for t in times)
                # Avoid reversing a donor's market direction on a poor match.
                delta=max(-total,delta)
                if times and total:
                    allocated=0;weight=0
                    for t in times:
                        weight+=hourly[t][p]
                        cumulative=round(delta*weight/total)
                        hourly[t][p]+=cumulative-allocated;allocated=cumulative
                elif delta>0:
                    # Additional visible output has no learned sale hour here.
                    # Spread it over late-day delivery rather than h1 dumping.
                    for i in range(delta):
                        t=min(718,(block+i%(stop-block))*24+20)
                        hourly[t][p]+=1
    farms={d:deepcopy(donor['farms'][d]) for d in range(day,30)}
    farms[day]=deepcopy(obs['farms'][1-int(obs['player'])])
    return dict(index=index,shops=shops,hourly={t:dict(c) for t,c in hourly.items()},farms=farms,donor=metadata)

"""Multi-generation public-cohort retrieval for rival continuation scenarios.

Forty outcome-blind modern examples supplement the older 75 training games.
The nearest visible farm, including cohort age, chooses the applicable family.
All earlier target cases and both forecast test splits are excluded.
"""
from collections import Counter,defaultdict
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import gzip
import json
from pathlib import Path

import rival_trajectory_model as M

MODERN=M.LIBRARY.parent/'modern_rival_library'
MODEL_SHA256=sha256(Path(__file__).read_bytes()).hexdigest()
PRODUCTS=M.PRODUCTS


@lru_cache(maxsize=1)
def training_library():
    rows=list(M.training_library())
    manifest=json.loads((MODERN/'manifest.json').read_text(encoding='utf-8'))
    for item in manifest['games']:
        if item['split']!='train':continue
        with gzip.open(MODERN/f"{item['episode']}.json.gz",'rt',encoding='utf-8') as f:row=json.load(f)
        assert row['verified'] and row['split']=='train' and row['episode'] not in manifest['excluded']
        rows.append(row)
    assert len(rows)==115
    return rows


@lru_cache(maxsize=800)
def donor_ideal(episode,day):
    row=next(r for r in training_library() if r['episode']==episode)
    return M.ideal_flows(row['farms'][day],day)


def select_donor(obs,shops,index):
    day=int(obs['day']);farm=obs['farms'][1-int(obs['player'])]
    ranked=[]
    for row in training_library():
        distance=M.board_distance(farm,row['farms'][day])
        score=distance+.6*M.shop_distance(obs['town']['unlocked_shops'],row['shops'][day])
        ranked.append((score,row))
    ranked.sort(key=lambda x:(x[0],x[1]['episode']))
    choices=[]
    for score,row in ranked[:12]:
        future=sum(M.shop_distance(shops[d],row['shops'][d]) for d in range(day+3,30,3))
        choices.append((score+.25*future,row))
    choices.sort(key=lambda x:(x[0],x[1]['episode']))
    score,donor=choices[(index//2)%3]
    return donor,dict(episode=donor['episode'],distance=score,
        public_board_distance=M.board_distance(farm,donor['farms'][day]))


def world(obs,index):
    day=int(obs['day']);shops=M.scenario_shops(obs,index)
    donor,metadata=select_donor(obs,shops,index);hourly=defaultdict(Counter)
    for t,op,p in donor['trades']:
        if t>=24*day:hourly[t][p]+=1 if op=='SELL' else -1
    target=M.ideal_flows(obs['farms'][1-int(obs['player'])],day)
    source=donor_ideal(donor['episode'],day)
    for block in range(day,30,3):
        stop=min(30,block+3)
        for p in PRODUCTS:
            delta=sum(target.get(d,{}).get(p,0)-source.get(d,{}).get(p,0) for d in range(block,stop))
            if not delta:continue
            times=[t for t in range(block*24,min(stop*24,719)) if hourly[t][p]>0]
            total=sum(hourly[t][p] for t in times);delta=max(-total,delta)
            if times and total:
                allocated=0;weight=0
                for t in times:
                    weight+=hourly[t][p];cumulative=round(delta*weight/total)
                    hourly[t][p]+=cumulative-allocated;allocated=cumulative
            elif delta>0:
                for i in range(delta):hourly[min(718,(block+i%(stop-block))*24+20)][p]+=1
    farms={d:deepcopy(donor['farms'][d]) for d in range(day,30)}
    farms[day]=deepcopy(obs['farms'][1-int(obs['player'])])
    return dict(index=index,shops=shops,hourly={t:dict(c) for t,c in hourly.items()},farms=farms,donor=metadata)

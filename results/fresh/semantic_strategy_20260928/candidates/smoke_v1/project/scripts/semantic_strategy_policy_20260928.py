"""Causal daily quantity policy above the validated semantic tiler / KB115LT.

Runtime reads only the public observation, own private inventory, and a static
coordinate-free decision library. Recorded episode identifiers, rewards, future
shop sequences and donor coordinates are never selection features. A forecast is
an assumption, rebuilt from the actual farm every day, not a commitment to a donor.

The policy deliberately proposes quantities, not crop identities or worker jobs.
The online adapter owns exact release/retirement identities and route admission.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path

CROPS = {
    "WHEAT": dict(seed=10, first=2, last=4, interval=0, units=6),
    "CARROT": dict(seed=20, first=2, last=3, interval=0, units=4),
    "TOMATO": dict(seed=50, first=8, last=11, interval=1, units=4),
    "STRAWBERRY": dict(seed=100, first=10, last=16, interval=2, units=4),
    "MELON": dict(seed=80, first=10, last=12, interval=0, units=6),
}
ANIMALS = {
    "COW": dict(cost=400, first=8, interval=2, product="MILK", structure="PASTURE", held=6),
    "SHEEP": dict(cost=500, first=6, interval=3, product="WOOL", structure="PASTURE", held=6),
    "GOOSE": dict(cost=300, first=4, interval=1, product="EGG", structure="COOP", held=4),
}
SHOPS = {
    "BAKERY": {"EGG": 1, "WHEAT": 1},
    "PIZZA_SHOP": {"MILK": 1, "TOMATO": 1, "WHEAT": 1},
    "BRUNCH_SPOT": {"EGG": 1, "WHEAT": 1, "STRAWBERRY": 1},
    "YARN_STORE": {"WOOL": 2}, "PET_CAFE": {"CARROT": 2},
    "ICE_CREAM_SHOP": {"STRAWBERRY": 1, "MILK": 1, "WHEAT": 1},
    "SMOOTHIE_SHOP": {"STRAWBERRY": 1, "MILK": 1},
    "FARMERS_MARKET": {"WHEAT": 1, "CARROT": 1, "TOMATO": 1, "STRAWBERRY": 1},
}
PRODUCTS = tuple(CROPS) + ("MILK", "WOOL", "EGG", "FERTILIZER")
WEIGHTS = {"STRAWBERRY": 3, "TOMATO": 2, "WOOL": 2, "MILK": 1.5,
           "CARROT": 1.5, "EGG": 1, "WHEAT": .5, "MELON": .5}
# Checked against engine 1.32.7. Observation market.params takes precedence.
_MARKET = {
    "WHEAT": (25,400,"sqrt",.8,"log",.2),
    "CARROT": (35,450,"hinge",1.,"sqrt",.7),
    "TOMATO": (60,200,"hinge",.4,"sqrt",.6),
    "STRAWBERRY": (120,100,"sqrt",.7,"linear",1.6),
    "MELON": (250,300,"log",.2,"sq",3.6),
    "EGG": (50,332,"hinge",.4,"log",.2),
    "MILK": (160,122,"sqrt",.6,"linear",1.6),
    "WOOL": (200,105,"log",.2,"sq",3.2),
    "FERTILIZER": (100,200,"linear",.4,"linear",.4),
}
DEFAULT_CONFIG = dict(neighbors=7, state_weight=.20, age_weight=.10,
    economics_weight=.0015, distance_weight=1., correction_fraction=.5,
    crop_correction_limit=4, animal_correction_limit=2, max_hands=14,
    forecast=True, forecast_economics=False, prior_future_shops=True,
    incremental_work_price=3., p95_work_factor=1.20,
    land_limit=4, max_land_add_per_day=1,
    minimum_wage_reserve=1., observed_supply_weight=.30, same_day_income_credit=1.)
DEFAULT_CONFIG["release_age"]={"WHEAT":4,"CARROT":3,"MELON":12,"TOMATO":12,"STRAWBERRY":17}


def _counts(x):
    return {str(k): int(v) for k, v in (x or {}).items() if int(v)>0}


def _shops(obs):
    result=[]
    for item in obs.get("town", {}).get("unlocked_shops", []):
        name=item if isinstance(item,str) else item.get("name", item.get("type", item.get("kind")))
        if name in SHOPS:
            result.append(name)
    return result


def demand(shops):
    out=Counter()
    for s in shops:
        out.update(SHOPS.get(s, {}))
    return dict(out)


def _birth(row):
    return int(row.get("birth",row.get("planted_day",row.get("placed_day",0))))


def _cohorts(farm):
    crops=Counter();animals=Counter();structures=Counter();animal_details=[]
    for row in farm.get("tiles", []):
        for tile in row:
            if not isinstance(tile,dict):
                continue
            if tile.get("crop") in CROPS:
                crops[(tile["crop"], int(tile["planted_day"]))]+=1
            if tile.get("kind") in ("PASTURE","COOP"):
                structures[tile["kind"]]+=1
            if tile.get("animal") in ANIMALS:
                animals[(tile["animal"], int(tile["placed_day"]))]+=1
                animal_details.append({k:tile[k] for k in ("animal","placed_day","pending_care_bonus",
                    "consecutive_unfed","yield_units") if k in tile})
    return ([dict(crop=s,birth=b,count=n) for (s,b),n in sorted(crops.items())],
            [dict(species=s,birth=b,count=n) for (s,b),n in sorted(animals.items())],
            dict(structures),animal_details)


def public_state(obs):
    """Allowlist observation projection; no reward, seed or episode field read."""
    day=int(obs["day"]); me=int(obs["player"]); own=obs["farms"][me]
    crops,animals,structures,details=_cohorts(own)
    rc,ra,rs,rd=_cohorts(obs["farms"][1-me])
    private=obs.get("private",{});stock=Counter(private.get("shed",{}))
    for inv in private.get("inventories",[]):
        stock.update(inv)
    available=Counter()
    for row in own.get("tiles",[]):
        for tile in row:
            if not isinstance(tile,dict):continue
            sp=tile.get("crop") or tile.get("animal")
            if sp in ANIMALS:
                available[ANIMALS[sp]["product"]]+=int(tile.get("yield_units",0))
                available["FERTILIZER"]+=int(bool(tile.get("fertilizer_available",False)))
            elif sp in CROPS and day-int(tile["planted_day"])>=CROPS[sp]["first"]:
                available[sp]+=int(tile.get("yield_units",0))
    market=obs.get("market",{})
    return dict(day=day,shops_prefix=_shops(obs),own_crop_cohorts=crops,
        own_animal_cohorts=animals,own_structures=structures,animal_details=details,
        cash=float(own.get("money",0)),owned_quadrants=len(own.get("unlocked_quadrants",["NW"])),
        prices={p:float(market.get("prices",{}).get(p,_MARKET[p][0])) for p in PRODUCTS},
        inventory={p:float(market.get("inventory",{}).get(p,10000)) for p in PRODUCTS},
        market_params=deepcopy(market.get("params",{})),stock=dict(stock),seeds=dict(private.get("seeds",{})),
        available_output=dict(available),
        rival_crop_cohorts=rc,rival_animal_cohorts=ra,rival_structures=rs,rival_animal_details=rd)


def crop_survivors(cohorts,day,release_age=None):
    """Assets left after today's routine full-age harvest / expiry.

    Release ages match the online adapter's ordinary service calendar. The last
    ongoing yield is harvested before replacement. Exact observed growth and
    delivery can cause the adapter to defer a proposed establishment.
    """
    out=Counter()
    for c in cohorts:
        crop=c.get("crop",c.get("species"));age=day-_birth(c)
        if crop in CROPS and age<(release_age or DEFAULT_CONFIG["release_age"])[crop]:
            out[crop]+=int(c.get("count",1))
    return out


def cohort_counts(cohorts,kind):
    out=Counter()
    for c in cohorts:
        out[c.get(kind,c.get("species",c.get("crop")))]+=int(c.get("count",1))
    return out


def _age_counts(cohorts,day,kind):
    out=Counter()
    for c in cohorts:
        out[(c.get(kind,c.get("species",c.get("crop"))),min(9,max(0,day-_birth(c))//3))]+=int(c.get("count",1))
    return out


def _l1(a,b,weights=None):
    return sum(abs(a.get(k,0)-b.get(k,0))*(weights or {}).get(k,1) for k in set(a)|set(b))


def _feature(row):
    return row.get("features",row)


def _target(row):
    return row.get("target",row.get("decision",{}))


def _land(features):
    x=features.get("owned_quadrants",features.get("land",1))
    return len(x) if isinstance(x,list) else int(x)


def _prefix(features):
    s=features.get("shops_prefix",features.get("shops",[]))
    if isinstance(s,dict):
        return [k for k,n in sorted(s.items()) for _ in range(int(n))]
    return list(s)


def row_distance(state,row,config):
    f=_feature(row);day=state["day"]
    shopcost=_l1(demand(state["shops_prefix"]),demand(_prefix(f)),WEIGHTS)
    # Compare survivors and age bands, not coordinate labels. This avoids
    # treating a ready wheat harvest as an unneeded replacement investment.
    a=crop_survivors(state["own_crop_cohorts"],day,config["release_age"])
    b=crop_survivors(f.get("own_crop_cohorts",[]),day,config["release_age"])
    a.update(cohort_counts(state["own_animal_cohorts"],"species"))
    b.update(cohort_counts(f.get("own_animal_cohorts",[]),"species"))
    ca=_age_counts(state["own_crop_cohorts"],day,"crop")
    cb=_age_counts(f.get("own_crop_cohorts",[]),day,"crop")
    aa=_age_counts(state["own_animal_cohorts"],day,"species")
    ab=_age_counts(f.get("own_animal_cohorts",[]),day,"species")
    return (shopcost+config["state_weight"]*_l1(a,b)+config["age_weight"]*(_l1(ca,cb)+_l1(aa,ab))
            +.65*abs(state["owned_quadrants"]-_land(f)))


def _shape(name,x,t):
    x=max(0.,x)
    if name=="sqrt": return math.sqrt(x)
    if name=="log": return math.log1p(x)
    if name=="log10": return math.log10(1+x)
    if name=="sq": return x*x
    if name=="hinge":
        u=x/t
        return u+8*max(0,u-1)**2
    return x


def market_price(product,inventory,params=None):
    base,t,below,bt,above,at=_MARKET[product]
    p=dict(base=base,T=t,I0=10000,below_func=below,below_target=bt,above_func=above,above_target=at)
    p.update((params or {}).get(product,{}))
    low=inventory<p["I0"];side="below" if low else "above"
    amp=p[side+"_target"]*p["base"]/_shape(p[side+"_func"],p["T"],p["T"])
    return max(1,int(round(p["base"]+(1 if low else -1)*amp*_shape(p[side+"_func"],abs(inventory-p["I0"]),p["T"]))))


def output_calendar(crops,animals,day,scale=1.,release_age=None):
    """Fast conservative physical calendar; delivery and care are assumptions."""
    byday={d:Counter() for d in range(day,30)}
    for c in crops:
        sp=c.get("crop",c.get("species"));r=CROPS[sp];birth=_birth(c);n=int(c.get("count",1))*scale
        if r["interval"]:
            for age in range(r["first"],r["last"]+1,r["interval"]):
                if day<=birth+age<=29:
                    byday[birth+age][sp]+=n*1.65
        else:
            harvest=min(29,birth+(release_age or DEFAULT_CONFIG["release_age"])[sp])
            if harvest>=max(day,birth+r["first"]):
                age=harvest-birth
                units=min(r["units"],1+max(0,age-(r["last"]+1)//2+1)*1.4)
                byday[harvest][sp]+=n*units
    for c in animals:
        sp=c.get("species",c.get("animal"));r=ANIMALS[sp];birth=_birth(c);n=int(c.get("count",1))*scale
        for d in range(day,30):
            if c.get("retire_day",99)+2<=d:continue
            if d-birth>=r["first"] and (d-birth-r["first"])%r["interval"]==0:
                care_days=r["first"]-1 if d-birth==r["first"] else r["interval"]
                units=1 if c.get("retire_day",99)<d else min(r["held"],1+care_days*.85)
                byday[d][r["product"]]+=n*units
            if d>birth:
                byday[d]["FERTILIZER"]+=n*.85
    return byday


def forecast_market(state,config,history=None):
    own=output_calendar(state["own_crop_cohorts"],state["own_animal_cohorts"],state["day"],release_age=config["release_age"])
    rival=output_calendar(state["rival_crop_cohorts"],state["rival_animal_cohorts"],state["day"],release_age=config["release_age"])
    flow=(history or {}).get("rival_net_daily",{})
    # If caller supplied own net trades, the market identity identifies rival
    # net trades without observing private rival stock. Otherwise use farm only.
    if flow:
        w=config["observed_supply_weight"]
        for d in rival:
            for p in PRODUCTS:
                if p in flow:
                    rival[d][p]=(1-w)*rival[d][p]+w*max(0,float(flow[p]))
    visible=demand(state["shops_prefix"]);prior=Counter()
    for values in SHOPS.values():
        for p,n in values.items(): prior[p]+=n/len(SHOPS)
    inv=dict(state["inventory"]);paths={}
    for d in range(state["day"],30):
        unknown=max(0,min(8,d//3)-len(state["shops_prefix"])) if config["prior_future_shops"] else 0
        for p in PRODUCTS:
            inv[p]+=own[d][p]+rival[d][p]-6*(visible.get(p,0)+unknown*prior[p])-(p!="FERTILIZER")
        paths[d]=dict(inv)
    return paths,rival


def cohort_value(state,species,paths,rival,config):
    """Marginal competitive receipts of one additional cohort, no spot shortcut."""
    day=state["day"];animal=species in ANIMALS;r=ANIMALS[species] if animal else CROPS[species]
    crops=[] if animal else [dict(crop=species,birth=day,count=1)]
    animals=[dict(species=species,birth=day,count=1)] if animal else []
    extra=output_calendar(crops,animals,day,release_age=config["release_age"])
    own=output_calendar(state["own_crop_cohorts"],state["own_animal_cohorts"],day,release_age=config["release_age"])
    accum=Counter();value=-r.get("cost",r.get("seed",0));work=0.
    final=min(29,day+(29 if animal else r["last"]))
    for d in range(day,30):
        for p,n in extra[d].items():
            if n<=0: continue
            before=market_price(p,paths[d][p]+accum[p],state["market_params"])
            after=market_price(p,paths[d][p]+accum[p]+n,state["market_params"])
            value+=n*(before+after)/2+(before-after)*(rival[d].get(p,0)-own[d].get(p,0))
            accum[p]+=n
            work+=n/4+1
        if animal and d<29:
            value-=market_price("WHEAT",paths[d]["WHEAT"],state["market_params"])
            work+=3.0
        elif not animal and d<=final:
            work+=.65
            if r["interval"] and d+1-day>=r["first"] and (d+1-day-r["first"])%r["interval"]==0:
                value-=.40*market_price("FERTILIZER",paths[d]["FERTILIZER"],state["market_params"])
    work+=5 if animal else 3
    return value-config["incremental_work_price"]*work


def bundle_value(state,choice,paths,rival,config,unit_values):
    """Correct separate-cohort scores for shared market inventory and price impact.

    All additions affect the same market path. Existing own revenue lost to a
    lower price offsets the rival's lost revenue in the competitive objective.
    This prevents a bundle of individually valuable berries being valued as if
    every added cohort sold into the original unaltered price curve.
    """
    day=state["day"];crops=[dict(crop=s,birth=day,count=n) for s,n in choice['plant_counts'].items()]
    animals=[dict(species=s,birth=day,count=n) for s,n in choice['animal_add_counts'].items()]
    own=output_calendar(state["own_crop_cohorts"],state["own_animal_cohorts"],day,release_age=config["release_age"])
    extra=output_calendar(crops,animals,day,release_age=config["release_age"])
    independent=0.;joint=0.;accum=Counter()
    for d in range(day,30):
        for p,n in extra[d].items():
            before=market_price(p,paths[d][p]+accum[p],state['market_params'])
            after=market_price(p,paths[d][p]+accum[p]+n,state['market_params'])
            joint+=n*(before+after)/2+(before-after)*(rival[d].get(p,0)-own[d].get(p,0))
            accum[p]+=n
    for species,count in list(choice['plant_counts'].items())+list(choice['animal_add_counts'].items()):
        c=[] if species in ANIMALS else [dict(crop=species,birth=day,count=1)]
        a=[dict(species=species,birth=day,count=1)] if species in ANIMALS else []
        one=output_calendar(c,a,day,release_age=config['release_age']);accum=Counter()
        for d in range(day,30):
            for p,n in one[d].items():
                before=market_price(p,paths[d][p]+accum[p],state['market_params'])
                after=market_price(p,paths[d][p]+accum[p]+n,state['market_params'])
                independent+=count*(n*(before+after)/2+(before-after)*(rival[d].get(p,0)-own[d].get(p,0)))
                accum[p]+=n
    return sum(unit_values[s]*n for k in ('plant_counts','animal_add_counts') for s,n in choice[k].items())+joint-independent


def _hire_cost(n):
    a=b=1;total=0
    for _ in range(int(n)):
        total+=a;a,b=b,a+b
    return total


def _target_end(row):
    f=_feature(row);t=_target(row);d=int(row.get("day",f.get("day",0)))
    end=t.get("end_occupancy_counts") or {}
    crops=t.get("end_crop_counts",end.get("crops"))
    animals=t.get("end_animal_counts",end.get("animals"))
    if crops is None:
        crops=cohort_counts(f.get("own_crop_cohorts",[]),"crop")
        crops.update(t.get("plant_counts",{}))
        for k in ("crop_end_counts","crop_remove_counts","crop_disappear_counts"):
            crops.subtract(t.get(k) or {})
    if animals is None:
        animals=cohort_counts(f.get("own_animal_cohorts",[]),"species")
        animals.update(t.get("animal_add_counts",{}));animals.subtract(t.get("animal_exit_counts") or {})
    return _counts(crops),_counts(animals)


def _round(x):
    return int(math.floor(x+.5))


class SemanticStrategyPolicy:
    """Static decision library plus bounded public-state economic corrections.

    model is {'rows':[{'day', 'features', 'target'}, ...]}. Offline provenance can
    remain in model metadata, but is stripped from runtime rows at construction.
    """
    def __init__(self,model,config=None):
        if isinstance(model,(str,Path)):
            model=json.loads(Path(model).read_text(encoding="utf-8"))
        self.config=dict(DEFAULT_CONFIG);self.config.update(config or {})
        self.byday=defaultdict(list)
        allowed=("shops_prefix","shops","own_crop_cohorts","own_animal_cohorts",
                 "own_structures","cash","owned_quadrants","land")
        for original in model.get("rows",[]):
            f=_feature(original);d=int(original.get("day",f.get("day",0)))
            row=dict(day=d,features={k:deepcopy(f[k]) for k in allowed if k in f},target=deepcopy(_target(original)))
            # Targets are semantic count fields only. Strip source coordinates,
            # returns and any accidental future-shop fields from the library.
            row["target"]={k:v for k,v in row["target"].items() if k in (
                "plant_counts","animal_add_counts","animal_retire_counts","animal_exit_counts",
                "crop_end_counts","crop_remove_counts","crop_disappear_counts","hands",
                "land_add_count","end_crop_counts","end_animal_counts","end_occupancy_counts",
                "build_counts","remove_structure_counts","target_land_count","owned_quadrants")}
            self.byday[d].append(row)
        if not self.byday:
            raise ValueError("empty_semantic_decision_library")

    def _proposal(self,state,row,values):
        cfg=self.config;d=state["day"];f=_feature(row);t=_target(row)
        desired_c,desired_a=_target_end(row)
        survivors=crop_survivors(state["own_crop_cohorts"],d,cfg["release_age"])
        animals=cohort_counts(state["own_animal_cohorts"],"species")
        plants={};adds={};retires={}
        for sp,r in CROPS.items():
            if d+r["first"]>29: continue
            raw=int(t.get("plant_counts",{}).get(sp,0));deficit=max(0,desired_c.get(sp,0)-survivors[sp])
            # Retained cohort deficits are caught up gradually. A mature annual
            # cohort is absent from survivors, so its replacement is counted.
            correction=max(-cfg["crop_correction_limit"],min(cfg["crop_correction_limit"],
                           _round(cfg["correction_fraction"]*(deficit-raw))))
            n=min(deficit,max(0,raw+correction))
            if n: plants[sp]=n
        for sp,r in ANIMALS.items():
            retire=min(animals[sp],int(t.get("animal_retire_counts",{}).get(sp,0)))
            if retire: retires[sp]=retire
            raw=int(t.get("animal_add_counts",{}).get(sp,0))
            deficit=max(0,desired_a.get(sp,0)-animals[sp])
            correction=max(-cfg["animal_correction_limit"],min(cfg["animal_correction_limit"],
                _round(cfg["correction_fraction"]*(deficit-raw))))
            n=min(deficit,max(0,raw+correction))
            if n and d+r["first"]<=28 and not retire: adds[sp]=n
        target_land=t.get("target_land_count",t.get("owned_quadrants",_land(f)+int(t.get("land_add_count",0))))
        if isinstance(target_land,list):target_land=len(target_land)
        land=min(cfg["land_limit"],max(state["owned_quadrants"],int(target_land)))
        land=min(land,state["owned_quadrants"]+cfg["max_land_add_per_day"])
        structure=Counter(state["own_structures"])
        usedpens=Counter()
        for sp,n in animals.items(): usedpens[ANIMALS[sp]["structure"]]+=n
        empty={k:max(0,structure[k]-usedpens[k]) for k in ("COOP","PASTURE")}
        # Retiring animals still occupy their pen today and tomorrow. No free
        # tile is credited merely because feeding is about to stop.
        free_open=max(0,land*25-sum(survivors.values())-sum(structure.values()))
        capacity=free_open+sum(empty.values())
        accepted_p=Counter();accepted_a=Counter();cost=0.;build=Counter();remove_structure=Counter()
        landcost=sum((1000,2000,4000)[q-1] for q in range(state["owned_quadrants"],land))
        hands_source=int(t.get("hands",0))
        basehands=min(cfg["max_hands"],max(hands_source,_round(6.186+.040*sum(survivors.values())+.123*sum(animals.values()))))
        reserve=cfg["minimum_wage_reserve"]*_hire_cost(basehands)
        # Income already present on the board can finance intraday planting;
        # available cash alone is not the full budget, but credit it cautiously.
        today_output=output_calendar(state["own_crop_cohorts"],state["own_animal_cohorts"],d,release_age=cfg["release_age"])[d]
        for p,n in state.get("available_output",{}).items():today_output[p]=max(today_output[p],n)
        receipts=cfg["same_day_income_credit"]*sum(n*state["prices"][p] for p,n in today_output.items())
        receipts+=sum(n*state["prices"][p] for p,n in state.get("stock",{}).items() if p in PRODUCTS and p!="WHEAT")
        budget=max(0.,state["cash"]+receipts-reserve-landcost)
        bids=[(values.get(sp,0)/(CROPS[sp]["last"]+1),sp,False) for sp,n in plants.items() for _ in range(n)]
        bids += [(values.get(sp,0)/max(1,29-d),sp,True) for sp,n in adds.items() for _ in range(n)]
        for _,sp,is_animal in sorted(bids,key=lambda x:(-x[0],x[1])):
            price=ANIMALS[sp]["cost"] if is_animal else CROPS[sp]["seed"]
            already=accepted_a[sp] if is_animal else accepted_p[sp]
            held=state.get("stock" if is_animal else "seeds",{}).get(sp,0)
            if already<held:price=0
            pen=ANIMALS[sp]["structure"] if is_animal else None
            if price+cost>budget or capacity<=0: continue
            capacity-=1
            if is_animal:
                accepted_a[sp]+=1
                if empty[pen]>0: empty[pen]-=1
                else:
                    build[pen]+=1
                    if free_open: free_open-=1
                    else:
                        other=max(empty,key=lambda k:empty[k]);empty[other]-=1;remove_structure[other]+=1
            else:
                accepted_p[sp]+=1
                if free_open:free_open-=1
                else:
                    other=max(empty,key=lambda k:empty[k]);empty[other]-=1;remove_structure[other]+=1
            cost+=price
        endc=survivors+accepted_p;enda=animals+accepted_a
        # Quantities are not dropped at an arbitrary farm-size threshold. This
        # estimate requests labour, while exact scheduling is left to KB115LT.
        work=1.2*sum(endc.values())+4.1*sum(enda.values())+2.8*sum(accepted_p.values())+5*sum(accepted_a.values())
        p95=cfg["p95_work_factor"]*work
        hands=max(basehands,math.ceil(p95/23)-1)
        hands=min(cfg["max_hands"],max(0,hands))
        return dict(day=d,plant_counts=dict(accepted_p),animal_add_counts=dict(accepted_a),
            animal_retire_counts=retires,target_animals=dict(enda),target_crop_counts=dict(endc),
            build_counts=dict(build),remove_structure_counts=dict(remove_structure),hands=hands,land_add_count=land-state["owned_quadrants"],
            target_land_count=land,estimated_work_p95=round(p95,3),
            estimated_capital_cost=cost+landcost,modeled_free_tiles=capacity)

    def _choose(self,state,history=None,economics=True):
        rows=self.byday.get(state["day"],[])
        if not rows:
            raise ValueError("no_training_rows_for_day_%s"%state["day"])
        nearest=sorted(enumerate(rows),key=lambda ir:(row_distance(state,ir[1],self.config),ir[0]))[:self.config["neighbors"]]
        paths,rival=forecast_market(state,self.config,history)
        values={s:cohort_value(state,s,paths,rival,self.config) for s in (*CROPS,*ANIMALS)}
        candidates=[]
        for index,row in nearest:
            choice=self._proposal(state,row,values)
            value=bundle_value(state,choice,paths,rival,self.config,values) if economics else sum(
                values[s]*n for k in ("plant_counts","animal_add_counts") for s,n in choice[k].items())
            distance=row_distance(state,row,self.config)
            # Economics breaks nearby joint-proposal ties. It cannot select a
            # completely unrelated donor simply by demanding more investments.
            score=-self.config["distance_weight"]*distance+(self.config["economics_weight"]*value if economics else 0)
            candidates.append((score,index,choice,distance,value))
        best=max(candidates,key=lambda x:(x[0],-x[1]))
        return best[2],dict(row_index=best[1],distance=best[3],estimated_incremental_margin=best[4],
            score=best[0],cohort_values={s:round(v,3) for s,v in values.items()},candidates=len(candidates))

    def _advance(self,state,choice):
        """Anonymous cohort accounting for an explicitly modelled suffix."""
        s=deepcopy(state);d=s["day"]
        s["own_crop_cohorts"]=[c for c in s["own_crop_cohorts"] if d-_birth(c)<self.config["release_age"][c["crop"]]]
        s["own_crop_cohorts"].extend(dict(crop=sp,birth=d,count=n) for sp,n in choice["plant_counts"].items())
        ac=[]
        for c in s["own_animal_cohorts"]:
            if c.get("retire_day",99)+1>d: ac.append(c)
        # Retire older production cohorts first in anonymous forecast only.
        # Actual identity selection stays with the tiler and can use phase.
        for sp,n in choice["animal_retire_counts"].items():
            for c in sorted(ac,key=lambda x:_birth(x)):
                if c["species"]!=sp or "retire_day" in c or n<=0: continue
                take=min(n,c["count"]);n-=take
                if take<c["count"]:
                    ac.append(dict(c,count=c["count"]-take));c["count"]=take
                c["retire_day"]=d
        ac.extend(dict(species=sp,birth=d,count=n) for sp,n in choice["animal_add_counts"].items())
        s["own_animal_cohorts"]=ac
        structures=Counter(s["own_structures"]);structures.update(choice.get("build_counts",{}));structures.subtract(choice.get("remove_structure_counts",{}))
        s["own_structures"]=dict(structures);s["owned_quadrants"]=choice["target_land_count"]
        # Forecast cash is a model assumption. Reconciliation is from real cash
        # tomorrow. Credit current planned production with a modest delivery lag.
        out=output_calendar(state["own_crop_cohorts"],state["own_animal_cohorts"],d,release_age=self.config["release_age"])[d]
        s["cash"]=max(0,s["cash"]+sum(n*s["prices"][p] for p,n in out.items())
            -choice["estimated_capital_cost"]-_hire_cost(choice["hands"])
            -sum(cohort_counts(ac,"species").values())*s["prices"]["WHEAT"])
        s["day"]=d+1
        # These credits belong only to the observed initial state; do not spend
        # the same observed shed stock or held output again in every forecast.
        s["available_output"]={};s["stock"]={};s["seeds"]={}
        return s

    def propose(self,observation,memory=None):
        state=public_state(observation);d=state["day"];memory=deepcopy(memory or {})
        if not 0<=d<=29: raise ValueError("outside_season")
        history={}
        recent=[v for key,v in memory.get("public_history",{}).items() if d-3<=int(key)<d]
        if recent:
            history["rival_net_daily"]={p:sum(x.get("rival_harvest",{}).get(p,0) for x in recent)/len(recent) for p in PRODUCTS}
        previous=memory.get("public_snapshot")
        own_net=memory.get("own_net_market_since_snapshot")
        if previous and own_net is not None and previous["day"]<d:
            elapsed=d-previous["day"];dem=demand(previous["shops_prefix"])
            history["rival_net_daily"]={p:(state["inventory"][p]-previous["inventory"][p]
                +elapsed*(6*dem.get(p,0)+(p!="FERTILIZER"))-float(own_net.get(p,0)))/elapsed for p in PRODUCTS}
        today,diag=self._choose(state,history,True)
        forecast=[today];future=self._advance(state,today)
        if self.config["forecast"]:
            while future["day"]<30:
                decision,_=self._choose(future,history,self.config["forecast_economics"])
                forecast.append(decision);future=self._advance(future,decision)
        memory["public_snapshot"]={k:deepcopy(state[k]) for k in ("day","shops_prefix","inventory")}
        memory.pop("own_net_market_since_snapshot",None)
        diag.update(causal_features_only=True,forecast_unrevealed_shops="uniform prior; no actual suffix",
            rival_supply_observed=bool(history),forecast_commitment="today only; future is modelled",
            replacement_rule="annual full-age release; ongoing last tick; actual adapter validates")
        return dict(day=d,today=today,forecast=forecast,memory=memory,diagnostics=diag,
                    replan_day=d+1,next_reveal_day=min(30,3*(d//3+1)))

    @staticmethod
    def observe(observation,memory=None,our_previous_action=None):
        return observe(observation,memory,our_previous_action)


def observe(observation,memory=None,our_previous_action=None):
    """Accumulate successful-looking public rival activity, never private state.

    Harvests are inferred from yield decreases on an unchanged cohort within a
    day; these estimate future deliveries, not verified rival sale quantities.
    Market inventory identifies combined net trades exactly under default town
    consumption intervals. No attempt is made to assign ambiguous trades to a
    player. ``our_previous_action`` is accepted for adapter compatibility but
    requested orders are deliberately not treated as successful transactions.
    """
    out=deepcopy(memory or {});day=int(observation["day"]);step=int(observation.get("step",24*day+int(observation.get("hour",0))))
    farm=observation["farms"][1-int(observation["player"])];cells=[]
    for row in farm.get("tiles",[]):
        for tile in row:
            if not isinstance(tile,dict): cells.append(None);continue
            species=tile.get("crop") or tile.get("animal")
            if species not in CROPS and species not in ANIMALS: cells.append(None);continue
            cells.append(dict(species=species,birth=int(tile.get("planted_day",tile.get("placed_day",0))),
                held=int(tile.get("yield_units",0)),fed=bool(tile.get("fed_today",False)),
                cared=bool(tile.get("cared_today",False)),fert=bool(tile.get("fertilizer_available",False))))
    now=dict(step=step,day=day,cells=cells,inventory=dict(observation.get("market",{}).get("inventory",{})),shops=_shops(observation))
    prev=out.get("last_public_tick")
    if prev and prev["step"]==step:
        return out
    if prev and prev["step"]+1==step:
        row=out.setdefault("public_history",{}).setdefault(str(prev["day"]),{})
        row["observed_ticks"]=row.get("observed_ticks",0)+1
        flow=Counter(row.get("combined_net_market",{}));dem=demand(prev["shops"])
        for p in PRODUCTS:
            if p not in now["inventory"] or p not in prev["inventory"]:continue
            consume=(dem.get(p,0) if prev["step"]%4==0 else 0)+(int(p!="FERTILIZER") if prev["step"]%24==0 else 0)
            flow[p]+=now["inventory"][p]-prev["inventory"][p]+consume
        row["combined_net_market"]=dict(flow)
        if prev["day"]==day:
            harvest=Counter(row.get("rival_harvest",{}));feed=Counter(row.get("rival_feed",{}));care=Counter(row.get("rival_care",{}))
            planting=Counter(row.get("rival_established",{}))
            for old,new in zip(prev["cells"],cells):
                if old and old["species"] in CROPS and not CROPS[old["species"]]["interval"]:
                    changed=new is None or (old["species"],old["birth"])!=(new["species"],new["birth"])
                    age=day-old["birth"]
                    if changed and CROPS[old["species"]]["first"]<=age<=CROPS[old["species"]]["last"]:
                        harvest[old["species"]]+=old["held"]
                if new is None:continue
                same=old is not None and old["species"]==new["species"] and old["birth"]==new["birth"]
                sp=new["species"]
                if not same:
                    planting[sp]+=1;continue
                if old["held"]>new["held"]:
                    # Crop expiry can also lower yield one unit per two turns.
                    # Ignore age-past-lifespan decreases rather than inventing
                    # rival deliveries from rotting plants.
                    alive=sp in ANIMALS or day-new["birth"]<=CROPS[sp]["last"]
                    if alive: harvest[ANIMALS[sp]["product"] if sp in ANIMALS else sp]+=old["held"]-new["held"]
                if sp in ANIMALS:
                    feed[sp]+=int(new["fed"] and not old["fed"])
                    care[sp]+=int(new["cared"] and not old["cared"])
                    if old["fert"] and not new["fert"]:harvest["FERTILIZER"]+=1
            row.update(rival_harvest=dict(harvest),rival_feed=dict(feed),rival_care=dict(care),rival_established=dict(planting))
    out["last_public_tick"]=now
    return out

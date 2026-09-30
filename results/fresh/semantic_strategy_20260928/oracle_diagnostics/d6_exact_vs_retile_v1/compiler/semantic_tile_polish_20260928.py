"""Optional suffix-trajectory layout polish using only a compiled tile plan.

Two unlocked, empty tiles at a day boundary may exchange their entire future
trajectories.  This preserves every crop/animal count and every cohort date; it
does not move a living cohort.  Shortlisting uses future same-day work adjacency,
then admission uses a deterministic angular-sweep route surrogate inspired by
KB115LT's tier search.  Surrogate improvement is not gameplay evidence.
"""
import argparse
import copy
import json
import math
from collections import Counter
from pathlib import Path

from semantic_tile_allocator_20260928 import DIST, SHED_DISTANCE, SECTOR

CROPS = {"WH":"WHEAT", "CA":"CARROT", "ME":"MELON", "ST":"STRAWBERRY", "TO":"TOMATO"}
FIRST = {"WHEAT":2, "CARROT":2, "MELON":10, "STRAWBERRY":10, "TOMATO":8}
INTERVAL = {"STRAWBERRY":2, "TOMATO":1}
ANIMAL = {"GOOSE":(4,1), "COW":(8,2), "SHEEP":(6,3)}
ANGLE = tuple(math.atan2(t//10-4.5,t%10-4.5) for t in range(100))


def _int_map(value):
    return {int(k):v for k,v in value.items()}


def work_calendar(plan):
    """Approximate daily visit work from cohort clocks, with no tape upkeep read."""
    n = plan["n"]
    work = [[0.0]*100 for _ in range(n)]
    births, animals, placed = {}, {}, {}
    prior_struct = {}
    for d in range(n):
        start_animals = animals
        end_animals = _int_map(plan["animals_by_day"][d])
        structures = _int_map(plan["struct_by_day"][d])
        end_next = _int_map(plan["animals_by_day"][min(d+1,n-1)])
        newplants = _int_map(plan["plant"][d])
        harvests = set(plan["harv_tiles"][d])
        for t,lab in enumerate(plan["board"][d]):
            crop = CROPS.get(lab)
            if crop:
                pd = births.get(t, (crop, max(0,d-1)))[1]
                age = d-pd
                if crop in INTERVAL:
                    step = INTERVAL[crop]
                    production = age >= FIRST[crop] and (age-FIRST[crop])%step==0 and age<=FIRST[crop]+3*step
                    eve = age+1 >= FIRST[crop] and (age+1-FIRST[crop])%step==0 and age+1<=FIRST[crop]+3*step
                    # Visits are discrete: fractional water on every tile/day
                    # would erase the same-cohort scheduling benefit we seek.
                    water = eve or age % 2 == 0
                    work[d][t] += (1.0 if water else 0.0) + (1.0 if production else 0.0) + (.65 if eve else 0.0)
                else:
                    work[d][t] += 1.0 if age % 2 == 0 else 0.0
                    if crop in ("WHEAT","CARROT") and age in (1,2):
                        work[d][t] += .7 + (1.0 if age % 2 else 0.0)
                if t in harvests and crop not in INTERVAL:
                    work[d][t] += 1.0
            sp = start_animals.get(t)
            if sp:
                retiring = end_animals.get(t)!=sp or end_next.get(t)!=sp
                if not retiring:
                    first,interval = ANIMAL[sp]
                    age=d-placed.get(t,0)
                    production=age>=first and (age-first)%interval==0
                    work[d][t] += 2.0 + .6 + (1.0 if production else 0.0)
                else:
                    work[d][t] += .8  # last held output / fertilizer; no FEED/CARE
        for t,crop in newplants.items():
            work[d][t] += 2.0  # PLANT and same-day survival water
            if plan["board"][d][t] in ("ST","TO","pa","co") and t not in start_animals:
                work[d][t] += 1.0
            births[t]=(crop,d)
        for t,kind in structures.items():
            if prior_struct.get(t)!=kind:
                work[d][t] += 1.0
        for t,sp in end_animals.items():
            if start_animals.get(t)!=sp:
                work[d][t] += 3.0  # PLACE, FEED, CARE
                placed[t]=d
        animals,prior_struct=end_animals,structures
    return work


def route_cost(work, hands, offsets=4):
    """Angular balanced work arcs, Manhattan nearest-neighbor route within each.

    The actual KB115LT uses ops+1.5 sweep weights and tests rotations, then route
    relocation.  This intentionally cheaper surrogate shares its day/route
    geometry while avoiding any recorded worker assignment or action sequence.
    """
    active=sorted((t for t in range(100) if work[t]>.01),key=lambda t:(ANGLE[t],t))
    if not active:
        return 0.0
    k=min(len(active),max(1,int(hands)+1))
    total=sum(work[t]+1.5 for t in active)
    best=float("inf")
    for offset in sorted(set(i*len(active)//max(1,offsets) for i in range(max(1,offsets)))):
        order=active[offset:]+active[:offset]
        arcs,current,acc=[],[],0.0
        for t in order:
            current.append(t)
            acc += work[t]+1.5
            if acc>=total*(len(arcs)+1)/k and len(arcs)<k-1:
                arcs.append(current); current=[]
        arcs.append(current)
        cost=0.0
        for arc in arcs:
            if not arc:
                continue
            rest=set(arc)
            first=min(rest,key=lambda t:(SHED_DISTANCE[t],t))
            walk=SHED_DISTANCE[first]
            hop=0
            p=first; rest.remove(first)
            while rest:
                t=min(rest,key=lambda t:(DIST[p][t],t))
                travel=DIST[p][t]
                walk+=travel; hop+=max(0,travel-1)
                rest.remove(t); p=t
            service=sum(work[t] for t in arc)
            finish=1.5+1.0+walk+service  # starts/one pickup allowance
            overtime=max(0.0,finish-24)
            cost+=walk+service+.5*hop+.5*SHED_DISTANCE[p]+25*overtime
        best=min(best,cost)
    return best


def _map_keys(mapping,a,b):
    result={}
    for k,v in mapping.items():
        t=int(k)
        result[str(b if t==a else a if t==b else t)]=v
    return result


def swap_suffix(plan,day,a,b):
    """Mutate an explicitly empty-boundary suffix, including review metadata."""
    if plan["board"][day][a]!=" ." or plan["board"][day][b]!=" .":
        raise ValueError("suffix swaps require two empty unlocked boundary tiles")
    if a==b:
        return
    swap=lambda t:b if int(t)==a else a if int(t)==b else int(t)
    for d in range(day,plan["n"]):
        for field in ("plant","struct_by_day","animals_by_day"):
            plan[field][d]=_map_keys(plan[field][d],a,b)
        plan["board"][d][a],plan["board"][d][b]=plan["board"][d][b],plan["board"][d][a]
        plan["harv_tiles"][d]=sorted(swap(t) for t in plan["harv_tiles"][d])
        plan["removals"][d]=[[swap(r[0]),*r[1:]] for r in plan["removals"][d]]
    plan["events"]=[[e[0],swap(e[1]) if e[0]>=day else e[1],e[2]] for e in plan["events"]]
    meta=plan.get("planner_metadata") or {}
    for row in meta.get("daily",[]):
        if row["day"]<day:
            continue
        row["end_board"][a],row["end_board"][b]=row["end_board"][b],row["end_board"][a]
        row["tiles"]=_map_keys(row["tiles"],a,b)
        for key in ("retirements_started","animal_exits"):
            for entry in row.get(key,[]):
                entry["tile"]=swap(entry["tile"])
    for warning in meta.get("warnings",[]):
        if warning.get("day",-1)>=day and "tile" in warning:
            warning["tile"]=swap(warning["tile"])


def _signature(plan):
    return {"plant":[dict(Counter(x.values())) for x in plan["plant"]],
            "structures":[dict(Counter(x.values())) for x in plan["struct_by_day"]],
            "animals":[dict(Counter(x.values())) for x in plan["animals_by_day"]],
            "board":[dict(Counter(x)) for x in plan["board"]],
            "harv":[len(x) for x in plan["harv_tiles"]],
            "removals":[dict(Counter((x[1],x[2]) for x in day)) for day in plan["removals"]],
            "hands":plan["hands"]}


def polish_plan(plan, rounds=2, finalists=16, route_offsets=4):
    """Return an independent improved-or-identical plan and surrogate audit."""
    result=copy.deepcopy(plan)
    handoff=int((result.get("planner_metadata") or {}).get("handoff_day",11))
    work=work_calendar(result)
    scores=[route_cost(work[d],result["hands"][d],route_offsets) for d in range(result["n"])]
    start=sum(scores[handoff:])
    audit=dict(initial_surrogate=start,final_surrogate=start,accepted=[],evaluated=0,
               model="daily ops+1.5 angular arcs and Manhattan routes; heuristic forecast, not gameplay")
    neighbors={t:[(u,1/DIST[t][u]) for u in range(100) if 0<DIST[t][u]<=2] for t in range(100)}
    for _ in range(rounds):
        proposals=[]
        for d in range(handoff,result["n"]):
            empty=[t for t,lab in enumerate(result["board"][d]) if lab==" ."]
            for ii,a in enumerate(empty):
                for b in empty[ii+1:]:
                    if all(work[k][a]==work[k][b] for k in range(d,result["n"])):
                        continue
                    delta=0.0
                    for k in range(d,result["n"]):
                        wa,wb=work[k][a],work[k][b]
                        delta+=.2*(wb-wa)*(SHED_DISTANCE[a]-SHED_DISTANCE[b])
                        # Co-activity attracts work toward nearby simultaneous
                        # visits, rather than simply toward the shed.
                        ca=sum(min(1,work[k][u])*weight for u,weight in neighbors[a] if u!=b)
                        cb=sum(min(1,work[k][u])*weight for u,weight in neighbors[b] if u!=a)
                        delta-=.8*(min(1,wb)-min(1,wa))*(ca-cb)
                    proposals.append((delta,d,a,b))
        proposals.sort()
        best=None
        # Include only a bounded pool; no episode-seeded randomness or outcomes.
        for _,d,a,b in proposals[:max(1,finalists)]:
            changed=[]
            for k in range(d,result["n"]):
                row=list(work[k]); row[a],row[b]=row[b],row[a]
                changed.append(route_cost(row,result["hands"][k],route_offsets))
            gain=sum(scores[d:])-sum(changed)
            audit["evaluated"]+=1
            if gain>1e-9 and (best is None or (gain,-d,-a,-b)>(best[0],-best[1],-best[2],-best[3])):
                best=(gain,d,a,b,changed)
        if best is None:
            break
        gain,d,a,b,changed=best
        swap_suffix(result,d,a,b)
        for k in range(d,result["n"]):
            work[k][a],work[k][b]=work[k][b],work[k][a]
        scores[d:]=changed
        audit["accepted"].append(dict(day=d,tile_a=a,tile_b=b,surrogate_gain=gain))
    audit["final_surrogate"]=sum(scores[handoff:])
    assert _signature(result)==_signature(plan), "suffix transform changed semantic counts"
    assert result["board"][:handoff+1]==plan["board"][:handoff+1], "changed opening handoff"
    result.setdefault("planner_metadata",{})["suffix_polish"]=audit
    return result,audit


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs",required=True)
    ap.add_argument("--out",required=True)
    ap.add_argument("--rounds",type=int,default=2)
    ap.add_argument("--finalists",type=int,default=16)
    a=ap.parse_args()
    plans=json.loads(Path(a.inputs).read_text(encoding="utf-8"))
    out={}; audits={}
    for ep,plan in plans.items():
        out[ep],audits[ep]=polish_plan(plan,a.rounds,a.finalists)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,separators=(",",":")),encoding="utf-8")
    dest.with_suffix(".polish_audit.json").write_text(json.dumps(audits,indent=2),encoding="utf-8")
    print(json.dumps(dict(worlds=len(out),accepted=sum(len(x["accepted"]) for x in audits.values()),
                         surrogate_gain=sum(x["initial_surrogate"]-x["final_surrogate"] for x in audits.values()))))


if __name__=="__main__":
    main()

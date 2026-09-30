"""Compile coordinate-free daily farm changes into a KB115LT TilePlanView.

The only input coordinates are the already-played opening/public D11 farm.
No future source tile, recorded action, sale, or opponent outcome is consulted.
The full daily plan also retains physically present animals marked for retirement.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CROP_LABEL = {"WHEAT": "WH", "CARROT": "CA", "TOMATO": "TO", "STRAWBERRY": "ST", "MELON": "ME"}
LABEL_CROP = {v: k for k, v in CROP_LABEL.items()}
FIRST = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
LIFE = {"WHEAT": 4, "CARROT": 3, "TOMATO": 11, "STRAWBERRY": 16, "MELON": 12}
ANIMAL_LABEL = {"COW": "co", "SHEEP": "sh", "GOOSE": "go"}
STRUCTURE = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}


def distance(t, u):
    return abs(t % 10 - u % 10) + abs(t // 10 - u // 10)


def shed_distance(t):
    return min(distance(t, s) for s in (44, 45, 54, 55))


def label(cell):
    if cell.get("locked"):
        return " L"
    if cell.get("animal"):
        return ANIMAL_LABEL[cell["animal"]]
    if cell.get("crop"):
        return CROP_LABEL[cell["crop"]]
    if cell.get("kind") == "PASTURE":
        return "pa"
    if cell.get("kind") == "COOP":
        return "co"
    return " ."


def _counts(value):
    return {k: int(v) for k, v in (value or {}).items() if int(v)}


def fallback_assign(day, requests, available, state, config):
    """Stable maturity-safe baseline; the independent allocator adds joint scoring."""
    result = []
    free = set(available)
    for req in requests:
        kind = req["kind"]
        def score(t):
            reuse = state[t].get("released_kind") == kind
            peers = [u for u, c in state.items() if c.get("crop") == kind]
            group = min((distance(t, u) for u in peers + result), default=0)
            return (-5 * reuse + 0.4 * shed_distance(t) + 0.7 * group, t)
        t = min(free, key=score)
        free.remove(t)
        result.append(t)
    return result


def compile_plan(semantic, *, variant="reuse", config=None, lifetimes=None,
                 use_first_harvest_counts=False):
    """Return executable interface plus detailed daily desired physical states."""
    cfg = dict(config or {})
    cfg.setdefault("variant", variant)
    if lifetimes is None and not cfg.get("legacy_fifo", False):
        from semantic_tile_lifetimes_20260928 import solve_lifetimes
        lifetimes = solve_lifetimes(semantic,use_first_harvest_counts=use_first_harvest_counts)
    n = int(semantic.get("n", 30))
    handoff = int(semantic.get("handoff_day", 11))
    initial = semantic["initial_state"]
    prefix = copy.deepcopy(semantic["opening_plan"])
    state = {t: {} for t in range(100)}
    for t, cell in initial["tiles"].items():
        state[int(t)] = copy.deepcopy(cell)
    for t, cell in state.items():
        if cell.get("crop") in ("STRAWBERRY", "TOMATO"):
            birth = cell["planted_day"]
            cell["first_harvest_done"] = any(t in prefix["harv_tiles"][d] for d in range(birth+1, handoff))
    birth_paths = {}
    if lifetimes is not None:
        from semantic_tile_lifetimes_20260928 import initial_group
        initial_paths = {}
        for crop, paths in lifetimes["by_crop"].items():
            for p in paths:
                target = initial_paths if p["initial"] else birth_paths
                key = ((crop,p["birth"],p["prior_first_harvest"]) if p["initial"] else (crop,p["birth"]))
                target.setdefault(key,[]).extend([dict(p,count=1) for _ in range(p["count"])])
        def path_priority(p):
            return (-(n+1 if p["exit_day"] is None else p["exit_day"]),
                    n+1 if p["first_harvest"] is None else p["first_harvest"])
        for key,paths in initial_paths.items():
            crop,birth,prior=key
            tiles=[t for t,c in state.items() if c.get("crop")==crop and initial_group(c,t,semantic)==(birth,True,prior)]
            assert len(paths)==len(tiles),(key,len(paths),len(tiles))
            # Same-age observed crops can have different current yields. A
            # public readiness bound must stay on its actual tile even though
            # future lifetimes are anonymous. Tightest bounds first have nested
            # eligible path sets; the remaining preference is unchanged.
            pending = sorted(paths,key=path_priority)
            ordered_tiles = sorted(tiles,key=lambda t:(
                -state[t].get("harvest_not_before", handoff),shed_distance(t),t))
            for t in ordered_tiles:
                earliest = state[t].get("harvest_not_before", handoff)
                eligible = next((i for i,p in enumerate(pending)
                    if p["exit_type"] != "harvest" or p["exit_day"] is None or p["exit_day"] >= earliest),None)
                if eligible is None:
                    raise ValueError(f"Initial {crop} tile {t}: no lifetime respects public harvest readiness {earliest}")
                state[t]["lifecycle"]=pending.pop(eligible)
        for paths in birth_paths.values():
            paths.sort(key=path_priority)
    out = {
        "n": n,
        "plant": copy.deepcopy(prefix["plant"][:handoff]) + [{} for _ in range(n-handoff)],
        "events": [list(e) for e in prefix["events"] if int(e[0]) < handoff],
        "board": copy.deepcopy(prefix["board"][:handoff]) + [[] for _ in range(n-handoff)],
        "struct_by_day": copy.deepcopy(prefix["struct_by_day"][:handoff]) + [{} for _ in range(n-handoff)],
        "animals_by_day": copy.deepcopy(prefix["animals_by_day"][:handoff]) + [{} for _ in range(n-handoff)],
        "harv_tiles": copy.deepcopy(prefix["harv_tiles"][:handoff]) + [[] for _ in range(n-handoff)],
        "removals": copy.deepcopy(prefix["removals"][:handoff]) + [[] for _ in range(n-handoff)],
        "land_day": copy.deepcopy(prefix.get("land_day", {})),
        "hands": list(prefix["hands"][:handoff]) + [0]*(n-handoff),
        "cum_sold": copy.deepcopy(prefix.get("cum_sold", []))[:handoff],
    }
    daily = []
    warnings = []
    try:
        from semantic_tile_allocator_20260928 import assign_tiles
    except ImportError:
        assign_tiles = fallback_assign

    def select(candidates, count, key, day, what):
        if len(candidates) < count:
            raise ValueError(f"D{day} {what}: need {count}, available {len(candidates)}")
        return sorted(candidates, key=key)[:count]

    def clear_crop(t):
        c = state[t]
        state[t] = {"released_kind": c["crop"], "released_birth": c.get("planted_day", 0)}

    def releases(day,crop,kind,count):
        if lifetimes is None:
            cand=[t for t,c in state.items() if c.get("crop")==crop]
            return select(cand,count,lambda t:(state[t].get("planted_day",0),t),day,kind+" "+crop)
        chosen=[t for t,c in state.items() if c.get("crop")==crop and c["lifecycle"]["exit_day"]==day
                and c["lifecycle"]["exit_type"]==kind]
        assert len(chosen)==count,(day,crop,kind,count,chosen)
        return sorted(chosen)

    for day in range(handoff, n):
        change = semantic["days"][day]
        out["board"][day] = [label(state[t]) for t in range(100)]
        out["hands"][day] = int(change["hands"])
        # Land additions are anonymous; use the engine's standard quadrant order.
        for _ in range(int(change.get("land_add_count", 0))):
            q = next((q for q in ("NE", "SW", "SE") if q not in out["land_day"]), None)
            if q is None:
                raise ValueError("land additions exceed quadrants")
            out["land_day"][q] = day
            for t, cell in state.items():
                quad = ("S" if t//10 >= 5 else "N") + ("E" if t%10 >= 5 else "W")
                if quad == q:
                    cell.pop("locked", None)

        # Explicit first-unfed day, while animal continues physically occupying its pen.
        retired_today = []
        pending_retirements = {}
        def mark_retiring(t, sp):
            state[t]["retiring_since"] = day
            retired_today.append({"tile":t, "animal":sp, "first_unfed_day":day, "expected_exit_day":day+1})

        for sp, count in _counts(change.get("animal_retire_counts")).items():
            cand = [t for t,c in state.items() if c.get("animal")==sp and "retiring_since" not in c]
            def retire_score(t):
                if cfg.get("retire_policy", "phase") == "distance":
                    return (-shed_distance(t), -state[t].get("placed_day",0), t)
                first, interval = {"COW":(8,2), "SHEEP":(6,3), "GOOSE":(4,1)}[sp]
                pd=state[t].get("placed_day",0)
                remaining=sum(night+1-pd>=first and (night+1-pd-first)%interval==0 for night in range(day,n-1))
                return (remaining, -shed_distance(t), -pd, t)
            # A placed animal can also miss its first feed today. Preserve the
            # existing-cohort preference, but defer a count deficit until the
            # anonymous same-day additions have been assigned their pens.
            deficit = max(0, count-len(cand))
            if deficit > int(change.get("animal_add_counts", {}).get(sp, 0)):
                select(cand, count, retire_score, day, "retire "+sp)
            if deficit:
                pending_retirements[sp] = deficit
            chosen = select(cand, min(count, len(cand)), retire_score, day, "retire "+sp)
            for t in chosen:
                mark_retiring(t, sp)

        # First harvest can occur on the same day as an intentional DIG. The
        # anonymous lifecycle schedule handles that before releasing the site.
        if lifetimes is not None:
            first_counts=Counter(c["crop"] for c in state.values()
                                 if c.get("crop") and c["lifecycle"]["first_harvest"]==day)
            if lifetimes.get("use_first_harvest_counts",True):
                assert dict(first_counts)==_counts(change.get("first_harvest_counts"))
        else:
            first_counts=_counts(change.get("first_harvest_counts"))
        for crop, count in first_counts.items():
            if lifetimes is not None:
                chosen=[t for t,c in state.items() if c.get("crop")==crop and c["lifecycle"]["first_harvest"]==day]
                assert len(chosen)==count,(day,crop,"first_harvest",count,chosen)
            else:
                cand = [t for t,c in state.items() if c.get("crop")==crop and not c.get("first_harvest_done")]
                chosen = select(cand, count, lambda t:(state[t].get("planted_day",0),t), day, "first harvest "+crop)
            for t in chosen:
                if lifetimes is not None:
                    assert day-state[t]["planted_day"]>=FIRST[crop]
                state[t]["first_harvest_done"]=True
                out["harv_tiles"][day].append(t)
        # The semantic compiler chooses anonymous lifetimes, never source tiles.
        for crop, count in _counts(change.get("crop_remove_counts")).items():
            chosen = releases(day,crop,"remove",count)
            for t in chosen:
                out["removals"][day].append([t,crop,state[t].get("planted_day",0)])
                clear_crop(t)
        for crop, count in _counts(change.get("crop_end_counts")).items():
            chosen = releases(day,crop,"harvest",count)
            for t in chosen:
                age=day-state[t].get("planted_day",0)
                if age < FIRST[crop]:
                    warnings.append({"day":day,"kind":"immature_end","crop":crop,"age":age,"tile":t})
                out["harv_tiles"][day].append(t)
                clear_crop(t)
        # Expiry/drought removes a cohort without a successful one-time harvest
        # or an explicit DIG. This is a separate semantic change, not an asset
        # the allocator may keep indefinitely for its own convenience.
        for crop,count in _counts(change.get("crop_disappear_counts")).items():
            if lifetimes is not None:
                for t in releases(day,crop,"disappear",count):
                    clear_crop(t)
                continue
            for _ in range(count):
                cand=[t for t,c in state.items() if c.get("crop")==crop]
                future_first=sum(row.get("first_harvest_counts",{}).get(crop,0) for row in semantic["days"][day+1:])
                future_births=sum(row.get("plant_counts",{}).get(crop,0) for row in semantic["days"][day:])
                unseen=sum(not state[t].get("first_harvest_done") for t in cand)
                surplus=unseen+future_births-future_first
                def disappear_key(t):
                    c=state[t]
                    age=day-c.get("planted_day",0)
                    # A source seedling loss is a count-level instruction. Do
                    # not consume an old cohort reserved by tomorrow's removals
                    # when the anonymous schedule can instead lose a seedling.
                    early_loss=(age<=2 and surplus>0 and not c.get("first_harvest_done"))
                    protected=(crop in ("STRAWBERRY","TOMATO") and not c.get("first_harvest_done") and surplus<=0)
                    return (protected, not early_loss, c.get("planted_day",0),t)
                t=select(cand,1,disappear_key,day,"disappear "+crop)[0]
                clear_crop(t)
        for kind, count in _counts(change.get("remove_structure_counts")).items():
            cand=[t for t,c in state.items() if c.get("kind")==kind and not c.get("animal")]
            chosen=select(cand,count,lambda t:(-shed_distance(t),t),day,"remove structure "+kind)
            for t in chosen:
                state[t]={"released_kind":kind}

        requests=[]
        for kind,count in sorted(_counts(change.get("build_counts")).items()):
            requests.extend([{"kind":kind,"category":"structure"} for _ in range(count)])
        for crop,count in sorted(_counts(change.get("plant_counts")).items()):
            paths=birth_paths.get((crop,day)) if lifetimes is not None else None
            if paths is not None:
                assert len(paths)==count
            requests.extend([{"kind":crop,"category":"crop","duration":LIFE[crop],
                              "lifecycle":paths[i] if paths is not None else None} for i in range(count)])
        available=[t for t,c in state.items() if not any(c.get(k) for k in ("crop","animal","kind","locked"))]
        if len(requests)>len(available):
            raise ValueError(f"D{day} capacity: {len(requests)} plant/build requests but {len(available)} free tiles")
        assigned=assign_tiles(day,requests,available,state,cfg) if requests else []
        assert len(assigned)==len(requests) and len(set(assigned))==len(assigned)
        for req,t in zip(requests,assigned):
            if t not in available:
                raise ValueError("allocator returned occupied tile")
            if req["category"]=="crop":
                crop=req["kind"]
                state[t]={"crop":crop,"planted_day":day}
                if req.get("lifecycle") is not None:
                    state[t]["lifecycle"]=copy.deepcopy(req["lifecycle"])
                out["plant"][day][str(t)]=crop
                out["events"].append([day,t,crop])
            else:
                state[t]={"kind":req["kind"],"built_day":day}
        for sp,count in sorted(_counts(change.get("animal_add_counts")).items()):
            cand=[t for t,c in state.items() if c.get("kind")==STRUCTURE[sp] and not c.get("animal")]
            chosen=select(cand,count,lambda t:(shed_distance(t),t),day,"place "+sp)
            for t in chosen:
                state[t].update(animal=sp,placed_day=day)

        for sp, count in pending_retirements.items():
            cand = [t for t,c in state.items() if c.get("animal")==sp
                    and c.get("placed_day")==day and "retiring_since" not in c]
            for t in select(cand, count, lambda t:(-shed_distance(t),t), day, "retire new "+sp):
                mark_retiring(t, sp)

        # Escape happens at the evening refresh, after daytime work.
        exits=[]
        for sp,count in _counts(change.get("animal_exit_counts")).items():
            cand=[t for t,c in state.items() if c.get("animal")==sp]
            chosen=select(cand,count,lambda t:(state[t].get("retiring_since",99),-shed_distance(t),t),day,"exit "+sp)
            for t in chosen:
                if state[t].get("retiring_since") != day-1:
                    warnings.append({"day":day,"tile":t,"kind":"exit_without_two_day_retirement","animal":sp})
                exits.append({"tile":t,"animal":sp})
                state[t]={"kind":STRUCTURE[sp],"last_animal":sp}
        out["struct_by_day"][day]={str(t):c["kind"] for t,c in state.items() if c.get("kind") in ("COOP","PASTURE")}
        out["animals_by_day"][day]={str(t):c["animal"] for t,c in state.items() if c.get("animal")}
        out["harv_tiles"][day]=sorted(set(out["harv_tiles"][day]))
        daily.append({"day":day,"hands":out["hands"][day],"retirements_started":retired_today,"animal_exits":exits,
                      "end_board":[label(state[t]) for t in range(100)],
                      "tiles":{str(t):{k:v for k,v in c.items() if not k.startswith("released_")} for t,c in state.items()}})
        expected=change.get("end_occupancy_counts")
        if expected:
            actual={"crops":dict(Counter(c["crop"] for c in state.values() if c.get("crop"))),
                    "structures":dict(Counter(c["kind"] for c in state.values() if c.get("kind") in ("COOP","PASTURE"))),
                    "animals":dict(Counter(c["animal"] for c in state.values() if c.get("animal")))}
            for key,counts in actual.items():
                if counts != expected[key]:
                    raise ValueError(f"D{day} {key} conservation: {counts} != {expected[key]}")
    out["planner_metadata"]={"version":"semantic_tiles_20260928","variant":variant,"config":cfg,
        "source":"coordinate-free counts plus public handoff state","handoff_day":handoff,
        "input_contract":"timing_extended" if lifetimes is None or lifetimes.get("use_first_harvest_counts",True) else "strict",
        "anonymous_lifetimes":lifetimes is not None,"warnings":warnings,"daily":daily}
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs",default="results/fresh/semantic_tile_20260928/semantic_inputs_strict.json")
    ap.add_argument("--out")
    ap.add_argument("--variant",default="reuse")
    ap.add_argument("--config",default="{}")
    ap.add_argument("--lifetimes",help="Optional cached anonymous_lifetimes.json; otherwise solved from counts")
    ap.add_argument("--use-recorded-first-harvests",action="store_true",help="Diagnostic extended contract only")
    args=ap.parse_args()
    src=Path(args.inputs)
    inp=json.loads(src.read_text(encoding="utf-8"))
    worlds=inp.get("worlds",inp)
    paths=json.loads(Path(args.lifetimes).read_text(encoding="utf-8")) if args.lifetimes else None
    if paths is not None:
        paths=paths.get("worlds",paths)
    plans={}
    for ep,s in worlds.items():
        plans[str(ep)]=compile_plan(s,variant=args.variant,config=json.loads(args.config),
                                    lifetimes=paths[str(ep)] if paths is not None else None,
                                    use_first_harvest_counts=args.use_recorded_first_harvests)
    dst=Path(args.out or f"results/fresh/semantic_tile_20260928/plans/{args.variant}.json")
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(plans,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"worlds":len(plans),"path":str(dst),"sha256":hashlib.sha256(dst.read_bytes()).hexdigest(),
                      "warnings":sum(len(p["planner_metadata"]["warnings"]) for p in plans.values())}))


if __name__=="__main__":
    main()

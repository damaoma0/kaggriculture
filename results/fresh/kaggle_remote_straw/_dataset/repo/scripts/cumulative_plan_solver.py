"""Compile timed cumulative-output targets into an aggregate farm plan.

This is deliberately a *production* compiler, not a router.  It turns a
day-boundary snapshot plus targets at several future checkpoints into integer
cohort decisions.  The result says which work must happen each day, but marks
movement/routing as unresolved: a daily action count is not a proof that a
particular set of workers can visit all those tiles.

Input is JSON.  The small public schema is documented in
docs/cumulative_plan_solver.md.  It accepts native board tiles in ``tiles`` or
an already-normalised ``cohorts`` list, which makes it usable before the replay
extractor's schema is frozen.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from cumulative_engine_profiles import ENGINE, engine_profile as _engine_profile

CROPS = {
    "WHEAT": (2, 4, 0, 6, False), "CARROT": (2, 3, 0, 4, False),
    "TOMATO": (8, 8, 1, 4, True), "STRAWBERRY": (10, 10, 2, 4, True),
    "MELON": (10, 12, 0, 6, False),
}
ANIMALS = {
    "GOOSE": (4, 1, 4, "EGG"), "COW": (8, 2, 6, "MILK"),
    "SHEEP": (6, 3, 6, "WOOL"),
}
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]



def _days(snapshot):
    return list(range(int(snapshot["day"]), int(snapshot.get("season_days", 30))))


def _tile_cohorts(snapshot):
    if snapshot.get("cohorts"):
        out=[]
        for raw in snapshot['cohorts']:
            c=dict(raw);kind=c.get('cohort_kind',c.get('kind'));typ=c.get('type',c.get('crop',c.get('animal')))
            if kind=='crop' and typ in ENGINE.CROPS:
                native=ENGINE._new_plant(typ,int(c['planted_day']),24)
                native.update({k:v for k,v in c.items() if k!='kind'});native.update(cohort_kind='crop',type=typ)
            elif kind=='animal' and typ in ENGINE.ANIMALS:
                native=ENGINE._new_animal(typ,int(c['placed_day']))
                native.update({k:v for k,v in c.items() if k!='kind'});native.update(cohort_kind='animal',type=typ)
            elif c.get('crop') or c.get('animal'):
                native=dict(c,cohort_kind='crop' if c.get('crop') else 'animal',type=typ)
            else:raise ValueError('cohort must describe a crop or animal')
            out.append(native)
        return out
    out = []
    tiles = snapshot.get("tiles", [])
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("crop"):
                out.append(dict(t, cohort_kind="crop", type=t["crop"]))
            elif t.get("animal"):
                out.append(dict(t, cohort_kind="animal", type=t["animal"]))
    return out


def checkpoint_to_snapshot(checkpoint):
    """Normalise the replay-corpus checkpoint schema supplied by the builder.

    The converter is intentionally read-only: it uses only the checkpoint
    observation, never later segments or future shops.  Callers supply funded
    purchase budgets and a travel reserve because those are policy choices, not
    facts recoverable from a board image.
    """
    obs = checkpoint["observation"]
    seat = int(obs.get("player", 0))
    farm = obs["farms"][seat]
    private = obs.get("private", {})
    shed = private.get("shed", {})
    fixed = 0
    for row in farm["tiles"]:
        for tile in row:
            if tile not in (None, "LOCKED") and not (isinstance(tile, dict) and (tile.get("crop") or tile.get("animal"))): fixed += 1
    return {
        "day": int(checkpoint.get("day", obs["day"])), "season_days": 30,
        "tiles": farm["tiles"],
        "land_capacity": sum(t != "LOCKED" for row in farm["tiles"] for t in row) - fixed,
        "fixed_land_occupancy": fixed,
        "seeds": private.get("seeds", {}), "fertilizer": int(shed.get("FERTILIZER", 0)),
        "wheat": int(shed.get("WHEAT", 0)),
        # Hands are reset at midnight.  A day-boundary board's hands list is
        # therefore not tomorrow's workforce and must never be extrapolated.
        # The caller supplies a funded per-day hire schedule if it wants more
        # than the farmer's 24 actions.
        "daily_action_capacity": 24,
        "already_produced": checkpoint.get("cumulative_output", checkpoint.get("prior_output", {})),
        "cash": farm.get("money", 0), "source": "fixed replay-checkpoint schema",
    }


def compile_checkpoint(checkpoint, timed_targets, **overrides):
    """Public bridge from the fixed corpus schema to :func:`solve`.

    ``timed_targets`` may be forecaster outputs with ``horizon`` in days; this
    normalises them to absolute checkpoint days before calling the solver.
    """
    snap = checkpoint_to_snapshot(checkpoint); snap.update(overrides)
    normal = []
    for t in timed_targets:
        q = dict(t)
        if "horizon" in q and "day" not in q:
            h=q.pop('horizon');q['day']=snap['season_days'] if h=='end' else snap['day']+int(h)
        normal.append(q)
    return solve(snap, normal, target_mode="remaining")


def _crop_profile(crop, planted, start, end, existing_units=None, fertilized_until=-1, fertilize=False):
    tile = ENGINE._new_plant(crop, planted, 24)
    if existing_units is not None: tile["yield_units"] = existing_units
    tile["fertilized_until_day"] = fertilized_until
    outputs, work, _inputs, release = _engine_profile(tile, start, end, fertilize=fertilize)
    return outputs[crop], work, release


def _animal_profile(animal, placed, start, end, existing_units=0, cared=True):
    tile = ENGINE._new_animal(animal, placed); tile["yield_units"] = existing_units
    outputs, work, _inputs, _release = _engine_profile(tile, start, end, care=cared)
    return ANIMALS[animal][3], outputs[ANIMALS[animal][3]], work


def _profile_candidates(snapshot):
    start, end = int(snapshot["day"]), int(snapshot.get("season_days", 30))
    rows = []
    for i, c in enumerate(_tile_cohorts(snapshot)):
        typ = c.get("type")
        if (c.get("cohort_kind") or c.get("kind")) == "crop" and typ in CROPS:
            cd=ENGINE.CROPS[typ]
            ages=[None] if cd['ongoing'] else range(cd['first_yield_day'],cd['max_yield_day']+1)
            seen=set()
            for age in ages:
                for fert in [False,True]:
                    outputs,work,inputs,release=_engine_profile(c,start,end,harvest_age=age,fertilize=fert)
                    signature=json.dumps([outputs,work,inputs,release],sort_keys=True)
                    if signature in seen:continue
                    seen.add(signature)
                    rows.append(dict(name=f"keep_existing_crop_{i}_{typ}_age{age}_fert{int(fert)}",product=typ,
                        output=outputs[typ],outputs=outputs,inputs=inputs,work=work,land={d:1 for d in range(start,release)},
                        upper=1,existing=True,existing_group=i,seed=0,fertilizer=0))
        elif (c.get("cohort_kind") or c.get("kind")) == "animal" and typ in ANIMALS:
            p = ANIMALS[typ][3]
            for care in [True,False]:
                for collect in [True,False]:
                    outputs,work,inputs,_=_engine_profile(c,start,end,care=care,collect_fertilizer=collect)
                    rows.append(dict(name=f"keep_existing_animal_{i}_{typ}_care{int(care)}_fert{int(collect)}",product=p,output=outputs[p],
                        outputs=outputs,inputs=inputs,work=work,land={d:1 for d in range(start,end)},upper=1,
                        existing=True,existing_group=i,seed=0,fertilizer=0))
    # New crop cohorts, one decision variable per plant day.  Fertilizer is an
    # explicit high-output alternative for ongoing crops, never silently free.
    for crop in CROPS:
        for d in range(start, end):
            cd = ENGINE.CROPS[crop]
            harvest_ages = [None] if cd["ongoing"] else range(cd["first_yield_day"], cd["max_yield_day"] + 1)
            for harvest_age in harvest_ages:
                suffix = "" if harvest_age is None else f"_harvest{harvest_age}"
                outputs, work, inputs, release = _engine_profile(None, d, end, new_crop=crop, harvest_age=harvest_age)
                out = outputs[crop]
                if not any(out.values()): continue
                rows.append(dict(name=f"plant_{crop}_d{d}{suffix}", product=crop, output=out, outputs=outputs, inputs=inputs, work=work,
                                 land={x: 1 for x in range(d, release)}, upper=10_000, existing=False, seed=1, fertilizer=0,
                                 plant_day=d, crop=crop))
                # One-time crops also have a real fertilizer profile: fertilizer
                # adds two units only in their maturity water window.
                if True:
                    fos, fw, finputs, fr = _engine_profile(None, d, end, new_crop=crop, fertilize=True, harvest_age=harvest_age)
                    fo = fos[crop]
                    rows.append(dict(name=f"plant_fertilized_{crop}_d{d}{suffix}", product=crop, output=fo, outputs=fos, inputs=finputs, work=fw,
                                     land={x: 1 for x in range(d, fr)}, upper=10_000, existing=False, seed=1,
                                     fertilizer=sum(w["fertilize"] for w in fw.values()), plant_day=d, crop=crop))
    # New herd expansion is opt-in: a caller must provide a funded count cap.
    # Structure/cash-market execution remains a later compiler responsibility.
    purchase_cap = snapshot.get("animal_purchase_budget", {})
    for animal in ANIMALS:
        if not int(purchase_cap.get(animal, 0)): continue
        for d in range(start, end):
            tile = ENGINE._new_animal(animal, d); outputs, work, inputs, _ = _engine_profile(tile, d, end); p, out = ANIMALS[animal][3], outputs[ANIMALS[animal][3]]
            # Matching a fertilizer count alone must not buy an animal that
            # cannot produce its main good before the game ends.
            if snapshot.get('require_primary_animal_output',True) and not any(out.values()):continue
            work[d]["pickup_animal"] += 1; work[d]["build_structure"] += 1; work[d]["place_animal"] += 1
            rows.append(dict(name=f"buy_{animal}_d{d}", product=p, output=out, outputs=outputs, inputs=inputs, work=work,
                             land={x: 1 for x in range(d, end)}, upper=int(purchase_cap[animal]), existing=False,
                             seed=0, fertilizer=0, animal=animal, purchase_day=d))
    return rows


def solve(snapshot, targets, *, work_slack=0, target_mode="remaining"):
    """Return an integer aggregate plan.  Requires scipy.optimize.milp."""
    try:
        import numpy as np
        from scipy.optimize import Bounds, LinearConstraint, milp
    except ImportError as e:
        raise RuntimeError("scipy.optimize.milp is required; run with the project Python environment") from e
    start, end = int(snapshot["day"]), int(snapshot.get("season_days", 30))
    days, cand = list(range(start, end)), _profile_candidates(snapshot)
    n, target_rows = len(cand), []
    prior = Counter(snapshot.get("already_produced", {})) if target_mode == "cumulative" else Counter()
    for t in targets:
        d, p, value = int(t["day"]), t["product"], int(t["units"])
        if not start <= d <= end or p not in PRODUCTS: raise ValueError(f"bad target {t}")
        target_rows.append((d, p, value - prior[p], t))
    # x candidates, then two non-negative absolute-deviation slacks per target.
    slack_n = 2 * len(target_rows); procurement_start = n + slack_n
    m = procurement_start + 2; c = np.zeros(m)
    c[n:procurement_start] = 10000.0
    # Tiny deterministic tie-break: prefer preserving assets, earlier outputs,
    # then fewer new plantings.  Slack dominates all of these.
    for j, row in enumerate(cand): c[j] = (0 if row["existing"] else 1) + 1e-4 * row["seed"]
    integrality = np.ones(m); lb = np.zeros(m); ub = np.full(m, np.inf)
    for j, row in enumerate(cand):
        ub[j] = row["upper"]
        # Existing productive assets are protected by default.  A later route
        # compiler may offer a paid DIG/retirement action with an explicit tile
        # release date; silently selecting zero is never retirement.
        if row["existing"] and 'existing_group' not in row: lb[j] = 1
    ub[procurement_start] = int(snapshot.get("feed_purchase_budget", 0))
    ub[procurement_start + 1] = int(snapshot.get("fertilizer_budget", 0))
    c[procurement_start:]=0.01
    constraints = []
    def add(vec, lo, hi): constraints.append(LinearConstraint(np.array([vec]), [lo], [hi]))
    for group in sorted({row['existing_group'] for row in cand if 'existing_group' in row}):
        v=np.zeros(m)
        for j,row in enumerate(cand):v[j]=int(row.get('existing_group')==group)
        add(v,1,1)
    # Horizon end is exclusive: horizon 3 at day D means actions/output on
    # D,D+1,D+2, never the day-D+3 refresh/collection.
    for k, (d, p, want, _) in enumerate(target_rows):
        v = np.zeros(m)
        for j, row in enumerate(cand): v[j] = sum(q for day, q in row.get("outputs", {}).get(p, {}).items() if day < d)
        v[n + 2*k], v[n + 2*k + 1] = 1, -1
        add(v, want, want)
    land_cap = int(snapshot.get("land_capacity", snapshot.get("land", 0)))
    for d in days:
        v = np.zeros(m)
        for j, row in enumerate(cand): v[j] = row["land"].get(d, 0)
        add(v, -np.inf, land_cap)
    seed_stock = Counter(snapshot.get("seeds", {})); seed_budget = snapshot.get("seed_budget")
    for crop in CROPS:
        v = np.zeros(m)
        for j, row in enumerate(cand): v[j] = row["seed"] if row.get("crop") == crop else 0
        cap = seed_stock[crop] + int(snapshot.get("seed_purchase_budget", {}).get(crop, 0))
        add(v, -np.inf, cap)
    for animal in ANIMALS:
        v = np.zeros(m)
        for j, row in enumerate(cand): v[j] = 1 if row.get("animal") == animal else 0
        add(v, -np.inf, int(snapshot.get("animal_purchase_budget", {}).get(animal, 0)))
    # No projected sales fund this plan.  These static purchase prices are an
    # explicit conservative assumption; seed stock is still charged here, so
    # the constraint errs toward rejecting rather than financing a plan twice.
    cash_budget = snapshot.get("procurement_cash_budget", snapshot.get("cash"))
    if cash_budget is not None:
        v = np.zeros(m)
        for j, row in enumerate(cand):
            price = ENGINE.CROPS.get(row.get("crop"), {}).get("seed", 0)
            price += ENGINE.ANIMALS.get(row.get("animal"), {}).get("cost", 0)
            v[j] = price * (row.get("seed", 0) or 1 if row.get("animal") else row.get("seed", 0))
        reserve = _labor_certificate(snapshot, start, end)["total_hire_cost"]
        quotes = snapshot.get("resource_prices", {})
        v[procurement_start] = float(quotes.get("WHEAT", ENGINE.MARKET_PARAMS["WHEAT"]["base"]))
        v[procurement_start+1] = float(quotes.get("FERTILIZER", ENGINE.MARKET_PARAMS["FERTILIZER"]["base"]))
        add(v, -np.inf, int(cash_budget) - reserve)
    # Conservative resource ledgers, at each day boundary.  Newly collected
    # fertilizer and harvested wheat may fund later days; same-day delivery is
    # deliberately only an aggregate assumption and reported as such.
    for item, stock_key, buy_idx in (("WHEAT", "wheat", procurement_start), ("FERTILIZER", "fertilizer", procurement_start+1)):
        initial = int(snapshot.get(stock_key, 0))
        for d in days:
            v = np.zeros(m)
            for j, row in enumerate(cand):
                used = sum(row.get("inputs", {}).get(q, {}).get(item, 0) for q in days if q <= d)
                made = sum(row.get("outputs", {}).get(item, {}).get(q, 0) for q in days if q <= d)
                v[j] = used - made
            v[buy_idx] = -1
            add(v, -np.inf, initial)
    # Work is an aggregate certificate with a declared travel reserve.  A true
    # route must still be compiled against tile locations and worker positions.
    daily_capacity = snapshot.get("daily_action_capacity")
    if daily_capacity is not None:
        for d in days:
            capacity = _service_capacity(snapshot,d) + int(work_slack)
            v = np.zeros(m)
            for j, row in enumerate(cand):
                v[j] = sum(row["work"].get(d, {}).values()) + (1 if row.get("plant_day") == d else 0)
            add(v, -np.inf, capacity)
    res = milp(c=c, integrality=integrality, bounds=Bounds(lb, ub), constraints=constraints,
               options={"time_limit": float(snapshot.get("solver_time_limit", 10)), "mip_rel_gap": float(snapshot.get("mip_rel_gap", 0.0))})
    if res.x is None: raise RuntimeError(f"MILP failed: {res.message}")
    x = np.rint(res.x[:n]).astype(int)
    plan = _render_plan(snapshot, cand, x, target_rows, res.x[n:procurement_start])
    plan["procurement"] = {"WHEAT": int(round(res.x[procurement_start])), "FERTILIZER": int(round(res.x[procurement_start+1]))}
    plan["solver"] = {"status": int(res.status), "message": res.message, "objective": float(res.fun),
                      "mip_gap": None if getattr(res, "mip_gap", None) is None else float(res.mip_gap),
                      "dual_bound": None if getattr(res, "mip_dual_bound", None) is None else float(res.mip_dual_bound),
                      "optimal": int(res.status) == 0}
    return plan


def _render_plan(snapshot, cand, x, target_rows, slacks):
    start, end = int(snapshot["day"]), int(snapshot.get("season_days", 30))
    daily = {str(d): {"plant": Counter(), "buy_animal": Counter(), "actions": Counter(), "expected_output": Counter(), "expected_inputs": Counter(), "land_used": 0} for d in range(start, end)}
    selections = []
    for row, q in zip(cand, x):
        if not q: continue
        selections.append({"decision": row["name"], "quantity": int(q)})
        if row.get("plant_day") is not None: daily[str(row["plant_day"])]["plant"][row["crop"]] += int(q)
        if row.get("purchase_day") is not None: daily[str(row["purchase_day"])]["buy_animal"][row["animal"]] += int(q)
        for product, profile in row.get("outputs", {row["product"]: row["output"]}).items():
            for d, units in profile.items():
                if str(d) in daily: daily[str(d)]["expected_output"][product] += int(q * units)
        for d, acts in row["work"].items():
            if str(d) in daily:
                for a, count in acts.items(): daily[str(d)]["actions"][a] += int(q * count)
        for d, used in row.get("inputs", {}).items():
            if str(d) in daily:
                for item, count in used.items(): daily[str(d)]["expected_inputs"][item] += int(q * count)
        for d, land in row["land"].items():
            if str(d) in daily: daily[str(d)]["land_used"] += int(q * land)
    for d, r in daily.items():
        r["plant"], r["buy_animal"], r["actions"], r["expected_output"], r["expected_inputs"] = dict(r["plant"]), dict(r["buy_animal"]), dict(r["actions"]), dict(r["expected_output"]), dict(r["expected_inputs"])
        r["workload"] = sum(r["actions"].values()) + sum(r["plant"].values())
        r["action_capacity_after_travel"] = _service_capacity(snapshot,int(d))
        r["routing_status"] = "unresolved: aggregate action count only"
    deviations = []
    for i, (d, p, want, raw) in enumerate(target_rows):
        actual = sum(daily[str(day)]["expected_output"].get(p, 0) for day in range(start, min(d, end)))
        deviations.append({"target": raw, "requested_remaining_units": want, "planned_remaining_units": actual,
                           "under": int(round(slacks[2*i])), "over": int(round(slacks[2*i+1]))})
    bins = []
    for a in range(start, end, 3):
        b = min(end, a + 3); total = Counter()
        for q in range(a, b): total.update(daily[str(q)]["expected_output"])
        bins.append({"days": [a, b], "output": dict(total)})
    return {"schema_version": 2, "snapshot_day": start, "season_days": end, "aggregate_feasible": not any(x["under"] or x["over"] for x in deviations),
            "routing_feasible": None, "routing_note": "No coordinates, worker positions, or route order were solved.",
            "target_deviations": deviations, "selections": selections, "daily": daily, "three_day_output": bins,
            "labor": _labor_certificate(snapshot, start, end),
            "resource_funding": {"cash_budget": snapshot.get("procurement_cash_budget", snapshot.get("cash")),
                                 "future_sales_credited": False, "quote_source": "resource_prices or engine base price",
                                 "conditional": "Purchases and shed transfer are aggregate constraints; routes/orders are not proven."},
            "assumptions": ["Crop and animal profiles are engine-rule calendars, not observed routed actions.",
                            "Existing productive assets are frozen unless an explicit retirement compiler replaces this constraint.",
                            "Resource stock flow is aggregate and assumes same-day collection/harvest can be staged; routing and shed transfer remain unresolved.",
                            "Purchases use supplied caps/prices and are conditional on the declared cash reserve; no future sales or prices are credited."]}


def _fib(n):
    a, b = 1, 1
    for _ in range(n): a, b = b, a + b
    return a


def _hires(snapshot, day):
    """Return explicitly planned hires; never carry forward snapshot hands."""
    h = snapshot.get("hire_schedule", {})
    return int(h.get(str(day), h.get(day, 0))) if isinstance(h, dict) else 0


def _daily_capacity(snapshot, day):
    explicit = snapshot.get("daily_action_capacity")
    if isinstance(explicit, dict): return int(explicit.get(str(day), explicit.get(day, 24)))
    # HIRE is a market order, so it does not occupy the farmer. New hands act
    # from the next step, with no more than ten orders in each batch.
    base = int(explicit) if explicit is not None else 24
    n = _hires(snapshot, day)
    if n<0:raise ValueError('negative hire count')
    turns = 23 if day >= 29 else 24
    # At most ten HIRE market orders fit at step 0. Those hands act from step
    # 1; an eleventh order at step 1 creates a hand acting from step 2.
    return min(base, turns)+sum(max(0,turns-1-i//10) for i in range(n))

def _service_capacity(snapshot,day):
    return math.floor(_daily_capacity(snapshot,day)*(1-float(snapshot.get('travel_fraction',0))))-int(snapshot.get('travel_allowance',0))


def _labor_certificate(snapshot, start, end):
    mult = int(snapshot.get("farm_hand_cost_mult", 1))
    rows, cost = [], 0
    for d in range(start, end):
        n = _hires(snapshot, d); daily_cost = mult * sum(_fib(i) for i in range(n)); cost += daily_cost
        rows.append({"day": d, "planned_hires": n, "hire_cost": daily_cost,
                     "raw_action_capacity": _daily_capacity(snapshot, d)})
    funded = snapshot.get("hire_cash_budget")
    return {"daily": rows, "total_hire_cost": cost, "hire_cash_budget": funded,
            "funding_status": "not_checked" if funded is None else ("within_budget" if cost <= funded else "over_budget"),
            "note": "Hires reset nightly; costs are per-day Fibonacci 1,1,2,3,... and use an explicit schedule."}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("input"); ap.add_argument("--out", required=True)
    ns = ap.parse_args(); inp = json.loads(Path(ns.input).read_text(encoding="utf-8"))
    if "checkpoint" in inp:
        plan = compile_checkpoint(inp["checkpoint"], inp["targets"], **inp.get("snapshot_overrides", {}))
    else:
        plan = solve(inp["snapshot"], inp["targets"], target_mode=inp.get("target_mode", "remaining"))
    p = Path(ns.out); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    print(json.dumps({k: plan[k] for k in ("aggregate_feasible", "routing_feasible", "target_deviations")}, indent=2))
if __name__ == "__main__": main()

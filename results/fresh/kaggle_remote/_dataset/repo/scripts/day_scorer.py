"""Offline day scorer with engine-true values (user 2026-09-28: teach the planner the hand-planning procedure; the scorer is
its yardstick). A day = the hour-0 state of an arm's run (labor viewer frames) + the work catalogue from its planner log;
a plan = routes per unit (as manual_day_score). Scores:
  feasibility  - one hour a step (Manhattan) or an op, one pickup hour when a route feeds (or declares fpick), mid-route
                 PICKUP / DROP only on the four shed tiles, fertilizes need a fertilizer in hand, ops after hour 23 late,
                 mandatory ops of the catalogue all present
  values       - engine rules on the tile's hour-0 state: WATER on a one-time crop in its window +1 / +2 units (capped)
                 x price, a survival water / planting water / harvest-day water = mandatory (0); FERTILIZE = the units
                 it adds (the planner's gain model) x price - the fertilizer price; CARE = one product unit when a
                 production night is ahead (paid only if fed that night: counted when the route also feeds or the
                 animal is fed by another route); FEED on a production day = (bank) x price, else 0.5 unit (it enables
                 the care bank); COLLECT = the fertilizer price; HARVEST / PLANT / DIG / PLACE = 0 (mandatory work)
  midnight     - loads carried home (harvest units + collects - fertilizes, 0 after a DROP) dumped in hire order on
                 top of the night shed (option --shed N; default the arm's observed shed before its own dump); units
                 past 100 deleted from the last hires first, charged at price
usage: day_scorer.py <labor_viz json> <arm> <day> <plan.json | --planner> [--shed N] [--prices gap.json]"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}
CROPS = {"WHEAT": dict(first=2, maxday=4, max=6, ongoing=False, interval=0),
         "CARROT": dict(first=2, maxday=3, max=4, ongoing=False, interval=0),
         "TOMATO": dict(first=8, maxday=8, max=4, ongoing=True, interval=1),
         "STRAWBERRY": dict(first=10, maxday=10, max=4, ongoing=True, interval=2),
         "MELON": dict(first=10, maxday=12, max=6, ongoing=False, interval=0)}
ANIMAL = {"SHEEP": ("WOOL", 1, 3), "COW": ("MILK", 1, 2), "GOOSE": ("EGG", 1, 1)}   # product, first, interval (engine)


def load_engine_animals():
    import upkeep_engine as UE
    E = UE.engine()
    out = {}
    for a, d in E.ANIMALS.items():
        out[a] = (d["product"], d["first_yield_day"], d["interval"])
    return out


def prod_day(t, day, A):
    prod, first, iv = A[t["animal"]]
    ds = day + 1 - int(t.get("placed_day", day)) - first
    return ds >= 0 and ds % iv == 0


def later_prod(t, day, A, last=28):
    return any(prod_day(t, d, A) for d in range(day + 1, last + 1))


def fert_gain(t, day):
    c = CROPS[t["crop"]]
    pd = int(t.get("planted_day", day))
    fu = int(t.get("fertilized_until_day", -1))
    if fu >= day:
        return 0
    if not c["ongoing"]:
        w0, w1 = (c["maxday"] + 1) // 2, c["maxday"]
        if not (w0 <= day - pd <= w1):
            return 0
        y0 = int(t.get("yield_units", 0) or 0)

        def units(f):
            y = y0
            for dd in range(day, pd + w1 + 1):
                if w0 <= dd - pd <= w1:
                    y = min(c["max"], y + (2 if (f and dd <= day + 2) or fu >= dd else 1))
            return y
        return units(True) - units(False)
    first, iv, mx = c["first"], max(1, c["interval"]), c["max"]
    n = 0
    for dd in range(day, day + 3):
        ds = dd + 1 - pd - first
        if ds >= 0 and ds % iv == 0 and ds // iv + 1 <= mx and dd > fu:
            n += 1
    return n


def score(ctx, routes, label, night_shed=None, verbose=True):
    b, P, A, cat = ctx["board"], ctx["prices"], ctx["animals"], ctx["cat"]
    day = ctx["day"]
    need = {}
    for tile, d in cat["tiles"].items():
        for op, m, v, _ in d["ops"]:
            if op in ("DROP", "DELIVER", "PLACE_HARVEST", "PICKUP"):
                continue
            k = (int(tile), op)
            need[k] = need.get(k, False) or m
    fed_any = set()
    for R in routes:
        for sx, sy, ops in R["stops"]:
            if "FEED" in ops:
                fed_any.add(sy * 10 + sx)
    done = Counter()
    value = 0.0
    vby = Counter()
    late = fbad = wbad = 0
    loads = []
    fp = float(P.get("FERTILIZER", 30))
    for R in routes:
        x, y = R["start"]
        t = int(R["t0"])
        f = int(R.get("fpick", 0))
        ff = next((k for k, s in enumerate(R["stops"]) if "FEED" in s[2]), None)
        fpk = next((k for k, s in enumerate(R["stops"]) if "PICKUP" in s[2]), None)
        wheat = False
        if (ff is not None and (fpk is None or fpk > ff)) or f:
            t += 1
            wheat = True
        load = Counter()
        for sx, sy, ops in R["stops"]:
            t += abs(sx - x) + abs(sy - y)
            x, y = sx, sy
            idx = sy * 10 + sx
            tl = b[idx] or {}
            watered_now = bool(tl.get("watered_today"))
            fert_now = int(tl.get("fertilized_until_day", -1)) >= day
            for op in ops:
                if op == "PICKUP":
                    wheat = True
                    t += 1
                    continue
                if op == "DROP":
                    load = Counter({"FERTILIZER": 0})
                    t += 1
                    continue
                if op == "PLACE_HARVEST":
                    prod_ = tl.get("crop") or (A[tl["animal"]][0] if tl.get("animal") else None)
                    if prod_:
                        load[prod_] = 0
                    t += 1
                    continue
                v = 0.0
                if op == "COLLECT_FERTILIZER":
                    f += 1
                    load["FERTILIZER"] += 1
                    v = fp
                elif op == "FERTILIZE":
                    if f <= 0:
                        fbad += 1
                    else:
                        f -= 1
                        load["FERTILIZER"] -= 1
                    if tl.get("kind") == "PLANT":
                        v = fert_gain(tl, day) * float(P.get(tl["crop"], 0)) - fp
                        fert_now = True
                elif op == "WATER" and tl.get("kind") == "PLANT" and not watered_now:
                    c = CROPS[tl["crop"]]
                    a = day - int(tl.get("planted_day", day))
                    if not c["ongoing"] and (c["maxday"] + 1) // 2 <= a <= c["maxday"] and not need.get((idx, "WATER")):
                        bonus = 2 if fert_now else 1
                        v = min(bonus, c["max"] - int(tl.get("yield_units", 0) or 0)) * float(P.get(tl["crop"], 0))
                    watered_now = True
                elif op == "FEED":
                    if not wheat:
                        wbad += 1
                    if tl.get("animal") and not need.get((idx, "FEED")):
                        pr = float(P.get(A[tl["animal"]][0], 0))
                        v = (int(tl.get("pending_care_bonus", 0) or 0) * pr) if prod_day(tl, day, A) else 0.5 * pr
                elif op == "CARE":
                    if tl.get("animal") and later_prod(tl, day, A) and idx in fed_any:
                        v = float(P.get(A[tl["animal"]][0], 0))
                elif op == "HARVEST":
                    if tl.get("kind") == "PLANT":
                        u = int(tl.get("yield_units", 0) or 0)
                        c = CROPS[tl["crop"]]
                        a = day - int(tl.get("planted_day", day))
                        if not c["ongoing"] and watered_now and not tl.get("watered_today") and (c["maxday"] + 1) // 2 <= a <= c["maxday"]:
                            u = min(c["max"], u + (2 if fert_now else 1))
                        load[tl["crop"]] += u
                    elif tl.get("animal"):
                        load[A[tl["animal"]][0]] += int(tl.get("yield_units", 0) or 0)
                t += 1
                if t - 1 > 23:
                    late += 1
                done[(idx, op)] += 1
                value += v
                vby[op] += v
        loads.append((R["u"], load))
    miss = [k for k, m in need.items() if m and done[k] == 0]
    # midnight: dump in hire order (unit index) on top of the night shed
    shed = ctx["night_shed"] if night_shed is None else night_shed
    room = 100 - shed
    deleted = Counter()
    for u, load in sorted(loads, key=lambda z: z[0]):
        for k, n in load.items():
            if n <= 0:
                continue
            keep = min(n, max(0, room))
            room -= keep
            if n > keep:
                deleted[k] += n - keep
    dval = sum(n * float(P.get(k, 0)) for k, n in deleted.items())
    total = value - dval
    if verbose:
        print(f'== {label}: value {value:.0f} - midnight deleted {dval:.0f} = {total:.0f} | late {late} fert-without {fbad} '
              f'feed-without {wbad} mandatory missing {len(miss)} | night shed {shed}, carried home '
              f'{sum(sum(v for v in l.values() if v > 0) for _, l in loads)}, deleted {dict(deleted)}')
        print('   value by op: ' + ', '.join(f'{k} {v:.0f}' for k, v in vby.most_common()))
    return dict(value=value, deleted=dval, total=total, late=late, fbad=fbad, miss=len(miss))


def context(vizjson, arm, day, cat_path, prices_path=None):
    import upkeep_engine  # noqa: F401
    r = json.load(open(vizjson, encoding="utf-8"))[0]
    tab = r["tiles"]
    fr = {f["step"]: f for f in r[arm.lower()]["frames"]}
    f0 = fr[day * 24]
    b = [tab[i] if i is not None and i >= 0 else None for i in f0["board"]]
    b = [t if isinstance(t, dict) else None for t in b]
    f23 = fr.get(day * 24 + 23)
    night = sum((f23 or {}).get("shed", {}).values()) if f23 else 0
    P = {}
    if prices_path:
        G = json.load(open(prices_path))
        g = next(iter(G.values()))
        g = g.get(arm.upper()) or next(iter(g.values()))
        for k in list(g):
            m = re.match(r"us\|SELL\|(\w+)\|n", k)
            if m and g[k]:
                P[m.group(1)] = g[f"us|SELL|{m.group(1)}|$"] / g[k]
    cat = json.load(open(cat_path))
    return dict(board=b, prices=P, animals=load_engine_animals(), cat=cat, day=day, night_shed=night)


def main():
    viz, arm, day, plan = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    cat_path = sys.argv[sys.argv.index("--cat") + 1]
    prices = sys.argv[sys.argv.index("--prices") + 1] if "--prices" in sys.argv else None
    shed = int(sys.argv[sys.argv.index("--shed") + 1]) if "--shed" in sys.argv else None
    ctx = context(viz, arm, day, cat_path, prices)
    if plan == "--planner":
        import manual_day_score as MS
        ep = Path(viz).stem
        routes = MS.planner_routes(arm.upper(), ep, day)
        score(ctx, routes, f"planner {arm}", shed)
    else:
        for p in plan.split(","):
            score(ctx, json.load(open(p))["routes"], Path(p).stem, shed)


if __name__ == "__main__":
    main()

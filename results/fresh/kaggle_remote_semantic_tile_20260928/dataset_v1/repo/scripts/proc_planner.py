"""Procedural day planner (user 2026-09-28: teach the planner the hand-planning procedure). Offline: day catalogue + hour-0
state -> routes in the hand-plan format (scored by day_scorer.py, runnable in the engine via sd_manual_plan). Steps:
  1. tile services: each tile's mandatory ops + its optional ops worth > vmin by engine rules (day_scorer values)
  2. pen lines: hands starting on the shed tiles grow straight lines of adjacent pens (whole service each), round robin
  3. crop tails: every hand extends its route to the nearest unassigned tile (parallel nearest-neighbour growth, the
     hand with most hours left first), while the route fits the day
  4. supply: a FERTILIZE is kept only when the route holds a spare fertilizer (a collect earlier on it)
  5. mandatory leftovers: cheapest insertion anywhere, dropping cheaper optional ops to make room
  6. midnight: projected load over 100 (night shed option) -> surplus collects dropped from the last hires first; routes of
     same-start / same-hour hands ordered so the early hires carry the high-value loads
usage: proc_planner.py <labor_viz json> <arm> <day> --cat <catalogue> --prices <gap json> --out <plan.json> [--shed N] [--vmin 5]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import day_scorer as DS  # noqa: E402

RANK = {"PLACE_HARVEST": 6.5, "DROP": 10, "DIG": 0, "COLLECT_FERTILIZER": 1, "FEED": 2, "CARE": 3, "FERTILIZE": 4, "WATER": 5, "HARVEST": 6, "PLANT": 7,
        "BUILD_PASTURE": 8.5, "BUILD_COOP": 8.5, "PLACE": 9}
ACCESS = [(4, 4), (5, 4), (4, 5), (5, 5)]


def man(a, b):
    return abs(a % 10 - b % 10) + abs(a // 10 - b // 10)


def op_value(ctx, tile, op, mand, fert_planned):
    if mand:
        return 0.0
    b, P, A, day = ctx["board"], ctx["prices"], ctx["animals"], ctx["day"]
    t = b[tile] or {}
    fp = float(P.get("FERTILIZER", 30))
    if op == "COLLECT_FERTILIZER":
        return fp
    if op == "FERTILIZE" and t.get("kind") == "PLANT":
        return DS.fert_gain(t, day) * float(P.get(t["crop"], 0)) - fp
    if op == "WATER" and t.get("kind") == "PLANT" and not t.get("watered_today"):
        c = DS.CROPS[t["crop"]]
        a = day - int(t.get("planted_day", day))
        if not c["ongoing"] and (c["maxday"] + 1) // 2 <= a <= c["maxday"]:
            bonus = 2 if (fert_planned or int(t.get("fertilized_until_day", -1)) >= day) else 1
            return min(bonus, c["max"] - int(t.get("yield_units", 0) or 0)) * float(P.get(t["crop"], 0))
        return 0.0
    if op == "CARE" and t.get("animal"):
        return float(P.get(A[t["animal"]][0], 0)) if DS.later_prod(t, day, A) else 0.0
    if op == "FEED" and t.get("animal"):
        pr = float(P.get(A[t["animal"]][0], 0))
        return int(t.get("pending_care_bonus", 0) or 0) * pr if DS.prod_day(t, day, A) else 0.5 * pr
    return 0.0


def services(ctx, vmin):
    """tile -> list of (op, mandatory, value) in engine order (the replant water after PLANT kept last)."""
    out = {}
    for tile_s, d in ctx["cat"]["tiles"].items():
        tile = int(tile_s)
        ops, seen = [], {}
        for op, m, v, _ in d["ops"]:
            if op in ("DROP", "DELIVER", "PLACE_HARVEST", "PICKUP"):
                continue
            seen[op] = seen.get(op, 0) + 1
            if op in [o for o, _, _ in ops] and op != "WATER":
                continue
            ops.append((op, bool(m), 0.0))
        fert = any(o == "FERTILIZE" for o, _, _ in ops)
        sv = []
        for op, m, _ in ops:
            v = op_value(ctx, tile, op, m, fert)
            if m or v > vmin:
                sv.append((op, m, v))
        waters = [x for x in sv if x[0] == "WATER"]
        seq = sorted([x for x in sv if x[0] != "WATER"], key=lambda x: RANK[x[0]])
        if waters and any(x[0] == "HARVEST" for x in seq):
            j = next(i for i, x in enumerate(seq) if x[0] == "HARVEST")
            seq.insert(j, waters.pop(0))           # the water before a harvest (window bonus / harvest-day water)
        if waters and any(x[0] == "PLANT" for x in seq):
            j = next(i for i, x in enumerate(seq) if x[0] == "PLANT")
            seq.insert(j + 1, waters.pop(0))       # the planting's water
        for w in waters:                           # a plain water after the fertilize
            j = next((i for i, x in enumerate(seq) if RANK[x[0]] > RANK["WATER"]), len(seq))
            seq.insert(j, w)
        if seq:
            out[tile] = seq
    return out


def sim(R, sv_of):
    """end hour, fertilizer bad count, late of a route [{"tile", "ops": [(op, m, v)]}]"""
    x, y = R["start"]
    t = R["t0"] + (1 if any(o == "FEED" for s in R["stops"] for o, _, _ in s["ops"]) or R.get("fpick") else 0)
    f = R.get("fpick", 0)
    bad = late = 0
    for s in R["stops"]:
        t += abs(s["tile"] % 10 - x) + abs(s["tile"] // 10 - y)
        x, y = s["tile"] % 10, s["tile"] // 10
        for op, m, v in s["ops"]:
            if op == "COLLECT_FERTILIZER":
                f += 1
            elif op == "FERTILIZE":
                if f <= 0:
                    bad += 1
                else:
                    f -= 1
            t += 1
            if t - 1 > 23:
                late += 1
    return t, bad, late


def spare_fert(R, upto):
    f = R.get("fpick", 0)
    for s in R["stops"][:upto]:
        for op, _, _ in s["ops"]:
            if op == "COLLECT_FERTILIZER":
                f += 1
            elif op == "FERTILIZE":
                f -= 1
    return f


def plan(ctx, vmin=5.0, night_shed=0, iters=4000):
    sv = services(ctx, vmin)
    b = ctx["board"]
    units = []
    spawn = ctx["cat"]["spawn"]
    for u in ctx["cat"]["units"]:
        start = (4, 4) if u["u"] == 0 else tuple(spawn[u["u"] - 1])
        units.append({"u": u["u"], "start": start, "t0": int(u["t0"]), "stops": [], "fpick": 0})
    pens = {t for t in sv if (b[t] or {}).get("animal")}
    free = set(sv)
    # 2. pen lines: straight runs of adjacent pens (rows / columns), chunks of <= 5, covering the pen block
    runs = []
    for fixed in range(10):
        for horiz in (True, False):
            cur = []
            for v in range(11):
                t = (fixed * 10 + v) if horiz else (v * 10 + fixed)
                if v < 10 and t in pens:
                    cur.append(t)
                else:
                    if cur:
                        for i in range(0, len(cur), 5):
                            runs.append(cur[i:i + 5])
                    cur = []
    covered, lines = set(), []
    while covered != pens:
        best = max(runs, key=lambda r: (len(set(r) - covered), -min(man(t, 44) for t in r)))
        if not set(best) - covered:
            break
        seg = [t for t in best if t not in covered]
        lines.append(seg)
        covered |= set(seg)
    spawn_units = sorted([R for R in units if R["start"] in ACCESS], key=lambda r: (r["t0"], r["u"]))
    pairs = sorted((min(man(R["start"][1] * 10 + R["start"][0], ln[0]), man(R["start"][1] * 10 + R["start"][0], ln[-1])), i, R["u"])
                   for i, ln in enumerate(lines) for R in spawn_units)
    used_l, used_u = set(), set()
    byu = {R["u"]: R for R in units}
    for d, i, u in pairs:
        if i in used_l or u in used_u:
            continue
        R = byu[u]
        st = R["start"][1] * 10 + R["start"][0]
        ln = lines[i] if man(st, lines[i][0]) <= man(st, lines[i][-1]) else lines[i][::-1]
        stops = []
        for t in ln:
            trial = dict(R, stops=stops + [{"tile": t, "ops": list(sv[t])}])
            if sim(trial, sv)[0] > 19:
                break
            stops = trial["stops"]
            free.discard(t)
        R["stops"] = stops
        used_l.add(i)
        used_u.add(u)

    # 3. tails: growth in widening rings from each route's end
    def add_tile(R, tile):
        ops = list(sv[tile])
        if any(o == "FERTILIZE" for o, _, _ in ops) and spare_fert(R, len(R["stops"])) <= 0:
            ops = [o for o in ops if o[0] != "FERTILIZE"]
            ops = [(o, m, (op_value(ctx, tile, o, m, False) if o == "WATER" else v)) for o, m, v in ops]
            ops = [o for o in ops if o[1] or o[2] > vmin]
        return dict(R, stops=R["stops"] + [{"tile": tile, "ops": ops}]) if ops else None
    for radius in (2, 3, 5, 99):
        moved = True
        while moved and free:
            moved = False
            for R in sorted(units, key=lambda r: sim(r, sv)[0]):
                pos = R["stops"][-1]["tile"] if R["stops"] else R["start"][1] * 10 + R["start"][0]
                near = sorted((t for t in free if man(pos, t) <= radius), key=lambda t: (man(pos, t), -len(sv[t]), t))
                for tile in near[:4]:
                    trial = add_tile(R, tile)
                    if trial is None:
                        free.discard(tile)
                        moved = True
                        break
                    e, bad, late = sim(trial, sv)
                    if e <= 24 and bad == 0:
                        R["stops"] = trial["stops"]
                        free.discard(tile)
                        moved = True
                        break
    # 4. leftovers: mandatory first (room made by dropping the cheapest optional ops, collects included, supply kept),
    #    then optional ones where they fit
    left = []
    for tile in sorted(free, key=lambda t: (-sum(1 for o in sv[t] if o[1]), -sum(o[2] for o in sv[t]))):
        mand = any(o[1] for o in sv[tile])
        best = None
        for R in units:
            base_e, base_bad, _ = sim(R, sv)
            for k in range(len(R["stops"]) + 1):
                stops = [dict(x, ops=list(x["ops"])) for x in R["stops"][:k]] + [{"tile": tile, "ops": list(sv[tile])}] +                         [dict(x, ops=list(x["ops"])) for x in R["stops"][k:]]
                trial = dict(R, stops=stops)
                lost = 0.0
                while True:
                    e, bad, late = sim(trial, sv)
                    if bad > base_bad:             # a fertilize without supply in the new tile: drop it
                        for x in trial["stops"]:
                            if x["tile"] == tile:
                                x["ops"] = [o for o in x["ops"] if o[0] != "FERTILIZE"]
                        continue
                    if e <= 24:
                        break
                    if not mand:
                        lost = None
                        break
                    c = [(v, j, i) for j, x in enumerate(trial["stops"]) if x["tile"] != tile
                         for i, (o, m, v) in enumerate(x["ops"]) if not m]
                    dropped = False
                    for v, j, i in sorted(c):
                        t2 = dict(trial, stops=[dict(x, ops=list(x["ops"])) for x in trial["stops"]])
                        t2["stops"][j]["ops"].pop(i)
                        t2["stops"] = [x for x in t2["stops"] if x["ops"]]
                        if sim(t2, sv)[1] <= base_bad:
                            trial, lost, dropped = t2, lost + v, True
                            break
                    if not dropped:
                        lost = None
                        break
                if lost is None:
                    continue
                gain = sum(o[2] for x in trial["stops"] if x["tile"] == tile for o in x["ops"]) - lost
                if best is None or (mand and lost < best[0]) or (not mand and gain > best[0]):
                    best = (lost if mand else gain, R, trial["stops"])
        if best is None or (not mand and best[0] <= 0):
            left.append(tile)
            continue
        best[1]["stops"] = best[2]
    if iters:
        optimize(ctx, units, sv, night_shed, iters)
    # 6. midnight: surplus collects dropped from the last hires first, high-value loads on early hires
    P = ctx["prices"]

    def load_of(R):
        L, val = 0, 0.0
        for s in R["stops"]:
            t = b[s["tile"]] or {}
            for o, m, v in s["ops"]:
                if o == "COLLECT_FERTILIZER":
                    L += 1
                    val += float(P.get("FERTILIZER", 30))
                elif o == "FERTILIZE":
                    L -= 1
                elif o == "HARVEST":
                    u = int(t.get("yield_units", 0) or 0)
                    prod = t.get("crop") or (ctx["animals"][t["animal"]][0] if t.get("animal") else None)
                    L += u
                    val += u * float(P.get(prod, 0))
        return L, val
    total = night_shed + sum(max(0, load_of(R)[0]) for R in units)
    for R in sorted(units, key=lambda r: -r["u"]):
        if total <= 100:
            break
        sp = spare_fert(R, len(R["stops"]))
        for s in reversed(R["stops"]):
            if total <= 100 or sp <= 0:
                break
            if any(o == "COLLECT_FERTILIZER" for o, _, _ in s["ops"]):
                s["ops"] = [o for o in s["ops"] if o[0] != "COLLECT_FERTILIZER"]
                sp -= 1
                total -= 1
        R["stops"] = [s for s in R["stops"] if s["ops"]]
    groups = {}
    for R in units:
        groups.setdefault((R["start"], R["t0"]), []).append(R)
    for g in groups.values():
        if len(g) < 2:
            continue
        us = sorted(R["u"] for R in g)
        routes = sorted(g, key=lambda R: -load_of(R)[1])
        for u, R in zip(us, routes):
            R["u"] = u
    out = [{"u": R["u"], "start": list(R["start"]), "t0": R["t0"], "fpick": R.get("fpick", 0),
            "stops": [[s["tile"] % 10, s["tile"] // 10, [o for o, _, _ in s["ops"]]] for s in R["stops"]]} for R in units]
    return {"routes": out, "left": [(t % 10, t // 10) for t in left]}


def optimize(ctx, units, sv, night_shed, iters, seed=1):
    """hill-climbing local search on the scorer's objective over tile services (see the module doc)."""
    import random
    rng = random.Random(seed)
    b, P, A, day = ctx["board"], ctx["prices"], ctx["animals"], ctx["day"]
    fp = float(P.get("FERTILIZER", 30))
    mand_feed = {t for t, ops in sv.items() for o, m, v in ops if o == "FEED" and m}

    def reval(R):
        x, y = R["start"]
        t = R["t0"] + (1 if any(o == "FEED" for s in R["stops"] for o, _, _ in s["ops"]) or R.get("fpick") else 0)
        f = R.get("fpick", 0)
        bad = late = steps = 0
        val = 0.0
        load = {}
        for s in R["stops"]:
            d = abs(s["tile"] % 10 - x) + abs(s["tile"] // 10 - y)
            steps += d
            t += d
            x, y = s["tile"] % 10, s["tile"] // 10
            tl = b[s["tile"]] or {}
            opn = [o for o, _, _ in s["ops"]]
            fert = "FERTILIZE" in opn or int(tl.get("fertilized_until_day", -1)) >= day
            fed = "FEED" in opn or s["tile"] in mand_feed or tl.get("fed_today")
            for op, m, v0 in s["ops"]:
                v = 0.0
                if op == "DROP":
                    load = {}
                    t += 1
                    continue
                if op == "PLACE_HARVEST":
                    prod_ = tl.get("crop") or (A[tl["animal"]][0] if tl.get("animal") else None)
                    if prod_:
                        load[prod_] = 0
                    t += 1
                    continue
                if op == "COLLECT_FERTILIZER":
                    f += 1
                    load["FERTILIZER"] = load.get("FERTILIZER", 0) + 1
                    v = fp
                elif op == "FERTILIZE":
                    if f <= 0:
                        bad += 1
                    else:
                        f -= 1
                        load["FERTILIZER"] = load.get("FERTILIZER", 0) - 1
                    v = v0
                elif op == "WATER" and not m:
                    v = op_value(ctx, s["tile"], op, m, fert)
                elif op == "CARE":
                    v = v0 if fed else 0.0
                elif op == "FEED":
                    v = v0
                elif op == "HARVEST":
                    if tl.get("kind") == "PLANT":
                        u = int(tl.get("yield_units", 0) or 0)
                        c = DS.CROPS[tl["crop"]]
                        a = day - int(tl.get("planted_day", day))
                        if (not c["ongoing"] and "WATER" in opn and not tl.get("watered_today")
                                and (c["maxday"] + 1) // 2 <= a <= c["maxday"]):
                            u = min(c["max"], u + (2 if fert else 1))
                        load[tl["crop"]] = load.get(tl["crop"], 0) + u
                    elif tl.get("animal"):
                        pr = A[tl["animal"]][0]
                        load[pr] = load.get(pr, 0) + int(tl.get("yield_units", 0) or 0)
                val += v
                t += 1
                if t - 1 > 23:
                    late += 1
        return {"val": val, "pen": 1000.0 * (late + bad), "steps": steps, "load": load, "end": t}

    ev = {R["u"]: reval(R) for R in units}
    byu = {R["u"]: R for R in units}

    def midnight():
        room = 100 - night_shed
        lost = 0.0
        for R in sorted(units, key=lambda r: r["u"]):
            for k, n in ev[R["u"]]["load"].items():
                if n <= 0:
                    continue
                keep = min(n, max(0, room))
                room -= keep
                lost += (n - keep) * float(P.get(k, 0))
        return lost

    def total():
        return sum(e["val"] - e["pen"] - 0.2 * e["steps"] for e in ev.values()) - midnight()

    placed = {}
    for R in units:
        for s_ in R["stops"]:
            for o, _, _ in s_["ops"]:
                placed[(s_["tile"], o)] = placed.get((s_["tile"], o), 0) + 1
    pool = [(t, (o, m, v)) for t, ops in sv.items() for o, m, v in ops if not m and placed.get((t, o), 0) == 0]
    cur = [total()]
    acc = [0]

    def try_set(changes):
        old = {u: (byu[u]["stops"], ev[u]) for u in changes}
        for u, stops in changes.items():
            byu[u]["stops"] = stops
            ev[u] = reval(byu[u])
        new = total()
        if new > cur[0] + 1e-6:
            cur[0] = new
            acc[0] += 1
            return True
        for u, (stops, e) in old.items():
            byu[u]["stops"] = stops
            ev[u] = e
        return False

    def cp(stops):
        return [dict(x, ops=list(x["ops"])) for x in stops]

    def order_ops(ops):
        has_h = any(o[0] == "HARVEST" for o in ops)
        has_p = any(o[0] == "PLANT" for o in ops)
        ws = [o for o in ops if o[0] == "WATER"]
        rest = sorted([o for o in ops if o[0] != "WATER"], key=lambda o: RANK[o[0]])
        if ws and has_h:
            j = next(i for i, o in enumerate(rest) if o[0] == "HARVEST")
            rest.insert(j, ws.pop(0))
        if ws and has_p:
            j = next(i for i, o in enumerate(rest) if o[0] == "PLANT")
            rest.insert(j + 1, ws.pop(0))
        for w in ws:
            j = next((i for i, o in enumerate(rest) if RANK[o[0]] > RANK["WATER"]), len(rest))
            rest.insert(j, w)
        return rest

    for it in range(iters):
        mv = rng.random()
        Rs = [R for R in units if R["stops"]]
        if not Rs:
            break
        if mv < 0.35:                              # relocate a tile service to the best position of a nearby route
            A_ = rng.choice(Rs)
            j = rng.randrange(len(A_["stops"]))
            x = A_["stops"][j]
            Bs = sorted(units, key=lambda r: min([man(r["start"][1] * 10 + r["start"][0], x["tile"])] +
                                                  [man(y["tile"], x["tile"]) for y in r["stops"]]))[:4]
            B_ = rng.choice(Bs)
            if B_ is A_:
                continue
            sa = cp(A_["stops"])
            sa.pop(j)
            best = None
            for q in range(len(B_["stops"]) + 1):
                sb = cp(B_["stops"])
                sb.insert(q, dict(x, ops=list(x["ops"])))
                oldA, oldB = (A_["stops"], ev[A_["u"]]), (B_["stops"], ev[B_["u"]])
                A_["stops"], B_["stops"] = sa, sb
                ev[A_["u"]], ev[B_["u"]] = reval(A_), reval(B_)
                v = total()
                A_["stops"], ev[A_["u"]] = oldA
                B_["stops"], ev[B_["u"]] = oldB
                if best is None or v > best[0]:
                    best = (v, sb)
            if best and best[0] > cur[0] + 1e-6:
                try_set({A_["u"]: sa, B_["u"]: best[1]})
        elif mv < 0.5:                             # swap two services between routes
            A_, B_ = rng.choice(Rs), rng.choice(Rs)
            if A_ is B_:
                continue
            i, j = rng.randrange(len(A_["stops"])), rng.randrange(len(B_["stops"]))
            sa, sb = cp(A_["stops"]), cp(B_["stops"])
            sa[i], sb[j] = sb[j], sa[i]
            try_set({A_["u"]: sa, B_["u"]: sb})
        elif mv < 0.7:                             # 2-opt inside a route
            A_ = rng.choice(Rs)
            if len(A_["stops"]) < 3:
                continue
            i = rng.randrange(len(A_["stops"]) - 1)
            j = rng.randrange(i + 1, len(A_["stops"]))
            sa = cp(A_["stops"])
            sa[i:j + 1] = sa[i:j + 1][::-1]
            try_set({A_["u"]: sa})
        elif mv < 0.88 and pool:                   # add an unplaced optional op to its tile's visit (else a new visit)
            k = rng.randrange(len(pool))
            t, op = pool[k]
            owner = next((R for R in units for y in R["stops"] if y["tile"] == t), None)
            if owner is not None:
                j = next(jj for jj, y in enumerate(owner["stops"]) if y["tile"] == t)
                sa = cp(owner["stops"])
                sa[j]["ops"] = order_ops(sa[j]["ops"] + [op])
                if try_set({owner["u"]: sa}):
                    pool.pop(k)
            else:
                A_ = min(units, key=lambda r: min([man(y["tile"], t) for y in r["stops"]] + [99]))
                for q in range(len(A_["stops"]) + 1):
                    sa = cp(A_["stops"])
                    sa.insert(q, {"tile": t, "ops": [op]})
                    if try_set({A_["u"]: sa}):
                        pool.pop(k)
                        break
        else:                                      # drop an optional op (frees an hour / fixes supply or midnight)
            A_ = rng.choice(Rs)
            j = rng.randrange(len(A_["stops"]))
            opts = [i for i, o in enumerate(A_["stops"][j]["ops"]) if not o[1]]
            if not opts:
                continue
            i = rng.choice(opts)
            sa = cp(A_["stops"])
            op = sa[j]["ops"].pop(i)
            tile = sa[j]["tile"]
            sa = [x for x in sa if x["ops"]]
            if try_set({A_["u"]: sa}):
                pool.append((tile, op))
    return cur[0], acc[0]


def main():
    viz, arm, day = sys.argv[1], sys.argv[2], int(sys.argv[3])
    cat = sys.argv[sys.argv.index("--cat") + 1]
    prices = sys.argv[sys.argv.index("--prices") + 1]
    outp = sys.argv[sys.argv.index("--out") + 1]
    shed = int(sys.argv[sys.argv.index("--shed") + 1]) if "--shed" in sys.argv else 0
    vmin = float(sys.argv[sys.argv.index("--vmin") + 1]) if "--vmin" in sys.argv else 5.0
    ctx = DS.context(viz, arm, day, cat, prices)
    iters = int(sys.argv[sys.argv.index("--iters") + 1]) if "--iters" in sys.argv else 4000
    P = plan(ctx, vmin, shed, iters)
    json.dump({"routes": P["routes"]}, open(outp, "w"), indent=1)
    print("unassigned tiles:", P["left"])
    DS.score(ctx, P["routes"], Path(outp).stem, shed)


if __name__ == "__main__":
    main()

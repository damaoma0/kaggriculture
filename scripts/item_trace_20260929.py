"""Item-by-item, tick-by-tick trace of goods for both farms of a harness game (user 2026-09-29: "trace the inbound items
and sales tick by tick, item by item"; bring-back runs vs prices).

Engine hooks log, per seat and tick (step = day * 24 + hour):
  produced   a HARVEST / COLLECT_FERTILIZER that put units into a unit's inventory (unit, tile, product, n)
  arrived    units entering the shed: a DROP / PLACE on a shed-access tile (unit, product, n) or the midnight dump of
             every unit's inventory (tick = the next day's hour 0)
  taken      PICKUPs out of the shed (feed wheat, fertilizer)
  sold       every executed SELL unit with its price; bought units (BUY_PRODUCT) enter the shed
  market     price and stock of every product before each tick's market
Items are then followed FIFO (per hand, per shed product): each produced unit gets its arrival tick / route (mid-day drop
or midnight dump) and its sale tick / price.

usage: item_trace_20260929.py CAND CASE_ID [--cases leaders_cases.json] [--out DIR] [--controls DIR --prefix 264]
         [--source-control]  (exact day-11 benchmark: dsmseat_cases.json, controls local_dsmseat/_controls; the source
         control is DSM continuing its own game, written to DIR_src)
  -> DIR/<case>.items.json (items, events, market) and a summary printed per product and route
       item_trace_20260929.py show ITEMS.json PRODUCT [--days 16-19] [--ticks 18]
  -> per-day flow (produced / in by drop / in by dump / sold @avg, market price and stock) and tick tables"""
import json
import sys
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
sys.path.insert(0, str(ROOT / "scripts"))
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}


def instrument(E, ev, mk):
    buf = []
    cur = dict(step=0, privs=None)
    oa, om, oc, oe = E._apply_unit_action, E._process_market, E._commit_unit, E._end_of_day

    def ap(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        pos = E._farmer_position(farm, idx)
        pos = tuple(pos) if pos is not None else None
        inv0 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        r = oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        inv1 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        op = action[0] if isinstance(action, list) and action else None
        if op and inv0 != inv1:
            buf.append((private, idx, op, pos, inv0, inv1))
        return r

    def pm(state, env, *a, **k):
        step = int(state[0].observation.step)
        privs = [state[i].observation.private for i in range(2)]
        cur["step"], cur["privs"] = step, privs
        for (priv, idx, op, pos, inv0, inv1) in buf:
            seat = 0 if priv is privs[0] else (1 if priv is privs[1] else None)
            if seat is None:
                continue
            for g in GOODS:
                d = int(inv1.get(g, 0) or 0) - int(inv0.get(g, 0) or 0)
                if d > 0 and op in ("HARVEST", "COLLECT_FERTILIZER"):
                    ev.append(("produced", seat, step, idx, pos, g, d))
                elif d > 0 and op == "PICKUP":
                    ev.append(("taken", seat, step, idx, pos, g, d))
                elif d < 0 and op in ("DROP", "PLACE") and pos in SHED:
                    ev.append(("arrived", seat, step, idx, "drop", g, -d))
                elif d < 0 and op in ("FEED", "FERTILIZE"):
                    ev.append(("used", seat, step, idx, pos, g, -d))
        buf.clear()
        m = state[0].observation.market
        mk.append([step] + [int(m["prices"].get(g, 0)) for g in GOODS] + [int(m["inventory"].get(g, 0)) - 10000 for g in GOODS])
        return om(state, env, *a, **k)

    def cu(op, item, price, farm, private, market, *a, **k):
        r = oc(op, item, price, farm, private, market, *a, **k)
        if r and cur["privs"] is not None and op in ("SELL", "BUY_PRODUCT"):
            for i in range(2):
                if private is cur["privs"][i]:
                    ev.append(("sold" if op == "SELL" else "bought", i, cur["step"], None, None, item, float(price)))
        return r

    def ee(state, env, day, *a, **k):
        for i in range(2):                          # animals at day end (before production): count, fed, cared, bank, held
            agg = {}
            for row in (state[0].observation.farms[i].get("tiles") or []):
                for t in row:
                    if isinstance(t, dict) and t.get("animal"):
                        a_ = agg.setdefault(t["animal"], [0, 0, 0, 0, 0])
                        a_[0] += 1
                        a_[1] += int(bool(t.get("fed_today")))
                        a_[2] += int(bool(t.get("cared_today")))
                        a_[3] += int(t.get("pending_care_bonus", 0) or 0)
                        a_[4] += int(t.get("yield_units", 0) or 0)
            for kind_, v_ in agg.items():
                ev.append(("animal", i, day, None, None, kind_, v_))
        for i in range(2):                          # the midnight dump: every unit's inventory into the shed
            for idx, inv in enumerate(state[i].observation.private["inventories"]):
                for g in GOODS:
                    n = int((inv or {}).get(g, 0) or 0)
                    if n > 0:
                        ev.append(("arrived", i, (day + 1) * 24, idx, "dump", g, n))
        return oe(state, env, day, *a, **k)
    E._apply_unit_action, E._process_market, E._commit_unit, E._end_of_day = ap, pm, cu, ee
    return lambda: setattr(E, "_apply_unit_action", oa) or setattr(E, "_process_market", om) or \
        setattr(E, "_commit_unit", oc) or setattr(E, "_end_of_day", oe)


def job(args):
    cand, case, out = args[:3]
    extra = args[3] if len(args) > 3 else {}
    import types
    import semantic_h2h_20260929 as SH
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    ev, mk = [], []
    un = instrument(E, ev, mk)
    me = Path(__file__).resolve()
    for k_, m_ in list(sys.modules.items()):
        if getattr(m_, "__file__", None) and Path(m_.__file__).resolve() == me:
            sys.modules[k_] = types.ModuleType(k_)
    try:
        harness = H / "study/candidates" / cand / "harness"
        j = dict(study=str(H / "study"), case=case, kind="recorded", output=str(out / f"{case['id']}.json"), candidate=cand,
                 control=str(H / extra.get("controls", "leadersx_credit/_controls") / f"{case['id']}.json"), leader_credit="exact",
                 leader_commits=str(H / "leader_commits" / f"{case['id']}.json"), leader_weeds=True)
        if extra.get("prefix"):                    # exact prefix: our seat replays its recording until this step
            j["prefix_steps"] = int(extra["prefix"])
        if extra.get("source_control"):           # both recorded streams (e.g. DSM continuing its own game)
            j = dict(study=str(H / "study"), case=case, kind="source_control", output=str(out / f"{case['id']}.ctl.json"),
                     candidate=cand, leader_weeds=True)
        row = SH._worker((str(harness), j, True))
    finally:
        un()
    return case["id"], row.get("margin"), ev, mk


def follow(ev, seat):
    """FIFO items of one seat: produced -> carried (per hand) -> shed -> sold"""
    hand = defaultdict(deque)                      # (idx, product) -> deque of item ids
    shed = defaultdict(deque)                      # product -> deque of item ids (None = stock from before / bought)
    items = []
    order = {"produced": 0, "used": 1, "taken": 2, "arrived": 3, "bought": 4, "sold": 5}
    for e in sorted((e for e in ev if e[1] == seat and e[0] in order), key=lambda e: (e[2], order[e[0]])):
        kind, _, t, idx, x, g, n = e
        if kind == "produced":
            for _ in range(n):
                items.append(dict(p=g, t_prod=t, tile=list(x) if x else None, hand=idx, t_shed=None, route=None,
                                  t_sold=None, price=None))
                hand[(idx, g)].append(len(items) - 1)
        elif kind == "used":                        # fed / fertilized from the hand
            for _ in range(n):
                if hand[(idx, g)]:
                    items[hand[(idx, g)].popleft()]["route"] = "used"
        elif kind == "taken":                       # picked up from the shed: leaves the shed queue, back in a hand
            for _ in range(n):
                i = shed[g].popleft() if shed[g] else None
                if i is not None:
                    items[i]["t_shed"] = None
                    hand[(idx, g)].append(i)
        elif kind == "arrived":
            for _ in range(n):
                i = hand[(idx, g)].popleft() if hand[(idx, g)] else None
                if i is not None:
                    items[i]["t_shed"], items[i]["route"] = t, x
                shed[g].append(i)
        elif kind == "bought":
            shed[g].append(None)
        elif kind == "sold":
            i = shed[g].popleft() if shed[g] else None
            if i is not None:
                items[i]["t_sold"], items[i]["price"] = t, n
    return items


def show(path, g, d0, d1, tick_days):
    R = json.loads(Path(path).read_text())
    G = R["goods"]
    j = G.index(g)
    mk = {r[0]: r for r in R["market"]}

    def flows(items, key):
        P, Dd, Dm, S = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(list)
        for it in items:
            if it["p"] != g:
                continue
            P[key(it["t_prod"])] += 1
            if it["t_shed"] is not None:
                (Dd if it["route"] == "drop" else Dm)[key(it["t_shed"])] += 1
            if it["t_sold"] is not None:
                S[key(it["t_sold"])].append(it["price"])
        return P, Dd, Dm, S

    def cell(X, k):
        s_ = X[3][k]
        return f"{X[0][k]:3d} / {X[1][k]:3d} | {X[2][k]:3d} / {len(s_):3d} " + (f"@{sum(s_) / len(s_):4.0f}" if s_ else "     ")
    A, B = flows(R["items"]["ours"], lambda t: t // 24), flows(R["items"]["leader"], lambda t: t // 24)
    print(f"{R['case']} {g} by day: price h0/h12/h23 stock | OURS produced / in by drop | in by dump / sold @avg | LEADER same")
    for d in range(d0, d1 + 1):
        p = [mk.get(d * 24 + h, [0] * 20)[1 + j] for h in (0, 12, 23)]
        print(f"  d{d:02d}: {p[0]:4d}/{p[1]:4d}/{p[2]:4d} {mk.get(d * 24, [0] * 20)[1 + len(G) + j]:+4d} | {cell(A, d)} | {cell(B, d)}")
    A, B = flows(R["items"]["ours"], lambda t: t), flows(R["items"]["leader"], lambda t: t)
    for d in tick_days:
        print(f"\n{g} day {d} by tick: price stock | OURS harvested / in by drop | in by dump / sold | LEADER same")
        for h in range(24):
            t = d * 24 + h
            m = mk.get(t, [0] * 20)
            print(f"  h{h:02d}: {m[1 + j]:4d} {m[1 + len(G) + j]:+4d} | {cell(A, t)} | {cell(B, t)}")


def main():
    if sys.argv[1] == "show":
        d0, d1 = map(int, (sys.argv[sys.argv.index("--days") + 1] if "--days" in sys.argv else "12-26").split("-"))
        td = [int(x) for x in sys.argv[sys.argv.index("--ticks") + 1].split(",")] if "--ticks" in sys.argv else []
        return show(sys.argv[2], sys.argv[3], d0, d1, td)
    cand, cid = sys.argv[1], sys.argv[2]
    cfile = Path(sys.argv[sys.argv.index("--cases") + 1]) if "--cases" in sys.argv else H / "leaders_cases.json"
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else H / "item_trace" / cand
    out.mkdir(parents=True, exist_ok=True)
    case = [c for c in json.loads(cfile.read_text())["cases"] if c["id"] == cid][0]
    extra = dict(controls=sys.argv[sys.argv.index("--controls") + 1] if "--controls" in sys.argv else "leadersx_credit/_controls",
                 prefix=int(sys.argv[sys.argv.index("--prefix") + 1]) if "--prefix" in sys.argv else 0,
                 source_control="--source-control" in sys.argv)
    if extra["source_control"]:
        out = out.parent / (out.name + "_src")
        out.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
        cid_, margin, ev, mk = next(pool.map(job, [(cand, case, out, extra)]))
    s = int(case["seat"])
    res = dict(case=cid, margin=margin, our_seat=s, goods=GOODS, market=mk,
               items={"ours": follow(ev, s), "leader": follow(ev, 1 - s)}, events=ev)
    (out / f"{cid}.items.json").write_text(json.dumps(res))
    print(cid, "margin", margin, "->", out / f"{cid}.items.json")
    for side in ("ours", "leader"):
        agg = defaultdict(lambda: defaultdict(list))
        for it in res["items"][side]:
            if it["t_prod"] < 144 or it["route"] in (None, "used"):
                continue
            key = ("same day" if it["route"] == "drop" and it["t_sold"] is not None and it["t_sold"] // 24 == it["t_prod"] // 24
                   else it["route"] + (",sold" if it["t_sold"] is not None else ",unsold"))
            agg[it["p"]][key].append(it)
        print(side)
        for g in ("STRAWBERRY", "MILK", "WOOL", "MELON", "EGG", "TOMATO", "CARROT", "WHEAT", "FERTILIZER"):
            if not agg[g]:
                continue
            tot = sum(len(v) for v in agg[g].values())
            parts = []
            for k, v in sorted(agg[g].items()):
                sold = [x for x in v if x["price"] is not None]
                lag = sum(x["t_sold"] - x["t_prod"] for x in sold) / max(1, len(sold))
                parts.append(f"{k} {len(v)} ({len(v) / tot:.0%}) @{sum(x['price'] for x in sold) / max(1, len(sold)):.0f} lag {lag:.0f}h")
            print(f"  {g:10s} {tot:4d} | " + " | ".join(parts))


if __name__ == "__main__":
    main()

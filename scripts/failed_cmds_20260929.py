"""Failed commands of our seat in a harness game, by day, op and cause (user 2026-09-29: "why we can't be action-exact
in days 6-10?"; n18rcx11 replayed DSM's recorded commands through day 11 and had 65-301 failed commands by day 12).

Engine hooks: every unit command of our seat that changes neither its tile nor its inventory (moves / PASS excluded) is
a failure, classified by the target tile (WEED / empty / plant crop / animal / structure / locked) and the unit's
inventory (no seed, no wheat, no fertilizer); failed market orders (a BUY / HIRE / BUY_LAND the engine refused) are
counted per op. Also the hand count per day and the router's tape switches if the harness logs them.

usage: failed_cmds_20260929.py CAND CASE_ID[,CASE_ID] [--days 6-11] [--cases leaders_cases.json]"""
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
sys.path.insert(0, str(ROOT / "scripts"))
MOVES = ("NORTH", "SOUTH", "EAST", "WEST")


def job(args):
    cand, case, out, d0, d1 = args
    import types
    import semantic_h2h_20260929 as SH
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    seat = int(case["seat"])
    fails = defaultdict(Counter)
    orders = defaultdict(Counter)
    cur = dict(step=0, privs=None)
    oa, om, oc = E._apply_unit_action, E._process_market, E._commit_unit
    buf = []

    def tile_kind(t):
        if t is None:
            return "empty"
        if t == "LOCKED" or (isinstance(t, dict) and t.get("kind") == "LOCKED"):
            return "locked"
        if isinstance(t, dict):
            if t.get("kind") == "WEED":
                return "weed"
            if t.get("animal"):
                return "animal:" + t["animal"]
            if t.get("crop"):
                return "plant:" + t["crop"]
            return str(t.get("kind")).lower()
        return str(t)

    def ap(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        op = action[0] if isinstance(action, list) and action else None
        pos = E._farmer_position(farm, idx)
        t0 = None
        if pos is not None:
            t = farm["tiles"][pos[1]][pos[0]]
            t0 = dict(t) if isinstance(t, dict) else t
        inv0 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        seeds0 = dict(private.get("seeds") or {})
        shed0 = dict(private.get("shed") or {})
        hands0 = len(farm["hands"])
        r = oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        t1 = farm["tiles"][pos[1]][pos[0]] if pos is not None else None
        t1 = dict(t1) if isinstance(t1, dict) else t1
        inv1 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        if op and op not in MOVES and op != "PASS" and t0 == t1 and inv0 == inv1 and seeds0 == (private.get("seeds") or {}) \
                and shed0 == (private.get("shed") or {}):
            why = tile_kind(t0)
            if op == "PLANT" and len(action) > 1 and int(seeds0.get(action[1], 0) or 0) <= 0:
                why = "no seed"
            elif op == "FEED" and int(inv0.get("WHEAT", 0) or 0) <= 0:
                why = "no wheat"
            elif op == "FERTILIZE" and int(inv0.get("FERTILIZER", 0) or 0) <= 0:
                why = "no fertilizer"
            elif pos is None:
                why = "no such hand"
            buf.append((private, day, op, why))
        elif pos is None and op and op != "PASS":
            buf.append((private, day, op, "no such hand"))
        return r

    def pm(state, env, *a, **k):
        privs = [state[i].observation.private for i in range(2)]
        cur["step"], cur["privs"] = int(state[0].observation.step), privs
        for priv, day, op, why in buf:
            if priv is privs[seat] and d0 <= day <= d1:
                fails[day][f"{op} | {why}"] += 1
        buf.clear()
        # market orders of our seat this step, to compare with what executed
        act = state[seat].action if isinstance(state[seat].action, dict) else {}
        for o in act.get("market", []) or []:
            if isinstance(o, list) and o and d0 <= cur["step"] // 24 <= d1:
                orders[cur["step"] // 24]["asked " + o[0]] += int(o[2]) if len(o) > 2 and str(o[2]).isdigit() else 1
        return om(state, env, *a, **k)

    def cu(op, item, price, farm, private, market, *a, **k):
        r = oc(op, item, price, farm, private, market, *a, **k)
        if cur["privs"] is not None and private is cur["privs"][seat] and d0 <= cur["step"] // 24 <= d1:
            orders[cur["step"] // 24][("done " if r else "FAILED ") + op] += 1
        return r
    E._apply_unit_action, E._process_market, E._commit_unit = ap, pm, cu
    me = Path(__file__).resolve()
    for k_, m_ in list(sys.modules.items()):
        if getattr(m_, "__file__", None) and Path(m_.__file__).resolve() == me:
            sys.modules[k_] = types.ModuleType(k_)
    try:
        harness = H / "study/candidates" / cand / "harness"
        j = dict(study=str(H / "study"), case=case, kind="recorded", output=str(out / f"{case['id']}.json"), candidate=cand,
                 control=str(H / "leadersx_credit/_controls" / f"{case['id']}.json"), leader_credit="exact",
                 leader_commits=str(H / "leader_commits" / f"{case['id']}.json"), leader_weeds=True)
        row = SH._worker((str(harness), j, True))
    finally:
        E._apply_unit_action, E._process_market, E._commit_unit = oa, om, oc
    return case["id"], row.get("margin"), {d: dict(c) for d, c in fails.items()}, {d: dict(c) for d, c in orders.items()}


def main():
    cand, ids = sys.argv[1], sys.argv[2].split(",")
    d0, d1 = map(int, (sys.argv[sys.argv.index("--days") + 1] if "--days" in sys.argv else "6-11").split("-"))
    cfile = Path(sys.argv[sys.argv.index("--cases") + 1]) if "--cases" in sys.argv else H / "leaders_cases.json"
    out = H / "failed_cmds" / cand
    out.mkdir(parents=True, exist_ok=True)
    cases = [c for c in json.loads(cfile.read_text())["cases"] if c["id"] in ids]
    res = {}
    with ProcessPoolExecutor(max_workers=min(2, len(cases)), max_tasks_per_child=1) as pool:
        for cid, margin, fails, orders in pool.map(job, [(cand, c, out, d0, d1) for c in cases]):
            res[cid] = dict(margin=margin, fails=fails, orders=orders)
            print(f"\n{cid} margin {margin}")
            tot = Counter()
            for d in sorted(fails, key=int):
                tot.update(fails[d])
                top = sorted(fails[d].items(), key=lambda x: -x[1])[:6]
                print(f"  day {d}: {sum(fails[d].values()):3d} failed | " + ", ".join(f"{k} {v}" for k, v in top))
                o = orders.get(d) or {}
                bad = {k: v for k, v in o.items() if k.startswith("FAILED")}
                if bad:
                    print(f"         market refused: {bad}")
            print("  total by cause:", dict(sorted(tot.items(), key=lambda x: -x[1])[:12]))
    (out / "failed.json").write_text(json.dumps(res))


if __name__ == "__main__":
    main()

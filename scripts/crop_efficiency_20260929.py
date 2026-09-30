"""Work efficiency per product for both farms of a harness game (user 2026-09-29: "how is our wheat-day / wheat,
wheat-action / wheat and wheat-visit / wheat compared with DSM?"). The game is played through the frozen harness (a
recorded-leader case: our candidate vs the leader's frozen commands, exact credit + recorded weeds) with an engine hook
on every unit command: the tile it acts on and whether it changed anything. Per product source (WHEAT = wheat tiles; MILK
= cows ...), days 6-29, per farm:
  tile-days           crop / animal hours on the board / 24 (the harness ledger)
  units               produced (harvested / collected)
  actions             effective commands on those tiles (PLANT, WATER, FERTILIZE, HARVEST; FEED, CARE, COLLECT)
  visits              a unit's stay on a tile with at least one effective command (a new visit when the unit worked
                      elsewhere or moved in between)
and the ratios per unit produced. One process per game.

usage: crop_efficiency_20260929.py CAND CASE[,CASE...] [--cases leaders_cases.json] [--out DIR]"""
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
H = ROOT / "results/fresh/semantic_h2h_20260929"
MOVES = ("NORTH", "SOUTH", "EAST", "WEST")
SRC = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}


def job(args):
    cand, case, out = args
    import semantic_h2h_20260929 as SH
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    seat_of, log = {}, defaultdict(lambda: defaultdict(Counter))     # seat -> product -> counter
    last = defaultdict(lambda: None)                                  # (seat, unit) -> last work tile
    oa, oe, om = E._apply_unit_action, E._end_of_day, E._process_market

    def apply(farm, private, idx, action, board_size, day, tpd, shed_capacity=100):
        op = action[0] if isinstance(action, list) and action else None
        pos = E._farmer_position(farm, idx)
        t_before = None
        tidx = None
        if pos is not None:
            tidx = pos[1] * board_size + pos[0]
            t = farm["tiles"][pos[1]][pos[0]]
            t_before = dict(t) if isinstance(t, dict) else t
        inv0 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        r = oa(farm, private, idx, action, board_size, day, tpd, shed_capacity)
        # the engine applies every command of player 0, then of player 1, each turn (interpreter loop over state):
        # the first farm seen after a market step is seat 0
        if turn["new"]:
            turn["first"], turn["new"] = id(farm), False
        seat = 0 if id(farm) == turn["first"] else 1
        if op is None or day < 6:
            return r
        if op in MOVES:
            last[(seat, idx)] = None
            return r
        t_after = farm["tiles"][pos[1]][pos[0]] if pos is not None else None
        t_after = dict(t_after) if isinstance(t_after, dict) else t_after
        inv1 = dict(private["inventories"][idx]) if idx < len(private["inventories"]) else {}
        eff = op != "PASS" and (t_before != t_after or inv0 != inv1)
        if not eff:
            return r
        tile = t_before if isinstance(t_before, dict) else (t_after if isinstance(t_after, dict) else {})
        prod = None
        if tile.get("crop"):
            prod = tile["crop"]
        elif tile.get("animal"):
            prod = SRC.get(tile["animal"])
        elif op == "PLANT" and isinstance(t_after, dict):
            prod = t_after.get("crop")
        if prod is None:
            return r
        log[seat][prod]["actions"] += 1
        log[seat][prod]["op:" + op] += 1
        if last[(seat, idx)] != tidx:
            log[seat][prod]["visits"] += 1
        last[(seat, idx)] = tidx
        return r

    turn = {"new": True, "first": None}

    def remap(state):
        turn["new"] = True

    def end(state, env, day):
        remap(state)
        return oe(state, env, day)

    def market(state, env, *a, **k):                # called every step: the farm objects of this step
        remap(state)
        return om(state, env, *a, **k)

    E._apply_unit_action, E._end_of_day, E._process_market = apply, end, market
    import types
    me = Path(__file__).resolve()                  # this runner too (the harness audit rejects unfrozen repo modules)
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
        E._apply_unit_action, E._end_of_day, E._process_market = oa, oe, om
    return case["id"], row.get("margin"), {s: {p: dict(c) for p, c in v.items()} for s, v in log.items()}


def main():
    cand, ids = sys.argv[1], sys.argv[2].split(",")
    cfile = Path(sys.argv[sys.argv.index("--cases") + 1]) if "--cases" in sys.argv else H / "leaders_cases.json"
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else H / "local_eff" / cand
    out.mkdir(parents=True, exist_ok=True)
    cases = [c for c in json.loads(cfile.read_text())["cases"] if c["id"] in ids]
    res = {}
    with ProcessPoolExecutor(max_workers=1, max_tasks_per_child=1) as pool:
        for cid, margin, lg in pool.map(job, [(cand, c, out) for c in cases]):
            res[cid] = dict(margin=margin, log=lg)
            print(cid, "margin", margin, flush=True)
    (out / "efficiency.json").write_text(json.dumps(res))
    # report with the harness ledgers (tile-days, produced) per side
    agg = defaultdict(lambda: defaultdict(Counter))
    for c in cases:
        r = json.loads((out / f"{c['id']}.json").read_text())
        s = r["case"]["seat"]
        for side, seat in (("ours", s), ("leader", 1 - s)):
            D = r["daily"][seat]
            lg = res[c["id"]]["log"].get(str(seat)) or res[c["id"]]["log"].get(seat) or {}
            for prod, key in (("WHEAT", "crop:WHEAT"), ("CARROT", "crop:CARROT"), ("STRAWBERRY", "crop:STRAWBERRY"),
                              ("TOMATO", "crop:TOMATO"), ("MELON", "crop:MELON"), ("MILK", "animal:COW"),
                              ("WOOL", "animal:SHEEP"), ("EGG", "animal:GOOSE")):
                a = agg[side][prod]
                a["tile_days"] += sum(D[d]["tile_hours"].get(key, 0) - D[d - 1]["tile_hours"].get(key, 0) for d in range(7, 31)) / 24
                a["units"] += D[30]["physical"].get("produced:" + prod, 0) - D[6]["physical"].get("produced:" + prod, 0)
                for k, v in (lg.get(prod) or {}).items():
                    a[k] += v
    print(f"\n{len(cases)} games, days 6-29 (totals per game; ratios per unit produced)")
    for prod in ("WHEAT", "CARROT", "STRAWBERRY", "TOMATO", "MELON", "MILK", "WOOL", "EGG"):
        for side in ("ours", "leader"):
            a = agg[side][prod]
            u = max(1e-9, a["units"])
            ops = {k[3:]: round(v / len(cases), 1) for k, v in a.items() if k.startswith("op:")}
            print(f"  {prod:10s} {side:6s} tile-days {a['tile_days'] / len(cases):6.1f} units {a['units'] / len(cases):6.1f} | "
                  f"tile-days/unit {a['tile_days'] / u:5.2f}  actions/unit {a['actions'] / u:5.2f}  visits/unit {a['visits'] / u:5.2f} | ops {ops}")


if __name__ == "__main__":
    main()

"""Build the day 0-5 hand-plan library (one representative current-DSM game per branch) and check the runner
(scripts/semantic_opening_plan_20260929.py) in every recorded current-DSM world against the recorded opponent: dawn-6 board
and cash vs DSM's own recording, the branch chosen, and the failed unit commands.

usage: check_opening_plan_20260929.py [--build] [--limit N]"""
import argparse, glob, gzip, json, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402
E = UE.engine()
LIB = ROOT / "data/semantic_strategy/opening_plan_dsm56619023.json.gz"


def board(f):
    return tuple(sorted((y * 10 + x, v.get("animal") or v.get("crop") or v.get("kind"))
                        for y, row in enumerate(f["tiles"]) for x, v in enumerate(row) if isinstance(v, dict) and v.get("kind") != "WEED"))


def fills_of(x):
    """per step, DSM's market orders as they actually FILLED in its game: [[op, item, units], ...] in fill order
    (HIRE as ["HIRE", "", 1] each)"""
    seat = int(x["seat"]); w = UE.World(x["seed"], x["shops"]); out = [[] for _ in range(144)]
    oc, oh = E._commit_unit, E._do_hire

    def commit(op, item, price, farm, private, market, *a, **k):
        r = oc(op, item, price, farm, private, market, *a, **k)
        if r and farm is w.farms[seat] and w.t < 144:
            row = out[w.t]
            if row and row[-1][:2] == [op, item]:
                row[-1][2] += 1
            else:
                row.append([op, item, 1])
        return r

    def hire(farm, *a, **k):
        m0 = farm["money"]; r = oh(farm, *a, **k)
        if farm is w.farms[seat] and farm["money"] != m0 and w.t < 144:
            out[w.t].append(["HIRE", "", 1])
        return r
    E._commit_unit, E._do_hire = commit, hire
    try:
        for t in range(144):
            a = UE.tape_action(x["actions"], t); o = UE.tape_action(x["opp_actions"], t)
            w.step([a, o] if seat == 0 else [o, a])
    finally:
        E._commit_unit, E._do_hire = oc, oh
    return out


def replay(x, agent=None):
    seat = int(x["seat"]); w = UE.World(x["seed"], x["shops"]); noeff = Counter()
    oa = E._apply_unit_action

    def apply(farm, private, idx, action, *a, **k):
        before = json.dumps(farm, sort_keys=True, default=str) if farm is w.farms[seat] else None
        inv0 = json.dumps(private, sort_keys=True, default=str) if farm is w.farms[seat] else None
        r = oa(farm, private, idx, action, *a, **k)
        if before is not None and isinstance(action, list) and action and action[0] not in ("PASS", "NORTH", "SOUTH", "EAST", "WEST"):
            if json.dumps(farm, sort_keys=True, default=str) == before and json.dumps(private, sort_keys=True, default=str) == inv0:
                noeff[action[0]] += 1
        return r
    E._apply_unit_action = apply
    try:
        for t in range(144):
            a = agent.act(w.obs(seat)) if agent else UE.tape_action(x["actions"], t)
            o = UE.tape_action(x["opp_actions"], t)
            w.step([a, o] if seat == 0 else [o, a])
    finally:
        E._apply_unit_action = oa
    return int(w.farms[seat]["money"]), board(w.farms[seat]), noeff


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--build", action="store_true"); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    tapes = {json.load(gzip.open(p, "rt"))["episode"]: p for p in sorted(glob.glob(str(ROOT / "data/leader_tapes/16732748_56619023/*.json.gz")))}
    if a.build:
        rows = []
        for ep, p in tapes.items():
            x = json.load(gzip.open(p, "rt")); cash, b, _ = replay(x)
            rows.append((ep, cash, b))
        c = Counter(r[2] for r in rows); bA, bB = [b for b, _ in c.most_common(2)]
        cow_b = bA if any(v == "COW" and t in (12, 21) for t, v in bA) else bB
        straw_b = bB if cow_b is bA else bA
        def pick(bb):
            g = sorted((r for r in rows if r[2] == bb), key=lambda r: r[1]); return g[len(g) // 2][0]
        epA, epB = pick(straw_b), pick(cow_b)
        lib = dict(source="DSM 56619023 recordings", strawberry_episode=epA, cow_episode=epB,
                   branches={"strawberry": json.load(gzip.open(tapes[epA], "rt"))["actions"][:144],
                             "cow": json.load(gzip.open(tapes[epB], "rt"))["actions"][:144]},
                   fills={"strawberry": fills_of(json.load(gzip.open(tapes[epA], "rt"))),
                          "cow": fills_of(json.load(gzip.open(tapes[epB], "rt")))},
                   boards={"strawberry": list(straw_b), "cow": list(cow_b)})
        LIB.parent.mkdir(parents=True, exist_ok=True)
        with gzip.GzipFile(filename=str(LIB), mode="wb", mtime=0) as h:
            h.write(json.dumps(lib).encode())
        print("library:", epA, "(strawberry branch),", epB, "(cow branch) ->", LIB)
    import importlib; sys.path.insert(0, str(ROOT / "scripts")); M = importlib.import_module("semantic_opening_plan_20260929")
    lib = json.load(gzip.open(LIB, "rt")); modal = {k: tuple(tuple(x) for x in v) for k, v in lib["boards"].items()}
    res = Counter(); gaps = []; fails = Counter()
    for i, (ep, p) in enumerate(tapes.items()):
        if a.limit and i >= a.limit:
            break
        x = json.load(gzip.open(p, "rt"))
        dc, db, _ = replay(x)
        agent = M.OpeningPlan(LIB)
        oc, ob, ne = replay(x, agent)
        br = agent.branch
        res["same board as DSM here" if ob == db else ("planned %s board" % br if ob == modal[br] else "other board")] += 1
        gaps.append(oc - dc); fails.update(ne)
    n = sum(res.values())
    print(n, "worlds:", dict(res), "| dawn-6 cash vs DSM's recording: mean %+.0f, min %+d, max %+d" % (sum(gaps) / n, min(gaps), max(gaps)))
    print("commands without effect (all worlds):", dict(fails.most_common(8)))


if __name__ == "__main__":
    main()

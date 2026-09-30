"""The recorded leader's cash-limited market outcomes in its REAL game, per step: units committed for every BUY_* order
(op, item), hires and land purchases. Input of the exact-credit lower bound (semantic_h2h_20260929.py
--leader-credit-exact): the leader's purchases then succeed exactly as often as they did for real, whatever its cash.
The plain credit mode let orders that failed for cash in the real game succeed (the tape routers over-request HIREs
and seeds): an extra hand shifts every later hand command, and 11 of 32 recordings broke from day 2 for every arm.

The outcomes come from an exact replay of both recorded action streams (scripts/upkeep_engine.World, which reproduces
both recorded cash totals) with the engine's market functions wrapped the same way the credit mode wraps them.

usage: leader_commits_20260929.py [--cases results/fresh/semantic_h2h_20260929/leaders_cases.json]
  -> results/fresh/semantic_h2h_20260929/leader_commits/<case id>.json {"steps": {step: {"BUY_SEED:MELON": n,
     "HIRE": n, "BUY_LAND": n}}, "final_cash": [..], "recorded": [..]}"""
import argparse
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402


def replay(case):
    game = json.loads(gzip.decompress((H / "study" / case["file"]).read_bytes()))
    E = UE.engine()
    lead = 1 - int(case["seat"])                   # the case seat is ours (the replaced team's); the leader is the other
    log = defaultdict(lambda: defaultdict(int))
    cur = {}
    o_pm, o_cu, o_hi, o_la = E._process_market, E._commit_unit, E._do_hire, E._do_buy_land

    def pm(state, env, *a, **k):
        cur["farm"] = state[0].observation.farms[lead]
        cur["step"] = int(state[0].observation.step)
        return o_pm(state, env, *a, **k)

    def cu(op, item, price, farm, private, market, *a, **k):
        r = o_cu(op, item, price, farm, private, market, *a, **k)
        if r and farm is cur.get("farm") and op.startswith("BUY"):
            log[cur["step"]][f"{op}:{item}"] += 1
        return r

    def hi(farm, *a, **k):
        n0 = len(farm["hands"])
        r = o_hi(farm, *a, **k)
        if farm is cur.get("farm") and len(farm["hands"]) > n0:
            log[cur["step"]]["HIRE"] += 1
        return r

    def la(farm, *a, **k):
        n0 = len(farm.get("unlocked_quadrants") or [])
        r = o_la(farm, *a, **k)
        if farm is cur.get("farm") and len(farm.get("unlocked_quadrants") or []) > n0:
            log[cur["step"]]["BUY_LAND"] += 1
        return r
    E._process_market, E._commit_unit, E._do_hire, E._do_buy_land = pm, cu, hi, la
    try:
        # recordings_leaders: "seat" / "our_actions" = the replaced team (our seat), "opp_actions" = the leader;
        # "shops" per day (31 lists) -> the flat final list of 8
        seat_of = {int(game["seat"]): "our_actions", 1 - int(game["seat"]): "opp_actions"}
        shops = game["shops"][-1] if game["shops"] and isinstance(game["shops"][0], list) else game["shops"]
        w = UE.World(game["seed"], shops)
        for t in range(719):
            w.step([UE.tape_action(game[seat_of[0]], t), UE.tape_action(game[seat_of[1]], t)])
        cash = [w.farms[0]["money"], w.farms[1]["money"]]
    finally:
        E._process_market, E._commit_unit, E._do_hire, E._do_buy_land = o_pm, o_cu, o_hi, o_la
    return dict(case=case["id"], lead_seat=lead, steps={str(s): dict(v) for s, v in sorted(log.items())},
                final_cash=cash, recorded=game.get("rewards"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default=str(H / "leaders_cases.json"))
    a = ap.parse_args()
    cases = json.loads(Path(a.cases).read_text())["cases"]
    out = H / "leader_commits"
    out.mkdir(exist_ok=True)
    ok = 0
    for c in cases:
        r = replay(c)
        match = [round(x) for x in r["final_cash"]] == [round(x) for x in (r["recorded"] or [])]
        ok += match
        (out / f"{c['id']}.json").write_text(json.dumps(r))
        print(c["id"], "cash match" if match else f"MISMATCH {r['final_cash']} vs {r['recorded']}",
              "hires", sum(v.get("HIRE", 0) for v in r["steps"].values()), flush=True)
    print(f"{ok}/{len(cases)} replays reproduce both recorded cash totals -> {out}")


if __name__ == "__main__":
    main()

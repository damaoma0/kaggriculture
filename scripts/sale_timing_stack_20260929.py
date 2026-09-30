"""Sale timing of the semantic stack against its live opponent, from exact replays of finished harness games.

Each game (result + .actions.json written by the harness) is replayed in the engine with its seed and its shops forced
(upkeep_engine.World, the harness's own day // 3 schedule); every committed market unit is recorded (step, side, op,
item, price). The replay must reproduce both final cash totals. Per product and side: units, revenue, average price, the
hour profile of sales, and the price gap against the rival: our units x (rival average - our average), in total and
within the same day (both sides selling the product that day).

usage: sale_timing_stack_20260929.py --dir results/fresh/semantic_h2h_20260929/arms_fresh8_fs/<arm> [--dir ...]
       [--out results/fresh/sale_timing_stack_20260929/<name>.json]"""
import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()


def replay(result, actions):
    w = UE.World(result["case"]["seed"], result["shops"])
    sales, quotes = [], []
    orig = E._commit_unit

    def commit(op, item, price, farm, private, market, cap=100):
        r = orig(op, item, price, farm, private, market, cap)
        if r:
            sales.append((w.t, 0 if farm is w.farms[0] else 1, op, item, float(price)))
        return r
    E._commit_unit = commit
    try:
        while w.t < 719:
            quotes.append(dict(w.market["prices"]))       # quotes at the start of step t (before its trades)
            w.step([UE.tape_action(actions[i], w.t) for i in (0, 1)])
    finally:
        E._commit_unit = orig
    return sales, quotes, [w.farms[0]["money"], w.farms[1]["money"]]


def analyse(result, sales, quotes):
    seat = result["case"]["seat"]
    side = {seat: "own", 1 - seat: "rival"}
    units, rev = defaultdict(Counter), defaultdict(Counter)
    day_u, day_r = defaultdict(Counter), defaultdict(Counter)
    hours = defaultdict(Counter)
    for t, s, op, item, p in sales:
        if op != "SELL":
            continue
        k = side[s]
        units[k][item] += 1
        rev[k][item] += p
        day_u[(k, t // 24)][item] += 1
        day_r[(k, t // 24)][item] += p
        hours[(k, item)][t % 24] += 1
    gap, gap_day = Counter(), Counter()
    for item in set(units["own"]) | set(units["rival"]):
        if units["own"][item] and units["rival"][item]:
            gap[item] = units["own"][item] * (rev["rival"][item] / units["rival"][item] - rev["own"][item] / units["own"][item])
        for d in range(30):
            uo, ur = day_u[("own", d)][item], day_u[("rival", d)][item]
            if uo and ur:
                gap_day[item] += uo * (day_r[("rival", d)][item] / ur - day_r[("own", d)][item] / uo)
    vs_mean, vs_max = Counter(), Counter()        # our units: day's mean / best quoted price minus the price we got
    for t, s, op, item, p in sales:
        if op == "SELL" and side[s] == "own":
            day = [q.get(item, 0) for q in quotes[24 * (t // 24):24 * (t // 24) + 24]]
            vs_mean[item] += sum(day) / len(day) - p
            vs_max[item] += max(day) - p
    return dict(vs_day_mean=dict(vs_mean), vs_day_max=dict(vs_max),
                units={k: dict(v) for k, v in units.items()}, revenue={k: dict(v) for k, v in rev.items()},
                gap=dict(gap), gap_same_day=dict(gap_day),
                hours={f"{k}|{i}": dict(v) for (k, i), v in hours.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = []
    for d in a.dir:
        for f in sorted(glob.glob(os.path.join(ROOT, d, "*.json"))):
            if f.endswith(".actions.json") or f.endswith("summary.json"):
                continue
            r = json.load(open(f))
            if not r.get("completed"):
                continue
            acts = json.load(open(f[:-5] + ".actions.json"))
            sales, quotes, final = replay(r, acts)
            ok = [round(x) for x in final] == [round(x) for x in r["cash_by_seat"]]
            row = dict(dir=d, case=r["case"], margin=r["margin"], replay_matches=ok, **analyse(r, sales, quotes))
            rows.append(row)
            print(f"{Path(d).name} {r['case']['id']} margin {r['margin']:+.0f} replay==result {ok} | price gap vs rival "
                  f"{sum(row['gap'].values()):+.0f} (same day {sum(row['gap_same_day'].values()):+.0f})", flush=True)
    if a.out:
        out = ROOT / a.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows))
    agg, aggd, u, uo, vm, vx = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    for r in rows:
        vm.update(r["vs_day_mean"])
        vx.update(r["vs_day_max"])
        agg.update(r["gap"])
        aggd.update(r["gap_same_day"])
        u.update(r["units"].get("own", {}))
        uo.update(r["units"].get("rival", {}))
    n = max(1, len(rows))
    print(f"\n{len(rows)} games; {sum(r['replay_matches'] for r in rows)} replays reproduce both cash totals")
    print("per game, by product: our units / rival units | price gap vs rival (positive = we sold cheaper) | same-day part"
          " | day's mean quote - ours | day's best quote - ours")
    for item in sorted(set(agg) | set(vm), key=lambda k: -vm[k]):
        print(f"  {item:11s} {u[item] / n:6.1f} / {uo[item] / n:6.1f} | {agg[item] / n:+7.0f} | {aggd[item] / n:+7.0f} | "
              f"{vm[item] / n:+7.0f} | {vx[item] / n:+7.0f}")
    print(f"  {'total':11s} {'':15s} | {sum(agg.values()) / n:+7.0f} | {sum(aggd.values()) / n:+7.0f} | "
          f"{sum(vm.values()) / n:+7.0f} | {sum(vx.values()) / n:+7.0f}")


if __name__ == "__main__":
    main()

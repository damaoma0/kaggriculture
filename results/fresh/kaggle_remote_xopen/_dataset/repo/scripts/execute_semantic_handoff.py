"""Execute five preselected feasible semantic handoff windows in the engine.

The target world's recorded shops and opponent actions remain fixed. The three
arms share the exact recorded prefix; only own actions in the next three days
change. This is a bounded diagnostic, not a full-game policy evaluation.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
import time

from fragments.continuation_calendar import adapt_calendar
from fragments.continuation_projection import check_window
from fragments import continuation_executor as executor
import research_labour_profit as R

from probe_semantic_handoff import ROOT, donor_window, read


OUT = ROOT / "results/fresh/semantic_tapes/handoff_exact_probe.json"


def compile_actions(obs, profile):
    node = adapt_calendar(obs, donor_window(profile, obs["day"]))
    node["hire_to"] = 12
    executor.set_deadline(time.perf_counter() + .6)
    try:
        result = check_window(obs, node, executor)
    finally:
        executor.set_deadline(None)
    assert result["ok"], result.get("failure")
    assert len(result["actions"]) == 72
    return result["actions"]


def farm_assets(state, seat):
    result = {}
    for row in state[0].observation.farms[seat]["tiles"]:
        for tile in row:
            if isinstance(tile, dict):
                item = tile.get("crop") or tile.get("animal")
                if item:
                    result[item] = result.get(item, 0) + 1
    return result


def run_arm(game, pair, seat, start, stop, actions=None):
    trial = deepcopy(pair)
    if actions is not None:
        trial[seat][start:stop] = deepcopy(actions)
    with R.Simulator(game) as sim:
        result = sim.run(sim.initial, 0, stop, trial, capture=True)
    farm = result["state"][0].observation.farms[seat]
    return dict(cash=float(farm["money"]), rival_cash=float(result["state"][0].observation.farms[1-seat]["money"]),
                assets=farm_assets(result["state"], seat),
                sales=R.economic(result["events"], seat)["revenue"],
                spend=R.economic(result["events"], seat)["spend"],
                status=str(result["state"][seat].status))


def main():
    previous = read(ROOT / "results/fresh/semantic_tapes/handoff_probe.json")
    chosen = [x for x in previous["rows"] if x["current"]["ok"] and x["alternative"]["ok"]][:5]
    assert len(chosen) == 5
    profiles = {x["episode"]: x for x in read(ROOT / "results/fresh/semantic_tapes/compact_profiles.json")}
    games = {g["episode"]: g for g in read(ROOT / "results/fresh/tape_gap_plans/dataset_primary.json")["games"]}
    rows = []
    for case in chosen:
        episode, day, seat = case["query_episode"], case["day"], case["seat"]
        obs = games[episode]["checkpoints"][str(day)]["observation"]
        start, stop = day * 24, (day + 3) * 24
        with gzip.open(ROOT / f"data/ladder_panel/56395605/{episode}.json.gz", "rt", encoding="utf-8") as handle:
            game = json.load(handle)
        assert game["seat"] == seat
        pair = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
        incumbent = compile_actions(obs, profiles[case["incumbent_episode"]])
        candidate = compile_actions(obs, profiles[case["candidate_episode"]])
        actual = run_arm(game, pair, seat, start, stop)
        baseline = run_arm(game, pair, seat, start, stop, incumbent)
        switched = run_arm(game, pair, seat, start, stop, candidate)
        rows.append(dict(episode=episode, day=day, seat=seat,
                         actual=actual, incumbent_compiled=baseline, candidate_compiled=switched,
                         candidate_minus_incumbent_cash=switched["cash"]-baseline["cash"],
                         candidate_minus_actual_cash=switched["cash"]-actual["cash"]))
        print(json.dumps({k: rows[-1][k] for k in ("episode", "day", "candidate_minus_incumbent_cash", "candidate_minus_actual_cash")}), flush=True)
    summary = dict(cases=len(rows), candidate_better_than_compiled_incumbent=sum(x["candidate_minus_incumbent_cash"] > 0 for x in rows),
                   mean_candidate_minus_compiled_incumbent=sum(x["candidate_minus_incumbent_cash"] for x in rows)/len(rows),
                   protocol="First five cases with both arms feasible in the prior projection, in saved query order. Target shop path and recorded opponent actions fixed; own actions replaced only for the next 72 hours.")
    OUT.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

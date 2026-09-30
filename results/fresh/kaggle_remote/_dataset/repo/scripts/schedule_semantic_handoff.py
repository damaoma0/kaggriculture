"""Apply the supplied-plan labor scheduler to compiled semantic windows.

The labor scheduler receives only the current observation and the first 48
hours of an already compiled candidate. Its answer replaces those 48 hours;
the third day remains from the same compiled plan. Exact-engine outcomes are
measured on the recorded target shop path and fixed opponent action stream.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import gzip
import json
from pathlib import Path

import research_labour_profit as R
from test_labour_selfplay import choose
from execute_semantic_handoff import compile_actions, run_arm
from probe_semantic_handoff import ROOT, read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    previous = read(ROOT / "results/fresh/semantic_tapes/handoff_probe.json")
    chosen = [x for x in previous["rows"] if x["current"]["ok"] and x["alternative"]["ok"]][:args.limit]
    profiles = {x["episode"]: x for x in read(ROOT / "results/fresh/semantic_tapes/compact_profiles.json")}
    games = {g["episode"]: g for g in read(ROOT / "results/fresh/tape_gap_plans/dataset_primary.json")["games"]}
    rows = []
    for case in chosen:
        episode, day, seat = case["query_episode"], case["day"], case["seat"]
        obs = games[episode]["checkpoints"][str(day)]["observation"]
        start, stop = day * 24, (day + 3) * 24
        with gzip.open(ROOT / f"data/ladder_panel/56395605/{episode}.json.gz", "rt", encoding="utf-8") as handle:
            game = json.load(handle)
        pair = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
        candidate = compile_actions(obs, profiles[case["candidate_episode"]])
        with R.Simulator(game) as sim:
            prefix = sim.run(sim.initial, 0, start, pair)
        live_obs = deepcopy(prefix["state"][seat].observation)
        assert live_obs.step == start and live_obs.player == seat
        assert live_obs.farms[seat]["tiles"] == obs["farms"][seat]["tiles"]
        selected, decision = choose(live_obs, candidate[:48], "wage", rounds=20)
        scheduled = deepcopy(candidate)
        scheduled[:48] = selected
        before = run_arm(game, pair, seat, start, stop, candidate)
        after = run_arm(game, pair, seat, start, stop, scheduled)
        row = dict(episode=episode, day=day, seat=seat,
                   selector={k: decision.get(k) for k in ("name", "gain", "wage", "fallback", "seconds", "candidates")},
                   action_changes=sum(a != b for a, b in zip(candidate, scheduled)),
                   cash_before=before["cash"], cash_after=after["cash"],
                   cash_delta=after["cash"]-before["cash"],
                   assets_equal=before["assets"] == after["assets"],
                   sales_equal=before["sales"] == after["sales"])
        rows.append(row)
        print(json.dumps(row), flush=True)
    out = ROOT / "results/fresh/semantic_tapes/scheduled_handoff_probe.json"
    out.write_text(json.dumps(dict(rows=rows, summary=dict(cases=len(rows),
        changed=sum(r["action_changes"] > 0 for r in rows),
        mean_cash_delta=sum(r["cash_delta"] for r in rows)/len(rows) if rows else 0)), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

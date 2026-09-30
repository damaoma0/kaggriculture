"""One bounded semantic crop edit on the intact m1 plan, then labor scheduling.

The change is picked from the offline conservative retrieval audit: at day 21
of episode 111291994 the donor requests one tomato instead of one wheat.
Only a funded seed order and one known-successful PLANT command are changed.
All future actions remain the recorded m1 stream for this fixed-world probe.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path

import research_labour_profit as R
from test_labour_selfplay import choose


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_tapes/inplace_edit_probe.json"
EPISODE, DAY = 111291994, 21
START, END = DAY * 24, 719
SEED_STEP, PLANT_STEP, UNIT = 505, 509, 6


def run(game, actions, seat, stop, capture_start=False):
    with R.Simulator(game) as sim:
        result = sim.run(sim.initial, 0, stop, actions, capture=True, snapshots=capture_start)
    own = result["state"][0].observation.farms[seat]
    rival = result["state"][0].observation.farms[1-seat]
    assets = {}
    for row in own["tiles"]:
        for tile in row:
            if isinstance(tile, dict):
                p = tile.get("crop") or tile.get("animal")
                if p:
                    assets[p] = assets.get(p, 0) + 1
    return dict(cash=float(own["money"]), rival_cash=float(rival["money"]),
                margin=float(own["money"]-rival["money"]), assets=assets,
                revenue=R.economic(result["events"], seat)["revenue"],
                spend=R.economic(result["events"], seat)["spend"],
                output_events=[w for w in result["work"] if w["seat"] == seat and
                               START <= w["t"] < min(stop, START + 72) and
                               w["cmd"][0] in ("PLANT", "HARVEST", "COLLECT_FERTILIZER")],
                buy_tomato_seed=sum(1 for t, s, op, item, _ in result["events"]
                                    if s == seat and t == SEED_STEP and op == "BUY_SEED" and item == "TOMATO"),
                observation_at_start=deepcopy(result["snapshots"][START][seat].observation) if capture_start else None)


def main():
    with gzip.open(ROOT / f"data/ladder_panel/56395605/{EPISODE}.json.gz", "rt", encoding="utf-8") as handle:
        game = json.load(handle)
    seat = int(game["seat"])
    original = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
    edited = deepcopy(original)
    assert original[seat][PLANT_STEP]["hands"][UNIT-1] == ["PLANT", "WHEAT"]
    assert len(original[seat][SEED_STEP]["market"]) < 10
    edited[seat][SEED_STEP]["market"].append(["BUY_SEED", "TOMATO", 1])
    edited[seat][PLANT_STEP]["hands"][UNIT-1] = ["PLANT", "TOMATO"]
    baseline = run(game, original, seat, START+72, capture_start=True)
    assert any(w["t"] == PLANT_STEP and w["unit"] == UNIT and w["cmd"] == ["PLANT", "WHEAT"]
               for w in baseline["output_events"])
    raw = run(game, edited, seat, START+72)
    assert raw["buy_tomato_seed"] == 1
    assert any(w["t"] == PLANT_STEP and w["unit"] == UNIT and w["cmd"] == ["PLANT", "TOMATO"]
               for w in raw["output_events"])
    selected, decision = choose(baseline["observation_at_start"], edited[seat][START:START+48], "wage", rounds=20)
    scheduled = deepcopy(edited)
    scheduled[seat][START:START+48] = selected
    scheduled_window = run(game, scheduled, seat, START+72)
    terminal = {name: run(game, actions, seat, END) for name, actions in
                (("baseline", original), ("raw_edit", edited), ("scheduled_edit", scheduled))}
    def compact(x):
        return {k: v for k, v in x.items() if k not in ("output_events", "observation_at_start")}
    result = dict(episode=EPISODE, day=DAY, seat=seat,
                  change="Buy one tomato seed at hour 1; replace one successful day-21 WHEAT planting with TOMATO on the same tile.",
                  scheduler={k: decision.get(k) for k in ("name", "gain", "wage", "fallback", "seconds", "candidates")},
                  first_48_action_changes=sum(a != b for a, b in zip(edited[seat][START:START+48], selected)),
                  day24={"baseline": compact(baseline), "raw_edit": compact(raw), "scheduled_edit": compact(scheduled_window)},
                  final={name: compact(x) for name, x in terminal.items()},
                  limitation="Fixed recorded future actions and shops; this is not an adaptive agent or causal market forecast.")
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"scheduler": result["scheduler"], "day24": {k: v["margin"] for k,v in result["day24"].items()},
                      "final": {k: v["margin"] for k,v in result["final"].items()}}, indent=2), flush=True)


if __name__ == "__main__":
    main()

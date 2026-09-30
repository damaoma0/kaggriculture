"""Replay recorded decisions through the standalone selected entry point."""
from collections import Counter
from copy import deepcopy
import json

from evaluate_boards import ROOT, module_at, observation


def main():
    folder = ROOT / "results/fresh/growth_opening"
    selected = json.loads((folder / "selection.json").read_text())["name"]
    module = module_at("selected_growth", ROOT / "agents/opening_v2.py")
    decisions = 0
    records = list(folder.glob(f"{selected}-86201-seat*"))
    assert len(records) == 2
    for record in records:
        replay = json.loads((record / "opening.json").read_text())
        summary = json.loads((record / "summary.json").read_text())
        seat = summary["seat"]
        assert len(replay["steps"]) == 217
        assert not any(summary["opening_losses"].values())
        for before, after in zip(replay["steps"], replay["steps"][1:]):
            obs = observation(before, seat)
            original = deepcopy(obs)
            action = module.agent(obs)
            assert obs == original, "Observation mutation"
            assert action == after[seat]["action"], "Standalone entry point mismatch"
            assert len(action["market"]) <= 10
            assert len(action["hands"]) == len(obs["farms"][seat]["hands"])
            plants = Counter(a[1] for a in [action["farmer"], *action["hands"]] if a[0] == "PLANT")
            assert all(n <= obs["private"]["seeds"].get(c, 0) for c, n in plants.items())
            decisions += 1
    print(f"PASS: {decisions} matching decisions, both seats on a new seed, no observation mutation, no seed overdraw or opening deaths.")


if __name__ == "__main__":
    main()

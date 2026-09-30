"""Check the selected file entry point against recorded opening trajectories."""
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location("opening_under_test", ROOT / "agents/opening_v1.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    count = 0
    for folder in sorted((ROOT / "results/fresh/openings").glob("sheep6-seed*-seat*")):
        summary = json.loads((folder / "summary.json").read_text())
        replay = json.loads((folder / "replay.json").read_text())
        seat = summary["seat"]
        assert len(replay["steps"]) == 217
        assert replay["info"]["seed"] == summary["seed"]
        assert not summary["actions"].get("crop_losses", 0)
        assert not summary["actions"].get("animal_losses", 0)
        for before, after in zip(replay["steps"], replay["steps"][1:]):
            obs = deepcopy(before[seat]["observation"])
            # The framework stores shared step/state on seat 0 and merges it
            # into the observation before calling either player.
            for key in ("step", "day", "hour", "farms", "market", "town"):
                obs[key] = deepcopy(before[0]["observation"][key])
            original = deepcopy(obs)
            action = module.agent(obs)
            assert obs == original, "Agent mutated its observation"
            assert action == after[seat]["action"], "File entry point differs from evaluated policy"
            assert len(action["market"]) <= 10
            assert len(action["hands"]) == len(obs["farms"][seat]["hands"])
            plants = Counter(a[1] for a in [action["farmer"], *action["hands"]] if a[0] == "PLANT")
            assert all(n <= obs["private"]["seeds"].get(c, 0) for c, n in plants.items()), "Atomic PLANT overdraw"
            assert all(s["status"] in ("ACTIVE", "DONE") for s in after)
            count += 1
        print(f"Verified {folder.name}")
    assert count == 6 * 216, count
    print(f"PASS: {count} decisions, six held-out trajectories, no observation mutation, valid seed allocation, matching entry point.")


if __name__ == "__main__":
    main()

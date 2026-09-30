"""Run an agent through the Kaggriculture environment locally.

Usage:
    python scripts/run_local.py agents/baseline.py [agents/other.py ...]

Requires `kaggle-environments` with the kaggriculture environment registered. If the
environment name differs, adjust ENV_NAME after checking the competition page.
"""
import sys

from kaggle_environments import make

ENV_NAME = "kaggriculture"


def main(agent_paths):
    env = make(ENV_NAME, debug=True)
    env.run(agent_paths)
    for i, state in enumerate(env.state):
        print(f"agent {i}: reward={state.reward} status={state.status}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])

"""Baseline Kaggriculture agent.

The environment calls `agent(obs)` once per turn (1 second limit) and expects
{"farmer": [...], "hands": [[...], ...], "market": [[...], ...]}.
See docs/environment.md for the observation schema and action vocabulary.
This is a placeholder that does nothing; replace with a real policy.
"""


def agent(obs):
    return {"farmer": ["PASS"], "hands": [], "market": []}

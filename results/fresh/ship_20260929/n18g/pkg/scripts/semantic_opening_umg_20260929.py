"""Days 0-5 of the semantic stack from the Mother-Goose tape router of the packaged V9-lite (agents/mgt_y3.py, the agent
under V9-lite's value search, which starts on day 12): 12 melons and 2 cows / 2 sheep on day 0, a cow on each of days 2
and 3, instead of the DSM opening's 6 + 4 melons and 2 cows / 3 sheep with strawberries on days 2-3.

The agent runs unchanged in its own module namespace (its globals keep their own state; the opponent's copy of the same
package is a different module). The caller owns strategy / tiling from step 144, exactly as with the DSM opening.
Melon arithmetic on the engine price curve: results/fresh/... melon_curve_field_20260929.py (user 2026-09-29)."""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "agents/mgt_y3.py"


class OpeningUMG:
    def __init__(self, path=SOURCE):
        name = "_semantic_opening_mgt_y3"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module                 # dataclasses and similar look their module up here
        spec.loader.exec_module(module)
        self.module = module
        entry = getattr(module, "mgt_kaggle_entry", None)
        if entry is None:                          # Kaggle's rule: the last new callable in the file
            entry = [v for k, v in vars(module).items() if callable(v) and not k.startswith("__")][-1]
        self.entry = entry
        self.history = []
        self.stats = Counter()

    def act(self, obs, configuration=None):
        step = int(obs["step"])
        if not 0 <= step < 144:
            raise ValueError("Opening is defined only for steps 0 through 143; hand off on day 6.")
        if step % 24 == 0:
            self.history.append(dict(day=step // 24, source="mgt_y3"))
        return self.entry(obs, configuration)

    __call__ = act


def make_opening():
    return OpeningUMG()

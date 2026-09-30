"""Selected local opening, frozen before the shop-grid test panel.

Research opening only; requires sibling modules. Evaluation switches both
farms to the common replanting controller at step 216.
"""
import importlib.util
from pathlib import Path

NAME = 'shop-adaptive'
CONFIG = {'default': 'router', 'by_shop': {'BAKERY': {'COW': 4, 'SHEEP': 8, 'crop': 'STRAWBERRY', 'hands': 8}, 'BRUNCH_SPOT': 'router', 'FARMERS_MARKET': 'router', 'ICE_CREAM_SHOP': 'router', 'PET_CAFE': 'router', 'PIZZA_SHOP': 'router', 'SMOOTHIE_SHOP': 'router', 'YARN_STORE': {'COW': 4, 'SHEEP': 8, 'crop': 'STRAWBERRY', 'hands': 8}}}
_policy = None


def agent(obs):
    global _policy
    if _policy is None or obs["step"] == 0:
        filename = "opening_v2.py" if NAME == "growth-control" else "shop_opening.py"
        spec = importlib.util.spec_from_file_location("selected_opening_module", Path(__file__).with_name(filename))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _policy = module.GrowthOpening(CONFIG) if NAME == "growth-control" else module.ShopOpening(CONFIG)
    return _policy(obs)

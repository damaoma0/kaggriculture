"""Public-board copying with independent worker scheduling; local research agent.

Uses only current public opponent tiles, land and crew. No opponent actions,
inventories, future route or seed are read. Requires sibling opening_v2.py.
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("copy_scheduler", Path(__file__).with_name("opening_v2.py"))
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
FIRST = {"WHEAT": 4, "CARROT": 3, "MELON": 10, "STRAWBERRY": 10, "TOMATO": 8}


class CopyPolicy(_base.OpeningPolicy):
    def __init__(self):
        super().__init__({"animals": [], "melons": 0, "hands": 1, "land_day": 99})
        self.opponent = None

    def layout(self, farm, day):
        targets = {}
        for y, row in enumerate(farm["tiles"]):
            for x, own in enumerate(row):
                if own == "LOCKED":
                    continue
                seen = self.opponent["tiles"][y][x]
                # Finish and protect our existing investments even when the
                # opponent already harvested or changed the corresponding tile.
                if isinstance(own, dict) and own.get("animal"):
                    targets[x,y] = own["animal"]
                elif isinstance(own, dict) and own.get("kind") == "PLANT":
                    targets[x,y] = own["crop"]
                elif isinstance(seen, dict):
                    if seen.get("animal") and day < 20:
                        targets[x,y] = seen["animal"]
                    elif seen.get("kind") == "PLANT" and day + FIRST[seen["crop"]] <= 29:
                        targets[x,y] = seen["crop"]
        return targets

    def __call__(self, obs):
        me = obs["player"]
        farm = obs["farms"][me]
        self.opponent = obs["farms"][1-me]
        targets = self.layout(farm, obs["day"])
        self.config["animals"] = [v for v in targets.values() if v in _base.ANIMAL_COST]
        self.config["hands"] = min(12, max(1, len(self.opponent["hands"])))
        # This first copier supports the NW and NE land used by this router.
        self.config["land_day"] = 0 if "NE" in self.opponent["unlocked_quadrants"] and obs["day"] < 20 else 99
        self.config["land_buffer"] = 300
        action = super().__call__(obs)
        if obs["step"] >= 712:
            acts = [action["farmer"], *action["hands"]]
            shed = dict(obs["private"]["shed"])
            for i, (pos, inv) in enumerate(zip([farm["farmer"], *farm["hands"]], obs["private"]["inventories"])):
                if any(n for item,n in inv.items() if item not in _base.ANIMAL_COST):
                    goal = min(_base.SHED, key=lambda p: _base.distance(pos,p))
                    if _base.distance(pos,goal) <= 718-obs["step"]:
                        acts[i] = ["DROP"] if tuple(pos) == goal else _base.move(pos,goal)
                        if acts[i] == ["DROP"]:
                            for item,n in inv.items():
                                take = min(n, max(0, 100-sum(shed.values())))
                                shed[item] = shed.get(item,0)+take
            action = {"farmer": acts[0], "hands": acts[1:], "market": [["SELL",p,n] for p,n in shed.items() if n and p not in _base.ANIMAL_COST][:10]}
        return action


_policy = None


def agent(obs):
    global _policy
    if _policy is None or obs["step"] == 0:
        _policy = CopyPolicy()
    return _policy(obs)

"""Local opening experiments that preserve the public router's movement schedule."""
import importlib.util
from pathlib import Path


class RouterOpeningVariant:
    def __init__(self, config):
        spec = importlib.util.spec_from_file_location("variant_router", Path(__file__).parent/"public/tschinkel_router_v31.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.router = self.module.Agent()
        self.config = config

    def __call__(self, obs):
        action = self.router.act(obs)
        mapping = self.config.get("mapping", {})
        for a in [action["farmer"],*action["hands"],*action["market"]]:
            if len(a)>1 and a[0] in ("BUY_SEED","BUY_ANIMAL","PICKUP","PLACE","PLANT"):
                a[1] = mapping.get(a[1],a[1])
        if self.config.get("sell_fertilizer"):
            for i,a in enumerate([action["farmer"],*action["hands"]]):
                if a[0]=="FERTILIZE":
                    if i==0: action["farmer"]=["PASS"]
                    else: action["hands"][i-1]=["PASS"]
            n=obs["private"]["shed"].get("FERTILIZER",0)
            if n and len(action["market"])<10 and not any(a[:2]==["SELL","FERTILIZER"] for a in action["market"]):
                action["market"].append(["SELL","FERTILIZER",n])
        if "hire_cap" in self.config and len(obs["farms"][obs["player"]]["hands"])>=self.config["hire_cap"]:
            action["market"]=[a for a in action["market"] if a[0]!="HIRE"]
        if self.config.get("sales_first"):
            action["market"].sort(key=lambda a:a[0]!="SELL")
        return action

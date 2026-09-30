"""Router prefix through day 2, configurable observed-state investment thereafter."""
import importlib.util
from pathlib import Path


def load(name,path):
    s=importlib.util.spec_from_file_location(name,Path(__file__).parent/path)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m


base=load("shop_scheduler","opening_v2.py")


class Investments(base.OpeningPolicy):
    def __init__(self,cfg):
        super().__init__({"animals":[],"land_day":0,"land_buffer":50,"hands":cfg["hands"]})
        self.cfg=cfg

    def layout(self,farm,day):
        result={}
        for y,row in enumerate(farm["tiles"]):
            for x,t in enumerate(row):
                if isinstance(t,dict) and (t.get("animal") or t.get("kind")=="PLANT"):
                    result[x,y]=t.get("animal") or t["crop"]
        for kind in ("COW","SHEEP"):
            need=max(0,self.cfg[kind]-sum(v==kind for v in result.values()))
            free=sorted(((x,y) for y in range(5) for x in range(10) if (x,y) not in result and farm["tiles"][y][x]!="LOCKED"),key=lambda p:(min(base.distance(p,s) for s in base.SHED),p[1],p[0]))
            for p in free[:need]: result[p]=kind
        for y in range(5):
            for x in range(10):
                if (x,y) not in result and farm["tiles"][y][x]!="LOCKED":
                    result[x,y]=self.cfg["crop"]
        return result

    def __call__(self,obs):
        farm=obs["farms"][obs["player"]]
        self.config["animals"]=[v for v in self.layout(farm,obs["day"]).values() if v in base.ANIMAL_COST]
        return super().__call__(obs)


class ShopOpening:
    def __init__(self,config):
        self.config=config
        self.router=load("shop_prefix_router","public/tschinkel_router_v31.py").Agent()
        self.tail=None
        self.choice=None

    def __call__(self,obs):
        if obs["step"]<72:
            return self.router.act(obs)
        if self.choice is None:
            self.choice=self.config.get("by_shop",{}).get(obs["town"]["unlocked_shops"][0],self.config.get("default","router"))
            if self.choice!="router": self.tail=Investments(self.choice)
        return self.router.act(obs) if self.choice=="router" else self.tail(obs)

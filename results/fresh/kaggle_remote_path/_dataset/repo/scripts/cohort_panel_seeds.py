"""Choose shop coverage without inspecting any game outcomes."""
import random,json
from benchmark_crop_replacement import SHOP_SEED_XOR
SHOPS=sorted(['BAKERY','PIZZA_SHOP','BRUNCH_SPOT','YARN_STORE','ICE_CREAM_SHOP','PET_CAFE','SMOOTHIE_SHOP','FARMERS_MARKET'])
if __name__=='__main__':
    selected={}
    for seed in range(158000,159000):
        schedule=random.Random(seed^SHOP_SEED_XOR).choices(SHOPS,k=8)
        selected.setdefault(schedule[0],dict(seed=seed,shops=schedule))
        if len(selected)==8:break
    print(json.dumps(dict(selection='First seed for each first-shop type in a fixed seed range; selected before outcomes.',cases=list(selected.values())),indent=2))

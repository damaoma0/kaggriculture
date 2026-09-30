"""Inspect successful baseline work for the directionally aligned day-15 case."""
from collections import Counter
from copy import deepcopy
import gzip
import json
from pathlib import Path

import research_labour_profit as R


ROOT = Path(__file__).resolve().parents[1]
EPISODE, DAY = 111289863, 15
START = DAY * 24


def main():
    with gzip.open(ROOT / f"data/ladder_panel/56395605/{EPISODE}.json.gz", "rt", encoding="utf-8") as f:
        game = json.load(f)
    seat = int(game["seat"])
    actions = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
    with R.Simulator(game) as sim:
        result = sim.run(sim.initial, 0, 719, actions, capture=True, snapshots=True)
    obs = result["snapshots"][START][seat].observation
    own = obs.farms[seat]
    own_work = [w for w in result["work"] if w["seat"] == seat and START <= w["t"] < 719]
    planting = [{k:w[k] for k in ("t", "unit", "pos", "cmd")} for w in own_work
                if w["cmd"] == ["PLANT", "WHEAT"] and START <= w["t"] < START+24]
    tile_visits = {}
    work_index = {(w["t"], w["unit"]):w for w in own_work}
    for plant in planting:
        pos = plant["pos"]
        visits = []
        for t in range(plant["t"]+1,719):
            snapshot = result["snapshots"][t][seat].observation
            farm = snapshot.farms[seat]
            positions = [farm["farmer"], *farm["hands"]]
            cmds = [actions[seat][t]["farmer"], *actions[seat][t]["hands"]]
            for unit,(xy,cmd) in enumerate(zip(positions,cmds)):
                if tuple(xy) == tuple(pos) and cmd and cmd[0] not in ("PASS","NORTH","SOUTH","EAST","WEST"):
                    w = work_index.get((t,unit))
                    visits.append({"t":t,"day":t//24,"unit":unit,"cmd":cmd,
                                   "success":bool(w and tuple(w["pos"])==tuple(pos)),
                                   "delta":w["delta"] if w and tuple(w["pos"])==tuple(pos) else None})
        tile_visits[f"{plant['t']}:{pos}"] = visits
    crops = Counter()
    for row in own["tiles"]:
        for tile in row:
            if isinstance(tile,dict) and tile.get("crop"):
                crops[tile["crop"]] += 1
    tomato_sales=[{"t":t,"seat":s,"price":price} for t,s,op,item,price in result["events"]
                  if t >= START and op == "SELL" and item == "TOMATO"]
    print(json.dumps({"seat":seat,"start_money":own["money"],"start_shed":obs.private["shed"],
        "start_seeds":obs.private.get("seeds"),"start_crops":dict(crops),"planting":planting,
        "tile_visits":tile_visits,"tomato_sales":tomato_sales,
        "final_money":[f["money"] for f in result["state"][0].observation.farms]},indent=2))


if __name__ == "__main__":
    main()

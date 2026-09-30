"""Audit strawberry sale hours and per-plant yield in the fixed shop replay."""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import json

import research_labour_profit as R
from probe_semantic_handoff import ROOT
from probe_earlier_strawberry_portfolio import EPISODE, END
from trace_reveal_aligned_strawberry_timeline import variant


OUT = ROOT / "results/fresh/semantic_tapes/strawberry_sales_and_yields.json"


def replay(game, actions):
    R.engine()
    E = R.E
    refresh = E._daily_refresh_plants
    ticks = []
    strawberry_discarded_at_day_end = []
    drop_call_count = 0
    with R.Simulator(game) as sim:
        def traced_refresh(farm, current_day, turns_per_day):
            seat = sim.seats[id(farm)]
            before = {}
            for y, row in enumerate(farm["tiles"]):
                for x, tile in enumerate(row):
                    if isinstance(tile, dict) and tile.get("crop") == "STRAWBERRY":
                        before[x, y] = deepcopy(tile)
            refresh(farm, current_day, turns_per_day)
            for (x, y), old in before.items():
                day = current_day + 1
                age = day - old["planted_day"] - 10
                if age < 0 or age % 2 or age // 2 >= 4:
                    continue
                new = farm["tiles"][y][x]
                survived = isinstance(new, dict) and new.get("crop") == "STRAWBERRY" and new.get("planted_day") == old["planted_day"]
                possible = 2 if old["watered_today"] and old.get("fertilized_until_day", -1) >= current_day else 1
                gained = new["yield_units"] - old["yield_units"] if survived else 0
                ticks.append({"seat": seat, "pos": [x, y], "planted_day": old["planted_day"],
                              "production_day": day, "production_number": age // 2 + 1,
                              "possible_units": possible, "gained_units": gained,
                              "cap_loss": max(0, possible - gained) if survived else 0,
                              "held_before": old["yield_units"],
                              "held_after": new["yield_units"] if survived else 0,
                              "watered": old["watered_today"], "survived": survived})
        E._daily_refresh_plants = traced_refresh
        drop = E._drop_inventories_to_shed
        def traced_drop(private, capacity):
            nonlocal drop_call_count
            seat = drop_call_count % 2
            drop_call_count += 1
            before = private["shed"].get("STRAWBERRY", 0) + sum(
                inv.get("STRAWBERRY", 0) for inv in private["inventories"])
            drop(private, capacity)
            after = private["shed"].get("STRAWBERRY", 0)
            if before > after:
                strawberry_discarded_at_day_end.append({"day": sim.t // 24, "seat": seat,
                                                         "units": before - after})
        E._drop_inventories_to_shed = traced_drop
        try:
            result = sim.run(sim.initial, 0, END, actions, capture=True)
        finally:
            E._daily_refresh_plants = refresh
            E._drop_inventories_to_shed = drop

    plants = []
    for w in result["work"]:
        if w["cmd"][:2] == ["PLANT", "STRAWBERRY"]:
            plants.append({"seat": w["seat"], "pos": list(w["pos"]), "plant_hour": w["t"],
                           "plant_day": w["t"] // 24, "harvests": [], "ticks": []})
    for tick in ticks:
        matches = [p for p in plants if p["seat"] == tick["seat"] and p["pos"] == tick["pos"]
                   and p["plant_day"] == tick["planted_day"]]
        assert len(matches) == 1, ("tick", tick, matches)
        matches[0]["ticks"].append(tick)
    for w in result["work"]:
        if w["cmd"][0] != "HARVEST" or w["delta"].get("STRAWBERRY", 0) <= 0:
            continue
        matches = [p for p in plants if p["seat"] == w["seat"] and p["pos"] == list(w["pos"])
                   and p["plant_hour"] < w["t"]]
        assert matches, ("harvest", w)
        plant = max(matches, key=lambda p: p["plant_hour"])
        plant["harvests"].append({"hour": w["t"], "day": w["t"] // 24,
                                  "hour_of_day": w["t"] % 24, "units": w["delta"]["STRAWBERRY"]})
    for p in plants:
        p["production_ticks"] = sum(t["survived"] for t in p["ticks"])
        p["yield_generated"] = sum(t["gained_units"] for t in p["ticks"])
        p["yield_lost_to_tile_cap"] = sum(t["cap_loss"] for t in p["ticks"])
        p["harvested_units"] = sum(h["units"] for h in p["harvests"])

    sales = [{"hour": t, "day": t // 24, "hour_of_day": t % 24, "seat": seat, "price": price}
             for t, seat, op, item, price in result["events"] if op == "SELL" and item == "STRAWBERRY"]
    by_day = defaultdict(lambda: defaultdict(list))
    for s in sales:
        by_day[s["day"]][s["seat"]].append(s)
    daily = [{"day": day, "seats": [
        {"seat": seat, "units": len(by_day[day][seat]),
         "revenue": sum(s["price"] for s in by_day[day][seat]),
         "first_hour": min((s["hour_of_day"] for s in by_day[day][seat]), default=None),
         "last_hour": max((s["hour_of_day"] for s in by_day[day][seat]), default=None),
         "hour_counts": dict(sorted(Counter(s["hour_of_day"] for s in by_day[day][seat]).items()))}
        for seat in range(2)]} for day in sorted(by_day)]
    return {"sales": sales, "daily_sales": daily, "plants": plants,
            "strawberry_discarded_at_day_end": strawberry_discarded_at_day_end,
            "final_cash": result["money"]}


def main():
    with gzip.open(ROOT / f"data/ladder_panel/56395605/{EPISODE}.json.gz", "rt", encoding="utf-8") as f:
        game = json.load(f)
    seat = int(game["seat"])
    original = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
    inspections = json.loads((ROOT / "results/fresh/semantic_tapes/earlier_strawberry_sites.json").read_text(encoding="utf-8"))
    sites = {p["t"]: p for day in inspections["days"] for p in day["wheat_plantings"]}
    baseline = replay(game, original)
    shifted = replay(game, variant(original, seat, sites))
    OUT.write_text(json.dumps({"episode": EPISODE, "our_seat": seat,
                               "baseline": baseline, "shifted": shifted}, indent=2), encoding="utf-8")
    for name, run in (("baseline", baseline), ("shifted", shifted)):
        print(name, "cash", run["final_cash"])
        for s in range(2):
            ps = [p for p in run["plants"] if p["seat"] == s]
            ss = [sale for sale in run["sales"] if sale["seat"] == s]
            print(" seat", s, "plants", len(ps), "ticks", sum(p["production_ticks"] for p in ps),
                  "generated", sum(p["yield_generated"] for p in ps),
                  "harvested", sum(p["harvested_units"] for p in ps),
                  "cap_loss", sum(p["yield_lost_to_tile_cap"] for p in ps),
                  "sales", len(ss), "revenue", sum(x["price"] for x in ss))


if __name__ == "__main__":
    main()

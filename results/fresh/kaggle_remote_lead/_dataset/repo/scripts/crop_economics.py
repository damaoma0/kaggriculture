"""Reproduce the no-demand crop-return baseline using installed engine functions.

This is an isolated mechanics/economics calculation, not a feasible farm schedule.
"""
import importlib.util
import json
from pathlib import Path
import sys


def load_engine():
    path = Path(sys.prefix) / "Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py"
    spec = importlib.util.spec_from_file_location("crop_probe_engine", path)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    return engine


def crop_cycle(engine, crop):
    farm = engine._new_farm(10, 3000)
    private = engine._new_private()
    private["seeds"][crop] = 1
    act = lambda action, day: engine._apply_unit_action(farm, private, 0, action, 10, day, 24)
    act(["PLANT", crop], 0)
    cd = engine.CROPS[crop]
    last_day = cd["first_yield_day"] + 3 * cd["interval"] if cd["ongoing"] else cd["max_yield_day"]
    harvests = []
    waters = 0
    for day in range(last_day + 1):
        act(["WATER"], day)
        waters += 1
        tile = farm["tiles"][4][4]
        ready = day >= cd["first_yield_day"] and tile["yield_units"] > 0
        take = ready and (cd["ongoing"] or tile["yield_units"] == cd["max_yield"] or day == last_day)
        if take:
            before = private["inventories"][0].get(crop, 0)
            act(["HARVEST"], day)
            harvests.append({"day": day, "units": private["inventories"][0][crop] - before})
            if not cd["ongoing"]:
                break
        engine._daily_refresh_plants(farm, day, 24)
    return {"crop": crop, "seed": cd["seed"], "harvests": harvests,
            "units": sum(h["units"] for h in harvests), "last_harvest_day": harvests[-1]["day"],
            "daily_water_schedule_actions": 1 + waters + len(harvests)}


def main():
    engine = load_engine()
    out = Path("results/fresh/economics")
    out.mkdir(parents=True, exist_ok=True)
    cycles = [crop_cycle(engine, c) for c in engine.CROPS]
    expected = {"WHEAT": (4, 4), "CARROT": (3, 3), "TOMATO": (4, 11),
                "STRAWBERRY": (4, 16), "MELON": (6, 10)}
    for cycle in cycles:
        assert (cycle["units"], cycle["last_harvest_day"]) == expected[cycle["crop"]], cycle
    rows = []
    for cycle in cycles:
        crop = cycle["crop"]
        inventory = engine.MARKET_PARAMS[crop]["I0"]
        cumulative = 0
        previous = 0
        for count in range(1, 101):
            for _ in range(cycle["units"]):
                price = engine.market_price(crop, inventory)
                cumulative += price
                if price > 1:
                    inventory += 1
            cost = count * cycle["seed"]
            rows.append({"crop": crop, "plants": count, "revenue": cumulative,
                         "profit": cumulative - cost, "seed_roe_percent": 100 * (cumulative - cost) / cost,
                         "marginal_plant_profit": cumulative - previous - cycle["seed"],
                         "profit_per_nominal_tile_day": (cumulative - cost) / (count * cycle["last_harvest_day"])})
            previous = cumulative
    (out / "curves.json").write_text(json.dumps({"cycles": cycles, "curves": rows}, indent=2), encoding="utf-8")
    lines = ["# Fresh crop economics: reproducible baseline", "",
             "Source: installed kaggle-environments engine. Crop yields are probed through its unit-action and daily-refresh functions; sales use its rounded price function and $1 floor behavior.", "",
             "## Assumptions", "",
             "No fertilizer, opponent trades, or town demand. Each product begins at equilibrium inventory. Daily watering; ongoing crops harvested after each production. Sell output sequentially. Seed costs only. Storage, travel, hiring, cash-flow constraints, and the 30-day horizon are excluded. This is a reference curve, not an agent or an optimal allocation.", "",
             "## Engine-checked harvests", "", "| Crop | Harvests (age: units) | Total units |", "|---|---|---:|"]
    for c in cycles:
        lines.append(f"| {c['crop']} | {', '.join(str(h['day']) + ': ' + str(h['units']) for h in c['harvests'])} | {c['units']} |")
    lines += ["", "## Seed return versus production scale", "",
              "ROE = (sale revenue - seed cost) / seed cost. Even one plant moves prices; these are discrete sale calculations.", "",
              "| Plants | Wheat | Carrot | Tomato | Strawberry | Melon |", "|---:|---:|---:|---:|---:|---:|"]
    for n in (1, 10, 25, 50, 100):
        vals = [next(r for r in rows if r["crop"] == c and r["plants"] == n) for c in engine.CROPS]
        lines.append(f"| {n} | " + " | ".join(f"{r['seed_roe_percent']:.1f}%" for r in vals) + " |")
    lines += ["", "## Interpretation and next layer", "",
              "Melon has max_yield_day=12, but its initial unit plus watering bonuses on ages 6-10 reach six units at age 10. Fertilizer cannot permit harvesting before first_yield_day=10.", "",
              "Nominal tile-days use last harvest age, matching the earlier discussion; a real schedule also needs planting/harvesting time and daily action ordering. Daily watering here is not a minimum-labour schedule.", "",
              "Next, optimize legal watering/fertilizer schedules, price fertilizer at its opportunity cost, and include movement, hiring, land, storage, and town/opponent supply. Greedy marginal allocation is not guaranteed optimal when these constraints and delayed revenues interact."]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

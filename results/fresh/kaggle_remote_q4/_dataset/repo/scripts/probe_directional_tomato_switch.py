"""Exact-engine one-tile tomato substitution at a directionally matched checkpoint.

The five day-15 successful wheat replants are candidate host tiles. Each probe
funds one tomato seed and orders its sale after the tape's first harvest visit
at least eight days later. All other recorded actions and the rival are fixed.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import json
from pathlib import Path

import research_labour_profit as R


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_tapes/directional_tomato_probe.json"
EPISODE, DAY, END = 111289863, 15, 719
START = DAY * 24
SEED_STEP = 361


def evaluate(game, pair, seat, pos=None, plant_t=None, sale_t=None):
    with R.Simulator(game) as sim:
        result = sim.run(sim.initial, 0, END, pair, capture=True)
    state = result["state"]
    obs = state[seat].observation
    cash = float(obs.farms[seat]["money"])
    rival = float(obs.farms[1-seat]["money"])
    service = defaultdict(Counter)
    output = Counter()
    tile_work = []
    tomato_plant_success = False
    for w in result["work"]:
        if w["seat"] != seat:
            continue
        op = w["cmd"][0]
        if op in ("FEED", "CARE", "PICKUP"):
            service[w["t"]//24][op] += 1
        if op in ("HARVEST", "COLLECT_FERTILIZER"):
            output.update({p:n for p,n in w["delta"].items() if n > 0})
        if pos is not None and tuple(w["pos"]) == tuple(pos) and w["t"] >= plant_t:
            if w["t"] == plant_t and w["cmd"] == ["PLANT", "TOMATO"]:
                tomato_plant_success = True
            if op in ("PLANT", "HARVEST"):
                tile_work.append({"t":w["t"], "cmd":w["cmd"], "delta":w["delta"]})
    sale_fills = [e for e in result["events"] if e[1] == seat and e[0] == sale_t and e[2:4] == ("SELL", "TOMATO")]
    return {"cash":cash,"rival_cash":rival,"margin":cash-rival,
            "revenue":R.economic(result["events"],seat)["revenue"],
            "spend":R.economic(result["events"],seat)["spend"],
            "service":{str(day):dict(c) for day,c in service.items()},
            "output":dict(output),"final_shed":{p:obs.private["shed"].get(p,0)
                for p in ("WHEAT","TOMATO","CARROT","MILK","EGG","WOOL")},
            "tomato_plant_success":tomato_plant_success,"sale_fills":len(sale_fills),
            "sale_cash":sum(e[4] for e in sale_fills),"tile_work":tile_work}


def main():
    with gzip.open(ROOT / f"data/ladder_panel/56395605/{EPISODE}.json.gz", "rt", encoding="utf-8") as f:
        game = json.load(f)
    seat = int(game["seat"])
    original = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
    assert len(original[seat][SEED_STEP]["market"]) < 10
    with R.Simulator(game) as sim:
        baseline_run = sim.run(sim.initial, 0, END, original, capture=True)
    baseline_works = [w for w in baseline_run["work"] if w["seat"] == seat]
    plants = [w for w in baseline_works if START <= w["t"] < START+24 and w["cmd"] == ["PLANT", "WHEAT"]]
    assert len(plants) == 5
    baseline = evaluate(game, original, seat)
    rows = []
    for plant in plants:
        plant_t, unit, pos = plant["t"],plant["unit"],plant["pos"]
        later_harvest = next(w for w in baseline_works if w["t"] >= plant_t+8*24 and
                             tuple(w["pos"]) == tuple(pos) and w["cmd"] == ["HARVEST"])
        sale_t = later_harvest["t"]+1
        assert sale_t < END and len(original[seat][sale_t]["market"]) < 10
        pair = deepcopy(original)
        pair[seat][SEED_STEP]["market"].append(["BUY_SEED", "TOMATO", 1])
        field = "farmer" if unit == 0 else "hands"
        if unit == 0:
            assert pair[seat][plant_t][field] == ["PLANT", "WHEAT"]
            pair[seat][plant_t][field] = ["PLANT", "TOMATO"]
        else:
            assert pair[seat][plant_t][field][unit-1] == ["PLANT", "WHEAT"]
            pair[seat][plant_t][field][unit-1] = ["PLANT", "TOMATO"]
        pair[seat][sale_t]["market"].append(["SELL", "TOMATO", 1])
        for mode in ("single_sale", "liquidate_at_tape_sale_hours"):
            trial = deepcopy(pair)
            if mode == "liquidate_at_tape_sale_hours":
                # Remove the speculative one-off order. At every subsequent
                # hour where m1 already planned a tomato sale, try to sell any
                # extra stock after the original order has run.
                trial[seat][sale_t]["market"].pop()
                for t in range(sale_t, END):
                    if any(cmd[:2] == ["SELL", "TOMATO"] for cmd in original[seat][t]["market"]):
                        assert len(trial[seat][t]["market"]) < 10
                        trial[seat][t]["market"].append(["SELL", "TOMATO", 10])
                trial[seat][718]["market"].append(["SELL", "TOMATO", 10])
            row = evaluate(game,trial,seat,pos,plant_t,sale_t if mode == "single_sale" else None)
            row.update(mode=mode,plant_t=plant_t,unit=unit,pos=pos,sale_t=sale_t,
                       margin_delta=row["margin"]-baseline["margin"],
                       cash_delta=row["cash"]-baseline["cash"],
                       rival_cash_delta=row["rival_cash"]-baseline["rival_cash"])
            rows.append(row)
            print(f"plant {plant_t} {pos} {mode}: margin {row['margin_delta']:+.0f}; "
                  f"tomato revenue {row['revenue'].get('TOMATO',0)} shed {row['final_shed']['TOMATO']}",flush=True)
    best=max(rows,key=lambda row:row["margin_delta"])
    OUT.write_text(json.dumps({"episode":EPISODE,"day":DAY,"seat":seat,"baseline":baseline,
        "variants":rows,"oracle_best_tested":{"plant_t":best["plant_t"],"pos":best["pos"],
                                     "mode":best["mode"],"margin_delta":best["margin_delta"]},
        "offline_switch_decision":"keep_incumbent" if best["margin_delta"]<=0 else "switch_to_best_tested",
        "limitation":"Five preselected one-tile edits, not the whole donor plan; same fixed shops and opponent, future m1 worker actions retained. The decision uses known future outcomes and is not live-deployable."},indent=2),encoding="utf-8")


if __name__ == "__main__":
    main()

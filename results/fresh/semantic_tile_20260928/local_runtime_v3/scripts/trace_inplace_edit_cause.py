"""Trace the physical and market path of the one-tile tomato substitution."""
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import json
from pathlib import Path

import research_labour_profit as R


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_tapes/inplace_edit_cause.json"
EPISODE, DAY, POS = 111291994, 21, (4, 6)


def read_game():
    with gzip.open(ROOT / f"data/ladder_panel/56395605/{EPISODE}.json.gz", "rt", encoding="utf-8") as handle:
        return json.load(handle)


def actions(game, edit):
    seat = int(game["seat"])
    pair = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
    if edit:
        pair[seat][505]["market"].append(["BUY_SEED", "TOMATO", 1])
        pair[seat][509]["hands"][5] = ["PLANT", "TOMATO"]
    return pair


def event_summary(events):
    data = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for t, seat, op, item, price in events:
        key = op + ":" + item
        data[str(seat)][key][0] += 1
        data[str(seat)][key][1] += price
    return {seat: dict(items) for seat, items in data.items()}


def output_summary(work):
    data = defaultdict(Counter)
    for item in work:
        if item["cmd"] and item["cmd"][0] in ("HARVEST", "COLLECT_FERTILIZER"):
            for product, n in item["delta"].items():
                if n > 0:
                    data[str(item["seat"])][product] += n
    return {seat: dict(counts) for seat, counts in data.items()}


def service_summary(work):
    data = defaultdict(Counter)
    for item in work:
        if item["cmd"] and item["cmd"][0] in ("FEED", "CARE", "PICKUP"):
            data[str(item["seat"])][item["cmd"][0]] += 1
    return {seat: dict(counts) for seat, counts in data.items()}


def run(game, edit):
    seat = int(game["seat"])
    pair = actions(game, edit)
    days = []
    with R.Simulator(game) as sim:
        prefix = sim.run(sim.initial, 0, DAY*24, pair)
        state = prefix["state"]
        for day in range(DAY, 30):
            start, stop = day*24, min((day+1)*24, 719)
            before = state[0].observation
            before_tile = deepcopy(before.farms[seat]["tiles"][POS[1]][POS[0]])
            before_cash = [float(f["money"]) for f in before.farms]
            before_wheat = state[seat].observation.private["shed"].get("WHEAT", 0)
            result = sim.run(state, start, stop, pair, capture=True, snapshots=True)
            visits = []
            fed_animals = []
            for t, snapshot in result["snapshots"].items():
                obs = snapshot[seat].observation
                farm = obs.farms[seat]
                commands = [pair[seat][t].get("farmer") or ["PASS"], *(pair[seat][t].get("hands") or [])]
                positions = [farm["farmer"], *farm["hands"]]
                for u, (position, command) in enumerate(zip(positions, commands)):
                    if tuple(position) == POS and command and command[0] not in ("PASS", "NORTH", "SOUTH", "EAST", "WEST"):
                        visits.append(dict(step=t, unit=u, command=command,
                                           pre_tile=deepcopy(farm["tiles"][POS[1]][POS[0]])))
            state = result["state"]
            after = state[0].observation
            for work in result["work"]:
                if work["seat"] == seat and work["cmd"] and work["cmd"][0] == "FEED":
                    x, y = work["pos"]
                    source = result["snapshots"][work["t"]][seat].observation.farms[seat]["tiles"][y][x]
                    fed_animals.append(dict(step=work["t"], tile=[x,y], animal=source.get("animal") if isinstance(source,dict) else None))
            days.append(dict(day=day, before_tile=before_tile,
                             after_tile=deepcopy(after.farms[seat]["tiles"][POS[1]][POS[0]]),
                             visits=visits,
                             successful_tilework=[w for w in result["work"] if w["seat"] == seat and tuple(w["pos"]) == POS],
                             cash_start=before_cash,
                             cash_end=[float(f["money"]) for f in after.farms],
                             own_shed_wheat_start=before_wheat,
                             own_shed_wheat_end=state[seat].observation.private["shed"].get("WHEAT", 0),
                             market_start={p: before.market["prices"][p] for p in ("WHEAT", "TOMATO", "CARROT", "EGG", "WOOL", "MILK")},
                             market_end={p: after.market["prices"][p] for p in ("WHEAT", "TOMATO", "CARROT", "EGG", "WOOL", "MILK")},
                             produced=output_summary(result["work"]),
                             service=service_summary(result["work"]),
                             fed_animals=fed_animals,
                             events=event_summary(result["events"])))
    return days


def main():
    game = read_game()
    baseline, edit = run(game, False), run(game, True)
    comparisons = []
    seat = str(game["seat"])
    rival = str(1-int(seat))
    for a, b in zip(baseline, edit):
        def delta_event(who, prefix):
            aa, bb = a["events"].get(who, {}), b["events"].get(who, {})
            return {k: [bb.get(k, [0,0])[0]-aa.get(k, [0,0])[0], bb.get(k, [0,0])[1]-aa.get(k, [0,0])[1]]
                    for k in aa.keys()|bb.keys() if k.startswith(prefix) and bb.get(k, [0,0]) != aa.get(k, [0,0])}
        comparisons.append(dict(day=a["day"],
                                own_cash_delta=b["cash_end"][int(seat)]-a["cash_end"][int(seat)],
                                rival_cash_delta=b["cash_end"][int(rival)]-a["cash_end"][int(rival)],
                                own_shed_wheat_delta=b["own_shed_wheat_end"]-a["own_shed_wheat_end"],
                                own_feed_success_delta=b["service"].get(seat, {}).get("FEED",0)-a["service"].get(seat, {}).get("FEED",0),
                                own_care_success_delta=b["service"].get(seat, {}).get("CARE",0)-a["service"].get(seat, {}).get("CARE",0),
                                own_sales_delta=delta_event(seat, "SELL:"),
                                rival_sales_delta=delta_event(rival, "SELL:"),
                                own_output_delta={p:b["produced"].get(seat, {}).get(p, 0)-a["produced"].get(seat, {}).get(p, 0)
                                                  for p in a["produced"].get(seat, {}).keys()|b["produced"].get(seat, {}).keys()
                                                  if a["produced"].get(seat, {}).get(p, 0)!=b["produced"].get(seat, {}).get(p, 0)},
                                rival_output_delta={p:b["produced"].get(rival, {}).get(p, 0)-a["produced"].get(rival, {}).get(p, 0)
                                                    for p in a["produced"].get(rival, {}).keys()|b["produced"].get(rival, {}).keys()
                                                    if a["produced"].get(rival, {}).get(p, 0)!=b["produced"].get(rival, {}).get(p, 0)},
                                tile_a=a["after_tile"], tile_b=b["after_tile"]))
    OUT.write_text(json.dumps(dict(episode=EPISODE, seat=int(seat), tile=list(POS),
                                   baseline=baseline, edited=edit, comparisons=comparisons), indent=2), encoding="utf-8")
    for x in comparisons:
        print(json.dumps({k:x[k] for k in ("day", "own_cash_delta", "rival_cash_delta", "own_sales_delta", "rival_sales_delta")}), flush=True)


if __name__ == "__main__":
    main()

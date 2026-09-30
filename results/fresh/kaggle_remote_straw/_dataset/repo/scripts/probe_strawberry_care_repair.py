"""Try exact-engine care edits after the day-12/15 strawberry substitutions."""
from copy import deepcopy
from collections import Counter
import gzip
import json
import sys

import research_labour_profit as R
from probe_semantic_handoff import ROOT
from probe_earlier_strawberry_portfolio import EPISODE, END
from trace_reveal_aligned_strawberry_timeline import variant
from trace_strawberry_sales_and_yields import replay as trace_replay


OUT = ROOT / "results/fresh/semantic_tapes/strawberry_care_repair.json"
TARGETS = {(2, 3): 23, (1, 9): 25, (4, 6): 28, (1, 6): 24}
JOBS = [
    (23, (2, 3), "WATER"),
    (24, (1, 6), "FERTILIZE"),
    (24, (1, 6), "WATER"),
    (25, (1, 9), "FERTILIZE"),
    (25, (1, 9), "WATER"),
    (27, (1, 9), "HARVEST"),
    (28, (4, 6), "WATER"),
]


def load():
    with gzip.open(ROOT / f"data/ladder_panel/56395605/{EPISODE}.json.gz", "rt", encoding="utf-8") as f:
        game = json.load(f)
    seat = int(game["seat"])
    original = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
    inspections = json.loads((ROOT / "results/fresh/semantic_tapes/earlier_strawberry_sites.json").read_text(encoding="utf-8"))
    sites = {p["t"]: p for day in inspections["days"] for p in day["wheat_plantings"]}
    return game, seat, variant(original, seat, sites)


def replay(game, actions, snapshots=False):
    with R.Simulator(game) as sim:
        result = sim.run(sim.initial, 0, END, actions, capture=True, snapshots=snapshots)
    return result


def inspect(game, seat, actions):
    result = replay(game, actions, snapshots=True)
    rows = []
    for pos, day in TARGETS.items():
        for t in range(day * 24, (day + 1) * 24):
            snapshot = result["snapshots"][t][seat].observation
            farm = snapshot.farms[seat]
            workers = [farm["farmer"], *farm["hands"]]
            commands = [actions[seat][t]["farmer"], *actions[seat][t]["hands"]]
            tile = farm["tiles"][pos[1]][pos[0]]
            for unit, position in enumerate(workers):
                if tuple(position) != pos:
                    continue
                rows.append({"target": list(pos), "day": day, "t": t, "hour": t % 24,
                             "unit": unit, "command": commands[unit],
                             "tile": {k: tile.get(k) for k in ("crop", "yield_units", "watered_today", "fertilized_until_day")}
                             if isinstance(tile, dict) else tile})
    return rows


def work_signature(work, seat, start, stop):
    return Counter((w["unit"], tuple(w["pos"]), tuple(w["cmd"]),
                    tuple(sorted((p, n) for p, n in w["delta"].items() if n)))
                   for w in work if w["seat"] == seat and start <= w["t"] < stop)


def next_job(game, seat, actions, day, pos, operation):
    start, stop = day * 24, (day + 1) * 24
    with R.Simulator(game) as sim:
        prefix = sim.run(sim.initial, 0, start, actions)["state"]
        base = sim.run(prefix, start, stop, actions, capture=True, snapshots=True)
        units, routes, jobs, _, _ = R.extract(base, seat, start)
        delta = {"FERTILIZER": -1} if operation == "FERTILIZE" else {}
        new_job = R.Job(len(jobs), pos, [[operation]], [delta], 2, False, -1)
        all_jobs = [*jobs, new_job]
        options = []
        for unit, route in routes.items():
            old_finish, _ = R.compile_route(units[unit], route, jobs)
            for index in range(len(route) + 1):
                trial_route = route[:index] + [new_job.id] + route[index:]
                finish, commands = R.compile_route(units[unit], trial_route, all_jobs)
                if finish > 24:
                    continue
                own = deepcopy(actions[seat])
                for hour in range(2, 24):
                    cmd = commands[hour - 2] if hour - 2 < len(commands) else ["PASS"]
                    if unit == 0:
                        own[start + hour]["farmer"] = cmd
                    else:
                        own[start + hour]["hands"][unit - 1] = cmd
                pair = list(actions)
                pair[seat] = own
                trial = sim.run(prefix, start, stop, pair, capture=True)
                old = work_signature(base["work"], seat, start, stop)
                new = work_signature(trial["work"], seat, start, stop)
                extra = new - old
                lost = old - new
                target = [w for w in trial["work"] if w["seat"] == seat and w["cmd"][0] == operation
                          and tuple(w["pos"]) == pos and start <= w["t"] < stop]
                if not target or lost:
                    continue
                if len(extra) != 1 or sum(extra.values()) != 1:
                    continue
                extra_key = next(iter(extra))
                if extra_key[1] != pos or extra_key[2] != (operation,):
                    continue
                options.append({"unit": unit, "insert_index": index, "old_finish": old_finish,
                                "new_finish": finish, "extra_work": [str(k) for k in extra],
                                "pair": pair})
        options.sort(key=lambda row: (row["new_finish"] - row["old_finish"], row["new_finish"], row["unit"]))
        return options


def essential_signature(work, seat, start, stop):
    return Counter((w["unit"], tuple(w["pos"]), tuple(w["cmd"]),
                    tuple(sorted((p, n) for p, n in w["delta"].items() if n)))
                   for w in work if w["seat"] == seat and start <= w["t"] < stop
                   and w["cmd"][0] not in ("PICKUP", "DROP"))


def search_berry_delivery(game, seat, actions, day):
    start, stop = day * 24, (day + 1) * 24
    with R.Simulator(game) as sim:
        prefix = sim.run(sim.initial, 0, start, actions)["state"]
        base = sim.run(prefix, start, stop, actions, capture=True, snapshots=True)
        units, routes, jobs, _, _ = R.extract(base, seat, start)
        base_signature = essential_signature(base["work"], seat, start, stop)
        base_sold = sum(1 for t, s, op, p, _ in base["events"]
                        if s == seat and op == "SELL" and p == "STRAWBERRY")
        base_stock = base["state"][seat].observation.private["shed"].get("STRAWBERRY", 0)
        options = []
        for unit, route in routes.items():
            for index in range(len(route) + 1):
                for shed in R.SHED:
                    new_job = R.Job(len(jobs), shed, [["DROP"]], [{}], 2, False, -1)
                    trial_route = route[:index] + [new_job.id] + route[index:]
                    finish, commands = R.compile_route(units[unit], trial_route, [*jobs, new_job])
                    if finish > 24:
                        continue
                    own = deepcopy(actions[seat])
                    for hour in range(2, 24):
                        cmd = commands[hour - 2] if hour - 2 < len(commands) else ["PASS"]
                        if unit == 0:
                            own[start + hour]["farmer"] = cmd
                        else:
                            own[start + hour]["hands"][unit - 1] = cmd
                        if cmd == ["DROP"] and len(own[start + hour]["market"]) < 10:
                            own[start + hour]["market"].append(["SELL", "STRAWBERRY", 10])
                    pair = list(actions)
                    pair[seat] = own
                    trial = sim.run(prefix, start, stop, pair, capture=True)
                    trial_signature = essential_signature(trial["work"], seat, start, stop)
                    lost = base_signature - trial_signature
                    if sum(lost.values()) > 2 or any(key[2][0] in ("FEED", "PLANT", "FERTILIZE", "WATER") for key in lost):
                        continue
                    sold = sum(1 for t, s, op, p, _ in trial["events"]
                               if s == seat and op == "SELL" and p == "STRAWBERRY")
                    stock = trial["state"][seat].observation.private["shed"].get("STRAWBERRY", 0)
                    gain = sold + stock - base_sold - base_stock
                    if gain <= 0:
                        continue
                    margin = (trial["money"][seat] - trial["money"][1 - seat]
                              - base["money"][seat] + base["money"][1 - seat])
                    options.append({"unit": unit, "insert_index": index, "shed": shed,
                                    "finish": finish, "berry_rescued": gain,
                                    "lost_work": [str(k) for k in lost],
                                    "local_margin_delta": margin, "pair": pair})
        options.sort(key=lambda row: (-row["berry_rescued"], len(row["lost_work"]),
                                      -row["local_margin_delta"], row["finish"], row["unit"]))
        return options


def search_capacity_priority(game, seat, actions, day):
    """Find one late harvest/collection to defer so berries fit in the shed."""
    start, stop = day * 24, (day + 1) * 24
    with R.Simulator(game) as sim:
        prefix = sim.run(sim.initial, 0, start, actions)["state"]
        base = sim.run(prefix, start, stop, actions, capture=True)
        base_signature = essential_signature(base["work"], seat, start, stop)
        base_sold = sum(1 for t, s, op, p, _ in base["events"]
                        if s == seat and op == "SELL" and p == "STRAWBERRY")
        base_stock = base["state"][seat].observation.private["shed"].get("STRAWBERRY", 0)
        rows = []
        for w in base["work"]:
            if w["seat"] != seat or not start <= w["t"] < stop:
                continue
            if w["cmd"][0] not in ("HARVEST", "COLLECT_FERTILIZER"):
                continue
            produced = {p: n for p, n in w["delta"].items() if n > 0}
            if not produced or "STRAWBERRY" in produced or "WOOL" in produced:
                continue
            own = deepcopy(actions[seat])
            if w["unit"] == 0:
                own[w["t"]]["farmer"] = ["PASS"]
            else:
                own[w["t"]]["hands"][w["unit"] - 1] = ["PASS"]
            pair = list(actions)
            pair[seat] = own
            trial = sim.run(prefix, start, stop, pair, capture=True)
            lost = base_signature - essential_signature(trial["work"], seat, start, stop)
            if len(lost) != 1 or sum(lost.values()) != 1:
                continue
            sold = sum(1 for t, s, op, p, _ in trial["events"]
                       if s == seat and op == "SELL" and p == "STRAWBERRY")
            stock = trial["state"][seat].observation.private["shed"].get("STRAWBERRY", 0)
            rescued = sold + stock - base_sold - base_stock
            if rescued <= 0:
                continue
            rows.append({"t": w["t"], "unit": w["unit"], "pos": w["pos"],
                         "foregone": produced, "berry_rescued": rescued,
                         "local_margin_delta": trial["money"][seat] - trial["money"][1-seat]
                                               - base["money"][seat] + base["money"][1-seat],
                         "pair": pair})
        rows.sort(key=lambda row: (-row["berry_rescued"], -row["local_margin_delta"], row["t"]))
        return rows


def main():
    game, seat, actions = load()
    starting_actions = actions
    records = []
    fert_day = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    planned = [(fert_day if pos == (1, 9) and operation == "FERTILIZE" else day,
                pos, operation) for day, pos, operation in JOBS]
    planned.sort(key=lambda job: job[0])
    for day, pos, operation in planned:
        options = next_job(game, seat, actions, day, pos, operation)
        print("job", day, pos, operation, "feasible", len(options), flush=True)
        if options:
            best = options[0]
            print(" chosen", {k: v for k, v in best.items() if k != "pair"}, flush=True)
            actions = best["pair"]
            records.append({k: v for k, v in best.items() if k != "pair"} | {"day": day, "pos": pos,
                                                                         "operation": operation})
        else:
            records.append({"day": day, "pos": pos, "operation": operation, "failed": True})
    deliveries = []
    for day in (26, 27):
        candidates = search_berry_delivery(game, seat, actions, day)
        print("delivery", day, "candidates", len(candidates), flush=True)
        if candidates:
            chosen = candidates[0]
            print(" chosen", {k: v for k, v in chosen.items() if k != "pair"}, flush=True)
            actions = chosen["pair"]
            deliveries.append({"day": day} | {k: v for k, v in chosen.items() if k != "pair"})
    capacity_edits = []
    for day in (26, 27):
        for attempt in range(3):
            candidates = search_capacity_priority(game, seat, actions, day)
            print("capacity", day, attempt, "candidates", len(candidates), flush=True)
            if not candidates:
                break
            base_full = replay(game, actions)
            base_margin = base_full["money"][seat] - base_full["money"][1-seat]
            choices = []
            for candidate in candidates[:8]:
                trial = replay(game, candidate["pair"])
                margin = trial["money"][seat] - trial["money"][1-seat]
                berry_sold = sum(1 for _, s, op, p, _ in trial["events"]
                                 if s == seat and op == "SELL" and p == "STRAWBERRY")
                choices.append((margin - base_margin, berry_sold, candidate))
            gain, berry_sold, chosen = max(choices, key=lambda row: (row[0], row[1]))
            if gain <= 0:
                break
            print(" chosen", {k: v for k, v in chosen.items() if k != "pair"},
                  "full_margin_delta", gain, "strawberry_sales", berry_sold, flush=True)
            actions = chosen["pair"]
            capacity_edits.append({"day": day, "full_margin_delta": gain,
                                   "strawberry_sales": berry_sold}
                                  | {k: v for k, v in chosen.items() if k != "pair"})
    final = replay(game, actions, snapshots=True)
    shifted = replay(game, starting_actions)
    econ = [R.economic(final["events"], s) for s in (seat, 1 - seat)]
    prior_econ = [R.economic(shifted["events"], s) for s in (seat, 1 - seat)]
    def output(work):
        goods = Counter()
        for w in work:
            if w["seat"] == seat and w["cmd"][0] in ("HARVEST", "COLLECT_FERTILIZER"):
                goods.update({p: n for p, n in w["delta"].items() if n > 0})
        return dict(goods)
    def feeds(work):
        return sum(w["seat"] == seat and w["cmd"][0] == "FEED" for w in work)
    result = {"episode": EPISODE, "fertilizer_day_for_1_9": fert_day,
              "jobs": records, "deliveries": deliveries,
              "capacity_edits": capacity_edits, "cash": final["money"],
              "margin": final["money"][seat] - final["money"][1 - seat],
              "economic": econ,
              "comparison_to_shift": {
                  "prior_cash": shifted["money"],
                  "prior_margin": shifted["money"][seat] - shifted["money"][1-seat],
                  "our_output_before": output(shifted["work"]),
                  "our_output_after": output(final["work"]),
                  "successful_feeds_before": feeds(shifted["work"]),
                  "successful_feeds_after": feeds(final["work"]),
                  "revenue_delta_ours": {p: econ[0]["revenue"].get(p, 0) - prior_econ[0]["revenue"].get(p, 0)
                                         for p in set(econ[0]["revenue"]) | set(prior_econ[0]["revenue"])},
                  "revenue_delta_rival": {p: econ[1]["revenue"].get(p, 0) - prior_econ[1]["revenue"].get(p, 0)
                                          for p in set(econ[1]["revenue"]) | set(prior_econ[1]["revenue"])},
                  "spend_delta_ours": {p: econ[0]["spend"].get(p, 0) - prior_econ[0]["spend"].get(p, 0)
                                       for p in set(econ[0]["spend"]) | set(prior_econ[0]["spend"])},
              },
              "our_strawberry_harvest": sum(w["delta"].get("STRAWBERRY", 0) for w in final["work"]
                                            if w["seat"] == seat and w["cmd"][0] == "HARVEST")}
    result["changed_hours"] = [t for t in range(END) if actions[seat][t] != starting_actions[seat][t]]
    detailed = trace_replay(game, actions)
    result["target_plants"] = [p for p in detailed["plants"] if p["seat"] == seat
                               and p["plant_hour"] in (302, 306, 365, 374)]
    result["strawberry_discarded_at_day_end"] = detailed["strawberry_discarded_at_day_end"]
    result["daily_strawberry_sales"] = detailed["daily_sales"]
    if fert_day == 24:
        assert result["comparison_to_shift"]["prior_margin"] == -5491
        assert result["margin"] == -4705
        assert [p["yield_generated"] for p in result["target_plants"]] == [8, 8, 6, 6]
        assert econ[0]["units"]["STRAWBERRY"] == 134
        assert result["comparison_to_shift"]["successful_feeds_before"] == 314
        assert result["comparison_to_shift"]["successful_feeds_after"] == 314
        assert not any(row["seat"] == seat for row in detailed["strawberry_discarded_at_day_end"])
    for s in (0, 1):
        row = R.economic(final["events"], s)
        assert 3000 + sum(row["revenue"].values()) - sum(row["spend"].values()) == final["money"][s]
    result["shed_near_overflow"] = []
    for day in (26, 27):
        for hour in (0, 20, 22, 23):
            private = final["snapshots"][day * 24 + hour][seat].observation.private
            result["shed_near_overflow"].append({"day": day, "hour": hour,
                "shed": dict(private["shed"]),
                "shed_total": sum(private["shed"].values()),
                "held": dict(sum((Counter(inv) for inv in private["inventories"]), Counter()))})
    result["berry_carriers"] = []
    result["shed_visitors"] = []
    for day in (26, 27):
        for hour in range(2, 24):
            state = final["snapshots"][day * 24 + hour][seat].observation
            farm, private = state.farms[seat], state.private
            positions = [farm["farmer"], *farm["hands"]]
            commands = [actions[seat][day * 24 + hour]["farmer"],
                        *actions[seat][day * 24 + hour]["hands"]]
            for unit, inv in enumerate(private["inventories"]):
                if tuple(positions[unit]) in R.SHED and inv and hour <= 21:
                    result["shed_visitors"].append({"day": day, "hour": hour,
                        "unit": unit, "pos": positions[unit], "inventory": dict(inv),
                        "cmd": commands[unit]})
                if inv.get("STRAWBERRY", 0):
                    if hour not in (12, 18, 20, 22, 23):
                        continue
                    result["berry_carriers"].append({"day": day, "hour": hour,
                        "unit": unit, "pos": positions[unit], "strawberry": inv["STRAWBERRY"],
                        "inventory": dict(inv), "cmd": commands[unit]})
    output = OUT if fert_day == 25 else OUT.with_name(f"strawberry_care_repair_fert_day{fert_day}.json")
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("final", result["cash"], result["margin"], result["our_strawberry_harvest"])


if __name__ == "__main__":
    main()

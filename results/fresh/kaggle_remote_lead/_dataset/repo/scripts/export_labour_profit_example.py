"""Export an executable example, extracted tile jobs and actual sale ledger."""
from collections import Counter, defaultdict
from dataclasses import asdict
import argparse
import json
import research_labour_profit as R


def group_trades(events):
    grouped = defaultdict(lambda: [0, 0])
    for t, seat, op, item, price in events:
        if op == "SELL":
            row = grouped[t, seat, item]
            row[0] += 1
            row[1] += price
    return [dict(step=t, day=t // 24, hour=t % 24, seat=s, product=p, units=v[0], revenue=v[1])
            for (t, s, p), v in sorted(grouped.items())]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="leaders_holdout")
    parser.add_argument("--mode", choices=("wage", "oracle", "forecast"), default="oracle")
    args = parser.parse_args()
    rows = [json.loads(p.read_text()) for p in (R.OUT / args.tag).glob("*.json") if p.stem.isdigit()]
    _, row, day = max(((b["selected"][args.mode]["gain"], r, b["day"])
                      for r in rows for b in r["blocks"]), key=lambda x: (x[0], x[1]["episode"], x[2]))
    game, actions = R.load_game(R.ROOT / row["source"])
    start, stop = day * 24, (day + 2) * 24
    with R.Simulator(game) as sim:
        original = sim.run(sim.initial, 0, start, actions)
        base, valid, selections, summary = R.block(sim, original["state"], actions, start, stop, 80)
        name, selected, pair, advance = valid[selections[args.mode]]
        items = {name.split(":early_")[-1]} if ":early_" in name else R.OUTPUTS
        trial = sim.run(original["state"], start, stop, pair, capture=True, snapshots=True,
                        advance=advance, quota=base["sold"],
                        reference=base if advance == "delivery" else None, advance_items=items)
        assert trial["money"] == selected["money"]
        assert R.equivalent(base, trial, game["seat"]) is None
        def production(work):
            result = Counter()
            for event in work:
                if event["seat"] == game["seat"] and event["cmd"][0] in ("HARVEST", "COLLECT_FERTILIZER"):
                    result.update({p: n for p, n in event["delta"].items() if n > 0})
            return result
        assert production(base["work"]) == production(trial["work"])
        units, routes, jobs, frozen, locked = R.extract(base, game["seat"], start)
        timeline = []
        baseline_timeline = []
        executed = []
        for t in range(start, stop):
            after = trial["snapshots"].get(t + 1, trial["state"])
            action = after[game["seat"]].action
            executed.append(action)
            if t >= start + 24:
                continue
            farm = trial["snapshots"][t][0].observation.farms[game["seat"]]
            cmds = [action.get("farmer") or ["PASS"], *(action.get("hands") or [])]
            pos = [farm["farmer"], *farm["hands"]]
            timeline.append(dict(hour=t - start, workers=[dict(id=u, at=p, command=cmds[u] if u < len(cmds) else ["PASS"])
                                                        for u, p in enumerate(pos)], market=action.get("market", [])))
            original_farm = base["snapshots"][t][0].observation.farms[game["seat"]]
            original_action = actions[game["seat"]][t]
            original_cmds = [original_action.get("farmer") or ["PASS"], *(original_action.get("hands") or [])]
            baseline_timeline.append(dict(hour=t - start, workers=[dict(id=u, at=p, command=original_cmds[u] if u < len(original_cmds) else ["PASS"])
                                      for u, p in enumerate([original_farm["farmer"], *original_farm["hands"]])]))
    output = dict(episode=game["episode"], seat=game["seat"], day_zero_based=day,
                  selection=summary["selected"][args.mode], source=row["source"],
                  information="Offline executable 48-hour schedule. Recorded opponent actions and future feasibility are known.",
                  harvested_and_collected=dict(production(trial["work"])),
                  jobs=[asdict(j) for j in jobs], initial_workers=units,
                  baseline_actions=actions[game["seat"]][start:stop], optimized_actions=executed,
                  worker_timeline=timeline, baseline_worker_timeline=baseline_timeline, baseline_sales=group_trades(base["events"]),
                  optimized_sales=group_trades(trial["events"]))
    target = R.OUT / f"example_{args.tag}_{args.mode}.json"
    target.write_text(json.dumps(output, indent=2))
    print(json.dumps(dict(file=str(target), episode=game["episode"], day=day,
                          selection=summary["selected"][args.mode]), indent=2))


if __name__ == "__main__":
    main()

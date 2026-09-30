"""Causal, supplied-plan labour scheduler versus the same unscheduled plan.

The planner receives only its observation and 48 hours of its own supplied plan.
It projects a PASS rival, empty unknown rival inventory, no new weeds and no new
shops. Candidate feasibility is checked in that projection, never in the actual
future. Real games use the official engine, real weeds and recorded shop worlds.
Both seats, a baseline-v-baseline control, and all failures are retained.
This is a research executor, not a packaged competition submission.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
import gzip
import json
from pathlib import Path
import random
import statistics
import time

import research_labour_profit as R


def digest(value):
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def project_input(observation):
    """Build a new engine world from agent-visible fields, not a full state."""
    obs = deepcopy(observation)
    game = dict(seed=0, seat=obs.player, episode=0,
                shops=[deepcopy(obs.town.unlocked_shops) for _ in range(31)])
    sim = R.Simulator(game)
    sim.env.configuration.weedSpawnChance = 0
    sim.env.configuration.townShopUnlockInterval = 10000
    initial = sim.initial
    for s in range(2):
        target = initial[s].observation
        for name in ("farms", "market", "town", "day", "hour", "step"):
            setattr(target, name, deepcopy(obs[name]))
        target.player = s
        if s == obs.player:
            target.private = deepcopy(obs.private)
        else:
            target.private = R.engine()._new_private()
            target.private["inventories"] = [{} for _ in range(1 + len(obs.farms[s]["hands"]))]
    # Engine shared observation references, as in its initialization.
    for name in ("farms", "market", "town"):
        setattr(initial[1].observation, name, getattr(initial[0].observation, name))
    assert initial[0].observation.farms == obs.farms
    assert initial[obs.player].observation.private == obs.private
    assert initial[0].observation.step == obs.step
    return sim, initial


def choose(observation, own_window, mode, rounds=80):
    """Causal API boundary: no episode seed, rival plan or future world input."""
    started = time.perf_counter()
    start, seat = observation.step, observation.player
    stop = start + len(own_window)
    assert start % 24 == 0 and len(own_window) == 48
    sim, initial = project_input(observation)
    pair = [[deepcopy(R.PASS) for _ in range(720)] for _ in range(2)]
    pair[seat][start:stop] = deepcopy(own_window)
    with sim:
        # The supplied plan's required inputs must execute in the projection.
        # Otherwise extracting only its successful work would silently replace
        # the intended production plan with a smaller, cheaper workload.
        baseline = sim.run(initial, start, stop, pair)
        requested = Counter()
        for t in range(start, stop):
            for order in ((pair[seat][t] or {}).get("market") or [])[:10]:
                if not order:
                    continue
                op = order[0]
                if op in ("HIRE", "BUY_LAND"):
                    requested[t, op, ""] += 1
                elif op.startswith("BUY_"):
                    requested[t, op, order[1]] += int(order[2]) if len(order) > 2 else 1
        filled = Counter((t, op, item) for t, s, op, item, price in baseline["events"]
                         if s == seat and op != "SELL")
        if requested != filled:
            selected = deepcopy(own_window)
            return selected, dict(day=start // 24, name="baseline", gain=0, wage=0,
                                  revenue=0, advance=False, candidates=1,
                                  fallback="projected_input_shortfall", rejected={},
                                  decision_input_sha256=digest([observation, own_window, mode, rounds]),
                                  decision_output_sha256=digest(selected),
                                  seconds=time.perf_counter() - started)
        base, valid, selections, summary = R.block(sim, initial, pair, start, stop, rounds)
        idx = selections[mode]
        name, predicted, actions, advance = valid[idx]
        if not advance:
            selected = deepcopy(actions[seat][start:stop])
        else:
            suffix = name.rsplit(":", 1)[-1]
            items = {suffix.removeprefix("early_")} if suffix.startswith("early_") else R.OUTPUTS
            sim.reference_actions = pair
            replay = sim.run(initial, start, stop, actions, snapshots=True,
                             advance=advance, quota=base["sold"], reference=base,
                             advance_items=items)
            assert replay["money"] == predicted["money"]
            # A post-turn snapshot retains the action actually executed in the
            # previous turn, including generated sale orders and original slots.
            selected = [deepcopy((replay["snapshots"][t + 1] if t + 1 < stop
                                  else replay["state"])[seat].action) for t in range(start, stop)]
            materialized = list(pair)
            materialized[seat] = list(pair[seat])
            materialized[seat][start:stop] = selected
            check = sim.run(initial, start, stop, materialized)
            assert check["events"] == replay["events"]
            assert R.equivalent(replay, check, seat) is None
    return selected, dict(day=start // 24, **summary["selected"][mode],
                          candidates=len(summary["candidates"]), rejected=summary["rejected"],
                          decision_input_sha256=digest([observation, own_window, mode, rounds]),
                          decision_output_sha256=digest(selected),
                          seconds=time.perf_counter() - started)


def physical_signature(result, seat):
    farm = deepcopy(result["state"][0].observation.farms[seat])
    farm.pop("money", None)
    return dict(farm=farm, private=R.clean(result["state"][seat].observation.private))


def production(work, seat):
    return dict(sum((Counter({p: n for p, n in w["delta"].items() if n > 0})
                     for w in work if w["seat"] == seat and
                     w["cmd"][0] in ("HARVEST", "COLLECT_FERTILIZER")), Counter()))


def run_world(job):
    path, rounds, artifact_folder = job
    started = time.perf_counter()
    game, original = R.load_game(path)
    own = original[game["seat"]]
    pair = [deepcopy(own), deepcopy(own)]
    days = list(range(4, 27, 2)) if "fixed_leaders" in str(path) else list(range(3, 28, 2))
    live = R.Simulator(game)
    with live:
        null = live.run(live.initial, 0, 719, pair, capture=True)
    null_economics = [R.economic(null["events"], s) for s in range(2)]
    null_production = [production(null["work"], s) for s in range(2)]
    assert all(s.status == "DONE" for s in null["state"])
    for s, ec in enumerate(null_economics):
        assert null["money"][s] == 3000 + sum(ec["revenue"].values()) - sum(ec["spend"].values())
    output = dict(episode=game["episode"], source=str(Path(path).relative_to(R.ROOT)),
                  source_sha256=sha256(Path(path).read_bytes()).hexdigest(),
                  panel="leaders" if "fixed_leaders" in str(path) else "ladder",
                  null_cash=null["money"], null_economics=null_economics,
                  null_production=null_production, games=[])
    for mode in ("wage", "forecast"):
        for seat in range(2):
            state, cursor = deepcopy(live.initial), 0
            events, work, choices = [], [], []
            executed = deepcopy(pair)
            for day in days:
                start, stop = day * 24, (day + 2) * 24
                if cursor < start:
                    with live:
                        gap = live.run(state, cursor, start, executed, capture=True)
                    state = gap["state"]
                    events += gap["events"]
                    work += gap["work"]
                # Exactly the player's own observation crosses this boundary.
                actions, row = choose(deepcopy(state[seat].observation), own[start:stop], mode, rounds)
                executed[seat][start:stop] = actions
                with live:
                    result = live.run(state, start, stop, executed, capture=True)
                state = result["state"]
                events += result["events"]
                work += result["work"]
                choices.append(row)
                cursor = stop
            with live:
                result = live.run(state, cursor, 719, executed, capture=True)
            events += result["events"]
            work += result["work"]
            cash = result["money"]
            economics = [R.economic(events, s) for s in range(2)]
            assert all(s.status == "DONE" for s in result["state"])
            for s in range(2):
                ec = economics[s]
                assert cash[s] == 3000 + sum(ec["revenue"].values()) - sum(ec["spend"].values())
            actual_production = [production(work, s) for s in range(2)]
            unchanged = [physical_signature(result, s) == physical_signature(null, s) for s in range(2)]
            margin = cash[seat] - cash[1 - seat]
            control = null["money"][seat] - null["money"][1 - seat]
            row = dict(mode=mode, seat=seat, cash=cash, margin=margin,
                       control_margin=control, adjusted_margin=margin - control,
                       own_gain=cash[seat] - null["money"][seat],
                       rival_gain=cash[1 - seat] - null["money"][1 - seat],
                       economics=economics, production=actual_production,
                       same_production=[actual_production[s] == null_production[s] for s in range(2)],
                       same_terminal_farm_inventory=unchanged, choices=choices,
                       executed_actions_sha256=digest(executed))
            artifact = Path(artifact_folder) / f"{game['episode']}-{mode}-{seat}.actions.json.gz"
            artifact.write_bytes(gzip.compress(json.dumps(executed, separators=(",", ":")).encode(), mtime=0))
            row["executed_actions_artifact"] = str(artifact.relative_to(R.ROOT))
            output["games"].append(row)
    output["seconds"] = time.perf_counter() - started
    return output


def summary(worlds):
    output = {}
    for panel in ("all", "ladder", "leaders"):
        selected = [w for w in worlds if panel == "all" or w["panel"] == panel]
        if not selected:
            continue
        output[panel] = {}
        for mode in ("wage", "forecast"):
            games = [g for w in selected for g in w["games"] if g["mode"] == mode]
            clusters = [statistics.mean(g["margin"] for g in w["games"] if g["mode"] == mode)
                        for w in selected]
            rng = random.Random(20260921)
            boot = sorted(statistics.mean(rng.choices(clusters, k=len(clusters))) for _ in range(5000))
            cost = []
            revenue = []
            other = []
            for w in selected:
                for g in w["games"]:
                    if g["mode"] != mode:
                        continue
                    s = g["seat"]
                    base, ec = w["null_economics"][s], g["economics"][s]
                    wage = base["spend"].get("HIRE", 0) - ec["spend"].get("HIRE", 0)
                    rev = sum(ec["revenue"].values()) - sum(base["revenue"].values())
                    rest = sum(base["spend"].values()) - sum(ec["spend"].values()) - wage
                    assert g["own_gain"] == wage + rev + rest
                    cost.append(wage)
                    revenue.append(rev)
                    other.append(rest)
            output[panel][mode] = dict(
                worlds=len(selected), games=len(games),
                wins=sum(g["margin"] > 0 for g in games),
                ties=sum(g["margin"] == 0 for g in games),
                losses=sum(g["margin"] < 0 for g in games),
                mean_margin=statistics.mean(g["margin"] for g in games),
                paired_world_margin_bootstrap_95=[boot[125], boot[4874]],
                median_world_margin=statistics.median(clusters),
                paired_world_wins=sum(x > 0 for x in clusters),
                paired_world_ties=sum(x == 0 for x in clusters),
                paired_world_losses=sum(x < 0 for x in clusters),
                mean_own_gain=statistics.mean(g["own_gain"] for g in games),
                mean_rival_gain=statistics.mean(g["rival_gain"] for g in games),
                mean_wage_saving=statistics.mean(cost),
                mean_revenue_gain=statistics.mean(revenue),
                mean_other_saving=statistics.mean(other),
                own_production_changed=sum(not g["same_production"][g["seat"]] for g in games),
                rival_production_changed=sum(not g["same_production"][1-g["seat"]] for g in games),
                own_terminal_changed=sum(not g["same_terminal_farm_inventory"][g["seat"]] for g in games),
                rival_terminal_changed=sum(not g["same_terminal_farm_inventory"][1-g["seat"]] for g in games),
                decisions=sum(len(g["choices"]) for g in games),
                nonbaseline_decisions=sum(c["name"] != "baseline" for g in games for c in g["choices"]),
                input_shortfall_fallbacks=sum(c.get("fallback") == "projected_input_shortfall" for g in games for c in g["choices"]),
                max_planning_seconds=max(c["seconds"] for g in games for c in g["choices"]),
            )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=80)
    parser.add_argument("--tag", default="selfplay_causal_v1")
    args = parser.parse_args()
    paths = []
    for tag in ("fixed_ladder_v2", "fixed_leaders_v2"):
        paths.extend(R.ROOT / p for p in json.loads((R.OUT / tag / "manifest.json").read_text())["paths"])
    paths = paths[args.offset:args.offset + args.count]
    folder = R.OUT / args.tag
    folder.mkdir(parents=True, exist_ok=True)
    manifest = dict(arguments=vars(args), paths=[str(p.relative_to(R.ROOT)) for p in paths],
                    sources={str(p.relative_to(R.ROOT)): sha256(p.read_bytes()).hexdigest()
                             for p in (Path(__file__), Path(R.__file__), Path(R.engine().__file__))},
                    policy="Observation and own supplied 48h plan only; no actual future feasibility filter.",
                    design="Two modes x two seats + baseline mirror control per world; recorded shops only in evaluator.")
    manifest_path = folder / "manifest.json"
    if manifest_path.exists():
        assert json.loads(manifest_path.read_text()) == manifest, "Frozen experiment mismatch; choose a new tag."
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows, todo = [], []
    for p in paths:
        target = folder / (p.name.split(".")[0] + ".json")
        if target.exists():
            rows.append(json.loads(target.read_text()))
        else:
            todo.append(p)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_world, (p, args.rounds, folder)): p for p in todo}
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            (folder / f"{row['episode']}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            print(json.dumps(dict(episode=row["episode"], seconds=round(row["seconds"], 2),
                                  margins=[g["margin"] for g in row["games"]],
                                  own_gains=[g["own_gain"] for g in row["games"]],
                                  production_changes=[not g["same_production"][g["seat"]] for g in row["games"]])), flush=True)
    result = summary(rows)
    (folder / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

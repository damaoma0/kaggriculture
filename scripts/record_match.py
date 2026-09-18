"""Record a local match, with action-aligned logs and daily summaries.

Example: .venv/Scripts/python.exe scripts/record_match.py starter agents/public/tschinkel_router_v31.py --out results/fresh/start
"""
import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from kaggle_environments import make


def farm_summary(farm):
    crops, animals = Counter(), Counter()
    weeds = 0
    for row in farm["tiles"]:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            if tile.get("kind") == "PLANT":
                crops[tile["crop"]] += 1
            if tile.get("animal"):
                animals[tile["animal"]] += 1
            weeds += tile.get("kind") == "WEED"
    return dict(money=farm["money"], crops=dict(crops), animals=dict(animals),
                weeds=weeds, hands=len(farm["hands"]), quadrants=farm["unlocked_quadrants"])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("players", nargs=2)
    ap.add_argument("--seed", type=int, default=20260915)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--html", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    provenance = []
    for player in args.players:
        path = Path(player)
        provenance.append({"agent": player, "sha256": sha256(path.read_bytes()).hexdigest()
                           if path.is_file() else None})
    env = make("kaggriculture", configuration={"seed": args.seed}, debug=True)
    print(f"Starting seed {args.seed}: {args.players}", flush=True)
    env.run(args.players)
    replay = env.toJSON()
    (args.out / "replay.json").write_text(json.dumps(replay), encoding="utf-8")
    lines = ["# Match log", "", f"Seed: {args.seed}; kaggle-environments: {version('kaggle-environments')}",
             "", *[f"- Seat {i}: `{p}`" for i, p in enumerate(args.players)], "",
             "The replay contains both players' private state for offline analysis. An agent cannot see its opponent's private state during play.",
             "", "Orders in the turn log are requests, not proof of successful execution. Cash changes are exact net changes, including purchases and hires.",
             "", "## Daily checkpoints", "", "Day/hour are zero-based; checkpoints show the start of each day and the terminal state.", "",
             "| Step | Day:hour | Seat 0 cash | Seat 1 cash | Seat 0 crops / animals | Seat 1 crops / animals |",
             "|---:|---:|---:|---:|---|---|"]
    with (args.out / "turns.jsonl").open("w", encoding="utf-8") as log:
        for index, states in enumerate(replay["steps"]):
            obs = states[0]["observation"]
            farms = [farm_summary(f) for f in obs["farms"]]
            if index % 24 == 0 or index == len(replay["steps"]) - 1:
                cells = [f"{f['crops']} / {f['animals']}" for f in farms]
                line = f"| {index} | {obs['day']}:{obs['hour']:02d} | {farms[0]['money']:.0f} | {farms[1]['money']:.0f} | {cells[0]} | {cells[1]} |"
                lines.append(line)
                print(f"step={index:3} cash={farms[0]['money']:.0f}/{farms[1]['money']:.0f}", flush=True)
            if index == 0:
                continue
            before = replay["steps"][index - 1][0]["observation"]
            record = {"action_step": index - 1, "result_step": index,
                      "actions": [s.get("action") for s in states],
                      "statuses": [s["status"] for s in states], "farms_after": farms,
                      "cash_delta": [f["money"] - before["farms"][p]["money"] for p, f in enumerate(farms)],
                      "market_before": before["market"], "market_after": obs["market"],
                      "shops_after": obs["town"]["unlocked_shops"],
                      "private_after": [s["observation"]["private"] for s in states]}
            log.write(json.dumps(record) + "\n")
    final = replay["steps"][-1]
    summary = {"seed": args.seed, "players": provenance, "engine_version": version("kaggle-environments"),
               "configuration": replay["configuration"], "states": len(replay["steps"]),
               "rewards": [s["reward"] for s in final], "statuses": [s["status"] for s in final]}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines += ["", "## Final result", "", f"Rewards: {summary['rewards']}; statuses: {summary['statuses']}",
              "", "Files: `replay.json` (full state/action history), `turns.jsonl` (one action/result pair per line), `summary.json` (provenance and result)."]
    if args.html:
        (args.out / "replay.html").write_text(env.render(mode="html"), encoding="utf-8")
        lines += ["", "`replay.html` is the environment's native visual replay."]
    (args.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary), flush=True)
    if any(s != "DONE" for s in summary["statuses"]):
        raise SystemExit("Incomplete match; inspect replay for agent errors.")


if __name__ == "__main__":
    main()

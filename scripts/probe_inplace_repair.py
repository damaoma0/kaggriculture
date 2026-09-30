"""Fixed-world repairs to the day-21 one-tile tomato substitution.

This is a diagnostic of action continuity, not a tape-selection policy. All
opponent actions, shops, and our unrelated recorded commands stay fixed.
"""
from collections import Counter
from copy import deepcopy
import gzip
import json
from pathlib import Path

import research_labour_profit as R


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_tapes/inplace_repair_probe.json"
EPISODE = 111291994
END = 719


def evaluate(game, pair, seat):
    with R.Simulator(game) as sim:
        result = sim.run(sim.initial, 0, END, pair, capture=True)
    state = result["state"]
    own = state[seat].observation
    rival = state[1-seat].observation
    trades = Counter()
    trade_cash = Counter()
    for t, player, op, item, value in result["events"]:
        if player == seat:
            trades[(op, item)] += 1
            trade_cash[(op, item)] += value
    output = Counter()
    feed_day25 = []
    for work in result["work"]:
        if work["seat"] != seat:
            continue
        if work["cmd"][0] == "FEED" and 600 <= work["t"] < 624:
            feed_day25.append({"t": work["t"], "pos": work["pos"]})
        if work["cmd"][0] in ("HARVEST", "COLLECT_FERTILIZER"):
            output.update({item: n for item, n in work["delta"].items() if n > 0})
    money = float(own.farms[seat]["money"])
    rival_money = float(rival.farms[1-seat]["money"])
    return {
        "own_cash": money,
        "rival_cash": rival_money,
        "margin": money-rival_money,
        "own_revenue": R.economic(result["events"], seat)["revenue"],
        "own_spend": R.economic(result["events"], seat)["spend"],
        "feed_day25": feed_day25,
        "output": dict(sorted(output.items())),
        "final_shed": {p: own.private["shed"].get(p, 0) for p in ("WHEAT", "TOMATO", "CARROT", "MILK", "EGG", "WOOL")},
        "own_trades": {f"{op}:{item}": [n, trade_cash[(op, item)]] for (op, item), n in sorted(trades.items())},
    }


def main():
    with gzip.open(ROOT / f"data/ladder_panel/56395605/{EPISODE}.json.gz", "rt", encoding="utf-8") as handle:
        game = json.load(handle)
    seat = int(game["seat"])
    original = [deepcopy(game["our_actions"] if i == seat else game["opp_actions"]) for i in range(2)]
    assert original[seat][509]["hands"][5] == ["PLANT", "WHEAT"]
    assert [original[seat][594]["market"][0], original[seat][601]["market"][4]] == [
        ["SELL", "WHEAT", 11], ["BUY_PRODUCT", "WHEAT", 4]]
    scenarios = {"baseline": original}
    for name, reserve, buy, sell_tomato in (
        ("raw_edit", 0, 0, False),
        ("tomato_sale", 0, 0, True),
        ("reserve_3_sale", 3, 0, True),
        ("reserve_5_sale", 5, 0, True),
        ("buy_3_sale", 0, 3, True),
    ):
        pair = deepcopy(original)
        own = pair[seat]
        own[505]["market"].append(["BUY_SEED", "TOMATO", 1])
        own[509]["hands"][5] = ["PLANT", "TOMATO"]
        own[594]["market"][0][2] -= reserve
        own[601]["market"][4][2] += buy
        if sell_tomato:
            own[718]["market"].append(["SELL", "TOMATO", 1])
        scenarios[name] = pair
    results = {}
    for name, pair in scenarios.items():
        print("running", name, flush=True)
        results[name] = evaluate(game, pair, seat)
        print(name, "margin", results[name]["margin"], "feeds", len(results[name]["feed_day25"]), flush=True)
    baseline = results["baseline"]
    for name, row in results.items():
        row["margin_delta"] = row["margin"] - baseline["margin"]
        row["own_cash_delta"] = row["own_cash"] - baseline["own_cash"]
        row["rival_cash_delta"] = row["rival_cash"] - baseline["rival_cash"]
    OUT.write_text(json.dumps({"episode": EPISODE, "seat": seat, "scenarios": results,
        "limitation": "Single fixed recorded world and action stream; demand fit at day 21 did not justify tomato planting."}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

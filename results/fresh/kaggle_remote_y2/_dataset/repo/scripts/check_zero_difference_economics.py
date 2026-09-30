"""Explain the D12 zero-production-difference donor transplant economically."""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import research_labour_profit as R  # noqa: E402
from test_nearest_donor_windows import load_compact, raw_actions, read_json

OUT = ROOT / "results" / "fresh" / "tape_gap_plans"


def strip_money(farm):
    farm = deepcopy(farm)
    farm.pop("money", None)
    return farm


def window_events(events, seat, start, stop):
    return [e for e in events if e[1] == seat and start <= e[0] < stop]


def summarize_events(events, seat, start, stop):
    ev = window_events(events, seat, start, stop)
    econ = R.economic(ev, seat)
    buys, sells, hires = {}, {}, 0
    for t, s, op, item, price in ev:
        if op == "SELL":
            sells[item] = sells.get(item, 0) + 1
        elif op == "HIRE":
            hires += 1
        elif op.startswith("BUY"):
            key = op + (":" + item if item else "")
            buys[key] = buys.get(key, 0) + 1
    return dict(revenue=econ["revenue"], spend=econ["spend"], hires=hires,
                buy_success_counts=buys, sell_success_counts=sells,
                successful_event_count=len(ev))


def main():
    plan = read_json(OUT / "local_transfer.json")
    case = next(c for c in plan["cases"] if int(c["episode"]) == 111317319 and int(c["day"]) == 12)
    seat, day = int(case["seat"]), int(case["day"])
    start, stop = day * 24, (day + 3) * 24
    own_path = ROOT / "data" / "ladder_panel" / "56395605" / "111317319.json.gz"
    own_game = load_compact(own_path)
    original = [deepcopy(own_game["our_actions"] if i == int(own_game["seat"]) else own_game["opp_actions"]) for i in range(2)]
    donor_path = None
    for ds in (ROOT / "results" / "fresh" / "cumulative_planning" / "dataset_train.json",
               ROOT / "results" / "fresh" / "cumulative_planning" / "dataset_test.json"):
        for row in read_json(ds)["games"]:
            if int(row["episode"]) == int(case["source"]["donor_episode"]) and int(row["seat"]) == int(case["source"]["donor_seat"]):
                donor_path = Path(row["source_raw"])
    assert donor_path is not None
    donor = raw_actions(donor_path)
    borrowed = deepcopy(original)
    borrowed[seat][start:stop] = deepcopy(donor[int(case["source"]["donor_seat"])][start:stop])
    with R.Simulator(own_game) as sim:
        base = sim.run(sim.initial, 0, stop, original, capture=True, snapshots=True)
    with R.Simulator(own_game) as sim:
        trial = sim.run(sim.initial, 0, stop, borrowed, capture=True, snapshots=True)
    bf = base["state"][0].observation.farms[seat]
    tf = trial["state"][0].observation.farms[seat]
    bp = base["state"][seat].observation.private
    tp = trial["state"][seat].observation.private
    result = dict(
        episode=111317319, seat=seat, day=day, window_steps=[start, stop], donor_episode=int(case["source"]["donor_episode"]),
        baseline_money=float(bf["money"]), borrowed_money=float(tf["money"]), cash_delta=float(tf["money"] - bf["money"]),
        farm_without_money=dict(baseline=strip_money(bf), borrowed=strip_money(tf), equal=strip_money(bf) == strip_money(tf)),
        private=dict(baseline=deepcopy(bp), borrowed=deepcopy(tp), equal=R.clean(bp) == R.clean(tp)),
        inventories=dict(baseline=deepcopy(bp.get("inventories")), borrowed=deepcopy(tp.get("inventories"))),
        shed=dict(baseline=deepcopy(bp.get("shed")), borrowed=deepcopy(tp.get("shed"))),
        seeds=dict(baseline=deepcopy(bp.get("seeds")), borrowed=deepcopy(tp.get("seeds"))),
        economics=dict(baseline=summarize_events(base["events"], seat, start, stop), borrowed=summarize_events(trial["events"], seat, start, stop)),
        interpretation="Production is identical, but the borrowed window changes successful trade timing/quantities; cash difference is therefore liquidation/input economics, not extra harvested output.",
    )
    (OUT / "zero_difference_economics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("baseline_money", "borrowed_money", "cash_delta", "farm_without_money", "private", "economics")}, indent=2))


if __name__ == "__main__":
    main()

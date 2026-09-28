"""Paired saved-result economics and action audit; never execute an agent."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def difference(new, old):
    return {key:new.get(key, 0)-old.get(key, 0) for key in sorted(set(new)|set(old))
            if new.get(key, 0) != old.get(key, 0)}


def product_record(ledger, product):
    units, revenue = ledger["sold_units"].get(product, 0), ledger["revenue"].get(product, 0)
    return dict(collected_units=ledger["physical"].get("produced:"+product, 0), sold_units=units,
        revenue=revenue, average_sale_price=revenue/units if units else None)


def physical(action):
    return {key:action.get(key) for key in ("farmer", "hands")}


def fertilizer_record(ledger):
    physical = ledger["physical"]
    consumed = physical.get("op:FERTILIZE", 0)-physical.get("no_effect:FERTILIZE", 0)
    # The frozen engine consumes exactly one item for each effective FERTILIZE.
    # Invalid or missing-worker commands never enter op:FERTILIZE.
    return dict(collected_units=physical.get("produced:FERTILIZER", 0),
        internally_consumed_units=consumed, sold_units=ledger["sold_units"].get("FERTILIZER", 0),
        sales_revenue=ledger["revenue"].get("FERTILIZER", 0),
        purchase_spending=ledger["spend"].get("BUY_PRODUCT:FERTILIZER", 0))


def runtime_record(result, seat):
    times = result["timings"][seat]
    return dict(calls=len(times),total_seconds=sum(times),maximum_call_seconds=max(times,default=0),
        calls_over_one_second=sum(t>1 for t in times),
        measured_overage=result["measured_overage_used"][seat],
        remaining_engine_overage=result["engine_audit"]["remaining_overage"][seat])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--candidate", required=True)
    p.add_argument("--mode", choices=("live", "recorded"), default="live")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    study = args.study.resolve()
    assert not args.out.exists(), "Do not replace an earlier report"
    rows = []
    cases = read(study/"protocol.json")["development"][args.mode]
    if args.mode == "recorded":
        cases = read(study/"selections/development.json")["cases"]
    for case in cases:
        paths = [study/"runs"/name/"development"/args.mode/(case["id"]+".json")
                 for name in (args.baseline, args.candidate)]
        old, new = map(read, paths)
        assert old["case"] == new["case"] == case
        assert all(r["completed"] and r["ledger_verified"] and not r["errors"] and not r.get("error") for r in (old,new))
        seat = case["seat"]
        action_paths = [p.with_suffix(".actions.json") for p in paths]
        actions_old, actions_new = map(read, action_paths)
        first = {}
        for who in (seat,1-seat):
            changed = [step for step,(a,b) in enumerate(zip(actions_old[who],actions_new[who])) if physical(a) != physical(b)]
            first[str(who)] = dict(first_physical_difference=changed[0] if changed else None,
                changed_physical_hours=len(changed), exact_action_lists_equal=actions_old[who] == actions_new[who])
        daily = []
        for day in range(30):
            by_seat = {}
            for who in (seat,1-seat):
                values = []
                for result in (old,new):
                    start, end = result["daily"][who][day:day+2]
                    current = {key:difference(end[key],start[key]) for key in ("physical","sold_units","revenue","spend")}
                    current["money_change"] = end["money"]-start["money"]
                    current["fertilizer_internally_consumed_units"] = (
                        current["physical"].get("op:FERTILIZE",0)-current["physical"].get("no_effect:FERTILIZE",0))
                    values.append(current)
                by_seat[str(who)] = dict(baseline=values[0],candidate=values[1],
                    deltas={key:difference(values[1][key],values[0][key]) for key in ("physical","sold_units","revenue","spend")})
            quotes = []
            for result in (old,new):
                observation = next((r.get("current_observation", {}) for r in result["diagnostics"][seat] if r["day"]==day), {})
                quotes.append(observation.get("market", {}).get("prices"))
            daily.append(dict(day=day,ledgers=by_seat,baseline_dawn_prices=quotes[0],candidate_dawn_prices=quotes[1]))
        own_diagnostics = new["final_diagnostics"][str(seat)]
        planned = [dict(day=row["day"],**row["harvest_exchange"]) for row in own_diagnostics if row.get("harvest_exchange", {}).get("accepted")]
        for exchange in planned:
            next_dawn = next((r.get("current_observation", {}) for r in new["diagnostics"][seat]
                              if r["day"] == exchange["day"]+1), {})
            shed = (next_dawn.get("private") or {}).get("shed")
            exchange["observed_next_dawn_shed"] = shed
            exchange["observed_next_dawn_shed_total"] = sum(shed.values()) if shed is not None else None
            exchange["projected_midnight_load_exceeds100"] = exchange.get("midnight_load", 0)>100
        rejections = Counter()
        for row in own_diagnostics:
            rejections.update(row.get("harvest_exchange", {}).get("rejected", {}))
        products = {str(who):{product:dict(baseline=product_record(old["daily"][who][-1],product),
            candidate=product_record(new["daily"][who][-1],product)) for product in PRODUCTS} for who in (seat,1-seat)}
        rows.append(dict(case=case, hashes={str(p):sha(p) for p in paths+action_paths},
            baseline_margin=old["margin"],candidate_margin=new["margin"],margin_delta=new["margin"]-old["margin"],
            own_cash_delta=new["cash"]-old["cash"],rival_cash_delta=new["opponent_cash"]-old["opponent_cash"],
            baseline_shops=old["shops"],candidate_shops=new["shops"],shops_equal=old["shops"]==new["shops"],
            action_audit=first,planned_exchanges=planned,exchange_rejection_counts=dict(rejections),
            products=products,daily=daily,phase_cash=dict(baseline=old["phase_cash"],candidate=new["phase_cash"]),
            fertilizer={str(who):dict(baseline=fertilizer_record(old["daily"][who][-1]),
                candidate=fertilizer_record(new["daily"][who][-1])) for who in (seat,1-seat)},
            spending={str(who):dict(baseline=old["daily"][who][-1]["spend"],candidate=new["daily"][who][-1]["spend"])
                for who in (seat,1-seat)},
            runtime_by_seat={str(who):dict(baseline=runtime_record(old,who),candidate=runtime_record(new,who))
                for who in (seat,1-seat)},
            own_runtime=dict(baseline=old["measured_overage_used"][seat],candidate=new["measured_overage_used"][seat]),
            original_strict_eligibility=dict(baseline=old["eligible"],candidate=new["eligible"])))
    result = dict(scope="EIGHT_WORLD_PAIRED_INCREMENTAL_DEVELOPMENT_SCREEN", baseline=args.baseline,candidate=args.candidate,
        mode=args.mode,planned=8,completed=len(rows),absolute_win_threshold=None,
        wins=dict(baseline=sum(r["baseline_margin"]>0 for r in rows),candidate=sum(r["candidate_margin"]>0 for r in rows)),
        mean_candidate_margin=sum(r["candidate_margin"] for r in rows)/len(rows),
        mean_margin_delta=sum(r["margin_delta"] for r in rows)/len(rows),
        mean_own_cash_delta=sum(r["own_cash_delta"] for r in rows)/len(rows),
        mean_rival_cash_delta=sum(r["rival_cash_delta"] for r in rows)/len(rows),
        paired_better=sum(r["margin_delta"]>0 for r in rows),paired_same=sum(r["margin_delta"]==0 for r in rows),
        paired_worse=sum(r["margin_delta"]<0 for r in rows),shop_sequences_equal=sum(r["shops_equal"] for r in rows),
        planned_exchanges=sum(len(r["planned_exchanges"]) for r in rows),rows=rows,
        limitations=["Native live shop differences are endogenous; paired changes are not isolated fixed-world treatment effects.",
          "The ledger key produced:PRODUCT measures successful HARVEST/COLLECT_FERTILIZER inventory gains. Reported collected_units are not additional biological production.",
          "Exchange summaries describe accepted route plans. Full-game physical receipts require action/state evidence; the earlier D18 component had that separate verification.",
          "The inherited projected load bound can exceed100. Next-dawn shed observations are included for capacity-model audit and do not by themselves prove absence of transient overflow.",
          "Eight reused development worlds do not establish qualification strength. No automatic forty-world dispatch."],
        script_sha256=sha(Path(__file__)))
    assert len(rows)==8
    args.out.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("rows","limitations")},indent=2))


if __name__ == "__main__":
    main()

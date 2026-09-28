"""Audit saved V14/V13 decisions and ledgers for the largest paired regression."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, required=True)
    args = p.parse_args(); study = args.study.resolve()
    comparison = study/"reports/v14_recorded_incremental_comparison.json"
    paired = read(comparison)
    row = min(paired["rows"], key=lambda r:r["margin_delta"])
    assert row["case"]["episode"] == "111681195"
    seat = row["case"]["seat"]
    paths = [study/"runs"/name/"development/recorded"/(row["case"]["id"]+".json")
        for name in (paired["baseline"], paired["candidate"])]
    results = [read(path) for path in paths]
    action_paths = [p.with_suffix(".actions.json") for p in paths]
    actions = [read(path) for path in action_paths]
    diagnostics = [{r["day"]:r for r in result["final_diagnostics"][str(seat)]} for result in results]
    days = sorted(d for d in set(diagnostics[0]) & set(diagnostics[1])
        if "proposal" in diagnostics[0][d] and "proposal" in diagnostics[1][d])
    changed_days = [d for d in days if diagnostics[0][d]["proposal"] != diagnostics[1][d]["proposal"]]
    first = changed_days[0]
    assert first == 13
    observations = [next(r["current_observation"] for r in result["diagnostics"][seat] if r["day"]==first)
        for result in results]
    normalized = [deepcopy(x) for x in observations]
    budgets = [x.pop("remainingOverageTime") for x in normalized]
    assert normalized[0] == normalized[1]
    own_first = next(i for i,(a,b) in enumerate(zip(actions[0][seat], actions[1][seat])) if a != b)
    assert own_first == 313 and actions[0][1-seat] == actions[1][1-seat]
    counts = []
    for result in results:
        observation = next(r["current_observation"] for r in result["diagnostics"][seat] if r["day"]==first+1)
        counts.append(dict(Counter(t["crop"] for cells in observation["own_farm"]["tiles"] for t in cells
            if isinstance(t, dict) and "crop" in t)))
    economics = {}
    for who in (seat,1-seat):
        product_deltas = {}
        for product,pair in row["products"][str(who)].items():
            a,b = pair["baseline"],pair["candidate"]
            q0,q1 = a["sold_units"],b["sold_units"]
            v0,v1 = a["average_sale_price"],b["average_sale_price"]
            qterm = (q1-q0)*v0 if v0 is not None else None
            pterm = q1*(v1-v0) if v0 is not None and v1 is not None else None
            if qterm is not None and pterm is not None:
                assert abs(qterm+pterm-(b["revenue"]-a["revenue"])) < 1e-7
            product_deltas[product] = dict(collected_delta=b["collected_units"]-a["collected_units"],
                sold_delta=q1-q0, revenue_delta=b["revenue"]-a["revenue"],
                baseline_average_price=v0,candidate_average_price=v1,
                quantity_term_at_baseline_average_price=qterm,remaining_price_and_timing_term=pterm)
        spend = row["spending"][str(who)]
        spending = {k:spend["candidate"].get(k,0)-spend["baseline"].get(k,0)
            for k in set(spend["baseline"])|set(spend["candidate"])}
        spending = {k:v for k,v in spending.items() if v}
        revenue_change = sum(r["revenue_delta"] for r in product_deltas.values())
        cash_change = results[1]["cash_by_seat"][who]-results[0]["cash_by_seat"][who]
        assert revenue_change-sum(spending.values()) == cash_change
        economics[str(who)] = dict(products=product_deltas,spending_changes=spending,
            revenue_change=revenue_change,spending_change=sum(spending.values()),cash_change=cash_change,
            fertilizer=row["fertilizer"][str(who)])
    value = dict(scope="SAVED_DIAGNOSTIC_ONLY_NO_POLICY_RECOMPUTE_OR_GAME",case=row["case"],
        baseline=paired["baseline"],candidate=paired["candidate"],margin_delta=row["margin_delta"],
        first_changed_semantic_proposal_day=first,first_changed_own_action_step=own_first,
        both_action_prefixes_identical_steps=own_first,recorded_rival_actions_identical_all_steps=True,
        first_action_pair=[a[seat][own_first] for a in actions],
        first_dawn_economic_observations_equal=True,excluded_observation_field="remainingOverageTime",
        actual_remaining_overage=budgets,normalized_dawn_observation_sha256=digest(normalized[0]),
        dawn_decision_pair=[d[first] for d in diagnostics],next_dawn_actual_crop_counts=counts,
        economics=economics,phase_cash=row["phase_cash"],daily=row["daily"],
        limitations=["Final changes after the first admitted crop mix include downstream routing, maintenance, harvest/sale timing and repeated replanning; this is not a one-day ablation.",
            "Quantity/price terms are exact accounting using season average sale prices, not a causal separation of endogenous price and sale timing.",
            "The clock field differs between runs and is explicitly excluded only from the economic-observation equality check. The full saved observations and actual budgets are preserved."],
        hashes={str(path):sha(path) for path in paths+action_paths+[comparison,Path(__file__)]})
    output = study/"reports/v14_worst_recorded_case_mechanism.json"
    assert not output.exists()
    output.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(path=str(output),sha256=sha(output),first_day=first,first_step=own_first,
        own=economics[str(seat)]["cash_change"],rival=economics[str(1-seat)]["cash_change"])))


if __name__ == "__main__":
    main()

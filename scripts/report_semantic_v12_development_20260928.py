"""Native-world development comparison; no isolated treatment-effect claim."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", type=Path, required=True)
    study = p.parse_args().study.resolve()
    out = study / "reports/v12_native_development_comparison.json"
    assert not out.exists()
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for i in range(8):
        case = f"live-{i:02}"
        paths = [study / f"runs/{n}/development/live/{case}.json" for n in
                 ("strategy_v8_kb115lt2_readiness", "strategy_v12_kb115lt2_runtime_fast")]
        old, new = map(read, paths)
        assert old["case"] == new["case"] and new["eligible"] and new["ledger_verified"] and not new["errors"]
        seat = new["case"]["seat"]
        products = {}
        for product in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"):
            values = []
            for row in (old, new):
                ledger = row["daily"][seat][-1]
                units, revenue = ledger["sold_units"].get(product, 0), ledger["revenue"].get(product, 0)
                values.append(dict(produced=ledger["physical"].get("produced:" + product, 0),
                    sold_units=units, revenue=revenue, average_sale_price=revenue / units if units else None))
            products[product] = dict(v8=values[0], v12=values[1])
        rows.append(dict(case=case, seat=seat, source_hashes={str(x): sha(x) for x in paths},
            old_cash=old["cash"], new_cash=new["cash"], own_cash_delta=new["cash"]-old["cash"],
            old_rival_cash=old["opponent_cash"], new_rival_cash=new["opponent_cash"],
            rival_cash_delta=new["opponent_cash"]-old["opponent_cash"],
            old_margin=old["margin"], new_margin=new["margin"], margin_delta=new["margin"]-old["margin"],
            old_shops=old["shops"], new_shops=new["shops"], shops_equal=old["shops"] == new["shops"],
            entire_ledgers_equal=old["daily"] == new["daily"], candidate_overage=new["measured_overage_used"][seat],
            candidate_remaining=new["engine_audit"]["remaining_overage"][seat], products=products))
    report = dict(scope="COMPLETE_NATIVE_DEVELOPMENT_PANEL_NOT_FIXED_WORLD_CAUSAL_ESTIMATE", candidate="strategy_v12_kb115lt2_runtime_fast",
        planned=8, technically_valid=8, wins=sum(r["new_margin"] > 0 for r in rows), required_wins=6,
        gate_pass=False, mean_margin=sum(r["new_margin"] for r in rows)/8,
        mean_paired_native_margin_delta=sum(r["margin_delta"] for r in rows)/8,
        mean_own_cash_delta=sum(r["own_cash_delta"] for r in rows)/8, rows=rows,
        recorded_panel_dispatched=False, qualification_dispatched=False,
        note="Changed01/07 have different natural shops; increased margin partly reflects reduced rival cash. Keep units, realized prices and both cash changes together. No promotion, no forty-world run.",
        script_sha256=sha(Path(__file__)))
    assert report["wins"] == 5 and report["mean_margin"] == 1992.875
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()

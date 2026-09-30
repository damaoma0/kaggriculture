"""Print concise decomposition of reveal-aligned planting trials."""
import json
from probe_semantic_handoff import ROOT


BASE=ROOT/"results/fresh/semantic_tapes"


def delta(a,b):
    return {k:a.get(k,0)-b.get(k,0) for k in a.keys()|b.keys() if a.get(k,0)!=b.get(k,0)}


def main():
    data=json.loads((BASE/"earlier_strawberry_shift.json").read_text(encoding="utf-8"))
    base=data["baseline"]
    examples=((12,302,[2,3]),(15,365,[4,6]))
    for day,t,pos in examples:
        v=next(r for r in data["rows"] if r["day"]==day and r["t"]==t and r["pos"]==pos and r["seed_mode"]=="use_stock")
        print(json.dumps({"day":day,"t":t,"pos":pos,"margin_delta":v["margin_delta"],
            "cash_delta":v["cash_delta"],"rival_cash_delta":v["rival_cash_delta"],
            "output_delta":v["output_delta"],"revenue_delta":delta(v["revenue"],base["revenue"]),
            "spend_delta":delta(v["spend"],base["spend"]),
            "tilework":[{"t":w["t"],"cmd":w["cmd"],"positive_delta":{p:n for p,n in w["delta"].items() if n>0}}
                        for w in v["tilework"]]},separators=(",",":")))
    portfolio=json.loads((BASE/"earlier_strawberry_portfolio.json").read_text(encoding="utf-8"))["recipes"]["day12_pair_day15_pair"]
    print(json.dumps({"portfolio":"day12_pair_day15_pair","margin_delta":portfolio["margin_delta"],
        "cash_delta":portfolio["cash_delta"],"rival_cash_delta":portfolio["rival_cash_delta"],
        "output_delta":delta(portfolio["output"],base["output"]),
        "revenue_delta":delta(portfolio["revenue"],base["revenue"]),
        "spend_delta":delta(portfolio["spend"],base["spend"]),
        "shed":portfolio["shed"]},separators=(",",":")))


if __name__=="__main__":
    main()

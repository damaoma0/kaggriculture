"""One-sheep forced day-18 Yarn response, exact fixed-opponent replay.

This is an intentionally permissive diagnostic of the existing sheep overlay.
It changes no policy before day 18 and does not represent a deployable gate.
"""
from hashlib import sha256
import json

import experiment_m1_micro as micro
from probe_semantic_handoff import ROOT


OUT=ROOT/"results/fresh/semantic_tapes/late_yarn_sheep_case"
EPISODE=111287532


def main():
    base=(ROOT/"agents/mgt_m1.py").read_bytes()
    old=b"_SHP_CFG = {'enabled': True, 'max_sheep': 16, 'max_hands': 4, 'min_deficit': 2, 'min_profit': 3000, 'first_day': 6, 'last_day': 19, 'latest_hour': 8, 'cash_margin': 2000, 'labour_model': 'count', 'hire_guard': 1}"
    new=b"_SHP_CFG = {'enabled': True, 'max_sheep': 12, 'max_hands': 4, 'min_deficit': 1, 'min_profit': -10000, 'first_day': 18, 'last_day': 18, 'latest_hour': 8, 'cash_margin': 2000, 'labour_model': 'count', 'hire_guard': 1}"
    lookup_old=b"_SHP_LOOKUP = {3: 10, 6: 9, 9: 4, 12: 2, 15: 2}"
    lookup_new=b"_SHP_LOOKUP = {3: 10, 6: 9, 9: 4, 12: 2, 15: 2, 18: 2}"
    assert base.count(old)==1 and base.count(lookup_old)==1
    forced=base.replace(old,new).replace(lookup_old,lookup_new)
    sources={"baseline":base,"forced_one_day18_sheep":forced}
    (OUT/"sources").mkdir(parents=True,exist_ok=True)
    for arm,body in sources.items():
        (OUT/"sources"/f"{arm}.py").write_bytes(body)
    design={"source_hashes":{arm:sha256(body).hexdigest() for arm,body in sources.items()}}
    micro.OUT=OUT
    summaries={}
    for arm in sources:
        result=micro.historical_job((arm,EPISODE,design))
        print(json.dumps(result),flush=True)
        row=json.loads((OUT/"historical"/f"{arm}-{EPISODE}.json").read_text(encoding="utf-8"))
        summaries[arm]=row
    a,b=summaries.values()
    def delta(x,y):
        return {k:y.get(k,0)-x.get(k,0) for k in sorted(set(x)|set(y)) if y.get(k,0)!=x.get(k,0)}
    result={"episode":EPISODE,"baseline_margin":a.get("margin"),
            "forced_margin":b.get("margin"),"margin_delta":b.get("margin",0)-a.get("margin",0),
            "cash_delta":b.get("cash",0)-a.get("cash",0),
            "opponent_cash_delta":b.get("opponent_cash",0)-a.get("opponent_cash",0),
            "first_change":b.get("first_change"),"action_changes":b.get("action_changes"),
            "overlay":b.get("overlay"),
            "our_revenue_delta":delta(a["economics"][0]["revenue"],b["economics"][0]["revenue"]),
            "our_spend_delta":delta(a["economics"][0]["spend"],b["economics"][0]["spend"]),
            "rival_revenue_delta":delta(a["economics"][1]["revenue"],b["economics"][1]["revenue"]),
            "rival_spend_delta":delta(a["economics"][1]["spend"],b["economics"][1]["spend"]),
            "limitation":"Forced permissive one-sheep overlay in one recorded world, fixed rival actions and shop sequence. It may alter other agent actions after day 18."}
    (OUT/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("baseline_margin","forced_margin","margin_delta","cash_delta",
                                            "opponent_cash_delta","first_change","action_changes",
                                            "our_revenue_delta","our_spend_delta")},indent=2))


if __name__=="__main__":
    main()

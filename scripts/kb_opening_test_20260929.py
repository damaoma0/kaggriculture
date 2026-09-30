"""Can our executor play days 0-5 from a tile plan? (hand-planned opening, user 2026-09-29: "keep 12 melons and plan an
opening with an advantage over both DSM and MGT").

The v16 executor (agents/mgt_lead_kb115lt2_v16.py with V13's executor recipe, v16's flags and the planner window opened to
day 0) plays a TilePlanView plan from step 0 in a recorded DSM world (seed, recorded shops) against the recorded
opponent's actions; a second world replays DSM's own actions as the reference. Dawn states of days 1..N for both: cash,
animals, crops, structures, hands, and the commands that had no effect.

usage: kb_opening_test_20260929.py --ep 112570602 [--plan results/fresh/tile_plans/dsm40.json] [--days 6]
       [--out results/fresh/kb_opening_20260929/<ep>.json]"""
import argparse
import glob
import gzip
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
CAND = ROOT / "results/fresh/semantic_h2h_20260929/study/candidates/v16/project/results/fresh/semantic_strategy_20260928"


def board(farm, private=None):
    c = Counter()
    for row in farm["tiles"]:
        for t in row:
            if isinstance(t, dict):
                if t.get("animal"):
                    c["a:" + t["animal"]] += 1
                elif t.get("kind") == "PLANT":
                    c["c:" + t["crop"]] += 1
                elif t.get("kind") == "STRUCTURE" or t.get("structure"):
                    c["s:" + str(t.get("structure") or t.get("kind"))] += 1
                elif t.get("kind") == "WEED":
                    c["weed"] += 1
    return dict(sorted(c.items()))


def load_executor(extra=None, exe="agents/mgt_lead_kb115lt2_v16.py"):
    spec = importlib.util.spec_from_file_location("_kbopen_exec", ROOT / exe)
    kb = importlib.util.module_from_spec(spec)
    sys.modules["_kbopen_exec"] = kb
    spec.loader.exec_module(kb)
    kb.CFG.update(json.loads((CAND / "executor_recipe_online.json").read_text()))
    kb.CFG.update(json.loads((CAND / "candidate_config.json").read_text()).get("executor", {}))
    kb.CFG.update(sd_days=[0, 29])
    kb.CFG.update(extra or {})
    kb._TP_LEAK.clear()
    kb._TGT_EP = None
    return kb


def run(ep, plan, days, extra=None, log_steps=False, exe="agents/mgt_lead_kb115lt2_v16.py", finance=True):
    tape = json.load(gzip.open(glob.glob(str(ROOT / f"data/leader_tapes/*/{ep}.json.gz"))[0], "rt", encoding="utf-8"))
    seat = int(tape["seat"])
    kb = load_executor(extra, exe)
    kb._T = kb.TilePlanView.from_dict(plan)
    books0 = list(kb.CFG["sd_books_sell"])
    if finance:                                    # the stack's early financing step (entry: _finance_execution)
        sys.path.insert(0, str(CAND.parents[3] / "scripts"))
        from semantic_strategy_financing_20260928 import capital_pacing_products
        fin_cfg = json.loads((CAND / "candidate_config.json").read_text()).get("early_financing")
    ours, ref = UE.World(tape["seed"], tape["shops"]), UE.World(tape["seed"], tape["shops"])
    noeff = [Counter(), Counter()]
    o_apply = E._apply_unit_action

    def apply(farm, private, idx, action, *a, **k):
        r = o_apply(farm, private, idx, action, *a, **k)
        if r is False or r is None and isinstance(action, list) and action and action[0] not in ("PASS",):
            pass
        return r
    rows, actions = [], []
    ledger = [[Counter() for _ in range(days + 1)] for _ in range(2)]   # [0] ours, [1] DSM: per day "op|item" -> money
    o_commit = E._commit_unit

    def commit(op, item, price, farm, private, market, *a, **k):
        r = o_commit(op, item, price, farm, private, market, *a, **k)
        if r:
            w_ = 0 if farm is ours.farms[seat] else (1 if farm is ref.farms[seat] else None)
            if w_ is not None:
                ledger[w_][min(days, cur_t[0] // 24)][f"{op}|{item}"] += price * (1 if op == "SELL" else -1)
        return r
    o_hire = E._do_hire

    def hire(farm, *a, **k):
        m0 = farm["money"]
        r = o_hire(farm, *a, **k)
        w_ = 0 if farm is ours.farms[seat] else (1 if farm is ref.farms[seat] else None)
        if w_ is not None and farm["money"] != m0:
            ledger[w_][min(days, cur_t[0] // 24)]["HIRE"] += farm["money"] - m0
        return r
    cur_t = [0]
    E._commit_unit, E._do_hire = commit, hire
    for t in range(days * 24):
        cur_t[0] = t
        if t % 24 == 0:
            d = t // 24
            rows.append(dict(day=d, ours=dict(cash=ours.farms[seat]["money"], hands=len(ours.farms[seat]["hands"]),
                                             board=board(ours.farms[seat]), shed=dict(ours.private(seat)["shed"]),
                                             seeds=dict(ours.private(seat)["seeds"])),
                             dsm=dict(cash=ref.farms[seat]["money"], hands=len(ref.farms[seat]["hands"]),
                                      board=board(ref.farms[seat]), shed=dict(ref.private(seat)["shed"]))))
        obs = ours.obs(seat)
        if finance:
            kb.CFG["sd_books_sell"], _ = capital_pacing_products(obs, kb._T, kb._S, books0, fin_cfg, kb._walk_cap)
        a = kb.agent(obs, None)
        actions.append(a)
        other = UE.tape_action(tape["opp_actions"], t)
        ours.step([a, other] if seat == 0 else [other, a])
        ref.step([UE.tape_action(tape["actions"], t), other] if seat == 0 else [other, UE.tape_action(tape["actions"], t)])
    d = days
    rows.append(dict(day=d, ours=dict(cash=ours.farms[seat]["money"], hands=len(ours.farms[seat]["hands"]),
                                     board=board(ours.farms[seat]), shed=dict(ours.private(seat)["shed"])),
                     dsm=dict(cash=ref.farms[seat]["money"], hands=len(ref.farms[seat]["hands"]), board=board(ref.farms[seat]),
                              shed=dict(ref.private(seat)["shed"]))))
    E._commit_unit, E._do_hire = o_commit, o_hire
    for row in rows:
        if row["day"] < days:
            row["ours"]["flows"] = {k: round(v) for k, v in ledger[0][row["day"]].items()}
            row["dsm"]["flows"] = {k: round(v) for k, v in ledger[1][row["day"]].items()}
    st = kb._sd_state(kb._S)["st"] if kb._S is not None else {}
    return dict(ep=ep, seat=seat, rows=rows, executor_errors=int(st.get("errors", 0)), last_error=st.get("last_error", ""),
                actions=actions if log_steps else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--plan", default="results/fresh/tile_plans/dsm40.json")
    ap.add_argument("--days", type=int, default=6)
    ap.add_argument("--out")
    ap.add_argument("--exe", default="agents/mgt_lead_kb115lt2_v16.py")
    ap.add_argument("--cfg", default="{}", help="extra executor settings (JSON)")
    a = ap.parse_args()
    plans = json.loads((ROOT / a.plan).read_text())
    plan = plans[a.ep] if a.ep in plans else plans
    r = run(a.ep, plan, a.days, extra=json.loads(a.cfg), log_steps=bool(a.out), exe=a.exe)
    for row in r["rows"]:
        print(f"dawn d{row['day']}: ours cash {row['ours']['cash']:6.0f} hands {row['ours']['hands']:2d} {row['ours']['board']}")
        print(f"          DSM  cash {row['dsm']['cash']:6.0f} hands {row['dsm']['hands']:2d} {row['dsm']['board']}")
        if "flows" in row["ours"]:
            print(f"      day {row['day']} flows ours {row['ours']['flows']}")
            print(f"      day {row['day']} flows DSM  {row['dsm']['flows']}")
    print("executor errors", r["executor_errors"], r["last_error"])
    if a.out:
        out = ROOT / a.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(r))


if __name__ == "__main__":
    main()

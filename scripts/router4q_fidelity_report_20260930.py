"""Summary tables of router4q_fidelity_20260930.py outputs (markdown to stdout).

usage: router4q_fidelity_report_20260930.py results/fresh/router4q_20260930/fidelity_<tag>.json [...]"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict

ANIMALS = ("co", "sh", "go")
CROPS = ("ST", "ME", "WH", "CA", "TO")


def med(xs):
    return st.median(xs) if xs else float("nan")


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def summarize(rows):
    out = {}
    out["n"] = len(rows)
    for d in ("6", "9", "11", "12"):
        rs = [r["days"][d] for r in rows if d in r["days"]]
        if not rs:
            continue
        out[f"d{d}_ham_mean"] = mean([x["ham_leader"] for x in rs])
        out[f"d{d}_ham_med"] = med([x["ham_leader"] for x in rs])
        out[f"d{d}_ham0"] = sum(x["ham_leader"] == 0 for x in rs)
        out[f"d{d}_ham_le4"] = sum(x["ham_leader"] <= 4 for x in rs)
        fl = [x["ham_followed"] for x in rs if x["ham_followed"] is not None]
        out[f"d{d}_hamfol_mean"] = mean(fl)
        out[f"d{d}_cash_diff_mean"] = mean([x["cash"] - x["cash_leader"] for x in rs])
        out[f"d{d}_cash_absdiff_med"] = med([abs(x["cash"] - x["cash_leader"]) for x in rs])
        out[f"d{d}_q_ours"] = mean([x["quadrants"] for x in rs])
        out[f"d{d}_q_lead"] = mean([x["quadrants_leader"] for x in rs])
        out[f"d{d}_q_equal"] = sum(x["quadrants"] == x["quadrants_leader"] for x in rs)
        out[f"d{d}_empty_ours"] = mean([x["counts"].get(" .", 0) for x in rs])
        out[f"d{d}_empty_lead"] = mean([x["counts_leader"].get(" .", 0) for x in rs])
        for k in ANIMALS + CROPS + ("pa", "co_"):
            out[f"d{d}_{k}_ours"] = mean([x["counts"].get(k, 0) for x in rs])
            out[f"d{d}_{k}_lead"] = mean([x["counts_leader"].get(k, 0) for x in rs])
        out[f"d{d}_control_ok"] = sum(bool(x["control_ok"]) for x in rs)
    out["switches_mean"] = mean([r["report"].get("switches", 0) for r in rows])
    out["switch_days"] = Counter()
    for r in rows:
        prev = None
        for h in r["history"]:
            if prev is not None and h[1] != prev:
                out["switch_days"][h[0]] += 1
            prev = h[1]
    out["router_errors"] = sum(r["report"].get("router_errors", 0) for r in rows)
    out["opening_fallback"] = sum(r["report"].get("opening_fallback", 0) for r in rows)
    tot = defaultdict(list)
    for r in rows:
        f = r["fails"][:11]
        c = r["lead_fails_control"][:11]
        tot["buy_cash"].append(sum(v for day in f for k, v in day.items() if k.startswith("buy_cash")))
        tot["buy_cash_lead"].append(sum(v for day in c for k, v in day.items() if k.startswith("buy_cash")))
        tot["hire_fail"].append(sum(day.get("hire_fail", 0) for day in f))
        tot["hire_fail_lead"].append(sum(day.get("hire_fail", 0) for day in c))
        tot["hire_ok"].append(sum(day.get("hire_ok", 0) for day in f))
        tot["hire_ok_lead"].append(sum(day.get("hire_ok", 0) for day in c))
        tot["land_fail"].append(sum(day.get("land_fail", 0) for day in f))
        tot["land_fail_lead"].append(sum(day.get("land_fail", 0) for day in c))
        tot["no_effect"].append(sum(day.get("no_effect", 0) for day in f))
        tot["no_effect_lead"].append(sum(day.get("no_effect", 0) for day in c))
        tot["opp_excess"].append(r["opp_no_effect"] - r["opp_no_effect_control"])
        tot["buy_cash_d6_10"].append(sum(v for day in f[6:11] for k, v in day.items() if k.startswith("buy_cash")))
        tot["buy_cash_d0_5"].append(sum(v for day in f[:6] for k, v in day.items() if k.startswith("buy_cash")))
    out["fails"] = {k: mean(v) for k, v in tot.items()}
    out["opp_excess_gt20"] = sum(1 for v in tot["opp_excess"] if v > 20)
    # land timing: day the 3rd / 4th quadrant arrived (first dawn with q >= 3 / 4, minus one)
    return out


def land_days(rows):
    c3, c4 = Counter(), Counter()
    for r in rows:
        q9, q11 = r["days"].get("9", {}), r["days"].get("11", {})
        c3["ours q3 by d9 dawn"] += q9.get("quadrants", 0) >= 3
        c3["lead q3 by d9 dawn"] += q9.get("quadrants_leader", 0) >= 3
        c4["ours q4 by d11 dawn"] += q11.get("quadrants", 0) >= 4
        c4["lead q4 by d11 dawn"] += q11.get("quadrants_leader", 0) >= 4
    return dict(c3), dict(c4)


def fmt(x, nd=1):
    return "-" if x is None or x != x else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def main():
    for path in sys.argv[1:]:
        data = json.loads(open(path, encoding="utf-8").read())
        rows = data["rows"]
        print(f"\n## {path} (lib {data['lib']}, until step {data['until']})\n")
        groups = defaultdict(list)
        for r in rows:
            groups[r["team"]].append(r)
        groups["ALL"] = rows
        print("| worlds | n | d6 ham mean/med (=0, <=4) | d6 cash diff | d9 ham | d9 ham vs followed | d11 ham | d11 ham vs followed | d11 cash diff | d12 ham | q3 by d9 ours/lead | q4 by d11 ours/lead | empty d11 ours/lead | empty d12 ours/lead | switches |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for g, rs in groups.items():
            s = summarize(rs)
            l3, l4 = land_days(rs)
            print(f"| {g} | {s['n']} | {fmt(s.get('d6_ham_mean'))} / {fmt(s.get('d6_ham_med'))} ({s.get('d6_ham0')}, {s.get('d6_ham_le4')}) | "
                  f"{fmt(s.get('d6_cash_diff_mean'), 0)} | {fmt(s.get('d9_ham_mean'))} | {fmt(s.get('d9_hamfol_mean'))} | "
                  f"{fmt(s.get('d11_ham_mean'))} | {fmt(s.get('d11_hamfol_mean'))} | {fmt(s.get('d11_cash_diff_mean'), 0)} | "
                  f"{fmt(s.get('d12_ham_mean'))} | {l3.get('ours q3 by d9 dawn')}/{l3.get('lead q3 by d9 dawn')} | "
                  f"{l4.get('ours q4 by d11 dawn')}/{l4.get('lead q4 by d11 dawn')} | {fmt(s.get('d11_empty_ours'))}/{fmt(s.get('d11_empty_lead'))} | "
                  f"{fmt(s.get('d12_empty_ours'))}/{fmt(s.get('d12_empty_lead'))} | {fmt(s['switches_mean'], 2)} |")
        print()
        print("| worlds | days 0-10 failed buys (cash) ours/lead | of which d0-5 / d6-10 | hires ok ours/lead | hire fails ours/lead | land fails ours/lead | no-effect unit cmds ours/lead | opp extra no-effect (>20 worlds) | switch days | control ok d6/d12 |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for g, rs in groups.items():
            s = summarize(rs)
            f = s["fails"]
            print(f"| {g} | {fmt(f['buy_cash'])}/{fmt(f['buy_cash_lead'])} | {fmt(f['buy_cash_d0_5'])} / {fmt(f['buy_cash_d6_10'])} | "
                  f"{fmt(f['hire_ok'])}/{fmt(f['hire_ok_lead'])} | {fmt(f['hire_fail'])}/{fmt(f['hire_fail_lead'])} | "
                  f"{fmt(f['land_fail'])}/{fmt(f['land_fail_lead'])} | {fmt(f['no_effect'])}/{fmt(f['no_effect_lead'])} | "
                  f"{fmt(f['opp_excess'])} ({s['opp_excess_gt20']}) | {dict(sorted(s['switch_days'].items()))} | "
                  f"{s.get('d6_control_ok')}/{s.get('d12_control_ok')} |")
        print()
        print("| worlds | day | co | sh | go | ST | ME | WH | CA | TO | pa (empty pasture) | empty |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for g, rs in groups.items():
            s = summarize(rs)
            for d in ("6", "9", "11"):
                cells = " | ".join(f"{fmt(s.get(f'd{d}_{k}_ours'))}/{fmt(s.get(f'd{d}_{k}_lead'))}" for k in ANIMALS + CROPS + ("pa",))
                print(f"| {g} | {d} | {cells} | {fmt(s.get(f'd{d}_empty_ours'))}/{fmt(s.get(f'd{d}_empty_lead'))} |")


if __name__ == "__main__":
    main()

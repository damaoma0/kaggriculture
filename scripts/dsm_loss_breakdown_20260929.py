"""Where we lose to current DSM (submission 56619023, 3 quadrants): the current-DSM worlds of dsmseat_cases.json, each a
full game of our candidate in DSM's seat against the recorded opponent (own tape left out of our router; local_dsmfull)
vs DSM's own recorded game (its source control) - both against the same opponent. Gap = our margin - DSM's margin =
(our cash - DSM's cash) - (the opponent's cash in our game - in DSM's game). Per product: our revenue / units / price vs
DSM's, and the opponent's revenue difference; spending by kind; the margin gap by day.

usage: dsm_loss_breakdown_20260929.py [CAND]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
PROD = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def main():
    cand = sys.argv[1] if len(sys.argv) > 1 else "n18rc105"
    cases = [c["id"] for c in json.loads((H / "dsmseat_cases.json").read_text())["cases"] if c["id"].startswith("dsm3q-")]
    R = [json.loads((H / "local_dsmfull" / cand / f"{c}.json").read_text()) for c in cases]
    C = [json.loads((H / "local_dsmfull/_controls" / f"{c}.json").read_text()) for c in cases]
    n = len(cases)
    s = lambda x: int(x["case"]["seat"])
    gap = sum(r["margin"] - c["margin"] for r, c in zip(R, C)) / n
    print(f"{cand} vs current DSM, {n} worlds: our margin {sum(r['margin'] for r in R) / n:+.0f}, DSM's {sum(c['margin'] for c in C) / n:+.0f},"
          f" gap {gap:+.0f} = our cash {sum(r['cash'] - c['cash'] for r, c in zip(R, C)) / n:+.0f}"
          f" - opponent {sum(r['opponent_cash'] - c['opponent_cash'] for r, c in zip(R, C)) / n:+.0f};"
          f" wins ours {sum(1 for r in R if r['margin'] > 0)}, DSM {sum(1 for c in C if c['margin'] > 0)}")
    print(f"  {'product':11s} {'our rev':>8s} {'DSM rev':>8s} {'gap':>7s} | {'our units@price':>15s} | {'DSM units@price':>15s} | {'opp rev Δ':>9s} | margin effect")
    tot_m = 0
    for p in PROD:
        ro = sum(r["daily"][s(r)][30]["revenue"].get(p, 0) for r in R) / n
        rd = sum(c["daily"][s(c)][30]["revenue"].get(p, 0) for c in C) / n
        uo = sum(r["daily"][s(r)][30]["sold_units"].get(p, 0) for r in R) / n
        ud = sum(c["daily"][s(c)][30]["sold_units"].get(p, 0) for c in C) / n
        op = sum(r["daily"][1 - s(r)][30]["revenue"].get(p, 0) - c["daily"][1 - s(c)][30]["revenue"].get(p, 0) for r, c in zip(R, C)) / n
        eff = (ro - rd) - op
        tot_m += eff
        print(f"  {p:11s} {ro:8.0f} {rd:8.0f} {ro - rd:+7.0f} | {uo:5.0f} @{ro / max(uo, 1e-9):6.1f} | {ud:5.0f} @{rd / max(ud, 1e-9):6.1f} | {op:+9.0f} | {eff:+7.0f}")
    sp = defaultdict(lambda: [0.0, 0.0])
    osp = 0.0
    for r, c in zip(R, C):
        for side, x in ((0, r), (1, c)):
            for k, v in x["daily"][s(x)][30]["spend"].items():
                kk = k.split(":")[0] + (":" + k.split(":")[1] if k.startswith(("BUY_ANIMAL", "BUY_PRODUCT")) else "")
                sp[kk][side] += v / n
        osp += (sum(r["daily"][1 - s(r)][30]["spend"].values()) - sum(c["daily"][1 - s(c)][30]["spend"].values())) / n
    print(f"  products total margin effect {tot_m:+.0f}")
    print("  our spend vs DSM:", ", ".join(f"{k} {v[0]:.0f}/{v[1]:.0f} ({v[0] - v[1]:+.0f})" for k, v in
                                      sorted(sp.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1])) if abs(v[0] - v[1]) >= 50),
          f"| opponent spend Δ {osp:+.0f}")
    line = []
    for dd in (5, 8, 10, 12, 15, 18, 21, 24, 27, 29):
        g = sum((r["daily"][s(r)][dd + 1]["money"] - r["daily"][1 - s(r)][dd + 1]["money"])
                - (c["daily"][s(c)][dd + 1]["money"] - c["daily"][1 - s(c)][dd + 1]["money"]) for r, c in zip(R, C)) / n
        line.append(f"d{dd} {g:+.0f}")
    print("  margin gap (ours - DSM) at the end of day:", " | ".join(line))


if __name__ == "__main__":
    main()

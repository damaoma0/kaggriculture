"""Where we lose to the leaders (leaders panel: our candidate vs a recorded leader in its own game, exact credit): per
opponent family, the margin, our cash vs the leader's, revenue / units / price by product (ours vs the leader's in the
same game), spending by kind, and the margin gap by day.

usage: leader_loss_breakdown_20260929.py [CAND] [--dir leadersx_credit]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
PROD = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def main():
    a = sys.argv
    cand = a[1] if len(a) > 1 and not a[1].startswith("--") else "n18rc105"
    d = H / (a[a.index("--dir") + 1] if "--dir" in a else "leadersx_credit") / cand
    games = defaultdict(list)
    for p in sorted(d.glob("*.json")):
        if p.name.endswith((".actions.json", ".spawns.json")):
            continue
        x = json.loads(p.read_text())
        if not isinstance(x, dict) or x.get("margin") is None:
            continue
        fam = "-".join(p.stem.split("-")[:2])
        games[fam].append(x)
        games["ALL"].append(x)
    for fam in sorted(games, key=lambda f: (f != "ALL", f)):
        G = games[fam]
        n = len(G)
        s_of = lambda x: int(x["case"]["seat"])
        m = sum(x["margin"] for x in G) / n
        wins = sum(1 for x in G if x["margin"] > 0)
        oc = sum(x["cash"] for x in G) / n
        lc = sum(x["opponent_cash"] for x in G) / n
        print(f"\n===== {fam}: {n} games, wins {wins}, margin {m:+.0f} (our cash {oc:.0f}, leader {lc:.0f})")
        print(f"  {'product':11s} {'our rev':>8s} {'leader':>8s} {'gap':>7s} | {'our units@price':>16s} | {'leader units@price':>18s}")
        tot = 0
        for pr in PROD:
            ro = sum(x["daily"][s_of(x)][30]["revenue"].get(pr, 0) for x in G) / n
            rl = sum(x["daily"][1 - s_of(x)][30]["revenue"].get(pr, 0) for x in G) / n
            uo = sum(x["daily"][s_of(x)][30]["sold_units"].get(pr, 0) for x in G) / n
            ul = sum(x["daily"][1 - s_of(x)][30]["sold_units"].get(pr, 0) for x in G) / n
            tot += ro - rl
            print(f"  {pr:11s} {ro:8.0f} {rl:8.0f} {ro - rl:+7.0f} | {uo:6.0f} @{ro / max(uo, 1e-9):5.1f}   | {ul:6.0f} @{rl / max(ul, 1e-9):5.1f}")
        print(f"  {'revenue':11s} {'':8s} {'':8s} {tot:+7.0f}")
        sp = defaultdict(lambda: [0.0, 0.0])
        for x in G:
            for side, seat in ((0, s_of(x)), (1, 1 - s_of(x))):
                for k, v in x["daily"][seat][30]["spend"].items():
                    sp[k.split(":")[0] + (":" + k.split(":")[1] if k.startswith(("BUY_ANIMAL", "BUY_PRODUCT")) else "")][side] += v / n
        print("  spend (ours / leader / gap):", ", ".join(f"{k} {v[0]:.0f}/{v[1]:.0f} ({v[0] - v[1]:+.0f})" for k, v in
                                                     sorted(sp.items(), key=lambda kv: -abs(kv[1][0] - kv[1][1])) if abs(v[0] - v[1]) >= 50))
        line = []
        for dd in (5, 8, 10, 12, 15, 18, 21, 24, 27, 29):
            g = sum((x["daily"][s_of(x)][dd + 1]["money"] - x["daily"][1 - s_of(x)][dd + 1]["money"]) for x in G) / n
            line.append(f"d{dd} {g:+.0f}")
        print("  margin (ours - leader) at the end of day:", " | ".join(line))


if __name__ == "__main__":
    main()

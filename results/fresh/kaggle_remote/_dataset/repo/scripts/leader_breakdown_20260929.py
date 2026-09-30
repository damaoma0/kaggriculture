"""Where the margin goes against the recorded leaders (exact-credit lower bound, `leadersx_credit`: the leader plays its
real game). Final money = start + revenue - spending for both farms, so margin = (our revenue - leader revenue) -
(our spending - leader spending), split by product and by spending kind; plus units / average prices per product and
the margin by day. Arms are compared with the team the leader actually beat in the same recorded games (the control).

usage: leader_breakdown_20260929.py [--arms n18,v17g,mgt_ref] [--mode leadersx_credit]"""
import argparse
import glob
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
PRODUCTS = ["STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "WHEAT", "CARROT", "TOMATO", "FERTILIZER"]


def rows(d):
    out = {}
    for f in glob.glob(os.path.join(d, "*.json")):
        if f.endswith((".actions.json", ".spawns.json")):
            continue
        r = json.load(open(f))
        if isinstance(r, dict) and r.get("completed"):
            out[r["case"]["id"]] = r
    return out


def spend_kind(k):
    if k.startswith("BUY_ANIMAL"):
        return "animals"
    if k.startswith("BUY_SEED"):
        return "seeds"
    if k.startswith("BUY_PRODUCT"):
        return "buy " + k.split(":")[1].lower()
    if k.startswith("HIRE"):
        return "hires"
    if k.startswith("BUY_LAND"):
        return "land"
    return k.lower()


def side(r, who):
    """who: 'us' (the case seat) or 'lead' (the other seat); final-day ledgers"""
    s = r["case"]["seat"] if who == "us" else 1 - r["case"]["seat"]
    return r["daily"][s]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="n18,v17g,mgt_ref")
    ap.add_argument("--mode", default="leadersx_credit")
    a = ap.parse_args()
    ctl = rows(H / a.mode / "_controls")
    arms = a.arms.split(",")
    data = {x: rows(H / a.mode / x) for x in arms}
    data["real team"] = ctl
    for fam, label in (("dsm", "DSM"), ("mmpq", "MMPQ")):
        ids = sorted(k for k in ctl if f"-{fam}-" in k and all(k in data[x] for x in arms))
        n = len(ids)
        print(f"\n######## vs {label}: {n} recorded worlds (exact credit: the leader plays its real game)")
        cols = arms + ["real team"]
        # ---- margin by day
        print("margin by dawn of day " + "  ".join(f"{d:>7d}" for d in (6, 9, 12, 15, 18, 21, 24, 27)) + "     end")
        for x in cols:
            vals = []
            for d in (6, 9, 12, 15, 18, 21, 24, 27, 30):
                v = [side(data[x][k], "us")[min(d, 30)]["money"] - side(data[x][k], "lead")[min(d, 30)]["money"] for k in ids]
                vals.append(sum(v) / n)
            print(f"  {x:22s}" + "  ".join(f"{v:+7.0f}" for v in vals))
        # ---- decomposition of the final margin
        rev = {x: {"us": Counter(), "lead": Counter()} for x in cols}
        units = {x: {"us": Counter(), "lead": Counter()} for x in cols}
        spend = {x: {"us": Counter(), "lead": Counter()} for x in cols}
        for x in cols:
            for k in ids:
                for who in ("us", "lead"):
                    L = side(data[x][k], who)[-1]
                    for p, v in L["revenue"].items():
                        rev[x][who][p] += v / n
                    for p, v in L["sold_units"].items():
                        units[x][who][p] += v / n
                    for p, v in L["spend"].items():
                        spend[x][who][spend_kind(p)] += v / n
        print("\nrevenue gap by product (ours - leader's, per game)" + "".join(f"{x:>14s}" for x in cols))
        for p in PRODUCTS:
            print(f"  {p:46s}" + "".join(f"{rev[x]['us'][p] - rev[x]['lead'][p]:+14.0f}" for x in cols))
        kinds = sorted({kk for x in cols for who in ("us", "lead") for kk in spend[x][who]})
        print("spending gap by kind (ours - leader's; + = we spend more, costs margin)")
        for kk in kinds:
            print(f"  {kk:46s}" + "".join(f"{spend[x]['us'][kk] - spend[x]['lead'][kk]:+14.0f}" for x in cols))
        print(f"  {'= margin (revenue gap - spending gap)':46s}" + "".join(
            f"{sum(rev[x]['us'].values()) - sum(rev[x]['lead'].values()) - sum(spend[x]['us'].values()) + sum(spend[x]['lead'].values()):+14.0f}" for x in cols))
        # ---- units and prices
        print("\nunits sold / average price, ours | leader's")
        for p in PRODUCTS:
            line = f"  {p:12s}"
            for x in cols:
                u, ul = units[x]["us"][p], units[x]["lead"][p]
                pr = rev[x]["us"][p] / u if u else 0
                prl = rev[x]["lead"][p] / ul if ul else 0
                line += f"  {x[:8]:>8s} {u:5.0f}@{pr:5.0f} | {ul:5.0f}@{prl:5.0f}"
            print(line)


if __name__ == "__main__":
    main()

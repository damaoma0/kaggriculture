"""One day of a tpp smoke game (scripts/tpp_smoke_20260930.py) against DSM's own continuation of the same world
(user 2026-09-30: "Can we do day by day. Anything going wrong at day12?"): cash, revenue / sold units / spend by item,
ops and failed ops, sale hours and quotes of the front goods, the dusk state of pens and crops, and our executor's plan.

usage: tpp_day_20260930.py EP TAG DAY"""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "results/fresh/dsm4q_d9_20260930/games"
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def load(ep, key):
    return json.loads(gzip.open(G / f"d4q9-{ep}.{key}.game.json.gz", "rt", encoding="utf-8").read())


def board(g, t):
    return [g["tiles"][i] for i in g["frames"][t]["b"]]


def main():
    ep, tag, day = sys.argv[1], sys.argv[2], int(sys.argv[3])
    o, d = load(ep, f"tpp{tag}.p264"), load(ep, "dsm")
    s = o["seat"]
    A0, A1, B0, B1 = o["daily"][s][day], o["daily"][s][day + 1], d["daily"][s][day], d["daily"][s][day + 1]
    print(f"== world {ep}, day {day}: cash at dawn ours {A0['money']:.0f} | DSM {B0['money']:.0f}; "
          f"day's change ours {A1['money'] - A0['money']:+.0f} | DSM {B1['money'] - B0['money']:+.0f}")
    print("revenue (sold units) by good, ours | DSM:")
    for gd in GOODS:
        ra, rb = A1["revenue"].get(gd, 0) - A0["revenue"].get(gd, 0), B1["revenue"].get(gd, 0) - B0["revenue"].get(gd, 0)
        ua, ub = A1["sold_units"].get(gd, 0) - A0["sold_units"].get(gd, 0), B1["sold_units"].get(gd, 0) - B0["sold_units"].get(gd, 0)
        if ra or rb:
            print(f"   {gd:10s} {ra:6.0f} ({ua:3d}) | {rb:6.0f} ({ub:3d})   {ra - rb:+6.0f}")
    ks = sorted(set(A1["spend"]) | set(B1["spend"]))
    sp = [(k, A1["spend"].get(k, 0) - A0["spend"].get(k, 0), B1["spend"].get(k, 0) - B0["spend"].get(k, 0)) for k in ks]
    print("spend ours | DSM: " + ", ".join(f"{k} {a:.0f}|{b:.0f}" for k, a, b in sp if a or b))
    ph = lambda X0, X1, k: X1["physical"].get(k, 0) - X0["physical"].get(k, 0)  # noqa: E731
    ops = ("op:PLANT", "op:HARVEST", "op:WATER", "op:FEED", "op:CARE", "op:COLLECT_FERTILIZER", "op:FERTILIZE",
           "op:PLACE", "op:DIG", "op:PICKUP", "op:DROP", "moves", "op:PASS")
    print("ops ours | DSM: " + ", ".join(f"{k.replace('op:', '')} {ph(A0, A1, k)}|{ph(B0, B1, k)}" for k in ops))
    fails = {k.replace("no_effect:", ""): ph(A0, A1, k) for k in A1["physical"] if k.startswith("no_effect:") and ph(A0, A1, k)}
    print("failed ops ours:", fails, "| DSM:", {k.replace("no_effect:", ""): ph(B0, B1, k) for k in B1["physical"]
                                                 if k.startswith("no_effect:") and ph(B0, B1, k)})
    print("front-good sale orders by hour (units requested @ quote before the tick), ours | DSM:")
    for gd, gi in (("STRAWBERRY", 3), ("WOOL", 7), ("MILK", 6), ("MELON", 4), ("EGG", 5)):
        row = []
        for g in (o, d):
            hs = []
            for t in range(24 * day, 24 * day + 24):
                fr = g["frames"][t]
                for m in (fr.get("a") or {}).get("market") or []:
                    if m and m[0] == "SELL" and m[1] == gd:
                        hs.append(f"h{t % 24}:{m[2]}@{fr['p'][gi]}")
            row.append(" ".join(hs) or "-")
        print(f"   {gd:10s} {row[0]}  |  {row[1]}")
    print("dusk state (hour 23), ours | DSM:")
    stats = []
    for g in (o, d):
        b = board(g, 24 * day + 23)
        an = [t for t in b if isinstance(t, dict) and t.get("animal")]
        pl = [t for t in b if isinstance(t, dict) and t.get("kind") == "PLANT"]
        c = Counter()
        c["animals"] = len(an)
        c["fed"] = sum(1 for t in an if t.get("fed_today"))
        c["cared"] = sum(1 for t in an if t.get("cared_today"))
        c["fed+cared"] = sum(1 for t in an if t.get("fed_today") and t.get("cared_today"))
        c["held products"] = sum(int(t.get("yield_units", 0) or 0) for t in an)
        c["bank"] = sum(int(t.get("pending_care_bonus", 0) or 0) for t in an)
        c["plants"] = len(pl)
        c["watered"] = sum(1 for t in pl if t.get("watered_today"))
        c["fertilized"] = sum(1 for t in pl if int(t.get("fertilized_until_day", -1)) >= day)
        c["units on strawberry/tomato"] = sum(int(t.get("yield_units", 0) or 0) for t in pl if t.get("crop") in ("STRAWBERRY", "TOMATO"))
        c["empty"] = sum(1 for t in b if t is None)
        c["weeds"] = sum(1 for t in b if isinstance(t, dict) and t.get("kind") == "WEED")
        stats.append(c)
    for k in stats[0]:
        print(f"   {k:28s} {stats[0][k]:4d} | {stats[1][k]:4d}")
    x = (o.get("diag") or {}).get(str(day))
    if x:
        print(f"our plan: jobs M {x['M']} N {x['N']} S {x['S']} h, units {x['units']}, bring-in legs {x['legs']}, walk {x['walk']}, "
              f"planned cuts N {x['cut_N']} S {x['cut_S']}, DSM plan {x['plan']}")
        print("executor log:", dict(sorted(x["log"].items())))


if __name__ == "__main__":
    main()

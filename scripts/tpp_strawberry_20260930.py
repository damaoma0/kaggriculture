"""Strawberries in a tpp smoke game vs DSM's own continuation, night by night (user 2026-09-30: "Let's find what's wrong
with strawberry first"). Per day d: strawberry plants standing / producing tonight; of those producing, watered and
fertilized at dusk (a fertilized plant adds 2 on a watered production day, else 1; engine _daily_refresh_plants);
units produced tonight (next dawn yield - dusk yield on the same plant) and units lost to the 4-unit cap; plants died
(dry -> weed) or decayed; units harvested today and when (hours); units sold today.

usage: tpp_strawberry_20260930.py EP TAG"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "results/fresh/dsm4q_d9_20260930/games"
FIRST, IV, MAXY = 10, 2, 4


def load(ep, key):
    return json.loads(gzip.open(G / f"d4q9-{ep}.{key}.game.json.gz", "rt", encoding="utf-8").read())


def board(g, t):
    return [g["tiles"][i] for i in g["frames"][t]["b"]]


def is_sb(t):
    return isinstance(t, dict) and t.get("crop") == "STRAWBERRY"


def producing(t, d):
    dsf = d + 1 - int(t["planted_day"]) - FIRST
    return dsf >= 0 and dsf % IV == 0 and dsf // IV + 1 <= MAXY


def day_stats(g, d):
    s = g["seat"]
    dawn, dusk, nxt = board(g, 24 * d), board(g, 24 * d + 23), board(g, 24 * d + 24)
    out = dict(standing=0, prod=0, prod_watered=0, prod_fert=0, prod_fert_watered=0, made=0, capped=0, died=0,
               harvested=0, hours=[], sold=0)
    for i in range(100):
        a, b, c = dawn[i], dusk[i], nxt[i]
        if is_sb(b):
            out["standing"] += 1
            if producing(b, d):
                out["prod"] += 1
                w, f = bool(b.get("watered_today")), int(b.get("fertilized_until_day", -1)) >= d
                out["prod_watered"] += w
                out["prod_fert"] += f
                out["prod_fert_watered"] += w and f
                add = 2 if (w and f) else 1
                yu = int(b.get("yield_units", 0) or 0)
                out["capped"] += max(0, yu + add - MAXY)
            if is_sb(c) and c.get("planted_day") == b.get("planted_day"):
                out["made"] += max(0, int(c.get("yield_units", 0) or 0) - int(b.get("yield_units", 0) or 0))
            elif isinstance(c, dict) and c.get("kind") == "WEED":
                out["died"] += 1
    # harvests during the day: yield drops on the same plant between consecutive frames
    for h in range(24):
        b0, b1 = board(g, 24 * d + h), board(g, 24 * d + h + 1) if h < 23 else None
        if b1 is None:
            break
        for i in range(100):
            x, y = b0[i], b1[i]
            if is_sb(x) and (not is_sb(y) or y.get("planted_day") == x.get("planted_day")):
                drop = int(x.get("yield_units", 0) or 0) - (int(y.get("yield_units", 0) or 0) if is_sb(y) else 0)
                if drop > 0:
                    out["harvested"] += drop
                    out["hours"].append(h)
    D0, D1 = g["daily"][s][d], g["daily"][s][d + 1]
    out["sold"] = D1["sold_units"].get("STRAWBERRY", 0) - D0["sold_units"].get("STRAWBERRY", 0)
    out["rev"] = D1["revenue"].get("STRAWBERRY", 0) - D0["revenue"].get("STRAWBERRY", 0)
    return out


def main():
    ep, tag = sys.argv[1], sys.argv[2]
    o, dsm = load(ep, f"tpp{tag}.p264"), load(ep, "dsm")
    tot = [dict(), dict()]
    print("day | standing | producing tonight (watered / fertilized / fert+watered) | made tonight (lost to cap) | died | "
          "harvested today (median hour) | sold today ($), ours || DSM")
    for d in range(11, 29):
        row = []
        for k, g in enumerate((o, dsm)):
            x = day_stats(g, d)
            for key, v in x.items():
                if isinstance(v, (int, float)):
                    tot[k][key] = tot[k].get(key, 0) + v
            hs = sorted(x["hours"])
            med = hs[len(hs) // 2] if hs else "-"
            row.append(f"{x['standing']:2d} | {x['prod']:2d} ({x['prod_watered']:2d}/{x['prod_fert']:2d}/{x['prod_fert_watered']:2d}) | "
                       f"{x['made']:2d} ({x['capped']}) | {x['died']} | {x['harvested']:2d} (h{med}) | {x['sold']:2d} (${x['rev']:.0f})")
        print(f" {d:2d} | {row[0]}  ||  {row[1]}")
    print("totals days 11-28, ours | DSM: " + ", ".join(f"{k} {tot[0].get(k, 0):.0f}|{tot[1].get(k, 0):.0f}" for k in tot[0]))


if __name__ == "__main__":
    main()

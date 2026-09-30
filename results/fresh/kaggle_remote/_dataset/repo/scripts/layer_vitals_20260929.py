"""Which layer failed - semantics (the day's counts), tiling (the compiler's tile plan) or execution (what the executor
did with it) - for our arm against the recorded leader in one or more harness games (user 2026-09-29).

For every product p: revenue = tile-days x output per tile-day x average price (tile-days = crop / animal hours on the
board / 24; animals: milk <- cows, wool <- sheep, eggs <- geese). Ours - leader is split shift-share:
  tile-days   (TD_us - TD_ld) x Y_ld x P_ld   - how much of it we held; itself split into
      plan      (planned TD - TD_ld) x Y_ld x P_ld   the tiler's planned end-of-day occupancy (semantics + tiling)
      achieved  (TD_us - planned TD) x Y_ld x P_ld   what the executor realised of that plan
  yield       TD_us x (Y_us - Y_ld) x P_ld          output per tile-day (execution: water / feed / care / harvest timing)
  price       TD_us x Y_us x (P_us - P_ld)          what each unit sold for (sale timing / market)
and unsold stock is ignored (sold units are used for Y). Plus the execution vitals of both farms: unit-hours working /
moving / idle, ops per unit-hour, feeds and cares per animal-day, waterings per plant-day, failed commands; and the
tiler's capacity clips and the semantic-vs-tiled count differences.

usage: layer_vitals_20260929.py ARM_DIR [CASE ...]   (ARM_DIR holds <case>.json; default: every case in it)"""
import json
import sys
from collections import Counter
from pathlib import Path

SOURCE = {"MILK": "animal:COW", "WOOL": "animal:SHEEP", "EGG": "animal:GOOSE", "STRAWBERRY": "crop:STRAWBERRY",
          "MELON": "crop:MELON", "WHEAT": "crop:WHEAT", "CARROT": "crop:CARROT", "TOMATO": "crop:TOMATO"}
PLAN_KEY = {"MILK": ("animals", "COW"), "WOOL": ("animals", "SHEEP"), "EGG": ("animals", "GOOSE"),
            "STRAWBERRY": ("crops", "STRAWBERRY"), "MELON": ("crops", "MELON"), "WHEAT": ("crops", "WHEAT"),
            "CARROT": ("crops", "CARROT"), "TOMATO": ("crops", "TOMATO")}


def td(D, key, d0=6):
    return sum(D[d]["tile_hours"].get(key, 0) - D[d - 1]["tile_hours"].get(key, 0) for d in range(d0 + 1, 31)) / 24


def planned_td(diags, cat, kind, d0=6):
    tot = 0.0
    for x in diags:
        if x.get("phase") == "semantic" and x["day"] >= d0:
            occ = ((x.get("realized_plan") or {}).get("end_occupancy_counts") or {}).get(cat) or {}
            tot += occ.get(kind, 0)
    return tot


def vitals(D, a=6, b=30):
    p0, p1 = D[a]["physical"], D[b]["physical"]
    g = lambda k: p1.get(k, 0) - p0.get(k, 0)  # noqa: E731
    n = max(1, g("commands"))
    moves = sum(g(k) for k in ("op:NORTH", "op:SOUTH", "op:EAST", "op:WEST"))
    work = n - moves - g("op:PASS")
    ad = sum(td(D, k, a) for k in ("animal:COW", "animal:SHEEP", "animal:GOOSE"))
    pd = sum(td(D, k, a) for k in ("crop:STRAWBERRY", "crop:MELON", "crop:WHEAT", "crop:CARROT", "crop:TOMATO"))
    return dict(unit_hours=n, work=work / n, move=moves / n, idle=g("op:PASS") / n, failed=g("no_effect"),
                feed_per_animal_day=g("op:FEED") / max(1, ad), care_per_animal_day=g("op:CARE") / max(1, ad),
                water_per_plant_day=g("op:WATER") / max(1, pd), harvests=g("op:HARVEST"), fertilize=g("op:FERTILIZE"))


def one(path):
    r = json.loads(Path(path).read_text())
    s = r["case"]["seat"]
    us, ld = r["daily"][s], r["daily"][1 - s]
    diags = (r.get("final_diagnostics") or {}).get(str(s)) or []
    rows, tot = {}, Counter()
    for p, key in SOURCE.items():
        TDu, TDl = td(us, key), td(ld, key)
        Uu = us[-1]["sold_units"].get(p, 0) - us[6]["sold_units"].get(p, 0)
        Ul = ld[-1]["sold_units"].get(p, 0) - ld[6]["sold_units"].get(p, 0)
        Ru = us[-1]["revenue"].get(p, 0) - us[6]["revenue"].get(p, 0)
        Rl = ld[-1]["revenue"].get(p, 0) - ld[6]["revenue"].get(p, 0)
        Yu, Yl = (Uu / TDu if TDu else 0), (Ul / TDl if TDl else 0)
        Pu, Pl = (Ru / Uu if Uu else 0), (Rl / Ul if Ul else 0)
        TDp = planned_td(diags, *PLAN_KEY[p])
        row = dict(gap=Ru - Rl, plan=(TDp - TDl) * Yl * Pl, achieved=(TDu - TDp) * Yl * Pl, yield_=TDu * (Yu - Yl) * Pl,
                   price=TDu * Yu * (Pu - Pl), TD=(TDu, TDp, TDl), Y=(Yu, Yl), P=(Pu, Pl), U=(Uu, Ul))
        rows[p] = row
        for k in ("gap", "plan", "achieved", "yield_", "price"):
            tot[k] += row[k]
    clips = sum(len(x.get("capacity_adjustments") or []) for x in diags if x.get("phase") == "semantic" and x["day"] == 6)
    sem_vs_tile = Counter()
    for x in diags:
        if x.get("phase") != "semantic":
            continue
        pr, rp = x.get("proposal") or {}, x.get("realized_plan") or {}
        for fld in ("plant_counts", "animal_add_counts"):
            for k in set(pr.get(fld) or {}) | set(rp.get(fld) or {}):
                sem_vs_tile[k] += int((rp.get(fld) or {}).get(k, 0)) - int((pr.get(fld) or {}).get(k, 0))
    return r, rows, tot, vitals(us), vitals(ld), clips, sem_vs_tile


def main():
    arm = Path(sys.argv[1])
    cases = sys.argv[2:] or sorted(p.stem for p in arm.glob("*.json") if not p.name.endswith((".actions.json", "summary.json")))
    T, V = Counter(), {"us": Counter(), "ld": Counter()}
    P = {p: Counter() for p in SOURCE}
    for c in cases:
        r, rows, tot, vu, vl, clips, svt = one(arm / f"{c}.json")
        print(f"\n=== {arm.name} / {c}: margin {r['margin']:+.0f} (days 6-29 product revenue gap {tot['gap']:+.0f})")
        print(f"  {'product':11s} {'gap':>7s} = {'plan':>7s} + {'achieved':>8s} + {'yield':>7s} + {'price':>7s} | tile-days us/plan/leader | units/tile-day us|ld | price us|ld")
        for p, x in rows.items():
            print(f"  {p:11s} {x['gap']:+7.0f} = {x['plan']:+7.0f} + {x['achieved']:+8.0f} + {x['yield_']:+7.0f} + {x['price']:+7.0f} | "
                  f"{x['TD'][0]:5.0f} / {x['TD'][1]:5.0f} / {x['TD'][2]:5.0f} | {x['Y'][0]:.2f} | {x['Y'][1]:.2f} | {x['P'][0]:4.0f} | {x['P'][1]:4.0f}")
            for k in ("gap", "plan", "achieved", "yield_", "price"):
                P[p][k] += x[k] / len(cases)
        print(f"  {'total':11s} {tot['gap']:+7.0f} = {tot['plan']:+7.0f} + {tot['achieved']:+8.0f} + {tot['yield_']:+7.0f} + {tot['price']:+7.0f}")
        print("  vitals days 6-29 (us | leader): " + ", ".join(
            f"{k} {vu[k]:.2f} | {vl[k]:.2f}" if isinstance(vu[k], float) else f"{k} {vu[k]} | {vl[k]}" for k in vu))
        print(f"  tiler vs semantic counts (tiled - proposed, days 6-29): {dict(svt)}; capacity clips {clips}")
        for k, v in tot.items():
            T[k] += v / len(cases)
        for k, v in vu.items():
            V["us"][k] += v / len(cases)
        for k, v in vl.items():
            V["ld"][k] += v / len(cases)
    if len(cases) > 1:
        print(f"\n######## mean over {len(cases)} games")
        for p, x in P.items():
            print(f"  {p:11s} {x['gap']:+7.0f} = plan {x['plan']:+7.0f} + achieved {x['achieved']:+7.0f} + yield {x['yield_']:+7.0f} + price {x['price']:+7.0f}")
        print(f"  {'total':11s} {T['gap']:+7.0f} = plan {T['plan']:+7.0f} + achieved {T['achieved']:+7.0f} + yield {T['yield_']:+7.0f} + price {T['price']:+7.0f}")
        print("  vitals (us | leader): " + ", ".join(f"{k} {V['us'][k]:.2f} | {V['ld'][k]:.2f}" for k in V["us"]))


if __name__ == "__main__":
    main()

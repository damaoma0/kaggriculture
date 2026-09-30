"""Day-11+ wheat gap on the dsm4q day-11 handoff test bed (2026-09-30): the arm (our stack from day 11) vs the DSM control
(DSM's own commands all game) on the same DSM-new 4-quadrant farm. Reads only finished harness results
(results/fresh/retrain4q_20260930/dsm4q_p264/<arm>/<case>.json and _controls/<case>.json): the dawn farm of every day
(diagnostics[seat][d].current_observation.own_farm), the daily ledgers (tile-hours, ops, produced / sold units, spend)
and, for the arm, the planner's diagnostics (requested plantings, tiler capacity clips).

Per-tile wheat cycles come from dawn-to-dawn transitions: a WHEAT plant (tile, planted_day p) present at dawn d and gone at
dawn d+1 was harvested (or lost) on day d at age d - p; the tile's occupant at dawn d+1 tells whether it was replanted
the same day (planted_day == d) and with what; fertilized_until_day tells whether the age-2 fertilize happened.

usage: wheat_gap_diag_20260930.py [--arm n18rc255d] [--cases dsm4q-115561922,...] [--json OUT] [--panel DIR]"""
import argparse
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "results/fresh/retrain4q_20260930/dsm4q_p264"
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
CUM = [0]
_a, _b = 1, 1
for _ in range(25):
    CUM.append(CUM[-1] + _a)
    _a, _b = _b, _a + _b


def hires_from_cost(c):
    c = int(round(c))
    return min(range(len(CUM)), key=lambda n: abs(CUM[n] - c))


def dawn_tiles(g, seat, d):
    return [t for row in g["diagnostics"][seat][d]["current_observation"]["own_farm"]["tiles"] for t in row]


def occupant(t):
    if t == "LOCKED":
        return "L"
    if not isinstance(t, dict):
        return "."
    if t.get("kind") == "PLANT":
        return t["crop"]
    if t.get("kind") == "WEED":
        return "weed"
    return t.get("animal") or t.get("kind")


def analyse(g, arm_diag=None):
    s = int(g["case"]["seat"])
    D = g["daily"][s]
    days = {}
    cycles = []                                    # finished wheat plants (planted any day, harvested day >= 11)
    for d in range(11, 30):
        b0 = dawn_tiles(g, s, d)
        b1 = dawn_tiles(g, s, d + 1) if d + 1 < 30 else None
        occ = Counter(occupant(t) for t in b0)
        row = dict(day=d, dawn={k: occ.get(k, 0) for k in CROPS + (".", "weed")},
                   dawn_animals=sum(occ.get(k, 0) for k in ("COW", "SHEEP", "GOOSE")),
                   wheat_tile_days=round((D[d + 1]["tile_hours"].get("crop:WHEAT", 0) - D[d]["tile_hours"].get("crop:WHEAT", 0)) / 24, 1),
                   empty_tile_days=round((D[d + 1]["tile_hours"].get("empty", 0) - D[d]["tile_hours"].get("empty", 0)) / 24, 1),
                   weed_tile_days=round((D[d + 1]["tile_hours"].get("weed", 0) - D[d]["tile_hours"].get("weed", 0)) / 24, 1),
                   produced_wheat=D[d + 1]["physical"].get("produced:WHEAT", 0) - D[d]["physical"].get("produced:WHEAT", 0),
                   sold_wheat=D[d + 1]["sold_units"].get("WHEAT", 0) - D[d]["sold_units"].get("WHEAT", 0),
                   bought_wheat_coins=round(D[d + 1]["spend"].get("BUY_PRODUCT:WHEAT", 0) - D[d]["spend"].get("BUY_PRODUCT:WHEAT", 0)),
                   wheat_seed_coins=round(D[d + 1]["spend"].get("BUY_SEED:WHEAT", 0) - D[d]["spend"].get("BUY_SEED:WHEAT", 0)),
                   feeds=D[d + 1]["physical"].get("op:FEED", 0) - D[d]["physical"].get("op:FEED", 0),
                   passes=D[d + 1]["physical"].get("op:PASS", 0) - D[d]["physical"].get("op:PASS", 0),
                   waters=D[d + 1]["physical"].get("op:WATER", 0) - D[d]["physical"].get("op:WATER", 0),
                   ferts=D[d + 1]["physical"].get("op:FERTILIZE", 0) - D[d]["physical"].get("op:FERTILIZE", 0),
                   hands=hires_from_cost(D[d + 1]["spend"].get("HIRE", 0) - D[d]["spend"].get("HIRE", 0)))
        planted = Counter()
        harvested = []
        if b1 is not None:
            for i in range(100):
                t0, t1 = b0[i], b1[i]
                if isinstance(t1, dict) and t1.get("kind") == "PLANT" and int(t1.get("planted_day", -1)) == d:
                    planted[t1["crop"]] += 1
                if isinstance(t0, dict) and t0.get("kind") == "PLANT" and t0.get("crop") == "WHEAT":
                    p = int(t0["planted_day"])
                    same = (isinstance(t1, dict) and t1.get("kind") == "PLANT" and t1.get("crop") == "WHEAT"
                            and int(t1.get("planted_day", -1)) == p)
                    if same:
                        continue
                    nxt = occupant(t1)
                    repl = isinstance(t1, dict) and t1.get("kind") == "PLANT" and int(t1.get("planted_day", -1)) == d
                    # fertilized at age 2: this plant's fertilized_until_day covered day p+2 at some later dawn
                    fert2 = False
                    for dd in range(max(p + 1, 11), d + 1):
                        tt = dawn_tiles(g, s, dd)[i]
                        if isinstance(tt, dict) and tt.get("crop") == "WHEAT" and int(tt.get("planted_day", -1)) == p:
                            if int(tt.get("fertilized_until_day", -1) or -1) >= p + 2:
                                fert2 = True
                    if b1 is not None and d + 1 < 30:
                        tt = b1[i]
                    harvested.append(dict(tile=i, planted=p, age=d - p, dawn_units=int(t0.get("yield_units", 0)),
                                          replant=nxt if repl else None, next=nxt, fert2=fert2))
        row["planted"] = dict(planted)
        row["wheat_gone"] = len(harvested)
        row["wheat_gone_ages"] = dict(Counter(h["age"] for h in harvested))
        row["replant_same_day"] = dict(Counter(h["replant"] for h in harvested if h["replant"]))
        row["gone_to_empty"] = sum(1 for h in harvested if h["next"] in (".", "weed"))
        row["fert2_of_gone"] = sum(1 for h in harvested if h["fert2"])
        cycles += [dict(h, day=d) for h in harvested]
        if arm_diag is not None:
            r = next((x for x in arm_diag if x.get("day") == d and x.get("phase") == "semantic"), None)
            if r:
                row["plan_plants"] = (r.get("proposal") or {}).get("plant_counts")
                row["realized_plants"] = (r.get("realized_plan") or {}).get("plant_counts")
                row["clips"] = [(w.get("crop") or w.get("species"), w.get("requested"), w.get("actual"))
                                for w in (r.get("capacity_adjustments") or []) if int(w.get("day", -1)) == d]
        days[d] = row
    return days, cycles


def summarise(name, days, cycles):
    ages = Counter(c["age"] for c in cycles)
    repl = Counter(c["replant"] for c in cycles if c["replant"])
    n = len(cycles)
    out = dict(name=name, wheat_gone=n, ages=dict(sorted(ages.items())),
               replant_same_day_share=round(sum(repl.values()) / max(1, n), 3), replant_same_day=dict(repl),
               to_empty=sum(1 for c in cycles if c["next"] in (".", "weed")),
               fert2_share=round(sum(1 for c in cycles if c["fert2"]) / max(1, n), 3),
               wheat_planted=sum(r["planted"].get("WHEAT", 0) for r in days.values()),
               planted=dict(sum((Counter(r["planted"]) for r in days.values()), Counter())),
               produced=sum(r["produced_wheat"] for r in days.values()),
               sold=sum(r["sold_wheat"] for r in days.values()),
               feeds=sum(r["feeds"] for r in days.values()),
               bought_coins=sum(r["bought_wheat_coins"] for r in days.values()),
               wheat_tile_days=round(sum(r["wheat_tile_days"] for r in days.values()), 1),
               empty_tile_days=round(sum(r["empty_tile_days"] for r in days.values()), 1),
               weed_tile_days=round(sum(r["weed_tile_days"] for r in days.values()), 1),
               passes=sum(r["passes"] for r in days.values()), waters=sum(r["waters"] for r in days.values()),
               ferts=sum(r["ferts"] for r in days.values()), hands=sum(r["hands"] for r in days.values()),
               units_per_wheat_tile_day=round(sum(r["produced_wheat"] for r in days.values())
                                              / max(1e-9, sum(r["wheat_tile_days"] for r in days.values())), 3),
               dawn_d12={k: days[12]["dawn"][k] for k in ("WHEAT", "TOMATO", "STRAWBERRY", "CARROT", "MELON", ".")},
               dawn_d16={k: days[16]["dawn"][k] for k in ("WHEAT", "TOMATO", "STRAWBERRY", "CARROT", "MELON", ".")},
               dawn_d22={k: days[22]["dawn"][k] for k in ("WHEAT", "TOMATO", "STRAWBERRY", "CARROT", "MELON", ".")})
    return out


def main():
    global P
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="n18rc255d")
    ap.add_argument("--cases")
    ap.add_argument("--json")
    ap.add_argument("--days", action="store_true", help="print the per-day table")
    ap.add_argument("--panel", default=str(P.relative_to(ROOT)), help="panel folder (default the 6-world dsm4q_p264)")
    a = ap.parse_args()
    P = ROOT / a.panel
    cases = a.cases.split(",") if a.cases else sorted(p.stem for p in (P / "_controls").glob("dsm4q-*.json")
                                                    if not p.stem.endswith(("actions", "spawns")))
    report = {}
    for c in cases:
        ctl = json.loads((P / "_controls" / f"{c}.json").read_text())
        arm = json.loads((P / a.arm / f"{c}.json").read_text())
        s = str(arm["case"]["seat"])
        dd, dc = analyse(ctl)
        ad, ac = analyse(arm, arm["final_diagnostics"][s])
        sd, sa = summarise("DSM", dd, dc), summarise(a.arm, ad, ac)
        report[c] = dict(dsm=sd, arm=sa, dsm_days=dd, arm_days=ad)
        print(f"== {c} (opp {ctl['case']['opponent']}): margin DSM {ctl['margin']:+.0f} / {a.arm} {arm['margin']:+.0f}")
        for k in ("wheat_planted", "wheat_gone", "ages", "fert2_share", "replant_same_day_share", "replant_same_day", "to_empty",
                  "produced", "units_per_wheat_tile_day", "sold", "feeds", "bought_coins", "wheat_tile_days",
                  "empty_tile_days", "weed_tile_days", "hands", "passes", "waters", "ferts", "planted", "dawn_d12",
                  "dawn_d16", "dawn_d22"):
            print(f"   {k:26s} DSM {sd[k]!s:60.60s} | ours {sa[k]!s:.60s}")
        if a.days:
            print("   day | DSM: dawn WH TO ST CA . | planted | wheat gone (ages) repl | prod sold feed | hands pass || ours: same | plan | clips")
            for d in range(11, 29):
                x, y = dd[d], ad[d]
                f = lambda r: (f"{r['dawn']['WHEAT']:2d} {r['dawn']['TOMATO']:2d} {r['dawn']['STRAWBERRY']:2d} {r['dawn']['CARROT']:2d} "
                               f"{r['dawn']['.'] + r['dawn']['weed']:2d} | {r['planted']} | {r['wheat_gone']} {r['wheat_gone_ages']} "
                               f"{sum(r['replant_same_day'].values())} | {r['produced_wheat']} {r['sold_wheat']} {r['feeds']} | {r['hands']} {r['passes']}")
                print(f"   {d:2d} | {f(x)} || {f(y)} | {y.get('plan_plants')} | {y.get('clips')}")
    keys = ("wheat_planted", "wheat_gone", "produced", "sold", "feeds", "wheat_tile_days", "empty_tile_days", "hands", "passes",
            "fert2_share", "replant_same_day_share", "units_per_wheat_tile_day")
    print("== medians over worlds (DSM | ours)")
    for k in keys:
        xs = [report[c]["dsm"][k] for c in cases]
        ys = [report[c]["arm"][k] for c in cases]
        print(f"   {k:26s} {st.median(xs):8.2f} | {st.median(ys):8.2f}")
    if a.json:
        Path(a.json).write_text(json.dumps(report, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()

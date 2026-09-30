"""Smoke comparison for the router4q arms (2026-09-30): frozen-harness results of b2b games (dsm3q worlds) and the ladder
game vs matu997, per arm, against n18rc223d.

Per game (our seat): cash, opponent cash, margin; day of the 3rd / 4th quadrant (purchase day = first dawn owning it - 1);
empty tiles a day on days 8-14 (tile-hours / 24, locked tiles excluded) and weeds; crop tile-days by crop (whole game and
days 11-29); hires by day (from the HIRE spend: cumulative fib costs are unique); land / seed / animal spend; per-product
revenue ours vs the opponent; days 0-10 requested vs executed seed / animal / land purchases (actions file vs spend); the
router trace (MGT_TRACE_DIR files) when present.

usage: router4q_smoke_report_20260930.py --arms n18rc223d,n18rc270d,... [--traces DIR] [--json OUT]"""
import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
GAMES = {"b2b-114393058": "b2b/dsm3q-114393058.{arm}.p0.result.json",
         "b2b-114514221": "b2b/dsm3q-114514221.{arm}.p0.result.json",
         "lad-115287820": "livex_credit/{arm}/lad-115287820.json"}
SEED = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def fib_counts():
    out, a, b, s = {0: 0}, 1, 1, 0
    for n in range(1, 60):
        s += a
        out[s] = n
        a, b = b, a + b
    return out


FIBSUM = fib_counts()


def hires_from_spend(coins):
    return FIBSUM.get(int(round(coins)))


def game_stats(r, acts=None):
    s = int(r["case"]["seat"])
    D, O = r["daily"][s], r["daily"][1 - s]
    out = dict(cash=r["cash"], opp=r["opponent_cash"], margin=r["margin"], eligible=r.get("eligible"),
               overage=round(r["measured_overage_used"][s], 1))
    q = []
    for e in r["diagnostics"][s]:
        f = e.get("farm") or {}
        q.append(len(f.get("unlocked_quadrants") or []))
    out["quadrants_by_dawn"] = q[:13]
    out["q2_day"] = next((d - 1 for d, n in enumerate(q) if n >= 2), None)
    out["q3_day"] = next((d - 1 for d, n in enumerate(q) if n >= 3), None)
    out["q4_day"] = next((d - 1 for d, n in enumerate(q) if n >= 4), None)

    def th(d, key):
        a, b = D[d]["tile_hours"], D[d + 1]["tile_hours"]
        return (b.get(key, 0) - a.get(key, 0)) / 24.0

    out["empty_d8_14"] = [round(th(d, "empty"), 1) for d in range(8, 15)]
    out["weed_d8_14"] = [round(th(d, "weed"), 1) for d in range(8, 15)]
    out["empty_d11"] = round(th(11, "empty"), 1)
    crops = Counter()
    crops_late = Counter()
    for d in range(30):
        for k in set(D[d + 1]["tile_hours"]) | set(D[d]["tile_hours"]):
            if k.startswith("crop:") or k.startswith("animal:"):
                v = th(d, k)
                crops[k] += v
                if d >= 11:
                    crops_late[k] += v
    out["tile_days"] = {k: round(v) for k, v in sorted(crops.items())}
    out["tile_days_d11_29"] = {k: round(v) for k, v in sorted(crops_late.items())}
    out["crop_tile_days"] = round(sum(v for k, v in crops.items() if k.startswith("crop:")))
    out["crop_tile_days_d11_29"] = round(sum(v for k, v in crops_late.items() if k.startswith("crop:")))
    hires = []
    for d in range(30):
        c = D[d + 1]["spend"].get("HIRE", 0) - D[d]["spend"].get("HIRE", 0)
        hires.append(hires_from_spend(c))
    out["hires_by_day"] = hires
    out["hires_total"] = sum(h for h in hires if h is not None)
    out["hires_d0_10"] = sum(h for h in hires[:11] if h is not None)
    out["hire_spend"] = round(D[30]["spend"].get("HIRE", 0))
    sp = D[30]["spend"]
    out["land_spend"] = round(sp.get("BUY_LAND", 0))
    out["seed_spend"] = {k.split(":")[1]: round(v) for k, v in sp.items() if k.startswith("BUY_SEED")}
    out["animal_spend"] = {k.split(":")[1]: round(v) for k, v in sp.items() if k.startswith("BUY_ANIMAL")}
    out["wheat_buy_spend"] = round(sp.get("BUY_PRODUCT:WHEAT", 0))
    out["revenue"] = {p: round(D[30]["revenue"].get(p, 0)) for p in PRODUCTS}
    out["opp_revenue"] = {p: round(O[30]["revenue"].get(p, 0)) for p in PRODUCTS}
    out["cash_d6_d11_d12"] = [D[6]["money"], D[11]["money"], D[12]["money"]]
    if acts is not None:
        req = Counter()
        for t in range(min(264, len(acts[s]))):
            a = acts[s][t] or {}
            for o in (a.get("market") or [])[:10]:
                if not o:
                    continue
                if o[0] == "BUY_SEED" and len(o) > 2:
                    req["seed_coins"] += SEED.get(o[1], 0) * int(o[2])
                elif o[0] == "BUY_ANIMAL" and len(o) > 2:
                    req["animal_coins"] += ANIMAL.get(o[1], 0) * int(o[2])
                elif o[0] == "BUY_LAND":
                    req["land_orders"] += 1
                elif o[0] == "HIRE":
                    req["hire_orders"] += 1
        s11 = D[11]["spend"]
        out["d0_10_requested"] = dict(req)
        out["d0_10_executed"] = dict(seed_coins=round(sum(v for k, v in s11.items() if k.startswith("BUY_SEED"))),
                                     animal_coins=round(sum(v for k, v in s11.items() if k.startswith("BUY_ANIMAL"))),
                                     land_coins=round(s11.get("BUY_LAND", 0)), hires=out["hires_d0_10"])
    return out


def load(arm, game):
    p = H / GAMES[game].format(arm=arm)
    if not p.exists():
        return None
    r = json.loads(p.read_text(encoding="utf-8"))
    ap = p.with_suffix(".actions.json")
    acts = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else None
    return game_stats(r, acts) if r.get("completed") else dict(error=(r.get("error") or "")[-300:])


def traces(d):
    out = {}
    if not d:
        return out
    for p in sorted(Path(d).glob("*/trace_*.json")):
        t = json.loads(p.read_text())
        out[p.parent.name] = dict(switches=t["report"].get("switches"), history=[[h[0], h[1], h[3]] for h in t["history"]],
                                  land_retry=t["report"].get("land_retry"), land_hold=t["report"].get("land_hold"),
                                  land_errors=t["report"].get("land_errors"), router_errors=t["report"].get("router_errors"),
                                  last_step=t["step"], ntapes=t["ntapes"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--traces")
    ap.add_argument("--json")
    ap.add_argument("--dsm4q", action="store_true", help="also the dsm4q no-prefix panel table")
    ap.add_argument("--dsm4q-ref", default="n18rc223d,n18rc255d", help="retrain4q p264 arms shown for reference")
    a = ap.parse_args()
    arms = a.arms.split(",")
    res = {arm: {g: load(arm, g) for g in GAMES} for arm in arms}
    tr = traces(a.traces)
    print("| arm | game | cash | opp | margin | vs n18rc223d | q2/q3/q4 day | empty tiles d8..14 | crop tile-days (d11-29) | hires d0-10 / total | land spend | overage s |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    base = res.get("n18rc223d", {})
    for arm in arms:
        for g in GAMES:
            x = res[arm][g]
            if x is None:
                continue
            if "error" in x:
                print(f"| {arm} | {g} | ERROR {x['error'][:80]} |")
                continue
            b = (base.get(g) or {}).get("margin")
            dm = "" if b is None or arm == "n18rc223d" else f"{x['margin'] - b:+,.0f}"
            print(f"| {arm} | {g} | {x['cash']:,.0f} | {x['opp']:,.0f} | {x['margin']:+,.0f} | {dm} | {x['q2_day']}/{x['q3_day']}/{x['q4_day']} | "
                  f"{' '.join(str(round(v)) for v in x['empty_d8_14'])} | {x['crop_tile_days']} ({x['crop_tile_days_d11_29']}) | "
                  f"{x['hires_d0_10']} / {x['hires_total']} | {x['land_spend']:,} | {x['overage']} |")
    print()
    print("| arm | game | revenue ours - opp by product (WH CA TO ST ME EGG MILK WOOL FERT) | total ours / opp |")
    print("|---|---|---|---|")
    for arm in arms:
        for g in GAMES:
            x = res[arm][g]
            if not x or "error" in x:
                continue
            diffs = " ".join(f"{x['revenue'][p] - x['opp_revenue'][p]:+,}" for p in PRODUCTS)
            print(f"| {arm} | {g} | {diffs} | {sum(x['revenue'].values()):,} / {sum(x['opp_revenue'].values()):,} |")
    print()
    print("| arm | game | our revenue - n18rc223d's by product (WH CA TO ST ME EGG MILK WOOL FERT) | ours total | opp total | spend | day-11 dawn cash |")
    print("|---|---|---|---|---|---|---|")
    for arm in arms:
        if arm == "n18rc223d":
            continue
        for g in GAMES:
            x, b = res[arm][g], base.get(g)
            if not x or "error" in x or not b or "error" in b:
                continue
            diffs = " ".join(f"{x['revenue'][p] - b['revenue'][p]:+,}" for p in PRODUCTS)
            rt = sum(x["revenue"].values()) - sum(b["revenue"].values())
            ot = sum(x["opp_revenue"].values()) - sum(b["opp_revenue"].values())
            sp = (x["cash"] - sum(x["revenue"].values())) - (b["cash"] - sum(b["revenue"].values()))
            print(f"| {arm} | {g} | {diffs} | {rt:+,} | {ot:+,} | {-sp:+,.0f} | {x['cash_d6_d11_d12'][1]:,.0f} (223d {b['cash_d6_d11_d12'][1]:,.0f}) |")
            odiffs = " ".join(f"{x['opp_revenue'][p] - b['opp_revenue'][p]:+,}" for p in PRODUCTS)
            print(f"| {arm} | {g} (opponent) | {odiffs} | | | | |")
    if tr:
        print()
        print("| trace | switches | picks [day, tape, board distance] | land retry / hold / errors |")
        print("|---|---|---|---|")
        for k, v in tr.items():
            print(f"| {k} | {v['switches']} | {v['history']} | {v['land_retry']} / {v['land_hold']} / {v['land_errors']} |")
    if a.dsm4q:
        # the retrain4q day-11 test bed without the prefix (our library opening from day 0), next to the source control
        # (DSM's own game) and the retrain4q p264 runs (DSM's recorded commands to day 10, then the arm)
        p0, p264 = ROOT / "results/fresh/router4q_20260930/dsm4q_p0", ROOT / "results/fresh/retrain4q_20260930/dsm4q_p264"
        cases = [c["id"] for c in json.loads((ROOT / "results/fresh/retrain4q_20260930/dsm4q_cases.json").read_text())["cases"]]
        cols = [("control", p0 / "_controls")] + [(f"{x} p264", p264 / x) for x in a.dsm4q_ref.split(",") if x] + \
               [(f"{x} p0", p0 / x) for x in arms]
        print()
        print("| world | " + " | ".join(c for c, _ in cols) + " |")
        print("|---|" + "---|" * len(cols))
        sums = {c: [] for c, _ in cols}
        stats = {}
        for cid in cases:
            cells = []
            for c, d in cols:
                f = d / f"{cid}.json"
                if not f.exists():
                    cells.append("-")
                    continue
                r = json.loads(f.read_text(encoding="utf-8"))
                if r.get("margin") is None:
                    cells.append("ERR")
                    continue
                cells.append(f"{r['margin']:+,.0f}" + ("" if r.get("eligible", True) else " (inel.)"))
                sums[c].append(r["margin"])
                if c.endswith(" p0") and r.get("completed"):
                    acts_p = f.with_suffix(".actions.json")
                    stats[(c, cid)] = game_stats(r, json.loads(acts_p.read_text()) if acts_p.exists() else None)
            print(f"| {cid} | " + " | ".join(cells) + " |")
        print("| mean | " + " | ".join(f"{sum(v) / len(v):+,.0f} (n={len(v)})" if v else "-" for v in sums.values()) + " |")
        print()
        print("| arm p0 | world | q2/q3/q4 day | empty d8..14 | crop tile-days (d11-29) | hires d0-10 / total | day-11 dawn cash | d0-10 seed coins req/exec | animal coins req/exec |")
        print("|---|---|---|---|---|---|---|---|---|")
        for (c, cid), x in stats.items():
            rq, ex = x.get("d0_10_requested", {}), x.get("d0_10_executed", {})
            print(f"| {c} | {cid} | {x['q2_day']}/{x['q3_day']}/{x['q4_day']} | {' '.join(str(round(v)) for v in x['empty_d8_14'])} | "
                  f"{x['crop_tile_days']} ({x['crop_tile_days_d11_29']}) | {x['hires_d0_10']} / {x['hires_total']} | "
                  f"{x['cash_d6_d11_d12'][1]:,.0f} | {rq.get('seed_coins', 0):,}/{ex.get('seed_coins', 0):,} | "
                  f"{rq.get('animal_coins', 0):,}/{ex.get('animal_coins', 0):,} |")
    if a.json:
        Path(a.json).write_text(json.dumps(dict(results=res, traces=tr), indent=1))


if __name__ == "__main__":
    main()

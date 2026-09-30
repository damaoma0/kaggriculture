"""Exact day-11 benchmark report (user 2026-09-29: "exact prefix and day-11 start for both"): each candidate plays DSM's
seat from DSM's own recorded day-11 state (semantic_h2h_20260929.py --prefix-steps 264) in the 9 current-DSM 3-quadrant
games of dsmseat_cases.json; the reference is DSM continuing its own game (local_dsmseat/_controls).

Per candidate: mean margin gap vs DSM's continuation (ours - opp) - (DSM - opp), its split into our cash and the
opponent's, games better than the base, and our revenue gap by product (days 11-29) with units.

usage: dsm3q_report_20260929.py CAND [CAND ...] [--base n18rc8x] [--dir results/fresh/semantic_h2h_20260929/local_dsmseat]"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")


def load(d, cand, cid):
    p = d / cand / f"{cid}.json"
    return json.loads(p.read_text()) if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cands", nargs="+")
    ap.add_argument("--base", default="n18rc8x")
    ap.add_argument("--dir", default="results/fresh/semantic_h2h_20260929/local_dsmseat")
    ap.add_argument("--vs-base", action="store_true", help="also: both sides' revenue by product vs the base candidate")
    a = ap.parse_args()
    d = ROOT / a.dir
    cases = [c["id"] for c in json.loads((ROOT / "results/fresh/semantic_h2h_20260929/dsmseat_cases.json").read_text())["cases"]
             if c["id"].startswith("dsm3q-")]
    for cand in [a.base] + [c for c in a.cands if c != a.base]:
        rows, prod = [], {p: [0.0, 0.0] for p in PRODUCTS}
        for cid in cases:
            r, c, b = load(d, cand, cid), load(d, "_controls", cid), load(d, a.base, cid)
            if not r or not c:
                continue
            s = int(c["case"]["seat"])
            rows.append((cid, r["margin"] - c["margin"], r["cash"] - c["cash"], r["opponent_cash"] - c["opponent_cash"],
                         r["margin"] - b["margin"] if b else 0.0))
            for p in PRODUCTS:
                prod[p][0] += (r["daily"][s][30]["revenue"].get(p, 0) - r["daily"][s][11]["revenue"].get(p, 0)
                               - c["daily"][s][30]["revenue"].get(p, 0) + c["daily"][s][11]["revenue"].get(p, 0))
                prod[p][1] += (r["daily"][s][30]["sold_units"].get(p, 0) - r["daily"][s][11]["sold_units"].get(p, 0)
                               - c["daily"][s][30]["sold_units"].get(p, 0) + c["daily"][s][11]["sold_units"].get(p, 0))
        n = len(rows)
        if not n:
            print(cand, "no results")
            continue
        m = sum(x[1] for x in rows) / n
        better = sum(1 for x in rows if x[4] > 0)
        print(f"{cand:10s} n={n} gap {m:+8.0f} (ours {sum(x[2] for x in rows) / n:+7.0f}, opp {sum(x[3] for x in rows) / n:+7.0f})"
              f" vs {a.base} {sum(x[4] for x in rows) / n:+6.0f} ({better}/{n} better) | "
              + " ".join(f"{p[:4]} {v[0] / n:+.0f}({v[1] / n:+.0f}u)" for p, v in prod.items() if abs(v[0]) / n >= 50))
        if a.vs_base and cand != a.base:
            vb = {(side, p): 0.0 for side in (0, 1) for p in PRODUCTS}
            k = 0
            for cid in cases:
                r, b = load(d, cand, cid), load(d, a.base, cid)
                if not r or not b:
                    continue
                k += 1
                s = int(r["case"]["seat"])
                for side, seat in ((0, s), (1, 1 - s)):
                    for p in PRODUCTS:
                        vb[(side, p)] += r["daily"][seat][30]["revenue"].get(p, 0) - b["daily"][seat][30]["revenue"].get(p, 0)
            for side, lab in ((0, "ours"), (1, "opp ")):
                print(f"{'':10s}   vs base, {lab} revenue: " + " ".join(f"{p[:4]} {vb[(side, p)] / k:+.0f}" for p in PRODUCTS
                                                                    if abs(vb[(side, p)]) / k >= 30))


if __name__ == "__main__":
    main()

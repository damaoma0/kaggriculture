"""Day-by-day audit of the full-game gap vs DSM (local_dsmfull, current-DSM 3-quadrant worlds, mean over worlds):
per day the margin-gap change split into our revenue by product, our spend by kind and the opponent's cash; tiles by
kind (ours - DSM); plantings by crop (seed spend / seed price) and animals bought (DSM / ours); hands.

usage: gap_audit_20260929.py [CAND] [--days 0-29]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
SEED = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIM = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
PROD = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")


def main():
    a = sys.argv
    cand = a[1] if len(a) > 1 and not a[1].startswith("--") else "n18rc99"
    d0, d1 = map(int, (a[a.index("--days") + 1] if "--days" in a else "0-29").split("-"))
    cases = [c["id"] for c in json.loads((H / "dsmseat_cases.json").read_text())["cases"] if c["id"].startswith("dsm3q-")]
    D = [json.loads((H / "local_dsmfull/_controls" / f"{c}.json").read_text()) for c in cases]
    O = [json.loads((H / "local_dsmfull" / cand / f"{c}.json").read_text()) for c in cases]
    n = len(cases)

    def dd(games, d, field, seat_opp=False):
        out = defaultdict(float)
        for x in games:
            s = x["case"]["seat"]
            s = 1 - s if seat_opp else s
            A, B = x["daily"][s][d + 1][field], x["daily"][s][d][field]
            for k in set(A) | set(B):
                out[k] += (A.get(k, 0) - B.get(k, 0)) / n
        return out
    cum = 0.0
    for d in range(d0, d1 + 1):
        ra, rb = dd(D, d, "revenue"), dd(O, d, "revenue")
        sa, sb = dd(D, d, "spend"), dd(O, d, "spend")
        oa, ob = dd(D, d, "revenue", True), dd(O, d, "revenue", True)
        osa, osb = dd(D, d, "spend", True), dd(O, d, "spend", True)
        ta, tb = dd(D, d, "tile_hours"), dd(O, d, "tile_hours")
        rev = {p: rb.get(p, 0) - ra.get(p, 0) for p in PROD}
        spend = defaultdict(float)
        for k in set(sa) | set(sb):
            spend[k.split(":")[0]] += sb.get(k, 0) - sa.get(k, 0)
        opp = sum(ob.values()) - sum(oa.values()) - (sum(osb.values()) - sum(osa.values()))
        gap = sum(rev.values()) - sum(spend.values()) - opp
        cum += gap
        print(f"\n== day {d}: gap {gap:+.0f} (cum {cum:+.0f}) | our revenue: " +
              " ".join(f"{p[:4]} {v:+.0f}" for p, v in rev.items() if abs(v) >= 40) +
              " | our extra spend: " + " ".join(f"{k.replace('BUY_', '')} {v:+.0f}" for k, v in spend.items() if abs(v) >= 40) +
              f" | opponent {opp:+.0f}")
        tiles = {k.split(":")[-1]: (tb.get(k, 0) - ta.get(k, 0)) / 24 for k in set(ta) | set(tb)}
        print("   tiles ours-DSM: " + " ".join(f"{k[:6]} {v:+.1f}" for k, v in sorted(tiles.items(), key=lambda kv: kv[1]) if abs(v) >= 0.5))
        pl = " ".join(f"{c[:4]} {sa.get('BUY_SEED:' + c, 0) / p:.1f}/{sb.get('BUY_SEED:' + c, 0) / p:.1f}" for c, p in SEED.items()
                      if sa.get("BUY_SEED:" + c, 0) or sb.get("BUY_SEED:" + c, 0))
        an = " ".join(f"{c[:4]} {sa.get('BUY_ANIMAL:' + c, 0) / p:.1f}/{sb.get('BUY_ANIMAL:' + c, 0) / p:.1f}" for c, p in ANIM.items()
                      if sa.get("BUY_ANIMAL:" + c, 0) or sb.get("BUY_ANIMAL:" + c, 0))
        land = f" land {sa.get('BUY_LAND', 0):.0f}/{sb.get('BUY_LAND', 0):.0f}" if sa.get("BUY_LAND", 0) or sb.get("BUY_LAND", 0) else ""
        print(f"   seeds DSM/ours: {pl or '-'} | animals: {an or '-'} | hires {sa.get('HIRE', 0):.0f}/{sb.get('HIRE', 0):.0f}{land}")


if __name__ == "__main__":
    main()

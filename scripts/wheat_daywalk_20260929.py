"""Day-by-day wheat shortfall vs DSM (full games from day 0 on the current-DSM 3-quadrant worlds, local_dsmfull): per day
(mean over the worlds) wheat tiles and empty/weed tiles (tile-hours / 24), wheat seed bought (~ plantings, seed 10),
units harvested, FEED commands (1 wheat each), wheat bought back (coins), units sold and price, and the opponent's wheat
revenue in our game minus DSM's game (its sales are fixed; the price moves with our supply).

usage: wheat_daywalk_20260929.py [CAND]   (default n18rc99)"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"


def main():
    cand = sys.argv[1] if len(sys.argv) > 1 else "n18rc99"
    cases = [c["id"] for c in json.loads((H / "dsmseat_cases.json").read_text())["cases"] if c["id"].startswith("dsm3q-")]
    G = {"dsm": [], "ours": []}
    for cid in cases:
        G["dsm"].append(json.loads((H / "local_dsmfull/_controls" / f"{cid}.json").read_text()))
        G["ours"].append(json.loads((H / "local_dsmfull" / cand / f"{cid}.json").read_text()))
    n = len(cases)

    def per_day(x, d, seat_fn, fn):
        s = x["case"]["seat"]
        return fn(x["daily"][seat_fn(s)][d + 1], x["daily"][seat_fn(s)][d])

    own = lambda s: s
    opp = lambda s: 1 - s
    rows = []
    for d in range(30):
        r = {}
        for k, games in G.items():
            m = lambda fn, sf=own: sum(per_day(x, d, sf, fn) for x in games) / n
            r[k] = dict(
                tiles=m(lambda A, B: (A["tile_hours"].get("crop:WHEAT", 0) - B["tile_hours"].get("crop:WHEAT", 0)) / 24),
                idle=m(lambda A, B: sum(A["tile_hours"].get(t, 0) - B["tile_hours"].get(t, 0) for t in ("empty", "weed")) / 24),
                seed=m(lambda A, B: (A["spend"].get("BUY_SEED:WHEAT", 0) - B["spend"].get("BUY_SEED:WHEAT", 0)) / 10),
                harv=m(lambda A, B: A["physical"].get("produced:WHEAT", 0) - B["physical"].get("produced:WHEAT", 0)),
                feed=m(lambda A, B: A["physical"].get("op:FEED", 0) - B["physical"].get("op:FEED", 0)),
                buy=m(lambda A, B: A["spend"].get("BUY_PRODUCT:WHEAT", 0) - B["spend"].get("BUY_PRODUCT:WHEAT", 0)),
                sold=m(lambda A, B: A["sold_units"].get("WHEAT", 0) - B["sold_units"].get("WHEAT", 0)),
                rev=m(lambda A, B: A["revenue"].get("WHEAT", 0) - B["revenue"].get("WHEAT", 0)),
                orev=m(lambda A, B: A["revenue"].get("WHEAT", 0) - B["revenue"].get("WHEAT", 0), opp))
        rows.append(r)
    print(f"wheat, {cand} vs DSM, mean of {n} worlds (DSM / ours); money columns = ours - DSM")
    print(f"{'day':>3} | {'wheat tiles':>11} | {'empty+weed':>10} | {'planted':>9} | {'harvested':>11} | {'fed':>9} | "
          f"{'bought':>11} | {'sold @price':>21} | {'our wheat rev':>13} | {'opp wheat rev':>13} | {'cum wheat margin':>16}")
    cum = 0.0
    for d, r in enumerate(rows):
        a, b = r["dsm"], r["ours"]
        dr = b["rev"] - a["rev"]
        do = b["orev"] - a["orev"]
        db = -(b["buy"] - a["buy"])
        cum += dr - do + db
        pa = a["rev"] / a["sold"] if a["sold"] else 0
        pb = b["rev"] / b["sold"] if b["sold"] else 0
        print(f"{d:3d} | {a['tiles']:4.1f} / {b['tiles']:4.1f} | {a['idle']:4.1f} / {b['idle']:4.1f} | {a['seed']:3.1f} / {b['seed']:3.1f} |"
              f" {a['harv']:4.1f} / {b['harv']:4.1f} | {a['feed']:3.0f} / {b['feed']:3.0f} | {a['buy']:4.0f} / {b['buy']:4.0f} |"
              f" {a['sold']:4.1f}@{pa:2.0f} / {b['sold']:4.1f}@{pb:2.0f} | {dr:+13.0f} | {do:+13.0f} | {cum:+16.0f}")
    tot = {k: {f: sum(r[k][f] for r in rows) for f in rows[0][k]} for k in G}
    print("season:", {f: (round(tot['dsm'][f]), round(tot['ours'][f])) for f in tot["dsm"]})


if __name__ == "__main__":
    main()

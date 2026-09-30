"""Compare arm pairs on the d4q9 panel (2026-09-30): an arm name X is candidate Xo on the fold-b worlds and Xp on the
fold-a worlds (every world out of sample for the DSM-new cassette); "live" is n18rc223d on every world; "dsm" is DSM's own
game. Only worlds where every listed arm has a game are used; worlds listed strongest recorded opponent first.

An arm starting with "n18" is a live-based candidate run as is on every world.

usage: d4q9_arm_compare_20260930.py ARM[,ARM...] [--min-rating R]    e.g. d9c4,d9w1,d9w2,d9w3,live
       (differences are against the first arm)"""
import argparse
import gzip
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/dsm4q_d9_20260930"


def load(cid, key):
    f = OUT / "games" / f"{cid}.{key}.game.json.gz"
    return json.loads(gzip.open(f, "rt", encoding="utf-8").read()) if f.exists() else None


def key_of(arm, fold):
    if arm.startswith("n18"):                       # live-based arms: one candidate for every world
        return f"{arm}.p0"
    return {"live": "n18rc223d.p0", "dsm": "dsm"}.get(arm) or f"{arm}{fold}.p0"


def stats(g):
    f = g["daily"][g["seat"]][-1]
    ph = f["physical"]
    return dict(margin=g["margin"], cash=g["cash"], opp=g["opp_cash"],
                wheat_made=ph.get("produced:WHEAT", 0), wheat_sold=f["sold_units"].get("WHEAT", 0),
                carrot_sold=f["sold_units"].get("CARROT", 0), waters=ph.get("op:WATER", 0),
                fertilize=ph.get("op:FERTILIZE", 0), collects=ph.get("op:COLLECT_FERTILIZER", 0),
                fert_sold=f["sold_units"].get("FERTILIZER", 0), passes=ph.get("op:PASS", 0),
                spend=sum(f["spend"].values()), revenue=sum(f["revenue"].values()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arms")
    ap.add_argument("--min-rating", type=float, default=0.0)
    a = ap.parse_args()
    arms = a.arms.split(",")
    folds = json.loads((OUT / "folds.json").read_text("utf-8"))
    fold_of = {f"d4q9-{e}": "o" for e in folds["b"]}
    fold_of.update({f"d4q9-{e}": "p" for e in folds["a"]})
    rat = {f"d4q9-{r['episode']}": (r["score"] or 0, r["opponent"]) for r in
           json.loads((OUT / "opponent_ratings.json").read_text("utf-8"))}
    cases = [c for c in json.loads((OUT / "cases.json").read_text("utf-8"))["cases"] if rat[c["id"]][0] >= a.min_rating]
    cases.sort(key=lambda c: -rat[c["id"]][0])
    rows = []
    for c in cases:
        gs = [load(c["id"], key_of(x, fold_of[c["id"]])) for x in arms]
        if all(gs):
            rows.append((c, [stats(g) for g in gs]))
    print(f"{len(rows)} worlds with all of {arms} (rating >= {a.min_rating}); margins, strongest opponent first")
    print("   rating opponent           | " + " ".join(f"{x:>9s}" for x in arms))
    for c, ss in rows:
        print(f"   {rat[c['id']][0]:6.0f} {rat[c['id']][1][:18]:18s} | " + " ".join(f"{s['margin']:+9.0f}" for s in ss))
    if not rows:
        return
    n = len(rows)
    print(f"\nmeans over {n} worlds (difference vs {arms[0]}, SE, better count)")
    for k in ("margin", "cash", "opp", "revenue", "spend", "wheat_made", "wheat_sold", "carrot_sold", "waters", "fertilize",
              "collects", "fert_sold", "passes"):
        line = f"   {k:12s}"
        for i, x in enumerate(arms):
            v = st.mean(ss[i][k] for c, ss in rows)
            line += f" | {x} {v:9.1f}"
            if i:
                d = [ss[i][k] - ss[0][k] for c, ss in rows]
                se = st.stdev(d) / n ** 0.5 if n > 1 else 0
                line += f" ({st.mean(d):+.0f}, {se:.0f}" + (f", {sum(x_ > 0 for x_ in d)}/{n})" if k == "margin" else ")")
        print(line)
    print("   wins vs the recorded opponent: " + ", ".join(f"{x} {sum(ss[i]['margin'] > 0 for c, ss in rows)}/{n}"
                                                       for i, x in enumerate(arms)))


if __name__ == "__main__":
    main()

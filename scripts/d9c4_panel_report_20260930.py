"""Full-game panel of the day-9 handover candidate (2026-09-30): d9c4o (cassette learned on fold a) on the 21 fold-b
worlds and its twin d9c4p (cassette learned on fold b) on the 22 fold-a worlds - every world out of sample - against
the live build n18rc223d and DSM's own recorded game, all from step 0 (harness job() of dsm4q_d9_gap_20260930.py,
prefix 0). Same world for all three: DSM's shops, our seat = DSM's seat, the opponent replays its recorded commands
(frozen). Worlds are listed strongest recorded opponent first (current ladder score of the opponent team,
results/fresh/dsm4q_d9_20260930/opponent_ratings.json); partial panels report what is on disk.

usage: d9c4_panel_report_20260930.py [--live n18rc223d.p0]"""
import argparse
import gzip
import json
import statistics as st
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/dsm4q_d9_20260930"
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
BANDS = ((2650, 9999, "2650+"), (2450, 2650, "2450-2650"), (0, 2450, "below 2450"))


def load(cid, key):
    f = OUT / "games" / f"{cid}.{key}.game.json.gz"
    return json.loads(gzip.open(f, "rt", encoding="utf-8").read()) if f.exists() else None


def q4_day(g):
    return next((f["t"] // 24 for f in g["frames"] if f.get("q", 0) >= 4), None)


def mse(xs):
    return (st.mean(xs), st.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else 0.0)


def rev(g, prod):
    return g["daily"][g["seat"]][-1]["revenue"].get(prod, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", default="n18rc223d.p0")
    a = ap.parse_args()
    folds = json.loads((OUT / "folds.json").read_text("utf-8"))
    cand_of = {f"d4q9-{e}": "d9c4o.p0" for e in folds["b"]}
    cand_of.update({f"d4q9-{e}": "d9c4p.p0" for e in folds["a"]})
    rat = {f"d4q9-{r['episode']}": r["score"] or 0 for r in json.loads((OUT / "opponent_ratings.json").read_text("utf-8"))}
    cases = json.loads((OUT / "cases.json").read_text("utf-8"))["cases"]
    cases.sort(key=lambda c: -rat[c["id"]])
    games = {c["id"]: (load(c["id"], "dsm"), load(c["id"], cand_of[c["id"]]), load(c["id"], a.live)) for c in cases}
    print(f"on disk: candidate {sum(1 for v in games.values() if v[1])}/43, live {sum(1 for v in games.values() if v[2])}/43"
          f" (candidate = d9c4o on fold b, d9c4p on fold a; live = {a.live}; DSM = its own recorded game)")
    errs = [(cid, k, g["errors"]) for cid, (d, o, v) in games.items() for k, g in (("cand", o), ("live", v)) if g and g.get("errors")]
    print(f"games with errors: {len(errs)} (bank stop: {sum('bank stop' in json.dumps(e) for e in errs)})")
    for x in errs[:5]:
        print("   ", x[0], x[1], json.dumps(x[2])[:200])
    print("\nper world, strongest opponent first: rating, opponent | final cash cand / live / DSM | margin cand / live / DSM"
          " | cand-live cash, margin | Q4 day cand/live/DSM")
    for c in cases:
        d, o, v = games[c["id"]]
        if not (o or v):
            continue
        f = lambda g, k, w: f"{g[k]:{w}.0f}" if g else " " * (w - 1) + "-"  # noqa: E731
        diff = f"{o['cash'] - v['cash']:+7.0f} {o['margin'] - v['margin']:+7.0f}" if (o and v) else " " * 15
        print(f"  {rat[c['id']]:6.0f} {c['opponent'][:18]:18s} | {f(o, 'cash', 7)} {f(v, 'cash', 7)} {d['cash']:7.0f} |"
              f" {f(o, 'margin', 8)} {f(v, 'margin', 8)} {d['margin']:+8.0f} | {diff} | "
              f"{q4_day(o) if o else '-'}/{q4_day(v) if v else '-'}/{q4_day(d)}")
    print("\nby opponent band (paired worlds only; SE of the paired difference in brackets)")
    for lo, hi, lab in BANDS:
        sub = [(c, *games[c["id"]]) for c in cases if lo <= rat[c["id"]] < hi]
        both = [(c, d, o, v) for c, d, o, v in sub if o and v]
        co = [(c, d, o) for c, d, o, v in sub if o]
        line = f"  {lab:10s}: candidate games {len(co)}/{len(sub)}"
        if co:
            m, s = mse([o["margin"] - d["margin"] for c, d, o in co])
            line += (f"; cand margin {st.mean(o['margin'] for c, d, o in co):+.0f} vs DSM {st.mean(d['margin'] for c, d, o in co):+.0f}"
                     f" (cand-DSM {m:+.0f} ({s:.0f})), cand wins {sum(o['margin'] > 0 for c, d, o in co)}/{len(co)},"
                     f" DSM wins {sum(d['margin'] > 0 for c, d, o in co)}/{len(co)}")
        print(line)
        if both:
            m, s = mse([o["cash"] - v["cash"] for c, d, o, v in both])
            mm, sm = mse([o["margin"] - v["margin"] for c, d, o, v in both])
            print(f"  {'':10s}  paired with live ({len(both)}): cash cand-live {m:+.0f} ({s:.0f}), margin cand-live {mm:+.0f} ({sm:.0f}),"
                  f" better {sum(o['margin'] > v['margin'] for c, d, o, v in both)}/{len(both)}; wins cand"
                  f" {sum(o['margin'] > 0 for c, d, o, v in both)} live {sum(v['margin'] > 0 for c, d, o, v in both)}")
    rows = [(c, *games[c["id"]]) for c in cases if all(games[c["id"]]) and games[c["id"]][0]["recorded_cash_match"]]
    if not rows:
        return
    n = len(rows)
    print(f"\nall paired worlds ({n}): means (SE of the paired difference)")
    for lab, f in (("final cash", lambda g: g["cash"]), ("margin", lambda g: g["margin"]),
                   ("opponent cash", lambda g: g["opp_cash"])):
        co, cv, cd = [f(o) for c, d, o, v in rows], [f(v) for c, d, o, v in rows], [f(d) for c, d, o, v in rows]
        m1, s1 = mse([x - y for x, y in zip(co, cv)])
        m2, s2 = mse([x - y for x, y in zip(co, cd)])
        m3, s3 = mse([x - y for x, y in zip(cv, cd)])
        print(f"  {lab:13s}: cand {st.mean(co):8.0f}  live {st.mean(cv):8.0f}  DSM {st.mean(cd):8.0f} | cand-live {m1:+7.0f} ({s1:.0f},"
              f" better {sum(x > y for x, y in zip(co, cv))}/{n})  cand-DSM {m2:+7.0f} ({s2:.0f})  live-DSM {m3:+7.0f} ({s3:.0f})")
    print(f"  Q4 owned from day: cand {sorted(Counter(q4_day(o) for c, d, o, v in rows).items(), key=str)}, "
          f"live {sorted(Counter(q4_day(v) for c, d, o, v in rows).items(), key=str)}, "
          f"DSM {sorted(Counter(q4_day(d) for c, d, o, v in rows).items(), key=str)}")
    print("\ncash at dawn, mean: cand / live / DSM")
    for day in (6, 9, 11, 12, 15, 20, 25):
        t = 24 * day
        print(f"  day {day:2d}: " + " / ".join(f"{st.mean(g['frames'][t]['m'][0] for g in gs):7.0f}"
                                            for gs in ([o for c, d, o, v in rows], [v for c, d, o, v in rows], [d for c, d, o, v in rows])))
    print("\nseason revenue by product, mean: cand / live / DSM (cand - live)")
    for p in GOODS:
        ro, rv, rd = (st.mean(rev(g, p) for g in gs) for gs in ([o for c, d, o, v in rows], [v for c, d, o, v in rows],
                                                                 [d for c, d, o, v in rows]))
        print(f"  {p:10s} {ro:8.0f} / {rv:8.0f} / {rd:8.0f} ({ro - rv:+6.0f})")


if __name__ == "__main__":
    main()

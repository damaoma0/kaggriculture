"""How the current leaders open (user 2026-09-30: "how are their openings converged and how might we copy them").
Action-only pass over the latest harvested submission of each top team (data/leader_tapes/<team>_<sub>/, written by
scripts/harvest_leader_tapes.py) plus our live n18rc99s (data/ladder_panel/56676484). Orders are REQUESTED market
orders (a request can fail for cash / the 10-order cap); quadrant days are exact (quadrants_by_day from the replay).

usage: leader_openings_20260930.py [--days 12] [--json out.json]"""
import argparse
import glob
import gzip
import json
import os
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CROPS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
ANIMALS = ["COW", "SHEEP", "GOOSE"]


def teams():
    """latest harvested submission per team (highest submission id), plus ours"""
    best = {}
    for d in glob.glob(str(ROOT / "data/leader_tapes/*_*")):
        tid, sub = os.path.basename(d).split("_")
        idx = Path(d) / "index.json"
        if not idx.exists() or not glob.glob(d + "/*.json.gz"):
            continue
        name = json.loads(idx.read_text("utf-8")).get("team", tid)
        if tid not in best or int(sub) > best[tid][1]:
            best[tid] = (name, int(sub), d)
    out = [(n, s, d, "actions") for n, s, d in best.values()]
    out.append(("US n18rc99s", 56676484, str(ROOT / "data/ladder_panel/56676484"), "our_actions"))
    return out


def game_features(x, key, days):
    seat = int(x["seat"])
    acts = x[key]
    f = dict(day={d: Counter() for d in range(days)}, sig0=None)
    sig = []
    for t in range(min(days * 24, len(acts))):
        a = acts[t] or {}
        d, h = divmod(t, 24)
        for o in a.get("market") or []:
            if not o:
                continue
            k = o[0]
            n = int(o[2]) if len(o) > 2 and isinstance(o[2], (int, float)) else 1
            if k == "BUY_SEED":
                f["day"][d][f"seed:{o[1]}"] += n
            elif k == "BUY_ANIMAL":
                f["day"][d][f"animal:{o[1]}"] += n
            elif k == "BUY_PRODUCT":
                f["day"][d][f"buy:{o[1]}"] += n
            elif k == "SELL":
                f["day"][d][f"sell:{o[1]}"] += n
            elif k == "HIRE":
                f["day"][d]["hire"] += 1
                f["day"][d][f"hire_h{min(h, 2)}"] += 1
            elif k == "BUY_LAND":
                f["day"][d]["land_req"] += 1
            if d == 0 and h <= 1:
                sig.append((h, k, o[1] if len(o) > 1 else "", n))
    f["sig0"] = tuple(sig)
    q = [row[seat] for row in x.get("quadrants_by_day") or []]
    f["quad_day"] = {k: next((d - 1 for d in range(1, len(q)) if q[d] >= k > q[d - 1]), None) for k in (2, 3, 4)} if q else {}
    f["margin"] = x["rewards"][seat] - x["rewards"][1 - seat]
    f["shops2"] = tuple((x.get("shops") or [])[:2])
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=12)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    rows = {}
    for name, sub, d, key in teams():
        gs = []
        for p in sorted(glob.glob(d + "/*.json.gz")):
            try:
                x = json.load(gzip.open(p, "rt", encoding="utf-8"))
            except (OSError, EOFError, ValueError):
                continue
            if key == "actions" and x["names"][0] == x["names"][1]:
                continue                               # self-play validation game
            gs.append(game_features(x, key, a.days))
        if gs:
            rows[(name, sub)] = gs
    order = sorted(rows, key=lambda k: (k[0].startswith("US"), k[0]))
    print(f"{'team':24s} {'sub':>9s} {'n':>3s} {'win%':>5s}  quadrants 2/3/4 (modal day, share)   day-0 signature share")
    for k in order:
        gs = rows[k]
        qs = []
        for q in (2, 3, 4):
            c = Counter(g["quad_day"].get(q) for g in gs)
            day, cnt = c.most_common(1)[0]
            qs.append(f"{day}:{cnt / len(gs):.0%}")
        sc = Counter(g["sig0"] for g in gs).most_common(1)[0][1] / len(gs)
        print(f"{k[0][:24]:24s} {k[1]:9d} {len(gs):3d} {100 * sum(g['margin'] > 0 for g in gs) / len(gs):5.0f}  "
              f"{'  '.join(qs):32s} {sc:.0%}")
    print("\nmean requested orders per game by day (seeds / animals / hires / wheat bought); '-' = none")
    items = [f"seed:{c}" for c in CROPS] + [f"animal:{x}" for x in ANIMALS] + ["hire", "buy:WHEAT", "buy:FERTILIZER"]
    for it in items:
        print(f"\n{it}")
        for k in order:
            gs = rows[k]
            vals = [st.mean(g["day"][d][it] for g in gs) for d in range(a.days)]
            print(f"  {k[0][:22]:22s} " + " ".join(f"{v:5.1f}" if v >= 0.05 else "    -" for v in vals))
    print("\nmodal day-0 hour 0-1 orders per team (hour, order, item, n)")
    for k in order:
        sig, cnt = Counter(g["sig0"] for g in rows[k]).most_common(1)[0]
        print(f"  {k[0][:22]:22s} {cnt}/{len(rows[k])}: {list(sig)[:14]}")
    if a.json:
        Path(a.json).write_text(json.dumps({f"{k[0]}|{k[1]}": [dict(day={d: dict(c) for d, c in g['day'].items()},
                                                                   sig0=g["sig0"], quad_day=g["quad_day"], margin=g["margin"],
                                                                   shops2=g["shops2"]) for g in v] for k, v in rows.items()}),
                                "utf-8")


if __name__ == "__main__":
    main()

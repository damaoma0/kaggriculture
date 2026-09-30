"""Day-by-day walk of a recorded back-to-back pair (b2b_replay_20260929.py caches): DSM's own game vs ours in the same
world, per day d (days FROM..29):
  gap      margin gap change that day (ours - DSM, end of day) and its split into our cash / the opponent's cash
  board    tiles whose kind differs at dawn of day d+1 (ours vs DSM), grouped by (DSM label -> ours label)
  plant    plantings (tile, crop) DSM made that day that we did not make that day, and ours that DSM did not
  work     executed field commands per type (from the step commands), idle commands (PASS / none), hands
  harvest  units harvested per product (engine 'produced') and wheat harvests by size
  sales    units sold and revenue per product; spend by kind

usage: b2b_daywalk_20260929.py CASE_ID TAG [--from 11] [--to 29] [--tiles]
  TAG = <cand>.p<prefix> (e.g. n18te1.p264); --tiles lists every differing tile"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_h2h_20260929/b2b"
LAB = {"WHEAT": "WH", "CARROT": "CA", "TOMATO": "TO", "STRAWBERRY": "ST", "MELON": "ME", "COW": "cow", "SHEEP": "shp",
       "GOOSE": "gse"}
WORK = ("PLANT", "HARVEST", "WATER", "FERTILIZE", "COLLECT_FERTILIZER", "FEED", "CARE", "DIG", "PICKUP", "DROP", "PLACE",
        "BUILD_COOP", "BUILD_PASTURE")


def load(key, cid):
    return json.loads(gzip.open(OUT / f"{cid}.{key}.game.json.gz", "rt", encoding="utf-8").read())


def lab(t):
    if t is None:
        return "."
    if t == "LOCKED":
        return "L"
    if isinstance(t, dict):
        if t.get("animal"):
            return LAB[t["animal"]]
        if t.get("crop"):
            return LAB[t["crop"]]
        if t.get("kind") in ("PASTURE", "COOP"):
            return t["kind"][:3].lower()
        if t.get("kind") == "WEED":
            return "weed"
    return "?"


def board(g, step):
    f = g["frames"][min(step, len(g["frames"]) - 1)]
    return [g["tiles"][i] for i in f["b"]]


def plantings(g, d):
    """(tile, crop) planted on day d: tiles whose plant has planted_day == d at the dawn of d + 1"""
    b = board(g, (d + 1) * 24) if d < 29 else board(g, len(g["frames"]) - 1)
    return {(i, t["crop"]) for i, t in enumerate(b) if isinstance(t, dict) and t.get("crop") and t.get("planted_day") == d}


def work(g, d):
    c, idle = Counter(), 0
    hands = 0
    for f in g["frames"][d * 24:(d + 1) * 24]:
        a = f.get("a") or {}
        cmds = [a.get("farmer")] + list(a.get("hands") or [])
        hands = max(hands, len(f["u"]) - 1)
        for x in cmds:
            if not x or x[0] == "PASS":
                idle += 1
            elif x[0] in WORK:
                c[x[0]] += 1
    return c, idle, hands


def delta(g, d, field):
    s = g["seat"]
    A, B = g["daily"][s][d + 1][field], g["daily"][s][d][field]
    return {k: A.get(k, 0) - B.get(k, 0) for k in set(A) | set(B) if A.get(k, 0) - B.get(k, 0)}


def main():
    a = sys.argv
    cid, tag = a[1], a[2]
    d0 = int(a[a.index("--from") + 1]) if "--from" in a else 11
    d1 = int(a[a.index("--to") + 1]) if "--to" in a else 29
    A, B = load("dsm", cid), load(tag, cid)
    s = A["seat"]
    cum = 0.0
    for d in range(d0, d1 + 1):
        ma = lambda g, k: g["daily"][s][k]["money"] - g["daily"][1 - s][k]["money"]
        gap_d = (ma(B, d + 1) - ma(A, d + 1)) - (ma(B, d) - ma(A, d))
        own = (B["daily"][s][d + 1]["money"] - B["daily"][s][d]["money"]) - (A["daily"][s][d + 1]["money"] - A["daily"][s][d]["money"])
        opp = (B["daily"][1 - s][d + 1]["money"] - B["daily"][1 - s][d]["money"]) - (A["daily"][1 - s][d + 1]["money"] - A["daily"][1 - s][d]["money"])
        tot = ma(B, d + 1) - ma(A, d + 1)
        print(f"\n===== DAY {d}: gap today {gap_d:+.0f} (our cash {own:+.0f}, opponent {opp:+.0f}); gap so far {tot:+.0f}")
        # board at the next dawn
        ba, bb = board(A, (d + 1) * 24), board(B, (d + 1) * 24)
        diff = Counter((lab(x), lab(y)) for x, y in zip(ba, bb) if lab(x) != lab(y))
        if diff:
            print("  board at next dawn, DSM -> ours:", ", ".join(f"{k[0]}->{k[1]} x{v}" for k, v in diff.most_common()))
            if "--tiles" in a:
                print("   ", [(i % 10, i // 10, lab(x), lab(y)) for i, (x, y) in enumerate(zip(ba, bb)) if lab(x) != lab(y)])
        pa, pb = plantings(A, d), plantings(B, d)
        miss, extra = pa - pb, pb - pa
        if miss or extra:
            print(f"  plantings: DSM {len(pa)}, ours {len(pb)}; DSM's not made by us {sorted(Counter(c for _, c in miss).items())}"
                  f"; ours not in DSM's {sorted(Counter(c for _, c in extra).items())}")
        wa, ia, ha = work(A, d)
        wb, ib, hb = work(B, d)
        keys = [k for k in WORK if wa[k] or wb[k]]
        print(f"  hands DSM {ha} / ours {hb}; idle commands DSM {ia} / ours {ib}")
        print("  work (DSM/ours):", " ".join(f"{k.lower()} {wa[k]}/{wb[k]}" for k in keys))
        pra, prb = delta(A, d, "physical"), delta(B, d, "physical")
        prods = sorted({k[9:] for k in list(pra) + list(prb) if k.startswith("produced:")})
        print("  harvested (DSM/ours):", " ".join(f"{p.lower()} {pra.get('produced:' + p, 0)}/{prb.get('produced:' + p, 0)}" for p in prods))
        fa = {k: v for k, v in pra.items() if k.startswith("no_effect") or k.startswith("fail")}
        fb = {k: v for k, v in prb.items() if k.startswith("no_effect") or k.startswith("fail")}
        if fa or fb:
            print("  commands without effect (DSM / ours):", fa, "/", fb)
        ua, ub = delta(A, d, "sold_units"), delta(B, d, "sold_units")
        ra, rb = delta(A, d, "revenue"), delta(B, d, "revenue")
        ps = sorted(set(ua) | set(ub))
        print("  sold (DSM/ours units @avg):", " ".join(
            f"{p.lower()} {ua.get(p, 0)}@{ra.get(p, 0) / max(1, ua.get(p, 0)):.0f}/{ub.get(p, 0)}@{rb.get(p, 0) / max(1, ub.get(p, 0)):.0f}" for p in ps))
        sa, sb = delta(A, d, "spend"), delta(B, d, "spend")
        sk = sorted(set(sa) | set(sb))
        if sk:
            print("  spend (DSM/ours):", " ".join(f"{k} {sa.get(k, 0):.0f}/{sb.get(k, 0):.0f}" for k in sk))


if __name__ == "__main__":
    main()

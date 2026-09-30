"""Where one executor loses output against another in the same world (2026-09-30): per animal-day and per ongoing-crop
production accounting and yield that never reached an inventory, days 11-29, from saved full-stack games.

usage: exec_loss_trace_20260930.py EP[,EP] KEY[,KEY...]   (keys as saved in results/fresh/dsm4q_d9_20260930/games,
       e.g. fsCand.p264,d9c4o.p0)

Frame layout of these games: frame t holds the units' positions at the start of step t, the actions of step t and the
board AFTER step t's actions; the midnight refresh is applied at the start of the next day's hour-0 step, so frame
24d+23 is the board the refresh of day d sees."""
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

G = Path(__file__).resolve().parents[1] / "results/fresh/dsm4q_d9_20260930/games"
AN = {"GOOSE": (4, 1, 4), "COW": (8, 2, 6), "SHEEP": (6, 3, 6)}      # first_yield_day, interval, max_held
CR = {"TOMATO": (8, 1, 4), "STRAWBERRY": (10, 2, 4)}                 # first_yield_day, interval, max_yield


def lab(t):
    return (t.get("crop") or t.get("animal")) if isinstance(t, dict) else None


def acts_at(f):
    out = {}
    alist = [f["a"].get("farmer")] + list(f["a"].get("hands") or [])
    for pos, a in zip(f["u"], alist):
        if a and pos:
            out.setdefault(pos[1] * 10 + pos[0], []).append(a[0])
    return out


def trace(key, ep):
    g = json.loads(gzip.open(G / f"d4q9-{ep}.{key}.game.json.gz", "rt", encoding="utf-8").read())
    T, F = g["tiles"], g["frames"]
    c = Counter()
    for d in range(11, 29):                                   # the refresh at the end of day d
        pre, post = F[24 * d + 23], F[24 * (d + 1)]
        post_acts = acts_at(post)
        for p in range(100):
            s, n = T[pre["b"][p]], T[post["b"][p]]
            if isinstance(s, dict) and s.get("animal"):
                an = s["animal"]
                fy, iv, mx = AN[an]
                fed, cared = s["fed_today"], s["cared_today"]
                c[an, "animal_days"] += 1
                c[an, "fed"] += fed
                c[an, "fed_and_cared"] += fed and cared
                c[an, "cared_unfed"] += cared and not fed
                if not (isinstance(n, dict) and n.get("animal")):
                    c[an, "escaped"] += 1
                    continue
                ds = d + 1 - s["placed_day"] - fy
                if ds >= 0 and ds % iv == 0:
                    bank = s.get("pending_care_bonus", 0)
                    prod = 1 + (bank if fed else 0)
                    lost = max(0, s["yield_units"] + prod - mx)
                    c[an, "made"] += prod - lost
                    c[an, "bank_wiped_unfed"] += 0 if fed else bank
                    c[an, "lost_pen_full"] += lost
            elif isinstance(s, dict) and s.get("crop") in CR:
                cr = s["crop"]
                fy, iv, mx = CR[cr]
                if not (isinstance(n, dict) and n.get("crop") == cr):
                    continue
                ds = d + 1 - s["planted_day"] - fy
                if ds < 0 or ds % iv or ds // iv + 1 > mx:
                    continue
                wat, fert = s["watered_today"], s.get("fertilized_until_day", -1) >= d
                inc = 2 if (wat and fert) else 1
                lost = max(0, s["yield_units"] + inc - mx)
                c[cr, "production_days"] += 1
                c[cr, "unfertilized_production"] += not fert
                c[cr, "made"] += inc - lost
                c[cr, "lost_plant_full"] += lost
    for t in range(265, 719):                                 # yield on a tile that vanished without a HARVEST
        pre, post = F[t - 1], F[t]
        acts = acts_at(post)
        for p in range(100):
            s, n = T[pre["b"][p]], T[post["b"][p]]
            if isinstance(s, dict) and s.get("yield_units", 0) > 0 and lab(s) and "HARVEST" not in acts.get(p, []) \
                    and lab(n) != lab(s):
                how = "+".join(acts.get(p, [])) or ("lifespan" if t == s.get("max_lifespan_step") else "refresh")
                c[lab(s), "lost_on_vanish:" + how] += s["yield_units"]
    for p in range(100):
        s = T[F[718]["b"][p]]
        if isinstance(s, dict) and s.get("yield_units", 0) > 0 and lab(s):
            c[lab(s), "left_at_end"] += s["yield_units"]
    return c


def main():
    eps, keys = sys.argv[1].split(","), sys.argv[2].split(",")
    for ep in eps:
        res = {k: trace(k, ep) for k in keys}
        print(f"== {ep}   " + " | ".join(keys))
        for r in sorted({r for c in res.values() for r in c}):
            print(f"   {r[0]:10s} {r[1]:26s}" + " | ".join(f"{res[k].get(r, 0):6d}" for k in keys))


if __name__ == "__main__":
    main()

"""What the new DSM (56692773) actually does, hour by hour, on chosen days (user 2026-09-30: "E68 is learning from what
is actually done by DSM ... you can do it as well"): from the step frames of the DSM controls of
scripts/dsm4q_d9_gap_20260930.py (DSM continuing its own recorded game; every step's board, units, action, cash).
Per hour, mean per game: market sells by product, buys (seeds by crop, animals, land, wheat), unit ops (HARVEST by tile
kind, COLLECT_FERTILIZER, DROP / PLACE at the shed, PLANT on old vs new land, WATER, FEED, CARE), cash.
Optionally the same for one of our arms (per-world names: {ep}) to compare.

usage: dsm4q_day_profile_20260930.py [--days 9,10] [--arm d9e68m{ep}] [--json out.json]"""
import argparse
import gzip
import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/dsm4q_d9_20260930"
SHED = {(4, 4), (5, 4), (4, 5), (5, 5)}


def load(cid, key):
    f = OUT / "games" / f"{cid}.{key}.game.json.gz"
    return json.loads(gzip.open(f, "rt", encoding="utf-8").read()) if f.exists() else None


def kind(t):
    if not isinstance(t, dict):
        return "LOCKED" if t == "LOCKED" else "EMPTY"
    return t.get("crop") or t.get("animal") or t.get("kind")


def profile(g, day):
    """per hour: Counter of events for one game and day"""
    T, F = g["tiles"], g["frames"]
    locked0 = {i for i, b in enumerate(F[24 * day]["b"]) if T[b] == "LOCKED"}
    rows = []
    for h in range(24):
        t = 24 * day + h
        fr = F[t]
        a = fr.get("a") or {}
        c = Counter()
        c["cash"] = fr["m"][0]
        for o in a.get("market") or []:
            if not o:
                continue
            n = int(o[2]) if len(o) > 2 and isinstance(o[2], (int, float)) else 1
            if o[0] == "SELL":
                c["sell:" + o[1]] += n
            elif o[0] == "BUY_SEED":
                c["seed:" + o[1]] += n
            elif o[0] == "BUY_ANIMAL":
                c["animal:" + o[1]] += n
            elif o[0] == "BUY_PRODUCT":
                c["buy:" + o[1]] += n
            elif o[0] in ("BUY_LAND", "HIRE"):
                c[o[0].lower()] += 1
        units = fr["u"]
        cmds = [a.get("farmer")] + list(a.get("hands") or [])
        for pos, cmd in zip(units, cmds):
            if not cmd:
                continue
            op = cmd[0]
            idx = pos[1] * 10 + pos[0]
            here = T[fr["b"][idx]] if 0 <= idx < 100 else None
            if op == "HARVEST":
                c["harvest:" + str(kind(here))] += 1
            elif op == "PLANT":
                c["plant_new" if idx in locked0 else "plant_old"] += 1
                c["plant:" + str(cmd[1] if len(cmd) > 1 else "?")] += 1
            elif op in ("DROP", "PLACE") and tuple(pos) in SHED:
                c["shed_drop"] += 1
                if op == "PLACE" and len(cmd) > 1:
                    c["shed_place:" + str(cmd[1])] += 1
            elif op in ("WATER", "FEED", "CARE", "COLLECT_FERTILIZER", "FERTILIZE", "PASS", "PICKUP"):
                c[op.lower()] += 1
        c["units"] = len(units)
        rows.append(c)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", default="9,10")
    ap.add_argument("--arm", default="")
    ap.add_argument("--keys", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    cases = json.loads((OUT / "cases.json").read_text("utf-8"))["cases"]
    days = [int(x) for x in a.days.split(",")]
    res = {}
    for who in ["DSM"] + ([a.arm] if a.arm else []):
        acc = {d: [Counter() for _ in range(24)] for d in days}
        n = 0
        for c in cases:
            g = None                               # an arm may be "a|b" (fold pairs): the first that exists for this case
            for alt in (["dsm"] if who == "DSM" else [w.replace("{ep}", c["episode"]) + ".p216" for w in who.split("|")]):
                g = g or load(c["id"], alt)
            if not g or (who != "DSM" and not load(c["id"], "dsm")):
                continue
            n += 1
            for d in days:
                for h, row in enumerate(profile(g, d)):
                    acc[d][h].update(row)
        res[who] = dict(n=n, days={d: [{k: v / n for k, v in r.items()} for r in acc[d]] for d in days})
    keys = a.keys.split(",") if a.keys else None
    for who, r in res.items():
        print(f"== {who} ({r['n']} games)")
        for d in days:
            rows = r["days"][d]
            ks = keys or sorted({k for row in rows for k in row if k not in ("cash", "units")},
                                key=lambda k: -sum(row.get(k, 0) for row in rows))[:18]
            print(f" day {d}: " + " ".join(f"{h:>5d}" for h in range(24)))
            print(f"  {'cash':16s}" + " ".join(f"{rows[h].get('cash', 0):5.0f}" for h in range(24)))
            for k in ks:
                tot = sum(row.get(k, 0) for row in rows)
                if tot >= 0.3:
                    print(f"  {k[:16]:16s}" + " ".join(f"{rows[h].get(k, 0):5.1f}" if rows[h].get(k, 0) >= 0.05 else "    ." for h in range(24)) + f"  = {tot:5.1f}")
    if a.json:
        Path(a.json).write_text(json.dumps(res), "utf-8")


if __name__ == "__main__":
    main()

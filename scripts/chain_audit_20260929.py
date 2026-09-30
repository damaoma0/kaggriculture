"""Action-chain audit of recorded games (b2b_replay caches), user 2026-09-29: "especially the action chain, in the value
approach we might harvest but not water as shown before, or fertilize but not water, water but not fertilize".

For every plant cohort (tile, crop, planted day) planted from day FROM, the recorded commands on its tile (a unit's work
command acts on the tile it stands on) are replayed against the engine rules (engine 1.32.7):
  one-time crops (wheat, carrot, melon): planted at 1 unit; each WATER on a window day [(maxday+1)//2, maxday] adds +1,
    +2 when fertilized that day (a FERTILIZE on day f covers f..f+2 and must come BEFORE the water), capped at max;
    harvest from `first`.
  ongoing crops (tomato, strawberry): a production at the end of day d adds +2 when the plant was watered that day AND
    fertilized (cover >= d), else +1; the yield is capped at max (4).
Per cohort, units a better chain on the SAME visits / days would have added:
  harvest_before_water   harvested on a window day, below the cap, not watered earlier that day (+1 / +2)
  window_day_dry         a window day before the harvest without any water (+1 / +2)
  water_unfertilized     a window water without fertilizer cover (+1 each; only counts where a +2 was still below cap)
  fert_after_water       the day's water came before the day's FERTILIZE (+1)
  fert_wasted            a FERTILIZE whose 3-day cover had no useful water (one-time: window water; ongoing: a watered
                         production day) - the fertilizer is lost
  prod_fert_dry          ongoing: a production night fertilized but not watered (+1)
  prod_water_nofert      ongoing: a production night watered but not fertilized (+1 possible)
  prod_overflow          ongoing: units lost because the yield on the tile hit the cap
Totals per crop and cause; compare games (DSM vs ours on the same worlds).

usage: chain_audit_20260929.py CASE_ID[,CASE_ID...] KEY [KEY ...] [--from 6]   (KEY: dsm | <cand>.p<prefix>)"""
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/semantic_h2h_20260929/b2b"
CROPS = {"WHEAT": dict(first=2, maxday=4, max=6, ongoing=False), "CARROT": dict(first=2, maxday=3, max=4, ongoing=False),
         "MELON": dict(first=10, maxday=12, max=6, ongoing=False),
         "TOMATO": dict(first=8, interval=1, max=4, prods=4, ongoing=True),
         "STRAWBERRY": dict(first=10, interval=2, max=4, prods=4, ongoing=True)}
WORK = ("WATER", "FERTILIZE", "HARVEST", "DIG", "PLANT")


def cohorts(g, d0):
    """(tile, crop, planted) -> dict(ops=[(step, op)], end_step, yields={step: yield})"""
    res = {}
    live = {}
    for f in g["frames"]:
        t = f["t"]
        a = f.get("a") or {}
        cmds = [a.get("farmer")] + list(a.get("hands") or [])
        acted = defaultdict(list)
        for u, c in enumerate(cmds):
            if c and u < len(f["u"]) and c[0] in WORK:
                x, y = f["u"][u]
                acted[y * 10 + x].append(c[0])
        board = [g["tiles"][i] for i in f["b"]]
        seen = set()
        for i, x in enumerate(board):
            if isinstance(x, dict) and x.get("crop") in CROPS and x.get("planted_day") is not None:
                key = (i, x["crop"], int(x["planted_day"]))
                seen.add(key)
                c = live.get(key)
                if c is None:
                    c = live[key] = dict(ops=[], yields={}, end=None, first_seen=t)
                c["yields"][t] = int(x.get("yield_units", 0) or 0)
                for op in acted.get(i, ()):
                    c["ops"].append((t, op))
        for key in [k for k in live if k not in seen]:
            c = live.pop(key)
            for op in acted.get(key[0], ()):          # the step that removed it (HARVEST / DIG)
                c["ops"].append((f["t"], op))
            c["end"] = f["t"]
            if key[2] >= d0:
                res[key] = c
    for key, c in live.items():
        if key[2] >= d0:
            res[key] = c
    return res


def audit_onetime(key, c, cr):
    loss = Counter()
    info = Counter()
    p = key[2]
    w0, w1 = (cr["maxday"] + 1) // 2, cr["maxday"]
    ops = sorted(c["ops"])
    ferts = [s for s, o in ops if o == "FERTILIZE"]
    harvest = next((s for s, o in ops if o == "HARVEST"), None)
    end_day = (harvest // 24) if harvest is not None else ((c["end"] // 24) if c["end"] is not None else 30)
    y = 1
    useful_fert = set()
    for d in range(p + w0, min(p + w1, end_day) + 1):
        day_ops = [(s, o) for s, o in ops if s // 24 == d]
        waters = [s for s, o in day_ops if o == "WATER"]
        hv = [s for s, o in day_ops if o == "HARVEST"]
        cover = [f for f in ferts if f // 24 <= d <= f // 24 + 2]
        if hv and (not waters or min(waters) > min(hv)):
            if y < cr["max"] and d <= p + w1:
                add = 2 if any(f < min(hv) for f in cover) or any(f // 24 < d for f in cover) else 1
                loss["harvest_before_water"] += min(add, cr["max"] - y)
                info["harvests_before_water"] += 1
            break
        if not waters:
            if d < end_day or harvest is None:
                add = 2 if cover else 1
                loss["window_day_dry"] += min(add, cr["max"] - y)
                info["dry_window_days"] += 1
            continue
        s = min(waters)
        fert_now = [f for f in cover if f < s]
        if fert_now:
            useful_fert.update(fert_now)
            y = min(cr["max"], y + 2)
            info["waters_fertilized"] += 1
        else:
            if any(f // 24 == d and f > s for f in ferts):
                loss["fert_after_water"] += min(1, cr["max"] - y - 1) if y + 1 < cr["max"] else 0
                info["fert_after_water"] += 1
            elif y + 1 < cr["max"]:
                loss["water_unfertilized"] += 1
            info["waters_unfertilized"] += 1
            y = min(cr["max"], y + 1)
    for f in ferts:
        if f not in useful_fert:
            loss["fert_wasted_units"] += 0
            info["fert_wasted"] += 1
    info["cohorts"] += 1
    info["model_units"] += y
    obs = [v for s, v in sorted(c["yields"].items()) if harvest is None or s < harvest]
    info["observed_units"] += obs[-1] if obs else 0
    return loss, info


def audit_ongoing(key, c, cr):
    loss = Counter()
    info = Counter()
    p = key[2]
    ops = sorted(c["ops"])
    ferts = [s for s, o in ops if o == "FERTILIZE"]
    useful = set()
    end_day = (c["end"] // 24) if c["end"] is not None else 30
    for k in range(cr["prods"]):
        d = p + cr["first"] - 1 + k * cr["interval"]          # production at the end of day d (engine next_day = d + 1)
        if d >= end_day or d > 28:
            break
        watered = any(o == "WATER" and s // 24 == d for s, o in ops)
        cover = [f for f in ferts if f // 24 <= d <= f // 24 + 2]
        info["productions"] += 1
        if watered and cover:
            useful.update(cover)
            info["prod_2"] += 1
        elif cover and not watered:
            loss["prod_fert_dry"] += 1
            info["prod_1"] += 1
        elif watered and not cover:
            loss["prod_water_nofert"] += 1
            info["prod_1"] += 1
        else:
            loss["prod_neither"] += 1
            info["prod_1"] += 1
        before = [v for s, v in sorted(c["yields"].items()) if s // 24 == d]
        after = [v for s, v in sorted(c["yields"].items()) if s // 24 == d + 1]
        if before and after:
            add = 2 if (watered and cover) else 1
            y_end = before[-1]
            if y_end + add > cr["max"]:
                loss["prod_overflow"] += y_end + add - cr["max"]
    for f in ferts:
        if f not in useful:
            info["fert_wasted"] += 1
    info["cohorts"] += 1
    return loss, info


def main():
    a = sys.argv
    cids = a[1].split(",")
    keys = [x for x in a[2:] if not x.startswith("--") and not x.isdigit()]
    d0 = int(a[a.index("--from") + 1]) if "--from" in a else 6
    for key in keys:
        L, I = defaultdict(Counter), defaultdict(Counter)
        n = 0
        for cid in cids:
            f = OUT / f"{cid}.{key}.game.json.gz"
            if not f.exists():
                continue
            n += 1
            g = json.loads(gzip.open(f, "rt", encoding="utf-8").read())
            for k, c in cohorts(g, d0).items():
                cr = CROPS[k[1]]
                l_, i_ = (audit_ongoing if cr["ongoing"] else audit_onetime)(k, c, cr)
                L[k[1]].update(l_)
                I[k[1]].update(i_)
        print(f"== {key}: {n} world(s), cohorts planted from day {d0}; per world")
        for crop in ("WHEAT", "CARROT", "MELON", "STRAWBERRY", "TOMATO"):
            if not I[crop]:
                continue
            li = ", ".join(f"{k} {v / n:.1f}" for k, v in sorted(L[crop].items(), key=lambda kv: -kv[1]) if v)
            ii = ", ".join(f"{k} {v / n:.1f}" for k, v in sorted(I[crop].items()))
            print(f"  {crop:10s} units lost: {li or '-'}\n  {'':10s} counts: {ii}")


if __name__ == "__main__":
    main()

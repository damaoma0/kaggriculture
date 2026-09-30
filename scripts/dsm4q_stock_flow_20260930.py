"""Stock / flow gap on days 9-10 after the exact day-8 handover (user 2026-09-30: "why do we lose in stockpile?"; then
"all are fixable. Please try to do this"): per paired world, ours vs the new DSM's
  - pens per day: animals at the day's last frame, fed / cared that day, pens harvested (held yield dropped), escapes
    (an animal tile that lost its animal between frames);
  - goods on days 9-10: produced (ledger produced:X), sold, revenue, shed at the day-9 and day-11 dawns;
  - feed wheat: units bought (market orders), FEED ops, wheat in the shed at the day-11 dawn;
  - melons: ripe tiles harvested on day 10 and units per harvested tile.
Only exact handovers (identical day-9 dawn board) count, as in dsm4q_d11_board_20260930.

usage: dsm4q_stock_flow_20260930.py ARM[,ARM...]   (per-world arm names use {ep}; fold pairs "a|b")"""
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsm4q_d11_board_20260930 import load, label  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
FLOW = ("WHEAT", "MELON", "MILK", "EGG", "WOOL", "FERTILIZER", "STRAWBERRY")


def tile(g, fr, i):
    t = g["tiles"][fr["b"][i]]
    return t if isinstance(t, dict) else {}


def flows(g):
    s = g["seat"]
    D9, D11 = g["daily"][s][9], g["daily"][s][11]
    out = Counter()
    for p in FLOW:
        out["produced:" + p] = D11["physical"].get("produced:" + p, 0) - D9["physical"].get("produced:" + p, 0)
        out["sold:" + p] = D11["sold_units"].get(p, 0) - D9["sold_units"].get(p, 0)
        out["revenue:" + p] = D11["revenue"].get(p, 0) - D9["revenue"].get(p, 0)
        out["shed9:" + p] = (g["frames"][216].get("sh") or {}).get(p, 0)
        out["shed11:" + p] = (g["frames"][264].get("sh") or {}).get(p, 0)
    out["fed_ops"] = D11["physical"].get("op:FEED", 0) - D9["physical"].get("op:FEED", 0)
    out["wheat_spend"] = D11["spend"].get("BUY_PRODUCT:WHEAT", 0) - D9["spend"].get("BUY_PRODUCT:WHEAT", 0)
    for t in range(216, 264):
        for o in ((g["frames"][t].get("a") or {}).get("market") or []):
            if o and o[0] == "BUY_PRODUCT" and o[1] == "WHEAT":
                out["wheat_bought"] += int(o[2])
    for day in (9, 10):
        last = g["frames"][24 * day + 23]
        for i in range(100):
            t = tile(g, last, i)
            if t.get("animal"):
                out[f"d{day}:pens"] += 1
                out[f"d{day}:fed"] += bool(t.get("fed_today"))
                out[f"d{day}:cared"] += bool(t.get("cared_today"))
        harvested = set()
        for k in range(24 * day, 24 * day + 24):
            a, b = g["frames"][k], g["frames"][k + 1]
            for i in range(100):
                ta, tb = tile(g, a, i), tile(g, b, i)
                if ta.get("animal"):
                    if not tb.get("animal"):
                        out[f"d{day}:escaped:" + ta["animal"]] += 1
                    elif k % 24 != 23 and int(tb.get("yield_units", 0) or 0) < int(ta.get("yield_units", 0) or 0):
                        harvested.add(i)
                if day == 10 and ta.get("crop") == "MELON" and not tb.get("crop"):
                    out["melon_tiles_harvested"] += 1
                    out["melon_units_harvested"] += int(ta.get("yield_units", 0) or 0)
        out[f"d{day}:pens_harvested"] = len(harvested)
    return out


def main():
    arms = sys.argv[1].split(",")
    cases = json.loads((ROOT / "results/fresh/dsm4q_d9_20260930/cases.json").read_text("utf-8"))["cases"]
    res = {a: [] for a in arms}
    for c in cases:
        d = load(c["id"], "dsm")
        games = {}
        for a in arms:
            g = None
            for alt in a.split("|"):
                g = g or load(c["id"], alt.replace("{ep}", c["episode"]) + ".p216")
            games[a] = g
        if not d or not all(games.values()):
            continue
        if any([label(t) for t in [g["tiles"][i] for i in g["frames"][216]["b"]]]
               != [label(t) for t in [d["tiles"][i] for i in d["frames"][216]["b"]]] for g in games.values()):
            continue                                   # exact handovers only
        fd = flows(d)
        for a, g in games.items():
            res[a].append((flows(g), fd))
    for a, rows in res.items():
        n = len(rows)
        if not n:
            continue
        m = lambda k, i: st.mean(r[i][k] for r in rows)  # noqa: E731
        print(f"== {a} ({n} paired worlds), per world: ours | DSM")
        for day in (9, 10):
            esc = {k.split(":")[-1] for r in rows for x in r for k in x if k.startswith(f"d{day}:escaped:")}
            print(f"   day {day} pens {m(f'd{day}:pens', 0):5.1f}|{m(f'd{day}:pens', 1):5.1f}  fed {m(f'd{day}:fed', 0):5.1f}|"
                  f"{m(f'd{day}:fed', 1):5.1f}  cared {m(f'd{day}:cared', 0):5.1f}|{m(f'd{day}:cared', 1):5.1f}  harvested "
                  f"{m(f'd{day}:pens_harvested', 0):5.1f}|{m(f'd{day}:pens_harvested', 1):5.1f}  escaped "
                  + (", ".join(f"{sp} {m(f'd{day}:escaped:' + sp, 0):.1f}|{m(f'd{day}:escaped:' + sp, 1):.1f}" for sp in sorted(esc))
                     or "none"))
        for p in FLOW:
            print(f"   {p:10s} produced {m('produced:' + p, 0):5.1f}|{m('produced:' + p, 1):5.1f}  sold {m('sold:' + p, 0):5.1f}|"
                  f"{m('sold:' + p, 1):5.1f} (${m('revenue:' + p, 0):6.0f}|${m('revenue:' + p, 1):6.0f})  shed d9 dawn "
                  f"{m('shed9:' + p, 0):5.1f}|{m('shed9:' + p, 1):5.1f}  d11 dawn {m('shed11:' + p, 0):5.1f}|{m('shed11:' + p, 1):5.1f}")
        print(f"   feed wheat bought {m('wheat_bought', 0):5.1f}|{m('wheat_bought', 1):5.1f} units (${m('wheat_spend', 0):5.0f}|"
              f"${m('wheat_spend', 1):5.0f})  FEED ops {m('fed_ops', 0):5.1f}|{m('fed_ops', 1):5.1f}")
        mt0, mt1 = m("melon_tiles_harvested", 0), m("melon_tiles_harvested", 1)
        print(f"   day-10 melon tiles harvested {mt0:4.1f}|{mt1:4.1f}  units / tile "
              f"{m('melon_units_harvested', 0) / max(mt0, 1e-9):4.2f}|{m('melon_units_harvested', 1) / max(mt1, 1e-9):4.2f}"
              "  (yield before the harvest frame; the water-then-harvest bonus lands in the same step)")


if __name__ == "__main__":
    main()

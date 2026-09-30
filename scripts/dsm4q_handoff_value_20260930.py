"""Handoff gap in cash and potential goods (user 2026-09-30: "What is the handoff gap in terms of cash and potential goods
produced?"): our state vs the new DSM's at the day-11 dawn (step 264) after the exact day-8 handover, per paired world.
Valued at DSM's own day-11 market prices (the frame's quotes) so both sides use one price vector:
  cash; stock = shed goods (+ seeds at seed cost); crops = the harvests each standing plant still has (wheat 4, carrot 3,
  melon 6 units - or its current yield once ripe; strawberry / tomato 1 unit per production left, 4 productions);
  animals = products over the rest of the season (days 11-29: cow 1 milk per 2 days, sheep 1 wool per 3, goose 1 egg a
  day, from their first production day) plus what they hold now. Units are unfertilized base yields: a common yardstick,
  not a forecast. bank (added 2026-09-30, reported beside the total, not in it): the care bonus the animals have banked
  (pending_care_bonus units, paid at the next production when the animal is fed that day) - what feed + care visits buy.

usage: dsm4q_handoff_value_20260930.py ARM[,ARM...]   (per-world arm names use {ep}; fold pairs "a|b")"""
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dsm4q_d11_board_20260930 import load, label  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GOODS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
SEED = dict(WHEAT=10, CARROT=20, TOMATO=50, STRAWBERRY=100, MELON=80)
ONE = dict(WHEAT=(2, 4), CARROT=(2, 3), MELON=(10, 6))              # first-yield age, units
ONGOING = dict(STRAWBERRY=(10, 2), TOMATO=(8, 1))                   # first production age, interval (4 productions)
ANIMAL = dict(COW=("MILK", 8, 2), SHEEP=("WOOL", 6, 3), GOOSE=("EGG", 4, 1))
DAY, END = 11, 29


def value(g, prices):
    fr = g["frames"][24 * DAY]
    out = Counter(cash=fr["m"][0])
    for k, v in (fr.get("sh") or {}).items():
        if k in prices:
            out["stock"] += v * prices[k]
            out["units:" + k] += v
    for i in fr["b"]:
        t = g["tiles"][i]
        if not isinstance(t, dict):
            continue
        if t.get("crop"):
            c, age, yu = t["crop"], DAY - int(t.get("planted_day", DAY)), int(t.get("yield_units", 0) or 0)
            if c in ONE:
                first, units = ONE[c]
                u = yu if (age >= first and yu > 0) else units
            else:
                first, iv = ONGOING[c]
                prods = [first + iv * n for n in range(4)]
                u = sum(1 for a in prods if a >= age and DAY + (a - age) <= END) + yu
            out["crops"] += u * prices[c]
            out["units:" + c] += u
        elif t.get("animal"):
            prod, first, iv = ANIMAL[t["animal"]]
            placed = int(t.get("placed_day", DAY))
            u = int(t.get("yield_units", 0) or 0)
            for d in range(DAY, END + 1):
                ds = d + 1 - placed - first
                if ds >= 0 and ds % iv == 0:
                    u += 1
            out["animals"] += u * prices[prod]
            out["units:" + prod] += u
            out["bank"] += int(t.get("pending_care_bonus", 0) or 0) * prices[prod]
            out["units:bank:" + prod] += int(t.get("pending_care_bonus", 0) or 0)
    out["total"] = out["cash"] + out["stock"] + out["crops"] + out["animals"]
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
        prices = dict(zip(GOODS, d["frames"][24 * DAY]["p"]))
        vd = value(d, prices)
        for a, g in games.items():
            res[a].append((value(g, prices), vd))
    for a, rows in res.items():
        n = len(rows)
        if not n:
            continue
        m = lambda k, i: st.mean(r[i][k] for r in rows)  # noqa: E731
        print(f"== {a} ({n} paired worlds): value at the day-11 dawn, ours | DSM | gap")
        for k in ("cash", "stock", "crops", "animals", "total", "bank"):
            print(f"   {k:8s} {m(k, 0):8.0f} | {m(k, 1):8.0f} | {m(k, 0) - m(k, 1):+8.0f}" + ("   (not in total)" if k == "bank" else ""))
        units = sorted({k for r in rows for x in r for k in x if k.startswith("units:")})
        print("   potential units ours | DSM: " + ", ".join(f"{k[6:]} {m(k, 0):.0f}|{m(k, 1):.0f}" for k in units))


if __name__ == "__main__":
    main()

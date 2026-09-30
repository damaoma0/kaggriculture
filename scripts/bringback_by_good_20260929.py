"""Bring-back by type of good (user 2026-09-29: "bring-back runs and prices strongly correlate"; "can we also analyze
bring-back by type of good"), from item traces (scripts/item_trace_20260929.py: every unit's harvest tick, how it
reached the shed - a mid-day drop or the midnight dump - and its sale tick / price).

Per good and side (days 6-28 harvests):
  produced         units a game
  same-day         brought back mid-day and sold on the harvest day: share and average price
  dump             reached the shed at the midnight dump: share and average price
  harvest hour     median hour the dumped units were harvested (late harvests cannot come home much earlier)
  bring-back value for every dumped unit sold: the market price on its harvest day from 2 ticks after the harvest to
                   hour 23 (its best same-day price, and the average) minus its actual sale price - what bringing it
                   home that day was worth before our own extra supply lowers the price (an upper bound)

usage: bringback_by_good_20260929.py ITEMS.json [ITEMS.json ...]"""
import json
import statistics
import sys
from collections import defaultdict

GOODS = ("STRAWBERRY", "MILK", "WOOL", "MELON", "EGG", "TOMATO", "CARROT", "WHEAT", "FERTILIZER")


def main():
    files = sys.argv[1:]
    n = len(files)
    A = {side: defaultdict(lambda: defaultdict(list)) for side in ("ours", "leader")}
    for f in files:
        R = json.load(open(f))
        G = R["goods"]
        px = {r[0]: r[1:1 + len(G)] for r in R["market"]}
        for side in ("ours", "leader"):
            for it in R["items"][side]:
                g, t = it["p"], it["t_prod"]
                if not (6 * 24 <= t < 29 * 24) or g not in GOODS:
                    continue
                a = A[side][g]
                a["prod"].append(1)
                if it["route"] == "used":
                    a["used"].append(1)
                    continue
                if it["t_sold"] is None:
                    a["unsold"].append(1)
                    continue
                if it["route"] == "drop" and it["t_sold"] // 24 == t // 24:
                    a["same"].append(it["price"])
                elif it["route"] == "drop":
                    a["drop_later"].append(it["price"])
                else:
                    a["dump"].append(it["price"])
                    a["dump_hour"].append(t % 24)
                    j = G.index(g)
                    day_end = (t // 24) * 24 + 23
                    ps = [px[s][j] for s in range(t + 2, day_end + 1) if s in px]
                    if ps:
                        a["cf_best"].append(max(ps) - it["price"])
                        a["cf_avg"].append(statistics.mean(ps) - it["price"])
    print(f"{n} games, harvests days 6-28, per game")
    hdr = (f"{'good':10s} {'side':6s} {'prod':>5s} | {'same-day':>14s} | {'drop later':>12s} | {'dump':>14s} | "
           f"{'dump harvest h':>14s} | bring-back value of dumped units (per unit / per game): day-avg, day-best")
    print(hdr)
    for g in GOODS:
        for side in ("ours", "leader"):
            a = A[side][g]
            P = len(a["prod"])
            if not P:
                continue
            sold = len(a["same"]) + len(a["drop_later"]) + len(a["dump"])
            f = lambda L: f"{len(L) / max(1, sold):4.0%} @{(sum(L) / len(L)) if L else 0:5.0f}"
            cfa = (sum(a["cf_avg"]) / len(a["cf_avg"])) if a["cf_avg"] else 0
            cfb = (sum(a["cf_best"]) / len(a["cf_best"])) if a["cf_best"] else 0
            mh = statistics.median(a["dump_hour"]) if a["dump_hour"] else 0
            print(f"{g:10s} {side:6s} {P / n:5.0f} | {f(a['same']):>14s} | {f(a['drop_later']):>12s} | {f(a['dump']):>14s} | "
                  f"{mh:14.0f} | {cfa:+6.1f} / {cfa * len(a['cf_avg']) / n:+6.0f}, {cfb:+6.1f} / {cfb * len(a['cf_best']) / n:+6.0f}")


if __name__ == "__main__":
    main()

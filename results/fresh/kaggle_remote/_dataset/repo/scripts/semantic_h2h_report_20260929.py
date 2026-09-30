"""Shortfall report for semantic-strategy head-to-head games (harness result JSONs: <case>.json with daily ledgers of both
seats). Candidate = the case's seat, opponent = the other seat (packaged mgt_v9lite in live games).

Per game: validity, margin, cash at days 6 / 11 / 12 / 18 / 24 / 30 (both seats), time bank. Aggregated over valid games
(candidate minus opponent, per game): margin by phase (the day the gap opens), revenue and units sold by product, spending
by category, physical counters (commands, failures, PASS), and the list of the largest per-game items.

usage: semantic_h2h_report_20260929.py DIR [DIR ...]"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PHASES = (6, 11, 12, 18, 24, 30)


def rows(dirs):
    out = []
    for d in dirs:
        for p in sorted(Path(d).glob("*.json")):
            if p.name.endswith(".actions.json") or p.name == "summary.json":
                continue
            try:
                r = json.loads(p.read_text())
            except Exception:
                continue
            if isinstance(r, dict) and "case" in r and "daily" in r:
                r["_file"] = str(p)
                out.append(r)
    return out


def main():
    R = rows(sys.argv[1:])
    print(f"{len(R)} games")
    agg = defaultdict(Counter)
    n = 0
    print(f"{'case':14s} {'seat':>4s} {'valid':>5s} {'margin':>8s} | margin by day " + " ".join(f"{d:>7d}" for d in PHASES)
          + " | bank used (cand, opp)")
    for r in R:
        seat = int(r["case"]["seat"])
        opp = 1 - seat
        daily = r["daily"]
        ph = [daily[seat][d]["money"] - daily[opp][d]["money"] for d in PHASES]
        ou = r.get("measured_overage_used") or [0, 0]
        print(f"{r['case']['id']:14s} {seat:4d} {str(bool(r.get('eligible'))):>5s} {r.get('margin', 0):+8.0f} | "
              + " ".join(f"{x:+7.0f}" for x in ph) + f" | {ou[seat]:.0f}, {ou[opp]:.0f}"
              + ("" if r.get("eligible") else f"  ERR {str(r.get('error') or r.get('opponent_health_failure'))[-120:]}"))
        if not r.get("eligible"):
            continue
        n += 1
        a, b = daily[seat][-1], daily[opp][-1]
        for d, x in zip(PHASES, ph):
            agg["phase"][d] += x
        for k in set(a["revenue"]) | set(b["revenue"]):
            agg["rev"][k] += a["revenue"].get(k, 0) - b["revenue"].get(k, 0)
            agg["rev_c"][k] += a["revenue"].get(k, 0)
            agg["rev_o"][k] += b["revenue"].get(k, 0)
        for k in set(a["sold_units"]) | set(b["sold_units"]):
            agg["units"][k] += a["sold_units"].get(k, 0) - b["sold_units"].get(k, 0)
        for k in set(a["spend"]) | set(b["spend"]):
            agg["spend"][k] += a["spend"].get(k, 0) - b["spend"].get(k, 0)
            agg["spend_c"][k] += a["spend"].get(k, 0)
            agg["spend_o"][k] += b["spend"].get(k, 0)
        for k in set(a["physical"]) | set(b["physical"]):
            agg["phys_c"][k] += a["physical"].get(k, 0)
            agg["phys_o"][k] += b["physical"].get(k, 0)
        agg["wins"]["n"] += r["margin"] > 0
        agg["margin"]["sum"] += r["margin"]
    if not n:
        return
    print(f"\nvalid {n}: wins {agg['wins']['n']}/{n}, mean margin {agg['margin']['sum'] / n:+.0f}")
    print("mean margin (candidate - opponent) at the start of day: " + ", ".join(f"d{d} {agg['phase'][d] / n:+.0f}" for d in PHASES))
    print("\nrevenue by product, mean per game: candidate / opponent / difference (units difference)")
    for k, v in sorted(agg["rev"].items(), key=lambda z: z[1]):
        print(f"   {k:12s} {agg['rev_c'][k] / n:9.0f} {agg['rev_o'][k] / n:9.0f} {v / n:+9.0f}  ({agg['units'][k] / n:+.1f} u)")
    print("spending by category, mean per game: candidate / opponent / difference (positive = candidate spends more)")
    for k, v in sorted(agg["spend"].items(), key=lambda z: -abs(z[1])):
        print(f"   {k:12s} {agg['spend_c'][k] / n:9.0f} {agg['spend_o'][k] / n:9.0f} {v / n:+9.0f}")
    print("physical counters, mean per game: candidate / opponent")
    for k in sorted(set(agg["phys_c"]) | set(agg["phys_o"])):
        print(f"   {k:24s} {agg['phys_c'][k] / n:9.1f} {agg['phys_o'][k] / n:9.1f}")


if __name__ == "__main__":
    main()

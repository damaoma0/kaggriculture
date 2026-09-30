"""Report the semantic-stack arms (sem_arms_20260929.py variants) against a baseline candidate, per panel: wins, mean
margin, the paired margin change per case, and where the change comes from (own / rival cash, day-12 cash, revenue by
product and spending by kind from the harness's daily ledgers; melon units sold by day 10 and 11).

usage: sem_arms_report_20260929.py [--base strategy_v13_kb115lt2_harvest_exchange] [--panels arms_fresh8,arms_dev]
       [--root results/fresh/semantic_h2h_20260929]"""
import argparse
import glob
import json
import os
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(d):
    out = {}
    for f in glob.glob(os.path.join(d, "*.json")):
        if f.endswith(".actions.json") or f.endswith("summary.json"):
            continue
        r = json.load(open(f))
        if r.get("completed") and r.get("margin") is not None:
            out[r["case"]["id"]] = r
    return out


def ledger(r, side, day=30):
    seat = r["case"]["seat"] if side == "own" else 1 - r["case"]["seat"]
    return r["daily"][seat][min(day, len(r["daily"][seat]) - 1)]


def spend_kind(k):
    if k.startswith("BUY_ANIMAL"):
        return "animals"
    if k.startswith("BUY_SEED"):
        return "seeds"
    if k.startswith("BUY_PRODUCT"):
        return "buy " + k.split(":")[1].lower()
    return {"HIRE": "hires", "BUY_LAND": "land"}.get(k, k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="strategy_v13_kb115lt2_harvest_exchange")
    ap.add_argument("--panels", default="arms_fresh8_fs,arms_dev_fs")
    ap.add_argument("--root", default="results/fresh/semantic_h2h_20260929")
    a = ap.parse_args()
    for panel in a.panels.split(","):
        P = ROOT / a.root / panel
        if not P.is_dir():
            continue
        arms = sorted(p.name for p in P.iterdir() if p.is_dir())
        base = rows(P / a.base)
        print(f"\n=== {panel}: baseline {a.base} {len(base)} games, wins {sum(r['margin'] > 0 for r in base.values())}, "
              f"mean {st.mean([r['margin'] for r in base.values()]) if base else float('nan'):+.0f}")
        print(f"{'arm':40s} {'n':>2s} {'wins':>5s} {'mean':>7s} | {'paired':>7s} {'better/worse':>12s} {'own':>7s} {'rival':>7s} "
              f"{'d12 own':>7s} | melon d10 u (base)")
        for arm in arms:
            R = rows(P / arm)
            common = sorted(set(R) & set(base))
            dm = [R[c]["margin"] - base[c]["margin"] for c in common]
            do = [R[c]["cash"] - base[c]["cash"] for c in common]
            dr = [R[c]["opponent_cash"] - base[c]["opponent_cash"] for c in common]
            d12 = [R[c]["phase_cash"]["12"][R[c]["case"]["seat"]] - base[c]["phase_cash"]["12"][base[c]["case"]["seat"]]
                   for c in common]
            mel = [ledger(R[c], "own", 11)["sold_units"].get("MELON", 0) for c in common]      # dawn of day 11 = through day 10
            melb = [ledger(base[c], "own", 11)["sold_units"].get("MELON", 0) for c in common]
            m = lambda x: st.mean(x) if x else float("nan")
            print(f"{arm:40s} {len(R):2d} {sum(r['margin'] > 0 for r in R.values()):2d}/{len(R):<2d} "
                  f"{m([r['margin'] for r in R.values()]):+7.0f} | {m(dm):+7.0f} {sum(x > 0 for x in dm):5d}/{sum(x < 0 for x in dm):<6d} "
                  f"{m(do):+7.0f} {m(dr):+7.0f} {m(d12):+7.0f} | {m(mel):4.1f} ({m(melb):4.1f})")
            if arm == a.base or not common:
                continue
            rev, spd, rrev = Counter(), Counter(), Counter()
            for c in common:
                for k, v in ledger(R[c], "own")["revenue"].items():
                    rev[k] += v / len(common)
                for k, v in ledger(base[c], "own")["revenue"].items():
                    rev[k] -= v / len(common)
                for k, v in ledger(R[c], "rival")["revenue"].items():
                    rrev[k] += v / len(common)
                for k, v in ledger(base[c], "rival")["revenue"].items():
                    rrev[k] -= v / len(common)
                for k, v in ledger(R[c], "own")["spend"].items():
                    spd[spend_kind(k)] += v / len(common)
                for k, v in ledger(base[c], "own")["spend"].items():
                    spd[spend_kind(k)] -= v / len(common)
            print("      revenue change: " + ", ".join(f"{k.lower()} {v:+.0f}" for k, v in sorted(rev.items(), key=lambda x: -abs(x[1])) if abs(v) >= 50))
            print("      rival revenue:  " + ", ".join(f"{k.lower()} {v:+.0f}" for k, v in sorted(rrev.items(), key=lambda x: -abs(x[1])) if abs(v) >= 50))
            print("      spend change:   " + ", ".join(f"{k} {v:+.0f}" for k, v in sorted(spd.items(), key=lambda x: -abs(x[1])) if abs(v) >= 50))
            print("      per case: " + " ".join(f"{c}:{R[c]['margin'] - base[c]['margin']:+.0f}" for c in common))


if __name__ == "__main__":
    main()

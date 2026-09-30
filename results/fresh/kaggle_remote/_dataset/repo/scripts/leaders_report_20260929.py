"""Report the recorded-leader panels (build_leader_recorded_20260929.py cases; semantic_h2h_20260929.py run with and
without --leader-credit): per mode (normal engine = our upper bound, leader credit = our lower bound), candidate and
leader team: valid games (completed, leader commands not materially broken; the research-mode runtime flag is
ignored), wins, mean margin, the replaced team's own recorded margin in the same games, and paired candidate changes.

usage: leaders_report_20260929.py [--root results/fresh/semantic_h2h_20260929] [--base strategy_v13_kb115lt2_harvest_exchange]"""
import argparse
import glob
import json
import os
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(d):
    out = {}
    for f in glob.glob(os.path.join(d, "*.json")):
        if f.endswith((".actions.json", ".spawns.json", "summary.json")):
            continue
        r = json.load(open(f))
        if isinstance(r, dict) and r.get("completed") and r.get("margin") is not None:
            out[r["case"]["id"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/fresh/semantic_h2h_20260929")
    ap.add_argument("--base", default="strategy_v13_kb115lt2_harvest_exchange")
    a = ap.parse_args()
    m = lambda x: st.mean(x) if x else float("nan")
    for mode, label in (("leadersw_normal", "normal engine + recorded weeds (our upper bound)"), ("leadersw_credit", "leader credit + recorded weeds (our lower bound)")):
        P = ROOT / a.root / mode
        if not P.is_dir():
            continue
        controls = load(P / "_controls")
        arms = sorted(p.name for p in P.iterdir() if p.is_dir() and not p.name.startswith("_"))
        runs = {arm: load(P / arm) for arm in arms}
        print(f"\n=== {label}: {len(controls)} source controls")
        for team in ("DSM", "M & M & P & Q"):
            ids = sorted(c for c, r in controls.items() if r["case"].get("opponent") == team)
            rec = [controls[c]["margin"] for c in ids]
            print(f"  vs {team} ({len(ids)} games): replaced teams' own recorded margin {m(rec):+.0f}, "
                  f"wins {sum(x > 0 for x in rec)}/{len(ids)}")
            base = runs.get(a.base, {})
            for arm in arms:
                R = runs[arm]
                ok = [c for c in ids if c in R and not (R[c].get("recorded_rival_audit") or {}).get("material_command_break")]
                broken = [c for c in ids if c in R and c not in ok]
                mm = [R[c]["margin"] for c in ok]
                rep_ = [controls[c]["margin"] for c in ok]
                vs_rep = [R[c]["margin"] - controls[c]["margin"] for c in ok]
                line = (f"    {arm:40s} valid {len(ok):2d} (broken {len(broken)}) wins {sum(x > 0 for x in mm):2d}/{len(ok):<2d} "
                        f"mean {m(mm):+7.0f} | same games, real opponent {m(rep_):+7.0f} -> ours better by {m(vs_rep):+6.0f} "
                        f"({sum(x > 0 for x in vs_rep)}/{sum(x < 0 for x in vs_rep)})")
                if arm != a.base:
                    pair = [R[c]["margin"] - base[c]["margin"] for c in ok if c in base
                            and not (base[c].get("recorded_rival_audit") or {}).get("material_command_break")]
                    line += f" | vs {a.base[:12]}: {m(pair):+6.0f} ({sum(x > 0 for x in pair)}/{sum(x < 0 for x in pair)})"
                print(line)


if __name__ == "__main__":
    main()

"""Leaders / ladder panel report (2026-09-29): per arm the games, wins, mean margin and, against a base arm, the paired
difference (mean, better / worse, win flips) overall and by opponent family (case id prefix, e.g. lead-dsm / lead-mmpq).

usage: panel_arms_report_20260929.py DIR ARM [ARM ...] [--base n18rc8]"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(d):
    out = {}
    for p in d.glob("*.json"):
        if p.name.endswith(".actions.json") or p.name.endswith(".spawns.json"):
            continue
        x = json.loads(p.read_text())
        if isinstance(x, dict) and x.get("margin") is not None:
            out[p.stem] = float(x["margin"])
    return out


def fam(cid):
    parts = cid.split("-")
    return "-".join(parts[:2]) if len(parts) > 2 else parts[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("arms", nargs="+")
    ap.add_argument("--base", default="n18rc8")
    a = ap.parse_args()
    d = ROOT / a.dir
    base = load(d / a.base)
    for arm in [a.base] + [x for x in a.arms if x != a.base]:
        r = load(d / arm)
        if not r:
            print(arm, "no results")
            continue
        n = len(r)
        w = sum(1 for v in r.values() if v > 0)
        line = f"{arm:10s} n={n:3d} wins {w:3d} ({w / n:.0%}) mean {sum(r.values()) / n:+8.0f}"
        common = [k for k in r if k in base]
        if arm != a.base and common:
            dd = [r[k] - base[k] for k in common]
            flips = sum(1 for k in common if (r[k] > 0) != (base[k] > 0))
            wb = sum(1 for k in common if r[k] > 0) - sum(1 for k in common if base[k] > 0)
            line += (f" | vs {a.base} n={len(common)} {sum(dd) / len(dd):+7.0f} better {sum(1 for x in dd if x > 0)}"
                     f" / worse {sum(1 for x in dd if x < 0)}, wins {wb:+d} ({flips} flips)")
            by = defaultdict(list)
            for k in common:
                by[fam(k)].append(r[k] - base[k])
            line += " | " + " ".join(f"{f} {sum(v) / len(v):+.0f} (n={len(v)})" for f, v in sorted(by.items()))
        print(line)


if __name__ == "__main__":
    main()

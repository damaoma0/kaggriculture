"""DSM's selling PACE rebuilt from its CURRENT submission (56619023) - the executor's pace table
(results/fresh/threads_20260928/dsm_sell_pace.json) comes from 40 games of DSM 56498734, the 4-quadrant version. Same
construction as scripts/dsm_sell_pace.py (its job() is reused unchanged); the recorded-leader panel episodes are held out.

usage: dsm_sell_pace_c_20260929.py <out.json> [--limit N]"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dsm_sell_pace as P  # noqa: E402

if __name__ == "__main__":
    out = sys.argv[1]
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    held = {str(c["episode"]) for c in json.loads((ROOT / "results/fresh/semantic_h2h_20260929/leaders_cases.json").read_text())["cases"]}
    eps = sorted(p.name.split(".")[0] for p in (ROOT / "data/leader_tapes/16732748_56619023").glob("*.json.gz"))
    games = [f"16732748:{e}" for e in eps if e not in held][:lim]
    A2, S2, A1, S1 = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(float)
    for g in games:
        for D, X in zip((A2, S2, A1, S1), P.job(g)):
            for k, v in X.items():
                D[k] += v
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"p2": {k: S2[k] / A2[k] for k in A2 if A2[k] >= 20}, "p1": {k: S1[k] / A1[k] for k in A1 if A1[k] >= 20},
               "n": dict(A1), "games": len(games), "source": "DSM 56619023, leader-panel episodes held out"}, open(out, "w"))
    print(len(games), "games ->", out)

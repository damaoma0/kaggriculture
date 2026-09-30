"""Fertilizer sourcing per game from the stored ledger round (results/fresh/lead_ledger/<side>_<episode>.json, written
2026-09-25 08:14, i.e. BEFORE fert_hold 1 became the deploy default): leader (recorded actions) vs ours (leader-plan
agent mgt_lead) vs deploy (then-current deploy, fert_hold 0). Per game: fertilizer picked up at the shed, fertilizer
deposited at the shed, COLLECT_FERTILIZER and FERTILIZE effective ops. One file at a time. No game runs.
Output: verify_code_audit_ledger.json next to this file.
"""
import glob
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
agg = defaultdict(lambda: defaultdict(float))
n = defaultdict(int)
seats = defaultdict(list)
for p in sorted(glob.glob(str(ROOT / "results/fresh/lead_ledger/*.json"))):
    g = json.load(open(p, encoding="utf-8"))
    side = g["side"]
    n[side] += 1
    seats[side].append((g["episode"], g["seat"]))
    for day in g["days"]:
        agg[side]["picked_FERTILIZER"] += day.get("picked", {}).get("FERTILIZER", 0)
        agg[side]["deposited_FERTILIZER"] += day.get("deposited", {}).get("FERTILIZER", 0)
        agg[side]["COLLECT_FERTILIZER"] += day.get("eff", {}).get("COLLECT_FERTILIZER", 0)
        agg[side]["FERTILIZE"] += day.get("eff", {}).get("FERTILIZE", 0)
        agg[side]["shed_arrivals"] += day.get("shed_arr", 0)
    del g
res = {s: {"n_games": n[s], **{k: round(v / n[s], 1) for k, v in agg[s].items()}} for s in agg}
# seat identification: every side must play the same (episode, seat) pairs
res["same_episode_seat_pairs_all_sides"] = len({tuple(sorted(v)) for v in seats.values()}) == 1
(OUT / "verify_code_audit_ledger.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))

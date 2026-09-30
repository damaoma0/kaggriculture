"""Skeptic check of the code-audit report against STORED game outputs (no game runs; one file loaded at a time).

A. Leader layout (what the G1 leader-world tests copy): data/leader_semantics/<team>/<ep>.json.gz, every Nth file.
   Boards are the leader's own seat (README: "the leader's seat only"; meta.seat recorded). On the day-start boards of
   days 12 / 18 / 24: mean Manhattan distance to the NEAREST of the four shed tiles for animal-structure tiles
   (sh / co / go / pa; 'co' = cow OR empty coop in this encoding, both are animal structures) vs crop tiles
   (WH CA TO ST ME) vs that day's FERTILIZE target tiles.
B. Our own deploy's layout: results/fresh/lead_cycles/mgt_lpv_{dep6,tierev,tiernd}/*.json 'boards' (our seat's own
   observation; empty structures are 'Co'/'Pa' there, so 'co' is an occupied cow).
C. Compose-phase animal additions (report: "Yes, this phase adds animals"): router counters of
   results/fresh/ladder_panel/mgt_lpv_dep7/*.json (animal_<SP>, build_<KIND>).
D. The deploy comment's +462/game for fert_hold 1 (report: "I did not verify it"): paired margin ff1 - pv30 over the
   stored full-panel shards results/fresh/kaggle_remote_lead/pfff1*/.../mgt_lpv_ff1 and pfpv30*/.../mgt_lpv_pv30.
Output: verify_code_audit_stored.json next to this file.
"""
import glob
import gzip
import json
import random
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
DAYS = (12, 18, 24)
CROPS = {"WH", "CA", "TO", "ST", "ME"}


def dsh(i):
    x, y = i % 10, i // 10
    return min(abs(x - a) + abs(y - b) for a, b in SHED)


def mean(v):
    return sum(v) / len(v) if v else None


def layout(board, animal_labels, fert=None):
    an = [i for i in range(100) if board[i] in animal_labels]
    cr = [i for i in range(100) if board[i] in CROPS]
    r = {"n_animal": len(an), "n_crop": len(cr), "d_animal": mean([dsh(i) for i in an]), "d_crop": mean([dsh(i) for i in cr])}
    if fert is not None:
        r["n_fert"] = len(fert)
        r["d_fert"] = mean([dsh(i) for i in fert])
    return r


def summarise(rows, key_a="d_animal", key_b="d_crop"):
    out = {}
    for d in DAYS:
        R = [r[d] for r in rows if r.get(d) and r[d][key_a] is not None and r[d][key_b] is not None]
        if not R:
            continue
        diff = [r[key_a] - r[key_b] for r in R]
        out[d] = {"n_games": len(R), "mean_d_animal": round(mean([r[key_a] for r in R]), 3),
                  "mean_d_crop": round(mean([r[key_b] for r in R]), 3),
                  "mean_diff_animal_minus_crop": round(mean(diff), 3),
                  "games_animal_nearer": sum(x < 0 for x in diff), "games_equal": sum(x == 0 for x in diff),
                  "games_animal_farther": sum(x > 0 for x in diff),
                  "mean_n_animal": round(mean([r["n_animal"] for r in R]), 1), "mean_n_crop": round(mean([r["n_crop"] for r in R]), 1)}
        F = [r[d] for r in rows if r.get(d) and r[d].get("d_fert") is not None and r[d]["d_animal"] is not None]
        if F:
            fd = [r["d_animal"] - r["d_fert"] for r in F]
            out[d].update({"n_games_with_fertilize": len(F), "mean_d_fert_targets": round(mean([r["d_fert"] for r in F]), 3),
                           "games_animal_nearer_than_fert_targets": sum(x < 0 for x in fd),
                           "games_animal_farther_than_fert_targets": sum(x > 0 for x in fd)})
    return out


res = {}
# ---- A. leader corpus
nth = int(sys.argv[1]) if len(sys.argv) > 1 else 10
paths = sorted(glob.glob(str(ROOT / "data/leader_semantics/*/*.json.gz")))[::nth]
rows, seats, cash_ok, teams = [], [], 0, set()
for p in paths:
    g = json.load(gzip.open(p, "rt", encoding="utf-8"))
    seats.append(g["meta"]["seat"])
    cash_ok += bool(g["meta"].get("cash_match"))
    teams.add(Path(p).parent.name)
    r = {"file": str(Path(p).relative_to(ROOT))}
    for d in DAYS:
        day = g["days"][d]
        r[d] = layout(day["board"], {"sh", "co", "go", "pa"}, day["maintenance"].get("FERTILIZE", []))
    rows.append(r)
    del g
res["A_leader_corpus"] = {"n_games": len(rows), "n_teams": len(teams), "seat0": seats.count(0), "seat1": seats.count(1),
                          "cash_match": cash_ok, "by_day": summarise(rows), "files": [r["file"] for r in rows]}
# null: random relabelling of the same occupied tiles (animal count kept) -> expected diff 0; report share nearer
rng = random.Random(20260925)

# ---- B. our deploy boards
for agent in ("mgt_lpv_dep6", "mgt_lpv_tierev", "mgt_lpv_tiernd"):
    rows_b = []
    for p in sorted(glob.glob(str(ROOT / "results/fresh/lead_cycles" / agent / "*.json"))):
        g = json.load(open(p, encoding="utf-8"))
        b = g.get("boards")
        if not b or len(b) <= max(DAYS):
            continue
        r = {"file": Path(p).name}
        for d in DAYS:
            s = b[d]
            board = [s[2 * i:2 * i + 2] for i in range(100)]
            r[d] = layout(board, {"sh", "co", "go", "Co", "Pa"})
        rows_b.append(r)
        del g
    res["B_ours_" + agent] = {"n_games": len(rows_b), "by_day": summarise(rows_b), "files": [r["file"] for r in rows_b]}

# ---- C. compose-phase animal additions, dep7 ladder panel
cnt, n = {}, 0
for p in sorted(glob.glob(str(ROOT / "results/fresh/ladder_panel/mgt_lpv_dep7/*.json"))):
    g = json.load(open(p, encoding="utf-8"))
    n += 1
    for k, v in (g.get("router") or {}).items():
        if k.startswith(("animal_", "build_")):
            cnt.setdefault(k, []).append(v)
res["C_dep7_compose_animals"] = {"n_games": n, "games_with_key": {k: len(v) for k, v in cnt.items()},
                                 "sum": {k: sum(v) for k, v in cnt.items()}}

# ---- D. fert_hold full panel: ff1 - pv30 paired by episode
def panel(pattern):
    out = {}
    for p in glob.glob(str(ROOT / pattern)):
        try:
            g = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(g, dict) and "margin" in g and "episode" in g:
            out[(g["episode"], g.get("seat"))] = g["margin"]
    return out

ff1 = panel("results/fresh/kaggle_remote_lead/pfff1*/output/*/out/mgt_lpv_ff1/*.json")
pv30 = panel("results/fresh/kaggle_remote_lead/pfpv30*/output/*/out/mgt_lpv_pv30/*.json")
common = sorted(set(ff1) & set(pv30))
diff = [ff1[k] - pv30[k] for k in common]
boots = []
for _ in range(2000):
    s = [diff[rng.randrange(len(diff))] for _ in diff]
    boots.append(sum(s) / len(s))
boots.sort()
res["D_fert_hold_full_panel"] = {"n_ff1": len(ff1), "n_pv30": len(pv30), "n_paired": len(common),
                                 "mean_ff1_minus_pv30": round(mean(diff), 1) if diff else None,
                                 "boot95": [round(boots[50], 1), round(boots[1949], 1)] if diff else None,
                                 "better": sum(x > 0 for x in diff), "worse": sum(x < 0 for x in diff),
                                 "same": sum(x == 0 for x in diff)}

(OUT / "verify_code_audit_stored.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
for k, v in res.items():
    v2 = {kk: vv for kk, vv in v.items() if kk != "files"}
    print(k, json.dumps(v2, default=str))

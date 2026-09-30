"""Did S2's comparison even contrast 'animals central' vs 'animals not central'? Stored DSM tapes only (one at a time).
Re-derives, with scripts/layout_value.py's own functions (exec'd, main() not run), the whole-game visit counts and the
greedy_relayout mapping for the same tapes as verify_code_audit_s2.py, then reports the nearest-shed distance of
ANIMAL tiles (any job with FEED / CARE / COLLECT_FERTILIZER) and CROP tiles (any job with WATER / FERTILIZE / PLANT and
no animal op) in DSM's actual layout and in S2's relaid-out layout (mapping of the same tile identities).
Output: verify_code_audit_s2_relayout.json next to this file.
"""
import glob
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
src = (ROOT / "scripts/layout_value.py").read_text(encoding="utf-8")
ns = {"__name__": "verify_lv", "__file__": str(ROOT / "scripts/layout_value.py")}
exec(compile(src, "layout_value", "exec"), ns)
instance, simulate, greedy_relayout, unlocked_by_day, dist_shed = (ns["instance"], ns["simulate"], ns["greedy_relayout"],
                                                                   ns["unlocked_by_day"], ns["dist_shed"])
ANIMAL_OPS = {"FEED", "CARE", "COLLECT_FERTILIZER"}
CROP_OPS = {"WATER", "FERTILIZE", "PLANT"}
step = int(sys.argv[1]) if len(sys.argv) > 1 else 18
paths = sorted(glob.glob(str(ROOT / "data/dsm_tapes/56444344/*.json.gz")))[::step]
rows = []
for p in paths:
    t = json.load(gzip.open(p, "rt", encoding="utf-8"))
    acts = [a if isinstance(a, dict) else {} for a in t["actions"]]
    unlocked = unlocked_by_day(t["boards"])
    del t
    sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
    freq, first_day, ops_on = Counter(), {}, {}
    for day in range(30):
        units, routes, busy, c = instance(sim, day)
        for r in routes.values():
            for j in r:
                freq[j.tile] += 1
                first_day[j.tile] = min(first_day.get(j.tile, day), day)
                ops_on.setdefault(j.tile, set()).update(j.ops)
    mapping = greedy_relayout(freq, first_day, unlocked)
    an = [x for x in freq if ops_on[x] & ANIMAL_OPS]
    cr = [x for x in freq if (ops_on[x] & CROP_OPS) and not (ops_on[x] & ANIMAL_OPS)]
    m = lambda v: round(sum(v) / len(v), 3) if v else None
    top = sorted(freq, key=lambda x: (-freq[x], first_day[x], x))[:len(an)]
    rows.append(dict(file=Path(p).name, n_animal_tiles=len(an), n_crop_tiles=len(cr),
                     actual_d_animal=m([dist_shed(x) for x in an]), actual_d_crop=m([dist_shed(x) for x in cr]),
                     relayout_d_animal=m([dist_shed(mapping[x]) for x in an]), relayout_d_crop=m([dist_shed(mapping[x]) for x in cr]),
                     animal_share_of_top_visited=round(sum(1 for x in top if x in set(an)) / max(1, len(an)), 3)))
    print(rows[-1], flush=True)
    del sim, acts
(OUT / "verify_code_audit_s2_relayout.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

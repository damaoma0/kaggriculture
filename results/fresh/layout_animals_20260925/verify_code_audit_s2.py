"""Skeptic check of the code-audit report, section 4 (what S2 / scripts/layout_value.py modelled for fertilizer).

Stored data only: DSM's recorded tapes data/dsm_tapes/56444344/*.json.gz (one file loaded at a time), replayed by
dead reckoning with scripts/fragments/tape_calendar.py exactly as layout_value.py does (no engine, no game run).
For every unit-day route of labour_search.instance():
  - fertilizer the route applies (FERTILIZE ops) and collects (COLLECT_FERTILIZER ops),
  - S2's pickup quantity need = max running deficit (finish()), and the same with collects ignored,
  - S2's fertilizer STEP charge: 1 if need > 0 else 0  -> credit of in-route collects = charge_without - charge_with,
  - whether a collect job precedes a fertilize job in route order,
  - whether the unit starts the day on one of the four shed tiles.
Also, from the raw per-step replay (DSM's actual commands): per unit-day with >= 1 FERTILIZE, did the unit PICKUP
fertilizer at the shed, and did a COLLECT at an animal tile precede a FERTILIZE with no shed PICKUP/DROP in between
("outbound chain"; animal tile at <= the crop tile's nearest-shed distance counted separately).
Output: verify_code_audit_s2.json next to this file.
"""
import glob
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
_src = (ROOT / "scripts/labour_search.py").read_text(encoding="utf-8")
ns = {"__name__": "verify_lib", "__file__": str(ROOT / "scripts/labour_search.py")}
exec(compile(_src, "labour_search", "exec"), ns)
instance, finish, simulate, SHED, dman = ns["instance"], ns["finish"], ns["simulate"], ns["SHED"], ns["d"]
MOVES = ns["MOVES"]


def dsh(p):
    return min(dman(p, s) for s in SHED)


def need_of(route, ignore_collect=False):
    need = bal = 0
    for j in route:
        f = sum(1 for o in j.ops if o == "FERTILIZE")
        c = 0 if ignore_collect else sum(1 for o in j.ops if o == "COLLECT_FERTILIZER")
        bal -= f - c
        need = max(need, -bal)
    return need


step = int(sys.argv[1]) if len(sys.argv) > 1 else 18
paths = sorted(glob.glob(str(ROOT / "data/dsm_tapes/56444344/*.json.gz")))[::step]
tot = Counter()
per_game = []
for p in paths:
    t = json.load(gzip.open(p, "rt", encoding="utf-8"))
    acts = [a if isinstance(a, dict) else {} for a in t["actions"]]
    del t
    sim = simulate(lambda s: acts[s] if s < len(acts) else {}, 0, 718, [(4, 4)])
    g = Counter()
    for day in range(30):
        units, routes, busy, cal = instance(sim, day)
        for u, r in routes.items():
            if not r:
                continue
            g["unit_days"] += 1
            g["start_on_shed"] += units[u][1] in SHED
            nf = sum(o == "FERTILIZE" for j in r for o in j.ops)
            nc = sum(o == "COLLECT_FERTILIZER" for j in r for o in j.ops)
            g["fert_ops"] += nf
            g["collect_ops"] += nc
            if nf == 0:
                continue
            g["ud_with_fert"] += 1
            nw, nn = need_of(r), need_of(r, True)
            ch_w, ch_n = int(nw > 0), int(nn > 0)
            g["S2_fert_steps_with_collects"] += ch_w
            g["S2_fert_steps_ignoring_collects"] += ch_n
            g["S2_step_credit_max"] = max(g["S2_step_credit_max"], ch_n - ch_w)
            g["fert_units_covered_in_route"] += nn - nw
            first_c = next((k for k, j in enumerate(r) if "COLLECT_FERTILIZER" in j.ops), None)
            last_f = max((k for k, j in enumerate(r) if "FERTILIZE" in j.ops), default=None)
            g["ud_collect_before_a_fertilize"] += first_c is not None and last_f is not None and first_c < last_f
            g["unit_hours_model"] += finish(units[u], r) - units[u][0]
        # raw commands: DSM's actual fertilizer sourcing
        seq = {}
        for s_ in range(day * 24, min(719, day * 24 + 24)):
            for u, (x, y, c) in enumerate(sim.get(s_, [])):
                seq.setdefault(u, []).append(((x, y), c if c else ["PASS"]))
        for u, v in seq.items():
            if not any(c[0] == "FERTILIZE" for _, c in v):
                continue
            g["raw_ud_with_fert"] += 1
            g["raw_ud_shed_pickup_fert"] += any(c[0] == "PICKUP" and len(c) > 1 and c[1] == "FERTILIZER" for _, c in v)
            carry_src = None              # tile of the last collect since the last shed pickup/drop
            chain = chain_out = False
            for pos, c in v:
                if c[0] in ("PICKUP", "DROP") and pos in SHED:
                    carry_src = None
                elif c[0] == "COLLECT_FERTILIZER":
                    carry_src = pos
                elif c[0] == "FERTILIZE" and carry_src is not None and carry_src != pos:
                    chain = True
                    chain_out = chain_out or dsh(carry_src) <= dsh(pos)
            g["raw_ud_collect_then_fertilize_no_shed_between"] += chain
            g["raw_ud_same_with_animal_not_farther_than_crop"] += chain_out
    del sim, acts
    per_game.append(dict(file=Path(p).name, **g))
    for k, v in g.items():
        tot[k] = max(tot[k], v) if k == "S2_step_credit_max" else tot[k] + v
    print(Path(p).name, dict(g), flush=True)

res = dict(files=[Path(p).name for p in paths], n_games=len(paths), total=dict(tot), per_game=per_game)
(OUT / "verify_code_audit_s2.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
print("TOTAL", json.dumps(dict(tot)))

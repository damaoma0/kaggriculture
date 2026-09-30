"""Skeptic check of the code-audit report (layout + fertilizer handling). STATIC reads only: no game runs, no imports
of agent modules (the executor's placement function is exec'd in isolation with stubs).

Checks, per build file:
  1. fert_hold default / override and whether the fert_keep branch exists (report: deploy + dep7 = 1, dep6 and the
     tie variants have no fert_hold code, mgt_lead = 0, ff1 = 1, ff2 = 2).
  2. deploy placement constants (land_max, last_animal, pred_mult, co_fix, fill_free) and executor placement keys
     (place_bonus_days, zone_penalty, spawn_allot, dispatch).
  3. order of the crop loop, the late fill loop and the animal loop inside _dep_compose.
  4. _dep_free_tiles: is its centre term |x-4.5|+|y-4.5| rank-identical to Manhattan distance to the NEAREST of the
     four shed tiles (4,4),(5,4),(4,5),(5,5)? Exec'd on an empty unlocked board.
  5. _free_tile (G1 executor fallback): does it contain any centre / shed term?
  6. every agents/mgt_lpv_*.py: CFG/DEP_CFG overrides that touch a placement key; hash of _free_tile / _dep_free_tiles.
Output: verify_code_audit_static.json next to this file.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
FILES = ["agents/mgt_lead.py", "agents/mgt_lead_deploy.py", "agents/mgt_lpv_dep6.py", "agents/mgt_lpv_dep7.py",
         "agents/mgt_lpv_ff1.py", "agents/mgt_lpv_ff2.py", "agents/mgt_lpv_tierev.py", "agents/mgt_lpv_tiernd.py"]
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
PLACEMENT_KEYS = {"place_bonus", "place_bonus_days", "zone_penalty", "spawn_allot", "land_max", "co_fix",
                  "fill_free", "fill_keep_empty", "last_animal"}


def read(p):
    return (ROOT / p).read_text(encoding="utf-8").replace("\r\n", "\n")


def func_src(src, name):
    m = re.search(r"^def %s\(.*?(?=^def |\Z)" % re.escape(name), src, re.S | re.M)
    return m.group(0) if m else None


def lineno(src, pat):
    for i, ln in enumerate(src.split("\n"), 1):
        if re.search(pat, ln):
            return i
    return None


def d_shed(idx):
    x, y = idx % 10, idx // 10
    return min(abs(x - a) + abs(y - b) for a, b in SHED)


res = {"files": {}}
for f in FILES:
    s = read(f)
    r = {"sha256_16": hashlib.sha256(s.encode()).hexdigest()[:16], "n_lines": s.count("\n") + 1}
    m = re.search(r'^\s+"fert_hold":\s*(\d)', s, re.M)
    r["fert_hold_default"] = int(m.group(1)) if m else None
    m = re.search(r"^CFG\.update\((\{.*?\})\)", s, re.M)
    r["cfg_update"] = m.group(1) if m else None
    m = re.search(r"^DEP_CFG\.update\((\{.*?\})\)", s, re.M)
    r["dep_cfg_update"] = m.group(1) if m else None
    eff = r["fert_hold_default"]
    if r["cfg_update"] and "fert_hold" in r["cfg_update"]:
        eff = int(re.search(r"'fert_hold':\s*(\d)", r["cfg_update"]).group(1))
    r["fert_hold_effective"] = eff if eff is not None else "absent (behaves as 0)"
    r["fert_keep_line"] = lineno(s, r"^\s+fert_keep = ")
    for k in ("place_bonus_days", "zone_penalty", "spawn_allot", "dispatch", "deliver_value", "pick_cap"):
        m = re.search(r'^\s+"%s":\s*([^,#\n]+(?:\}[^,#\n]*)?)' % k, s, re.M)
        r[k] = m.group(1).strip() if m else None
    for k in ("land_max", "co_fix", "fill_free", "last_animal", "pred_mult", "compose_from"):
        m = re.search(r'^\s+"%s":\s*(\{[^}]*\}|[^,#\n]+)' % k, s, re.M)
        r["DEP." + k] = m.group(1).strip() if m else None
    comp = func_src(s, "_dep_compose")
    if comp:
        base = lineno(s, r"^def _dep_compose\(")
        cl = comp.split("\n")
        find = lambda pat: next((base + i for i, ln in enumerate(cl) if re.search(pat, ln)), None)
        r["compose_def_line"] = base
        r["compose_crop_loop_line"] = find(r'for crop in \("STRAWBERRY", "TOMATO", "MELON", "WHEAT", "CARROT"\)')
        r["compose_fill_line"] = find(r'if DEP_CFG\["fill_free"\]')
        r["compose_animal_loop_line"] = find(r'for sp in \("SHEEP", "COW", "GOOSE"\)')
        r["compose_empties_line"] = find(r"empties = \[")
        r["compose_co_fix_line"] = find(r'DEP_CFG\["co_fix"\]')
        r["crop_before_animal"] = (r["compose_crop_loop_line"] or 1e9) < (r["compose_animal_loop_line"] or -1)
    ft = func_src(s, "_free_tile")
    r["free_tile_has_centre_or_shed_term"] = bool(ft and re.search(r"4\.5|SHED|_near_shed|centre|center", ft))
    r["free_tile_line"] = lineno(s, r"^def _free_tile\(")
    res["files"][f] = r

# 4. _dep_free_tiles rank check, exec'd in isolation on an empty board (every tile None = empty and unlocked)
s = read("agents/mgt_lead_deploy.py")
ns = {"_tile": lambda tiles, idx: None, "_is_weed": lambda t: False}
exec(func_src(s, "_dep_free_tiles"), ns)
order = ns["_dep_free_tiles"](None, set(), None, None)
ref = sorted(range(100), key=lambda i: (d_shed(i), i))
centre = {i: abs(i % 10 - 4.5) + abs(i // 10 - 4.5) for i in range(100)}
res["dep_free_tiles"] = {
    "n_tiles": len(order),
    "order_identical_to_nearest_shed_distance_then_index": order == ref,
    "centre_term_minus_1_equals_nearest_shed_distance_all_100": all(abs(centre[i] - 1 - d_shed(i)) < 1e-9 for i in range(100)),
    "first_8": order[:8],
}
# same function with a leader-label preference: pref tiles first regardless of distance
pref_board = [" ."] * 100
pref_board[0] = "sh"
order2 = ns["_dep_free_tiles"](None, set(), pref_board, "sh")
res["dep_free_tiles"]["leader_label_tile_ranks_first_even_at_corner"] = order2[0] == 0

# 6. all mgt_lpv variants
lpv = {}
h_free, h_dfree = set(), set()
for p in sorted((ROOT / "agents").glob("mgt_lpv_*.py")):
    s = p.read_text(encoding="utf-8").replace("\r\n", "\n")
    ups = re.findall(r"^(?:CFG|DEP_CFG)\.update\((\{.*?\})\)", s, re.M)
    keys = set()
    for u in ups:
        keys |= set(re.findall(r"'([a-z_0-9]+)':", u))
    lpv[p.name] = sorted(keys & PLACEMENT_KEYS)
    h_free.add(hashlib.md5((func_src(s, "_free_tile") or "").encode()).hexdigest()[:8])
    h_dfree.add(hashlib.md5((func_src(s, "_dep_free_tiles") or "").encode()).hexdigest()[:8])
res["lpv_variants"] = {"n": len(lpv), "placement_key_overrides": {k: v for k, v in lpv.items() if v},
                       "distinct__free_tile_bodies": sorted(h_free), "distinct__dep_free_tiles_bodies": sorted(h_dfree)}

(OUT / "verify_code_audit_static.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
for f, r in res["files"].items():
    print(f, "| fert_hold eff:", r["fert_hold_effective"], "| fert_keep line", r["fert_keep_line"],
          "| land_max", r.get("DEP.land_max"), "| co_fix", r.get("DEP.co_fix"), "| crop<animal", r.get("crop_before_animal"),
          "| lines crop/fill/animal", r.get("compose_crop_loop_line"), r.get("compose_fill_line"), r.get("compose_animal_loop_line"),
          "| free_tile centre term", r["free_tile_has_centre_or_shed_term"], "| place_bonus_days", r["place_bonus_days"],
          "| zone", r["zone_penalty"], "| spawn_allot", r["spawn_allot"], "| dispatch", r["dispatch"])
print(json.dumps(res["dep_free_tiles"]))
print(json.dumps(res["lpv_variants"]))

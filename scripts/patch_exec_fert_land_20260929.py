"""v18w -> v18x: sd_fert_land (default None) - {crop: [age_lo, age_hi, coins]}: a FERTILIZE at those ages is worth `coins`
more (the tile-day its earlier release saves), in both fertilize rules. When sd_fert_force_tiles is set, a crop listed in
sd_fert_force gets the land value only on those tiles.

User 2026-09-29 ("We do it only if we expect this as a 2day cycle"): n18rc190d flagged 80 age-1 carrots whose tile the
plan uses tomorrow, but only 29 were fertilized (28 cut at age 2 with 3 units); the rest stayed to age 3 while the plan
counted their tile free. The age-2 wheat fertilize (5 units at age 3 -> released at age 3, not 4) was done on 49 / 88
(n18rc178d) and 32 / 93 (n18rc190d) wheat, DSM 88 / 100 - on the days it was skipped we sold fertilizer (d10: 2 / 13
wheat fertilized, 14 sold). sd_tier_fert_exact values a FERTILIZE by units x price - 0.6 x the fertilizer price (about
2 x $30 - $30 for a wheat), with no value for the tile-day it frees, so the route planner drops it.

usage: patch_exec_fert_land_20260929.py  (writes agents/mgt_lead_kb115lt2_v18x.py from v18w)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18w.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18x.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


HELPER = '''

def _fert_land(crop, age, idx):
    """sd_fert_land: coins a FERTILIZE at this age adds for the tile-day its earlier release saves (0 if not configured)."""
    fl_ = (CFG.get("sd_fert_land") or {}).get(crop)
    if not fl_ or not (int(fl_[0]) <= age <= int(fl_[1])):
        return 0.0
    if (crop in (CFG.get("sd_fert_force") or {}) and CFG.get("sd_fert_force_tiles") is not None
            and idx not in CFG["sd_fert_force_tiles"]):
        return 0.0
    return float(fl_[2])
'''


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_fert_force_tiles": None,''', '''    "sd_fert_land": None,     # {crop: [age_lo, age_hi, coins]}: a FERTILIZE at these ages is worth `coins` more (the tile-day saved)
    "sd_fert_force_tiles": None,''')
    s = sub(s, '''

def _tier_fert_exact(rec, tiles, day, prices, st):''', HELPER + '''

def _tier_fert_exact(rec, tiles, day, prices, st):''')
    s = sub(s, '''        if g > 0 and CFG["sd_fert_bonus"] and t["crop"] in (CFG["sd_fert_bonus_crops"] or ()):
            v += float(CFG["sd_fert_bonus"])      # sd_fert_bonus''', '''        if g > 0 and CFG["sd_fert_bonus"] and t["crop"] in (CFG["sd_fert_bonus_crops"] or ()):
            v += float(CFG["sd_fert_bonus"])      # sd_fert_bonus
        if g > 0 and CFG.get("sd_fert_land"):
            v += _fert_land(t["crop"], day - int(t.get("planted_day", day)), idx)   # sd_fert_land''')
    s = sub(s, '''            if du > 0 and du * price - inp > 0:
                cand.append((du * price - inp, x, y, crop, du, price, prod))''', '''            land_ = _fert_land(crop, day - int(t.get("planted_day", day)), 10 * y + x) if du > 0 and CFG.get("sd_fert_land") else 0.0
            if du > 0 and du * price - inp + land_ > 0:
                cand.append((du * price - inp + land_, x, y, crop, du, price, prod))''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

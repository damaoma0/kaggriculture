"""v18u -> v18v: sd_fert_force (default None) - {crop: [age_lo, age_hi]}: a FERTILIZE on a plant of that crop at those ages
is worth at least one unit in both fertilize rules (_sd_fert_first and sd_tier_fert_exact).

User 2026-09-29 ("harvest wheat at age 3 and plant carrots when we foresee this tile would be planted for strawberries 2
days later"): the morning plan has no gaps (gap_fill found no tile free with a later next use on days 7-26 in
114393058); the carrot cycle is the loss (3.33 tile-days a harvest vs DSM 2.75; DSM cuts 37 carrots at age 2, we 0).
The tiler releases an age-2 carrot only if its dawn projection reaches min_yield 3, i.e. only if it is already
fertilized at dawn. Both fertilize rules value a FERTILIZE by the units it adds for a harvest at age 3, where the age-2
FERTILIZE gives the same 4 units, so the age-1 value is 0: n18rc178d fertilized 85 carrots, all at age 2 (DSM: 21 at age
1, 44 at age 2), none was fertilized at an age-2 dawn (DSM 24 / 119), and no carrot was released or cut at age 2.
A FERTILIZE at age 1 covers ages 1-3, so a carrot kept to age 3 still reaches 4 units: the same one fertilizer, a day
earlier, and the plan can cut it at age 2 with 3 units when it needs the tile.

usage: patch_exec_fert_force_20260929.py  (writes agents/mgt_lead_kb115lt2_v18v.py from v18u)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18u.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18v.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_carrot_age2": 0,''', '''    "sd_fert_force": None,    # {crop: [age_lo, age_hi]}: a FERTILIZE at these ages is worth >= 1 unit in both fertilize rules
    "sd_carrot_age2": 0,''')
    # first-useful-day rule
    s = sub(s, '''            du = int(p1["units"]) - int(p0["units"])
            lg_ = _S["log"] if _S is not None else None''', '''            du = int(p1["units"]) - int(p0["units"])
            ffo_ = (CFG.get("sd_fert_force") or {}).get(crop)
            if ffo_ is not None and du <= 0 and int(ffo_[0]) <= day - int(t.get("planted_day", day)) <= int(ffo_[1]):
                du = 1                                 # sd_fert_force: fertilize at this age (carrot age 1 -> 3 units at age 2)
            lg_ = _S["log"] if _S is not None else None''')
    # exact tier valuation
    s = sub(s, '''        g = _tier_fert_gain(idx, t, day)
        price = float(prices.get(t["crop"], 0) or 0)''', '''        g = _tier_fert_gain(idx, t, day)
        ffo_ = (CFG.get("sd_fert_force") or {}).get(t.get("crop"))
        if (ffo_ is not None and g <= 0 and int(t.get("fertilized_until_day", -1) or -1) < day
                and int(ffo_[0]) <= day - int(t.get("planted_day", day)) <= int(ffo_[1])):
            g = 1                                      # sd_fert_force
        price = float(prices.get(t["crop"], 0) or 0)''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

"""v18t -> v18u: sd_carrot_age2 (default 0) - a carrot is harvested at age 2 once its units (after today's window water)
reach sd_carrot_age2_min (default 3).

User 2026-09-29 ("We are wasting tile-days on 3 days carrot and fallow while wheat loses"): DSM harvests 48% of its
carrots at age 2 (9 current-DSM worlds; plant -> next plant 2.53 days, 1.27 carrots a tile-day), we 0% (3.0-3.4 days,
1.0-1.13 a tile-day). A carrot fertilized and watered at age 2 already holds 1 + 2 = 3 units (cap 4 at age 3): 1.5 a
day vs 1.33. The tiler's release age 2 (n18rc173d / 178d) only frees capacity in its model - the replant goes to any
free tile - and _onetime_should_harvest keeps a carrot below its cap until age 3 (sd_onetime_gain_fix), so no carrot was
ever harvested at age 2 (n18rc178d: 84 / 84 at age 3, 63% fertilized).

usage: patch_exec_carrot_age2_20260929.py  (writes agents/mgt_lead_kb115lt2_v18u.py from v18t)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18t.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18u.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_lastday": 0,''', '''    "sd_carrot_age2": 0,      # 1: a carrot is harvested at age 2 once its units (after today's water) reach sd_carrot_age2_min
    "sd_carrot_age2_min": 3,
    "sd_tier_lastday": 0,''')
    s = sub(s, '''def _onetime_should_harvest(t, day):
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if age < c["first"]:
        return False''', '''def _onetime_should_harvest(t, day):
    c = CROPS[t["crop"]]
    age = day - t["planted_day"]
    if age < c["first"]:
        return False
    if (CFG.get("sd_carrot_age2") and t["crop"] == "CARROT" and age >= 2
            and int(t.get("yield_units", 0) or 0) >= int(CFG.get("sd_carrot_age2_min", 3))):
        return True                                # sd_carrot_age2: 3 units at age 2 (fertilized) - replant a day sooner''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

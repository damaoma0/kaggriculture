"""v18n -> v18o: execution fixes found by the tile-exact replay (default off). User 2026-09-29: "With this changed retry
the exactness experiment with extra hand".

World 114523301, DSM's commands to day 11, DSM's own tile plan after (n18te0 / n18te1, scripts/b2b_cohorts_20260929.py):
same 98 wheat cohorts, 4.44 units each vs DSM's 5.01; same 82 carrot cohorts, 2.6 vs 3.2; wool sold at the floor.
  (1) Harvest BEFORE the day's water: tile (1,8) planted d13, day 16 - our hand does HARVEST -> PLANT -> WATER on a wheat
      fertilized through the day (3 units); DSM does WATER -> HARVEST -> PLANT -> WATER (5 units). ~10 cohorts.
      sd_tier_water_first 1: a hand about to HARVEST a one-time crop inside its growth window, unwatered today and below
      the tile cap, WATERs first (the HARVEST follows next hour; the route index does not advance).
  (2) Harvest a day EARLY: _onetime_should_harvest treats an unfertilized wheat at >= 4 units as done (4 = the
      unfertilized maximum from planting), but the cap is 6 - a wheat fertilized earlier sits at 5 on age 3 and one more
      water at age 4 makes 6 (DSM on 26 of 99 cohorts). In tile-exact runs the plan's harvest days are DSM's
      (sd_harvest_follow_dsm + sd_follow_defer_exact, existing flags). sd_onetime_gain_fix 1 (general): a one-time crop
      below the cap keeps growing while a window water remains (age < max_yield_day).
  (3) Wool sold on arrival at 1-23 (12 @23, 8 @2, 4 @1 on days 12-16; DSM 1-2 a day @24-66).
      sd_sell_floor_px {product: price}: the arrival / quota seller sells nothing of a listed product below the price
      (the endgame still sells everything).

sd_tier_water_first 2: the water is added to the tile's ops at planning instead (mode 1 was unbudgeted: n18te2/3 wilted
tiles from day 12).

usage: patch_exec_exact_fixes_20260929.py  (writes agents/mgt_lead_kb115lt2_v18o.py from v18n)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18n.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18o.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_sell_lot_front": 0,''', '''    "sd_tier_water_first": 0,  # 1 (tile-exact replay 114523301: HARVEST -> PLANT -> WATER on fertilized wheat, 3 units where
    # DSM's WATER -> HARVEST made 5): a HARVEST of a one-time crop in its window, unwatered today, below the cap, waters first
    "sd_onetime_gain_fix": 0,  # 1: a one-time crop below the tile cap is not "done" while a window water remains (the 4-unit
    # unfertilized maximum assumed no earlier fertilized water; DSM takes 6-unit wheat at age 4)
    "sd_sell_floor_px": None,  # {product: price}: the arrival / quota seller holds a listed product below this quote
    "sd_sell_lot_front": 0,''')
    # (1) water before a harvest, at command issue in the tier route runner
    s = sub(s, '''        v = _tier_check(c, t, inv, day, seeds_left)
        if v == "do" and c[0] == "DROP" and CFG["sd_tier_deliver_check"]''', '''        if (CFG.get("sd_tier_water_first") and c[0] == "HARVEST" and _is_plant(t) and t.get("crop") in CROPS
                and not CROPS[t["crop"]]["ongoing"] and not t.get("watered_today")):
            cd_ = CROPS[t["crop"]]
            age_ = day - int(t.get("planted_day", day))
            if (cd_["maxday"] + 1) // 2 <= age_ <= cd_["maxday"] and int(t.get("yield_units", 0) or 0) < cd_["max"]:
                cnt["water_first"] += 1                # the window water first; the HARVEST follows next hour
                lg.append([step, u, "water_first", it["tile"], t["crop"]])
                return ["WATER"]
        v = _tier_check(c, t, inv, day, seeds_left)
        if v == "do" and c[0] == "DROP" and CFG["sd_tier_deliver_check"]''')
    # (2) general harvest-age fix
    s = sub(s, '''    # remaining possible gain
    fert = t.get("fertilized_until_day", -1) >= day
    return False if fert else (y >= _unfert_max(t["crop"]))''', '''    # remaining possible gain
    fert = t.get("fertilized_until_day", -1) >= day
    if CFG.get("sd_onetime_gain_fix"):
        return False                               # below the cap with a window water left (age < maxday): keep growing
    return False if fert else (y >= _unfert_max(t["crop"]))''')
    # (3) sale floor on the arrival / quota seller
    s = sub(s, '''            lot_ = (CFG.get("sd_sell_lot") or {}).get(p)''', '''            flo_ = (CFG.get("sd_sell_floor_px") or {}).get(p)
            if flo_ is not None and float(prices.get(p, 0) or 0) < float(flo_):
                n = 0                              # sd_sell_floor_px: held in the shed below the floor
            lot_ = (CFG.get("sd_sell_lot") or {}).get(p)''')
    # (1b) mode 2 (after the pass that adds today's plan jobs missing from the hour-0 task list - the seeds are bought
    # at hour 0/1, so a replant stop there is HARVEST -> PLANT -> WATER with the window water left optional and dropped
    # by the route search): the water joins the tile's ops at planning (the route timing includes it); mode 1 inserted it at
    # command issue, unbudgeted - routes ran past the day and keep-alive waters were dropped (n18te2 / n18te3: carrot,
    # wheat and strawberry tiles wilted from day 12, strawberries -22 units)
    s = sub(s, '''    st["tier_plan_added"] = st.get("tier_plan_added", 0) + added
''', '''    st["tier_plan_added"] = st.get("tier_plan_added", 0) + added
    if int(CFG.get("sd_tier_water_first", 0) or 0) >= 2:   # a planned window water before every one-time crop harvest
        for idx_, r_ in rec.items():
            t_ = _tile(tiles, idx_)
            if not (_is_plant(t_) and t_.get("crop") in CROPS and not CROPS[t_["crop"]]["ongoing"]) or t_.get("watered_today"):
                continue
            if not any(o["c"][0] == "HARVEST" for o in r_["ops"]):
                continue
            cd_ = CROPS[t_["crop"]]
            age_ = day - int(t_.get("planted_day", day))
            if not ((cd_["maxday"] + 1) // 2 <= age_ <= cd_["maxday"] and int(t_.get("yield_units", 0) or 0) < cd_["max"]):
                continue
            pre_ = [o for o in r_["ops"] if o["c"][0] == "WATER" and o["rank"] < _TIER_RANK["HARVEST"]]
            if pre_:
                for o in pre_:
                    o["m"], o["tier"] = True, 2
            else:
                r_["ops"] = sorted(r_["ops"] + [_tier_op(["WATER"], True, 0.0, 2)], key=lambda o: o["rank"])
                st["tier_water_first"] = st.get("tier_water_first", 0) + 1
''')
    s = s.replace('''        if (CFG.get("sd_tier_water_first") and c[0] == "HARVEST" and _is_plant(t) and t.get("crop") in CROPS''',
                  '''        if (int(CFG.get("sd_tier_water_first", 0) or 0) == 1 and c[0] == "HARVEST" and _is_plant(t) and t.get("crop") in CROPS''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

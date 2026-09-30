"""Port of the melon flags of agents/mgt_lead_sector_search.py (sd_melon_fert, sd_melon_rush; user 2026-09-29, "an hour
is literally worth thousands here") onto a KB115LT2-family executor (V13 lineage). All default OFF.

  sd_melon_fert   a melon aged 6..8, not fertilized and below its cap, gets a FERTILIZE (+ the day's WATER) worth
                  sd_melon_fert_v, after the exact-fertilize pass (which values it at 0: the cap is reached anyway, one hour
                  later on the harvest day). Each later window water then adds 2, so it is at the cap by the harvest day and
                  the harvest trip needs no water hour.
  sd_melon_rush   harvest-day melon trips scored around hour sd_melon_rush_by instead of 8, no replant before walking
                  back, and the drop is sold in the same turn (unit actions run before market orders).

Melons have no shop demand (only the town takes one a day), so the first seller takes the top of a quadratic price
curve: V13 sells day-10 melons at hours 10-13, V9-lite from hour 9, the current DSM its first tile at hour 6.

usage: patch_exec_melon_20260929.py <source.py> <output.py>"""
import sys
from pathlib import Path


def patch(s):
    def rep(old, new):
        nonlocal s
        assert s.count(old) == 1, (s.count(old), old[:90])
        s = s.replace(old, new)

    rep('''    "sd_mel_pen": 10.0,       # coins per melon unit per hour delivered after 8 (never after 12)''',
        '''    "sd_mel_pen": 10.0,       # coins per melon unit per hour delivered after 8 (never after 12)
    "sd_melon_fert": 0,       # 1: melons aged 6..8 below the cap get FERTILIZE + WATER worth sd_melon_fert_v (at the cap by
    # the harvest day, so the harvest trip needs no water)
    "sd_melon_fert_v": 300.0,
    "sd_melon_rush": 0,       # 1: harvest-day melon trips scored around hour sd_melon_rush_by instead of 8, no replant before
    # walking back, the drop sold in the same turn
    "sd_melon_rush_by": 6,
    "sd_mel_last": 12,        # latest melon delivery hour of the melon rule (melons no hand can drop by then are harvested
    # later by the planner); MGT sells its day-10 melons until hour 15, V13 with MGT's 12-tile opening sold 30 of 72''')
    for old_, new_ in (("    if drop > 12:\n", "    if drop > int(CFG[\"sd_mel_last\"]):\n"),
                       ("        if hand_best > 12 and far[0] <= 12:",
                        "        if hand_best > int(CFG[\"sd_mel_last\"]) and far[0] <= int(CFG[\"sd_mel_last\"]):"),
                       ("for u in units) <= 12]", "for u in units) <= int(CFG[\"sd_mel_last\"])]"),
                       ("for _, p0, t0 in units) <= 12]", "for _, p0, t0 in units) <= int(CFG[\"sd_mel_last\"])]")):
        rep(old_, new_)
    rep('''        cost = units * (float(CFG["sd_mel_pen"]) * max(0, drop - 8) - float(CFG["sd_mel_bonus"]) * max(0, 8 - drop))
    return drop, cost, units, order, hh''', '''        piv_ = int(CFG["sd_melon_rush_by"]) if CFG["sd_melon_rush"] else 8
        cost = units * (float(CFG["sd_mel_pen"]) * max(0, drop - piv_) - float(CFG["sd_mel_bonus"]) * max(0, piv_ - drop))
    return drop, cost, units, order, hh''')
    # sd_melon_rush skips only the replant merge; the loop also prunes the melon tiles' WATER / HARVEST jobs from the
    # general plan and sets their release hour (a first version skipped the whole loop: duplicate melon jobs every
    # melon harvest day - a4_melon on Kaggle 2026-09-29, executor sha b3d90dc4)
    rep('''            if rest and len(rest) == len([o for o in r_["ops"] if o["m"]]):
                seg_ = {"p0": M["p0"], "t0": M["t0"], "stops": M["stops"]}''', '''            if rest and len(rest) == len([o for o in r_["ops"] if o["m"]]) and not CFG["sd_melon_rush"]:
                seg_ = {"p0": M["p0"], "t0": M["t0"], "stops": M["stops"]}''')
    rep('''            R["k"] += 1
            R.setdefault("done", []).append((hour, it["tile"], "PLACE"))
            return ["PLACE", "MELON", m]''', '''            R["k"] += 1
            R.setdefault("done", []).append((hour, it["tile"], "PLACE"))
            if CFG["sd_melon_rush"]:                   # sold in the same turn (unit actions run before the market)
                TP.setdefault("dsell", Counter())["MELON"] += m
            return ["PLACE", "MELON", m]''')
    rep('''    if CFG["sd_tier_fert_exact"]:
        _tier_fert_exact(rec, tiles, day, prices, st)
''', '''    if CFG["sd_tier_fert_exact"]:
        _tier_fert_exact(rec, tiles, day, prices, st)
    if CFG["sd_melon_fert"] and day < last_day:      # melons at their cap before the harvest day (after the exact pass,
        # which values a melon fertilize at 0 units: the cap is reached anyway, one hour later)
        for idx_ in range(100):
            t_ = _tile(tiles, idx_)
            if not (_is_plant(t_) and t_.get("crop") == "MELON"):
                continue
            a_ = day - int(t_.get("planted_day", day))
            if not (6 <= a_ <= 8) or int(t_.get("fertilized_until_day", -1) or -1) >= day \\
                    or int(t_.get("yield_units", 0) or 0) >= CROPS["MELON"]["max"]:
                continue
            r_ = rec.setdefault(idx_, {"ops": [], "rel": 0})
            if not any(o["c"][0] == "FERTILIZE" for o in r_["ops"]):
                r_["ops"].append(_tier_op(["FERTILIZE"], False, float(CFG["sd_melon_fert_v"]), 3))
                st["tier_melon_fert"] = st.get("tier_melon_fert", 0) + 1
            if not t_.get("watered_today") and not any(o["c"][0] == "WATER" for o in r_["ops"]):
                r_["ops"].append(_tier_op(["WATER"], False, float(prices.get("MELON", 0) or 0), 3))
''')
    return s


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    assert src.resolve() != out.resolve(), "refusing an in-place edit"
    s = patch(src.read_text(encoding="utf-8"))
    compile(s, str(out), "exec")
    out.write_text(s, encoding="utf-8", newline="\n")
    print("patched ->", out)

"""v18r -> v18s: sd_land_virtual {"days": [6], "hour": 5} (default None) - the day's route plan includes the quadrant bought
that day.

User 2026-09-29: "What we are aiming before end of day6 is collecting and selling all fertilizer generated in day6 and
finishing the daily production goal ... I think we need to make a special case for day6 regardless". Measured (9
current-DSM 3Q worlds, n18rc105 / n18rc106): the day-6 quadrant unlocks at hour 5 in all 9 worlds (day 8 at hour 8);
the tier plan is made at hour 0 only and omits then-locked tiles, so the entry (_unlock_execution) switches to the old
hourly dispatcher for the rest of the day - every tier feature is off from hour 5: fertilizer drops (n18rc106 sold 2.6
on day 6, the same as without them; DSM 9.2), dawn fertilizer trips (n18rc113 3.6), water-first. Day 6 plants 11 of 16
planned, day 8 12 of 19; days 9-11 plant exactly the plan.

sd_land_virtual: at hour 0 of a listed day, the tiles of a quadrant the tile plan buys today (land_day == day, still
locked) are planned as empty (the planner's tile grid only; the market still sees the quadrant locked and buys it), and
every job on them is released at "hour" (the engine lets hands walk on locked tiles; their ops no-op until the unlock).
Use with the entry's unlock switch off on those days (sem_arms --keep-tier-days).

usage: patch_exec_land_virtual_20260929.py  (writes agents/mgt_lead_kb115lt2_v18s.py from v18r)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18r.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18s.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_dig_after_harvest": 0,''', '''    "sd_land_virtual": None,  # {"days": [6], "hour": 5}: hour-0 route plan includes the quadrant bought today (jobs from "hour")
    "sd_dig_after_harvest": 0,''')
    s = sub(s, '''    unlocked = list(farm.get("unlocked_quadrants", ["NW"]))

    jobs, fert = _plan(obs, S, tiles, day)''', '''    unlocked = list(farm.get("unlocked_quadrants", ["NW"]))
    lv_ = CFG.get("sd_land_virtual")
    S["_lv_tiles"] = set()
    if lv_ and hour == 0 and day in [int(x_) for x_ in lv_.get("days", [])]:
        pend_ = {q_ for q_, d_ in _T.land_day.items() if int(d_) == day and q_ not in unlocked}
        if pend_:                                  # sd_land_virtual: plan today's quadrant as empty, jobs from "hour"
            tiles = [list(r_) for r_ in tiles]
            for y_ in range(len(tiles)):
                for x_ in range(len(tiles[y_])):
                    if tiles[y_][x_] == "LOCKED" and _quad(x_, y_) in pend_:
                        tiles[y_][x_] = None
                        S["_lv_tiles"].add(y_ * 10 + x_)
            S["log"]["land_virtual_tiles"] += len(S["_lv_tiles"])

    jobs, fert = _plan(obs, S, tiles, day)''')
    s = sub(s, '''        pre, planp = (kept, []) if k0 is None else (kept[:k0], kept[k0:])
        rel_ = hour
''', '''        pre, planp = (kept, []) if k0 is None else (kept[:k0], kept[k0:])
        rel_ = hour
        if idx in (S.get("_lv_tiles") or ()):
            rel_ = max(rel_, int(CFG["sd_land_virtual"].get("hour", 5)))   # sd_land_virtual: after the unlock
''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

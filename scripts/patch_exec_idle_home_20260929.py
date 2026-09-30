"""v18e -> v18f: sd_tier_idle_home (default off). User 2026-09-29: "focus on the bring-back hands, the objective is to
make these resemble DSM's choice closely"; bring-back trips are "one of our biggest shortfalls".

Measured (scripts/bringback_profile_20260929.py, n18rc8x vs the recorded leader in the same 8 harness worlds, days
6-29 per day): our hands drop goods mid-day 2.6 times (DSM 4.4), 15 goods (DSM 25, wheat 2.0 vs 6.9, strawberries 0.3
vs 2.2); the missing drops are the afternoon ones (hours 14-22: ours ~0.06 an hour, DSM ~0.25) - DSM's hands that finish
their field work walk home, drop the load (sold the same day) and pick up / do near-shed work. Our routes END early
instead: 17.9 idle hand-hours a day after the last planned job (DSM 3.2), only 5.4 of 10.5 hands work to hour 24.

sd_tier_idle_home [min_units, hmax]: a hand whose planned route is done and that carries >= min_units goods (products
except fertilizer) walks to the nearest shed-access tile and DROPs everything by hour hmax; the goods are sold at once
like a planned delivery (not wheat, not sd_tier_deliver_keep products, not fertilizer - fertilizer stays in the shed for
tomorrow's routes when sd_fert_sell 3 keeps a reserve). Then the other idle fillers (sd_tier_idle_fert: shed
fertilizer pickup + fertilize; sd_tier_idle_work: care / collect / water) take over as before.

usage: patch_exec_idle_home_20260929.py  (writes agents/mgt_lead_kb115lt2_v18f.py)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18e.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18f.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:80], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_idle_work_wc": 10.0,
''', '''    "sd_tier_idle_work_wc": 10.0,
    "sd_tier_idle_home": None,  # [min_units, hmax] (user 2026-09-29 bring-back hands, DSM's afternoon drops: our routes end
    # early - 17.9 idle hand-hours a day after the last planned job vs DSM 3.2 - while DSM's hands walk home with their
    # load at hours 14-22): a hand whose plan is done and that carries >= min_units goods (products except fertilizer)
    # walks to the nearest shed-access tile and DROPs by hour hmax, sold at once (not wheat / sd_tier_deliver_keep /
    # fertilizer); then sd_tier_idle_fert / sd_tier_idle_work as before
''')
    s = sub(s, '''    if CFG["sd_tier_idle_fert"] and hour < 23:     # the plan is done: fertilize more with shed fertilizer (user)
        a_ = _tier_idle_fert(TP, R, u, p, inv, tiles, day, hour, shed_left)''', '''    if CFG["sd_tier_idle_home"] and hour < 23:     # the plan is done: bring the load home (DSM's afternoon drops)
        a_ = _tier_idle_home(TP, R, u, p, inv, tiles, day, hour)
        if a_ is not None:
            return a_
    if CFG["sd_tier_idle_fert"] and hour < 23:     # the plan is done: fertilize more with shed fertilizer (user)
        a_ = _tier_idle_fert(TP, R, u, p, inv, tiles, day, hour, shed_left)''')
    s = sub(s, '''def _tier_idle_fert(TP, R, u, p, inv, tiles, day, hour, shed_left):''', '''def _tier_idle_home(TP, R, u, p, inv, tiles, day, hour):
    """sd_tier_idle_home: a hand with no planned work left carrying goods walks home and DROPs them (see the flag)."""
    mn, hmax = (list(CFG["sd_tier_idle_home"]) + [2, 22])[:2]
    goods = {k: int(v) for k, v in inv.items() if k in PRODUCTS and k != "FERTILIZER" and int(v or 0) > 0}
    if sum(goods.values()) < int(mn):
        return None
    sh = _near_shed(p)
    d_ = abs(p[0] - sh[0]) + abs(p[1] - sh[1])
    if hour + d_ > int(hmax):                     # the DROP itself happens at hour + d_
        return None
    cnt = TP["cnt"]
    if tuple(p) != tuple(sh):
        if R.get("_home_day") != day:
            R["_home_day"] = day
            cnt["idle_home_trips"] += 1
        return _step_toward(p, sh)
    nosell_ = set(CFG["sd_tier_deliver_keep"] or ())
    TP.setdefault("dsell", Counter()).update({k: v for k, v in goods.items() if k != "WHEAT" and k not in nosell_})
    cnt["idle_home_drops"] += 1
    cnt["idle_home_units"] += sum(goods.values())
    R.setdefault("done", []).append((hour, sh[1] * 10 + sh[0], "DROP"))
    return ["DROP"]


def _tier_idle_fert(TP, R, u, p, inv, tiles, day, hour, shed_left):''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

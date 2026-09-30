"""v18i -> v18j: strawberry pulses (sd_tier_spulse) + a price gate on the dedicated strawberry run (sd_tier_sclu_pmin),
both default off. User 2026-09-29: "when we spot the need of a bringback run, make dedicated effort into it first";
"isn't ripening happening at hour 0 every day?" -> "yeah let's try".

Measured (item traces, 8 leader worlds): strawberry yield appears at the midnight refresh, a tile every second night;
ours split over both parities (43-66% of units harvested on even days, 0 tiles ever harvested on both parities in 6 of
8 worlds: every tile is picked on its production morning) -> a flat 8-16 a day; the leader's lean to one parity
(54-77%) AND it holds tiles an extra night (5-18 tiles a game harvested on both parities) -> big every-other-day pulses
(114377700: 34 / 36 on days 16 / 18), picked early (median hour 13-14 vs our 14-17), brought home and sold the same day
before the crash. The dedicated run (sd_tier_sclu, n18rc49) on our flat flow sold 29% same-day but @72 (leader @139):
small batches every day, into the crash too.

sd_tier_spulse {"from": d0, "to": d1}: at the dawn plan, if tomorrow's strawberry units (tiles producing tonight + what
we hold) exceed today's ripe units, today's ripe tiles that do NOT produce tonight (their yield cannot overflow) and
are not at their last production skip today's HARVEST and join tomorrow's pulse.
sd_tier_sclu_pmin p: the dedicated strawberry run only when the dawn strawberry price is >= p (no runs into a crash).

usage: patch_exec_spulse_20260929.py  (writes agents/mgt_lead_kb115lt2_v18j.py from v18i)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18i.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18j.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_bb": None,''', '''    "sd_tier_spulse": None,  # {"from": d0, "to": d1} (user 2026-09-29 strawberry pulses: the leader's tiles ripen on
    # one parity and it holds some a night -> 34 / 36-unit pulses sold the same day before the crash; ours pick every
    # tile on its production morning -> a flat 8-16 a day): when tomorrow's strawberry units exceed today's, today's ripe
    # tiles that do not produce tonight skip today's HARVEST and join tomorrow's pulse
    "sd_tier_sclu_pmin": None,  # the dedicated strawberry run (sd_tier_sclu) only when the dawn strawberry price >= this
    "sd_tier_bb": None,''')
    # the hold in the dawn op catalogue (before the price hold)
    s = sub(s, '''            if c == "HARVEST" and CFG["sd_tier_hold_price"] and _tier_hold(_tile(tiles, b), day, prices, i == hi):''', '''            if c == "HARVEST" and CFG.get("sd_tier_spulse") and _tier_spulse_hold(tiles, b, day, st):
                st["tier_spulse_held"] = st.get("tier_spulse_held", 0) + 1
                continue                               # joins tomorrow's strawberry pulse
            if c == "HARVEST" and CFG["sd_tier_hold_price"] and _tier_hold(_tile(tiles, b), day, prices, i == hi):''')
    s = sub(s, '''def _tier_hold(t, day, prices, hard):''', '''_SPULSE = {}


def _spulse_produces(t, night):
    """a strawberry tile produces at the end of day `night` (engine _daily_refresh_plants)"""
    cr = CROPS["STRAWBERRY"]
    dsf = night + 1 - int(t.get("planted_day", night)) - cr["first"]
    return dsf >= 0 and dsf % cr["interval"] == 0 and dsf // cr["interval"] + 1 <= cr["max"]


def _tier_spulse_hold(tiles, idx, day, st):
    """sd_tier_spulse: this strawberry tile's HARVEST waits for tomorrow's pulse (see the flag)."""
    cfg = CFG.get("sd_tier_spulse") or {}
    if not (int(cfg.get("from", 12)) <= int(day) <= min(int(cfg.get("to", 27)), int(CFG["sd_tier_anim_harv_end"]) - 1)):
        return False
    t = _tile(tiles, idx)
    if not (_is_plant(t) and t.get("crop") == "STRAWBERRY") or int(t.get("yield_units", 0) or 0) <= 0:
        return False
    if _SPULSE.get("day") != day:                  # today's ripe units vs tomorrow's (tonight's production + held)
        ready, tomorrow = 0, 0
        for i in range(100):
            u_ = _tile(tiles, i)
            if not (_is_plant(u_) and u_.get("crop") == "STRAWBERRY"):
                continue
            y_ = int(u_.get("yield_units", 0) or 0)
            if _spulse_produces(u_, day):
                fert_ = int(u_.get("fertilized_until_day", -1) or -1) >= day and bool(u_.get("watered_today"))
                tomorrow += 2 if fert_ else 1   # tonight's new units only (a producing tile is harvested today)
            else:
                ready += y_
        _SPULSE.clear()
        _SPULSE.update(day=day, ready=ready, tomorrow=tomorrow, hold=tomorrow > ready)
        st["_spulse_day"] = dict(_SPULSE)
    if not _SPULSE["hold"]:
        return False
    if _spulse_produces(t, day):                   # it produces tonight: its yield could overflow - harvest it
        return False
    if int(t.get("max_lifespan_step", -1) or -1) >= 0:
        return False                               # last production done: the plant decays
    return True


def _tier_hold(t, day, prices, hard):''')
    # price gate on the dedicated run
    s = sub(s, '''    if ready_ < int(CFG["sd_tier_sclu_day_min"]):''', '''    pmin_ = CFG.get("sd_tier_sclu_pmin")
    if pmin_ is not None and float((S.get("_tier_prices") or {}).get("STRAWBERRY", 0) or 0) < float(pmin_):
        st["_sclu_day"] = {"clusters": [], "cand": len(cand), "ready": ready_, "gate": "price"}
        return {}
    if ready_ < int(CFG["sd_tier_sclu_day_min"]):''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

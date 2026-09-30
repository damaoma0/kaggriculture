"""v18j -> v18k: strawberry bring-back gated by the OPPONENT's harvest (default off). User 2026-09-29: "threshold will
be different for different games with different shops? I think the gate should depend on opponent harvest: selling at
same tick vs selling behind opponent creates a big enough gap."

Engine: the market quotes both players unit by unit in lockstep - selling on the same ticks as the opponent gets the
same prices; selling after their batch meets the price their units already pushed down. Both farms' tiles are public:
at the dawn plan the opponent's ripe strawberry units (yield on its strawberry tiles) and its tiles producing tonight
(its harvest tomorrow) are known.

At the dawn plan (_tier_pre) S["_opp_straw"] = {day, ready: the opponent's ripe strawberry units, tomorrow: its tiles
producing tonight}.
  sd_tier_sclu_opp_min n     the dedicated strawberry run (sd_tier_sclu) only when the opponent holds >= n ripe
                             strawberry units at dawn (its harvest day: we sell on the same ticks)
  sd_tier_spulse {"opp": 1}  the pulse hold aligns to the OPPONENT: our ripe tiles that do not produce tonight wait a
                             night when the opponent's harvest is tomorrow (tomorrow > ready), else are picked today

usage: patch_exec_oppgate_20260929.py  (writes agents/mgt_lead_kb115lt2_v18k.py from v18j)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18j.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18k.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_sclu_pmin": None,''', '''    "sd_tier_sclu_pmin": None,
    "sd_tier_sclu_opp_min": None,  # the dedicated strawberry run only when the opponent holds >= this many ripe strawberry
    # units at dawn (user 2026-09-29: sell on the same ticks as the opponent's batch, not behind it)''')
    s = sub(s, '''    t_start = time.perf_counter()
    st = L["st"]
    S["_shed_h0"] = dict(shed or {})''', '''    t_start = time.perf_counter()
    st = L["st"]
    S["_shed_h0"] = dict(shed or {})
    try:                                           # the opponent's strawberries (public tiles): ripe now, producing tonight
        me_ = int(_g(obs, "player", 0))
        of_ = (_g(obs, "farms", []) or [])[1 - me_]
        rdy_, tmr_ = 0, 0
        for row_ in (_g(of_, "tiles", []) or []):
            for t_ in row_:
                if _is_plant(t_) and t_.get("crop") == "STRAWBERRY":
                    if _spulse_produces(t_, day):
                        tmr_ += 1
                    elif day - int(t_.get("planted_day", day)) >= CROPS["STRAWBERRY"]["first"]:
                        rdy_ += int(t_.get("yield_units", 0) or 0)
        S["_opp_straw"] = {"day": day, "ready": rdy_, "tomorrow": tmr_}
        st["_opp_straw_day"] = dict(S["_opp_straw"])
    except Exception:
        S["_opp_straw"] = None''')
    # pulse hold aligned to the opponent
    s = sub(s, '''        _SPULSE.clear()
        _SPULSE.update(day=day, ready=ready, tomorrow=tomorrow, hold=tomorrow > ready)''', '''        hold_ = tomorrow > ready
        if cfg.get("opp"):                         # align to the opponent's harvest day (user)
            o_ = (_S or {}).get("_opp_straw") or {}
            if o_.get("day") == day:
                hold_ = int(o_.get("tomorrow", 0)) > int(o_.get("ready", 0))
        _SPULSE.clear()
        _SPULSE.update(day=day, ready=ready, tomorrow=tomorrow, hold=hold_)''')
    s = sub(s, '''    pmin_ = CFG.get("sd_tier_sclu_pmin")''', '''    omin_ = CFG.get("sd_tier_sclu_opp_min")
    if omin_ is not None:
        o_ = S.get("_opp_straw") or {}
        if o_.get("day") != day or int(o_.get("ready", 0)) < int(omin_):
            st["_sclu_day"] = {"clusters": [], "cand": len(cand), "ready": ready_, "gate": "opp", "opp": o_.get("ready")}
            return {}
    pmin_ = CFG.get("sd_tier_sclu_pmin")''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

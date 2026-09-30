"""v18o -> v18p: sd_eve_feed_buy (default off) - tomorrow's feed wheat bought the evening before on listed days.

World 114523301 hour by hour, day 8 (n18rc106, the day-6/7 fertilizer drop): dawn cash 450 (DSM 942); after the hour-0
hires and the dawn feed-wheat buy we hold 30 coins (DSM 934 - it bought its feed wheat on day 7: 618 coins vs our 368),
the morning sales reach the $2,000 third quadrant at hour 11 (DSM hour 6) and we plant 10 wheat that day from hour 13
(DSM 16 from hour 10). sd_eve_feed_buy {"days": [d0, d1], "hour": h}: at hour h of those days, wheat for tomorrow's
feeds (one per live animal) minus the wheat in the shed and in hands is bought, if the cash covers it.

usage: patch_exec_eve_feed_20260929.py  (writes agents/mgt_lead_kb115lt2_v18p.py from v18o)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18o.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18p.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_water_first": 0,''', '''    "sd_eve_feed_buy": None,   # {"days": [d0, d1], "hour": h}: tomorrow's feed wheat (one per live animal, minus shed + hands)
    # bought at hour h of those days (DSM buys day 8's feed wheat on day 7; our dawn buy delayed the day-8 land to hour 11)
    "sd_tier_water_first": 0,''')
    s = sub(s, '''    if CFG["sd_evening_wheat_surplus"] and hour >= int(CFG["sd_ews_hour"]) and day < last_day:''', '''    ef_ = CFG.get("sd_eve_feed_buy")
    if ef_ and not endgame and hour == int(ef_.get("hour", 21)) and int(ef_["days"][0]) <= day <= int(ef_["days"][1]):
        n_an_ = sum(1 for r_ in farm["tiles"] for t_ in r_ if _animal(t_))
        k_ = n_an_ - int(shed.get("WHEAT", 0) or 0) - sum(int(i.get("WHEAT", 0) or 0) for i in invs)
        pw_ = max(1, prices.get("WHEAT", 25))
        if k_ > 0 and money >= k_ * (pw_ + 2):
            sells.append(["BUY_PRODUCT", "WHEAT", int(k_)])
    if CFG["sd_evening_wheat_surplus"] and hour >= int(CFG["sd_ews_hour"]) and day < last_day:''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

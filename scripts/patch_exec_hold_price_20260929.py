"""v18f -> v18g: sd_tier_hold_price (default off). User 2026-09-29 "bring-back runs and prices strongly correlate" + "trace
the inbound items and sales tick by tick, item by item" (scripts/item_trace_20260929.py, lead-dsm-114377700):

- the leader stores goods ON THE ANIMAL / PLANT through a crash: milk 0 produced on days 15-18 (price 26-42), 18 on day
  20 (53-61); strawberries 34 / 36 on days 16 / 18 (sold the same day @173 / @100), then 7, 8, 0, 2, 0 on days 19-24
  (price 9-48); we harvested 8-16 a day straight into the crash (days 19-23 @48 / 30 / 12 / 10 / 9).
- holding in the SHED fails for us (n18rc26-37): held goods take the room of the ~60-unit nightly dump, the room check
  trips and the capacity sells dump them at crash prices. On the animal / plant the hold costs no shed room (cows / sheep
  hold 6, geese 4, a strawberry plant 4).

sd_tier_hold_price {product: price}: at the dawn plan, a HARVEST is left out of today's jobs while the product's market
price is below its threshold and the harvest can wait:
  animals     the harvest is optional already (sd_tier_anim_harv: tonight's production still fits under max_held)
  STRAWBERRY  / TOMATO (ongoing crops) held yield + tonight's possible production (2) fits under the crop's cap and the
              crop has productions left (not in its decay window)
Never from sd_tier_anim_harv_end on (season end). Dawn legs take only harvests left in the plan, so they skip held pens too.

usage: patch_exec_hold_price_20260929.py  (writes agents/mgt_lead_kb115lt2_v18g.py from v18f)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18f.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18g.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_idle_home": None,''', '''    "sd_tier_hold_price": None,  # {product: price} (user 2026-09-29 item trace: the leader holds milk on its cows
    # through a crash - 0 harvested on days 15-18 at 26-42, 18 on day 20 at 53-61 - and stops picking strawberries in the
    # crash; a shed hold fails for us, n18rc26-37, it takes the nightly dump's room): at the dawn plan a HARVEST that can
    # wait (animal: tonight's production fits under max_held; strawberry / tomato: held + 2 fits under the cap and the
    # plant has productions left) is left out while the product's price is below its threshold; never from
    # sd_tier_anim_harv_end on
    "sd_tier_idle_home": None,''')
    s = sub(s, '''            v_ = vals[i] if i < len(vals) else 0.0
            if (c == "HARVEST" and CFG["sd_tier_anim_harv"] and i != hi and _animal(_tile(tiles, b))''', '''            v_ = vals[i] if i < len(vals) else 0.0
            if c == "HARVEST" and CFG["sd_tier_hold_price"] and _tier_hold(_tile(tiles, b), day, prices, i == hi):
                st["tier_hold_price"] = st.get("tier_hold_price", 0) + 1
                continue                               # held on the animal / plant while the price is low
            if (c == "HARVEST" and CFG["sd_tier_anim_harv"] and i != hi and _animal(_tile(tiles, b))''')
    s = sub(s, '''def _tier_anim_mand(rec, tiles, minv, st):''', '''def _tier_hold(t, day, prices, hard):
    """sd_tier_hold_price: this HARVEST waits on the animal / plant (low price, nothing overflows or decays)."""
    thr = CFG["sd_tier_hold_price"] or {}
    if hard or not isinstance(t, dict) or day >= int(CFG["sd_tier_anim_harv_end"]):
        return False
    if _animal(t):
        p = ANIMALS[t["animal"]]["product"]
        if p not in thr or float(prices.get(p, 0) or 0) >= float(thr[p]):
            return False
        return not _tier_anim_harv_needed(t, day)
    if _is_plant(t):
        p = t.get("crop")
        cr = CROPS.get(p)
        if p not in thr or not cr or not cr["ongoing"] or float(prices.get(p, 0) or 0) >= float(thr[p]):
            return False
        if int(t.get("max_lifespan_step", -1) or -1) >= 0:
            return False                           # last production done: the plant decays, harvest now
        return int(t.get("yield_units", 0) or 0) + 2 <= int(cr["max"])
    return False


def _tier_anim_mand(rec, tiles, minv, st):''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

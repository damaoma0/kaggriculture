"""Two default-OFF market fixes on a KB115LT2-family executor (V13 lineage), from the V13 live05 newborn-feed trace
(docs in the recovery worktree: semantic_v13_newborn_feed_shadow_20260928.md):

  sd_market_carried_actual  `_market` counts wheat carried by the hands from their actual inventories at the start of the
                            turn. The dispatcher's `carried` also holds this turn's greedy pickups, whose units are still
                            in the observed shed, so they were counted twice (live05 D7 H1: 13 needed - 4 carried - 4 in
                            the shed -> buy 5, the 4 carried being the shed's 4); the tier override can also discard those
                            pickups while `carried` keeps them.
  sd_tier_wheat_buy_live    the dawn tier wheat purchase is requested in full and placed after the turn's sales and hires.
                            The engine fills a purchase unit by unit while cash lasts, so the sales fund it and the hires
                            keep their priority; the old cap on the cash at the start of the turn bought 1 of 8 and latched.

usage: patch_exec_market_fix_20260929.py <source.py> <output.py>"""
import sys
from pathlib import Path


def patch(s):
    def rep(old, new):
        nonlocal s
        assert s.count(old) == 1, (s.count(old), old[:80])
        s = s.replace(old, new)

    rep('''    "hires_at_front": True,''', '''    "hires_at_front": True,
    "sd_market_carried_actual": 0,   # 1: _market counts the hands' wheat from their actual inventories (this turn's pickups
    # are still in the observed shed; counting them as carried too double counts them)
    "sd_tier_wheat_buy_live": 0,     # 1: the dawn tier wheat buy is requested in full after the sales and hires (the engine
    # fills it unit by unit while cash lasts) instead of capped on the starting cash and latched''')
    rep('''            unlocked, farm, pos, last_day):
    T = _T
''', '''            unlocked, farm, pos, last_day):
    T = _T
    if CFG["sd_market_carried_actual"]:
        act_ = Counter()
        for inv_ in invs:
            act_.update(inv_)
        if int(CFG["sd_market_carried_actual"]) >= 2:  # wheat only: other goods keep the dispatcher's carried counts
            carried = Counter(carried)                 # (they drive the midnight-cap sales; mode 1 moved wool sale days)
            carried["WHEAT"] = act_.get("WHEAT", 0)
        else:
            carried = act_
''')
    # sd_seeds_first (hand-planned opening, 2026-09-29): the plan's seed purchases go ahead of feed-wheat purchases in the
    # order list (the engine fills orders in list order unit by unit while cash lasts): the executor-played DSM plan bought
    # 7 feed wheat on day 0 and could afford only 5 of its 6 melon seeds (one melon tile never planted)
    rep('''    "sd_tier_wheat_buy_live": 0,''', '''    "sd_seeds_first": 0,             # 1: seed purchases ahead of feed-wheat purchases in the order list
    "sd_tier_wheat_buy_live": 0,''')
    rep('''    buys = wheat_buy + buys''', '''    buys = (buys + wheat_buy) if CFG["sd_seeds_first"] else (wheat_buy + buys)''')
    # sd_books_reserve (2026-09-29): the pace seller of the books products sold a share of the WHOLE shed stock, ignoring
    # the market's own reserve (today's feed wheat, planned fertilizes): the executor-played DSM plan sold 174 of wheat on
    # day 1 while two sheep went unfed and escaped at dawn of day 2. With the flag the pace works on shed - reserve.
    rep('''    "sd_seeds_first": 0,''', '''    "sd_seeds_first": 0,
    "sd_books_reserve": 0,           # 1: the books pace seller sells from shed - reserve (feed wheat, planned fertilize)''')
    rep('''            for p_ in sorted(bk_):
                have_ = int(shed.get(p_, 0) or 0)''', '''            for p_ in sorted(bk_):
                have_ = int(shed.get(p_, 0) or 0)
                if CFG["sd_books_reserve"]:
                    have_ = max(0, have_ - int(reserve.get(p_, 0) or 0))''')
    rep('''        k_ = int(TPw_["wheat_buy"])
        pw_ = max(1, prices.get("WHEAT", 25))
        k_ = min(k_, int(money // (pw_ + 2)))
        if k_ > 0:                                 # first in the list: it lands before the hour-1 pickups
            orders = [["BUY_PRODUCT", "WHEAT", k_]] + [o for o in orders if not (o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")][:9]
        TPw_["wheat_bought"] = True''', '''        k_ = int(TPw_["wheat_buy"])
        pw_ = max(1, prices.get("WHEAT", 25))
        if CFG["sd_tier_wheat_buy_live"]:
            rest_ = [o for o in orders if not (o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")]
            at_ = 0
            for i_, o_ in enumerate(rest_):
                if o_[0] in ("SELL", "HIRE") or (CFG["sd_seeds_first"] and o_[0] == "BUY_SEED"):
                    at_ = i_ + 1
            at_ = min(at_, 9)
            if k_ > 0:
                orders = (rest_[:at_] + [["BUY_PRODUCT", "WHEAT", k_]] + rest_[at_:])[:10]
        else:
            k_ = min(k_, int(money // (pw_ + 2)))
            if k_ > 0:                                 # first in the list: it lands before the hour-1 pickups
                orders = [["BUY_PRODUCT", "WHEAT", k_]] + [o for o in orders if not (o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")][:9]
        TPw_["wheat_bought"] = True''')
    return s


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    assert src.resolve() != out.resolve(), "refusing an in-place edit"
    s = patch(src.read_text(encoding="utf-8"))
    compile(s, str(out), "exec")
    out.write_text(s, encoding="utf-8", newline="\n")
    print("patched ->", out)

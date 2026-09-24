# sem_market: hold-and-batch SELL rule learned from the 3000+ leader corpus (2026-09-24).
#
# Self-contained fragment (stdlib only, `_smk_` / `SMK_` prefixes) so it can be pasted into a single-file agent.
#
# Engine facts used (data/kaggriculture.py): a product's price is a pure function of its market inventory
# (obs["market"]["inventory"], public); every unit sold above $1 raises the inventory by 1 for good, town consumption
# lowers it on a fixed schedule (each unlocked shop 1 unit per 4 steps, 2 for a single-product shop; the town centre
# 1 per 24 steps). So a unit's price depends only on (units sold before it by anyone) - (consumption so far), and a
# seller does best by selling each unit when the market is locally EMPTIEST, i.e. when the price is near its recent
# high - not the moment it reaches the shed, and never into the dip right after the rival (or we) dumped a lot.
#
# Leaders (54 logged leader worlds, results/fresh/market_events_20260924/LEADER): they hold ~5-9 units per product,
# sell in 10-26% of the steps they have stock, in lots of ~3, mostly right after a consumption tick (t % 4 == 1) and
# more often when the price is at its 24-step high (P 0.44-0.56 vs 0.15-0.21 when >10% below it).
#
# RULE (per product p, per step; everything observable):
#   ref  = max published price of p over the last W steps (including now)
#   thr  = q_p * ref
#   sell the units whose exact marginal price f(inventory + j) is >= thr ("sell down the price to q of the recent
#          high"), at most have - keep_p; discretionary sells only at post-tick steps (t % 4 == 1) when post_tick
#   hold at the $1 floor (a floor sale earns 1 and moves nothing)
#   forced: stock above smax_p is sold regardless of price; total held above cap_total -> sell the excess
#   liquidation: from liq_step on, thr falls linearly to 0 at the last executed step (718); all left is sold at 718
#
# Entry point
#   sell_orders(obs, player, stock, reserve, state, params=None) -> [["SELL", item, n], ...]
#     stock   {product: units in our shed}            (obs private shed is fine)
#     reserve {product: units that must not be sold} (wheat the herd eats, fertilizer for pending jobs)
#     state   dict owned by the caller, kept across steps (price history); pass {} at game start
#   decide(item, t, inv, hist, have, prm, g, flow) -> units   (pure core, used by the offline evaluator)
#   wheat_buy(obs, player, stock_w, need_w, n_fed, room, cash_free, state, params=None) -> units of wheat to buy now
#     WHEAT POLICY (coordinator scope, 2026-09-24): shops drain wheat, so its price climbs ~25 -> ~40 by day 12 (54 logged
#     leader worlds: median 25 / 30 / 34 / 37 / 40 at days 0 / 4 / 8 / 10 / 12, flat ~37-41 after). Buy ahead while it
#     is cheap: cover the herd's next `cover_days` of feed (plus optional `arb_units` to resell later) when the buy quote
#     is <= buy_max_price and day <= buy_last_day, bounded by shed room and by the cash left after every other purchase
#     minus cash_reserve. The sell side keeps the caller's herd reserve and sells the surplus by the hold rule.

SMK_LAST_STEP = 718
SMK_PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
SMK_MARKET = {
    "WHEAT":      (25, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT":     (35, 450, "hinge", 1.00, "sqrt", 0.70),
    "TOMATO":     (60, 200, "hinge", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON":      (250, 300, "log", 0.20, "sq", 3.60),
    "EGG":        (50, 332, "hinge", 0.40, "log", 0.20),
    "MILK":       (160, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL":       (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}
SMK_I0 = 10000

# global parameters
SMK_G = {
    "W": 6,               # steps of price history for the reference high
    "post_tick": True,    # discretionary sells only at t % 4 == 1 (right after a consumption tick)
    "liq_step": 696,      # day 29 hour 0: the threshold falls linearly to 0 at step 718; all is sold from step 717
    "cap_total": 70,      # held units over all products incl. reserves (shed cap 100; purchases fail at 100)
    "floor": 1,           # never sell at <= this price before the last steps (unless forced)
    "H": 48,              # steps of market flow for the rival-rate estimate
    "kappa": 1.0,         # hold only while town consumption > kappa x the rival's sales rate (else sell at once)
}
# per-product parameters. mode 'asap' = everything above the reserve at once (the deploy rule: wheat above the herd's
# keep, fertilizer, melon - everyone harvests melons on day 10 and the first seller wins); 'hold' = the rule above.
# Chosen by an exact market-only replay (54 leader worlds x {leader, y3} production, rival sales fixed; see
# docs/sem_market_progress.md): the largest own-revenue gain that does not lower the margin on either production.
SMK_P = {
    "WHEAT":      {"mode": "asap"},
    "CARROT":     {"mode": "hold", "q": 1.00, "keep": 0, "smax": 30},
    "TOMATO":     {"mode": "hold", "q": 1.00, "keep": 0, "smax": 30},
    "STRAWBERRY": {"mode": "hold", "q": 1.00, "keep": 0, "smax": 30},
    "MELON":      {"mode": "asap"},
    "EGG":        {"mode": "hold", "q": 1.00, "keep": 0, "smax": 30},
    "MILK":       {"mode": "hold", "q": 0.90, "keep": 0, "smax": 10},
    "WOOL":       {"mode": "hold", "q": 0.95, "keep": 0, "smax": 30},
    "FERTILIZER": {"mode": "asap"},
}


SMK_WHEAT = {
    "on": False,            # G1 (12 leader worlds): -0.013 vs the sell rule alone, margin -2.9k; see the progress doc
    "cover_days": 10,       # herd feed days bought ahead
    "buy_max_price": 34,    # only while the buy quote is at most this
    "buy_last_day": 10,     # ... and only up to this day (the climb is over by day ~12)
    "room_total": 85,       # never fill the shed above this (all products + animals)
    "cash_reserve": 300,    # cash kept after every other purchase of the step
    "arb_units": 0,         # extra units bought to resell later (0 = feed cover only)
}


def _smk_shape(func, x, T):
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return x ** 0.5
    if func == "log":
        import math
        return math.log(1.0 + x)
    if func == "hinge":
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    return x


def smk_price(item, inv):
    """exact engine price of `item` at market inventory `inv` (data/kaggriculture.py market_price)."""
    base, T, fb, tb, fa, ta = SMK_MARKET[item]
    if inv < SMK_I0:
        price = base + tb * base / _smk_shape(fb, T, T) * _smk_shape(fb, SMK_I0 - inv, T)
    else:
        price = base - ta * base / _smk_shape(fa, T, T) * _smk_shape(fa, inv - SMK_I0, T)
    return max(1, int(round(price)))


def decide(item, t, inv, hist, have, prm, g, flow=None):
    """units of `item` to sell at step t. inv = market inventory now, hist = published prices of the last steps
    (hist[-1] = now), have = sellable stock (above the reserve), flow = (rival units per step, consumption per step)
    over the recent window or None."""
    if have <= 0:
        return 0
    if t >= SMK_LAST_STEP - 1:
        return have
    if prm.get("mode", "hold") == "asap":
        return have
    price = smk_price(item, inv)
    kappa = prm.get("kappa", g.get("kappa", 0))
    if kappa and flow is not None and kappa * flow[0] >= flow[1] and price > g.get("floor", 1):
        return have        # the rival out-sells consumption: the market will not recover, holding only helps the rival
    forced = max(0, have - int(prm.get("smax", 10 ** 6)))
    if t >= g["liq_step"]:
        frac = max(0.0, (SMK_LAST_STEP - t) / float(max(1, SMK_LAST_STEP - g["liq_step"])))
    else:
        frac = 1.0
    if g.get("post_tick") and t % 4 != 1 and t < g["liq_step"]:
        return forced
    if price <= g.get("floor", 1):
        return forced
    ref = max(hist[-int(g["W"]):]) if hist else price
    thr = prm.get("q", 0.95) * ref * frac
    n = 0
    lim = have - int(prm.get("keep", 0))
    while n < lim and smk_price(item, inv + n) >= max(thr, g.get("floor", 1) + 1):
        n += 1
    return max(n, forced)


SMK_SHOPS = {
    "BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"], "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE": ["WOOL"], "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"], "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}


def _smk_get(o, k, default=None):
    try:
        v = o[k]
        return default if v is None else v
    except (KeyError, TypeError, IndexError):
        return getattr(o, k, default)


def smk_consumption(shops, item, s):
    """town consumption of `item` in step s (applied after that step's market phase)."""
    c = 0
    if s % 4 == 0:
        for sh in shops:
            prods = SMK_SHOPS.get(sh, ())
            if item in prods:
                c += 2 if len(prods) == 1 else 1
    if s % 24 == 0 and item != "FERTILIZER":
        c += 1
    return c


def sell_orders(obs, player, stock, reserve, state, params=None, sold_total=None):
    """sold_total: {product: units we have ordered to sell so far, all sources} (optional; used to separate our own
    sales from the rival's in the observed inventory change). Without it the module's own orders are used."""
    g = dict(SMK_G)
    P = SMK_P
    if params:
        g.update({k: v for k, v in params.items() if k in SMK_G})
        if params.get("P"):
            P = {p: dict(SMK_P[p], **params["P"].get(p, {})) for p in SMK_P}
    market = _smk_get(obs, "market", {})
    inv = dict(_smk_get(market, "inventory", {}))
    prices = dict(_smk_get(market, "prices", {}))
    shops = list(_smk_get(_smk_get(obs, "town", {}), "unlocked_shops", []) or [])
    t = int(_smk_get(obs, "step", 0))
    hist = state.setdefault("hist", {})
    rec = state.setdefault("rec", [])            # [(t, {p: inventory}, {p: our cumulative sold}, shops)]
    own = state.setdefault("own", {})
    if state.get("t") != t:
        state["t"] = t
        for p in SMK_PRODUCTS:
            h = hist.setdefault(p, [])
            h.append(int(prices.get(p, smk_price(p, inv.get(p, SMK_I0)))))
            del h[:-max(1, int(g["W"]))]
        cum = dict(sold_total) if sold_total is not None else dict(own)
        rec.append((t, {p: int(inv.get(p, SMK_I0)) for p in SMK_PRODUCTS}, cum, tuple(shops)))
        while rec and rec[0][0] < t - int(g["H"]):
            rec.pop(0)
    flows = {}
    if len(rec) >= 2 and rec[-1][0] == t:
        t0, inv0, cum0 = rec[0][0], rec[0][1], rec[0][2]
        cum1 = rec[-1][2]
        span = max(1, t - t0)
        shop_at = []                              # shops in force at each step t0..t-1 (the latest record at or before)
        j = 0
        for s_ in range(t0, t):
            while j + 1 < len(rec) and rec[j + 1][0] <= s_:
                j += 1
            shop_at.append(rec[j][3])
        for p in SMK_PRODUCTS:
            cons = sum(smk_consumption(shop_at[s_ - t0], p, s_) for s_ in range(t0, t))
            riv = int(inv.get(p, SMK_I0)) - inv0[p] - (cum1.get(p, 0) - cum0.get(p, 0)) + cons
            rate = sum(smk_consumption(shops, p, s_) for s_ in range(t, t + 24)) / 24.0
            flows[p] = (max(0, riv) / float(span), rate)
    orders = []
    held = 0
    for p in SMK_PRODUCTS:
        have = int(stock.get(p, 0) or 0) - int(reserve.get(p, 0) or 0)
        if have <= 0:
            held += max(0, int(stock.get(p, 0) or 0))
            continue
        n = decide(p, t, int(inv.get(p, SMK_I0)), hist.get(p, []), have, P.get(p, {}), g, flows.get(p))
        n = max(0, min(n, have))
        if n:
            orders.append(["SELL", p, n])
        held += int(stock.get(p, 0) or 0) - n
    extra = held - int(g["cap_total"])
    if extra > 0:           # shed pressure: sell the excess from the products nearest their recent high
        sold = {o[1]: o[2] for o in orders}
        cand = []
        for p in SMK_PRODUCTS:
            can = int(stock.get(p, 0) or 0) - int(reserve.get(p, 0) or 0) - sold.get(p, 0)
            if can > 0:
                h = hist.get(p) or [1]
                cand.append((-(smk_price(p, int(inv.get(p, SMK_I0)) + sold.get(p, 0)) / float(max(1, max(h)))), p, can))
        for _, p, can in sorted(cand):
            if extra <= 0:
                break
            k = min(can, extra)
            sold[p] = sold.get(p, 0) + k
            extra -= k
        orders = [["SELL", p, n] for p, n in sold.items() if n > 0]
    for o in orders:
        own[o[1]] = own.get(o[1], 0) + o[2]
    return orders


def wheat_buy(obs, player, stock_w, need_w, n_fed, room, cash_free, state, params=None):
    """units of WHEAT to buy this step (buy-ahead). stock_w = wheat in the shed + carried, need_w = wheat still needed
    today, n_fed = animals we feed, room = free shed slots we may fill, cash_free = cash after the step's other orders."""
    w = dict(SMK_WHEAT)
    if params and params.get("wheat"):
        w.update(params["wheat"])
    if not w.get("on"):
        return 0
    t = int(_smk_get(obs, "step", 0))
    day = t // 24
    if day > int(w["buy_last_day"]) or n_fed <= 0 and not w.get("arb_units"):
        return 0
    inv = int(dict(_smk_get(_smk_get(obs, "market", {}), "inventory", {})).get("WHEAT", SMK_I0))
    target = int(n_fed) * int(w["cover_days"]) + max(0, int(need_w)) + int(w.get("arb_units", 0))
    want = min(target - int(stock_w), int(room))
    budget = float(cash_free) - float(w["cash_reserve"])
    n = 0
    while n < want:
        q = smk_price("WHEAT", inv - 1 - n)        # engine quotes a buy at the post-buy inventory
        if q > w["buy_max_price"] or budget < q:
            break
        budget -= q
        n += 1
    return n

"""v18za -> v18zb: sd_goods_sale (default None) - sd_straw_sale's margin hold rule for the animal goods (MILK / WOOL; EGG
accepted), each product with its own engine price curve, town draws and rival holdings. sd_straw_sale is untouched.

User 2026-09-30: generalize the strawberry hold rule to milk and wool. Evidence (offline market-only re-pricing, 9 worlds,
our n18rc127 supply, rival frozen on its recorded ticks, exact engine pricing incl. the $1 floor; goods_eval.py = the
generic-product copy of scripts/strawberry_sale_eval_20260930.py, 2026-09-30 thread scratchpad; no games run). Margin =
our revenue of the good - the rival's, mean per world:
  MILK  recorded -737; hold H12 theta 4 same_tick 0.5 -321 (+416), H24 -325 (+412); DSM's own selling shares applied to
        our supply -377 (+360). On DSM's supply the rule loses to DSM's recorded selling (+471 vs +747).
  WOOL  recorded -2,698; hold H24 theta 4 same_tick 1.0 -2,157 (+541) / 0.5 -2,171 (+527), H12 below the top six
        (< -2,438); DSM's own shares on our supply -1,793 (+905, better than the rule); on DSM's supply the rule gives
        -878 against DSM's recorded -48. The WOOL market sits at the $1 floor for 15-250 ticks in 7 of 9 worlds: a sale at
        $1 does not move the market stock, so the executor cannot see the rival's floor sales (the offline rule used its
        true units) - the WOOL evidence is the weaker one.
CAVEATS as sd_straw_sale (frozen-replay rivals, market-only, the shed / other goods at their recorded levels, not a full
game) plus the WOOL ones above: check it on the day-11 world in the viewer, then on a paired fixed-shop Kaggle panel.

config sd_goods_sale {"MILK": {"days": [12, 29], "H": 12, "theta": 4.0, "win": 1, "prior": 20.0, "f0": 0.08,
                               "same_tick": 0.5, "phase": 1, "front": 1, "room": 1},
                      "WOOL": {the same keys; H 24 was WOOL's best offline}}
  any subset of the animal goods (EGG / MILK / WOOL; other names are ignored); a missing key takes the value above
  ("ripe": false as in sd_straw_sale). Requires a non-empty sd_books_sell (the rule runs inside the books block).
  every step (_gsale_track, public data only, from the first executor step; in our entry that is step 144): per configured
    good, the rival's harvests of the previous step from its public board (its COW / SHEEP / GOOSE tiles, same tile and
    placed_day): the engine's HARVEST takes the whole yield; the hour-23 refresh adds, on a production day, 1 + the whole
    care bank (the previous observation's pending_care_bonus) when the animal was fed that day (consecutive_unfed == 0
    after the refresh) else 1, capped at max_held; an animal unfed two days escapes (its yield is lost, not harvested); a
    yield below that no-harvest projection = a harvest of the whole previous yield. Its sales from S["_riv_hist"]
    (_rival_infer, now also called with the rule's goods: market stock change - our sells + town draws). Holdings
    R = harvested - sold (floored at 0) and the exposure E / Sx exactly as _ssale_track;
  at step t with day in the good's days (_gsale_n = _ssale_n with the good's price curve _gsale_pc - the engine's _shape
    with math.sqrt / math.log as there: MILK sqrt below / linear above, WOOL log below / sq above ($1 from ~59 units of
    glut) - and the good's draws: each unlocked shop listing it takes 1 every 4 steps, a single-product shop (YARN_STORE)
    2, the town centre 1 a day): SELL the whole shed stock after this step's arrivals (_gsale_shed_after) or hold;
  books goods (MILK in our configs): the rule replaces the books (pace) quantity, as sd_straw_sale does for STRAWBERRY;
  other goods (WOOL: in our configs sold on arrival by the generic `for p in PRODUCTS` loop of _market, sd_clean ->
    quota = shed stock): that loop skips them on the rule's days, and every other SELL of them (hire / seed funding, the
    overflow guards, sd_tier_deliver's sell-at-once) is replaced by the rule's order, as the books block does for its
    own products; a flag without WOOL leaves WOOL exactly as before;
  front 1: the rule's sells go to the head of the queue, ordered by our units x the rival's expected units this tick x the
    price drop a unit causes (what index 0, in lockstep with the rival's usual index-0 lump, is worth), then by value;
    sd_straw_sale's STRAWBERRY move to index 0 (A6) is unchanged and runs after it;
  10-order cap (hires and buys are never dropped, as before): other sells go first (non-books from the end, then books),
    then the rule's least valuable sell; the unchanged cap loop after it only meets sd_straw_sale's STRAWBERRY;
  room 1: from hour 21, after sd_straw_sale's guard, the projected midnight load computed as that guard does (shed +
    everything carried + the tier plan's remaining harvest when it is today's - this tick's sells) above 100 -
    sd_tier_dump_buffer is sold from the rule's held goods, the cheapest good first; those room sells are exempt from
    the walk floor when sd_books_cap_free is set, like sd_books_cap's own room sales;
  the walk (sd_books_walk), sd_books_cap and the step-718 sell-all are unchanged and see the rule's orders; sd_tier_sclu /
  sd_tier_bb deliveries of a rule good are not sold on arrival on its days (the rule's avail counts that PLACE); the
  hour-0 hire-slot estimate (sd_books_h0_slots, pace) counts no sell of a rule good at hour 0 (phase != 0); 29 in days:
  the last day runs the rule instead of the endgame's sell-everything-every-tick.
  NOT modelled (as sd_straw_sale): room for a mid-day DROP or for the hour-0 feed-wheat BUY while goods are held (the
  offline evaluation kept room at every tick); rival harvests before the executor's first step; the rival's sales at $1.
  Keep "days" from 11 on: the entry's early financing (days 6-10) releases a books good for cash by taking it out of
  sd_books_sell, and the rule's non-books path would then hold it.
Flag off (None): every inserted statement is behind `if CFG.get("sd_goods_sale")`, `if gsale_cfg_` or an empty
gs_on_ / gs_x_ / gs_rm_ / gs_fr_; the only unguarded additions are the CFG key, the helper definitions (never called) and
the reads at the top of _market. This script checks each anchor occurs once, that the new names were absent from v18za,
the placements next to sd_straw_sale's blocks, that deleting every inserted block gives v18za back byte for byte, and
compiles v18zb.

usage: patch_exec_goods_sale_20260930.py  (writes agents/mgt_lead_kb115lt2_v18zb.py from v18za)"""
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18za.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18zb.py"

_INSERTED = []                                     # (anchor, anchor with its block) in application order


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def ins_after(s, anchor, block):
    new = anchor + block
    _INSERTED.append((anchor, new))
    return sub(s, anchor, new)


def ins_before(s, anchor, block):
    new = block + anchor
    _INSERTED.append((anchor, new))
    return sub(s, anchor, new)


CFG_LINE = '''    "sd_goods_sale": None,    # v18zb (2026-09-30; see scripts/patch_exec_goods_sale_20260930.py; offline MILK margin +416 a world vs our recorded selling, WOOL +541 with H 24) {"MILK": {"days": [12, 29], "H": 12, "theta": 4.0, "win": 1, "prior": 20.0, "f0": 0.08, "same_tick": 0.5, "phase": 1, "front": 1, "room": 1}, "WOOL": {the same keys}} (any subset of EGG / MILK / WOOL; needs a non-empty sd_books_sell): sd_straw_sale's margin hold rule for each animal good with its own engine price curve, town draws and the rival's public holdings (its cows / sheep / geese: harvests from yield drops against the night's production; its sales inferred from the market); a books good (MILK) has its pace quantity replaced, another (WOOL: sold on arrival by the sd_clean loop) every other sell of it replaced by the rule's; front: queue head, behind sd_straw_sale's STRAWBERRY; room: from hour 21 the held goods make the midnight room, cheapest first; 29 in days: the last day too; keep days >= 11 (the entry's day 6-10 financing releases books goods). None = off
'''

HELPERS = '''

# ---- sd_goods_sale (v18zb, default None): sd_straw_sale's margin hold rule for the animal goods --------------------------
# make_hold_rule / RivalView of scripts/strawberry_sale_eval_20260930.py with each good's own engine price curve and town
# draws (its generic-product copy goods_eval.py, 2026-09-30); the rival's holdings from its public board (the good's
# animal), its sales from the market (_rival_infer)
_GSALE_SRC = {"EGG": "GOOSE", "MILK": "COW", "WOOL": "SHEEP"}


def _gsale_on(item, day):
    """sd_goods_sale has item (an animal good), sd_books_sell is set (the rule runs in the books block) and day is in the
    item's "days"."""
    cfg = (CFG.get("sd_goods_sale") or {}).get(item)
    if not cfg or item not in _GSALE_SRC or not CFG.get("sd_books_sell"):
        return False
    d0, d1 = (cfg.get("days") or [12, 29])[:2]
    return int(d0) <= int(day) <= int(d1)


def _gsale_shape(func, x, T):
    """the engine's _shape (kaggriculture.py 1.32.7), with math.sqrt / math.log as there"""
    x = max(0.0, x)
    if func == "linear":
        return x
    if func == "sq":
        return x * x
    if func == "sqrt":
        return _math.sqrt(x)
    if func == "log":
        return _math.log(1.0 + x)
    if func == "hinge":
        u = x / T
        return u + _MKT_HINGE * max(0.0, u - 1.0) ** 2
    return x


def _gsale_pc(item, x):
    """the engine's price of item at market stock x, unrounded, floor kept: MILK 160 + 8.69 sqrt(10000 - x) below 10000,
    max(1, 160 - 2.10 (x - 10000)) above; WOOL 200 + 8.58 ln(10001 - x) below, max(1, 200 - 0.0580 (x - 10000)^2) above
    ($1 from ~59 units of glut)"""
    p = _MKT_PARAMS[item]
    base, T = p["base"], p["T"]
    if x < _MKT_I0:
        amp = p["below_target"] * base / _gsale_shape(p["below_func"], T, T)
        v = base + amp * _gsale_shape(p["below_func"], _MKT_I0 - x, T)
    else:
        amp = p["above_target"] * base / _gsale_shape(p["above_func"], T, T)
        v = base - amp * _gsale_shape(p["above_func"], x - _MKT_I0, T)
    return max(float(_MKT_FLOOR), float(v))


def _gsale_track(S, obs, step, items):
    """sd_goods_sale, once a step (in _market after _rival_infer of these items, so S["_riv_hist"] holds the rival's sales
    of step - 1): the rival's public holdings of each animal good, as _ssale_track does for strawberries.
      harvests of step - 1: its animals of the good's species on the previous and on this observation (same tile, same
        placed_day). The engine's HARVEST takes the tile's whole yield; the hour-23 refresh adds, on a production day, 1 +
        the whole care bank (the previous observation's pending_care_bonus) when the animal was fed that day
        (consecutive_unfed == 0 after the refresh) else 1, capped at max_held; an animal unfed two days escapes (the tile
        keeps no animal: its yield is lost, not harvested). A yield below that no-harvest projection = a harvest of the
        whole previous yield (a harvest at hour 23 of a production day is invisible only when 1 + bank >= max_held);
      holdings R(t) = max(0, R(t-1) - sold(t-1)) + harvested(t-1) (milk / wool / eggs cannot be bought, so a sale beyond
        the tracked holdings can only be a harvest the board did not show);
      exposure: after each step t' on day >= 11 with R(t') > 0: E[(day, hour)] += R(t'), Sx[(day, hour)] += min(sold, R)."""
    G = S.setdefault("_gsale", {})
    me = int(_g(obs, "player", 0))
    farms = _g(obs, "farms", []) or []
    tiles = farms[1 - me]["tiles"] if len(farms) > 1 else []
    rh = S.get("_riv_hist") or {}
    s1 = step - 1
    for item in items:
        sp = _GSALE_SRC[item]
        st = G.get(item)
        if st is None:
            st = G[item] = {"step": -1, "prev": None, "pstep": -1, "R": 0, "Rstep": -1, "E": {}, "Sx": {},
                            "harv": 0, "sold": 0, "ripe": 0}
        if st["step"] == step:
            continue
        st["step"] = step
        cur, ripe = {}, 0
        for y_ in range(len(tiles)):
            for x_ in range(len(tiles[y_])):
                t_ = tiles[y_][x_]
                if isinstance(t_, dict) and t_.get("animal") == sp:
                    yv_ = int(t_.get("yield_units", 0) or 0)
                    cur[y_ * 10 + x_] = (yv_, int(t_.get("placed_day", -99)), int(t_.get("pending_care_bonus", 0) or 0),
                                         int(t_.get("consecutive_unfed", 0) or 0))
                    ripe += max(0, yv_)
        E, Sx = st["E"], st["Sx"]
        if st["Rstep"] == s1 and st["R"] > 0 and s1 >= 0 and s1 // 24 >= 11:
            k_ = divmod(s1, 24)
            E[k_] = E.get(k_, 0.0) + st["R"]
            Sx[k_] = Sx.get(k_, 0.0) + min(int(rh.get((s1, item), 0) or 0), st["R"])
        harv = 0
        prev = st["prev"]
        if prev is not None and st["pstep"] == s1:
            a_ = ANIMALS[sp]
            d1_, eod_ = s1 // 24, (s1 + 1) % 24 == 0
            for idx, (yp, pd, bank, _cu) in prev.items():
                now = cur.get(idx)
                if yp <= 0 or now is None or now[1] != pd:
                    continue                       # nothing to take, or the animal escaped / another one stands there
                exp_ = yp
                if eod_:
                    dsf = d1_ + 1 - pd - a_["first"]
                    if dsf >= 0 and dsf % max(1, a_["interval"]) == 0:
                        exp_ = min(a_["max_held"], yp + 1 + (bank if now[3] == 0 else 0))
                if now[0] < exp_:
                    harv += yp                     # harvested to 0 (then the night's production)
        elif prev is not None:                     # a gap in the steps seen: plain yield drops
            for idx, (yp, pd, _b, _cu) in prev.items():
                now = cur.get(idx)
                if now is not None and now[1] == pd and now[0] < yp:
                    harv += yp
        sold = 0
        if st["Rstep"] >= 0:
            sold = sum(int(rh.get((s_, item), 0) or 0) for s_ in range(st["Rstep"], step))
        st["R"] = max(0, int(st["R"]) - sold) + harv
        st["Rstep"] = step
        st["prev"], st["pstep"] = cur, step
        st["harv"] += harv
        st["sold"] += sold
        st["ripe"] = ripe
    return G


def _gsale_shed_after(S, obs, shed, invs, pos, tiles):
    """sd_goods_sale: our whole shed after this step's unit commands, before the market (_ssale_shed_after for every good:
    the farmer, then each hand; PICKUP takes from the shed, PLACE / DROP add up to the room left of the 100-unit shed, DROP
    empties the inventory in its item order, an animal PLACE on its own structure does not touch the shed). Without this
    step's commands (S["_gsale_act"] from the agent): the observed shed."""
    step = int(_g(obs, "step", 0))
    sh = Counter({k: int(v or 0) for k, v in shed.items()})
    sa = S.get("_gsale_act")
    if not sa or sa[0] != step:
        return sh
    inv = [Counter({k: int(v or 0) for k, v in (i or {}).items()}) for i in invs]
    for u, a in enumerate(sa[1]):
        if u >= len(pos) or u >= len(inv) or not a or not _is_shed_adjacent_t(pos[u]):
            continue
        op = a[0]
        try:
            n = int(a[2]) if len(a) >= 3 else 1
        except (TypeError, ValueError):
            continue
        if op == "DROP":
            for it_, k_ in list(inv[u].items()):
                if k_ > 0:
                    sh[it_] += min(k_, max(0, 100 - sum(sh.values())))
            inv[u] = Counter()
        elif op == "PICKUP" and len(a) >= 2 and n > 0:
            k_ = min(n, int(sh.get(a[1], 0)))
            if k_ > 0:
                sh[a[1]] -= k_
                inv[u][a[1]] += k_
        elif op == "PLACE" and len(a) >= 2 and n > 0:
            it_ = a[1]
            t_ = tiles[pos[u][1]][pos[u][0]] if tiles else None
            if it_ in ANIMALS and isinstance(t_, dict) and t_.get("kind") == ANIMALS[it_]["structure"] and "animal" not in t_:
                continue
            k_ = min(n, int(inv[u].get(it_, 0)), max(0, 100 - sum(sh.values())))
            if k_ > 0:
                sh[it_] += k_
                inv[u][it_] -= k_
    return sh


def _gsale_n(S, obs, item, day, hour, avail):
    """sd_goods_sale decision for item at this step: avail (the whole shed stock after this step's arrivals) or 0 (hold) -
    _ssale_n with the item's price curve and town draws. Keeps the lockstep value of this tick (the rival's expected
    units now x the price drop a unit causes) for the queue order (_gsale_lock)."""
    cfg = (CFG.get("sd_goods_sale") or {}).get(item) or {}
    lg = S["log"]
    if avail <= 0:
        return 0
    step = int(_g(obs, "step", 0))
    Hh = min(int(cfg.get("H", 12)), 718 - step)
    if Hh <= 0:
        return int(avail)
    ph = int(cfg.get("phase", 1))
    if step % 4 != ph:
        return 0
    st = (S.get("_gsale") or {}).get(item) or {}
    E, Sx = st.get("E") or {}, st.get("Sx") or {}
    win, prior, f0 = int(cfg.get("win", 1)), float(cfg.get("prior", 20.0)), float(cfg.get("f0", 0.08))
    days = range(max(11, day - win), day + 1)
    ex = [sum(E.get((d_, h_), 0.0) for d_ in days) for h_ in range(24)]
    hi = [sum(Sx.get((d_, h_), 0.0) for d_ in days) for h_ in range(24)]
    if sum(ex) <= 0:
        f = [f0 * 4 if h_ % 4 == 1 else 0.0 for h_ in range(24)]
    else:
        pooled = sum(hi) / sum(ex)
        f = [(hi[h_] + prior * pooled) / (ex[h_] + prior) for h_ in range(24)]
    R = float(st.get("R", 0) or 0) + (float(st.get("ripe", 0) or 0) if cfg.get("ripe") else 0.0)
    shops = list(_g(_g(obs, "town", {}), "unlocked_shops", []) or [])
    nsh = sum((2 if len(_SHOPS_E.get(s_, ())) == 1 else 1) for s_ in shops if item in _SHOPS_E.get(s_, ()))
    ctr = 0 if item == "FERTILIZER" else 1         # the town centre takes 1 of every good but fertilizer a day
    I0 = float(int((_g(_g(obs, "market", {}), "inventory", {}) or {}).get(item, _MKT_I0)))
    stc, theta = float(cfg.get("same_tick", 0.5)), float(cfg.get("theta", 4.0))
    p0 = _gsale_pc(item, I0)
    Ij, ext, best, lk = I0, 0.0, -1e9, 0.0
    for j in range(Hh + 1):
        o = f[(step + j) % 24] * R
        R -= o
        sl = _gsale_pc(item, Ij) - _gsale_pc(item, Ij + 1)
        if j == 0:
            lk = o * sl
        elif (step + j) % 4 == ph:
            g = _gsale_pc(item, Ij) - p0 - ext - stc * o * sl
            if g > best:
                best = g
        ext += o * sl
        Ij += o - ((nsh if (step + j) % 4 == 0 else 0) + (ctr if (step + j) % 24 == 0 else 0))
    if st:
        st["lk"] = (step, lk)
    if best <= theta:
        lg["goods_sale_sell_ticks_" + item] += 1
        return int(avail)
    lg["goods_sale_hold_ticks_" + item] += 1
    lg["goods_sale_hold_units_" + item] += int(avail)
    return 0


def _gsale_lock(S, item, step, n, price):
    """sd_goods_sale queue order (descending): our units x the lockstep value _gsale_n kept at this step, then our units x
    the quote"""
    lk = ((S.get("_gsale") or {}).get(item) or {}).get("lk")
    return (n * (float(lk[1]) if lk and lk[0] == step else 0.0), n * float(price or 0))
'''

# B3: this step's unit commands, stashed for the market (arrivals before the sale)
B3 = '''    if CFG.get("sd_goods_sale"):                   # sd_goods_sale: this step's unit commands (their shed arrivals precede the market)
        S["_gsale_act"] = (step, [list(a_) if isinstance(a_, (list, tuple)) else ["PASS"] for a_ in actions])
'''

# B4a: the rule's goods today (empty when off)
B4A = '''    gsale_cfg_ = CFG.get("sd_goods_sale")         # sd_goods_sale (v18zb): the animal goods' margin hold rule (None = off)
    gs_on_ = {p_ for p_ in (gsale_cfg_ or {}) if _gsale_on(p_, day)}   # its goods on today
    gs_x_ = gs_on_ - bk_                           # ... that are not books goods (WOOL): the rule replaces their other sells
'''

# B4b: the generic loop leaves the rule's non-books goods (WOOL: sold on arrival here in our configs) to the rule
B4B = '''        if p in gs_x_ and not endgame:
            continue                      # sd_goods_sale: sold below by the rule (in our configs WOOL was sold on arrival here)
'''

# B5: the rival's sales and public holdings of the rule's goods, every step
B5 = '''    if gsale_cfg_:                                 # sd_goods_sale: the rival's sales and public holdings of the rule's goods
        gp_ = tuple(p_ for p_ in sorted(gsale_cfg_) if p_ in _GSALE_SRC)
        if gp_:
            inv_riv_ = _rival_infer(S, obs, int(_g(obs, "step", 0)), gp_)
            _gsale_track(S, obs, int(_g(obs, "step", 0)), gp_)
'''

# B6a: our shed after this step's arrivals; no other sell of the rule's non-books goods
B6A = '''            if gs_on_:                             # sd_goods_sale: our shed after this step's arrivals, and no other sell of
                gsh_ = _gsale_shed_after(S, obs, shed, invs, pos, farm["tiles"])   # its non-books goods (WOOL)
                orders = [o for o in orders if not (o[0] == "SELL" and o[1] in gs_x_)]
'''

# B6: a books good (MILK): the rule replaces its books quantity
B6 = '''                if p_ in gs_on_:                   # sd_goods_sale: the hold rule, not the pace (a books good: MILK)
                    av_ = int(gsh_.get(p_, 0))
                    if CFG["sd_books_reserve"]:
                        av_ = max(0, av_ - int(reserve.get(p_, 0) or 0))
                    n_gs_ = _gsale_n(S, obs, p_, day, hour, av_)
                    if n_gs_ > 0:
                        front_.append((0, ["SELL", p_, int(n_gs_)]))
                        S["log"]["goods_sale_units_" + p_] += int(n_gs_)
                    continue
'''

# B7: the rule's non-books goods (WOOL) through the rule, right after the books loop
B7 = '''            for p_ in sorted(gs_x_):               # sd_goods_sale: its goods outside the books (WOOL) through the rule too
                n_gs_ = _gsale_n(S, obs, p_, day, hour, int(gsh_.get(p_, 0)))
                if n_gs_ > 0:
                    front_.append((0, ["SELL", p_, int(n_gs_)]))
                    S["log"]["goods_sale_units_" + p_] += int(n_gs_)
'''

# B8: the room guard for the rule's goods (after sd_straw_sale's, before sd_books_cap)
B8 = '''            gs_rm_ = [p_ for p_ in gs_on_ if int((gsale_cfg_.get(p_) or {}).get("room", 1))] if hour >= 21 else []
            if gs_rm_:                             # sd_goods_sale room guard: the rule's held goods make the midnight room
                TPg_ = S.get("tier") or {}
                load_g_ = (sum(int(v or 0) for v in shed.values())
                           + sum(int(v or 0) for inv_ in invs for v in (inv_ or {}).values()))
                if TPg_.get("day") == day:
                    load_g_ += int(TPg_.get("_harv_left", 0) or 0)
                load_g_ -= sum(int(o_[2]) for o_ in orders if o_[0] == "SELL") + sum(o_[2] for _, o_ in front_)
                ex_g_ = load_g_ - (100 - int(CFG["sd_tier_dump_buffer"]))
                for p_ in sorted(gs_rm_, key=lambda q: (float(prices.get(q, 0) or 0), q)):   # the cheapest good first
                    if ex_g_ <= 0:
                        break
                    done_g_ = sum(o_[2] for _, o_ in front_ if o_[1] == p_)
                    k_g_ = min(max(0, int(gsh_.get(p_, 0)) - int(done_g_)), int(ex_g_))
                    if k_g_ > 0:
                        hit_g_ = next((x for x in front_ if x[1][1] == p_), None)
                        if hit_g_:
                            hit_g_[1][2] += k_g_
                        else:
                            front_.append((0, ["SELL", p_, k_g_]))
                        if CFG["sd_books_cap_free"]:   # room beats price, as for sd_books_cap's own room sales
                            S.setdefault("_cap_free", set()).add((int(_g(obs, "step", 0)), p_))
                        ex_g_ -= k_g_
                        S["log"]["goods_sale_room_units_" + p_] += k_g_
'''

# B9: sd_tier_sclu / sd_tier_bb deliveries of a rule good wait for the rule on its days
B9 = '''                    if p_ in gs_on_:                  # sd_goods_sale: the trip's goods wait for the rule (its avail counts this PLACE)
                        S["log"]["goods_sale_arrive_units_" + p_] += max(0, int(n_))
                        continue
'''

# B10: the rule's sells at the queue head, then a 10-order cap that keeps them (before sd_straw_sale's A6 and the old cap)
B10 = '''            gs_fr_ = [p_ for p_ in gs_on_ if int((gsale_cfg_.get(p_) or {}).get("front", 1))]
            sel_g_ = [o_ for o_ in orders if o_[0] == "SELL" and o_[1] in gs_fr_] if gs_fr_ else []
            if sel_g_:                             # sd_goods_sale: the rule's sells at the queue head, the likeliest rival lump
                sel_g_.sort(key=lambda o_: _gsale_lock(S, o_[1], int(_g(obs, "step", 0)), int(o_[2]), prices.get(o_[1], 0)),
                            reverse=True)          # first (sd_straw_sale's STRAWBERRY move below still puts it at index 0)
                orders = sel_g_ + [o_ for o_ in orders if not any(o_ is x_ for x_ in sel_g_)]
            if gs_on_:                             # sd_goods_sale 10-order cap: other sells go first (non-books, then books),
                prot_g_ = set(gs_on_) | ({"STRAWBERRY"} if ssale_cfg_ and _ssale_on(day) else set())   # then the rule's
                while len(orders) > 10:            # least valuable (the last of its head block), never a hire or a buy
                    dg_ = next((i_ for i_ in range(len(orders) - 1, -1, -1) if orders[i_][0] == "SELL"
                                and orders[i_][1] not in bk_ and orders[i_][1] not in prot_g_), None)
                    if dg_ is None:
                        dg_ = next((i_ for i_ in range(len(orders) - 1, -1, -1)
                                    if orders[i_][0] == "SELL" and orders[i_][1] not in prot_g_), None)
                    if dg_ is None:
                        dg_ = next((i_ for i_ in range(len(orders) - 1, -1, -1)
                                    if orders[i_][0] == "SELL" and orders[i_][1] in gs_on_), None)
                    if dg_ is None:
                        break                      # only sd_straw_sale's sell, hires and buys left: the cap below
                    orders.pop(dg_)
                    S["log"]["goods_sale_dropped_order"] += 1
'''

# B11: the last day (endgame skips the books block), after sd_straw_sale's A7
B11 = '''    if gs_on_ and endgame and int(_g(obs, "step", 0)) < 718:   # sd_goods_sale on the last day: the rule instead of
        gsh_ = _gsale_shed_after(S, obs, shed, invs, pos, farm["tiles"])      # selling everything every tick
        inv_m_ = dict(_g(_g(obs, "market", {}), "inventory", {}) or {})
        new_g_ = []
        for p_ in sorted(gs_on_):
            n_gs_ = _gsale_n(S, obs, p_, day, hour, int(gsh_.get(p_, 0)))
            if n_gs_ > 0 and CFG["sd_books_walk"] and p_ in inv_m_:
                n_gs_ = _walk_cap(p_, int(inv_m_[p_]), float(CFG["sd_books_minpx"]), n_gs_)
            orders = [o_ for o_ in orders if not (o_[0] == "SELL" and o_[1] == p_)]
            if n_gs_ > 0:
                new_g_.append(["SELL", p_, int(n_gs_)])
                S["log"]["goods_sale_units_" + p_] += int(n_gs_)
        if new_g_:
            fr_g_ = [o_ for o_ in new_g_ if int((gsale_cfg_.get(o_[1]) or {}).get("front", 1))]
            fr_g_.sort(key=lambda o_: _gsale_lock(S, o_[1], int(_g(obs, "step", 0)), int(o_[2]), prices.get(o_[1], 0)),
                       reverse=True)
            i0_g_ = 1 if (orders and ssale_cfg_ and _ssale_on(day) and int(ssale_cfg_.get("front", 1))
                          and orders[0][0] == "SELL" and orders[0][1] == "STRAWBERRY") else 0   # behind sd_straw_sale's
            orders = (orders[:i0_g_] + fr_g_ + orders[i0_g_:]
                      + [o_ for o_ in new_g_ if not any(o_ is x_ for x_ in fr_g_)])
            prot_g_ = set(gs_on_) | ({"STRAWBERRY"} if ssale_cfg_ and _ssale_on(day) else set())
            while len(orders) > 10:                # 10-order cap: other sells from the end first, never a hire or a buy
                i_gs_ = next((i_ for i_ in range(len(orders) - 1, -1, -1)
                              if orders[i_][0] == "SELL" and orders[i_][1] not in prot_g_), None)
                if i_gs_ is None:
                    i_gs_ = next((i_ for i_ in range(len(orders) - 1, -1, -1) if orders[i_][0] == "SELL"), None)
                if i_gs_ is None:
                    break
                orders.pop(i_gs_)
'''

# B12: the hour-0 hire-slot estimate of the pace
B12 = '''            if p_ in (CFG.get("sd_goods_sale") or {}) and _gsale_on(p_, day) and int(CFG["sd_goods_sale"][p_].get("phase", 1)) % 4 != 0:
                n_ = 0                             # sd_goods_sale: the rule sells none of this good at hour 0
'''

NEW_NAMES = ("sd_goods_sale", "_gsale", "gsale_", "gs_on_", "gs_x_", "gsh_", "n_gs_", "goods_sale_", "gs_rm_", "gs_fr_",
             "sel_g_", "prot_g_", "load_g_", "ex_g_", "done_g_", "k_g_", "hit_g_", "TPg_", "gp_ ", "dg_", "new_g_",
             "fr_g_", "i0_g_", "i_gs_", "GSALE")

# sd_straw_sale's blocks (v18z / v18za) the new ones sit next to
A5_TAIL = '''                        S["log"]["straw_sale_units"] += int(n_ss_)
                    continue
'''
HZ = '''                if hz_:                            # DSM-free: DSM's learned hazard x our shed stock
'''
ROOM_HEAD = '''            if ssale_cfg_ and _ssale_on(day) and hour >= 21 and int(ssale_cfg_.get("room", 1)):   # sd_straw_sale room guard (v18za)
'''
ROOM_TAIL = '''                        S["log"]["straw_sale_room_units"] += k_r_
'''
CAP = '''            if CFG["sd_books_cap"] and hour >= 21:     # shed capacity at midnight
'''
A9_TAIL = '''                        S["log"]["straw_sale_arrive_units"] += max(0, int(n_))   # for the rule (its avail counts this PLACE)
                        continue
'''
A6_HEAD = '''            if ssale_cfg_ and int(ssale_cfg_.get("front", 1)) and _ssale_on(day):   # sd_straw_sale: STRAWBERRY at index 0
'''
OLD_CAP = '''            while len(orders) > 10:                # 10-order cap: never drop a hire or a buy (the hour-0 feed wheat buy:
'''
A7_TAIL = '''                if i_ss_ is None:
                    break
                orders.pop(i_ss_)
'''
FINAL = '''    if CFG["sd_final_sell_all"] and int(_g(obs, "step", 0)) >= 718:
'''
A8 = '''                n_ = 0                             # sd_straw_sale: the rule sells no strawberries at hour 0
'''


def main():
    src = SRC.read_text(encoding="utf-8")
    for nm in NEW_NAMES:
        assert nm not in src, ("name already in v18za", nm)
    s = src
    # B1: the config default (off), next to sd_straw_sale's
    s = ins_before(s, '''    "sd_books_minpx": 5,
''', CFG_LINE)
    # B2: the helpers, after sd_straw_sale's, before _market
    s = ins_before(s, '''
def _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
''', HELPERS)
    # B3: this step's unit commands, stashed for the market (after sd_straw_sale's A3)
    s = ins_before(s, '''    orders = _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
                     unlocked, farm, pos, last_day)
''', B3)
    # B4a: the rule's goods today, before the generic sell loop
    s = ins_after(s, '''    bk_ = set(CFG["sd_books_sell"] or ())
    pt_ |= bk_
''', B4A)
    # B4b: the generic loop skips the rule's non-books goods (WOOL's sell-on-arrival path in our configs)
    s = ins_after(s, '''        if p in bk_ and not endgame:
            continue                      # sd_books_sell: sold below on the leader's plan
''', B4B)
    # B5: the rival tracker, every step, after sd_straw_sale's (A4)
    s = ins_after(s, '''        _ssale_track(S, obs, int(_g(obs, "step", 0)))
''', B5)
    # B6a: the shed after arrivals; the non-books goods' other sells leave the list with the books goods' own
    s = ins_after(s, '''            orders = [o for o in orders if not (o[0] == "SELL" and o[1] in bk_)]
            front_ = []
''', B6A)
    # B6: a books good (MILK): the rule replaces its books quantity (after sd_straw_sale's A5, before the hazard / pace)
    s = ins_before(s, HZ, B6)
    # B7: the non-books goods (WOOL) through the rule, right after the books loop (before sd_straw_sale's room guard)
    s = ins_before(s, ROOM_HEAD, B7)
    # B8: the goods' room guard, after sd_straw_sale's, before sd_books_cap
    s = ins_before(s, CAP, B8)
    # B9: bring-back deliveries of a rule good wait for the rule (after sd_straw_sale's A9 in the dsell_now loop)
    s = ins_after(s, A9_TAIL, B9)
    # B10: the rule's sells at the queue head + a cap that keeps them (before sd_straw_sale's A6 and the old cap)
    s = ins_before(s, A6_HEAD, B10)
    # B11: the last day, after sd_straw_sale's A7
    s = ins_before(s, FINAL, B11)
    # B12: the hour-0 slot estimate (after sd_straw_sale's A8)
    s = ins_after(s, A8, B12)
    # placements: next to sd_straw_sale's blocks, in the order the market runs them
    assert s.count(A5_TAIL + B6 + HZ) == 1, "B6 must follow A5 and precede the hazard / pace branches"
    assert s.count(B7 + ROOM_HEAD) == 1 and s.count(ROOM_TAIL + B8 + CAP) == 1, "B7 / B8 around sd_straw_sale's guard"
    assert s.count(A9_TAIL + B9) == 1, "B9 must follow A9 inside the dsell_now loop"
    assert s.count(B10 + A6_HEAD) == 1, "B10 must precede A6"
    i_b10, i_a6, i_cap = s.index(B10), s.index(A6_HEAD), s.index(OLD_CAP)
    assert i_b10 < i_a6 < i_cap and s[i_a6:i_cap].count("\n") == 4, (i_b10, i_a6, i_cap)   # A6 (4 lines) right before the cap
    assert s.count(A7_TAIL + B11 + FINAL) == 1, "B11 must follow A7 and precede the step-718 sell-all"
    order = [s.index(x) for x in (B4A, B4B, B5, B6A, B6, B7, ROOM_HEAD, B8, CAP, B9, B10, B11)]
    assert order == sorted(order), order
    assert s.index(B12) > s.index("def _tier_pre(") and s.index(A8 + B12) >= 0
    # reversibility: deleting every inserted block (last first) gives v18za back byte for byte
    back = s
    for anchor, new in reversed(_INSERTED):
        back = sub(back, new, anchor)
    assert back == src, "removing the inserted blocks does not give v18za back"
    DST.write_text(s, encoding="utf-8")
    py_compile.compile(str(DST), doraise=True)
    print("wrote", DST, "(%d insertions, %d -> %d lines; compiles; reverts to v18za byte for byte)"
          % (len(_INSERTED), src.count("\n"), s.count("\n")))


if __name__ == "__main__":
    main()

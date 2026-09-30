"""v18y -> v18z: sd_straw_sale (default None) - the STRAWBERRY margin hold rule ("hold_best") in place of the pace.

User 2026-09-30: "the strawberry bringback could use better sale timing". Evidence (offline market-only re-pricing,
scripts/strawberry_sale_eval_20260930.py, make_hold_rule(**BEST); no games run): 97% of our strawberries ride in hand to
the midnight dump and the learned pace (sd_books_source "pace") sells most of it at hours 0-1, the day's low point right
after the rival's evening lumps and our own dump; the sd_rush bring-back (n18rc206d / 207d, world 114393058) brought 58
strawberries home on the peak days (vs 19) but lost $883 strawberry revenue, because a mid-day delivery lands in the
pace formula's afternoon share (77-86%) and is sold into its own lump at the very next tick (206d day 21: 24 units vs 10).
Strawberry margin (our revenue - the rival's) of hold_best vs the recorded pace: 21 main games +1,017 a game (18/21
better; our 12 games +1,474); leave-one-world-out +756 (world-weighted +455); 75 other cached arms +1,169 (74/75);
rush world 194d +2,208 / 206d +3,315 / 207d +2,644; with our order at the back of the queue only +719; with the
executor's day-29 sell-all +974. Mechanism: the town takes 1 strawberry every 4 steps per buyer shop (+1 a day at the
town centre), so the price climbs through every 4-step block nobody sells in; on the glut side moving one of our units
from tick t to tick k changes margin by ~1.92 x (draws in between - 2 x rival units sold in between) - hold while the
town drains the market and the rival is not selling, sell at a post-draw tick in lockstep with (or just before) the
rival's lump. CAVEATS: frozen-replay rivals (9 worlds), the shed / other goods fixed at their recorded levels, a
market-only re-pricing, not a full game (earlier sale-timing ideas lost on full games): check it on the day-11 world in
the viewer, then on a paired fixed-shop Kaggle panel.

config sd_straw_sale {"days": [12, 29], "H": 30, "theta": 4.0, "win": 1, "prior": 20.0, "f0": 0.08, "same_tick": 0.5,
                      "phase": 1, "front": 1, "ripe": false}
  (plateau: H 30-48, theta 4-6, win 1-2 within ~100; same_tick 0.5-1, prior 5-20, f0 barely matter; prior 80 -164,
   ripe true -859). Requires STRAWBERRY in sd_books_sell (the rule replaces its books quantity).
  every step (from step 0, _ssale_track, public data only): the rival's STRAWBERRY harvests of the previous step from its
    public board (the engine's HARVEST takes a tile's whole yield; that night's production and the post-lifespan decay are
    recomputed from the public tile fields, so neither is mistaken for a harvest); its sales from S["_riv_hist"] (market
    stock change - our sells + town draws; exact, strawberries cannot be bought); holdings R = harvested - sold through
    the previous step (floored at 0); after each step t' on day >= 11 with R > 0: E[day, hour] += R, Sx[day, hour] +=
    min(sold at t', R);
  at step t (day d, hour h) with d in days (_ssale_n):
    1. h % 4 != phase: no strawberry sell (hold);
    2. hazards over days max(11, d - win)..d: e_h = sum E, s_h = sum Sx per hour; no exposure yet: f_h = 4 f0 at
       h % 4 == 1 else 0; otherwise f_h = (s_h + prior * pooled) / (e_h + prior), pooled = sum s / sum e;
    3. H' = min(H, 718 - t); o_j = f_((h+j) mod 24) R_j, R_0 = R (+ the rival's standing yield if ripe), R_(j+1) = R_j - o_j;
    4. D_j = the town's strawberry draw at step t+j from today's unlocked shops (after the market);
    5. I_0 = market stock, I_(j+1) = I_j + o_j - D_j; Pc = the engine price curve unrounded, sl(x) = Pc(x) - Pc(x+1);
    6. g_j = Pc(I_j) - Pc(I_0) - sum_(i<j) o_i sl(I_i) - same_tick o_j sl(I_j) for the later post-draw ticks j = 4, 8, ...;
    7. max g_j <= theta (or no later post-draw tick): SELL the whole shed stock after this step's PLACE / DROP / PICKUP
       commands (_ssale_shed_after, the engine's farmer-then-hands order and shed room), else nothing;
  the order goes to queue index 0 (front 1, lockstep with the rival's index-0 lumps); the midnight capacity sells (hour
  >= 21), the walk (sd_books_walk) and the step-718 sell-all are unchanged and see the rule's order; the 10-order cap
  loop keeps it (it is the last sell it would drop); with 29 in days the last day runs the rule too instead of the
  endgame's sell-everything-every-tick for strawberries; the hour-0 hire-slot estimate (sd_books_h0_slots, pace) counts
  no strawberry sell at hour 0 (the rule never sells there with phase != 0).
  Bring-back trips that sell on arrival (sd_tier_sclu DELIVER stops with sell_now, sd_tier_bb; both record their units in
  TP["dsell_now"] and PLACE them on a shed tile in the same step): on the rule's days their STRAWBERRY is NOT added to
  the order (A9) - the rule's avail (_ssale_shed_after) already counts that PLACE, and the rule times those units like
  every other strawberry (log straw_sale_arrive_units). Their other products are still sold on arrival.
  FIX 2026-09-30 (review of the first v18z): before A9 the unchanged dsell_now block ran after the rule and (a) on a sell
  tick added the arrivals a second time (order = avail + n, above the stock: the engine sells only the stock, but
  S["_riv_prev"] recorded avail + n as our sells, so the next _rival_infer returned the rival's strawberry sales minus
  n, dropped when <= 0, and _ssale_track's holdings R stayed too high and its hazard too low), (b) on a hold or off-phase
  tick sold the arrivals at once, bypassing the rule; v18y's pace sized from the observed shed (no arrivals), so it
  never double-counted. Affected: bases with sd_tier_sclu (n18rc201d / 202d) or sd_tier_bb; not sd_rush (its DELIVER
  stops carry no sell_now: n18rc206d / 207d / 212d). Also moved: the front move (A6) now runs after that block, whose
  sell-on-arrival inserts of other products at index 0 had pushed the rule's STRAWBERRY sell to index 1+.
Flag off (None): every inserted statement is behind `if CFG.get("sd_straw_sale")` / `if ssale_cfg_`; the only unguarded
additions are the CFG key, the helper definitions (never called) and the read `ssale_cfg_ = CFG.get("sd_straw_sale")`.
This script checks each anchor occurs once, that the new names were absent from v18y, that A9 is the first statement of
the dsell_now loop and A6 follows that block (right before the books 10-order cap), that deleting every inserted block
gives v18y back byte for byte, and compiles v18z.

usage: patch_exec_straw_sale_20260930.py  (writes agents/mgt_lead_kb115lt2_v18z.py from v18y)"""
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18y.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18z.py"

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


CFG_LINE = '''    "sd_straw_sale": None,    # v18z (2026-09-30; scripts/strawberry_sale_eval_20260930.py hold_best, offline strawberry margin +1,017 a game vs the pace, 18/21 better; see scripts/patch_exec_straw_sale_20260930.py) {"days": [12, 29], "H": 30, "theta": 4.0, "win": 1, "prior": 20.0, "f0": 0.08, "same_tick": 0.5, "phase": 1, "front": 1, "ripe": false}: STRAWBERRY (must be in sd_books_sell) on days d0-d1 sells only at the post-draw hours (hour % 4 == phase), and then the whole shed stock (with this step's PLACE / DROP arrivals) unless a later post-draw tick within H steps is forecast to be worth more than theta a unit in margin (own price rise from the town's draws minus the rival's units priced higher meanwhile; the rival's holdings = its public harvests - its inferred sales, its hazard by hour over the last win days shrunk with prior); replaces the pace quantity; at queue index 0 (front); sd_tier_sclu / sd_tier_bb strawberry deliveries are not sold on arrival on these days (the rule's avail includes this step's PLACE, the rule times them); the midnight capacity sells, the walk and the step-718 sell-all unchanged; 29 in days: the rule also replaces the last day's sell-all for strawberries. None = off
'''

HELPERS = '''

# ---- sd_straw_sale (v18z, default None): the STRAWBERRY margin hold rule ------------------------------------------------
# a port of make_hold_rule(**BEST) in scripts/strawberry_sale_eval_20260930.py (the decision) and RivalView (the rival's
# holdings and selling hazard), fed from the public observation only
_SSALE_I = "STRAWBERRY"


def _ssale_on(day):
    """sd_straw_sale is set, STRAWBERRY is a books product (the rule replaces its books quantity) and day is in "days"."""
    cfg = CFG.get("sd_straw_sale")
    if not cfg or _SSALE_I not in set(CFG.get("sd_books_sell") or ()):
        return False
    d0, d1 = (cfg.get("days") or [12, 29])[:2]
    return int(d0) <= int(day) <= int(d1)


def _ssale_pc(x):
    """the engine's STRAWBERRY price at market stock x, unrounded (floor kept): 120 + 8.4 sqrt(10000 - x) below 10000,
    max(1, 120 - 1.92 (x - 10000)) above"""
    p = _MKT_PARAMS[_SSALE_I]
    base, T = p["base"], p["T"]
    if x < _MKT_I0:
        amp = p["below_target"] * base / _mkt_shape(p["below_func"], T, T)
        v = base + amp * _mkt_shape(p["below_func"], _MKT_I0 - x, T)
    else:
        amp = p["above_target"] * base / _mkt_shape(p["above_func"], T, T)
        v = base - amp * _mkt_shape(p["above_func"], x - _MKT_I0, T)
    return max(float(_MKT_FLOOR), float(v))


def _ssale_track(S, obs, step):
    """sd_straw_sale, once a step (in _market after _rival_infer, so S["_riv_hist"] holds the rival's sales of step - 1):
    the rival's public STRAWBERRY holdings.
      harvests of step - 1: its STRAWBERRY plants on the previous and on this observation. The engine's HARVEST takes the
        whole yield (an ongoing plant stays with yield 0), the night refresh then adds 1 (2 when watered and fertilized;
        capped at the crop's max) on a production day, and past max_lifespan_step a plant loses 1 unit every 2nd step and
        becomes a weed at <= 0 - all recomputed from the public tile fields, so a production or a decay is never counted
        as a harvest (a harvest to 0 followed by the decay tick shows as a weed with >= 2 units the step before);
      holdings R(t) = max(0, R(t-1) - sold(t-1)) + harvested(t-1) (= harvested - sold through t-1: strawberries cannot
        be bought, so a sale beyond the tracked holdings can only be a harvest the board did not show);
      exposure: after each step t' on day >= 11 with R(t') > 0: E[(day, hour)] += R(t'), Sx[(day, hour)] += min(sold(t'), R(t'))."""
    st = S.get("_ssale")
    if st is None:
        st = S["_ssale"] = {"step": -1, "prev": None, "pstep": -1, "R": 0, "Rstep": -1, "E": {}, "Sx": {},
                            "harv": 0, "sold": 0, "ripe": 0}
    if st["step"] == step:
        return st
    st["step"] = step
    me = int(_g(obs, "player", 0))
    farms = _g(obs, "farms", []) or []
    tiles = farms[1 - me]["tiles"] if len(farms) > 1 else []
    cur, ripe = {}, 0
    for y_ in range(len(tiles)):
        for x_ in range(len(tiles[y_])):
            t_ = tiles[y_][x_]
            if _is_plant(t_) and t_.get("crop") == _SSALE_I:
                yv_ = int(t_.get("yield_units", 0) or 0)
                cur[y_ * 10 + x_] = (yv_, int(t_.get("planted_day", -99)), int(t_.get("max_lifespan_step", -1)),
                                     int(t_.get("consecutive_unwatered", 1) or 0), int(t_.get("fertilized_until_day", -1)))
                ripe += max(0, yv_)
    rh = S.get("_riv_hist") or {}
    E, Sx = st["E"], st["Sx"]
    s1 = step - 1
    if st["Rstep"] == s1 and st["R"] > 0 and s1 >= 0 and s1 // 24 >= 11:
        k_ = divmod(s1, 24)
        E[k_] = E.get(k_, 0.0) + st["R"]
        Sx[k_] = Sx.get(k_, 0.0) + min(int(rh.get((s1, _SSALE_I), 0) or 0), st["R"])
    harv = 0
    prev = st["prev"]
    if prev is not None and st["pstep"] == s1:
        cd = CROPS[_SSALE_I]
        d1_, eod_ = s1 // 24, (s1 + 1) % 24 == 0
        for idx, (yp, pd, mls, _cu, _fu) in prev.items():
            if yp <= 0:
                continue
            dec = 1 if (mls >= 0 and s1 >= mls and (s1 - mls) % 2 == 0) else 0
            now = cur.get(idx)
            if now is not None and now[1] == pd:
                prod = 0
                if eod_:
                    dsf = d1_ + 1 - pd - cd["first"]
                    if dsf >= 0 and dsf % max(1, cd["interval"]) == 0 and dsf // max(1, cd["interval"]) + 1 <= cd["max"]:
                        prod = 2 if (now[3] == 0 and now[4] >= d1_) else 1
                if now[0] < min(cd["max"], yp - dec + prod):
                    harv += yp                     # harvested to 0 (then the night's production)
            elif now is None and dec and yp >= 2:
                harv += yp                         # harvested to 0, then the decay tick made it a weed
    elif prev is not None:                         # a gap in the steps seen: plain yield drops
        for idx, (yp, pd, mls, _cu, _fu) in prev.items():
            now = cur.get(idx)
            if now is not None and now[1] == pd and now[0] < yp:
                harv += yp - now[0]
    sold = 0
    if st["Rstep"] >= 0:
        sold = sum(int(rh.get((s_, _SSALE_I), 0) or 0) for s_ in range(st["Rstep"], step))
    st["R"] = max(0, int(st["R"]) - sold) + harv
    st["Rstep"] = step
    st["prev"], st["pstep"] = cur, step
    st["harv"] += harv
    st["sold"] += sold
    st["ripe"] = ripe
    return st


def _ssale_shed_after(S, obs, shed, invs, pos, tiles):
    """sd_straw_sale: our STRAWBERRY shed stock after this step's unit commands, before the market (engine order: the
    farmer, then each hand; PICKUP takes from the shed, PLACE / DROP add up to the room left of the 100-unit shed, DROP
    empties the inventory in its item order, an animal PLACE on its own structure does not touch the shed). Without this
    step's commands (S["_ssale_act"] from the agent): the observed shed."""
    step = int(_g(obs, "step", 0))
    base = int(shed.get(_SSALE_I, 0) or 0)
    sa = S.get("_ssale_act")
    if not sa or sa[0] != step:
        return base
    sh = Counter({k: int(v or 0) for k, v in shed.items()})
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
    return max(0, int(sh.get(_SSALE_I, 0)))


def _ssale_n(S, obs, day, hour, avail):
    """sd_straw_sale decision at this step: avail (the whole shed stock after this step's arrivals) or 0 (hold)."""
    cfg = CFG.get("sd_straw_sale") or {}
    lg = S["log"]
    if avail <= 0:
        return 0
    step = int(_g(obs, "step", 0))
    Hh = min(int(cfg.get("H", 30)), 718 - step)
    if Hh <= 0:
        return int(avail)
    ph = int(cfg.get("phase", 1))
    if step % 4 != ph:
        return 0
    st = S.get("_ssale") or {}
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
    nsh = sum((2 if len(_SHOPS_E.get(s_, ())) == 1 else 1) for s_ in shops if _SSALE_I in _SHOPS_E.get(s_, ()))
    I0 = float(int((_g(_g(obs, "market", {}), "inventory", {}) or {}).get(_SSALE_I, _MKT_I0)))
    stc, theta = float(cfg.get("same_tick", 0.5)), float(cfg.get("theta", 4.0))
    p0 = _ssale_pc(I0)
    Ij, ext, best = I0, 0.0, -1e9
    for j in range(Hh + 1):
        o = f[(step + j) % 24] * R
        R -= o
        sl = _ssale_pc(Ij) - _ssale_pc(Ij + 1)
        if j > 0 and (step + j) % 4 == ph:
            g = _ssale_pc(Ij) - p0 - ext - stc * o * sl
            if g > best:
                best = g
        ext += o * sl
        Ij += o - ((nsh if (step + j) % 4 == 0 else 0) + (1 if (step + j) % 24 == 0 else 0))
    if best <= theta:
        lg["straw_sale_sell_ticks"] += 1
        return int(avail)
    lg["straw_sale_hold_ticks"] += 1
    lg["straw_sale_hold_units"] += int(avail)
    return 0
'''

A3 = '''    if CFG.get("sd_straw_sale"):                   # sd_straw_sale: this step's unit commands (their shed arrivals precede the market)
        S["_ssale_act"] = (step, [list(a_) if isinstance(a_, (list, tuple)) else ["PASS"] for a_ in actions])
'''

A4 = '''    ssale_cfg_ = CFG.get("sd_straw_sale")         # sd_straw_sale (v18z): the STRAWBERRY margin hold rule (None = off)
    if ssale_cfg_:
        if not (bk_ and dfree_ and "STRAWBERRY" in bk_):   # the rival's strawberry sales are otherwise not inferred
            inv_riv_ = _rival_infer(S, obs, int(_g(obs, "step", 0)), ("STRAWBERRY",))
        _ssale_track(S, obs, int(_g(obs, "step", 0)))
'''

A5 = '''                if ssale_cfg_ and p_ == "STRAWBERRY" and _ssale_on(day):   # sd_straw_sale: the hold rule, not the pace
                    av_ = _ssale_shed_after(S, obs, shed, invs, pos, farm["tiles"])
                    if CFG["sd_books_reserve"]:
                        av_ = max(0, av_ - int(reserve.get(p_, 0) or 0))
                    n_ss_ = _ssale_n(S, obs, day, hour, av_)
                    if n_ss_ > 0:
                        front_.append((0, ["SELL", p_, int(n_ss_)]))
                        S["log"]["straw_sale_units"] += int(n_ss_)
                    continue
'''

A6 = '''            if ssale_cfg_ and int(ssale_cfg_.get("front", 1)) and _ssale_on(day):   # sd_straw_sale: STRAWBERRY at index 0
                i_ss_ = next((i_ for i_, o_ in enumerate(orders) if o_[0] == "SELL" and o_[1] == "STRAWBERRY"), None)
                if i_ss_:                          # (after the trips' sell-on-arrival inserts of other products at index 0)
                    orders.insert(0, orders.pop(i_ss_))
'''

A7 = '''    if ssale_cfg_ and endgame and _ssale_on(day) and int(_g(obs, "step", 0)) < 718:   # sd_straw_sale on the last day:
        av_ = _ssale_shed_after(S, obs, shed, invs, pos, farm["tiles"])      # the rule instead of selling everything every tick
        n_ss_ = _ssale_n(S, obs, day, hour, av_)
        if n_ss_ > 0 and CFG["sd_books_walk"]:
            inv_m_ = dict(_g(_g(obs, "market", {}), "inventory", {}) or {})
            if "STRAWBERRY" in inv_m_:
                n_ss_ = _walk_cap("STRAWBERRY", int(inv_m_["STRAWBERRY"]), float(CFG["sd_books_minpx"]), n_ss_)
        orders = [o_ for o_ in orders if not (o_[0] == "SELL" and o_[1] == "STRAWBERRY")]
        if n_ss_ > 0:
            orders.insert(0 if int(ssale_cfg_.get("front", 1)) else len(orders), ["SELL", "STRAWBERRY", int(n_ss_)])
            S["log"]["straw_sale_units"] += int(n_ss_)
            while len(orders) > 10:                # 10-order cap: other sells from the end first, never a hire or a buy
                i_ss_ = next((i_ for i_ in range(len(orders) - 1, -1, -1)
                              if orders[i_][0] == "SELL" and orders[i_][1] != "STRAWBERRY"), None)
                if i_ss_ is None:
                    i_ss_ = next((i_ for i_ in range(len(orders) - 1, -1, -1) if orders[i_][0] == "SELL"), None)
                if i_ss_ is None:
                    break
                orders.pop(i_ss_)
'''

A8 = '''            if CFG.get("sd_straw_sale") and p_ == "STRAWBERRY" and _ssale_on(day) and int(CFG["sd_straw_sale"].get("phase", 1)) % 4 != 0:
                n_ = 0                             # sd_straw_sale: the rule sells no strawberries at hour 0
'''

A9 = '''                    if ssale_cfg_ and p_ == "STRAWBERRY" and _ssale_on(day):   # sd_straw_sale: the trip's strawberries wait
                        S["log"]["straw_sale_arrive_units"] += max(0, int(n_))   # for the rule (its avail counts this PLACE)
                        continue
'''

NEW_NAMES = ("sd_straw_sale", "_ssale", "ssale_", "n_ss_", "i_ss_", "straw_sale_")


def main():
    src = SRC.read_text(encoding="utf-8")
    for nm in NEW_NAMES:
        assert nm not in src, ("name already in v18y", nm)
    s = src
    # A1: the config default (off)
    s = ins_after(s, '''    "sd_books_front_min": 1.0,
''', CFG_LINE)
    # A2: the helpers, before _market
    s = ins_before(s, '''
def _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
''', HELPERS)
    # A3: this step's unit commands, stashed for the market (arrivals before the sale)
    s = ins_before(s, '''    orders = _market(S, obs, day, hour, money, shed, seeds, carried, invs, tasks, jobs, demand, prices,
                     unlocked, farm, pos, last_day)
''', A3)
    # A4: the rival tracker, every step, right after the rival-sale inference of the books block
    s = ins_after(s, '''    inv_riv_ = _rival_infer(S, obs, int(_g(obs, "step", 0)), bk_) if (bk_ and dfree_) else None
''', A4)
    # A5: the rule replaces the books quantity of STRAWBERRY (before the hazard / pace / dsm paths)
    s = ins_before(s, '''                if hz_:                            # DSM-free: DSM's learned hazard x our shed stock
''', A5)
    # A6: our STRAWBERRY sell at queue index 0 - after the books orders are placed AND after the sd_tier_sclu / sd_tier_bb
    # sell-on-arrival block (it inserts other delivered products at index 0), right before the books 10-order cap
    s = ins_before(s, '''            while len(orders) > 10:                # 10-order cap: never drop a hire or a buy (the hour-0 feed wheat buy:
''', A6)
    # A7: the last day (endgame skips the books block)
    s = ins_before(s, '''    if CFG["sd_final_sell_all"] and int(_g(obs, "step", 0)) >= 718:
''', A7)
    # A8: the hour-0 hire-slot estimate of the pace
    s = ins_after(s, '''            n_ = min(int(shed.get(p_, 0) or 0), int(round(float(P_["p1"].get("%s|%s|0" % (p_, ph_), 0.0)) * int(shed.get(p_, 0) or 0))))
''', A8)
    # A9: the sd_tier_sclu / sd_tier_bb sell-on-arrival block adds no STRAWBERRY on the rule's days (review fix: the
    # rule's avail already counts this step's PLACE; adding it again ordered avail + n and bypassed the rule's holds)
    s = ins_after(s, '''                for p_, n_ in TPn_["dsell_now"].items():
''', A9)
    # placement: A9 is the first statement of the dsell_now loop (before its sclu cap and its sell-on-arrival insert);
    # A6 follows the block's reset and directly precedes the books 10-order cap
    loop_ = '''                for p_, n_ in TPn_["dsell_now"].items():\n'''
    cap_ = '''            while len(orders) > 10:                # 10-order cap: never drop a hire or a buy (the hour-0 feed wheat buy:\n'''
    assert s.count(loop_ + A9) == 1 and s.count(A6 + cap_) == 1
    i9_ = s.index(loop_ + A9)
    i_cap_ = s.index('if p_ in bk_ and n_ > 0 and int(CFG["sd_tier_sclu_sell_cap"]) and not dfree_:')
    i_ins_ = s.index('orders.insert(0, ["SELL", p_, int(n_)])')
    i_rst_ = s.index('TPn_["dsell_now"] = Counter()')
    assert i9_ < i_cap_ < i_ins_ < i_rst_ < s.index(A6 + cap_), (i9_, i_cap_, i_ins_, i_rst_)
    # reversibility: deleting every inserted block (last first) gives v18y back byte for byte
    back = s
    for anchor, new in reversed(_INSERTED):
        back = sub(back, new, anchor)
    assert back == src, "removing the inserted blocks does not give v18y back"
    DST.write_text(s, encoding="utf-8")
    py_compile.compile(str(DST), doraise=True)
    print("wrote", DST, "(%d insertions, %d -> %d lines; compiles; reverts to v18y byte for byte)"
          % (len(_INSERTED), src.count("\n"), s.count("\n")))


if __name__ == "__main__":
    main()

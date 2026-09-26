# ============================================================================================
# ===== BEGIN SEARCH DISPATCH BLOCK (mgt_lpv_search only; inserted by scripts/search_dispatch_build.py) ======
# Source: scripts/search_dispatch_block.py. This text is inserted verbatim into the agent file (it is not a module):
# it uses the executor's globals CFG, SHED, ANIMALS, CROPS, PRODUCTS, _tile, _near_shed, _step_toward, _is_plant,
# _is_weed, _animal, _fib, _T, _S, _sm, _mj_fert and the deploy's _DEP, DEP_CFG, _MGT_REPORT. stdlib only.
#
# CFG["dispatch_search"]: "off" = nothing below runs (every hook is guarded; the executor is the source deploy's);
# "shadow" = the greedy acts; the planner runs every step and logs its time, its planned drops and its agreement with
# the greedy; "active" = inside CFG["sd_days"] ([lo, hi], None = all days) every non-delivering unit with a planned
# route follows the plan's next step, with a per-unit fallback to the greedy when that step is invalid (and for
# everyone when the planner fails, runs out of its time bank or the day is outside the window).
#
# Every step: the executor's tile tasks (+ predicted jobs: plan plantings whose seeds are bought this step, and the
# same-day replant after a wheat / carrot harvest as an order pair harvest -> plant + water) become jobs with per-op
# coin values and deadlines (the maintenance module's values as _sched_tile_ops reads them; plan jobs = plan_value on
# completion); survival ops (plant dies / animal escapes tonight) are hard. The previous step's routes are the warm
# start (gone jobs dropped, infeasible routes repaired), unplanned jobs are regret-inserted, then relocate / 2-opt /
# or-opt / ruin-and-recreate run inside a work budget (route evaluations: deterministic) and a time cap. Only each
# unit's next step is executed.
#
# Time model (the unit acts at hour t): Manhattan moves; one step per op; one PICKUP step per item type at the shed
# tile of least detour, placed before the first job the unit cannot supply (exact amounts = the route's lowest running
# balance; wheat harvested / fertilizer collected earlier in the route count; the shed stock is shared by the routes);
# the executor's delivery trigger (>= deliver_units or >= deliver_value before late_hour, >= deliver_value_late
# before 20, any value when cash is short) inserts the walk to the nearest shed tile + the DROP / PLACE steps (a pending
# pickup is merged into that visit); release hours; an op after its deadline keeps sd_late_frac of its value; a hard
# op must be on time; only the route's last job may be cut by the day end (maintenance only: plan jobs complete);
# day-29 routes must leave the walk back to the shed. Objective = coins of the ops done - sd_lambda x route time -
# sd_switch x steps already walked toward a job the unit is taken off - sd_cap_w x the projected midnight load (shed
# wheat / fertilizer / animals + everything carried + wheat / fertilizer gained - consumed) above sd_cap - sd_cap_margin.
#
# v2 (2026-09-25, all off by default = v1): v1 carried products to midnight (a delivery cost route time and earned
# nothing, and full routes never went idle), so they sold a day late into lower prices (12 G1 worlds: volume +5.2k /
# +6.9k, price -3.7k / -5.2k). The in-day delivery credit is paid for each deliverable
# unit that reaches the shed by a DROP / PLACE at or before sd_dv_hour (the market sells it the same day: unit actions
# come before the market, and the sell orders are computed from the shed seen at the start of the turn), glut goods
# (melon, milk, wool, strawberry) highest; per-product tables sd_dv_frac (x the current price) + sd_dv_coins (coins,
# optionally by day), swappable for the measured same-day-vs-next-morning margin table; sd_final_trip = after its last job a route walks what it carries to the
# nearest shed tile (the idle rule does that in execution) and gets the credit when the drop is in time. v1 left
# survival ops to hour 23 (thirsty plants still dry at 23h: 20 -> 54 / 66 a game): sd_hard_late_w = coins per hour a
# hard op is done after sd_hard_safe; sd_hard_all = every unit is a candidate for a hard job; sd_hard_eject = a hard
# job nobody can take is inserted where dropping the least value of non-hard jobs makes the route feasible.
#
# v3 (2026-09-25, user ruling: the leaders' harvest timing as tendencies, soft): sd_hv_pref = a small table (empty =
# off, the same table the executor gets later) of bonuses on a HARVEST op: a one-time crop on its last day before decay
# ("decay"), wheat / carrot at the leaders' ages by season part ("ages": [day_from, day_to, age_lo, age_hi]), melons
# once today's water brings them to full yield ("full") and early in the morning (a soft target: "by_hour" /
# "hour_w" = coins per hour later), tomatoes / strawberries at every production; WATER stays before HARVEST. MELON
# "offer": 1 = the planner adds the full-yield melon harvest the executor's tasks skip until the last day (job ("H",
# tile), after the tile's WATER task; value = the bonus, the same-day credit, the soft hour; a planned unit does it).
# sd_cap_all: the midnight shed-load term also counts the products that stay in the shed overnight (beyond the day's
# leader sell quota; with the deploy's sem rule, the held strawberries). sd_mr: a maintenance job's coin value is scaled
# by marginal revenue / price of its product: p(inv) - slope(inv) x our units still to sell this season (the leader's
# season total minus ours), slope = the engine price drop for one more unit at today's market inventory (a sold unit
# raises the inventory for good) x our share of the season's supply beyond the market's remaining consumption, floored
# at sd_mr_floor x p; glut goods lose most, wheat / carrot / egg little.
# sd_early_animal: a BUILD job's animal is bought while the tile still waits for its crop's harvest (the executor's
# market buys animals only for tasks that PLACE them; with harvest_before_build that task appears after the harvest).
# sd_water_first: a task that harvests a one-time crop in its growth window, unwatered today and below cap, waters first
# (the PLANT pipeline's rule; the BUILD / REMOVE harvest paths lacked it: the coop tile's melon was cut at 5 units).
# sd_hire_demand: at hour 0 the planner plans the day with k virtual hires for k in [want - 6, want] (sd_hire_evals
# route evaluations each) and hires the k with the best planned value net of the fib wages (the executor's market hires
# that many). sd_spawn_steer: the farmer's hour-0 stand (stay, a neighbouring shed tile or off the shed) and the split of
# the hires between hour 0 and hour 1 are chosen so the spawn quadrants (least-occupied shed tile, NW NE SW SE order)
# match the plan's work per quadrant. Both act through the market's hire count (CFG hire_extra for the day) and the
# farmer's hour-0 command. sd_hp_parity: the planner values the executor's harvest_policy jobs as the executor does
# (a melon harvest in the leaders' window = held units x price x hp_frac; a melon window water = the melon price);
# sd_split_place: a BUILD + PLACE plan part is split into the structure job (sd_build_value) and the placement job
# (plan_value, successor of the structure): the leader builds the coop at h13 and places the goose at h14.
# sd_bundle_build (user design, replaces the split): every plan BUILD with an animal is one job for one hand: clear the
# tile (WATER if due, HARVEST or DIG) -> BUILD -> PLACE -> FEED -> CARE, the animal and its feed wheat picked up at the
# trip start, valued at a day's delay (a day of the animal's product + fertilizer, sd_bundle_value "auto") on top of the
# clearing ops; never an empty structure (no animal: the structure waits whole). sd_water_tomorrow: a water on a dry
# plant is worth at least this (tomorrow's labour saved: a plant dry today is a must-do tomorrow), and plants without a
# sd_coop_pair (user, main branch M): the structure and its animal as ONE job ([DIG,] BUILD, PLACE: two hours, one hand,
# the animal from the trip start), FEED / CARE upkeep afterwards; a crop on the tile is harvested first and the pair is
# predicted after that harvest; the pair buys its animal from hour 0 (the clearing task carries the need); never an
# empty structure. sd_coop_pair 2: the pair must complete by the day end (hard op:
# sd_hard on the PLACE, deadline the day end, any hour; the clearing harvest is kept planned first).
# (radial corridors, user design) sd_corr_w: each unit's angular corridor around the shed (equal work, by spawn angle,
# disjoint); an op outside it costs sd_corr_w; sd_rad_in / sd_rad_side: coins per inward / sideways step between job
# tiles (the trip works outward; deliveries and pickups are not job-to-job moves).
# task get a planner-only water job; sd_idle_fert: an idle planned unit delivers its fertilizer too.
# v5: sd_surv_fb = from this hour the executor's own survival routes (surv_reserve: a plant dying / an animal escaping
# tonight, nearest-arrival routes) keep their units and tiles: the planner plans neither (guaranteed fallback).
# sectors (2026-09-25, research copy agents/mgt_lead_sector.py): each unit has a home quadrant (a hand: the quadrant of
# the tile it spawned on; the farmer: the second = NW); an op outside home costs sd_sector_w coins in the route objective
# (a soft term, not a constraint; hard / survival ops and plan structural jobs PLANT / BUILD / PLACE are exempt). At the
# hours sd_sector_hours the homes rebalance: while one quadrant's remaining ops per home hand exceed sd_sector_ratio x
# another's, the hand of the lighter quadrant nearest to the heavier one moves its home there. Pickups stay sized to each
# route's own need (the route evaluation's running balance), never to a sector's. sd_hop_w = coins per step of a hop
# beyond one between consecutive job tiles of a route (user: each trip works a chain of adjacent tiles), applied in the
# patch only: tiles within sd_hop_central steps of the shed (the animals) are en-route ops on the way out / back.
# ============================================================================================
import random as _sd_random

_SD_SP = ("GOOSE", "COW", "SHEEP")
_SD_SPI = {s: i for i, s in enumerate(_SD_SP)}
_SD_Z3 = (0, 0, 0)
_SD_TAB = []           # [D, SD, SA, DS, NS] 100 x 100 tile tables (built once per process)
_SD_MOVES = ("NORTH", "SOUTH", "EAST", "WEST")
_SD_WORK = ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER", "PLANT", "DIG", "BUILD_COOP",
            "BUILD_PASTURE")
_SD_PLANC = ("PLANT", "PLACE", "BUILD_COOP", "BUILD_PASTURE")
_SD_FAIL = (False, 0.0, 99, 0, 0, _SD_Z3, -1, 0, None)
_SD_FAILS = {k: (False, 0.0, k, 0, 0, _SD_Z3, -1, 0, None) for k in (
    "stock_a", "hard_stock", "pred_later", "pred_none", "dayend", "cut", "hard_late", "lastday")}
_SD_T = []             # [entry time of the current step] (set by the entry point)
# job tuple: 0 tile, 1 n ops, 2 wheat need, 3 fertilizer need, 4 animal species index (-1), 5 wheat gained, 6 fertilizer
# gained, 7 per-op values, 8 per-op deadlines, 9 release hour, 10 hard op index (-1), 11 predecessor job (-1), 12 lag
# after the predecessor's finish, 13 is a predecessor, 14 leading ops that may stand alone when the day ends inside the
# job (maintenance: all; plan parts: 0), 15 deliverable units gained, 16 deliverable value gained, 17 deliverable
# product types gained, 18 FERTILIZE op indices, 19 FEED (+ CARE) op indices (skipped when the item cannot be had),
# 20 in-day delivery credit gained (v2), 21 soft time target (op index, hour, coins per hour later) or None (v3),
# 22 quadrant index (0 NW, 1 NE, 2 SW, 3 SE), 23 exempt from the sector term (hard op or plan structural job)


def _sd_dv_table(S, day, prices, shed):
    """v2: coins credited per unit of each product delivered in time for a same-day sale = CFG sd_dv_frac[p] x the
    current price + CFG sd_dv_coins[p] (a number, or [[first_day, coins], ...]: the last entry with first_day <= day).
    Wheat is never deliverable here (the executor keeps it for feeding). sd_dv_quota with the leader sell rule
    (sell_source "leader": we sell up to the leader's cumulative units of the day): only products whose quota still
    has room after the units already in the shed (the rule then reproduces the leaders: melons sold the day they are
    picked, strawberries / tomatoes mostly the next morning)."""
    fr = CFG["sd_dv_frac"] or {}
    co = CFG["sd_dv_coins"] or {}
    gate = bool(CFG["sd_dv_quota"]) and CFG.get("sell_source") == "leader" and _T is not None
    d_ = min(day, _T.n - 1) if gate else 0
    out = {}
    for k in PRODUCTS:
        if k == "WHEAT":
            continue
        if gate and _T.cum_sold[d_].get(k, 0) - S["sold"][k] - int(shed.get(k, 0) or 0) <= 0:
            continue
        c = co.get(k, 0.0)
        if isinstance(c, (list, tuple)):
            cc = 0.0
            for d0, v0 in c:
                if day >= int(d0):
                    cc = float(v0)
            c = cc
        per = float(fr.get(k, 0.0)) * float(prices.get(k, 0) or 0) + float(c)
        if per > 0:
            out[k] = per
    return out


def _sd_tables():
    if not _SD_TAB:
        D = [[abs(a % 10 - b % 10) + abs(a // 10 - b // 10) for b in range(100)] for a in range(100)]
        sheds = [q[1] * 10 + q[0] for q in SHED]
        SD = [[0] * 100 for _ in range(100)]
        SA = [[0] * 100 for _ in range(100)]
        for a in range(100):
            Da = D[a]
            for b in range(100):
                best = None
                for s in sheds:
                    c = (Da[s] + D[s][b], Da[s], s)       # least detour, then the shed nearest to the unit
                    if best is None or c < best:
                        best = c
                SD[a][b] = best[0]
                SA[a][b] = best[2]
        DS = [min(D[a][s] for s in sheds) for a in range(100)]
        NS = []
        for a in range(100):
            q = _near_shed((a % 10, a // 10))             # the executor's delivery target
            NS.append(q[1] * 10 + q[0])
        _SD_TAB.extend([D, SD, SA, DS, NS])
    return _SD_TAB


def _sd_state(S):
    L = S.get("sd")
    if L is None:
        L = {"day": -1, "routes": {}, "walk": {}, "pred_seen": {}, "recs": [], "path": None, "off": False,
             "prev_kind": None, "prev_thirst": None, "water23": set(), "seq": {}, "seq_day": -1, "lastP": None,
             "final_done": False,
             "st": {"steps": 0, "plan_ms": [], "plan_ms_first": [], "step_ms": [], "evals": 0, "time_capped": 0,
                    "errors": 0, "last_error": "", "fb_step": 0, "fb_unit": 0, "fb_pickup": 0, "fb_noop": 0,
                    "fb_notask": 0, "idle_unit": 0, "planned_unit": 0, "pred_wait": 0, "switch_steps": 0,
                    "moves": 0, "work": 0, "shed_cmds": 0, "shed_visits": 0, "shed_arrivals": 0, "passes": 0,
                    "walk_after_last": 0, "walk_after_last_nodeliv": 0, "unit_days": 0, "unit_steps": 0,
                    "dropped_jobs": 0, "dropped_value": 0.0, "dropped_prod_jobs": 0, "dropped_prod_value": 0.0,
                    "dropped_prod_units": 0, "dropped_hard": 0, "plants_lost": 0, "plants_lost_thirst": 0,
                    "animals_lost": 0, "planned_drop_first": 0, "planned_drop_first_value": 0.0,
                    "planned_hard_unplanned": 0, "deliv_deferred": 0, "agree": 0, "agree_n": 0, "bank_used": 0.0, "steps_over_1s": 0,
                    "rr_tried": 0, "rr_acc": 0, "load_proj_h23": [], "cash0": [], "days_planned": 0,
                    "forced_hard": 0, "idle_deliver": 0, "offered_harvest": 0, "surv_fb_units": 0}}
        S["sd"] = L
    return L


class _SdP(object):
    """one planning problem (jobs, units, plan state)."""
    pass


def _sd_want_hands(day):
    """the market's default hand count for the day (hire_demand / sched_hire off)."""
    T = _T
    d = min(day, T.n - 1)
    want = T.hands[d] + CFG["hire_extra"]
    if CFG["hands_d29_fix"] and d == T.n - 1 and T.hands[d] == 0 and d > 0:
        want = T.hands[d - 1] + CFG["hire_extra"]
    return max(0, int(want))


def _sd_spawn(pos, k):
    """spawn tiles of k hires in order (engine rule: least occupied shed tile, NWSE order)."""
    order = [(4, 4), (5, 4), (4, 5), (5, 5)]
    occ = {q: 0 for q in order}
    for p in pos:
        if tuple(p) in occ:
            occ[tuple(p)] += 1
    out = []
    for _ in range(k):
        q = sorted(order, key=lambda q: (occ[q], order.index(q)))[0]
        occ[q] += 1
        out.append(q)
    return out


def _sd_harvest(t, cmds, day):
    """(product, units) a HARVEST in this op list takes (a WATER earlier in the list included)."""
    if not isinstance(t, dict):
        return None, 0
    if _is_plant(t):
        c = CROPS.get(t.get("crop"))
        if c is None:
            return None, 0
        y = int(t.get("yield_units", 0) or 0)
        if not c["ongoing"] and "WATER" in cmds and not t.get("watered_today"):
            ws = (c["maxday"] + 1) // 2
            age = day - int(t.get("planted_day", day))
            if ws <= age <= c["maxday"]:
                y = min(c["max"], y + (2 if t.get("fertilized_until_day", -1) >= day else 1))
        return t.get("crop"), y
    sp = _animal(t)
    if sp:
        return ANIMALS[sp]["product"], int(t.get("yield_units", 0) or 0)
    return None, 0


_SD_MR = {}            # v3: product -> marginal revenue / price of this step (sd_mr)
_SD_MKT = {"WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20), "CARROT": (35, 450, "hinge", 1.00, "sqrt", 0.70),
           "TOMATO": (60, 200, "hinge", 0.40, "sqrt", 0.60), "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
           "MELON": (250, 300, "log", 0.20, "sq", 3.60), "EGG": (50, 332, "hinge", 0.40, "log", 0.20),
           "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60), "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
           "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40)}   # engine market params (docs/environment.md)


def _sd_price(item, inv):
    """the engine's price curve, unrounded (base, T, below shape / target, above shape / target; I0 = 10000)."""
    import math
    base, T, fb, tb, fa, ta = _SD_MKT[item]

    def f(fn, x):
        x = max(0.0, x)
        if fn == "linear":
            return x
        if fn == "sq":
            return x * x
        if fn == "sqrt":
            return x ** 0.5
        if fn == "log":
            return math.log(1.0 + x)
        u = x / T
        return u + 8.0 * max(0.0, u - 1.0) ** 2
    if inv < 10000:
        return base + tb * base / f(fb, T) * f(fb, 10000 - inv)
    return max(1.0, base - ta * base / f(fa, T) * f(fa, inv - 10000))


_SD_SHOPS = {"BAKERY": ("EGG", "WHEAT"), "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
             "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"), "YARN_STORE": ("WOOL",),
             "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"), "PET_CAFE": ("CARROT",),
             "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"), "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY")}


def _sd_mr_table(S, obs, day, st):
    """v3: product -> marginal revenue / price. A unit sold raises the market inventory for good, so it costs our later
    units the price slope each; only the supply beyond the market's remaining consumption stays (demand now: town
    center 1 a day, 6 a day per listed shop product, 12 for a single-product shop; future shops ignored): loss = chord
    slope over 10 units x max(0, our units still to sell x 2 (the rival assumed alike) - consumption) / 2."""
    out = {}
    inv = dict(((obs.get("market") or {}).get("inventory")) or {})
    dem = Counter({k: 1 for k in PRODUCTS if k != "FERTILIZER"})
    for sh in list(((obs.get("town") or {}).get("unlocked_shops")) or []):
        ps = _SD_SHOPS.get(str(sh), ())
        for q in ps:
            dem[q] += 12 if len(ps) == 1 else 6
    rem = max(0, 29 - day) + 1
    fl = float(CFG["sd_mr_floor"])
    for k in PRODUCTS:
        if k not in inv or k not in _SD_MKT:
            continue
        x = float(inv[k])
        p0 = _sd_price(k, x)
        sl = max(0.0, (p0 - _sd_price(k, x + 10)) / 10.0)
        try:
            n = max(0, int(_T.cum_sold[_T.n - 1].get(k, 0)) - int(S["sold"][k]))
        except Exception:
            n = 0
        mr = p0 - sl * max(0.0, 2.0 * n - dem[k] * rem) / 2.0
        r = max(fl, min(1.0, mr / p0)) if p0 > 0 else 1.0
        out[k] = r
        if st is not None:
            st["mrs_" + k] = st.get("mrs_" + k, 0.0) + r
            st["mrv_" + k] = st.get("mrv_" + k, 0.0) + max(0.0, mr)
    if st is not None:
        st["mrn"] = st.get("mrn", 0) + 1
    return out


def _sd_hv_pref(t, cmds, vals, day):
    """v3: the leaders' harvest timing as soft preferences (CFG sd_hv_pref; {} = off). Returns (vals with a bonus on
    the HARVEST op, soft time target (op index, hour, coins per hour later) or None)."""
    tab = CFG["sd_hv_pref"]
    if not tab or "HARVEST" not in cmds or not _is_plant(t):
        return vals, None
    crop = t.get("crop")
    c = CROPS.get(crop)
    if c is None:
        return vals, None
    prod, units = _sd_harvest(t, cmds, day)
    if units <= 0:
        return vals, None
    i = cmds.index("HARVEST")
    age = day - int(t.get("planted_day", day))
    ent = tab.get(crop) or {}
    b = 0.0
    if c["ongoing"]:
        b += float(ent.get("bonus", 0.0))                 # tomatoes / strawberries: every production
    else:
        if age >= c["maxday"]:
            b += float((tab.get("decay") or {}).get("bonus", 0.0))   # decays from tomorrow
        for d0, d1, a0, a1 in ent.get("ages", ()):
            if int(d0) <= day <= int(d1) and int(a0) <= age <= int(a1):
                b += float(ent.get("bonus", 0.0))
                break
        if ent.get("full") and units >= c["max"]:
            b += float(ent.get("bonus", 0.0))             # melons: the first day today's water brings them to 6
    soft = None
    if ent.get("by_hour") is not None and float(ent.get("hour_w", 0.0)) > 0:
        soft = (i, int(ent["by_hour"]), float(ent["hour_w"]))
    if b:
        vals = tuple(v + (b if k == i else 0.0) for k, v in enumerate(vals))
    return vals, soft


def _sd_opvals(S, idx, t, ops, plan, day, E, last_day):
    """(per-op values, per-op deadlines, hard op index, may be cut) of one tile task, by the executor's own values."""
    n = len(ops)
    last = E - 1
    vmin = float(CFG["sd_vmin"])
    if plan:
        return tuple([0.0] * (n - 1) + [float(CFG["plan_value"])]), tuple([last] * n), -1, False
    asset = start = None
    if _is_plant(t):
        asset, start = t.get("crop"), t.get("planted_day")
    elif _animal(t):
        asset, start = t.get("animal"), t.get("placed_day")
    mj = ()
    if CFG["sched_maint"] and (idx, asset, start) in S.get("mj_known", ()):
        mj = S.get("mj", {}).get(idx, ())
    vals, dls, hi = [], [], -1
    used = set()
    for i, o in enumerate(ops):
        c = o[0]
        v, dl, hard = None, last, False
        for k, jm in enumerate(mj):
            if k in used or jm.get("asset") != asset or jm.get("cmd") != c:
                continue
            used.add(k)
            if jm.get("optional"):
                v = float(jm.get("held", 0)) * float(jm.get("price", 0)) * CFG["opt_harvest_frac"]
            else:
                v = max(0.0, float(jm.get("value", 0.0))) * _SD_MR.get(jm.get("product"), 1.0)
                dl = min(last, int(jm.get("deadline", last)))
                hard = jm.get("kind") == "survival"
            break
        if v is None:
            v = 50.0                                  # the executor's own-rule tasks (no solve yet): 50 an op
        if CFG["sd_hp_parity"] and _is_plant(t):     # parity with the executor's harvest_policy task values
            try:
                pr_ = float((S.get("prices") or {}).get(t.get("crop"), 0) or 0)
                if (c == "HARVEST" and CFG.get("harvest_policy") == "leader_tendency"
                        and t.get("crop") in CFG.get("hp_crops", ()) and _hp_window(t, day, idx)):
                    v = max(v, float(t.get("yield_units", 0) or 0) * pr_ * float(CFG["hp_frac"]))
                elif (c == "WATER" and CFG.get("harvest_policy") == "leader_tendency" and t.get("crop") == "MELON"
                      and "MELON" in CFG.get("hp_crops", ()) and 6 <= day - int(t.get("planted_day", day)) <= 10
                      and int(t.get("yield_units", 0) or 0) < CROPS["MELON"]["max"] and not t.get("watered_today")):
                    v = max(v, pr_ or 200.0)
            except Exception:
                pass
        if (CFG["sd_water_tomorrow"] and c == "WATER" and _is_plant(t) and not t.get("watered_today")
                and day < last_day):
            v = max(v, float(CFG["sd_water_tomorrow"]))   # tomorrow's labour saved (a dry plant is a must-do tomorrow)
        if day < last_day and ((c == "WATER" and _is_plant(t) and not t.get("watered_today")
                                and t.get("consecutive_unwatered", 0) >= 1)
                               or (c == "FEED" and _animal(t) and not t.get("fed_today")
                                   and t.get("consecutive_unfed", 0) >= 1)):
            hard = True
        if hard and hi < 0:
            hi = i
            v += float(CFG["sd_hard"])
            dl = last
        vals.append(max(v, vmin))
        dls.append(dl)
    return tuple(vals), tuple(dls), hi, True


def _sd_qi(idx):
    """quadrant index of a tile index: 0 NW (second), 1 NE (first), 2 SW (third), 3 SE (fourth)."""
    return (0 if idx // 10 < 5 else 2) + (0 if idx % 10 < 5 else 1)


def _sd_angle(idx):
    import math
    return math.atan2(idx // 10 - 4.5, idx % 10 - 4.5)


def _sd_corridors(P, L, hour, n):
    """radial corridors for the day: at the first plan with hands, the job tiles sorted by angle around the shed are cut
    into as many contiguous angular ranges as units, with equal work (ops); range r goes to the unit whose position
    angle matches (cyclic assignment with the least total angle gap). P.tcorr[tile] = range, P.ucorr[unit] = range."""
    import math
    cr = L.get("corr")
    day = L.get("day")
    if (cr is None or cr.get("day") != day) and n > 1:
        units = [u for u in range(n) if P.ue[u] >= 0]
        W = {}
        for j in range(P.J):
            if P.real[j]:
                W[P.jb[j][0]] = W.get(P.jb[j][0], 0) + P.jb[j][1]
        H = max(1, len(units))
        tiles = sorted(W, key=lambda i: (_sd_angle(i), i))
        tot = float(sum(W.values())) or 1.0
        cuts, acc, k = [], 0.0, 1
        for i in tiles:
            acc += W[i]
            while k < H and acc >= k * tot / H:
                cuts.append(_sd_angle(i) + 1e-6)
                k += 1
        while len(cuts) < H - 1:
            cuts.append(math.pi)
        edges = [-math.pi - 1e-9] + cuts + [math.pi + 1e-9]
        mids = [(edges[r] + edges[r + 1]) / 2.0 for r in range(H)]
        ua = sorted(units, key=lambda u: (_sd_angle(P.up[u]), u))
        best = None
        for sh in range(H):
            gap = 0.0
            for r in range(H):
                d = abs(_sd_angle(P.up[ua[(r + sh) % H]]) - mids[r])
                gap += min(d, 2 * math.pi - d)
            if best is None or gap < best[0] - 1e-9:
                best = (gap, sh)
        u2r = {ua[(r + best[1]) % H]: r for r in range(H)}
        cr = {"day": day, "edges": edges, "u2r": u2r}
        L["corr"] = cr
        def rng_of(i):
            a = _sd_angle(i)
            for r in range(H):
                if edges[r] <= a < edges[r + 1]:
                    return r
            return H - 1
        tc = [rng_of(i) for i in range(100)]
        r2u = {r: u for u, r in u2r.items()}
        L.setdefault("corridor_log", {})[str(day)] = {str(r2u[r]): [i for i in range(100) if tc[i] == r
                                                                    and (i % 10, i // 10) not in SHED]
                                                      for r in range(H) if r in r2u}
        L["st"]["corridor_days"] = L["st"].get("corridor_days", 0) + 1
    if cr is None or cr.get("day") != day:
        P.tcorr, P.ucorr = None, [-1] * P.U
        return
    edges, u2r = cr["edges"], cr["u2r"]
    H = len(edges) - 1

    def rng_of(i):
        a = _sd_angle(i)
        for r in range(H):
            if edges[r] <= a < edges[r + 1]:
                return r
        return H - 1
    P.tcorr = [rng_of(i) for i in range(100)]
    P.ucorr = [u2r.get(u, -1) for u in range(P.U)]


def _sd_sector(P, L, hour, n):
    """home quadrants of the units (P.uhome) and the rebalancing at the sectors' hours."""
    home = L.setdefault("home", {})
    uh = []
    L.setdefault("sector_log", {}).setdefault(str(L.get("day")), {})["0"] = "NW"
    for u in range(P.U):
        if u == 0:
            uh.append(0)                           # the farmer: the second quadrant (NW)
        elif u < n:
            if u not in home:
                home[u] = _sd_qi(P.up[u])
                L.setdefault("sector_log", {}).setdefault(str(L.get("day")), {})[str(u)] = ("NW", "NE", "SW", "SE")[home[u]]
            uh.append(home[u])
        else:
            uh.append(_sd_qi(P.up[u]))             # virtual hires: their spawn tile
    hrs = CFG["sd_sector_hours"] or ()
    if hour in hrs and L.get("sector_h") != (L.get("day"), hour):
        L["sector_h"] = (L.get("day"), hour)
        W = [0.0] * 4
        for j in range(P.J):
            if P.real[j] and not P.jb[j][23]:
                W[P.jb[j][22]] += P.jb[j][1]
        ctl = [u for u in range(1, min(n, P.U)) if P.uctrl[u] and P.ue[u] >= 0]
        ratio = float(CFG["sd_sector_ratio"])
        for _ in range(4):
            H = [0] * 4
            for u in ctl:
                H[uh[u]] += 1
            ld = [W[q] / max(H[q], 0.5) for q in range(4)]
            qh = max(range(4), key=lambda q: (ld[q], -q))
            don = [q for q in range(4) if H[q] >= 1 and q != qh]
            if not don or W[qh] <= 0:
                break
            ql = min(don, key=lambda q: (ld[q], q))
            if ld[qh] <= ratio * ld[ql] + 1.0:
                break
            cx, cy = (2, 2) if qh in (0, 1) else (7, 7), 0
            tx, ty = (2 if qh in (0, 2) else 7), (2 if qh in (0, 1) else 7)
            u = min((u for u in ctl if uh[u] == ql),
                    key=lambda u: (abs(P.up[u] % 10 - tx) + abs(P.up[u] // 10 - ty), u))
            uh[u] = qh
            home[u] = qh
            L.setdefault("sector_changes", []).append([int(L.get("day", 0)) * 24 + int(hour), int(u), ("NW", "NE", "SW", "SE")[qh]])
            L["st"]["sector_moves"] = L["st"].get("sector_moves", 0) + 1
    P.uhome = uh


def _sd_bundle(S, L, P, idx, t, ops, job, carried, prices, day, E, last_day, hour, last, add, gains):
    """sd_bundle_build: the tile's clearing ops (WATER if due, HARVEST / DIG) + BUILD + PLACE + FEED + CARE as one job
    (the harvest_before_build task holds only the clearing ops: the structure part is appended). Value: the clearing
    ops' own values + a day of the animal (2 x its product price / interval + the fertilizer price) on the last op; only
    the clearing ops may stand alone at the day end. Without the animal (bought at hour 0 at the earliest) the structure
    waits whole: hour 0 plans nothing on the tile, later hours only the clearing ops. Returns True when handled."""
    sp = job[2]
    cmds = [o[0] for o in ops]
    if not any(c in ("BUILD_COOP", "BUILD_PASTURE") for c in cmds):
        if not all(c in ("WATER", "HARVEST", "DIG") for c in cmds):
            return False
        ops = [list(o) for o in ops] + [["BUILD_" + job[1]], ["PLACE", sp], ["FEED"], ["CARE"]]
        cmds = [o[0] for o in ops]
    ib = next(i for i, c in enumerate(cmds) if c in ("BUILD_COOP", "BUILD_PASTURE"))
    clear = ops[:ib]
    avail = P.ava[_SD_SPI[sp]] + carried.get(sp, 0) > 0
    if not avail:
        L["st"]["bundle_wait"] = L["st"].get("bundle_wait", 0) + 1
        if hour == 0 or not clear:
            return True
        ops, cmds = clear, cmds[:ib]
    if not any(o[0] == "PLACE" for o in ops) and any(c in ("BUILD_COOP", "BUILD_PASTURE") for c in cmds):
        return True                                # never an empty structure
    cv, cd, chi, _ = _sd_opvals(S, idx, t, clear, False, day, E, last_day) if clear else ((), (), -1, True)
    cv, soft = _sd_hv_pref(t, [o[0] for o in clear], cv, day) if clear else (cv, None)
    n = len(ops)
    if len(ops) > len(clear):
        a = ANIMALS[sp]
        dv = (2.0 * float(prices.get(a["product"], 0) or 0) / max(1, a["interval"])
              + float(prices.get("FERTILIZER", 0) or 0)) if CFG["sd_bundle_value"] == "auto" else float(CFG["sd_bundle_value"])
        vals = tuple(cv) + tuple([0.0] * (n - len(clear) - 1) + [dv])
        dls = tuple(cd) + tuple([last] * (n - len(clear)))
    else:
        vals, dls = tuple(cv), tuple(cd)
    gw, gf, gdu, gdv, gty, gcv = gains(t, [o[0] for o in clear]) if clear else (0, 0, 0, 0.0, 0, 0.0)
    add(idx, idx, ops, vals, dls, chi, len(clear), hour, -1, 0, True, None, gw, gf, gdu, gdv, gty, gcv, soft)
    L["st"]["bundle_jobs"] = L["st"].get("bundle_jobs", 0) + (1 if len(ops) > len(clear) else 0)
    return True


def _sd_build(S, L, ctx):
    D, SD, SA, DS, NS = _sd_tables()
    day, hour, tiles, tasks = ctx["day"], ctx["hour"], ctx["tiles"], ctx["tasks"]
    invs, pos, shed, seeds, assign = ctx["invs"], ctx["pos"], ctx["shed"], ctx["seeds"], ctx["assign"]
    n, last_day, prices = len(pos), ctx["last_day"], ctx["prices"]
    fert_keep = bool(ctx["fert_keep"])
    P = _SdP()
    P.d, P.sd, P.sa, P.ds, P.ns = D, SD, SA, DS, NS
    P.day, P.hour = day, hour
    P.lastday = day >= last_day
    E = 24 if day < last_day else 23
    P.E = E
    P.lam = float(CFG["sd_lambda"])
    P.late_frac = float(CFG["sd_late_frac"])
    P.switch_w = float(CFG["sd_switch"])
    P.cap_w = float(CFG["sd_cap_w"])
    P.cap_lim = float(CFG["sd_cap"] - CFG["sd_cap_margin"])
    P.nev = 0
    P.deliv = bool(CFG["sd_deliv"])
    P.dunits = float(CFG["deliver_units"])
    P.dval = float(CFG["deliver_value"])
    P.dval_late = float(CFG["deliver_value_late"])
    P.late_h = CFG["late_hour"] if CFG["prio3"] else 99
    P.short = bool(S.get("short"))
    P.fert_keep = fert_keep
    _SD_MR.clear()
    if CFG["sd_mr"]:
        _SD_MR.update(_sd_mr_table(S, ctx["obs"], day, L["st"] if hour == 1 else None))
    dvt = {} if P.lastday else _sd_dv_table(S, day, prices, shed)   # day 29: the endgame rule delivers everything
    P.dvc = bool(dvt)                                  # v2: in-day delivery credit on
    P.dvt = dvt
    P.dv_h1 = int(CFG["sd_dv_hour"]) + 1                 # a delivery ending by this hour sells the same day
    P.ftrip = bool(CFG["sd_final_trip"])
    P.hlw = float(CFG["sd_hard_late_w"])
    P.hsafe = int(CFG["sd_hard_safe"])
    carried = Counter()
    for inv in invs:
        carried.update(inv)
    P.base_load = float(sum(int(shed.get(k, 0) or 0) for k in ("WHEAT", "FERTILIZER") + _SD_SP)
                        + sum(v for v in carried.values() if v > 0))
    if CFG["sd_cap_all"]:                          # v3: products that stay in the shed overnight count too
        ss = CFG.get("sell_source")
        for k in PRODUCTS:
            v = int(shed.get(k, 0) or 0)
            if k in ("WHEAT", "FERTILIZER") or v <= 0:
                continue
            if ss == "leader" and _T is not None:  # the rest of the leader's quota of the day sells today
                v -= min(v, max(0, _T.cum_sold[min(day, _T.n - 1)].get(k, 0) - S["sold"][k]))
            elif ss == "sem" and k != "STRAWBERRY":
                v = 0                              # the sem rule sells everything but strawberries at once
            P.base_load += v
    # shed stock shared by the routes (wheat: + the executor's feed buy of this step, in the shed next step)
    dw = max(0, int(ctx["demand"].get("WHEAT", 0)) - int(carried.get("WHEAT", 0)) - int(shed.get("WHEAT", 0)))
    P.avw = int(shed.get("WHEAT", 0)) + dw
    P.avf = int(shed.get("FERTILIZER", 0))
    P.ava = [int(shed.get(s, 0)) for s in _SD_SP]
    pf_price = float(prices.get("FERTILIZER", 0) or 0)
    last = E - 1
    pv = float(CFG["plan_value"])
    # ---------------------------------------------------------------- jobs
    keys, JB, OPS, REAL, CROPI, NET, HARD, VRAW = [], [], [], [], [], [], [], []
    kidx = {}

    def add(key, tile, ops, vals, dls, hi, cutp, rel, pred, lag, real, crop_i, gw, gf, gdu, gdv, gty, gcv=0.0,
            soft=None):
        cmds = [o[0] for o in ops]
        nw = cmds.count("FEED")
        nf = cmds.count("FERTILIZE")
        na = -1
        for o in ops:
            if o[0] == "PLACE" and len(o) > 1 and o[1] in _SD_SPI:
                na = _SD_SPI[o[1]]
        fi = tuple(i for i, c in enumerate(cmds) if c == "FERTILIZE")
        wi = tuple(i for i, c in enumerate(cmds) if c == "FEED" or (c == "CARE" and nw))   # no wheat: no FEED, no CARE
        j = len(keys)
        keys.append(key)
        kidx[key] = j
        JB.append((tile, len(ops), nw, nf, na, gw, gf, vals, dls, int(rel), int(hi), pred, int(lag), False,
                   int(cutp), gdu, gdv, gty, fi, wi, gcv, soft, _sd_qi(tile),
                   hi >= 0 or any(c_ in ("PLANT", "BUILD_COOP", "BUILD_PASTURE", "PLACE") for c_ in cmds)))
        OPS.append(ops)
        REAL.append(real)
        CROPI.append(crop_i)
        NET.append(gw + gf - nw - nf - (1 if na >= 0 else 0))
        HARD.append(hi >= 0)
        VRAW.append(sum(vals) - (float(CFG["sd_hard"]) if hi >= 0 else 0.0))
        return j

    def gains(t, cmds):
        prod, units = _sd_harvest(t, cmds, day) if "HARVEST" in cmds else (None, 0)
        gw = units if prod == "WHEAT" else 0
        gf = cmds.count("COLLECT_FERTILIZER")
        gdu, gdv, gty, gcv = 0, 0.0, 0, 0.0
        if prod is not None and prod != "WHEAT" and units > 0:
            gdu, gdv, gty = units, units * float(prices.get(prod, 0) or 0), 1
            gcv = units * dvt.get(prod, 0.0)
        if gf and not fert_keep:
            gdu += gf
            gdv += gf * pf_price
            gty += 1
            gcv += gf * dvt.get("FERTILIZER", 0.0)
        return gw, gf, gdu, gdv, gty, gcv

    stiles = ctx.get("stiles") or ()
    for idx in sorted(tasks):
        if idx in stiles:
            continue                               # v5: the greedy's survival route serves this tile
        ops, need, prio = tasks[idx]
        t = _tile(tiles, idx)
        if CFG["sd_coop_pair"]:
            jb_ = ctx["jobs"].get(idx)
            if jb_ is not None and jb_[0] == "BUILD" and len(jb_) > 2 and jb_[2] in _SD_SPI:
                oc_ = [o[0] for o in ops]
                sp_ = jb_[2]
                emp_ = (isinstance(t, dict) and t.get("kind") == ANIMALS[sp_]["structure"] and "animal" not in t
                        and oc_[:1] == ["PLACE"])      # the structure stands empty: the rest of the pair
                if emp_ or any(c_ in ("BUILD_COOP", "BUILD_PASTURE") for c_ in oc_):
                    if P.ava[_SD_SPI[sp_]] + carried.get(sp_, 0) > 0 and any(o[0] == "PLACE" for o in ops):
                        pops = [list(o) for o in ops if o[0] not in ("FEED", "CARE")]
                        ip_ = max(i_ for i_, o in enumerate(pops) if o[0] == "PLACE")
                        pops = pops[:ip_ + 1]
                        hd_ = CFG["sd_coop_pair"] >= 2        # must complete by the day end (any hour): a hard op
                        add(idx, idx, pops, tuple([0.0] * ip_ + [pv + (float(CFG["sd_hard"]) if hd_ else 0.0)]),
                            tuple([last] * len(pops)), ip_ if hd_ else -1, 0, hour, -1, 0, True, None, 0, 0, 0, 0.0, 0,
                            0.0)
                        L["st"]["coop_pair"] = L["st"].get("coop_pair", 0) + 1
                    else:
                        L["st"]["coop_wait"] = L["st"].get("coop_wait", 0) + 1
                    continue                       # never an empty structure: without the animal the pair waits
        if CFG["sd_bundle_build"]:
            jb_ = ctx["jobs"].get(idx)
            if jb_ is not None and jb_[0] == "BUILD" and len(jb_) > 2 and jb_[2] in _SD_SPI:
                if _sd_bundle(S, L, P, idx, t, ops, jb_, carried, prices, day, E, last_day, hour, last, add, gains):
                    continue
        kept = []
        placing_blocked = False
        for o in ops:                              # an animal nobody can supply today: PLACE and its FEED / CARE go
            c = o[0]
            if c == "PLACE" and len(o) > 1 and o[1] in _SD_SPI:
                sp = o[1]
                if P.ava[_SD_SPI[sp]] + carried.get(sp, 0) <= 0:
                    placing_blocked = True
                    continue
            if placing_blocked and c in ("FEED", "CARE"):
                continue
            kept.append(o)
        if not kept:
            continue
        cmds = [o[0] for o in kept]
        job_ = ctx["jobs"].get(idx)
        # plan part = from the first structural op (DIG / PLANT / BUILD / PLACE) on; the maintenance ops before it (the
        # current plant's WATER / HARVEST of a replant) are a job of their own, and the plan part follows it (order pair)
        k0 = next((i for i, c in enumerate(cmds) if c in ("DIG",) + _SD_PLANC), None)
        if k0 is not None and not any(c in _SD_PLANC for c in cmds):
            k0 = None                              # a lone DIG (weed / removal) is maintenance
        if job_ is not None and job_[0] == "BUILD" and cmds == ["HARVEST"]:
            k0 = 0                                 # harvest_before_build: clears the tile for the structure
        pre, planp = (kept, []) if k0 is None else (kept[:k0], kept[k0:])
        j1 = None
        if pre:
            pc = [o[0] for o in pre]
            vals, dls, hi, trunc = _sd_opvals(S, idx, t, pre, False, day, E, last_day)
            vals, soft = _sd_hv_pref(t, pc, vals, day)
            gw, gf, gdu, gdv, gty, gcv = gains(t, pc)
            j1 = add(idx, idx, pre, vals, dls, hi, len(pre), hour, -1, 0, True, None, gw, gf, gdu, gdv, gty, gcv,
                     soft)
        if planp:
            pc = [o[0] for o in planp]
            crop_i = next((o[1] for o in planp if o[0] == "PLANT"), None)
            nn = len(planp)
            vals, dls = tuple([0.0] * (nn - 1) + [pv]), tuple([last] * nn)
            gw, gf, gdu, gdv, gty, gcv = gains(t, pc) if (pc == ["HARVEST"]) else (0, 0, 0, 0.0, 0, 0.0)
            key = idx if j1 is None else ("B", idx)
            ip = next((i_ for i_ in range(1, nn) if pc[i_] == "PLACE" and pc[i_ - 1] in ("BUILD_COOP", "BUILD_PASTURE")),
                      None) if CFG["sd_split_place"] else None
            if ip is None:
                add(key, idx, planp, vals, dls, -1, 0, hour, -1 if j1 is None else j1, 0, True, crop_i, gw, gf, gdu, gdv,
                    gty, gcv)
            else:                                  # the structure first (short, no pickup), the placement as its successor
                ja = add(key, idx, planp[:ip], tuple([0.0] * (ip - 1) + [float(CFG["sd_build_value"])]),
                         tuple([last] * ip), -1, 0, hour, -1 if j1 is None else j1, 0, True, None, 0, 0, 0, 0.0, 0, 0.0)
                add(("G", idx), idx, planp[ip:], tuple([0.0] * (nn - ip - 1) + [pv]), tuple([last] * (nn - ip)), -1, 0,
                    hour, ja, 0, True, None, 0, 0, 0, 0.0, 0, 0.0)
                jb = JB[ja]
                JB[ja] = jb[:13] + (True,) + jb[14:]
                L["st"]["split_place"] = L["st"].get("split_place", 0) + 1
            if j1 is not None:
                jb = JB[j1]
                JB[j1] = jb[:13] + (True,) + jb[14:]      # the prefix is a predecessor: its finish is tracked
    # sd_coop_pair: a tile still holding its crop (harvest_before_build) gets the pair predicted after its harvest job
    if CFG["sd_coop_pair"]:
        for idx, jb_ in sorted(ctx["jobs"].items()):
            if not (jb_ and jb_[0] == "BUILD" and len(jb_) > 2 and jb_[2] in _SD_SPI) or idx not in kidx:
                continue
            j1 = kidx[idx]
            if any(o[0] in ("BUILD_COOP", "BUILD_PASTURE") for o in OPS[j1]):
                continue
            sp_ = jb_[2]
            if P.ava[_SD_SPI[sp_]] + carried.get(sp_, 0) <= 0:
                continue
            hd_ = CFG["sd_coop_pair"] >= 2
            add(("K", idx), idx, [["BUILD_" + jb_[1]], ["PLACE", sp_]],
                (0.0, pv + (float(CFG["sd_hard"]) if hd_ else 0.0)), (last, last), 1 if hd_ else -1, 0, hour, j1, 0, True,
                None, 0, 0, 0, 0.0, 0, 0.0)
            jb = JB[j1]
            JB[j1] = jb[:13] + (True,) + jb[14:]
            if hd_:
                HARD[j1] = True                    # the clearing harvest carries the pair: inserted / kept first
    # v3: melons offered at full yield (see the header)
    ment = (CFG["sd_hv_pref"] or {}).get("MELON") or {}
    if ment.get("offer") and not P.lastday:
        cm = CROPS["MELON"]
        pm = float(prices.get("MELON", 0) or 0)
        for idx in range(100):
            t = _tile(tiles, idx)
            if not (_is_plant(t) and t.get("crop") == "MELON") or ("B", idx) in kidx:
                continue
            age = day - int(t.get("planted_day", day))
            if age < cm["first"]:
                continue
            j1 = kidx.get(idx)
            c1 = [o[0] for o in OPS[j1]] if j1 is not None else []
            if "HARVEST" in c1 or "DIG" in c1:
                continue                           # the task harvests / removes it already
            wat = "WATER" in c1
            units = _sd_harvest(t, ["WATER", "HARVEST"], day)[1] if wat else int(t.get("yield_units", 0) or 0)
            if units < cm["max"]:
                continue
            soft = ((0, int(ment["by_hour"]), float(ment.get("hour_w", 0.0)))
                    if ment.get("by_hour") is not None and float(ment.get("hour_w", 0.0)) > 0 else None)
            add(("H", idx), idx, [["HARVEST"]], (max(float(ment.get("bonus", 0.0)), float(CFG["sd_vmin"])),),
                (last,), -1, 1, hour, j1 if wat else -1, 0, True, None, 0, 0, units, units * pm, 1,
                units * dvt.get("MELON", 0.0), soft)
            if wat:
                jb = JB[j1]
                JB[j1] = jb[:13] + (True,) + jb[14:]          # the WATER task is a predecessor: its finish is tracked
    # sd_water_tomorrow: plants the executor leaves dry today (no task: no production effect) get a planner-only water
    # job worth tomorrow's labour saved; idle capacity then waters the patch instead of passing
    if CFG["sd_water_tomorrow"] and not P.lastday:
        wv = float(CFG["sd_water_tomorrow"])
        for idx in range(100):
            if idx in kidx or ("B", idx) in kidx or ("H", idx) in kidx or idx in stiles:
                continue
            t = _tile(tiles, idx)
            if _is_plant(t) and not t.get("watered_today"):
                add(("W", idx), idx, [["WATER"]], (wv,), (last,), -1, 1, hour, -1, 0, True, None, 0, 0, 0, 0.0, 0, 0.0)
    # predicted jobs (1): plan plantings whose seeds are bought this step (tile free or weed, no task yet)
    pseen = L["pred_seen"]
    if CFG["sd_plan_jobs"]:
        for idx, job in sorted(ctx["jobs"].items()):
            if not job or job[0] != "PLANT" or idx in tasks or idx in kidx:
                continue
            crop = job[1]
            if seeds.get(crop, 0) > 0:
                continue
            t = _tile(tiles, idx)
            if not (t is None or _is_weed(t)):
                continue
            k = ("P", idx)
            first = pseen.setdefault(k, hour)
            if hour - first > 2:
                continue                           # the seeds never came: stop waiting for them
            ops = ([["DIG"]] if t is not None else []) + [["PLANT", crop], ["WATER"]]
            nn = len(ops)
            add(k, idx, ops, tuple([0.0] * (nn - 1) + [pv]), tuple([last] * nn), -1, 0, hour + 1, -1, 0, False,
                None, 0, 0, 0, 0.0, 0)
    # predicted jobs (2): the deploy's same-day replant after a wheat / carrot harvest (order pair: harvest -> plant +
    # water). The replant task appears the step after the harvest (the tile reads empty) when seeds are in stock, one
    # step later when they are bought then.
    if CFG["sd_pairs"] and "DEP_CFG" in globals() and "_DEP" in globals():
        try:
            dc = DEP_CFG
            ds_c = _DEP.get("ds_crops", {}) if _DEP.get("ds_day") == day else {}
            if dc.get("replant_same_day") and day >= dc.get("replant_from", 99) and ds_c:
                capped = False
                if dc.get("replant_cap") and _DEP.get("wh_pred", (None,))[0] == day:
                    n_wh = sum(1 for j in range(100) if _is_plant(_tile(tiles, j)) and _tile(tiles, j)["crop"] == "WHEAT")
                    n_wh += sum(1 for j, c in _T.plant[day].items() if c == "WHEAT" and _tile(tiles, j) is None)
                    capped = n_wh >= dc["replant_cap"] * _DEP["wh_pred"][1]
                in_stock = Counter(seeds)
                for j2, c2 in enumerate(CROPI):
                    if c2 is not None and REAL[j2]:
                        in_stock[c2] -= 1
                for idx in sorted(tasks):
                    j1 = kidx.get(idx)
                    if j1 is None or idx not in ds_c or ("B", idx) in kidx or ("K", idx) in kidx:
                        continue
                    crop = ds_c[idx]
                    t = _tile(tiles, idx)
                    cm = [o[0] for o in OPS[j1]]
                    if not (_is_plant(t) and t.get("crop") == crop and "HARVEST" in cm and "PLANT" not in cm):
                        continue
                    if idx in _T.plant[day] or day > dc["last_plant"].get(crop, -1) or (crop == "WHEAT" and capped):
                        continue
                    lag = 0 if in_stock.get(crop, 0) > 0 else 1
                    if in_stock.get(crop, 0) > 0:
                        in_stock[crop] -= 1
                    add(("R", idx), idx, [["PLANT", crop], ["WATER"]], (0.0, float(CFG["sd_replant_value"])),
                        (last, last), -1, 0, hour, j1, lag, False, None, 0, 0, 0, 0.0, 0)
                    jb = JB[j1]
                    JB[j1] = jb[:13] + (True,) + jb[14:]      # j1 is a predecessor: its finish is tracked
        except Exception:
            S["log"]["sd_pair_error"] += 1
    P.key, P.jb, P.ops, P.real, P.cropi, P.net, P.hard, P.vraw, P.kidx = (
        keys, JB, OPS, REAL, CROPI, NET, HARD, VRAW, kidx)
    J = len(keys)
    P.J = J
    P.succ = [-1] * J
    for j in range(J):
        if JB[j][11] >= 0:
            P.succ[JB[j][11]] = j
    P.seeds = {c: int(v) for c, v in seeds.items()}
    # ---------------------------------------------------------------- units
    cols = {k: [] for k in ("t0", "p", "w", "f", "a", "an", "du", "dv", "ty", "e", "ctrl", "virt", "swk", "swn",
                            "cv")}
    walk = L["walk"]

    def unit(t0, pi, inv, ctrl, virt, w):
        du = dv = cv = 0.0
        ty = 0
        for k_, v_ in inv.items():
            if v_ > 0 and k_ in PRODUCTS and k_ != "WHEAT" and not (k_ == "FERTILIZER" and fert_keep):
                du += v_
                dv += v_ * float(prices.get(k_, 0) or 0)
                cv += v_ * dvt.get(k_, 0.0)
                ty += 1
        cols["cv"].append(cv)
        cols["t0"].append(t0)
        cols["p"].append(pi)
        cols["w"].append(int(inv.get("WHEAT", 0)))
        cols["f"].append(int(inv.get("FERTILIZER", 0)))
        cols["a"].append(tuple(int(inv.get(s, 0)) for s in _SD_SP))
        cols["an"].append(sum(int(inv.get(s, 0)) for s in _SD_SP))
        cols["du"].append(du)
        cols["dv"].append(dv)
        cols["ty"].append(ty)
        cols["e"].append(E)
        cols["ctrl"].append(ctrl)
        cols["virt"].append(virt)
        cols["swk"].append(w[0] if w else None)
        cols["swn"].append(int(w[1]) if (w and w[0] is not None) else 0)

    for u in range(n):
        p = tuple(pos[u])
        pi = p[1] * 10 + p[0]
        inv = invs[u]
        t0 = hour
        ctrl = True
        if assign.get(u) == "D":                   # delivering: free once the executor's delivery is done
            dv = ctx["deliv_u"](u)
            s = _near_shed(p)
            si = s[1] * 10 + s[0]
            k = 1 if (dv and all(k_ in dv for k_ in inv)) else max(1, len(dv))
            t0 = hour + D[pi][si] + k
            pi = si
            inv = Counter({k_: v_ for k_, v_ in inv.items() if k_ not in dv})
            ctrl = False
        unit(t0, pi, inv, ctrl, False, walk.get(u))
    for u in ctx.get("keep") or ():                # v5: units on the greedy's survival routes are not planned
        if u < n:
            cols["e"][u] = -1
            cols["ctrl"][u] = False
    P.n_real = n
    if hour == 0 and n == 1 and day < last_day:            # hour 0: the day's hires spawn at hour 1 (virtual units)
        vu = ctx.get("vunits")
        if vu is None:
            vu = [(q, 1) for q in _sd_spawn(pos, _sd_want_hands(day))]
        for q, t0v in vu:
            unit(t0v, q[1] * 10 + q[0], Counter(), False, True, None)
    (P.ut0, P.up, P.uw, P.uf, P.ua, P.uan, P.udu, P.udv, P.uty, P.ue, P.uctrl, P.uvirt, P.uswk, P.uswn) = (
        cols["t0"], cols["p"], cols["w"], cols["f"], cols["a"], cols["an"], cols["du"], cols["dv"], cols["ty"],
        cols["e"], cols["ctrl"], cols["virt"], cols["swk"], cols["swn"])
    P.ucv = cols["cv"]
    U = len(P.ut0)
    P.U = U
    P.corrw = float(CFG["sd_corr_w"])
    P.radin, P.radside = float(CFG["sd_rad_in"]), float(CFG["sd_rad_side"])
    if P.corrw:
        _sd_corridors(P, L, hour, n)
    else:
        P.tcorr, P.ucorr = None, [-1] * U
    P.secw = float(CFG["sd_sector_w"])
    P.hopw = float(CFG["sd_hop_w"])
    P.hopc = int(CFG["sd_hop_central"])
    if P.secw:
        _sd_sector(P, L, hour, n)
    else:
        P.uhome = [-1] * U
    # ---------------------------------------------------------------- empty plan
    P.routes = [[] for _ in range(U)]
    P.rsc = [0.0] * U
    P.rpw = [0] * U
    P.rpf = [0] * U
    P.rpa = [_SD_Z3] * U
    P.rkp = [(-1, 0)] * U
    P.rfin = [None] * U
    P.rend = [0] * U
    P.where = [-1] * J
    P.ft = {}
    P.tpw = P.tpf = 0
    P.tpa = [0, 0, 0]
    P.seed_used = Counter()
    P.load = P.base_load
    for u in range(U):
        ev = _sd_eval(P, u, [])
        P.rsc[u] = ev[1]
        P.rend[u] = ev[2]
    return P


def _sd_eval(P, u, r):
    """(ok, score, t_end, pick wheat, pick fertilizer, pick animals (3), pickup position, pickup steps, finish of the
    predecessor jobs in r) for unit u doing the jobs r in order: the best of taking the wheat / fertilizer the route
    needs from the shed or leaving it (the FEED + CARE / FERTILIZE ops without it are skipped, as the executor's
    usable_ops does; a hard op among them fails that variant)."""
    ev = _sd_eval1(P, u, r, True, True)
    if not r or (not ev[0] and ev[2] not in ("dayend", "cut", "hard_late", "lastday")):
        return ev
    need_w = need_f = False
    if ev[0]:
        need_w, need_f = ev[3] > 0, ev[4] > 0
    else:                                          # infeasible with pickups: which items does the route need?
        JB = P.jb
        need_w = any(JB[j][2] for j in r) and P.uw[u] < sum(JB[j][2] for j in r)
        need_f = any(JB[j][3] for j in r) and P.uf[u] < sum(JB[j][3] for j in r)
    best = ev
    for aw, af in ((True, False), (False, True), (False, False)):
        if (not aw and not need_w) or (not af and not need_f):
            continue
        e2 = _sd_eval1(P, u, r, aw, af)
        if e2[0] and (not best[0] or e2[1] > best[1] + 1e-9):
            best = e2
    return best


def _sd_eval1(P, u, r, aw_ok, af_ok):
    """one variant of _sd_eval: aw_ok / af_ok = wheat / fertilizer may be picked up at the shed (the shared stock
    permitting; a route short of stock takes what is left and skips what it cannot supply)."""
    P.nev += 1
    t = P.ut0[u]
    t0 = t
    sw = 0.0
    if P.uswn[u] and (not r or P.key[r[0]] != P.uswk[u]):
        sw = P.switch_w * P.uswn[u]
    if not r:
        if P.ftrip and P.deliv and P.ucv[u] > 0:       # v2: an idle unit walks what it carries to the shed
            p = P.up[u]
            s = P.ns[p]
            ty = P.uty[u]
            nd = P.uw[u] > 0 or P.uan[u] > 0 or (P.uf[u] > 0 and P.fert_keep)
            tf = t + P.d[p][s] + ((ty if ty < 4 else 4) if nd else 1)
            if tf <= P.dv_h1:
                return (True, P.ucv[u] - P.lam * (tf - t0) - sw, tf, 0, 0, _SD_Z3, -1, 0, None)
        return (True, -sw, t, 0, 0, _SD_Z3, -1, 0, None)
    JB = P.jb
    D = P.d
    L_ = len(r)
    # ---- items: lowest running balance (wheat / fertilizer gained earlier in the route count)
    bw = P.uw[u]
    bf = P.uf[u]
    lw, lf = bw, bf
    neg = L_
    a0 = a1 = a2 = 0
    ua = P.ua[u]
    for k in range(L_):
        jb = JB[r[k]]
        x = jb[2]
        if x:
            bw -= x
            if bw < lw:
                lw = bw
                if bw < 0 and k < neg:
                    neg = k
        x = jb[3]
        if x:
            bf -= x
            if bf < lf:
                lf = bf
                if bf < 0 and k < neg:
                    neg = k
        x = jb[4]
        if x >= 0:
            if x == 0:
                a0 += 1
                c = a0
            elif x == 1:
                a1 += 1
                c = a1
            else:
                a2 += 1
                c = a2
            if c > ua[x] and k < neg:
                neg = k
        bw += jb[5]
        bf += jb[6]
    pw = -lw if lw < 0 else 0
    pf = -lf if lf < 0 else 0
    pa = (a0 - ua[0] if a0 > ua[0] else 0, a1 - ua[1] if a1 > ua[1] else 0, a2 - ua[2] if a2 > ua[2] else 0)
    kp = -1
    p = P.up[u]
    wsk = fsk = False
    if pw:
        aw = P.avw - (P.tpw - P.rpw[u]) if aw_ok else 0
        if pw > aw:
            pw = aw if aw > 0 else 0
            wsk = True
    if pf:
        af = P.avf - (P.tpf - P.rpf[u]) if af_ok else 0
        if pf > af:
            pf = af if af > 0 else 0
            fsk = True
    if pa[0] + pa[1] + pa[2]:
        ra = P.rpa[u]
        for i in range(3):
            if pa[i] and pa[i] > P.ava[i] - (P.tpa[i] - ra[i]):
                return _SD_FAILS["stock_a"]
    npk = (pw > 0) + (pf > 0) + (pa[0] > 0) + (pa[1] > 0) + (pa[2] > 0)
    if npk:
        SD = P.sd
        prev = p
        best = 999
        for k in range(neg + 1 if neg < L_ else L_):
            b = JB[r[k]][0]
            det = SD[prev][b] - D[prev][b]
            if det < best:
                best = det
                kp = k
            prev = b
    # ---- time
    val = 0.0
    prev = p
    fin = None
    E = P.ue[u]
    lf_ = P.late_frac
    deliv = P.deliv
    picked = not npk
    cw, cf, can = P.uw[u], P.uf[u], P.uan[u]
    if deliv:
        du, dv, ty = P.udu[u], P.udv[u], P.uty[u]
        late_h, dun, dva, dvl, short, fk = P.late_h, P.dunits, P.dval, P.dval_late, P.short, P.fert_keep
        cv, dvh1 = P.ucv[u], P.dv_h1
    hlw = P.hlw
    secw, uhq = P.secw, P.uhome[u]
    corrw, ucr, tcr = P.corrw, P.ucorr[u], P.tcorr
    radin, radside = P.radin, P.radside
    hopw, pj, hopc = P.hopw, False, P.hopc
    for k in range(L_):
        j = r[k]
        jb = JB[j]
        b = jb[0]
        if k == kp and not picked:
            s = P.sa[prev][b]
            t += D[prev][s] + npk
            prev = s
            pj = False
            picked = True
            cw += pw
            cf += pf
            can += pa[0] + pa[1] + pa[2]
        if hopw and pj and D[prev][b] > 1 and P.ds[prev] > hopc and P.ds[b] > hopc:   # contiguity in the patch
            val -= hopw * (D[prev][b] - 1)
        if (radin or radside) and pj:              # radial: job to job, inward and sideways steps cost
            da_, db_ = P.ds[prev], P.ds[b]
            val -= radin * (da_ - db_ if da_ > db_ else 0) + radside * (D[prev][b] - (db_ - da_ if db_ > da_ else da_ - db_))
        t += D[prev][b]
        rel = jb[9]
        pr = jb[11]
        if pr >= 0:
            f = fin.get(pr) if fin is not None else None
            if f is None:
                if pr in r:                        # the predecessor comes later in this route
                    return _SD_FAILS["pred_later"]
                f = P.ft.get(pr)
                if f is None:                      # predecessor not planned
                    return _SD_FAILS["pred_none"]
            if f + jb[12] > rel:
                rel = f + jb[12]
        if t < rel:
            t = rel
        n = jb[1]
        vals = jb[7]
        dls = jb[8]
        hi = jb[10]
        skip = ()
        nw, nf = jb[2], jb[3]
        if (wsk and nw and cw < nw) or (fsk and nf and cf < nf):
            if wsk and nw and cw < nw:
                skip = jb[19]
                nw = 0
            if fsk and nf and cf < nf:
                skip = skip + jb[18]
                nf = 0
            if hi in skip:
                return _SD_FAILS["hard_stock"]
        m = n - len(skip)                          # ops executed
        if hi >= 0 and hlw:                        # v2: a hard op done late in the day (it fails if not on time)
            x = t + (hi - sum(1 for s_ in skip if s_ < hi) if skip else hi) - P.hsafe
            if x > 0:
                val -= hlw * x
        if secw and uhq >= 0 and jb[22] != uhq and not jb[23]:   # sectors: ops outside the unit's home quadrant
            val -= secw * (m if t + m <= E else (E - t if E > t else 0))
        if corrw and ucr >= 0 and tcr is not None and tcr[b] != ucr and not jb[23]:   # radial corridors
            val -= corrw * (m if t + m <= E else (E - t if E > t else 0))
        sft = jb[21]
        if sft is not None and sft[0] not in skip:  # v3: soft time target (melons early in the morning)
            x = t + (sft[0] - sum(1 for s_ in skip if s_ < sft[0]) if skip else sft[0])
            if sft[1] < x < E:
                val -= sft[2] * (x - sft[1])
        if t + m > E:
            # the day ends inside this job: only the route's last job, only its leading maintenance ops
            if k != L_ - 1:
                return _SD_FAILS["dayend"]
            mm = E - t
            if mm <= 0 or mm > jb[14]:
                return _SD_FAILS["cut"]
            done = 0
            for i in range(n):
                if i in skip:
                    continue
                if done >= mm:
                    if i == hi:
                        return _SD_FAILS["cut"]
                    continue
                if t + done <= dls[i]:
                    val += vals[i]
                else:
                    val += vals[i] * lf_
                done += 1
            t = E
            prev = b
            break
        if skip:
            done = 0
            for i in range(n):
                if i in skip:
                    continue
                if t + done <= dls[i]:
                    val += vals[i]
                elif i == hi:
                    return _SD_FAILS["hard_late"]
                else:
                    val += vals[i] * lf_
                done += 1
        else:
            for i in range(n):
                if t + i <= dls[i]:
                    val += vals[i]
                elif i == hi:
                    return _SD_FAILS["hard_late"]
                else:
                    val += vals[i] * lf_
        t += m
        if jb[13]:
            if fin is None:
                fin = {}
            fin[j] = t
        prev = b
        pj = True
        cw += jb[5] - nw
        cf += jb[6] - nf
        if jb[4] >= 0:
            can -= 1
        if deliv:
            g = jb[15]
            if g:
                du += g
                dv += jb[16]
                ty += jb[17]
                cv += jb[20]
                if t < 22 and (((du >= dun or dv >= dva) and t < late_h) or (short and dv > 0)
                               or (dv >= dvl and t < 20)):
                    s = P.ns[b]                    # the executor's delivery: nearest shed tile, DROP / PLACE a type
                    nd = cw > 0 or can > 0 or (cf > 0 and fk)
                    t += D[b][s] + ((ty if ty < 4 else 4) if nd else 1)
                    if cv and t <= dvh1:           # v2: sold the same day
                        val += cv
                    prev = s
                    pj = False
                    du = dv = 0.0
                    ty = 0
                    cv = 0.0
                    if not picked and kp > k:      # the pending pickup rides on this visit
                        t += npk
                        picked = True
                        cw += pw
                        cf += pf
                        can += pa[0] + pa[1] + pa[2]
    if deliv and cv > 0 and P.ftrip:               # v2: after the last job the unit walks its products to the shed
        s = P.ns[prev]
        nd = cw > 0 or can > 0 or (cf > 0 and fk)
        tf = t + D[prev][s] + ((ty if ty < 4 else 4) if nd else 1)
        if tf <= dvh1:
            val += cv
            t = tf
            prev = s
    if P.lastday and t + P.ds[prev] + 1 > E:
        return _SD_FAILS["lastday"]
    te = t if t < E else E
    return (True, val - P.lam * (te - t0) - sw, t, pw, pf, pa, kp, npk, fin)


def _sd_obj(P):
    ov = P.load - P.cap_lim
    return sum(P.rsc) - (P.cap_w * ov if ov > 0 else 0.0)


def _sd_commit(P, u, r, ev):
    """install route r (evaluated as ev) for unit u; keeps the counters consistent."""
    old = P.routes[u]
    for j in old:
        P.where[j] = -1
        P.load -= P.net[j]
        c = P.cropi[j]
        if c is not None and P.real[j]:
            P.seed_used[c] -= 1
        if j in P.ft:
            del P.ft[j]
    for j in r:
        P.where[j] = u
        P.load += P.net[j]
        c = P.cropi[j]
        if c is not None and P.real[j]:
            P.seed_used[c] += 1
    P.routes[u] = list(r)
    P.rsc[u] = ev[1]
    P.rend[u] = ev[2]
    P.tpw += ev[3] - P.rpw[u]
    P.tpf += ev[4] - P.rpf[u]
    ra = P.rpa[u]
    P.tpa = [P.tpa[i] + ev[5][i] - ra[i] for i in range(3)]
    P.rpw[u], P.rpf[u], P.rpa[u] = ev[3], ev[4], ev[5]
    P.rkp[u] = (ev[6], ev[7])
    P.rfin[u] = ev[8]
    if ev[8]:
        P.ft.update(ev[8])


def _sd_fix_pairs(P, us):
    """after routes us changed: a successor whose predecessor moved / vanished is re-timed (dropped if it no longer
    fits). sd_coop_pair: chains (a re-timed route holding another route's predecessor) propagate until nothing moves."""
    work = list(us)
    chain = bool(CFG["sd_coop_pair"])
    guard = 4 * P.U + 8
    while work:
        u = work.pop(0)
        for j in P.routes[u]:
            s = P.succ[j]
            if s < 0:
                continue
            v = P.where[s]
            if v < 0 or v == u:
                continue
            old = (P.rsc[v], P.rend[v], tuple(P.ft.get(x) for x in P.routes[v])) if chain else None
            ev = _sd_eval(P, v, P.routes[v])
            if not ev[0]:
                r2 = [x for x in P.routes[v] if x != s]
                ev = _sd_eval(P, v, r2)
                if ev[0]:
                    _sd_commit(P, v, r2, ev)
            else:
                _sd_commit(P, v, P.routes[v], ev)
            if chain and guard > 0 and v not in work and old != (P.rsc[v], P.rend[v],
                                                                 tuple(P.ft.get(x) for x in P.routes[v])):
                work.append(v)
                guard -= 1
    for j in range(P.J):                          # successors of predecessors no longer planned
        pr = P.jb[j][11]
        if pr >= 0 and P.where[j] >= 0 and P.where[pr] < 0:
            v = P.where[j]
            r2 = [x for x in P.routes[v] if x != j]
            ev = _sd_eval(P, v, r2)
            if ev[0]:
                _sd_commit(P, v, r2, ev)


def _sd_seed_ok(P, j):
    c = P.cropi[j]
    return c is None or not P.real[j] or P.seed_used[c] < P.seeds.get(c, 0)


def _sd_load_delta(P, dnet):
    a = P.load - P.cap_lim
    b = P.load + dnet - P.cap_lim
    return -P.cap_w * ((b if b > 0 else 0.0) - (a if a > 0 else 0.0))


def _sd_cands(P, j):
    """candidate units for job j: the nearest routes / units (sd_k_units) + the two nearest idle units."""
    D = P.d
    if P.hard[j] and CFG["sd_hard_all"]:
        return [u for u in range(P.U) if P.ue[u] >= 0]    # v2: every unit may take a survival job
    b = P.jb[j][0]
    near, idle = [], []
    for u in range(P.U):
        if P.ue[u] < 0:
            continue
        r = P.routes[u]
        dm = D[b][P.up[u]]
        for x in r:
            dx = D[b][P.jb[x][0]]
            if dx < dm:
                dm = dx
        (near if r else idle).append((dm, u))
    near.sort()
    idle.sort()
    return [u for _, u in near[:CFG["sd_k_units"]]] + [u for _, u in idle[:2]]


def _sd_best_ins(P, j, units, skip_u=-1):
    """best and second-best (over units) insertion of job j: (d1, u1, k1, ev1, d2) or None."""
    if not _sd_seed_ok(P, j):
        return None
    ld = _sd_load_delta(P, P.net[j])
    best = {}
    for u in units:
        if u == skip_u:
            continue
        r = P.routes[u]
        base = P.rsc[u]
        bu = None
        for k in range(len(r) + 1):
            nr = r[:k] + [j] + r[k:]
            ev = _sd_eval(P, u, nr)
            if not ev[0]:
                continue
            d = ev[1] - base + ld
            if bu is None or d > bu[0]:
                bu = (d, u, k, ev)
        if bu is not None:
            best[u] = bu
    if not best:
        return None
    vals = sorted(best.values(), key=lambda x: -x[0])
    d2 = vals[1][0] if len(vals) > 1 else None
    d1, u1, k1, ev1 = vals[0]
    return (d1, u1, k1, ev1, d2)


def _sd_insert_many(P, pool, rng=None, noise=0.0, deadline=None):
    """regret-2 insertion of the jobs in pool (hard jobs first); jobs that fit nowhere with a positive gain stay
    unplanned. Returns the number inserted."""
    pool = [j for j in pool if P.where[j] < 0]
    if not pool:
        return 0
    cu = {j: _sd_cands(P, j) for j in pool}
    best = {j: _sd_best_ins(P, j, cu[j]) for j in pool}
    done = 0
    guard = 4 * len(pool) + 8
    while best and guard > 0:
        guard -= 1
        if deadline is not None and time.perf_counter() > deadline:
            break
        sel = None
        for j, b in best.items():
            if b is None or b[0] <= 1e-6:
                continue
            reg = 1e9 if b[4] is None else b[0] - b[4]
            if noise and rng is not None:
                reg += noise * rng.random()
            key = (P.hard[j], reg, b[0], -j)
            if sel is None or key > sel[0]:
                sel = (key, j)
        if sel is None:
            break
        j = sel[1]
        d1, u, k, ev, _ = best.pop(j)
        r = P.routes[u]
        nr = r[:k] + [j] + r[k:]
        ev = _sd_eval(P, u, nr)                   # reservations may have moved since it was scored
        if not ev[0] or not _sd_seed_ok(P, j):
            b = _sd_best_ins(P, j, cu[j])
            if b is not None:
                best[j] = b
            continue
        _sd_commit(P, u, nr, ev)
        if P.jb[j][13] or P.jb[j][11] >= 0 or (CFG["sd_coop_pair"] and P.rfin[u]):   # sd_coop_pair: a shifted predecessor too
            _sd_fix_pairs(P, [u])
        done += 1
        for j2 in list(best):
            if u in cu[j2] or best[j2] is None:
                best[j2] = _sd_best_ins(P, j2, cu[j2])
    return done


def _sd_repair(P, u, r):
    """drop jobs from r until the route is feasible (the removal that leaves the best score, non-hard first)."""
    r = list(r)
    ev = _sd_eval(P, u, r)
    while not ev[0] and r:
        best = None
        for i in range(len(r)):
            r2 = r[:i] + r[i + 1:]
            e2 = _sd_eval(P, u, r2)
            if not e2[0]:
                continue
            key = (not P.hard[r[i]], e2[1])
            if best is None or key > best[0]:
                best = (key, i, e2)
        if best is None:
            r = r[:-1]                             # nothing single fixes it: shorten from the end
            ev = _sd_eval(P, u, r)
        else:
            r = r[:best[1]] + r[best[1] + 1:]
            ev = best[2]
    return r, ev


def _sd_construct(P):
    """initial plan by an event simulation of the executor's greedy (each free unit takes the cheapest reachable job:
    travel with a shed detour when it lacks items, +10 for low-value jobs after late_hour)."""
    import heapq
    D, SD = P.d, P.sd
    JB = P.jb
    heap = [(P.ut0[u], u) for u in range(P.U) if P.ue[u] > 0]
    heapq.heapify(heap)
    upos = list(P.up)
    cw, cf = list(P.uw), list(P.uf)
    left = set(j for j in range(P.J) if JB[j][11] < 0)
    seq = [[] for _ in range(P.U)]
    seeds = Counter()
    late = CFG["late_hour"]
    p1 = float(CFG["p1_min_value"])
    while heap and left:
        t, u = heapq.heappop(heap)
        if t >= P.ue[u]:
            continue
        p = upos[u]
        best = None
        for j in left:
            jb = JB[j]
            b = jb[0]
            lack = jb[2] > cw[u] or jb[3] > cf[u] or jb[4] >= 0
            trav = (SD[p][b] + 1) if lack else D[p][b]
            st = max(t + trav, jb[9])
            if st + jb[1] > P.ue[u] or (jb[10] >= 0 and st + jb[10] > jb[8][jb[10]]):
                continue
            c = trav + (10 if (t >= late and P.vraw[j] <= p1) else 0) - min(4000.0, P.vraw[j]) * 1e-4
            if best is None or c < best[0]:
                best = (c, j, st)
        if best is None:
            continue
        _, j, st = best
        jb = JB[j]
        c = P.cropi[j]
        if c is not None and P.real[j]:
            if seeds[c] >= P.seeds.get(c, 0):
                left.discard(j)
                heapq.heappush(heap, (t, u))
                continue
            seeds[c] += 1
        left.discard(j)
        seq[u].append(j)
        if jb[2] > cw[u] or jb[3] > cf[u]:
            cw[u] = max(cw[u], jb[2])
            cf[u] = max(cf[u], jb[3])
        cw[u] = cw[u] - jb[2] + jb[5]
        cf[u] = cf[u] - jb[3] + jb[6]
        upos[u] = jb[0]
        s = P.succ[j]
        if s >= 0:
            left.add(s)
        heapq.heappush(heap, (st + jb[1], u))
    for u in range(P.U):
        if seq[u]:
            r, ev = _sd_repair(P, u, seq[u])
            _sd_commit(P, u, r, ev)
    _sd_fix_pairs(P, range(P.U))


def _sd_intra(P, u, deadline, ev_end):
    """2-opt and or-opt (segments of 1-3) on route u until no improvement."""
    improved = True
    any_imp = False
    while improved:
        improved = False
        r = P.routes[u]
        L_ = len(r)
        if L_ < 2:
            return any_imp
        base = P.rsc[u]
        best = None
        for i in range(L_ - 1):                    # 2-opt: reverse r[i..k]
            for k in range(i + 1, L_):
                nr = r[:i] + r[i:k + 1][::-1] + r[k + 1:]
                ev = _sd_eval(P, u, nr)
                if ev[0] and ev[1] > base + 1e-6 and (best is None or ev[1] > best[1][1]):
                    best = (nr, ev)
        for sl in (1, 2, 3):                       # or-opt: move a segment
            for i in range(L_ - sl + 1):
                seg = r[i:i + sl]
                rest = r[:i] + r[i + sl:]
                for k in range(len(rest) + 1):
                    if k == i:
                        continue
                    nr = rest[:k] + seg + rest[k:]
                    ev = _sd_eval(P, u, nr)
                    if ev[0] and ev[1] > base + 1e-6 and (best is None or ev[1] > best[1][1]):
                        best = (nr, ev)
        if best is not None:
            _sd_commit(P, u, best[0], best[1])
            if P.rfin[u] or any(P.jb[j][11] >= 0 for j in best[0]):
                _sd_fix_pairs(P, [u])
            improved = any_imp = True
        if time.perf_counter() > deadline or P.nev >= ev_end:
            break
    return any_imp


def _sd_relocate(P, j):
    """move job j to its best position anywhere (its own route included); True when the objective improved."""
    u = P.where[j]
    if u < 0:
        return False
    r = P.routes[u]
    i = r.index(j)
    r0 = r[:i] + r[i + 1:]
    ev0 = _sd_eval(P, u, r0)
    if not ev0[0]:
        return False
    gain0 = ev0[1] - P.rsc[u]
    best = None
    cands = _sd_cands(P, j)
    if u not in cands:
        cands.append(u)
    for v in cands:
        rv = r0 if v == u else P.routes[v]
        base = ev0[1] if v == u else P.rsc[v]
        for k in range(len(rv) + 1):
            if v == u and k == i:
                continue
            nr = rv[:k] + [j] + rv[k:]
            ev = _sd_eval(P, v, nr)
            if not ev[0]:
                continue
            d = (ev[1] - P.rsc[u]) if v == u else (gain0 + ev[1] - base)
            if d > 1e-6 and (best is None or d > best[0]):
                best = (d, v, nr, ev)
    if best is None:
        return False
    d, v, nr, ev = best
    if v == u:
        _sd_commit(P, u, nr, ev)
    else:
        _sd_commit(P, u, r0, ev0)                 # re-check the target against the reservations after the move
        ev = _sd_eval(P, v, nr)
        if not ev[0]:
            r1 = r0[:i] + [j] + r0[i:]
            ev1 = _sd_eval(P, u, r1)
            if ev1[0]:
                _sd_commit(P, u, r1, ev1)
            return False
        _sd_commit(P, v, nr, ev)
    if P.jb[j][13] or P.jb[j][11] >= 0 or P.rfin[u] or (v != u and P.rfin[v]):
        _sd_fix_pairs(P, [u, v])
    return True


def _sd_snap(P):
    return ([list(r) for r in P.routes], list(P.rsc), list(P.rend), list(P.rpw), list(P.rpf), list(P.rpa),
            list(P.rkp), list(P.rfin), list(P.where), dict(P.ft), P.tpw, P.tpf, list(P.tpa), Counter(P.seed_used),
            P.load)


def _sd_restore(P, s):
    (P.routes, P.rsc, P.rend, P.rpw, P.rpf, P.rpa, P.rkp, P.rfin, P.where, P.ft, P.tpw, P.tpf, P.tpa, P.seed_used,
     P.load) = ([list(r) for r in s[0]], list(s[1]), list(s[2]), list(s[3]), list(s[4]), list(s[5]), list(s[6]),
                list(s[7]), list(s[8]), dict(s[9]), s[10], s[11], list(s[12]), Counter(s[13]), s[14])


def _sd_rr(P, rng, deadline):
    """ruin (a seed job and its nearest planned jobs) and recreate (regret insertion with noise, the nearby
    unplanned jobs included); kept only when the objective improves."""
    planned = [j for j in range(P.J) if P.where[j] >= 0]
    if not planned:
        return False
    D = P.d
    seed = rng.choice(planned)
    b0 = P.jb[seed][0]
    m = rng.randint(2, max(2, CFG["sd_rr_max"]))
    near = sorted(planned, key=lambda j: (D[b0][P.jb[j][0]], rng.random()))[:m]
    snap = _sd_snap(P)
    obj0 = _sd_obj(P)
    touched = set(P.where[j] for j in near)
    rm = set(near)
    for u in touched:
        r2 = [x for x in P.routes[u] if x not in rm]
        ev = _sd_eval(P, u, r2)
        if not ev[0]:
            _sd_restore(P, snap)
            return False
        _sd_commit(P, u, r2, ev)
    _sd_fix_pairs(P, touched)
    pool = list(near) + [j for j in range(P.J) if P.where[j] < 0 and j not in rm
                         and (P.hard[j] or D[b0][P.jb[j][0]] <= 3)]
    _sd_insert_many(P, pool, rng, CFG["sd_rr_noise"], deadline)
    if _sd_obj(P) > obj0 + 1e-6:
        return True
    _sd_restore(P, snap)
    return False


def _sd_force_hard(P, deadline):
    """v2: each hard job still unplanned goes where the route stays feasible after dropping the non-hard jobs whose
    removal costs least (the nearest six units, every position); the dropped jobs are re-inserted where they fit.
    Returns the number of hard jobs placed."""
    D = P.d
    placed = 0
    for j in [j for j in range(P.J) if P.where[j] < 0 and P.hard[j]]:
        if time.perf_counter() > deadline or not _sd_seed_ok(P, j) or P.where[j] >= 0:
            continue
        b = P.jb[j][0]

        def dist(u):
            dm = D[b][P.up[u]]
            for x in P.routes[u]:
                if D[b][P.jb[x][0]] < dm:
                    dm = D[b][P.jb[x][0]]
            return dm
        units = sorted((u for u in range(P.U) if P.ue[u] >= 0), key=lambda u: (dist(u), u))[:6]
        best = None
        for u in units:
            r0 = P.routes[u]
            for k in range(len(r0) + 1):
                nr = r0[:k] + [j] + r0[k:]
                ev = _sd_eval(P, u, nr)
                rm = []
                while not ev[0]:
                    cand = None
                    for i, x in enumerate(nr):
                        if x == j or P.hard[x]:
                            continue
                        r2 = nr[:i] + nr[i + 1:]
                        e2 = _sd_eval(P, u, r2)
                        sc = e2[1] if e2[0] else -1e18
                        if cand is None or sc > cand[0]:
                            cand = (sc, i, e2)
                    if cand is None:
                        break
                    rm.append(nr[cand[1]])
                    nr = nr[:cand[1]] + nr[cand[1] + 1:]
                    ev = cand[2]
                if not ev[0]:
                    continue
                d = ev[1] - P.rsc[u]
                if best is None or d > best[0]:
                    best = (d, u, nr, ev, rm)
            if time.perf_counter() > deadline:
                break
        if best is None:
            continue
        d, u, nr, ev, rm = best
        _sd_commit(P, u, nr, ev)
        _sd_fix_pairs(P, [u])
        placed += 1
        if rm:
            _sd_insert_many(P, rm, None, 0.0, deadline)
    return placed


def _sd_seed_repair(P):
    """sd_seed_fix: the warm start re-adds the previous step's planting jobs without a seed check (seeds used or not
    bought since): drop the latest-placed real planting of an over-committed crop until the plan fits the seeds held."""
    for c in list(P.seed_used):
        over = P.seed_used[c] - P.seeds.get(c, 0)
        while over > 0:
            best = None
            for u in range(P.U):
                for i, j in enumerate(P.routes[u]):
                    if P.cropi[j] == c and P.real[j] and (best is None or (i, u) > (best[1], best[0])):
                        best = (u, i)
            if best is None:
                break
            u, i = best
            r2 = P.routes[u][:i] + P.routes[u][i + 1:]
            ev = _sd_eval(P, u, r2)
            if not ev[0]:
                r2, ev = _sd_repair(P, u, r2)
            _sd_commit(P, u, r2, ev)
            over -= 1
    _sd_fix_pairs(P, range(P.U))


def _sd_search(P, rng, t_end, evals_max):
    """improve the plan inside the budget; returns (iterations, rr tried, rr accepted, time capped)."""
    ev_end = P.nev + evals_max
    unpl = [j for j in range(P.J) if P.where[j] < 0]
    _sd_insert_many(P, unpl, None, 0.0, t_end)
    P.forced = 0
    if CFG["sd_hard_eject"] and any(P.hard[j] and P.where[j] < 0 for j in range(P.J)):
        P.forced = _sd_force_hard(P, t_end)
    capped = False
    it = rr_t = rr_a = 0
    for u in range(P.U):
        if P.routes[u] and P.nev < ev_end:
            _sd_intra(P, u, t_end, ev_end)
    while True:
        if time.perf_counter() > t_end:
            capped = True
            break
        if P.nev >= ev_end:
            break
        it += 1
        imp = False
        order = [j for j in range(P.J) if P.where[j] >= 0]
        rng.shuffle(order)
        for j in order:
            if P.nev >= ev_end or time.perf_counter() > t_end:
                break
            if P.where[j] >= 0 and _sd_relocate(P, j):
                imp = True
        for u in range(P.U):
            if P.routes[u] and P.nev < ev_end and _sd_intra(P, u, t_end, ev_end):
                imp = True
        unpl = [j for j in range(P.J) if P.where[j] < 0]
        if unpl and P.nev < ev_end and _sd_insert_many(P, unpl, None, 0.0, t_end):
            imp = True
        if imp:
            continue
        stall = 0                                  # local optimum: ruin and recreate until the budget / a stall
        while P.nev < ev_end and stall < CFG["sd_rr_stall"]:
            if time.perf_counter() > t_end:
                capped = True
                break
            rr_t += 1
            if _sd_rr(P, rng, t_end):
                rr_a += 1
                stall = 0
            else:
                stall += 1
        break
    if time.perf_counter() > t_end:
        capped = True
    return it, rr_t, rr_a, capped


def _sd_step(S, L, ctx):
    """one planning run. Returns None (the greedy acts for everyone) or {P, units, first, claimed}."""
    st = L["st"]
    day, hour, step = ctx["day"], ctx["hour"], ctx["step"]
    if L["day"] != day:
        L["day"] = day
        L["routes"] = {}
        L["walk"] = {}
        L["pred_seen"] = {}
        L["home"] = {}
        L["first_of_day"] = True
        st["days_planned"] += 1
    t_start = time.perf_counter()
    first = L.pop("first_of_day", False) or not L["routes"]
    budget = CFG["sd_budget0"] if first else CFG["sd_budget"]
    evals = CFG["sd_evals0"] if first else CFG["sd_evals"]
    if _SD_T:
        budget = min(budget, CFG["sd_step_cap"] - (time.time() - _SD_T[0]))
    budget = max(0.005, budget)
    t_end = t_start + budget
    try:
        P = _sd_build(S, L, ctx)
        rng = _sd_random.Random(int(CFG["sd_seed"]) * 100003 + step)
        prev = L["routes"]
        if prev:
            for u in range(P.U):
                r = []
                seen = set()
                for k in prev.get(u, ()):
                    j = P.kidx.get(k)
                    if j is None and isinstance(k, tuple):
                        j = P.kidx.get(k[1])                   # a predicted job whose task now exists
                        if j is None:
                            j = P.kidx.get(("P", k[1]))
                    if j is None or j in seen or P.where[j] >= 0:
                        continue
                    pr = P.jb[j][11]
                    if pr >= 0 and pr not in seen and P.where[pr] < 0:
                        continue                   # successor before its predecessor is planned: re-inserted later
                    seen.add(j)
                    r.append(j)
                if r:
                    r, ev = _sd_repair(P, u, r)
                    _sd_commit(P, u, r, ev)
            _sd_fix_pairs(P, range(P.U))
            if CFG["sd_seed_fix"]:
                _sd_seed_repair(P)
        else:
            _sd_construct(P)
        P.obj_start = _sd_obj(P)
        it, rr_t, rr_a, capped = _sd_search(P, rng, t_end, evals)
        L["routes"] = {u: [P.key[j] for j in P.routes[u]] for u in range(P.U) if P.routes[u]}
    except Exception as exc:
        st["errors"] += 1
        st["fb_step"] += 1
        st["last_error"] = ("%s: %s" % (type(exc).__name__, exc))[:300]
        try:
            S["log"]["sd_err:step:" + st["last_error"][:100]] += 1      # the text survives in agent_log
        except Exception:
            pass
        L["routes"] = {}
        return None
    ms = 1000.0 * (time.perf_counter() - t_start)
    st["steps"] += 1
    st["plan_ms"].append(round(ms, 2))
    if first:
        st["plan_ms_first"].append(round(ms, 2))
    st["evals"] += P.nev
    st["time_capped"] += 1 if capped else 0
    st["rr_tried"] += rr_t
    st["rr_acc"] += rr_a
    st["forced_hard"] += getattr(P, "forced", 0)
    unpl = [j for j in range(P.J) if P.where[j] < 0 and P.real[j]]
    unv = sum(P.vraw[j] for j in unpl)
    if hour == 1 or (first and hour > 1):
        st["planned_drop_first"] += len(unpl)
        st["planned_drop_first_value"] += unv
    st["planned_hard_unplanned"] += sum(1 for j in unpl if P.hard[j])
    if hour == 23:
        st["load_proj_h23"].append(round(P.load, 1))
    if CFG["sd_log"]:
        L["recs"].append({"s": step, "ms": round(ms, 1), "J": P.J, "U": P.U, "un": len(unpl), "unv": round(unv, 1),
                          "unh": sum(1 for j in unpl if P.hard[j]), "ev": P.nev, "it": it, "rr": [rr_t, rr_a],
                          "cap": int(capped), "load": round(P.load, 1), "obj0": round(P.obj_start, 1),
                          "obj": round(_sd_obj(P), 1),
                          "busy": sum(max(0, P.rend[u] - P.ut0[u]) for u in range(P.U) if P.routes[u])})
    if CFG["sd_keep"]:
        L["lastP"] = P
    if CFG["sd_plan_log"]:                         # viewer: each hand's planned job tiles (route order), on every change
        snap = {str(u): [int(P.jb[j][0]) for j in P.routes[u]] for u in range(P.n_real)}
        if snap != L.get("plan_last"):
            L.setdefault("plan_log", {})[str(step)] = snap
            L["plan_last"] = snap
    first_job, claimed = {}, set()
    for u in range(P.n_real):
        fk = None
        for j in P.routes[u]:
            if P.real[j]:
                claimed.add(P.jb[j][0])
                if fk is None:
                    fk = P.jb[j][0]
        if fk is not None:
            first_job[u] = fk
    ctrl = set(u for u in range(P.n_real) if P.uctrl[u])
    return {"P": P, "ctrl": ctrl, "first": first_job, "claimed": claimed}


def _sd_hire_plan(S, L, ctx):
    """hour 0: the day's hire count (sd_hire_demand) and the spawn steering (sd_spawn_steer); L["hire"]."""
    day, hour, pos = ctx["day"], ctx["hour"], ctx["pos"]
    st = L["st"]
    L.setdefault("hire_extra0", CFG["hire_extra"])
    CFG["hire_extra"] = L["hire_extra0"]           # the executor's own count this morning
    if L["day"] != day:                            # the day's first step: no stale walks / predicted jobs in the tries
        L["walk"] = {}
        L["pred_seen"] = {}
    want = _sd_want_hands(day)
    ks = list(range(max(1, want - 6), want + 1)) if CFG["sd_hire_demand"] else [want]
    rng = _sd_random.Random(int(CFG["sd_seed"]) * 7919 + day)
    best, plans = None, {}
    cap = 10                                       # the engine executes 10 market orders a step: hires beyond wait for hour 1
    for k in ks:
        vu = [(q, 1) for q in _sd_spawn(pos, min(k, cap))] + [(q, 2) for q in _sd_spawn([], k - min(k, cap))]
        P = _sd_build(S, L, dict(ctx, vunits=vu))
        _sd_construct(P)
        _sd_search(P, rng, time.perf_counter() + 10.0, int(CFG["sd_hire_evals"]))
        net = _sd_obj(P) - sum(_fib(i) for i in range(k))
        plans[k] = P
        if best is None or net > best[0] + 1e-6:
            best = (net, k)
    k = best[1]
    st["hire_k"] = st.get("hire_k", 0) + k
    st["hire_want"] = st.get("hire_want", 0) + want
    F, k0 = tuple(pos[0]), min(k, cap)
    vunits = [(q, 1) for q in _sd_spawn(pos, k0)] + [(q, 2) for q in _sd_spawn([], k - k0)]
    if CFG["sd_spawn_steer"]:
        P = plans[k]
        W = [0.0] * 4
        for j in range(P.J):
            if P.real[j]:
                W[_sd_qi(P.jb[j][0])] += P.jb[j][1]
        tot = sum(W) or 1.0
        tgt = [(k + 1) * W[q] / tot for q in range(4)]
        tgt[0] -= 1.0                              # the farmer works the second quadrant (NW)
        f0 = tuple(pos[0])
        opts = [(f0, 0.0)] + [((f0[0] + dx, f0[1] + dy), 0.1) for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1))]
        cand = None
        for Fp, fc in opts:
            if not (0 <= Fp[0] < 10 and 0 <= Fp[1] < 10):
                continue
            for k0_ in range(min(k, cap), max(-1, min(k, cap) - 5), -1):
                sp0 = _sd_spawn([Fp], k0_)
                sp1 = _sd_spawn([], k - k0_)       # at hour 1 the hour-0 units have left the shed tiles
                cnt = [0] * 4
                for q in sp0 + sp1:
                    cnt[_sd_qi(q[1] * 10 + q[0])] += 1
                sc = sum(abs(cnt[q] - tgt[q]) for q in range(4)) + 0.25 * (k - k0_) + fc
                key = (round(sc, 6), -k0_)
                if cand is None or key < cand[0]:
                    cand = (key, Fp, k0_, [(q, 1) for q in sp0] + [(q, 2) for q in sp1], cnt)
        _, F, k0, vunits, cnt = cand
        st["steer_moves"] = st.get("steer_moves", 0) + (1 if F != f0 else 0)
        st["steer_h1"] = st.get("steer_h1", 0) + (k - k0)
    L["hire"] = {"day": day, "k": int(k), "k0": int(k0), "F": F, "vunits": vunits}


def _sd_pre(S, obs, me, step, day, hour, last_day, tiles, pos, invs, tasks, jobs, shed, seeds, prices, assign, taken,
            surv_route, deliv_u, fert_keep, demand, prev):
    """HOOK 1 (after the delivery rule and the survival routes, before the greedy matching): plan; in active mode the
    planned units get their first planned tile as their assignment (the greedy matching skips them) and leave the
    greedy's survival routes; the greedy keeps the units without a route. A delivery the executor's rule starts THIS
    step for a planned unit standing on its current planned tile waits until the tile is done (the routes check the
    trigger after each job; a mid-tile delivery abandoned a seedling between PLANT and WATER)."""
    L = _sd_state(S)
    run = {"active": False, "units": set(), "P": None, "first": {}, "claimed": set(), "acted": set(), "jobs": jobs}
    try:
        _sd_watch(L, tiles, day, hour)
    except Exception as exc:
        L["st"]["errors"] += 1
        L["st"]["last_error"] = ("watch %s: %s" % (type(exc).__name__, exc))[:300]
        try:
            S["log"]["sd_err:" + L["st"]["last_error"][:100]] += 1
        except Exception:
            pass
    if CFG["sd_water_first"]:
        for idx, (ops_, need_, prio_) in list(tasks.items()):
            if ops_ and ops_[0][0] == "HARVEST" and not any(o[0] == "WATER" for o in ops_):
                t_ = _tile(tiles, idx)
                if _is_plant(t_) and not t_.get("watered_today"):
                    c_ = CROPS.get(t_.get("crop"))
                    if c_ and not c_["ongoing"]:
                        a_ = day - int(t_.get("planted_day", day))
                        if (c_["maxday"] + 1) // 2 <= a_ <= c_["maxday"] and int(t_.get("yield_units", 0) or 0) < c_["max"]:
                            tasks[idx] = ([["WATER"]] + [list(o) for o in ops_], need_, prio_)
                            L["st"]["water_first"] = L["st"].get("water_first", 0) + 1
    win = CFG["sd_days"]
    if L["off"] or (win is not None and not (int(win[0]) <= day <= int(win[1]))):
        return run
    if CFG["dispatch_search"] == "active" and CFG["sd_finish_tile"] and L["day"] == day:
        for u in [u for u, v in assign.items() if v == "D" and prev.get(u) != "D" and u < len(pos)]:
            p = tuple(pos[u])
            idx = p[1] * 10 + p[0]
            r = L["routes"].get(u)
            k0 = (r[0] if isinstance(r[0], int) else r[0][1]) if r else None
            if idx in tasks and k0 == idx and day < last_day:
                assign.pop(u, None)
                L["st"]["deliv_deferred"] += 1
    keep, stiles = set(), set()
    if CFG["sd_surv_fb"] is not None and hour >= int(CFG["sd_surv_fb"]) and surv_route:
        keep = set(surv_route)
        stiles = set(i_ for r_ in surv_route.values() for i_, o_ in r_)
        L["st"]["surv_fb_units"] += len(keep)
    ctx = {"keep": keep, "stiles": stiles, "obs": obs, "day": day, "hour": hour, "step": step, "tiles": tiles, "tasks": tasks, "invs": invs, "pos": pos,
           "shed": shed, "seeds": seeds, "assign": assign, "last_day": last_day, "jobs": jobs, "prices": prices,
           "deliv_u": deliv_u, "fert_keep": fert_keep, "demand": demand}
    if (hour == 0 and len(pos) == 1 and day < last_day and CFG["dispatch_search"] == "active"
            and (CFG["sd_hire_demand"] or CFG["sd_spawn_steer"])):
        try:
            _sd_hire_plan(S, L, ctx)
        except Exception as exc:
            L["st"]["errors"] += 1
            L["st"]["last_error"] = ("hire %s: %s" % (type(exc).__name__, exc))[:300]
            L.pop("hire", None)
    hp = L.get("hire")
    if hp and hp.get("day") == day and hour == 0:
        ctx["vunits"] = hp["vunits"]
    r = _sd_step(S, L, ctx)
    if r is None:
        return run
    run.update(P=r["P"], first=r["first"], claimed=r["claimed"])
    if CFG["dispatch_search"] != "active":
        return run
    P = r["P"]
    run["active"] = True
    idle_pass = CFG["sd_idle"] == "pass"
    for u in r["ctrl"]:
        if not P.routes[u]:
            if idle_pass and u not in surv_route:
                run["units"].add(u)                # planned idle (delivers what it carries, else waits)
            continue                               # no route but a greedy survival route: the greedy keeps it
        run["units"].add(u)
        surv_route.pop(u, None)
        fk = r["first"].get(u)
        if fk is not None and fk in tasks:
            assign[u] = fk
        elif u in assign and assign[u] != "D":
            assign.pop(u, None)
    taken.clear()
    taken.update(v for v in assign.values() if v != "D")
    taken.update(k for k in r["claimed"] if k in tasks)
    return run


def _sd_act(S, run, u, p, inv, tasks, tiles, shed_left, seeds_left, plant_count, carried, hour, usable_ops, deliv_u):
    """HOOK 2: next command of planned unit u, or None (the greedy code decides this unit's step)."""
    P = run["P"]
    L = S["sd"]
    st = L["st"]
    walk = L["walk"]
    pi = p[1] * 10 + p[0]
    r = P.routes[u]
    if CFG["sd_coop_pair"]:                        # never an empty structure: standing on one with its animal, place it
        t_ = _tile(tiles, pi)
        if isinstance(t_, dict) and t_.get("kind") in ("COOP", "PASTURE") and "animal" not in t_:
            for sp_ in _SD_SP:
                if ANIMALS[sp_]["structure"] == t_["kind"] and inv.get(sp_, 0) > 0:
                    st["pair_place_now"] = st.get("pair_place_now", 0) + 1
                    st["planned_unit"] += 1
                    run["acted"].add(u)
                    return ["PLACE", sp_]
    if not r:
        st["idle_unit"] += 1
        w = walk.get(u)
        if w and w[1]:
            st["switch_steps"] += w[1]
        walk[u] = (None, 0)
        dv = deliv_u(u)
        if CFG["sd_idle_fert"] and inv.get("FERTILIZER", 0) > 0 and "FERTILIZER" not in dv:
            dv = dict(dv)
            dv["FERTILIZER"] = int(inv["FERTILIZER"])   # an idle unit has no fertilize job left: its fertilizer to the shed
        if dv and hour < 23:
            st["idle_deliver"] += 1
            s = _near_shed(p)
            if p != s:
                return _step_toward(p, s)
            if all(k in dv for k in inv):
                return ["DROP"]
            k = sorted(dv)[0]
            return ["PLACE", k, int(inv[k])]
        return ["PASS"]
    j0 = r[0]
    b0 = P.jb[j0][0]
    key0 = P.key[j0]
    w = walk.get(u, (None, 0))
    if w[0] is not None and w[0] != key0 and w[1]:
        st["switch_steps"] += w[1]
    kp, npk = P.rkp[u]
    if kp == 0 and npk:
        s = P.sa[pi][b0]
        if pi != s:
            walk[u] = (None, 0)
            st["planned_unit"] += 1
            return _step_toward(p, (s % 10, s // 10))
        if CFG["sd_hs_drop"] and CFG["hand_stock"] and hour >= CFG["hs_drop_hour"] and P.rpw[u] == 0:
            sur = inv.get("WHEAT", 0) - sum(P.jb[j][2] for j in r) - CFG["hs_buffer"]
            if sur > 0:
                S["log"]["hs_drop"] += int(sur)
                st["planned_unit"] += 1
                return ["PLACE", "WHEAT", int(sur)]
        pa = P.rpa[u]
        for item, amt in (("WHEAT", P.rpw[u]), ("FERTILIZER", P.rpf[u]), ("GOOSE", pa[0]), ("COW", pa[1]),
                          ("SHEEP", pa[2])):
            if amt > 0:
                a = min(int(amt), int(shed_left.get(item, 0)))
                if a > 0:
                    shed_left[item] -= a
                    carried[item] += a
                    walk[u] = (None, 0)
                    st["planned_unit"] += 1
                    return ["PICKUP", item, a]
        st["fb_unit"] += 1
        st["fb_pickup"] += 1
        return None
    if pi != b0:
        walk[u] = (key0, (w[1] + 1) if w[0] == key0 else 1)
        st["planned_unit"] += 1
        return _step_toward(p, (b0 % 10, b0 // 10))
    walk[u] = (None, 0)
    if not P.real[j0]:
        st["pred_wait"] += 1
        st["planned_unit"] += 1
        return ["PASS"]                            # predicted job: wait on the tile for its task
    if isinstance(key0, tuple) and key0[0] == "W" and b0 not in tasks:   # sd_water_tomorrow: a planner-only water
        t = _tile(tiles, b0)
        if _is_plant(t) and not t.get("watered_today"):
            st["planned_unit"] += 1
            st["water_tomorrow"] = st.get("water_tomorrow", 0) + 1
            run["acted"].add(u)
            return ["WATER"]
    if isinstance(key0, tuple) and key0[0] == "H" and b0 not in tasks:   # v3: an offered melon harvest
        t = _tile(tiles, b0)
        if _is_plant(t) and int(t.get("yield_units", 0) or 0) > 0:
            st["planned_unit"] += 1
            st["offered_harvest"] += 1
            run["acted"].add(u)
            return ["HARVEST"]
    if b0 not in tasks:
        st["fb_unit"] += 1
        st["fb_notask"] += 1
        return None
    ops, need, prio = tasks[b0]
    t = _tile(tiles, b0)
    act = None
    for op in usable_ops(u, ops, need):
        c = op[0]
        if c == "FEED" and inv.get("WHEAT", 0) <= 0:
            continue
        if c == "CARE" and isinstance(t, dict) and not t.get("fed_today") and any(o[0] == "FEED" for o in ops):
            continue
        if c == "FERTILIZE" and inv.get("FERTILIZER", 0) <= 0:
            continue
        if c == "PLACE" and inv.get(op[1], 0) <= 0:
            break
        if c in ("BUILD_COOP", "BUILD_PASTURE") and (CFG["sd_bundle_build"] or CFG["sd_coop_pair"]):
            sp_ = next((o[1] for o in ops if o[0] == "PLACE" and len(o) > 1), None)
            if sp_ and inv.get(sp_, 0) <= 0:       # never an empty structure: fetch the animal first (or wait)
                if shed_left.get(sp_, 0) > 0:
                    st["fb_unit"] += 1
                    st["fb_pickup"] += 1
                    return None
                st["planned_unit"] += 1
                return ["PASS"]
        if c == "PLANT":
            if seeds_left.get(op[1], 0) <= 0 or hour >= 23:
                break
            seeds_left[op[1]] -= 1
            plant_count[op[1]] += 1
        act = op
        break
    if act is None:
        st["fb_unit"] += 1
        st["fb_noop"] += 1
        return None
    st["planned_unit"] += 1
    run["acted"].add(u)
    return list(act)


def _sd_watch(L, tiles, day, hour):
    """plants that turned into weeds (dried out or decayed) and animals gone since the previous step."""
    st = L["st"]
    cur, thirst = [], set()
    for idx in range(100):
        t = _tile(tiles, idx)
        if _is_plant(t):
            cur.append("P")
            if not t.get("watered_today") and t.get("consecutive_unwatered", 0) >= 1:
                thirst.add(idx)
        elif _animal(t):
            cur.append("A")
        elif _is_weed(t):
            cur.append("W")
        else:
            cur.append(None)
    prev = L.get("prev_kind")
    if prev is not None:
        pth = L.get("prev_thirst") or set()
        w23 = L.get("water23") or set()
        for idx in range(100):
            if prev[idx] == "P" and cur[idx] == "W":
                st["plants_lost"] += 1
                if hour == 0 and idx in pth and idx not in w23:
                    st["plants_lost_thirst"] += 1
            elif prev[idx] == "A" and cur[idx] != "A":
                st["animals_lost"] += 1
    L["prev_kind"] = cur
    L["prev_thirst"] = thirst
    if hour == 0:
        L["water23"] = set()


def _sd_post(S, run, obs, me, step, day, hour, last_day, tiles, pos, tasks, assign, actions):
    """HOOK 3 (after every unit's command, before the market): counters, shadow agreement."""
    L = _sd_state(S)
    st = L["st"]
    try:
        if run.get("P") is not None and not run["active"]:
            for u, k in run["first"].items():      # shadow: plan's next job vs the greedy's assignment
                g = assign.get(u)
                if g is None or g == "D":
                    continue
                st["agree_n"] += 1
                st["agree"] += 1 if g == k else 0
        _sd_track(S, L, obs, me, step, day, hour, last_day, len(pos), pos, actions, tiles)
        hp = L.get("hire")
        if hp and hp.get("day") == day and CFG["dispatch_search"] == "active" and hour <= 12:
            if hour == 0 and tuple(pos[0]) != tuple(hp["F"]) and actions:
                actions[0] = _step_toward(tuple(pos[0]), tuple(hp["F"]))
            CFG["hire_extra"] = int((hp["k0"] if hour == 0 else hp["k"]) - _T.hands[min(day, _T.n - 1)])
        elif "hire_extra0" in L:
            CFG["hire_extra"] = L["hire_extra0"]
        if CFG["sd_coop_pair"] and run.get("active"):
            # the pair job buys its animal from hour 0: a BUILD job's tile still holding its crop has only the clearing
            # task ([WATER,] HARVEST: harvest_before_build, water first), whose need carries no animal
            for idx, job in (run.get("jobs") or {}).items():
                if job and job[0] == "BUILD" and len(job) > 2 and job[2] and idx in tasks:
                    ops_, need_, prio_ = tasks[idx]
                    if ([o[0] for o in ops_] in (["HARVEST"], ["WATER", "HARVEST"]) and need_.get(job[2], 0) <= 0):
                        need_[job[2]] += 1
                        st["pair_buy"] = st.get("pair_buy", 0) + 1
        if CFG["sd_early_animal"] and run.get("active"):
            # a BUILD job with an animal whose tile still holds a harvestable one-time crop has only a HARVEST task
            # (harvest_before_build), so the market would buy the animal only after that harvest: count it now (the
            # market reads the tasks' needs after this hook; nothing else reads them this step)
            for idx, job in (run.get("jobs") or {}).items():
                if job and job[0] == "BUILD" and len(job) > 2 and job[2] and idx in tasks:
                    ops_, need_, prio_ = tasks[idx]
                    if [o[0] for o in ops_] == ["HARVEST"] and need_.get(job[2], 0) <= 0:
                        need_[job[2]] += 1
                        st["early_animal"] = st.get("early_animal", 0) + 1
    except Exception as exc:
        st["errors"] += 1
        st["last_error"] = ("post %s: %s" % (type(exc).__name__, exc))[:300]
        try:
            S["log"]["sd_err:" + st["last_error"][:100]] += 1
        except Exception:
            pass


def _sd_track(S, L, obs, me, step, day, hour, last_day, n, pos, actions, tiles):
    """executed-command counters for the per-game summary (all modes but off)."""
    st = L["st"]
    seq = L["seq"]
    if L.get("seq_day") != day:
        L["seq_day"] = day
        seq.clear()
    if hour == 0:
        st["cash0"].append(round(float(obs["farms"][me]["money"]), 1))
    for u in range(n):
        a = actions[u] if u < len(actions) else ["PASS"]
        c = a[0] if a else "PASS"
        p = tuple(pos[u])
        st["unit_steps"] += 1
        if c in _SD_MOVES:
            kind = "M"
            st["moves"] += 1
            dx, dy = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}[c]
            q = (p[0] + dx, p[1] + dy)
            if 0 <= q[0] < 10 and 0 <= q[1] < 10 and q in SHED and p not in SHED:
                st["shed_arrivals"] += 1
        elif c in ("PICKUP", "DROP") or (c == "PLACE" and p in SHED and not (
                len(a) > 1 and a[1] in ANIMALS and isinstance(_tile(tiles, p[1] * 10 + p[0]), dict)
                and _tile(tiles, p[1] * 10 + p[0]).get("kind") == ANIMALS[a[1]]["structure"])):
            kind = "S"
            st["shed_cmds"] += 1
        elif c == "PASS":
            kind = "P"
            st["passes"] += 1
        else:
            kind = "W"
            st["work"] += 1
            if c == "WATER" and hour == 23:
                L["water23"].add(p[1] * 10 + p[0])
        sq = seq.setdefault(u, [])
        if kind == "S" and (not sq or sq[-1] != "S"):
            st["shed_visits"] += 1
        sq.append(kind)
    if hour == 23 or step >= 718:
        for u, sq in seq.items():
            st["unit_days"] += 1
            last = max((i for i, k in enumerate(sq) if k == "W"), default=-1)
            tail = sq[last + 1:]
            st["walk_after_last"] += tail.count("M")
            nd = run_m = 0                         # moves of a final delivery trip (moves then a shed command) excluded
            for k in tail:
                if k == "M":
                    run_m += 1
                elif k == "S":
                    run_m = 0
                else:
                    nd += run_m
                    run_m = 0
            st["walk_after_last_nodeliv"] += nd + run_m
        seq.clear()
    if hour == 23 and day < last_day:
        # dropped = a fresh maintenance solve's jobs (value > 0) still open after this step's commands, valued by the
        # executor's own module (the idle tracer's definition); production-affecting = units > 0
        done23, gone23 = set(), set()
        for u in range(n):
            a = actions[u] if u < len(actions) else ["PASS"]
            if a and a[0] in ("WATER", "FEED", "CARE", "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER"):
                i23 = pos[u][1] * 10 + pos[u][0]
                done23.add((i23, a[0]))
                t23 = _tile(tiles, i23)
                if a[0] == "HARVEST" and _is_plant(t23) and not CROPS[t23["crop"]]["ongoing"]:
                    gone23.add(i23)                # a one-time crop harvested now: its other jobs are moot
        try:
            jl = _sm()["maintenance_jobs"](obs, me, prices=None, fertilize=_mj_fert(), include_optional=False,
                                          collect=CFG["mj_collect"])
        except Exception:
            jl = []
        for j in jl:
            idx = j["tile"][1] * 10 + j["tile"][0]
            v = float(j.get("value", 0.0))
            if v <= 0 or (idx, j["cmd"]) in done23 or idx in gone23:
                continue
            st["dropped_jobs"] += 1
            st["dropped_value"] += v
            if j.get("units", 0) > 0:
                st["dropped_prod_jobs"] += 1
                st["dropped_prod_value"] += v
                st["dropped_prod_units"] += int(j.get("units", 0))
            if j.get("kind") == "survival":
                st["dropped_hard"] += 1
    if hour == 23 or step >= 718:
        _sd_flush(S, False)


def _sd_summary(S):
    st = S["sd"]["st"]

    def q(xs, f):
        if not xs:
            return 0.0
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(f * (len(xs) - 1) + 0.5))]
    pm, sm, pf = st["plan_ms"], st["step_ms"], st["plan_ms_first"]
    out = {k: v for k, v in st.items() if not isinstance(v, list) and not k.startswith(("mrs_", "mrv_"))}
    for k in PRODUCTS:                             # v3: mean marginal revenue / price and coins (hour-1 plans)
        if st.get("mrn"):
            out["mr_" + k] = round(st.get("mrs_" + k, 0.0) / st["mrn"], 3)
            out["mrc_" + k] = round(st.get("mrv_" + k, 0.0) / st["mrn"], 1)
    out.update(plan_ms_max=max(pm) if pm else 0.0, plan_ms_mean=round(sum(pm) / len(pm), 2) if pm else 0.0,
               plan_ms_p95=q(pm, 0.95), plan_ms_first_max=max(pf) if pf else 0.0,
               plan_ms_first_mean=round(sum(pf) / len(pf), 2) if pf else 0.0,
               step_ms_max=max(sm) if sm else 0.0, step_ms_mean=round(sum(sm) / len(sm), 2) if sm else 0.0,
               step_ms_p95=q(sm, 0.95), moves_per_op=round(st["moves"] / max(1, st["work"]), 4),
               bank_min_remaining=round(60.0 - st["bank_used"], 3),
               load_proj_h23_mean=round(sum(st["load_proj_h23"]) / len(st["load_proj_h23"]), 2)
               if st["load_proj_h23"] else 0.0, mode=CFG["dispatch_search"], days=CFG["sd_days"])
    return out


def _sd_flush(S, final):
    """write the step records (and the game summary at the end) to CFG sd_log; numeric summary -> _MGT_REPORT."""
    import json as _json
    import os as _os
    L = S["sd"]
    if final and not L["final_done"]:
        L["final_done"] = True
        summ = _sd_summary(S)
        num = {"sd_" + k: v for k, v in summ.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        try:
            for k, v in num.items():               # lead_g1 / lead_sem4 keep S["log"] as agent_log (diagnostics only)
                S["log"][k] = v
        except Exception:
            pass
        try:
            _MGT_REPORT.update(num)                # the deploy: ladder_panel's "router" record
        except Exception:
            pass
        L["recs"].append({"summary": summ, "cash0": list(S["sd"]["st"]["cash0"])})
    if not CFG["sd_log"]:
        del L["recs"][:]
        return
    try:
        if L["path"] is None:
            _os.makedirs(CFG["sd_log"], exist_ok=True)
            L["path"] = _os.path.join(CFG["sd_log"], "%d_%d.jsonl" % (_os.getpid(), int(time.time() * 1000)))
        with open(L["path"], "a", encoding="utf-8") as f:
            for r in L["recs"]:
                f.write(_json.dumps(r) + "\n")
    except Exception:
        pass
    del L["recs"][:]


def _sd_step_end(step, t_entry):
    """HOOK 5 (entry point, after everything): whole-step time and the 1 s overage bank estimate; the planner switches
    itself off for the rest of the game when the estimated bank use passes sd_bank_stop."""
    S = _S
    if S is None:
        return
    L = _sd_state(S)
    st = L["st"]
    dt = time.time() - t_entry
    st["step_ms"].append(round(1000.0 * dt, 2))
    if dt > 1.0:
        st["steps_over_1s"] += 1
        st["bank_used"] += dt - 1.0
        if st["bank_used"] > CFG["sd_bank_stop"] and not L["off"]:
            L["off"] = True
            st["last_error"] = "bank stop at step %d" % step
    if step >= 718:
        _sd_flush(S, True)
# ===== END SEARCH DISPATCH BLOCK =============================================================

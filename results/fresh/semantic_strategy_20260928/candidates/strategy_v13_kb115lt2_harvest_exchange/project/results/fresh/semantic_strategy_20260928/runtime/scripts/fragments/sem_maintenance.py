# sem_maintenance: minimum-sufficient maintenance jobs [E] + end-of-life abandonment (2026-09-24).
#
# Self-contained fragment (stdlib only, `_sm_` / `SM_` prefixes) so it can be concatenated into a
# single-file agent.  The day-level tile model is a copy of scripts/min_maintenance.py Part A
# (0 mismatches vs engine 1.32.7 on 4000 random transitions there; re-checked against that module
# by scripts/sem_maintenance_validate.py), with two changes:
#   * today's decay starts at the observation hour (a mid-day call sees decays already applied);
#   * the objective is integer: 20*units - inputs*round(20*input_price/product_price)
#     - visits*round(20*visit_cost/product_price), then units, -visit-days, -turns, earliest release.
#     Integer arithmetic makes ties exact, so the plan is the minimum-visit full-production plan.
#
# Public entry points
#   maintenance_jobs(obs, player, prices=None, fertilize='auto', future_hour=8, visit_cost=0.0,
#                    include_optional=False, log=None) -> [job, ...]
#     job = {'tile': (x, y), 'cmd': WATER|FEED|CARE|FERTILIZE|HARVEST|COLLECT_FERTILIZER,
#            'value': coins lost if not done today (net of the wheat / fertilizer it consumes),
#            'deadline': last hour today that still keeps `value`,
#            'needs': {'WHEAT': 1} | {'FERTILIZER': 1} | {},
#            'reason': str, 'kind': survival|production|bonus|harvest|bank|endoflife,
#            'order': same-tile execution order (FERTILIZE 0 < WATER 1 < HARVEST 2),
#            'units': product units at stake, 'product': str, 'price': coins/unit,
#            'decay_per_2h': units lost per 2 hours past the deadline (decaying harvests only)}
#   Following the list each day (and nothing else) gives the full production of the DP plan with the
#   fewest visit-days.  A job with value 0 is in that plan only to save later visits.
#   fertilize: 'auto' (use when the extra units pay for the fertilizer at market price),
#              True (fertilizer free: maximum production), False (never), or {crop: one of those}.
#   log: optional list; abandoned assets (end of life or error) are appended once per asset.
#   collect: False (default) = animal DP values the product only; True = it also values the daily
#            fertilizer (market price, one turn), so FEED keeps a past-production animal alive when the
#            fertilizer pays for the wheat.  COLLECT_FERTILIZER jobs are emitted in both modes.
#
#   abandonment_log_entry(kind, tile, state, day, verdict, ...) -> dict (see below).
#   sm_tile_plan(kind, state, day, hour, ...) -> per-tile plan (used by the validators).

SM_TURNS = 24
SM_LAST_STEP = 718                  # last executed action (day 29 hour 22)
SM_LAST_DAY = SM_LAST_STEP // SM_TURNS
SM_LAST_REFRESH_DAY = SM_LAST_DAY - 1
SM_Q = 20                           # objective scale: 1/20 of a product unit

SM_CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}
SM_ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}
SM_BASE_PRICE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
                 "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100}
SM_SHED_ACCESS = ((4, 4), (5, 4), (4, 5), (5, 5))
_SM_ORDER = {"FERTILIZE": 0, "WATER": 1, "FEED": 0, "CARE": 1, "HARVEST": 2, "COLLECT_FERTILIZER": 3}
_SM_SOLVERS = {}
_SM_PLAN_CACHE = {}


# ---------------------------------------------------------------- day model (engine copy)
def _sm_decay(yu, mls, s0, s1):
    if mls < 0 or s1 <= mls:
        return yu
    for s in range(max(s0, mls), s1):
        if (s - mls) % 2 == 0:
            yu -= 1
            if yu <= 0:
                return None
    return yu


def _sm_crop_day(crop, st, day, water, fert, harvest, hour, h0=0):
    """One day on a crop tile from hour h0 (decays before h0 already applied); actions at `hour`
    in the order FERTILIZE, WATER, HARVEST. -> (state | None (weed) | 'GONE', units)."""
    cd = SM_CROPS[crop]
    planted, cu, yu, fud, mls, wt = st
    base = day * SM_TURNS
    end = min(base + SM_TURNS, SM_LAST_STEP + 1)
    yu = _sm_decay(yu, mls, base + h0, base + hour)
    if yu is None:
        return None, 0
    if fert:
        fud = max(fud, day + 2)
    if water and not wt:
        wt = True
        if not cd["ongoing"]:
            age = day - planted
            if (cd["max_yield_day"] + 1) // 2 <= age <= cd["max_yield_day"]:
                yu = min(cd["max_yield"], yu + (2 if fud >= day else 1))
    units = 0
    if harvest and yu > 0 and day - planted >= cd["first_yield_day"]:
        units, yu = yu, 0
        if not cd["ongoing"]:
            return "GONE", units
    yu = _sm_decay(yu, mls, base + hour, end)
    if yu is None:
        return None, units
    if day > SM_LAST_REFRESH_DAY:
        return (planted, cu, yu, fud, mls, wt), units
    cu = 0 if wt else cu + 1
    if cu >= 2:
        return None, units
    if cd["ongoing"]:
        dsf = day + 1 - planted - cd["first_yield_day"]
        if dsf >= 0 and dsf % cd["interval"] == 0:
            pc = dsf // cd["interval"] + 1
            if pc <= cd["max_yield"]:
                yu = min(cd["max_yield"], yu + (2 if (wt and fud >= day) else 1))
                if pc == cd["max_yield"]:
                    mls = (day + 2) * SM_TURNS
    return (planted, cu, yu, fud, mls, False), units


def _sm_animal_day(animal, st, day, feed, care, harvest):
    a = SM_ANIMALS[animal]
    placed, cu, pend, yu, ft, ct = st
    ft = ft or feed
    ct = ct or care
    units = 0
    if harvest and yu > 0:
        units, yu = yu, 0
    if day > SM_LAST_REFRESH_DAY:
        return (placed, cu, pend, yu, ft, ct), units
    cu = 0 if ft else cu + 1
    if cu >= 2:
        return None, units
    dsf = day + 1 - placed - a["first_yield_day"]
    if dsf >= 0 and dsf % a["interval"] == 0:
        yu = min(a["max_held"], yu + 1 + (pend if ft else 0))
        pend = 0
    if ct and ft:
        pend += 1
    return (placed, cu, pend, yu, False, False), units


def _sm_state(kind, t):
    if kind in SM_CROPS:
        return (int(t["planted_day"]), int(t["consecutive_unwatered"]), int(t["yield_units"]),
                int(t.get("fertilized_until_day", -1)), int(t["max_lifespan_step"]), bool(t["watered_today"]))
    return (int(t["placed_day"]), int(t["consecutive_unfed"]), int(t.get("pending_care_bonus", 0) or 0),
            int(t["yield_units"]), bool(t["fed_today"]), bool(t["cared_today"]))


# ---------------------------------------------------------------- DP solver (shared memo)
_SM_ZERO = ((0, 0, 0, 0, 0), None)


class _SMSolver(object):
    def __init__(self, kind, fert_ok, rin, rv, fh, rc=0):
        self.kind = kind
        self.crop = kind in SM_CROPS
        self.fert_ok = fert_ok
        self.rin, self.rv, self.fh = rin, rv, fh
        self.rc = rc        # animals: value of the daily fertilizer collection (0 = not modelled)
        self.memo = {}

    def combos(self, st, day):
        out = []
        if self.crop:
            can_h = st[2] > 0 and day - st[0] >= SM_CROPS[self.kind]["first_yield_day"]
            for w in ((0, 1) if not st[5] else (0,)):
                for f in ((0, 1) if self.fert_ok else (0,)):
                    for h in ((0, 1) if can_h else (0,)):
                        out.append((w, f, h))
        else:
            for f in ((0, 1) if not st[4] else (0,)):
                for c in ((0, 1) if not st[5] else (0,)):
                    for h in ((0, 1) if st[3] > 0 else (0,)):
                        out.append((f, c, h))
        return out

    def step(self, st, day, combo, hour, h0, avail=None):
        extra = 0
        if self.crop:
            w, f, h = combo
            st2, u = _sm_crop_day(self.kind, st, day, w, f, h, hour, h0)
            inputs = f
        else:
            f, c, h = combo
            st2, u = _sm_animal_day(self.kind, st, day, f, c, h)
            inputs = f
            if self.rc and (day > st[0] if avail is None else avail):
                extra = 1       # collect today's fertilizer (one turn)
        turns = combo[0] + combo[1] + combo[2] + extra
        visits = 1 if turns else 0
        econ = SM_Q * u - inputs * self.rin - visits * self.rv + extra * self.rc
        return st2, (econ, u, -visits, -turns, -(day if st2 == "GONE" else 0))

    def value(self, st, day):
        if st is None or st == "GONE" or day > SM_LAST_DAY:
            return _SM_ZERO
        key = (st, day)
        r = self.memo.get(key)
        if r is not None:
            return r
        best = None
        for combo in self.combos(st, day):
            st2, v = self.step(st, day, combo, self.fh, 0)
            if v is None:
                continue
            fut = self.value(st2, day + 1)[0]
            tot = (v[0] + fut[0], v[1] + fut[1], v[2] + fut[2], v[3] + fut[3], v[4] + fut[4])
            if best is None or tot > best[0]:
                best = (tot, combo, st2)
        self.memo[key] = best
        return best

    def today(self, st, day, hour, must=None, forbid=None, avail=None):
        best = None
        for combo in self.combos(st, day):
            if must is not None and not combo[must]:
                continue
            if forbid is not None and combo[forbid]:
                continue
            st2, v = self.step(st, day, combo, hour, hour, avail)
            if v is None:
                continue
            fut = self.value(st2, day + 1)[0]
            tot = (v[0] + fut[0], v[1] + fut[1], v[2] + fut[2], v[3] + fut[3], v[4] + fut[4])
            if best is None or tot > best[0]:
                best = (tot, combo, st2, v)
        return best


def _sm_solver(kind, fert_ok, rin, rv, fh, rc=0):
    key = (kind, fert_ok, rin, rv, fh, rc)
    s = _SM_SOLVERS.get(key)
    if s is None:
        if len(_SM_SOLVERS) > 96:
            _SM_SOLVERS.clear()
            _SM_PLAN_CACHE.clear()
        s = _SM_SOLVERS[key] = _SMSolver(kind, fert_ok, rin, rv, fh, rc)
    return s


def _sm_ratio(num, den):
    if den <= 0:
        return 10 ** 6
    return max(0, int(round(SM_Q * float(num) / float(den))))


def _sm_product(kind):
    return kind if kind in SM_CROPS else SM_ANIMALS[kind]["product"]


def _sm_is_production_day(animal, placed, day):
    a = SM_ANIMALS[animal]
    dsf = day + 1 - placed - a["first_yield_day"]
    return day <= SM_LAST_REFRESH_DAY and dsf >= 0 and dsf % a["interval"] == 0


def _sm_productions_so_far(kind, st, day):
    """Production refreshes that have already happened (visible by `day`)."""
    if kind in SM_CROPS:
        cd = SM_CROPS[kind]
        if not cd["ongoing"]:
            return 0
        dsf = day - st[0] - cd["first_yield_day"]
        return 0 if dsf < 0 else min(cd["max_yield"], dsf // cd["interval"] + 1)
    a = SM_ANIMALS[kind]
    dsf = day - st[0] - a["first_yield_day"]
    return 0 if dsf < 0 else dsf // a["interval"] + 1


def sm_tile_plan(kind, state, day, hour, price=None, input_price=None, fert_ok=False,
                 future_hour=8, visit_cost=0.0, collect_price=0.0, avail=None):
    """Today's minimum plan for one tile. Returns a dict:
    combo (w,f,h | f,c,h), values_q {action: objective loss if forbidden, 1/SM_Q product units},
    units_lost {action: product units lost if forbidden}, units (econ plan, from today),
    full_units (fertilizer/wheat free, same fert_ok), held (harvestable now), abandoned verdict."""
    st = state if isinstance(state, tuple) else _sm_state(kind, state)
    product = _sm_product(kind)
    price = float(SM_BASE_PRICE[product] if price is None else price)
    if input_price is None:
        input_price = SM_BASE_PRICE["FERTILIZER" if kind in SM_CROPS else "WHEAT"]
    rin = _sm_ratio(input_price, price)
    rv = _sm_ratio(visit_cost, price) if visit_cost else 0
    rc = _sm_ratio(collect_price, price) if (collect_price and kind in SM_ANIMALS) else 0
    ck = (kind, st, day, hour, bool(fert_ok), rin, rv, future_hour, rc, avail)
    r = _SM_PLAN_CACHE.get(ck)
    if r is not None:
        return r
    S = _sm_solver(kind, bool(fert_ok), rin, rv, future_hour, rc)
    best = S.today(st, day, hour, avail=avail)
    if best is None:
        r = {"combo": None, "values_q": {}, "units_lost": {}, "repairs": {}, "units": 0, "full_units": 0, "held": 0,
             "econ_q": 0, "visits": 0}
        _SM_PLAN_CACHE[ck] = r
        return r
    tot, combo, st2, v = best
    names = ("WATER", "FERTILIZE", "HARVEST") if kind in SM_CROPS else ("FEED", "CARE", "HARVEST")
    values_q, units_lost, repairs = {}, {}, {}
    for i, name in enumerate(names):
        if combo[i]:
            # strict skip: drop this one action, keep the rest of today's plan, optimal from tomorrow
            c2 = tuple(0 if k == i else combo[k] for k in range(3))
            s2, v2 = S.step(st, day, c2, hour, hour, avail)
            fut = S.value(s2, day + 1)[0]
            values_q[name] = tot[0] - (v2[0] + fut[0])
            units_lost[name] = tot[1] - (v2[1] + fut[1])
            # repaired skip: best plan without this action (other actions of today may change)
            alt = S.today(st, day, hour, forbid=i, avail=avail)
            if alt is not None and alt[0][0] > v2[0] + fut[0]:
                repairs[name] = (tot[0] - alt[0][0], tot[1] - alt[0][1],
                                 [n for n, on in zip(names, alt[1]) if on])
    if kind in SM_CROPS:
        cd = SM_CROPS[kind]
        held = st[2] if day - st[0] >= cd["first_yield_day"] else 0
        productive = tot[1] > (held if cd["ongoing"] else 0)
    else:
        held = st[3]
        productive = tot[1] > held
    alive_to_end = False
    if rc and not productive:       # fed only for its fertilizer? follow the plan to the season end
        s_, d_ = st2, day + 1
        while s_ is not None and s_ != "GONE" and d_ <= SM_LAST_DAY:
            b_ = S.value(s_, d_)
            if b_[1] is None:
                break
            s_, d_ = b_[2], d_ + 1
        alive_to_end = s_ is not None and s_ != "GONE" and d_ > SM_LAST_DAY
    full_units = tot[1]
    if (rin or rv) and not productive:     # only needed to tell end of life from an upkeep error
        fb = _sm_solver(kind, bool(fert_ok), 0, 0, future_hour).today(st, day, hour)
        full_units = fb[0][1] if fb else 0
    r = {"combo": combo, "values_q": values_q, "units_lost": units_lost, "repairs": repairs,
         "units": tot[1], "full_units": full_units, "held": held, "econ_q": tot[0], "visits": -tot[2],
         "harvest_today": v[1], "kept_for_fertilizer": alive_to_end}
    if len(_SM_PLAN_CACHE) > 20000:
        _SM_PLAN_CACHE.clear()
    _SM_PLAN_CACHE[ck] = r
    return r


# ---------------------------------------------------------------- helpers
def _sm_get(obs, key, default=None):
    try:
        v = obs[key]
    except (KeyError, TypeError, IndexError):
        v = getattr(obs, key, default)
    return default if v is None else v


def _sm_prices(obs, prices):
    pr = dict(SM_BASE_PRICE)
    mk = _sm_get(obs, "market", None)
    if mk:
        mp = _sm_get(mk, "prices", None)
        if mp:
            for k in pr:
                try:
                    if mp[k] is not None:
                        pr[k] = float(mp[k])
                except (KeyError, TypeError):
                    pass
    if prices:
        for k, v in prices.items():
            if v is not None:
                pr[k] = float(v)
    return pr


def _sm_shed_dist(x, y):
    return min(abs(x - a) + abs(y - b) for a, b in SM_SHED_ACCESS)


def _sm_fert_mode(fertilize, crop, price, fert_price):
    m = fertilize.get(crop, "auto") if isinstance(fertilize, dict) else fertilize
    if m is True:
        return True, 0.0
    if m is False or m is None:
        return False, fert_price
    return True, fert_price            # 'auto': allowed, charged at the fertilizer price


def _sm_harvest_deadline(kind, st, day, hour, x, y):
    """(deadline hour, decay_per_2h) for a HARVEST done today."""
    last = 23 if day < SM_LAST_DAY else SM_LAST_STEP - SM_LAST_DAY * SM_TURNS
    decay = 0
    dl = last
    if kind in SM_CROPS:
        mls = st[4]
        base = day * SM_TURNS
        if mls >= 0 and mls <= base + 23:
            s1 = max(mls, base + hour)
            if (s1 - mls) % 2:
                s1 += 1
            dl = min(dl, max(hour, s1 - base))
            decay = 1
    if day >= SM_LAST_DAY:          # no day-end drop: carry to the shed, DROP and SELL by step 718
        dl = min(dl, SM_LAST_STEP - SM_LAST_DAY * SM_TURNS - 1 - _sm_shed_dist(x, y))
    return max(hour, dl), decay


def abandonment_log_entry(kind, tile, state, day, verdict, price=None, cost=None, revenue=None,
                          forfeited_units=0, upkeep_saved=0.0, reason="", shops=None):
    """One abandonment record.  verdict: 'end_of_life' (cannot complete another production cycle
    before the season ends; correct play, never a planting signal) or 'error' (could, but its remaining
    value does not cover upkeep, or it never produced and never will: a planting / purchase error).
    `revenue` (produced so far) and `cost` are the caller's if known; cost defaults to the seed or
    animal price.  `paid_back` is None when revenue is unknown."""
    st = state if isinstance(state, tuple) else _sm_state(kind, state)
    product = _sm_product(kind)
    price = float(SM_BASE_PRICE[product] if price is None else price)
    if cost is None:
        cost = SM_CROPS[kind]["seed"] if kind in SM_CROPS else SM_ANIMALS[kind]["cost"]
    prods = _sm_productions_so_far(kind, st, day)
    return {
        "kind": kind, "tile": tuple(tile), "start_day": st[0], "day": day, "cost": cost,
        "revenue": revenue, "paid_back": (None if revenue is None else revenue >= cost),
        "productions_so_far": prods, "forfeited_units": forfeited_units,
        "forfeited_value": round(forfeited_units * price, 1), "upkeep_saved": round(upkeep_saved, 1),
        "verdict": verdict, "planting_signal": verdict == "error", "reason": reason,
        "shops": list(shops) if shops else None,
    }


# ---------------------------------------------------------------- main entry
def maintenance_jobs(obs, player, prices=None, fertilize="auto", future_hour=8, visit_cost=0.0,
                     include_optional=False, log=None, collect=False):
    step = _sm_get(obs, "step", None)
    if step is not None:
        day, hour = divmod(int(step), SM_TURNS)
    else:
        day, hour = int(_sm_get(obs, "day", 0)), int(_sm_get(obs, "hour", 0))
    farm = _sm_get(obs, "farms")[player]
    tiles = _sm_get(farm, "tiles")
    pr = _sm_prices(obs, prices)
    wheat_p, fert_p = pr["WHEAT"], pr["FERTILIZER"]
    last_hour = 23 if day < SM_LAST_DAY else SM_LAST_STEP - SM_LAST_DAY * SM_TURNS
    jobs = []
    logged = None
    if log is not None:
        logged = {(e["tile"], e["start_day"], e["kind"]) for e in log}
    for y, row in enumerate(tiles):
        for x, t in enumerate(row):
            if not isinstance(t, dict):
                continue
            if t.get("kind") == "PLANT":
                kind = t.get("crop")
                if kind not in SM_CROPS:
                    continue
                crop = True
            elif t.get("animal") in SM_ANIMALS:
                kind = t["animal"]
                crop = False
            else:
                continue
            product = _sm_product(kind)
            price = pr.get(product, SM_BASE_PRICE[product])
            st = _sm_state(kind, t)
            if crop:
                fert_ok, inp = _sm_fert_mode(fertilize, kind, price, fert_p)
            else:
                fert_ok, inp = False, wheat_p
            if crop or not collect:
                p = sm_tile_plan(kind, st, day, hour, price, inp, fert_ok, future_hour, visit_cost)
            else:
                p = sm_tile_plan(kind, st, day, hour, price, inp, fert_ok, future_hour, visit_cost,
                                 collect_price=fert_p, avail=bool(t.get("fertilizer_available")))
            combo = p["combo"]
            tile = (x, y)
            future_full = p["full_units"] - p["held"]
            future_econ = p["units"] - p["held"]
            ongoing = (not crop) or SM_CROPS[kind]["ongoing"]
            verdict = None
            if p.get("kept_for_fertilizer"):
                pass                    # past its last production but worth feeding for fertilizer
            elif ongoing and future_full <= 0:
                prods = _sm_productions_so_far(kind, st, day)
                verdict = "end_of_life" if prods > 0 else "error"
                why = "no production reachable before the season ends" if prods else "never productive"
            elif (not ongoing) and p["full_units"] <= 0:
                verdict, why = "error", "cannot reach a harvest before the season ends"
            elif future_full > 0 and future_econ <= 0:
                verdict, why = "error", "remaining value does not cover upkeep"
            if verdict and logged is not None and (tile, st[0], kind) not in logged:
                fu = max(0, p["full_units"] - p["units"])
                log.append(abandonment_log_entry(kind, tile, st, day, verdict, price=price,
                                                 forfeited_units=fu, reason=why))
                logged.add((tile, st[0], kind))
            h_dl, h_decay = _sm_harvest_deadline(kind, st, day, hour, x, y)
            if combo is not None:
                names = ("WATER", "FERTILIZE", "HARVEST") if crop else ("FEED", "CARE", "HARVEST")
                for i, cmd in enumerate(names):
                    if not combo[i]:
                        continue
                    vq = p["values_q"].get(cmd, 0)
                    value = round(vq * price / SM_Q, 1)
                    units = p["units_lost"].get(cmd, 0)
                    needs = {}
                    dl = last_hour
                    decay = 0
                    if cmd == "HARVEST":
                        kind_j = "endoflife" if (verdict or (ongoing and future_econ <= 0)) else "harvest"
                        dl, decay = h_dl, h_decay
                        if decay:
                            reason = "decaying: -1 unit per 2 h"
                        elif units:
                            reason = "held yield lost if left" if not ongoing or verdict else "cap overflow / final yield"
                        else:
                            reason = "harvest now, frees the tile"
                    elif crop:
                        if cmd == "FERTILIZE":
                            needs = {"FERTILIZER": 1}
                            kind_j, reason = "bonus", "fertilised yield +%d" % units
                        elif st[1] >= 1 and not combo[2]:
                            kind_j, reason = "survival", "dies tonight if dry"
                        elif not SM_CROPS[kind]["ongoing"]:
                            kind_j, reason = "bonus", "window watering +%d" % units
                        else:
                            kind_j, reason = "production", "fertilised production needs water"
                        if combo[2]:
                            dl = min(dl, h_dl)
                    else:
                        if cmd == "FEED":
                            needs = {"WHEAT": 1}
                            if st[1] >= 1:
                                kind_j, reason = "survival", "escapes tonight if unfed"
                            elif _sm_is_production_day(kind, st[0], day):
                                kind_j, reason = "production", "production day: bank %d paid only if fed" % st[2]
                            elif p.get("kept_for_fertilizer") or (collect and units == 0):
                                kind_j, reason = "production", "keeps the fertilizer stream alive"
                            else:
                                kind_j, reason = "bank", "fed+cared day banks +1"
                        else:
                            kind_j, reason = "bank", "care banks +1 for next production"
                    job = {"tile": tile, "cmd": cmd, "value": value, "deadline": dl, "needs": needs,
                           "reason": reason, "kind": kind_j, "order": _SM_ORDER[cmd], "units": units,
                           "product": product, "price": price, "asset": kind}
                    if decay:
                        job["decay_per_2h"] = 1
                    rep = p["repairs"].get(cmd)
                    if rep:     # skipping it costs less if today's other actions change as listed
                        job["repair"] = {"value": round(rep[0] * price / SM_Q, 1), "units": rep[1], "do": rep[2]}
                    jobs.append(job)
                if include_optional and not combo[2] and p["held"] > 0:
                    jobs.append({"tile": tile, "cmd": "HARVEST", "value": 0.0, "deadline": h_dl, "needs": {},
                                 "reason": "optional: can wait", "kind": "harvest", "order": 2,
                                 "units": 0, "product": product, "price": price, "asset": kind,
                                 "optional": True, "held": p["held"]})
            if (not crop) and t.get("fertilizer_available") and fert_p > 1:
                jobs.append({"tile": tile, "cmd": "COLLECT_FERTILIZER", "value": round(fert_p, 1),
                             "deadline": (last_hour if day < SM_LAST_DAY else h_dl), "needs": {},
                             "reason": "fertilizer does not accumulate",
                             "kind": "endoflife" if verdict else "production", "order": 3, "units": 1,
                             "product": "FERTILIZER", "price": fert_p, "asset": kind})
    return jobs

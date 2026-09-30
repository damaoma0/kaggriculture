"""v18x -> v18y: sd_rush (default None) - the morning bring-back, planned first.

User 2026-09-29: "rush 2 hands immediately, get closest 4-8 strawberry and back. If there are needs that are ignored we
can hire an extra hand. Same story for milk ... Our target is to beat DSM to the shop"; "2 hand rush is just farmer+1 hand
with its spawn tile on or near shed"; "make sure part of the harvest make it back within the day and beat opponent's
morning batch"; "maybe we can plan this bit first and tell planner so that we can hire correctly?"; "moving is not by
default, the farmer could also do pickup on his tile if needed".

Evidence (9 worlds, days 10-28): 97% of our strawberries, 80% of our milk and 65% of our wool ride in hand to the midnight
dump (DSM 75 / 58 / 42%); DSM sells 59 strawberries on days 15-18 against our 41 (peak days 16 / 18 / 20 / 22 hold 18-23
ready units at dawn); every earlier bring-back run took its hand off the routes (n18rc95: wheat -49, eggs -15), and the
extra hand of n18rc64-67 was hired on every day 12-28 (the 12th hire, ~2.4k a game).

config sd_rush {"prods": {product: {"ready": min ready units at dawn, "tiles": max tiles a leg, "by": deliver-by hour, "hire": 0|1}}, "order": [products],
                "farmer": 1, "units": 2, "hire": 1, "days": [12, 28]}
  - a product qualifies on a day when the dawn farm holds >= ready units of it (strawberry tiles / cow or sheep pens);
  - legs are planned before anything else: the farmer (at a shed tile, acting from hour 0) and then the first hour-0 hire
    take nearest-first tours over the qualifying tiles (<= tiles per product, taking the tile's HARVEST / WATER / CARE /
    COLLECT_FERTILIZER ops), then DELIVER at the nearest shed tile by the product's hour (sold on arrival); each unit
    then plans the rest of its day from that shed tile (the dawn-leg path of sd_tier_dawn);
  - the farmer's leg is known before the spawn prediction, so the hour-0 hires' spawn tiles follow from its first step
    (engine rule); without a farmer leg he keeps the hour-0 hold (with sd_tier_farmer_h0pick his hour-0 command is a
    pickup / job on his own tile);
  - on a qualifying day the day's hire count gets + hire (both the market's hire orders and the tier plan).

usage: patch_exec_rush_20260929.py  (writes agents/mgt_lead_kb115lt2_v18y.py from v18x)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18x.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18y.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


HELPERS = '''

_RUSH_DAY = {}


def _rush_targets(tiles, day):
    """sd_rush: {product: [tile idx with ready units]} for the products that qualify today (dawn ready units >= ready)."""
    cfg = CFG.get("sd_rush") or {}
    d0, d1 = (cfg.get("days") or [12, 28])[:2]
    if not cfg or not (int(d0) <= day <= int(d1)):
        return {}
    out = {}
    for prod, pc in (cfg.get("prods") or {}).items():
        idxs, ready = [], 0
        for idx in range(100):
            t = _tile(tiles, idx)
            if not isinstance(t, dict):
                continue
            y = int(t.get("yield_units", 0) or 0)
            if y <= 0:
                continue
            if prod == "STRAWBERRY":
                ok = _is_plant(t) and t.get("crop") == "STRAWBERRY"
            else:
                ok = bool(_animal(t)) and ANIMALS.get(t.get("animal"), {}).get("product") == prod
            if ok:
                idxs.append(idx)
                ready += y
        if idxs and ready >= int(pc.get("ready", 1)):
            out[prod] = idxs
    return out


def _rush_decide(tiles, day):
    """cache today's sd_rush decision (qualifying products, extra hires) at the first call of the day."""
    if _RUSH_DAY.get("day") == day:
        return _RUSH_DAY
    cfg = CFG.get("sd_rush") or {}
    tg = _rush_targets(tiles, day) if cfg else {}
    prods = cfg.get("prods") or {}                 # the extra hand only on days a product with "hire" qualifies
    extra = max([int(prods[p].get("hire", cfg.get("hire", 0)) or 0) for p in tg] or [0]) if int(cfg.get("units", 2)) >= 2 else 0
    _RUSH_DAY.clear()
    _RUSH_DAY.update(day=day, prods=sorted(tg), extra=extra)
    return _RUSH_DAY


def _rush_hire_extra(day):
    return int(_RUSH_DAY.get("extra", 0) or 0) if CFG.get("sd_rush") and _RUSH_DAY.get("day") == day else 0


_RUSH_OPS = ("HARVEST", "PLACE_HARVEST", "WATER", "CARE", "COLLECT_FERTILIZER")


def _rush_leg_eval(tour, pi, t0, rec):
    """stops of a rush leg (the tour's tiles, then DELIVER at the shed tile nearest the last tile) and its evaluation."""
    D = _TIER_D
    stops = []
    for idx in tour:
        ops = [dict(o, m=True, tier=1) if o["c"][0] in ("HARVEST", "PLACE_HARVEST") else dict(o)
               for o in rec[idx]["ops"] if o["c"][0] in _RUSH_OPS]
        stops.append({"tile": idx, "ops": sorted(ops, key=lambda o: o["rank"]), "rel": rec[idx]["rel"]})
    last = tour[-1]
    sh = min(_TIER_SHED_I, key=lambda q: (D[last][q], D[q][pi], q))
    stops.append({"tile": sh, "ops": [_tier_op(["DELIVER"], True, 0.0, 1)], "rel": 0, "turn": True})
    ev = _tier_eval({"p0": pi, "t0": t0, "stops": []}, stops, want_hours=True)
    if ev[1] > 0 or ev[3] > 0:
        return None
    drops = [h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER"]
    if not drops:
        return None
    return stops, ev, max(drops)


def _tier_rush(S, rec, tiles, day, units, busy, st):
    """sd_rush: the morning bring-back legs (see the flag). Returns {u: leg} in the sd_tier_dawn leg format; the taken ops
    leave rec."""
    cfg = CFG.get("sd_rush") or {}
    tg = _rush_targets(tiles, day)
    if not tg:
        return {}
    D = _TIER_D
    prods = cfg.get("prods") or {}
    cand = []
    for prod, idxs in tg.items():
        for idx in idxs:
            r_ = rec.get(idx)
            if not r_ or not any(o["c"][0] == "HARVEST" for o in r_["ops"]):
                continue
            cand.append((idx, prod, int(_tile(tiles, idx).get("yield_units", 0) or 0)))
    free = [x for x in units if x[0] not in busy]
    chosen = [x for x in free if x[0] == 0 and x[2] == 0 and tuple(x[1]) in SHED] if int(cfg.get("farmer", 1)) else []
    chosen += [x for x in free if x[0] != 0 and x[2] <= 1][:max(0, int(cfg.get("units", 2)) - len(chosen))]
    order = [p for p in (cfg.get("order") or list(prods)) if p in tg]
    out, taken = {}, set()
    for u, p0, t0 in chosen:
        pi = p0[1] * 10 + p0[0]
        tour, best = [], None
        for prod in order:                         # one product a leg, in priority order (strawberries first)
            left = [c for c in cand if c[0] not in taken and c[1] == prod]
            pos = pi
            while left:
                c = min(left, key=lambda c: (D[pos][c[0]], -c[2], c[0]))
                left.remove(c)
                if len(tour) >= int(prods[prod].get("tiles", 4)):
                    break
                trial = tour + [c]
                got = _rush_leg_eval([x[0] for x in trial], pi, t0, rec)
                if got is None or got[2] > int(prods[prod].get("by", 22)):
                    continue
                tour, pos, best = trial, c[0], got
            if tour:
                break
        if not tour:
            continue
        stops, ev, drop = best
        out[u] = {"stops": stops, "p0": pi, "t0": t0, "end": ev[0], "tile": stops[-1]["tile"], "drop": drop,
                  "pen": tour[0][0], "units": sum(x[2] for x in tour), "prod": "+".join(sorted(set(x[1] for x in tour))),
                  "hours": [(b_, c_[0], h) for b_, c_, h in ev[4]]}
        for x in tour:
            taken.add(x[0])
            rec[x[0]]["ops"] = [o for o in rec[x[0]]["ops"] if o["c"][0] not in _RUSH_OPS]
            if not rec[x[0]]["ops"]:
                rec.pop(x[0])
        st["rush_legs"] = st.get("rush_legs", 0) + 1
        st["rush_units"] = st.get("rush_units", 0) + out[u]["units"]
        st["rush_tiles"] = st.get("rush_tiles", 0) + len(tour)
        st["rush_drop_h"] = st.get("rush_drop_h", 0) + drop
        if u == 0:
            st["rush_farmer"] = st.get("rush_farmer", 0) + 1
    return out
'''


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_fert_land": None,''', '''    "sd_rush": None,          # {"prods": {product: {"ready", "tiles", "by"}}, "farmer", "units", "hire", "days"}: the morning bring-back legs (see _tier_rush)
    "sd_fert_land": None,''')
    s = sub(s, '''

def _tier_dawn(S, rec, tiles, day, units, busy, st):''', HELPERS + '''

def _tier_dawn(S, rec, tiles, day, units, busy, st):''')
    # the legs inside the tier core: before the dawn legs, which then skip the rush units
    s = sub(s, '''    dawn_of = {}
    if int(CFG["sd_tier_dawn"]) == 1:              # learned from DSM: short dawn round trips to the near pens (forced)
        dawn_of = _tier_dawn(S, rec, tiles, day, units, set(mel_of) | ani_units, st)
    elif int(CFG["sd_tier_dawn"]) == 3:            # user: DSM's recorded early trips of the day, same hands / pens / hours
        dawn_of = _tier_dawn_shape(S, rec, tiles, day, units, set(mel_of) | ani_units, st)''', '''    dawn_of = {}
    rush_of_ = _tier_rush(S, rec, tiles, day, units, set(mel_of) | ani_units, st) if CFG.get("sd_rush") else {}
    if int(CFG["sd_tier_dawn"]) == 1:              # learned from DSM: short dawn round trips to the near pens (forced)
        dawn_of = _tier_dawn(S, rec, tiles, day, units, set(mel_of) | ani_units | set(rush_of_), st)
    elif int(CFG["sd_tier_dawn"]) == 3:            # user: DSM's recorded early trips of the day, same hands / pens / hours
        dawn_of = _tier_dawn_shape(S, rec, tiles, day, units, set(mel_of) | ani_units | set(rush_of_), st)
    dawn_of.update(rush_of_)                       # sd_rush: the morning bring-back legs (planned first)''')
    # the farmer's leg decided before the spawn prediction
    s = sub(s, '''        ft0 = 0                                    # sd_tier_dawn 3: DSM's farmer makes his early trip from hour 0
    sp0 = _sd_spawn([f0] if ft0 else ([] if f0 in SHED else [f0]), k0)''', '''        ft0 = 0                                    # sd_tier_dawn 3: DSM's farmer makes his early trip from hour 0
    rush_f1_ = None
    if CFG.get("sd_rush") and int((CFG["sd_rush"] or {}).get("farmer", 1)) and f0 in SHED:
        _rush_decide(tiles, day)
        rl_ = _tier_rush(S, _tier_copy.deepcopy(rec), tiles, day, [(0, f0, 0)], set(), {})
        if 0 in rl_:                               # sd_rush: the farmer leaves at hour 0; his first step fixes the spawns
            ft0 = 0
            q_ = rl_[0]["stops"][0]["tile"]
            q_ = (q_ % 10, q_ // 10)
            dx_, dy_ = q_[0] - f0[0], q_[1] - f0[1]
            rush_f1_ = (f0[0] + (1 if dx_ > 0 else -1), f0[1]) if dx_ else ((f0[0], f0[1] + (1 if dy_ > 0 else -1)) if dy_ else f0)
    sp0 = _sd_spawn([rush_f1_] if rush_f1_ is not None else ([f0] if ft0 else ([] if f0 in SHED else [f0])), k0)''')
    # hires: the rush day's extra hand in the tier plan's count and in the market's hire orders
    s = sub(s, '''    want = T.hands[d] + CFG["hire_extra"]
    if CFG["hands_d29_fix"] and d == T.n - 1 and T.hands[d] == 0 and d > 0:
        want = T.hands[d - 1] + CFG["hire_extra"]
    return max(0, int(want))''', '''    want = T.hands[d] + CFG["hire_extra"]
    if CFG["hands_d29_fix"] and d == T.n - 1 and T.hands[d] == 0 and d > 0:
        want = T.hands[d - 1] + CFG["hire_extra"]
    return max(0, int(want) + _rush_hire_extra(day))''')
    s = sub(s, '''    hires = []
    if (not endgame or CFG["hands_d29_fix"]) and hour <= 12 and CFG["hires_first"]:
        want = T.hands[d] + CFG["hire_extra"]''', '''    hires = []
    if CFG.get("sd_rush"):
        _rush_decide(farm["tiles"], day)
    if (not endgame or CFG["hands_d29_fix"]) and hour <= 12 and CFG["hires_first"]:
        want = T.hands[d] + CFG["hire_extra"] + _rush_hire_extra(day)''')
    s = sub(s, '''    if not endgame and hour <= 12 and not CFG["hires_first"]:
        want = T.hands[d] + CFG["hire_extra"]''', '''    if not endgame and hour <= 12 and not CFG["hires_first"]:
        want = T.hands[d] + CFG["hire_extra"] + _rush_hire_extra(day)''')
    # the tier pre-plan decides today's rush before its hire count
    s = sub(s, '''    want = _sd_want_hands(day)
    k0 = min(want, 10)''', '''    if CFG.get("sd_rush"):
        _rush_decide(tiles, day)
    want = _sd_want_hands(day)
    k0 = min(want, 10)''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

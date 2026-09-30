"""Exact (same-output) speedups of the tier planner's hour-0 day plan (2026-09-29, shipping: n17 spends ~100 s of the
60 s overage bank on Kaggle, all in the day plan). Default OFF; each flag must leave every action unchanged.

  sd_fast_relief   _tier_relief re-evaluated, for EVERY unplanned extra, the same removal of each stop from each route
                   and the same insertion of that stop at every position of every other route (none of it depends on
                   the extra; the routes change only when a relief move is applied, which bumps their "ver"). Those
                   evaluations are cached per (route, version, stop, other route, version, position) for one call.
  sd_fast_ins      _tier_best_ins built every candidate position with _tier_merge (a copy of every stop dict per
                   position) only to evaluate it; the positions are now evaluated on light lists sharing the stop
                   dicts, and only the candidates that are returned or paired are materialised exactly as before.

usage: patch_exec_fast_20260929.py <source.py> <output.py>"""
import sys
from pathlib import Path


def patch(s):
    def rep(old, new, n=1):
        nonlocal s
        assert s.count(old) == n, (s.count(old), old[:90])
        s = s.replace(old, new)

    rep('''    "sd_tier_budget": 10.0,''', '''    "sd_fast_relief": 0,      # 1: exact cache of the relief pass's extra-independent route evaluations
    "sd_fast_ins": 0,         # 1: _tier_best_ins evaluates positions without copying every stop per position
    "sd_tier_budget": 10.0,''')
    # ---- relief cache
    rep('''    D = _TIER_D
    moves = 0
    slack = int(CFG["sd_tier_relief_slack"])
    for _pass in range(int(CFG["sd_tier_relief_passes"])):''', '''    D = _TIER_D
    moves = 0
    slack = int(CFG["sd_tier_relief_slack"])
    fast_ = bool(CFG["sd_fast_relief"])
    rc_ = {}                                       # sd_fast_relief: per-call cache keyed by route versions
    for _pass in range(int(CFG["sd_tier_relief_passes"])):''')
    rep('''            for r in cand_r:
                R = segs[r]
                evR = _tier_eval(R)
                cR = _tier_cost(R, evR)
                for i, x in enumerate(R["stops"]):
                    if x.get("place") or x.get("dawn") or x.get("svc") or x["tile"] == bd["tile"]:
                        continue
                    R2 = dict(R, stops=R["stops"][:i] + R["stops"][i + 1:])
                    ev2 = _tier_eval(R2)''', '''            for r in cand_r:
                R = segs[r]
                if fast_:
                    kR_ = ("R", r, R["ver"])
                    if kR_ not in rc_:
                        evR_ = _tier_eval(R)
                        rc_[kR_] = (evR_, _tier_cost(R, evR_))
                    evR, cR = rc_[kR_]
                else:
                    evR = _tier_eval(R)
                    cR = _tier_cost(R, evR)
                for i, x in enumerate(R["stops"]):
                    if x.get("place") or x.get("dawn") or x.get("svc") or x["tile"] == bd["tile"]:
                        continue
                    R2 = dict(R, stops=R["stops"][:i] + R["stops"][i + 1:])
                    if fast_:
                        k2_ = ("R2", r, R["ver"], i)
                        if k2_ not in rc_:
                            rc_[k2_] = _tier_eval(R2)
                        ev2 = rc_[k2_]
                    else:
                        ev2 = _tier_eval(R2)''')
    rep('''                    for k, S in enumerate(segs):
                        if k == r or S["kind"] == "central":
                            continue
                        evS = _tier_eval(S)
                        if evS[0] > 24 - slack:
                            continue
                        cS = _tier_cost(S, evS)
                        for pos in range(S.get("lo", 0), len(S["stops"]) + 1):
                            stS, _ = _tier_merge(S["stops"], x["tile"], x["ops"], x.get("rel", 0), pos)
                            evS2 = _tier_eval(S, stS)
                            if evS2[1] > evS[1] or evS2[3] > evS[3]:
                                continue
                            cS2 = _tier_cost(S, evS2, stS)
                            sc = bd["v"] / max(0.25, (cR3 - cR) + (cS2 - cS))''', '''                    for k, S in enumerate(segs):
                        if k == r or S["kind"] == "central":
                            continue
                        if fast_:
                            kS_ = ("S", r, R["ver"], i, k, S["ver"])
                            if kS_ not in rc_:     # the extra-independent part: x moved into S, every feasible position
                                evS_ = _tier_eval(S)
                                if evS_[0] > 24 - slack:
                                    rc_[kS_] = None
                                else:
                                    cS_ = _tier_cost(S, evS_)
                                    lst_ = []
                                    for pos in range(S.get("lo", 0), len(S["stops"]) + 1):
                                        stS, _ = _tier_merge(S["stops"], x["tile"], x["ops"], x.get("rel", 0), pos)
                                        evS2 = _tier_eval(S, stS)
                                        if evS2[1] > evS_[1] or evS2[3] > evS_[3]:
                                            continue
                                        lst_.append((stS, _tier_cost(S, evS2, stS) - cS_))
                                    rc_[kS_] = lst_
                            if rc_[kS_] is None:
                                continue
                            for stS, dS_ in rc_[kS_]:
                                sc = bd["v"] / max(0.25, (cR3 - cR) + dS_)
                                if sc >= rate and (best is None or sc > best[0]):
                                    best = (sc, r, ins[2], k, stS, x["tile"], ins[3])
                            continue
                        evS = _tier_eval(S)
                        if evS[0] > 24 - slack:
                            continue
                        cS = _tier_cost(S, evS)
                        for pos in range(S.get("lo", 0), len(S["stops"]) + 1):
                            stS, _ = _tier_merge(S["stops"], x["tile"], x["ops"], x.get("rel", 0), pos)
                            evS2 = _tier_eval(S, stS)
                            if evS2[1] > evS[1] or evS2[3] > evS[3]:
                                continue
                            cS2 = _tier_cost(S, evS2, stS)
                            sc = bd["v"] / max(0.25, (cR3 - cR) + (cS2 - cS))''')
    # ---- best insertion without per-position copies
    rep('''    opts = []
    if has:
        opts.append(_tier_merge(seg["stops"], bundle["tile"], bundle["ops"]))
    else:
        for k in range(lo, len(seg["stops"]) + 1):
            opts.append(_tier_merge(seg["stops"], bundle["tile"], bundle["ops"], 0, k))''', '''    opts = []
    light_ = False
    if has:
        opts.append(_tier_merge(seg["stops"], bundle["tile"], bundle["ops"]))
    elif CFG["sd_fast_ins"]:
        # no stop on the tile: _tier_merge would insert {"tile", "ops", "rel": 0} at k over shallow copies of the stops;
        # evaluate on light lists sharing the stop dicts, copy only what is returned or paired (below)
        base_ = seg["stops"]
        new_ = {"tile": bundle["tile"], "ops": sorted([dict(o) for o in bundle["ops"]], key=lambda o: o["rank"]), "rel": 0}
        for k in range(lo, len(base_) + 1):
            opts.append((base_[:k] + [new_] + base_[k:], k))
        light_ = True
    else:
        for k in range(lo, len(seg["stops"]) + 1):
            opts.append(_tier_merge(seg["stops"], bundle["tile"], bundle["ops"], 0, k))''')
    # a light candidate that is kept as the best is materialised exactly as _tier_merge makes it: fresh shallow copies of
    # every stop and a fresh ops list of fresh op dicts for the new stop
    rep('''            c = _tier_cost(seg, ev2, st2)
            dh = max(0.25, c - c0)
            sc = (bundle["v"] + (0.0 if CFG["sd_tier_pair_own"] else va)) / dh
            if best is None or sc > best[0]:
                best = (sc, c - c0, st2, a)
    return best''', '''            c = _tier_cost(seg, ev2, st2)
            dh = max(0.25, c - c0)
            sc = (bundle["v"] + (0.0 if CFG["sd_tier_pair_own"] else va)) / dh
            if best is None or sc > best[0]:
                best = (sc, c - c0, st2, a)
    if light_ and best is not None and any(best[2] is o_[0] for o_ in opts):
        best = (best[0], best[1], [dict(x_) for x_ in best[2]], best[3])   # as _tier_merge returns it: shallow copies
    return best''')
    return s


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    assert src.resolve() != out.resolve(), "refusing an in-place edit"
    s = patch(src.read_text(encoding="utf-8"))
    compile(s, str(out), "exec")
    out.write_text(s, encoding="utf-8", newline="\n")
    print("patched ->", out)

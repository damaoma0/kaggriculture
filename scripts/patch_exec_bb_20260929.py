"""v18h -> v18i: sd_tier_bb, HARD-CODED bring-back runs (default off). User 2026-09-29: "I suggest hard-coded bring-back
runs instead of trying to adjust weights and hope it fires".

Why: the planned mid-day drop (sd_tier_pdrop, even with room-making in v18h) is a scored insertion that rarely fires
(one game: 651 of 972 route checks "full", 0 strawberry drops); the leader's returns are 0.72 strawberry drops a day
(4.2 units, from 4.7 tiles out, mostly hours 12-20), 0.76 milk, 0.48 wool (1.6 tiles out); ours 0.15 strawberry drops.

sd_tier_bb {"min": {product: units}, "hmax": h, "days": [d0, d1], "detour": k}: every hour, a unit that is between two stops of its
route and carries >= min units of a listed product walks to the nearest shed-access tile when it can place the goods by
hour hmax, PLACEs every listed product it carries (one per hour; feed wheat / fertilizer stay in hand) - sold that hour
(non-books products through the delivery sale, books products on arrival) - and then resumes its route where it left
off. No planning or value: what no longer fits by hour 24 is simply not reached. "detour" (n18rc45 / 46: runs from the far
fields cost ~8-10 hand-hours and lost 21 strawberries a game): only when going via the shed to the next stop adds <= k
steps over going there directly (always at the route's end).

usage: patch_exec_bb_20260929.py  (writes agents/mgt_lead_kb115lt2_v18i.py from v18h)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18h.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18i.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_pdrop_room": None,''', '''    "sd_tier_bb": None,  # {"min": {product: units}, "hmax": h, "days": [d0, d1]} (user 2026-09-29: hard-coded bring-back
    # runs): a unit between two stops carrying >= min of a listed product walks to the nearest shed tile, PLACEs the listed
    # products (sold that hour) and resumes its route; no planning or value
    "sd_tier_pdrop_room": None,''')
    s = sub(s, '''    if CFG["sd_tier_fert_opp"] and int(inv.get("FERTILIZER", 0) or 0) > 0:
        a_ = _tier_fert_opp(TP, R, u, p, inv, tiles, day, hour)''', '''    if CFG.get("sd_tier_bb"):                      # hard-coded bring-back run (user)
        a_ = _tier_bb(TP, R, u, p, inv, day, hour)
        if a_ is not None:
            return a_
    if CFG["sd_tier_fert_opp"] and int(inv.get("FERTILIZER", 0) or 0) > 0:
        a_ = _tier_fert_opp(TP, R, u, p, inv, tiles, day, hour)''')
    s = sub(s, '''def _tier_idle_home(TP, R, u, p, inv, tiles, day, hour):''', '''def _tier_bb(TP, R, u, p, inv, day, hour):
    """sd_tier_bb: the next command of a hard-coded bring-back run, or None (see the flag)."""
    cfg = CFG["sd_tier_bb"] or {}
    mins = cfg.get("min") or {}
    dw = cfg.get("days")
    if dw and not (int(dw[0]) <= int(day) <= int(dw[1])):
        return None
    cnt = TP["cnt"]
    st = R.setdefault("_bb", {})
    if st.get("day") != day:
        st.clear()
        st["day"] = day
    sh = _near_shed(p)
    if not st.get("on"):
        if R.get("sub", 0):                        # in the middle of a stop's ops: finish the stop first
            return None
        goods = [k for k in mins if int(inv.get(k, 0) or 0) >= int(mins[k])]
        if not goods:
            return None
        d_ = abs(p[0] - sh[0]) + abs(p[1] - sh[1])
        if hour + d_ + len(goods) - 1 > int(cfg.get("hmax", 21)):
            return None
        if cfg.get("detour") is not None:          # only a cheap run: via the shed to the next stop costs <= detour steps
            nxt_ = next((it_ for it_ in R["items"][R["k"]:] if it_.get("kind") == "stop"), None)
            if nxt_ is not None:
                q_ = (nxt_["tile"] % 10, nxt_["tile"] // 10)
                via_ = d_ + abs(sh[0] - q_[0]) + abs(sh[1] - q_[1])
                if via_ - (abs(p[0] - q_[0]) + abs(p[1] - q_[1])) > int(cfg["detour"]):
                    cnt["bb_skip_detour"] += 1
                    return None
        st["on"], st["goods"] = True, goods
        cnt["bb_trips"] += 1
        cnt["bb_dist"] += d_
    if tuple(p) != tuple(sh):
        return _step_toward(p, sh)
    for k in st["goods"]:
        n = int(inv.get(k, 0) or 0)
        if n > 0:
            TP.setdefault("dsell", Counter())[k] += n        # non-books products: sold this hour
            TP.setdefault("dsell_now", Counter())[k] += n    # books products: sold on arrival
            cnt["bb_units_" + k] += n
            R.setdefault("done", []).append((hour, sh[1] * 10 + sh[0], "PLACE"))
            return ["PLACE", k, n]
    st["on"] = False                               # run done: back to the route
    return None


def _tier_idle_home(TP, R, u, p, inv, tiles, day, hour):''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

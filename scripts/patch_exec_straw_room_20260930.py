"""v18z -> v18za: sd_straw_sale room guard (default on inside the rule: sd_straw_sale "room": 1; the rule itself stays off by
default, so v18za with sd_straw_sale unset behaves exactly like v18z / v18y).

Review of v18z (2026-09-30, low severity, confirmed by reading the code): the margin hold rule can hold up to ~40
strawberries overnight, and the offline evaluation (scripts/strawberry_sale_eval_20260930.py run_policy) makes room for
them by force-selling the rule's own strawberries when the shed would overflow at midnight (786 of 792 forced units at
hour 23). The executor's midnight capacity block (sd_books_cap) instead (1) sells the CHEAPEST books products first
(eggs, feed wheat, fertilizer, carrots before any strawberry) and (2) computes its load only when today's tier plan
exists - `load_ = (shed + carried + harv_left if TPc_.get("day") == day else 0)` binds the conditional to the whole sum -
so on a day the tier plan is off nothing is sold and the midnight dump deletes the overflow.

Guard: on rule days from hour 21, before sd_books_cap, the projected midnight load (shed + everything the units carry +
the tier plan's remaining harvest when that plan is today's, minus this tick's planned sells) is computed without
depending on the tier plan; the excess over 100 - sd_tier_dump_buffer is sold from the rule's strawberries first (the
shed stock after this step's arrivals), exactly the evaluated behaviour. sd_books_cap then sees the smaller excess.

usage: patch_exec_straw_room_20260930.py  (writes agents/mgt_lead_kb115lt2_v18za.py from v18z)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18z.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18za.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


GUARD = '''            if ssale_cfg_ and _ssale_on(day) and hour >= 21 and int(ssale_cfg_.get("room", 1)):   # sd_straw_sale room guard (v18za)
                TPr_ = S.get("tier") or {}
                load_r_ = (sum(int(v or 0) for v in shed.values())
                           + sum(int(v or 0) for inv_ in invs for v in (inv_ or {}).values()))
                if TPr_.get("day") == day:
                    load_r_ += int(TPr_.get("_harv_left", 0) or 0)
                load_r_ -= sum(int(o_[2]) for o_ in orders if o_[0] == "SELL") + sum(o_[2] for _, o_ in front_)
                ex_r_ = load_r_ - (100 - int(CFG["sd_tier_dump_buffer"]))
                if ex_r_ > 0:
                    av_r_ = _ssale_shed_after(S, obs, shed, invs, pos, farm["tiles"])
                    done_r_ = sum(o_[2] for _, o_ in front_ if o_[1] == "STRAWBERRY")
                    k_r_ = min(max(0, int(av_r_) - int(done_r_)), int(ex_r_))
                    if k_r_ > 0:
                        hit_r_ = next((x for x in front_ if x[1][1] == "STRAWBERRY"), None)
                        if hit_r_:
                            hit_r_[1][2] += k_r_
                        else:
                            front_.append((0, ["SELL", "STRAWBERRY", k_r_]))
                        S["log"]["straw_sale_room_units"] += k_r_
'''


def main():
    s = SRC.read_text(encoding="utf-8")
    anchor = '''            if CFG["sd_books_cap"] and hour >= 21:     # shed capacity at midnight
'''
    s = sub(s, anchor, GUARD + anchor)
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

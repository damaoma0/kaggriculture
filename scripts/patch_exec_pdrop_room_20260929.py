"""v18g -> v18h: sd_tier_pdrop_room (default off). User 2026-09-29: "bring-back runs and prices strongly correlate".

Measured (item traces, 8 leader worlds): the harvest-to-sale lag costs us -4.1k a game vs the leader (wool -1.8k, milk
-1.0k, melons -0.65k, strawberries -0.45k); a dumped unit would have sold for +14.7 (wool) / +3.9 (strawberries, ~+50 on
crash days) / +4.0 (milk) more on its harvest day. The mid-day drop (sd_tier_pdrop) almost never fires: on one game 651 of
972 route checks stop at "full" (the route already ends at 24), 320 candidates at "end" (the drop pushes it past 24),
0 strawberry drops - it only uses free time and never gives up a job, whereas DSM goes home after its far strawberry
block instead of doing its cheapest remaining jobs.

sd_tier_pdrop_room {product: value per unit}: the mid-day drop may also (1) sit at the route's end and (2) make room by
removing the route's cheapest optional ops (never mandatory ones, never on dawn legs) until the route ends by 24 with no
added lateness or supply failure; a drop is taken only when its value (units x value per unit) exceeds the planner's
value of what it removed, best (value - removed) first.

usage: patch_exec_pdrop_room_20260929.py  (writes agents/mgt_lead_kb115lt2_v18h.py from v18g)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18g.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18h.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_tier_hold_price": None,''', '''    "sd_tier_pdrop_room": None,  # {product: value per unit} (user 2026-09-29 bring-back: the mid-day drop stops at
    # "full" / "end" on 2/3 of routes and never gives up a job; DSM goes home after its far strawberry block): the drop may
    # sit at the route's end and make room by removing the route's cheapest optional ops, taken only when units x value
    # per unit exceeds the removed value
    "sd_tier_hold_price": None,''')
    old = '''            if ev0[0] >= 24:
                why["full"] += 1
                break
            stops = sg["stops"]
            best = None
            carry = Counter()
            for pos in range(1, len(stops)):            # mid-route only: the hand goes back out after the drop'''
    new = '''            room_ = CFG.get("sd_tier_pdrop_room")
            if ev0[0] >= 24 and not room_:
                why["full"] += 1
                break
            stops = sg["stops"]
            best = None
            carry = Counter()
            for pos in range(1, len(stops) + (1 if room_ else 0)):   # mid-route (room mode: the route's end too)'''
    s = sub(s, old, new)
    old = '''                if x.get("dawn") or stops[pos].get("dawn"):
                    continue
                want = sorted('''
    new = '''                if x.get("dawn") or (pos < len(stops) and stops[pos].get("dawn")):
                    continue
                want = sorted('''
    s = sub(s, old, new)
    old = '''                a, b = x["tile"], stops[pos]["tile"]
                sh = min(_TIER_SHED_I, key=lambda q: (D[a][q] + D[q][b], q))
                dl = {"tile": sh, "ops": [_tier_op(["DELIVER", p], True, 0.0, 2) for _, p in want], "rel": 0, "turn": True, "pdrop": True}
                trial = stops[:pos] + [dl] + stops[pos:]
                ev = _tier_eval(sg, trial, want_hours=True)
                add = ev[0] - ev0[0]
                if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3] or add > cap:'''
    new = '''                a = x["tile"]
                b = stops[pos]["tile"] if pos < len(stops) else a
                sh = min(_TIER_SHED_I, key=lambda q: (D[a][q] + D[q][b], q))
                dl = {"tile": sh, "ops": [_tier_op(["DELIVER", p], True, 0.0, 2) for _, p in want], "rel": 0, "turn": True, "pdrop": True}
                trial = stops[:pos] + [dl] + stops[pos:]
                ev = _tier_eval(sg, trial, want_hours=True)
                add = ev[0] - ev0[0]
                if room_:                                 # make room: drop the cheapest optional ops until it fits
                    dv_ = sum(u * float(room_.get(p, 0) or 0) for u, p in want)
                    rm_ = 0.0
                    opt_ = sorted(((float(o["v"]), i_, j_) for i_, y in enumerate(trial) if y is not dl and not y.get("dawn")
                                   and not y.get("turn") and not y.get("deliver") for j_, o in enumerate(y["ops"]) if not o["m"]),
                                  key=lambda z: z[0])
                    drop_ = set()
                    while (ev[0] > 24 or ev[1] > ev0[1]) and opt_:
                        v_, i_, j_ = opt_.pop(0)
                        if rm_ + v_ >= dv_:
                            break
                        drop_.add((i_, j_))
                        rm_ += v_
                        t2_ = []
                        for i2_, y in enumerate(trial):
                            ops2_ = [o for j2_, o in enumerate(y["ops"]) if (i2_, j2_) not in drop_]
                            if ops2_ or y is dl:
                                t2_.append(dict(y, ops=ops2_) if len(ops2_) != len(y["ops"]) else y)
                        ev = _tier_eval(sg, t2_, want_hours=True)
                        if ev[0] <= 24 and ev[1] <= ev0[1]:
                            trial = t2_
                            break
                    if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3] or rm_ >= dv_:
                        why["room_" + ("end" if ev[0] > 24 else "late" if ev[1] > ev0[1] else "supply" if ev[3] > ev0[3] else "value")] += 1
                        continue
                    if max(h for (b_, c_, h) in ev[4] if c_[0] == "DELIVER") > hmax:
                        why["hmax"] += 1
                        continue
                    why["room_ok"] += 1
                    sc = (dv_ - rm_, u_)
                    if best is None or sc > best[0]:
                        best = (sc, trial, want, ev[0] - ev0[0])
                    continue
                if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3] or add > cap:'''
    s = sub(s, old, new)
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

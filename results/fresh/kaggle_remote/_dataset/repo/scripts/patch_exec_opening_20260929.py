"""Executor changes for a hand-planned opening played by our own executor from day 0 (user 2026-09-29). Default OFF.

  sd_place_feed         a planned animal placement (BUILD + PLACE) also FEEDs the new animal at the same stop. Without it
                        an animal is never fed on the day it is placed: it starts the next day one missed feed from
                        escaping (DSM's plan played from day 0 lost 2 of 3 sheep at dawn of day 2; V13's day 6-8 newborn
                        deaths are the same mechanism).
  sd_fix_d0 / sd_fix_d1 the day window of the A1 feed fixes (wheat priority, residual wheat retry, unfunded-build guard),
                        hard-coded 6..10 when the opening was a replayed tape (defaults 6 / 10 keep that).

usage: patch_exec_opening_20260929.py <source.py> <output.py>"""
import sys
from pathlib import Path


def patch(s):
    def rep(old, new, n=1):
        nonlocal s
        assert s.count(old) == n, (s.count(old), old[:90])
        s = s.replace(old, new)

    rep('''    "sd_mel_last": 12,''', '''    "sd_place_feed": 0,       # 1: a planned animal placement also feeds the new animal at the same stop
    "sd_fix_d0": 6,           # day window of the A1 feed fixes (wheat priority / retry / unfunded-build guard)
    "sd_fix_d1": 10,
    "sd_mel_last": 12,''')
    rep("6 <= day <= 10", 'int(CFG["sd_fix_d0"]) <= day <= int(CFG["sd_fix_d1"])', 4)
    rep('''                if len(job) > 2 and job[2] in ANIMALS:
                    new += [_tier_op(["PLACE", job[2]], True, float(CFG["plan_value"]), 2)]''',
        '''                if len(job) > 2 and job[2] in ANIMALS:
                    new += [_tier_op(["PLACE", job[2]], True, float(CFG["plan_value"]), 2)]
                    if CFG["sd_place_feed"]:           # fed on its placement day (else one miss from escaping tomorrow)
                        new += [_tier_op(["FEED"], True, 0.0, 2)]''')
    # sd_tier_pdrop with FERTILIZER: a pen's COLLECT_FERTILIZER puts 1 unit in the hand (engine), counted as carried so the
    # route can drop it at a shed tile it passes (DSM's farmer collects at hour 0 and sells at hour 2: the day's first cash)
    rep('''                if any(o["c"][0] == "HARVEST" for o in x["ops"]) and not any(o["c"][0] == "PLACE_HARVEST" for o in x["ops"]):
                    p = prod_of(t)
                    if p in need:
                        carry[p] += int(t.get("yield_units", 0) or 0)''',
        '''                if any(o["c"][0] == "HARVEST" for o in x["ops"]) and not any(o["c"][0] == "PLACE_HARVEST" for o in x["ops"]):
                    p = prod_of(t)
                    if p in need:
                        carry[p] += int(t.get("yield_units", 0) or 0)
                if "FERTILIZER" in need and any(o["c"][0] == "COLLECT_FERTILIZER" for o in x["ops"]):
                    carry["FERTILIZER"] += 1''')
    # the drop quota reads DSM's recorded sales only for the lag gate; with sd_tier_pdrop_need 0 it must not read them
    # (the semantic stack's interface guard refuses any DSM data: o12 stopped at day 1 on "dsm_data:sales")
    rep('''    books = set(CFG["sd_books_sell"] or ())
    cum = _books_cum(S)
    shed0 = S.get("_shed_h0") or {}''', '''    books = set(CFG["sd_books_sell"] or ())
    cum = _books_cum(S) if int(CFG["sd_tier_pdrop_need"]) else None
    shed0 = S.get("_shed_h0") or {}''')
    # sd_tier_pdrop_dawn (2026-09-29): the mid-day drop skipped every position touching a dawn stop, but the pens'
    # fertilizer is collected in the dawn round (pens next to the shed); on days 6-8 all of it rode in hands until the
    # midnight dump and sold the next morning, a permanent one-day lag on the main early income (500-1,100 a day) in
    # the cash-starved window. With the flag a drop may follow the last dawn stop (never inside the dawn round).
    rep('''    "sd_fix_d1": 10,''', '''    "sd_fix_d1": 10,
    "sd_tier_pdrop_dawn": 0,  # 1: a mid-day drop may follow the last stop of the dawn round''')
    rep('''                if x.get("dawn") or stops[pos].get("dawn"):
                    continue''', '''                if (x.get("dawn") and not CFG["sd_tier_pdrop_dawn"]) or stops[pos].get("dawn"):
                    continue''')
    # sd_tier_pdrop_trim (2026-09-29): the fertilizer collects are optional fill jobs, so a drop planned before the fills
    # finds nothing to carry and one planned after them finds every route packed to 24 h ("full"); on days 6-8 all
    # fertilizer rode in hands until midnight. With the flag a drop that would end the route after 24 h removes the
    # route's last all-optional stops until it fits (never a stop with a mandatory op, never one before the drop).
    rep('''    "sd_tier_pdrop_dawn": 0,''', '''    "sd_tier_pdrop_dawn": 0,
    "sd_tier_pdrop_trim": 0,  # 1: a mid-day drop may push out the route's last all-optional stops to fit in 24 h''')
    rep('''            if ev0[0] >= 24:
                why["full"] += 1
                break
            stops = sg["stops"]''', '''            if ev0[0] >= 24 and not CFG["sd_tier_pdrop_trim"]:
                why["full"] += 1
                break
            stops = sg["stops"]''')
    rep('''                trial = stops[:pos] + [dl] + stops[pos:]
                ev = _tier_eval(sg, trial, want_hours=True)
                add = ev[0] - ev0[0]''', '''                trial = stops[:pos] + [dl] + stops[pos:]
                ev = _tier_eval(sg, trial, want_hours=True)
                if CFG["sd_tier_pdrop_trim"]:          # make room: drop the last all-optional stops after the drop
                    while ev[0] > 24 and len(trial) > pos + 1 and not any(o["m"] for o in trial[-1]["ops"]) \\
                            and not trial[-1].get("turn") and not trial[-1].get("place"):
                        trial = trial[:-1]
                        ev = _tier_eval(sg, trial, want_hours=True)
                    why["trimmed"] += int(len(trial) < len(stops) + 1)
                add = ev[0] - ev0[0]''')
    rep('''                if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3] or add > cap:''', '''                if ev[0] > 24 or ev[1] > ev0[1] or ev[3] > ev0[3] or (add > cap and not CFG["sd_tier_pdrop_trim"]):''')
    # sd_mel_greedy: the melon rule's partition search considers only the first 8 ripe tiles and is all-or-nothing: on
    # MGT's 12-melon board three tiles only the farmer can drop by the last hour, no partition is feasible, the rule
    # assigns NOTHING (50 s a call) and every melon falls to the ordinary planner (u16: harvests h9-h19, 41 melons in the
    # midnight dump). Greedy singletons: most-constrained tile first, to the free unit with the earliest drop; tiles no
    # unit can drop in time are left to the planner.
    rep('''    CFG["sd_mel_last"] = CFG.get("sd_mel_last", 12)''' if False else '''    "sd_fix_d1": 10,''', '''    "sd_fix_d1": 10,
    "sd_mel_greedy": 0,       # 1: the melon rule assigns single tiles greedily (see _tier_melon_greedy)''')
    rep('''def _tier_melon(day, tiles, units):''', '''def _tier_melon_greedy(day, tiles, units):
    """sd_mel_greedy: one ripe melon tile per unit, most-constrained tile first (fewest units that can drop it by
    sd_mel_last), each to the free unit with the lowest (cost, drop); tiles no free unit can drop in time are left out
    (normal harvest). Same return shape as _tier_melon."""
    ripe = [i for i in range(100) if _mel_ripe(_tile(tiles, i), day)]
    if not ripe or not units:
        return [], ripe
    last = int(CFG["sd_mel_last"])
    opts = {}
    for i in ripe:
        o = [_mel_block(p0, t0, [i], tiles, day) + (u,) for u, p0, t0 in units]
        opts[i] = sorted((x for x in o if x[0] <= last and x[1] != float("inf")), key=lambda x: (x[1], x[0]))
    used, asg, left = set(), [], []
    for i in sorted(ripe, key=lambda i: (len(opts[i]), opts[i][0][0] if opts[i] else 99)):
        pick = next((x for x in opts[i] if x[5] not in used), None)
        if pick is None:
            left.append(i)
            continue
        used.add(pick[5])
        asg.append((pick[5], list(pick[3]), pick[0], pick[4]))
    return asg, left


def _tier_melon(day, tiles, units):
    if CFG["sd_mel_greedy"]:
        return _tier_melon_greedy(day, tiles, units)''')
    return s


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    assert src.resolve() != out.resolve(), "refusing an in-place edit"
    s = patch(src.read_text(encoding="utf-8"))
    compile(s, str(out), "exec")
    out.write_text(s, encoding="utf-8", newline="\n")
    print("patched ->", out)

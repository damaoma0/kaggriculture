"""sd_tier_dawn_cash (2026-09-29, default off): cash-window dawn trips. On days [d0, d1] the learned dawn rule (DSM's old
version: pens on a shed tile, or one tile off with cows >= 6) also sends dawn trips to cow / sheep pens up to
sd_tier_dawn_cash_dist tiles from the shed with >= 3 units, and a dawn delivery may arrive by sd_tier_dawn_cash_by.
Day 8 (n18rc4 vs DSM 114436723): the farmer's dawn trip delivers one cow's milk (sold at hour 2), the second cow (farther
out) is harvested at hour 10 and its milk rides to midnight: 12 milk collected, 6 sold (the leaders 12 / 12); DSM sells
it all that morning, buys its 3rd quadrant on day 8 and plants 16-17 wheat there, we wait until day 9.

usage: patch_exec_dawn_cash_20260929.py <source.py> <output.py>"""
import sys
from pathlib import Path


def patch(s):
    def rep(old, new):
        nonlocal s
        assert s.count(old) == 1, old[:80]
        s = s.replace(old, new)
    rep('''    "sd_tier_dawn_by": 4,''', '''    "sd_tier_dawn_by": 4,
    "sd_tier_dawn_cash": None,   # [d0, d1]: cash-window dawn trips (farther cow / sheep pens, later delivery)
    "sd_tier_dawn_cash_dist": 3,
    "sd_tier_dawn_cash_by": 8,''')
    rep('''            elif d == 2 and sync2_ and an == "SHEEP" and 4 <= u < mh_:
                far_.append((2, -u, idx, an))''', '''            elif d == 2 and sync2_ and an == "SHEEP" and 4 <= u < mh_:
                far_.append((2, -u, idx, an))
            elif (CFG.get("sd_tier_dawn_cash") and int(CFG["sd_tier_dawn_cash"][0]) <= day <= int(CFG["sd_tier_dawn_cash"][1])
                  and 1 <= d <= int(CFG["sd_tier_dawn_cash_dist"]) and an in ("COW", "SHEEP") and u >= 3):
                cands.append((d, -u, idx, an))         # sd_tier_dawn_cash: the cash-window morning collection''')
    rep('''    if ev[4][nd - 1][2] > int(CFG["sd_tier_dawn_by"]):''', '''    by_ = int(CFG["sd_tier_dawn_by"])
    cw_ = CFG.get("sd_tier_dawn_cash")
    if cw_ and int(cw_[0]) <= int(_TIER_DAY[0] if _TIER_DAY else -1) <= int(cw_[1]):
        by_ = int(CFG["sd_tier_dawn_cash_by"])
    if ev[4][nd - 1][2] > by_:''')
    rep('''def _tier_dawn_ins(seg, bundle):''', '''_TIER_DAY = []                                    # sd_tier_dawn_cash: the day being planned (set in _tier_core)


def _tier_dawn_ins(seg, bundle):''')
    rep('''def _tier_core(S, L, st, day, tiles, rec, units, want, t_start):''', '''def _tier_core(S, L, st, day, tiles, rec, units, want, t_start):
    _TIER_DAY[:] = [day]''')
    return s


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    assert src.resolve() != out.resolve()
    s = patch(src.read_text(encoding="utf-8"))
    compile(s, str(out), "exec")
    out.write_text(s, encoding="utf-8", newline="\n")
    print("patched ->", out)

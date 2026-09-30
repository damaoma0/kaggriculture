"""sd_tier_pdrop_days (2026-09-29, default off): the mid-day drop (sd_tier_pdrop) only on days [d0, d1]. Days 6-10 are
cash-starved; the hands' milk / fertilizer / wool ride until the midnight drop and sell the next morning (day 8: 12 milk
collected, 6 sold vs the leaders' 12 / 12; 13 fertilizer collections, no drop), so DSM buys its 3rd quadrant and plants
16-17 wheat on day 8 while we wait until day 9. f6 (drops all season, fertilizer included) cost 4-5k because it sold the
fertilizer the routes fertilize with and trimmed jobs in every phase; this keeps the drop to the cash-starved window.

usage: patch_exec_pdrop_days_20260929.py <source.py> <output.py>"""
import sys
from pathlib import Path


def patch(s):
    def rep(old, new):
        nonlocal s
        assert s.count(old) == 1, old[:80]
        s = s.replace(old, new)
    rep('''    "sd_tier_pdrop_early": 0,''', '''    "sd_tier_pdrop_days": None,  # [d0, d1]: the mid-day drop only on these days (None: every day)
    "sd_tier_pdrop_early": 0,''')
    rep('''    prods = list(CFG["sd_tier_pdrop"] or ())
    if not prods:
        return 0''', '''    prods = list(CFG["sd_tier_pdrop"] or ())
    if not prods:
        return 0
    dw_ = CFG.get("sd_tier_pdrop_days")
    if dw_ and not (int(dw_[0]) <= int(day) <= int(dw_[1])):
        return 0''')
    return s


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    assert src.resolve() != out.resolve()
    s = patch(src.read_text(encoding="utf-8"))
    compile(s, str(out), "exec")
    out.write_text(s, encoding="utf-8", newline="\n")
    print("patched ->", out)

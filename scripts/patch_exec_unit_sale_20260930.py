"""v18zb -> v18zc: per-unit selling quantity for the margin hold rules (sd_straw_sale and sd_goods_sale option "unit": 1;
absent / 0 = v18zb's all-or-nothing decision, byte-identical behaviour).

User 2026-09-30 (from the wool / milk timeline viewer): DSM sells MEDIUM batches while the opponent still holds stock,
then SMALL batches while the price recovers; trickles when prices fall or when outnumbered. v18zb's rule tests only the
FIRST unit (its best hold gain at today's inventory) and then sells the whole stock or nothing, so it sells in lumps.
Unit mode sells units one at a time while the NEXT unit's best hold gain - quoted at the inventory raised by the units
already sold now, the same rival forecast and draws - stays <= theta (goods_eval.py / unit_rule.py make_unit_rule, the
2026-09-30 thread scratchpad). The first unit's test is v18zb's, so unit mode sells 0 exactly when v18zb holds.

Evidence (offline fixed-tick market simulator, rival frozen on its recorded ticks, exact engine pricing incl. the $1
floor, 9 DSM worlds, our n18rc127 supply; margin = our revenue of the good - the rival's, mean per world):
  WOOL        recorded -2,698 | all-or-nothing H24 theta4 same_tick 1.0 -2,157 | unit -2,026 (+131) | DSM's shares -1,793
  MILK        recorded   -737 | all-or-nothing H24 theta4 same_tick 0.5   -325 | unit   -201 (+124) | DSM's shares   -377
  STRAWBERRY  recorded -2,213 | all-or-nothing H24 theta4 same_tick 0.5 -1,484 | unit -1,371 (+113) | DSM's shares -1,634
CAVEATS as v18z / v18zb (market-only re-pricing of a frozen replay; the shed and the other goods at their recorded levels).

config: add "unit": 1 to the sd_straw_sale dict and / or to an item's sd_goods_sale dict.
usage: .venv/Scripts/python.exe scripts/patch_exec_unit_sale_20260930.py"""
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18zb.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18zc.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


HELPER = '''def _sale_unit_n(pc, I0, f, R0, step, Hh, ph, nsh, ctr, stc, theta, avail):
    """v18zc unit mode (sd_straw_sale / sd_goods_sale "unit"): the units to sell now = the largest n <= avail such that
    each of the first n units, quoted at the inventory raised by the units sold before it, has a best hold gain <= theta
    under the same rival forecast (hazard f x holdings R0) and town draws (nsh every 4 steps, ctr at the day start)."""
    n = 0
    while n < avail:
        R = R0
        p0 = pc(I0 + n)
        Ij, ext, best = I0 + n, 0.0, -1e9
        for j in range(Hh + 1):
            o = f[(step + j) % 24] * R
            R -= o
            sl = pc(Ij) - pc(Ij + 1)
            if j > 0 and (step + j) % 4 == ph:
                g = pc(Ij) - p0 - ext - stc * o * sl
                if g > best:
                    best = g
            ext += o * sl
            Ij += o - ((nsh if (step + j) % 4 == 0 else 0) + (ctr if (step + j) % 24 == 0 else 0))
        if best > theta:
            break
        n += 1
    return n


'''

# anchors (each must occur exactly once in v18zb)
A_SSALE_DEF = "def _ssale_n(S, obs, day, hour, avail):\n"
R_LINE = '    R = float(st.get("R", 0) or 0) + (float(st.get("ripe", 0) or 0) if cfg.get("ripe") else 0.0)\n'
S_TAIL = '''    if best <= theta:
        lg["straw_sale_sell_ticks"] += 1
        return int(avail)
'''
G_TAIL = '''    if best <= theta:
        lg["goods_sale_sell_ticks_" + item] += 1
        return int(avail)
'''
R0_INS = "    R0_ = R                                          # v18zc unit mode: the holdings before the scan\n"
S_UNIT = '''    if cfg.get("unit"):                            # v18zc: sell units one at a time (the first unit's test is the above)
        n_ = _sale_unit_n(_ssale_pc, I0, f, R0_, step, Hh, ph, nsh, 1, stc, theta, int(avail))
        if n_ > 0:
            lg["straw_sale_sell_ticks"] += 1
        if n_ < int(avail):
            lg["straw_sale_hold_ticks"] += 1
            lg["straw_sale_hold_units"] += int(avail) - n_
        lg["straw_sale_unit_units"] += n_
        return n_
'''
G_UNIT = '''    if cfg.get("unit"):                            # v18zc: sell units one at a time (the first unit's test is the above)
        n_ = _sale_unit_n(lambda x_: _gsale_pc(item, x_), I0, f, R0_, step, Hh, ph, nsh, ctr, stc, theta, int(avail))
        if n_ > 0:
            lg["goods_sale_sell_ticks_" + item] += 1
        if n_ < int(avail):
            lg["goods_sale_hold_ticks_" + item] += 1
            lg["goods_sale_hold_units_" + item] += int(avail) - n_
        lg["goods_sale_unit_units_" + item] += n_
        return n_
'''


def main():
    src = SRC.read_text(encoding="utf-8")
    assert "_sale_unit_n" not in src
    s = sub(src, A_SSALE_DEF, HELPER + A_SSALE_DEF)
    # R0_ after each R line (the first is in _ssale_n, the second in _gsale_n)
    assert s.count(R_LINE) == 2
    i1 = s.index(R_LINE)
    s = s[:i1 + len(R_LINE)] + R0_INS + s[i1 + len(R_LINE):]
    i2 = s.index(R_LINE, i1 + len(R_LINE) + len(R0_INS))
    s = s[:i2 + len(R_LINE)] + R0_INS + s[i2 + len(R_LINE):]
    s = sub(s, S_TAIL, S_UNIT + S_TAIL)
    s = sub(s, G_TAIL, G_UNIT + G_TAIL)
    # placement: the unit branches sit inside their own functions, after the scans
    i_s, i_g = s.index("def _ssale_n("), s.index("def _gsale_n(")
    assert i_s < s.index(S_UNIT) < s.index("def _ssale_track(", i_s) if "def _ssale_track(" in s[i_s:] else True
    assert i_s < s.index(S_UNIT) < i_g < s.index(G_UNIT), "unit branches out of place"
    assert s.index(R0_INS, i_s) < s.index(S_UNIT) and s.index(R0_INS, i_g) < s.index(G_UNIT)
    DST.write_text(s, encoding="utf-8", newline="\n")
    # removing the insertions gives v18zb back byte for byte
    back = s.replace(HELPER, "", 1).replace(R0_INS, "").replace(S_UNIT, "", 1).replace(G_UNIT, "", 1)
    assert back == src, "removing the inserted blocks does not give v18zb back"
    py_compile.compile(str(DST), doraise=True)
    print("wrote", DST, "(4 insertion sites, %d -> %d lines; compiles; reverts to v18zb byte for byte)"
          % (src.count("\n"), s.count("\n")))


if __name__ == "__main__":
    main()

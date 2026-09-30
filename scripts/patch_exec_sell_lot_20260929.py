"""v18m -> v18n: sd_sell_lot (default off) - at most N units of a product sold per step outside the books seller.

Exact day-11 benchmark, 9 current-DSM 3-quadrant games (item traces, scratchpad sale_hours.py): we sell 54% of our wool
at hour 1 @83 (the midnight dump, sold on arrival in one order), DSM spreads its wool over the day (hours 2-7 @146-150,
20% at 20-23 @107), the opponent sells 12% at 4-7 @150 and 17% at 8-11 @151. Wool's glut curve is steep (sq 3.2 x base
over T=105: ~-12 a unit near +55 stock), so one big order walks our own price down; in 114537918's crash we sold 20 @4
on day 19 where DSM sold 4-10 a day. Wool stays off the pace seller (n18rc8: +608 for selling on arrival).

sd_sell_lot {product: N}: the arrival / quota sale of a listed product is at most N units a step (the rest stays in the
shed for the next steps); the endgame sells everything as before.

usage: patch_exec_sell_lot_20260929.py  (writes agents/mgt_lead_kb115lt2_v18n.py from v18m)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18m.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18n.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_glut_live": 0,''', '''    "sd_sell_lot": None,      # {product: N} (exact benchmark: 54% of our wool sold at hour 1 in one order @83, DSM spreads it
    # over the day @146-150): the arrival / quota sale of a listed product is at most N units a step
    "sd_glut_live": 0,''')
    s = sub(s, '''            n = min(have, quota)
        if n > 0:
            sells.append(["SELL", p, int(n)])''', '''            n = min(have, quota)
            lot_ = (CFG.get("sd_sell_lot") or {}).get(p)
            if lot_ is not None:
                n = min(n, int(lot_))              # sd_sell_lot: small lots, the rest waits for the next steps
        if n > 0:
            sells.append(["SELL", p, int(n)])''')
    s = sub(s, '''        fr_ = [["SELL", p_, int(shed.get(p_, 0) or 0)] for p_ in TPh_["h0_front"] if int(shed.get(p_, 0) or 0) > 0]''',
            '''        fr_ = [["SELL", p_, int(shed.get(p_, 0) or 0)] for p_ in TPh_["h0_front"] if int(shed.get(p_, 0) or 0) > 0]
        if CFG.get("sd_sell_lot_front"):           # sd_sell_lot also caps the hour-0 front sale (the midnight dump)
            fr_ = [["SELL", o_[1], min(o_[2], int((CFG.get("sd_sell_lot") or {}).get(o_[1], o_[2])))] for o_ in fr_]''')
    s = sub(s, '''    "sd_glut_live": 0,''', '''    "sd_sell_lot_front": 0,   # 1: sd_sell_lot also caps the sd_h0_front hour-0 sale (where 54% of our wool is sold)
    "sd_glut_live": 0,''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

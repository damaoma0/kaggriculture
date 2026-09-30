"""v18zc -> v18zd: sd_sell_front (default None) - a list of goods whose SELL orders go to the head of the market queue, in
that order, after every other queue decision of the step (the step-718 sell-all is unchanged).

User 2026-09-30 (timeline viewer): "different prices at the same tick for our sale vs opponent sell - why?" The engine
cuts each list to 10 orders and processes them by INDEX: all index-0 orders first (HIRE / BUY_LAND of that index, then a
per-unit lockstep over both players' index-0 orders: both quote at the same pre-commit inventory, seat 0 commits first),
then index 1, ... Each unit sold raises the market inventory, so the side whose SELL of a good sits at a LOWER index sells
all its units first at the higher prices. Measured on the b2b games (ticks where both sides sold the same good):
  DSM  WOOL behind the rival's order 0% (same index 87%, ahead 13%); MILK behind 1%; STRAWBERRY behind 23%
  ours WOOL behind 33% (-$23.4 a unit, our lots 9.0 vs their 2.5 units); MILK behind 44% (-$7.0); STRAWBERRY behind 20%
(sd_straw_sale forces STRAWBERRY to index 0 and our hires / buys / other sells precede the animal goods; the rivals keep
WOOL at index 0.) Exact re-pricing with our recorded units per tick moved to index 0 (fixed-tick market simulator, rival
frozen): n18rc127 supply, 9 worlds, margin per game MILK +362, WOOL +92, STRAWBERRY +83; n18rc223d (2 worlds) WOOL +360;
DSM's own supply +2 (WOOL) / +36 (MILK) - it already sells them first. Upper bound: only one good can sit at index 0.

config sd_sell_front ["WOOL", "MILK", "STRAWBERRY"] (fixed order) or {"auto": ["WOOL", "MILK", "STRAWBERRY"]} (user:
"high volatility goods and items where the opponent has the largest amount of stock could go first": sorted by our units
x the rival's tracked holdings (sd_straw_sale / sd_goods_sale trackers) x the price drop one unit causes at today's market
stock); None = off.
usage: .venv/Scripts/python.exe scripts/patch_exec_sell_front_20260930.py"""
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18zc.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18zd.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


CFG_ANCHOR = '    "sd_goods_sale": None,'
CFG_INS = ('    "sd_sell_front": None,    # v18zd (2026-09-30; see scripts/patch_exec_sell_front_20260930.py) ["WOOL", "MILK", '
           '"STRAWBERRY"]: these goods\' SELL orders go to the queue head in this order after every other queue decision '
           '(the rivals keep WOOL at index 0; behind them our units sell lower). None = off\n')
FINAL = '    if CFG["sd_final_sell_all"] and int(_g(obs, "step", 0)) >= 718:\n'
FRONT = '''    fo_ = CFG.get("sd_sell_front")                 # v18zd: goods' SELLs to the queue head (the lockstep runs by index)
    if fo_ and int(_g(obs, "step", 0)) < 718:
        if isinstance(fo_, dict):                  # {"auto": [goods]}: by our units x the rival's tracked stock x the
            inv_f_ = dict(_g(_g(obs, "market", {}), "inventory", {}) or {})   # price drop a unit causes now
            def _fkey(o_):
                p_ = o_[1]
                R_ = float(((S.get("_ssale") or {}).get("R", 0) if p_ == "STRAWBERRY"
                            else (((S.get("_gsale") or {}).get(p_) or {}).get("R", 0))) or 0)
                x_ = float(int(inv_f_.get(p_, _MKT_I0)))
                sl_ = _gsale_pc(p_, x_) - _gsale_pc(p_, x_ + 1) if p_ in _MKT_PARAMS else 0.0
                return (int(o_[2]) * R_ * sl_, int(o_[2]) * float(prices.get(p_, 0) or 0))
            head_ = sorted([o_ for o_ in orders if o_[0] == "SELL" and o_[1] in (fo_.get("auto") or [])], key=_fkey,
                           reverse=True)
        else:
            head_ = [o_ for p_ in fo_ for o_ in orders if o_[0] == "SELL" and o_[1] == p_]
        if head_ and orders[:len(head_)] != head_:
            orders = head_ + [o_ for o_ in orders if not any(o_ is x_ for x_ in head_)]
            S["log"]["sell_front_moves"] += 1
'''


def main():
    src = SRC.read_text(encoding="utf-8")
    assert "sd_sell_front" not in src
    s = sub(src, CFG_ANCHOR, CFG_INS + CFG_ANCHOR)
    s = sub(s, FINAL, FRONT + FINAL)
    DST.write_text(s, encoding="utf-8", newline="\n")
    back = s.replace(CFG_INS, "", 1).replace(FRONT, "", 1)
    assert back == src, "removing the inserted blocks does not give v18zc back"
    py_compile.compile(str(DST), doraise=True)
    print("wrote", DST, "(2 insertions; compiles; reverts to v18zc byte for byte)")


if __name__ == "__main__":
    main()

"""v18l -> v18m: sd_glut_live (default off) - the glut service rule (sd_glut_stop) follows the quote both ways.

Exact day-11 benchmark (9 current-DSM 3-quadrant games, n18rc8x from DSM's own day-11 state vs DSM continuing, item traces
with the day-end animal state, scratchpad herd_abs.py): DSM feeds / cares 48-71% of its cows on days the dawn milk quote
is under 100 and 88-98% above it (we 56-98%, 81-86% at 40-80), holds 1.7 milk per cow on the animal under 40 (we 0.8) and
3.0 wool per sheep under 50 (we 0.4). Its milk sells @88 (we @72, 149 vs 157 units), wool @113 (we @93, 84 vs 89 units):
supply leaves the glut days (milk quote 19-40 in our game, 51-82 in DSM's on days 17-23) for the late shops.

sd_glut_stop {product: price} made a product glutted for the rest of the season the first time its trailing mean quote
fell below the price (then no optional CARE and no optional FEED on non-production days). With sd_glut_live 1 the state is
re-evaluated every step: glutted while the trailing sd_glut_hours mean is below the price, served again once it is back.

usage: patch_exec_glut_live_20260929.py  (writes agents/mgt_lead_kb115lt2_v18m.py from v18l)"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "agents/mgt_lead_kb115lt2_v18l.py"
DST = ROOT / "agents/mgt_lead_kb115lt2_v18m.py"


def sub(s, old, new, n=1):
    assert s.count(old) == n, (old[:90], s.count(old))
    return s.replace(old, new)


def main():
    s = SRC.read_text(encoding="utf-8")
    s = sub(s, '''    "sd_glut_hours": 48,''', '''    "sd_glut_hours": 48,
    "sd_glut_live": 0,        # 1: sd_glut_stop is not sticky - a product is glutted while its trailing mean quote is below
    # the price and served again once it recovers (DSM, exact day-11 benchmark: cows fed ~50-70% under milk 100, ~95% above)''')
    s = sub(s, '''            if len(h_) >= int(CFG["sd_glut_hours"]) and k_ not in gl_ and sum(x[1] for x in h_) / len(h_) < float(px_):
                gl_[k_] = day''', '''            if len(h_) >= int(CFG["sd_glut_hours"]) and k_ not in gl_ and sum(x[1] for x in h_) / len(h_) < float(px_):
                gl_[k_] = day
            elif int(CFG.get("sd_glut_live", 0) or 0) and k_ in gl_ and h_ and sum(x[1] for x in h_) / len(h_) >= float(px_):
                gl_.pop(k_, None)                      # sd_glut_live: served again once the quote recovers''')
    DST.write_text(s, encoding="utf-8")
    print("wrote", DST)


if __name__ == "__main__":
    main()

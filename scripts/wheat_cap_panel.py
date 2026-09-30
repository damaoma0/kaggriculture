"""KW/KWd thread: panel-wide totals for the wheat h23-sell / morning-buy log counters (wheat_h23_sold,
wheat_h23_buy_capped, wheat_h23_room_sold) via the agent's own S["log"] Counter, read through sys.settrace on
_market()'s return (no behavior change). Requires a full game run per world (uses scripts/run_arms.py's machinery).

usage: wheat_cap_panel.py <arm> [spec.json] -> prints per-world and total log counters for that arm over panel13.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import sector_run as SR  # noqa: E402
import xfix_run as X  # noqa: E402
import run_arms as RA  # noqa: E402
from run_arms import PANEL13  # noqa: E402
from collections import Counter  # noqa: E402

SR.setup()

CUR = {}


def make_global_trace(target_file):
    def local_trace(frame, event, arg):
        if event == 'return' and frame.f_code.co_name == '_market':
            S_ = frame.f_locals.get('S') or {}
            log_ = S_.get('log') or {}
            CUR['h23_sold'] = log_.get('wheat_h23_sold', 0)
            CUR['h23_capped'] = log_.get('wheat_h23_buy_capped', 0)
            CUR['h23_room_sold'] = log_.get('wheat_h23_room_sold', 0)
        return local_trace

    def global_trace(frame, event, arg):
        if event == 'call' and frame.f_code.co_name == '_market' and frame.f_code.co_filename == target_file:
            return local_trace
        return None
    return global_trace


def traced_loader(path, tag):
    mod = X_orig_load(path, tag)
    target_file = str(ROOT / path)
    sys.settrace(make_global_trace(target_file))
    return mod


X_orig_load = X.load_module
X.load_module = traced_loader

if __name__ == '__main__':
    arm = sys.argv[1]
    if len(sys.argv) > 2:
        RA.register(json.loads(Path(sys.argv[2]).read_text(encoding='utf-8')))
    totals = Counter()
    for game in PANEL13:
        CUR.clear()
        CUR.update(h23_sold=0, h23_capped=0, h23_room_sold=0)
        res = SR.run_one(('multi', game, arm, 19))
        sys.settrace(None)
        ep = game.split(':')[1]
        print(ep, dict(CUR), 'final money', res[3])
        for k, v in CUR.items():
            totals[k] += v
    print('TOTAL', dict(totals))

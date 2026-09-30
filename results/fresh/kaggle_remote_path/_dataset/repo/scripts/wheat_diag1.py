"""KW thread diagnostic: trace agents/mgt_lead_sector_wheat.py's _market() reserve/sell/buy decisions for WHEAT,
hour by hour, for one panel world under a given arm (default K5b). Read-only: does not change agent behavior.

usage: wheat_diag1.py <team:ep> [arm] [days] [spec.json] -> writes JSON log to
  results/fresh/threads_20260928/wheat/diag_<arm>_<ep>.json
  spec.json (optional): a run_arms.py-style spec to register custom arms (e.g. KWd1) before running.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import sector_run as SR  # noqa: E402
import xfix_run as X  # noqa: E402
import run_arms as RA  # noqa: E402

SR.setup()

LOG = []


def make_global_trace(target_file):
    def local_trace(frame, event, arg):
        if event == 'return' and frame.f_code.co_name == '_market':
            loc = frame.f_locals
            reserve = loc.get('reserve') or {}
            shed = loc.get('shed') or {}
            carried = loc.get('carried') or {}
            demand = loc.get('demand') or {}
            sells = loc.get('sells') or []
            wheat_buy = loc.get('wheat_buy') or []
            farm = loc.get('farm') or {}
            n_anim = sum(1 for r in farm.get('tiles', []) for t in r
                         if isinstance(t, dict) and 'animal' in t)
            sell_w = sum(o[2] for o in sells if o[1] == 'WHEAT')
            S_ = loc.get('S') or {}
            log_ = S_.get('log') or {}
            TPw_ = loc.get('TPw_') or {}
            LOG.append(dict(
                day=loc.get('day'), hour=loc.get('hour'), endgame=loc.get('endgame'),
                n_anim=n_anim, n_plants=loc.get('n_plants'),
                shed_wheat=shed.get('WHEAT', 0), carried_wheat=carried.get('WHEAT', 0),
                demand_wheat=demand.get('WHEAT', 0), reserve_wheat=reserve.get('WHEAT', 0),
                sell_wheat_order=sell_w, buy_wheat_order=(wheat_buy[0][2] if wheat_buy else 0),
                cash=loc.get('cash'), short=loc.get('short'),
                tier_wheat_buy_planned=TPw_.get('wheat_buy'), tier_wheat_bought=TPw_.get('wheat_bought'),
                final_buy_k=loc.get('k_'), room=loc.get('room_'),
                cum_h23_sold=log_.get('wheat_h23_sold', 0), cum_h23_buy_capped=log_.get('wheat_h23_buy_capped', 0),
                money=loc.get('money'),
            ))
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
    game = sys.argv[1] if len(sys.argv) > 1 else '16730612:112444381'
    arm = sys.argv[2] if len(sys.argv) > 2 else 'K5b'
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 19
    if len(sys.argv) > 4:
        RA.register(json.loads(Path(sys.argv[4]).read_text(encoding='utf-8')))
    res = SR.run_one(('multi', game, arm, days))
    sys.settrace(None)
    print('RESULT', res)
    out_dir = ROOT / 'results/fresh/threads_20260928/wheat'
    out_dir.mkdir(parents=True, exist_ok=True)
    ep = game.split(':')[1]
    out = out_dir / f'diag_{arm}_{ep}.json'
    out.write_text(json.dumps(LOG), encoding='utf-8')
    print('wrote', out, len(LOG), 'records')

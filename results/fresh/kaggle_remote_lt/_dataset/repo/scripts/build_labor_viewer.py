"""Season viewer (days 11-29) of one panel world: the leader's recorded game vs our arm's stream, reusing the day12
side-by-side viewer (build_day12_side_by_side.py: its engine replay, frames, Follow / Regions / Assigned views and HTML
template) for worlds that have no T-tape or xopen ledger. The 'T' comparison slot shows the same arm from day 12.
Writes its own files, never the shared day12 viewer: viz/labor_<ep>.html and results/fresh/labor_viz/<ep>.json.
usage: build_labor_viewer.py team:ep [ARM[,ARM...]]   (default kb78; stream dirs results/fresh/day12_viz/<arm>_streams)"""
import os
import sys
from pathlib import Path

ARMS = (sys.argv[2] if len(sys.argv) > 2 else 'kb78').lower()   # comma list: the first fills the 'T' slot
ARM = ARMS.split(',')[0]
os.environ['VIEWER_LAST_DAY'] = os.environ.get('VIEWER_LAST_DAY', '29')
os.environ['VIEWER_ARMS'] = ARMS
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_day12_side_by_side as B  # noqa: E402
import upkeep_engine as UE           # noqa: E402


def process(game, ctx, dynamic_arms):
    team_id, ep_s = game.split(':')
    ep = int(ep_s)
    tape = UE.load_tape(team_id, ep)
    seat, seed, shops = tape['seat'], tape['seed'], tape['shops']
    lookup, table = {}, []

    def leader_provider(t):
        return UE.tape_action(tape['actions'], t), UE.tape_action(tape['opp_actions'], t)
    run_to = max(719, B.DAY13_MORNING)
    lf, lfinal, lopp = B.run_side(seed, shops, seat, leader_provider, B.DAY11_START, B.DAY12_END, run_to, lookup, table, ctx)
    result = dict(episode=ep, team=B.lead_g1.TEAM.get(team_id, team_id), seat=seat,
                  leader=dict(frames=lf, final=lfinal, target=tape['rewards'][seat]),
                  x=dict(available=False), fhmrp=dict(available=False))
    for arm in dynamic_arms:
        result[arm['key']] = B.build_exact_arm(arm['dir'], ep, tape, lf, seed, shops, seat, lookup, table, ctx)
    a = result.get(ARM) or {}
    af = a.get('frames') or lf
    off = B.DAY12_START - B.DAY11_START
    result['t'] = dict(frames=af[off:], final=a.get('final_at_d12end', 0), target=a.get('final_at_d12end', 0))
    result['verify'] = dict(leader_cash_ok=round(lfinal) == round(tape['rewards'][seat]), leader_cash=lfinal,
                            leader_target=tape['rewards'][seat], leader_opp_cash_ok=round(lopp) == round(tape['rewards'][1 - seat]),
                            t_cash_ok=True, t_cash=a.get('final_at_d12end', 0), t_target=a.get('final_at_d12end', 0),
                            t_opp_cash_ok=True, spot_leader=None, spot_t=None)
    result['tiles'] = table
    return result


def main():
    game = sys.argv[1]
    ep = game.split(':')[1]
    B.OUT_DIR = ROOT / 'results/fresh/labor_viz'
    B.OUT_HTML = ROOT / 'viz' / (f'labor_{ep}.html' if ARM == 'kb78' else f'labor_{ep}_{ARM}.html')
    B.check_memory('start')
    E = UE.engine()
    ctx = B.install_hooks(E)
    dyn = B.discover_dynamic_arms()
    print('arms:', [(d['key'], d['label']) for d in dyn], flush=True)
    r = process(game, ctx, dyn)
    a = r.get(ARM) or {}
    print(f"leader cash reproduced {r['verify']['leader_cash_ok']} ({r['verify']['leader_cash']:.0f} vs {r['verify']['leader_target']:.0f}); "
          f"{ARM} available {a.get('available')} handoff_ok {a.get('handoff_ok')} final {a.get('final_at_d12end')}", flush=True)
    B.OUT_DIR.mkdir(parents=True, exist_ok=True)
    import json
    (B.OUT_DIR / f'{ep}.json').write_text(json.dumps([r], separators=(',', ':')), encoding='utf-8')
    B.write_html([r], dyn)
    B.check_memory('after html write')


if __name__ == '__main__':
    main()

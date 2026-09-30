"""Trace the y2/lib584 wool anomaly on ladder world 111302438.

mgt_y2 = mgt_m1 (mgt_lib584) + the late-Yarn service layer (scripts/fragments/mgt_sheep.py
`_shp_topups`, `--sheep yarn_service=1,yarn_gate=1`). On this world the ladder panel shows y2
FEEDING AND CARING sheep more (ops_feed 42 vs 46 -- wait, actually fewer raw ops but MORE
yarn_service commitments and MORE ops_harvest: 6 vs 3) yet SELLING 13 FEWER wool units
(203 vs 216) for -3,166 revenue, while y2's margin is -4,324 against lib584's -1,171.

This script replays the recorded ladder game (data/ladder_panel/56368334/111302438.json.gz)
exactly as scripts/ladder_panel.py's `run()` does -- same seed, forced shops, the opponent's
recorded actions replayed via scripts/tape_vs_bench.py's `_play` -- but wraps OUR agent's step
function to log, every step, for every SHEEP tile on our board:
    yield_units, pending_care_bonus (bank), fed_today, cared_today, consecutive_unfed,
and every FEED/CARE/HARVEST command issued that step, tagged with the acting unit index and
whether that unit is one of the sheep-overlay's hidden hands (from the agent's own
`_SHP_STATES[seat]['own']`, read via `entry.__globals__` the same way ladder_panel.py reads
`_SHP_REPORT`/`_MGT_HISTORY`), plus the WOOL price, shed WOOL, per-unit WOOL inventories and any
SELL WOOL order that step.

Usage:
    .venv/Scripts/python.exe scripts/trace_y2_anomaly.py <agent_name> [out.json]

Runs ONE game. Checks available memory (need psutil >= 3.0 GB) before starting, per the
memory rule for this shared machine; run this once per agent, sequentially, never in parallel.
"""
import gzip
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

EPISODE_PATH = ROOT / 'data/ladder_panel/56368334/111302438.json.gz'
OUT_DIR = ROOT / 'results/fresh/newphase_20260923/y2_anomaly'


def wait_for_memory(min_gb=3.0, poll_s=30, tries=20):
    import psutil
    for _ in range(tries):
        avail = psutil.virtual_memory().available / 1e9
        if avail >= min_gb:
            return avail
        print(f'waiting for memory: {avail:.2f} GB available, need {min_gb:.1f}', flush=True)
        time.sleep(poll_s)
    raise RuntimeError('memory never freed up')


def sheep_snapshot(farm):
    out = []
    for y, row in enumerate(farm['tiles']):
        for x, c in enumerate(row):
            if isinstance(c, dict) and c.get('animal') == 'SHEEP':
                out.append(dict(x=x, y=y, yield_units=int(c.get('yield_units', 0) or 0),
                                 bank=int(c.get('pending_care_bonus', 0) or 0),
                                 fed=bool(c.get('fed_today')), cared=bool(c.get('cared_today')),
                                 unfed=int(c.get('consecutive_unfed', 0) or 0),
                                 placed_day=c.get('placed_day')))
    return out


def trace_agent(name):
    import tape_vs_bench as TV
    from ladder_panel import PASS
    from kaggle_environments import make
    from kaggle_environments.agent import get_last_callable
    from kaggle_environments.envs.kaggriculture import kaggriculture as E

    g = json.load(gzip.open(EPISODE_PATH, 'rt', encoding='utf-8'))
    seat, rec, shops, seed = g['seat'], g['opp_actions'], g['shops'], g['seed']
    ap = ROOT / 'agents' / f'{name}.py'
    entry = get_last_callable(ap.read_text(encoding='utf-8'), path=str(ap))
    G = entry.__globals__
    log = []

    def ours(obs, t):
        farm = obs['farms'][seat]
        before = sheep_snapshot(farm)
        action = entry(obs)
        state = (G.get('_SHP_STATES') or {}).get(seat) or {}
        own = sorted(state.get('own') or [])
        overlay_tiles = list(state.get('tiles') or [])
        culled = list(state.get('culled') or [])
        cmds = [list(action.get('farmer') or ['PASS'])] + [list(c or ['PASS']) for c in (action.get('hands') or [])]
        touches = []
        for idx, c in enumerate(cmds):
            if c and c[0] in ('FEED', 'CARE', 'HARVEST'):
                if idx == 0:
                    pos = tuple(farm['farmer'])
                else:
                    pos = tuple(farm['hands'][idx - 1]) if idx - 1 < len(farm['hands']) else None
                touches.append(dict(idx=idx, cmd=c[0], pos=pos, is_own=idx in own))
        market = action.get('market') or []
        sell_wool = sum(int(o[2]) for o in market if o and len(o) > 2 and o[0] == 'SELL' and o[1] == 'WOOL')
        prices = (obs.get('market') or {}).get('prices') or {}
        shed = obs['private'].get('shed') or {}
        invs = obs['private'].get('inventories') or []
        inv_wool = {i: int(v.get('WOOL', 0) or 0) for i, v in enumerate(invs) if int((v or {}).get('WOOL', 0) or 0) > 0}
        log.append(dict(step=t, day=t // 24, hour=t % 24, sheep=before, touches=touches, sell_wool=sell_wool,
                         wool_price=prices.get('WOOL'), shed_wool=int(shed.get('WOOL', 0) or 0), inv_wool=inv_wool,
                         own_hands=own, overlay_tiles=overlay_tiles, culled=culled, cash=farm['money'],
                         n_hands=len(farm['hands'])))
        return action

    players = [None, None]
    players[seat] = ours
    players[1 - seat] = lambda obs, t: (rec[t] if t < len(rec) and isinstance(rec[t], dict) and rec[t] else dict(PASS))
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    res = TV._play(E, env, players, seat, shops, None, None, seat)
    d, o = res['daily'][seat][-1], res['daily'][1 - seat][-1]
    summary = dict(agent=name, episode=g['episode'], seat=seat, final=res['final'][seat], rival=res['final'][1 - seat],
                   margin=res['final'][seat] - res['final'][1 - seat],
                   sold_wool=d['sold_units'].get('WOOL', 0), revenue_wool=d['revenue'].get('WOOL', 0),
                   overlay={k: v for k, v in (G.get('_SHP_REPORT') or {}).items() if isinstance(v, (int, float))})
    return summary, log


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'mgt_lib584'
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else (OUT_DIR / f'trace_{name}.json')
    wait_for_memory()
    summary, log = trace_agent(name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(summary=summary, log=log)), encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()

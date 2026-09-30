"""(2026-09-26, KQ plant deaths) Deterministic reproduction of a wall-clock bank stop: play RUN_ARM in-process (no files written) and switch the
tiered planner off at the end of step STOP exactly as _sd_step_end does when the estimated bank passes sd_bank_stop;
compare every action with the stored stream of STORED_ARM. STOP = -1: no forced stop (the clean run).
usage: bank_stop_repro.py RUN_ARM team:ep STORED_ARM STOP
  e.g. bank_stop_repro.py KQ1 16732748:112603263 KQ1 432 -> 455/455 steps identical to the stored (bank-stopped) KQ1 game"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_arms as RA  # noqa: E402
import sector_run as SR  # noqa: E402

arm, game, stored, stop = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
spec = json.loads((ROOT / 'results/fresh/threads_20260928/animal/spec.json').read_text(encoding='utf-8'))
RA.init(spec)
path, cfg = SR.ARMS[arm]
X = SR.X
import lead_g1  # noqa: E402
import lead_ledger  # noqa: E402

box = {}


def loader(_cfg):
    mod = X.load_module(path, 'fs_' + arm)
    orig = mod._sd_step_end

    def step_end(step, t_entry):
        orig(step, t_entry)
        if step == stop:
            L = mod._sd_state(mod._S)
            if not L['off']:
                L['off'] = True
                L['st']['last_error'] = 'FORCED bank stop at step %d' % step
    mod._sd_step_end = step_end
    h = X.Handoff(mod, dict(X.BASE, **cfg), X.tape_of(game), hand=X.D, stop=30 * 24)
    h.record = {}
    box['h'] = h
    return h


lead_g1._load_agent = loader
r = lead_ledger.play(game, 'ours')
ep = game.split(':')[1]
acts = json.load(open(ROOT / 'results/fresh/day12_viz' / (stored.lower() + '_streams') / f'{ep}.json'))['actions']
diff = [t for t in range(264, len(acts)) if json.dumps(box['h'].record.get(t, {}), sort_keys=True) !=
        json.dumps(acts[t] if isinstance(acts[t], dict) else {}, sort_keys=True)]
m = json.load(open(ROOT / 'results/fresh/sector_20260925/multi' / stored / f'{ep}.json'))
died = {d: dict(dd['died']) for d, dd in enumerate(r['days']) if dd['died'] and d >= 11}
st = ((getattr(box['h'].mod, '_S', None) or {}).get('sd') or {}).get('st') or {}
print(json.dumps(dict(run=arm, stored=stored, ep=ep, forced_stop=stop, final=[r['final'], r['opp_final']],
                      stored_final=m['money']['30'], steps_compared=len(acts) - 264, steps_differing=len(diff),
                      first_diff=diff[:3], died=died, stored_died={k: v for k, v in m['died'].items() if v},
                      last_error=st.get('last_error'), bank_used=st.get('bank_used'))))

"""Deploy smoke worlds for the search dispatcher (Kaggle side): scripts/lead_world_trace.py's run_one (the ladder-panel
harness: recorded seed, forced shops, the opponent's recorded actions, our build through Kaggle's loader) for every
(agent, episode), plus the agent's search-dispatch summary read from the loaded module after the game (the loader's
entry function is captured to reach its globals; lead_world_trace.py is not edited).

usage: search_dispatch_trace.py run <agent[,agent...]> <ep[,ep...]> [submission=p2750]
Results: results/fresh/lead_world_trace/<agent>_<ep>.json (lead_world_trace: actions, per-day ledger)
         results/fresh/search_dispatch_20260925/smoke/<agent>_<ep>.json (planner summary + per-step times)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/search_dispatch_20260925/smoke'


def run_one(name, path):
    import kaggle_environments.agent as KA
    import lead_world_trace as LWT
    orig = KA.get_last_callable
    box = []

    def glc(raw, path=None):
        f = orig(raw, path=path)
        box.append(f)
        return f
    KA.get_last_callable = glc
    try:
        res = LWT.run_one(name, path)
    finally:
        KA.get_last_callable = orig
    G = box[0].__globals__ if box else {}
    S = G.get('_S')
    rec = dict(agent=name, episode=res[1], final=res[2], rival=res[3])
    if S and 'sd' in S and '_sd_summary' in G:
        st = S['sd']['st']
        rec['summary'] = G['_sd_summary'](S)
        rec['plan_ms'] = st.get('plan_ms')
        rec['step_ms'] = st.get('step_ms')
        rec['load_proj_h23'] = st.get('load_proj_h23')
        rec['cash0'] = st.get('cash0')
    rec['router'] = {k: v for k, v in (G.get('_MGT_REPORT') or {}).items() if isinstance(v, (int, float))}
    rec['exec_log'] = {k: v for k, v in dict((S or {}).get('log', {})).items() if isinstance(v, (int, float))}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}_{res[1]}.json').write_text(json.dumps(rec), encoding='utf-8')
    return res


def main():
    if sys.argv[1] != 'run':
        raise SystemExit(__doc__)
    agents, eps = sys.argv[2].split(','), sys.argv[3].split(',')
    sub = sys.argv[4] if len(sys.argv) > 4 else 'p2750'
    jobs = [(a, str(ROOT / f'data/ladder_panel/{sub}/{e}.json.gz')) for e in eps for a in agents]
    if not Path('/kaggle').exists():
        raise SystemExit('games run on Kaggle (scripts/kaggle_remote/remote_panel.py pushcmd), not on the shared laptop')
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import os
    with ProcessPoolExecutor(max_workers=min(int(os.environ.get('LP_WORKERS', 4)), len(jobs)), max_tasks_per_child=1) as pool:
        for f in as_completed([pool.submit(run_one, *j) for j in jobs]):
            try:
                print(f.result(), flush=True)
            except Exception as exc:
                print('FAILED', type(exc).__name__, exc, flush=True)


if __name__ == '__main__':
    main()

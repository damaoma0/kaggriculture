"""Tape coverage under limited resources: load time, memory and router cost as a function of library size N.

For each N the shipped agent source (agents/mgt_m1.py, read-only) is copied to the scratch directory with its
`_MGT_LIB` blob replaced by an N-tape library (random subset for N <= 584; for N > 584 the library is replicated,
action table included, so every per-tape structure grows linearly). A fresh child process (one at a time) then

  1. loads the file the way kaggle_environments does on the FIRST step (exec of the whole module; this time is
     inside the timed act() call, so beyond actTimeout=1 s it is drawn from the 60 s remainingOverageTime bank),
  2. records resident memory after load and the process peak,
  3. calls the module's own `_mgt_router` at every router morning (days 3..28) with synthetic observations built
     from real tape boards/shops (label -> tile), timing each call; also the `_MGT_IGNORE` path (overlay-owned tiles).

No game is simulated. Single worker. Usage:
  .venv/Scripts/python.exe scripts/library_resource_probe.py [N ...]      (default 73 146 292 584 1168)
Writes results/fresh/newphase_20260923/library_structure/resource_probe.json
"""
import base64, gc, json, os, re, subprocess, sys, time, zlib
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'agents/mgt_m1.py'
OUT = ROOT / 'results/fresh/newphase_20260923/library_structure'
SCRATCH = Path(os.environ.get('LIB_PROBE_SCRATCH', str(Path(os.environ.get('TEMP', '/tmp')) / 'library_resource_probe')))
PY = ROOT / '.venv/Scripts/python.exe'

LABEL_TILE = {
    ' L': 'LOCKED', ' .': None, ' w': {'kind': 'WEED'},
    'WH': {'kind': 'PLANT', 'crop': 'WHEAT'}, 'CA': {'kind': 'PLANT', 'crop': 'CARROT'},
    'TO': {'kind': 'PLANT', 'crop': 'TOMATO'}, 'ST': {'kind': 'PLANT', 'crop': 'STRAWBERRY'},
    'ME': {'kind': 'PLANT', 'crop': 'MELON'},
    'co': {'kind': 'PASTURE', 'animal': 'COW'}, 'sh': {'kind': 'PASTURE', 'animal': 'SHEEP'},
    'go': {'kind': 'COOP', 'animal': 'GOOSE'}, 'pa': {'kind': 'PASTURE', 'animal': None},
}


def farm_from_board(board):
    labs = [board[i:i + 2] for i in range(0, 200, 2)]
    tiles = [[LABEL_TILE[labs[y * 10 + x]] for x in range(10)] for y in range(10)]
    return {'tiles': tiles, 'money': 0, 'farmer': [4, 4], 'hands': []}


# ----------------------------------------------------------------------------------------------------- child
def child(path, n_tapes, out_path):
    import psutil
    proc = psutil.Process()
    gc.collect()
    rss0 = proc.memory_info().rss
    src = Path(path).read_text(encoding='utf-8')
    t0 = perf_counter()
    env = {}
    exec(compile(src, path, 'exec'), env)                     # what get_last_callable does on the first act()
    t_load = perf_counter() - t0
    gc.collect()
    mi = proc.memory_info()
    rss1 = mi.rss
    peak = getattr(mi, 'peak_wset', None)
    # phase split of the decode on the same blob (objects freed afterwards)
    m = re.search(r"_mgt_b64\.b85decode\('([^']*)'\)", src)
    blob = m.group(1)
    del src
    t = perf_counter(); z = base64.b85decode(blob); t_b85 = perf_counter() - t
    t = perf_counter(); raw = zlib.decompress(z); t_zlib = perf_counter() - t
    t = perf_counter(); lib = json.loads(raw); t_json = perf_counter() - t
    json_bytes = len(raw)
    del blob, z, raw, lib
    gc.collect()
    tapes = env['_MGT_TAPES']
    router = env['_mgt_router']
    ignore = env['_MGT_IGNORE']
    n = len(tapes)
    base = min(n, 584)
    sample = sorted({(i * 37) % base for i in range(16)})
    per_day = {}
    calls = []
    for day in range(3, 29):
        ts = []
        for i in sample:
            t = tapes[i]
            obs = {'player': 0, 'day': day, 'hour': 0, 'step': 24 * day,
                   'town': {'unlocked_shops': list(t['shops'][:min(8, day // 3)])},
                   'farms': [farm_from_board(t['boards'][day]), farm_from_board(t['boards'][day])]}
            best = None
            for _ in range(3):
                state = {'route': i}
                s = perf_counter()
                router(obs, 24 * day, state)
                e = perf_counter() - s
                best = e if best is None else min(best, e)
            ts.append(best)
        per_day[day] = dict(mean_ms=1000 * sum(ts) / len(ts), max_ms=1000 * max(ts))
        calls += ts
    # overlay path: _MGT_IGNORE non-empty switches the Hamming loop to the slower generator form
    ign_ts = []
    for day in (3, 6, 12, 18, 24):
        for i in sample[:6]:
            t = tapes[i]
            obs = {'player': 0, 'town': {'unlocked_shops': list(t['shops'][:min(8, day // 3)])},
                   'farms': [farm_from_board(t['boards'][day])] * 2}
            ignore[0] = {99}
            s = perf_counter()
            router(obs, 24 * day, {'route': i})
            ign_ts.append(perf_counter() - s)
            ignore.pop(0, None)
    res = dict(N=n_tapes, tapes_loaded=n, file_bytes=Path(path).stat().st_size, json_bytes=json_bytes,
               load_s=t_load, decode_b85_s=t_b85, decode_zlib_s=t_zlib, decode_json_s=t_json,
               rss_before_mb=rss0 / 2 ** 20, rss_after_load_mb=rss1 / 2 ** 20,
               rss_growth_mb=(rss1 - rss0) / 2 ** 20, peak_wset_mb=(peak / 2 ** 20) if peak else None,
               router_call_ms=dict(mean=1000 * sum(calls) / len(calls), max=1000 * max(calls),
                                   per_game_total_ms=sum(v['mean_ms'] for v in per_day.values())),
               router_per_day=per_day,
               router_ignore_path_ms=dict(mean=1000 * sum(ign_ts) / len(ign_ts), max=1000 * max(ign_ts)),
               telemetry=dict(env['_MGT_REPORT']))
    Path(out_path).write_text(json.dumps(res, indent=1), encoding='utf-8')


# ---------------------------------------------------------------------------------------------------- parent
def build_source(src, blob_src, lib_n):
    blob = base64.b85encode(zlib.compress(json.dumps(lib_n, separators=(',', ':')).encode('utf-8'), 9)).decode('ascii')
    assert "'" not in blob and '\\' not in blob
    return src.replace(blob_src, blob, 1)


def replicate(lib, reps):
    A = lib['actions']
    nA = len(A)
    actions, tapes = [], []
    for r in range(reps):
        # distinct copies of every action so the table (and its decoded objects) grows too
        actions += [dict(a, _r=r) if r else a for a in A]
        for t in lib['tapes']:
            t2 = dict(t)
            t2['ids'] = [j + r * nA for j in t['ids']]
            t2['ep'] = t['ep'] * 10 + r if r else t['ep']
            if r:
                t2['modal'] = False
            tapes.append(t2)
    return dict(actions=actions, tapes=tapes)


def main():
    sys.path.insert(0, str(ROOT / 'scripts'))
    from library_structure_analysis import load_library, sub_library
    import numpy as np
    import psutil
    Ns = [int(x) for x in sys.argv[1:]] or [73, 146, 292, 584, 1168]
    SCRATCH.mkdir(parents=True, exist_ok=True)
    src = AGENT.read_text(encoding='utf-8')
    blob_src = re.search(r"_mgt_b64\.b85decode\('([^']*)'\)", src).group(1)
    lib, meta = load_library()
    rng = np.random.default_rng(5)
    rows = []
    out_json = OUT / 'resource_probe.json'
    prev = json.loads(out_json.read_text(encoding='utf-8')) if out_json.exists() else {}
    done = {r['N']: r for r in prev.get('rows', [])}
    for N in Ns:
        if N <= 584:
            idx = sorted(rng.choice(584, size=N, replace=False).tolist()) if N < 584 else list(range(584))
            libN = sub_library(lib, idx) if N < 584 else lib
        else:
            assert N % 584 == 0
            libN = replicate(lib, N // 584)
        text = build_source(src, blob_src, libN)
        del libN
        gc.collect()
        path = SCRATCH / f'probe_{N}.py'
        path.write_text(text, encoding='utf-8')
        del text
        avail = psutil.virtual_memory().available / 2 ** 20
        need = 0.6 * N + 400                                        # MB, conservative guess refined by the runs
        if avail < need + 600:
            print(f'skip N={N}: available {avail:.0f} MB < need {need:.0f}+600 MB', flush=True)
            continue
        o = SCRATCH / f'probe_{N}.json'
        t = time.time()
        subprocess.run([str(PY), str(Path(__file__).resolve()), 'child', str(path), str(N), str(o)], check=True)
        r = json.loads(o.read_text(encoding='utf-8'))
        r['wall_s'] = time.time() - t
        r['available_mb_before'] = avail
        done[N] = r
        print(f"N={N}: load {r['load_s']:.2f}s (json {r['decode_json_s']:.2f}s), rss +{r['rss_growth_mb']:.0f} MB, "
              f"router mean {r['router_call_ms']['mean']:.2f} ms max {r['router_call_ms']['max']:.2f} ms, "
              f"per game {r['router_call_ms']['per_game_total_ms']:.0f} ms", flush=True)
        path.unlink()
    rows = [done[k] for k in sorted(done)]
    import numpy as np
    fit = {}
    if len(rows) >= 2:
        xs = np.array([r['N'] for r in rows], float)
        for key, f in (('load_s', lambda r: r['load_s']), ('rss_growth_mb', lambda r: r['rss_growth_mb']),
                       ('router_mean_ms', lambda r: r['router_call_ms']['mean']),
                       ('router_max_ms', lambda r: r['router_call_ms']['max'])):
            ys = np.array([f(r) for r in rows], float)
            slope, icpt = np.polyfit(xs, ys, 1)
            fit[key] = dict(per_tape=float(slope), intercept=float(icpt))
    host = dict(cpu=os.environ.get('PROCESSOR_IDENTIFIER'), logical_cpus=os.cpu_count(),
                note='local laptop under concurrent load (a game panel ran in the background); Kaggle agents get '
                     '1.6 vCPU, so budget with a slowdown factor')
    limits = dict(actTimeout_s=1.0, remainingOverageTime_s=60.0, episodeSteps=720,
                  source='.venv/Lib/site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.json; '
                         'module load happens inside the first timed act() (kaggle_environments/agent.py '
                         'callable_agent -> get_last_callable)',
                  submission_limit='100 MiB (competition overview, recorded in docs/environment.md and '
                                   'docs/leader_policy_size_and_next_directions.md); 6.5 GiB RAM, 1.6 vCPU')
    caps = {}
    if fit:
        for slow in (1.0, 3.0):
            # router: one call per morning must stay inside the 1 s act budget (keep 0.5 s of it for the rest)
            rt = fit['router_max_ms']['per_tape'] * slow
            lo = fit['load_s']['per_tape'] * slow
            caps[f'slowdown_x{slow:g}'] = dict(
                router_call_under_0_5s=int(500.0 / rt) if rt > 0 else None,
                load_under_30s_of_overage=int(30.0 / lo) if lo > 0 else None,
                memory_under_4GiB=int(4096.0 / fit['rss_growth_mb']['per_tape']) if fit['rss_growth_mb']['per_tape'] > 0 else None)
    OUT.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(dict(limits=limits, host=host, rows=rows, linear_fit=fit, capacity=caps), indent=1),
                        encoding='utf-8')
    print(json.dumps(dict(linear_fit=fit, capacity=caps), indent=1))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'child':
        child(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    else:
        main()

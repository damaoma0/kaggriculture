"""Isolated cloud benchmark of JSON tile plans on the frozen KB115LT executor.

The established sector_run/lead_ledger engine harness is used unchanged. This
wrapper preserves its full ledger in addition to the usual cash and action
artifacts, and fails the kernel if any requested game is incomplete.
"""
import argparse
import hashlib
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_arms as RA

OUT = None


def initialize(spec, out):
    global OUT
    OUT = ROOT / out
    RA.init(spec)
    RA.SR.OUT = OUT / 'sector'
    RA.SR.X.OUT = RA.SR.OUT


def run_one(job):
    import lead_ledger
    mode, game, arm, ndays = job
    original = lead_ledger.play
    started = time.time()
    captured = {}

    def record_play(g, side):
        value = original(g, side)
        captured['ledger'] = value
        return value

    lead_ledger.play = record_play
    try:
        result = RA.SR.run_one(job)
    finally:
        lead_ledger.play = original
    ep = game.split(':')[1]
    dest = OUT / 'ledgers' / arm
    dest.mkdir(parents=True, exist_ok=True)
    if captured:
        ledger = captured['ledger']
        ledger['arm'] = arm
        ledger['wall_seconds'] = time.time() - started
        (dest / f'{ep}.json').write_text(json.dumps(ledger, default=str), encoding='utf-8')
    if result[4] is None:
        value = json.loads((OUT / 'sector' / 'multi' / arm / f'{ep}.json').read_text())
        final = value['money'][str(11 + ndays)]
        assert all(math.isfinite(x) for x in final), (arm, ep, final)
        ledger = captured['ledger']
        assert final == [ledger['final'], ledger['opp_final']], (arm, ep, final, ledger['final'])
        errors = value.get('tier_err', {}).get('errors')
        assert not errors, (arm, ep, 'executor errors', errors)
        for day, detail in value.get('tier_days', {}).items():
            assert not detail.get('tp_leak'), (arm, ep, day, detail['tp_leak'])
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--arms', required=True)
    ap.add_argument('--games', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args()
    spec = json.loads((ROOT / a.spec).read_text(encoding='utf-8'))
    games = a.games.split(',')
    arms = a.arms.split(',')
    initialize(spec, a.out)
    OUT.mkdir(parents=True, exist_ok=True)
    sources = ['scripts/semantic_tile_20260928_run.py', 'scripts/run_arms.py',
               'scripts/sector_run.py', 'scripts/xfix_run.py', 'scripts/lead_ledger.py', 'scripts/lead_g1.py',
               'scripts/fragments/sem_maintenance.py', a.spec]
    sources += [spec[arm]['agent'] for arm in arms]
    sources += [spec[arm]['cfg']['sd_tp_file'] for arm in arms if spec[arm]['cfg'].get('sd_tp_file')]
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(set(sources))}
    (OUT / 'run_manifest.json').write_text(json.dumps(dict(games=games, arms=arms, source_hashes=hashes,
        workers=a.workers, spec=spec), indent=2), encoding='utf-8')
    jobs = [('multi', game, arm, 19) for arm in arms for game in games]
    t0 = time.time()
    results = []
    with ProcessPoolExecutor(max_workers=a.workers, initializer=initialize, initargs=(spec, a.out)) as pool:
        for future in as_completed([pool.submit(run_one, job) for job in jobs]):
            result = future.result()
            results.append(result)
            print('completed', result[2], result[1], result[3], result[4] or 'OK', flush=True)
    (OUT / 'completion.json').write_text(json.dumps(dict(requested=len(jobs), results=results,
        elapsed_seconds=time.time() - t0), indent=2), encoding='utf-8')
    assert len(results) == len(jobs) and all(r[4] is None for r in results), 'incomplete or failed benchmark'
    print(f'{len(results)} games completed in {time.time() - t0:.1f}s', flush=True)


if __name__ == '__main__':
    main()

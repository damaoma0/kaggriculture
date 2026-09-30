"""Path-planner trial (2026-09-27): season runs (days 11-29) of spec arms on a few worlds, then each arm's vital
statistics (panel_path_metrics / panel_hour_budget / panel_tile_coverage / panel_hand_time) and season gap to the
leader (season_gap.py), in one process tree. Made for a private Kaggle kernel
(scripts/kaggle_remote/remote_panel.py pushcmd); runs locally too.

Arms with sd_sim_fert_free get the SIMULATION-ONLY engine patch scripts/sim_fert_free.py (our seat, from the day-11
morning) in the game AND in every replay of their stream; the leader's own replay in season_gap never gets it.
Fork start method (Linux) is assumed for the replay pools: their workers inherit the patched engine.

usage: path_trial.py --spec S --arms A,B --games team:ep,... --out DIR [--workers 4] [--days 19] [--no_vitals] [--no_gap]
out: DIR/games.json (final cash, error, fertilizer created by the patch, seconds), DIR/vitals_<group>.txt,
     DIR/gap_<arm>.json; the usual stream / multi files of sector_run.
"""
import argparse
import contextlib
import io
import json
import os
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import run_arms as RA  # noqa: E402
import sector_run as SR  # noqa: E402
import sim_fert_free as FF  # noqa: E402

VITALS = ('panel_path_metrics', 'panel_hour_budget', 'panel_tile_coverage', 'panel_hand_time')


def init(spec, seats):
    RA.init(spec)
    FF.install()
    FF.SEAT_BY_SEED.update(seats)


def game_job(j, fert):
    FF.ACTIVE['on'] = bool(fert)
    FF.INJECTED.update(n=0, events=0)
    t0 = time.time()
    m, g, arm, fin, err = SR.run_one(j)
    FF.ACTIVE['on'] = False
    return dict(arm=arm, game=g, final=fin, err=err, fert_created=FF.INJECTED['n'], fert_events=FF.INJECTED['events'],
                seconds=round(time.time() - t0, 1))


def gap_job(a):
    import season_gap as SG
    g, arm, fert = a
    team, ep = g.split(':')
    tape = SG.UE.load_tape(int(team), int(ep))
    s = json.loads((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f'{ep}.json').read_text(encoding='utf-8'))
    FF.ACTIVE['on'] = False
    lead = SG.run(tape, None)
    FF.ACTIVE['on'] = bool(fert)
    FF.INJECTED.update(n=0, events=0)
    ours = SG.run(tape, s['actions'])
    FF.ACTIVE['on'] = False
    return ep, {'leader': lead, arm: ours}, FF.INJECTED['n']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True)
    ap.add_argument('--arms', required=True)
    ap.add_argument('--games', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--days', type=int, default=19)
    ap.add_argument('--skip_games', action='store_true')
    ap.add_argument('--no_vitals', action='store_true')   # games (+ gap) only
    ap.add_argument('--no_gap', action='store_true')      # no season gap replays
    a = ap.parse_args()
    # research runs: no framework overage limit (lead_ledger's KAGG_NO_TIMEOUT). Kaggle's CPU is ~2x slower than the
    # laptop: path1 (2026-09-27) used the whole 60 s bank by days 20-24 (local KB109: 9.8 s) and the engine then
    # dropped every action of ours. The planner's search is iteration-bounded, so the game is the same without it.
    os.environ['KAGG_NO_TIMEOUT'] = '1'
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    spec = json.loads((ROOT / a.spec).read_text(encoding='utf-8'))
    arms, games = a.arms.split(','), a.games.split(',')
    SR.setup()
    RA.register(spec)
    import upkeep_engine as UE
    seats = {}
    for g in games:
        t = UE.load_tape(*map(int, g.split(':')))
        seats[t['seed']] = t['seat']
    init(spec, seats)
    fert = {arm: bool(SR.ARMS[arm][1].get('sd_sim_fert_free')) for arm in arms}
    for arm in arms:
        print('ARM', arm, 'fert_free', fert[arm], SR.ARMS[arm][0], flush=True)

    # 1. games
    rows = []
    if not a.skip_games:
        t0 = time.time()
        jobs = [(('multi', g, arm, a.days), fert[arm]) for arm in arms for g in games]
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=a.workers, initializer=init, initargs=(spec, seats)) as pool:
            futs = [pool.submit(game_job, j, f) for j, f in jobs]
            for fu in as_completed(futs):
                r = fu.result()
                rows.append(r)
                print(time.strftime('%H:%M:%S'), r['arm'], r['game'],
                      ('FAILED ' + r['err'][-1500:]) if r['err'] else f"final money {r['final']} fert_created {r['fert_created']} ({r['seconds']} s)",
                      flush=True)
        (out / 'games.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
        print(f'games done in {time.time() - t0:.0f}s', flush=True)
    ok_arms = [arm for arm in arms if all((ROOT / 'results/fresh/day12_viz' / f'{arm.lower()}_streams' / f"{g.split(':')[1]}.json").exists()
                                          for g in games)]

    # 2. vitals, one call per patch group (the patch state is inherited by the scripts' forked workers)
    os.environ['PANEL_GAMES'] = ' '.join(games)
    for grp, on in ((() if a.no_vitals else (('fertfree', True), ('plain', False)))):
        sel = [arm for arm in ok_arms if fert[arm] == on]
        if not sel:
            continue
        FF.ACTIVE['on'] = on
        buf = io.StringIO()
        for name in VITALS:
            buf.write(f'=== {name}\n')
            argv0 = sys.argv
            sys.argv = [str(ROOT / 'scripts' / f'{name}.py'), ','.join(sel), '--workers', str(a.workers)]
            try:
                with contextlib.redirect_stdout(buf):
                    runpy.run_path(sys.argv[0], run_name='__main__')
            except BaseException as exc:          # a failing script must not lose the others
                buf.write(f'FAILED {type(exc).__name__}: {exc}\n')
            finally:
                sys.argv = argv0
        FF.ACTIVE['on'] = False
        (out / f'vitals_{grp}.txt').write_text(buf.getvalue(), encoding='utf-8')
        print(f'vitals {grp} written ({len(buf.getvalue())} chars)', flush=True)

    # 3. season gap to the leader, per arm (leader replay without the patch)
    from multiprocessing import Pool
    import season_gap  # noqa: F401  (engine recorders installed before the fork)
    for arm in ([] if a.no_gap else ok_arms):
        res, created = {}, {}
        with Pool(min(a.workers, len(games))) as pool:
            for ep, r, n in pool.imap_unordered(gap_job, [(g, arm, fert[arm]) for g in games]):
                res[ep] = r
                created[ep] = n
        (out / f'gap_{arm.lower()}.json').write_text(json.dumps(res), encoding='utf-8')
        print('gap', arm, 'replay fert created', created, flush=True)
    print('completed', flush=True)


if __name__ == '__main__':
    main()

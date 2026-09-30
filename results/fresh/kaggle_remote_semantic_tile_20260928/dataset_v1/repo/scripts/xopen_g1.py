"""xopen E0/E1: leader worlds, T with an exactly replayed leader opening (thread xopen, 2026-09-25).

Every game is played by scripts/lead_ledger.py's own harness (lead_ledger.play: the recording's seed, forced shops,
the recorded opponent, the full per-day work / output / cash ledger) without editing it: side 'leader' replays the
leader's tape; side 'ours' loads the agent through lead_g1._load_agent, which this runner replaces per job so the
agent file and its configure options can be chosen (lead_ledger itself calls configure(sem) without options).

Arms (T's options everywhere: p1_min_value=30, release_stale_d=true, fert_hold=1 = BASE):
  LEADER  the leader's tape (lead_ledger 'leader'; must reproduce the recorded cash)
  T       agents/mgt_lead_xopen.py, xopen_day -1 (off: the copied mgt_lead.py, the paired baseline)
  X5 X8 X11   replay days 0..D-1 exactly, T from hour 0 of day D = 5 / 8 / 11 (X11 = the fixed-D fallback D = 11)
  Xdyn    the dynamic cash-safe rule (floor 10, cap 13) on our live money and measured revenue
  X30     replay the whole game (E0: must reproduce the leader's recorded cash to the dollar)
  ORIG    the frozen source copy of agents/mgt_lead.py (E0: must equal T to the dollar)
  F11     follow mode (the follower core on the compiled full-game plan) with D = 11 (identity check: = X11)

usage: xopen_g1.py run [--arms LEADER,T,...] [--worlds g1|<worlds.json>] [--games ep,...] [--skip-g1] [--workers 4]
       xopen_g1.py e0                 (print the E0 checks from the stored results)
Results: results/fresh/xopen_20260925/g1/<arm>/<ep>.json (the lead_ledger record + arm, cfg, xo = the agent's report)
"""
import glob
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
OUT = ROOT / 'results/fresh/xopen_20260925/g1'
BASE = {'p1_min_value': 30, 'release_stale_d': True, 'fert_hold': 1}
XOPEN = 'agents/mgt_lead_xopen.py'


def orig_path():
    man = json.loads((ROOT / 'results/fresh/xopen_20260925/build_manifest.json').read_text(encoding='utf-8'))
    h = man['mgt_lead_xopen']['source_sha256']
    return f'results/fresh/xopen_20260925/src/mgt_lead_{h[:12]}.py'


def arms():
    return {
        'T': (XOPEN, dict(BASE, xopen_day=-1)),
        'X5': (XOPEN, dict(BASE, xopen_day=5)),
        'X8': (XOPEN, dict(BASE, xopen_day=8)),
        'X11': (XOPEN, dict(BASE, xopen_day=11)),
        'Xdyn': (XOPEN, dict(BASE, xopen_day=99, xopen_rule='dynamic')),
        'X30': (XOPEN, dict(BASE, xopen_day=30)),
        'F11': (XOPEN, dict(BASE, xopen_day=11, xopen_mode='follow')),
        'ORIG': (None, dict(BASE)),
    }


def job(args):
    game, arm = args
    try:
        import lead_g1
        import lead_ledger
        import importlib.util
        t0 = time.time()
        box = {}
        if arm == 'LEADER':
            r = lead_ledger.play(game, 'leader')
        else:
            path, cfg = arms()[arm]
            path = ROOT / (path or orig_path())

            def loader(_cfg):
                spec = importlib.util.spec_from_file_location('xopen_arm_' + arm, str(path))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                inner = mod.configure
                mod.configure = lambda sem, **kw: inner(sem, **dict(cfg, **kw))
                box['mod'] = mod
                return mod
            lead_g1._load_agent = loader
            r = lead_ledger.play(game, 'ours')
            mod = box.get('mod')
            rep = {}
            if mod is not None and hasattr(mod, 'xo_e1_report'):
                try:
                    rep = mod.xo_e1_report()
                except Exception as exc:
                    rep = {'report_error': f'{type(exc).__name__}: {exc}'}
            r['xo'] = rep
            r['cfg'] = cfg
            r['agent_path'] = str(path.relative_to(ROOT)).replace('\\', '/')
        r['arm'] = arm
        r['wall'] = time.time() - t0
        ep = game.split(':')[1]
        (OUT / arm).mkdir(parents=True, exist_ok=True)
        (OUT / arm / f'{ep}.json').write_text(json.dumps(r, default=str), encoding='utf-8')
        return game, arm, r['final'], r['target'], None
    except Exception as exc:
        return game, arm, None, None, f'{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2500:]}'


def worlds(spec, skip_g1):
    import lead_g1
    if spec == 'g1':
        return list(lead_g1.GAMES)
    w = json.loads((ROOT / spec).read_text(encoding='utf-8'))['worlds']
    out = [x['game'] for x in w]
    if skip_g1:
        out = [g for g in out if g not in lead_g1.GAMES]
    return out


def e0():
    rows = {}
    for f in OUT.glob('*/*.json'):
        r = json.loads(f.read_text(encoding='utf-8'))
        rows[(r['arm'], r['episode'])] = r
    ok = True
    for (arm, ep), r in sorted(rows.items()):
        if arm == 'X30':
            m = abs(r['final'] - r['target']) < 0.5
            ok &= m
            print(f'X30 {ep}: final {r["final"]:.0f} recorded {r["target"]:.0f} -> {"OK" if m else "MISMATCH"}')
        if arm == 'LEADER':
            m = abs(r['final'] - r['target']) < 0.5
            ok &= m
            print(f'LEADER {ep}: final {r["final"]:.0f} recorded {r["target"]:.0f} -> {"OK" if m else "MISMATCH"}')
        if arm == 'ORIG' and ('T', ep) in rows:
            t = rows[('T', ep)]
            m = abs(r['final'] - t['final']) < 0.5 and abs(r['opp_final'] - t['opp_final']) < 0.5
            same_days = all(a.get('cash') == b.get('cash') for a, b in zip(r['days'], t['days']))
            ok &= m and same_days
            print(f'ORIG {ep}: final {r["final"]:.0f} vs T {t["final"]:.0f}, opp {r["opp_final"]:.0f} vs {t["opp_final"]:.0f}, '
                  f'day-start cash identical {same_days} -> {"OK" if m and same_days else "MISMATCH"}')
        if arm == 'F11' and ('X11', ep) in rows:
            t = rows[('X11', ep)]
            m = abs(r['final'] - t['final']) < 0.5
            print(f'F11 {ep}: final {r["final"]:.0f} vs X11 {t["final"]:.0f} -> {"OK" if m else "DIFF"}')
    print('E0', 'PASS' if ok else 'FAIL')
    return ok


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] == 'e0':
        e0()
        return
    sel_arms = ['X30', 'ORIG', 'LEADER', 'T', 'X5', 'X8', 'X11', 'Xdyn']
    spec, games_sel, skip_g1, workers = 'g1', None, False, int(os.environ.get('LP_WORKERS', 4))
    ctl_games = None
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == '--arms':
            sel_arms = argv[i + 1].split(','); i += 2
        elif a == '--worlds':
            spec = argv[i + 1]; i += 2
        elif a == '--games':
            games_sel = argv[i + 1].split(','); i += 2
        elif a == '--skip-g1':
            skip_g1 = True; i += 1
        elif a == '--workers':
            workers = int(argv[i + 1]); i += 2
        elif a == '--ctl-games':
            ctl_games = int(argv[i + 1]); i += 2
        else:
            i += 1
    games = worlds(spec, skip_g1)
    if games_sel:
        games = [g for g in games if g.split(':')[1] in games_sel]
    jobs = []
    for arm in sel_arms:
        gs = games[:ctl_games] if (ctl_games and arm in ('ORIG',)) else games
        jobs += [(g, arm) for g in gs]
    print(len(jobs), 'jobs', flush=True)
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(job, j) for j in jobs]
        for f in as_completed(futs):
            g, arm, fin, tgt, err = f.result()
            print(time.strftime('%H:%M:%S'), arm, g, 'ERROR ' + err if err else f'{fin:.0f} / {tgt:.0f} = {fin / tgt:.3f}',
                  flush=True)
    print(f'completed {len(jobs)} jobs in {time.time() - t0:.0f}s', flush=True)
    e0()


if __name__ == '__main__':
    main()

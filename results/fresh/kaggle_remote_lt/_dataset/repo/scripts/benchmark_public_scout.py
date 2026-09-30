"""Frozen live public-agent screen against packaged MGT, official runner, fresh process/game."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/public_scout_20260925'
NAMES = ['kaito_v13', 'rayk_v11', 'flex_v59', 'ahmed_v55']


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.write_text(json.dumps(value, indent=2), encoding='utf-8')


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / 'manifest.json'
    if manifest_path.exists():
        m = json.loads(manifest_path.read_text())
        for rel, sha in m['hashes'].items():
            assert digest(OUT / rel) == sha, rel
        return m
    pkg = ROOT / 'submissions/2026-09-24-mgt_v9lite/pkg'
    expected = json.loads((pkg.parent / 'MANIFEST.json').read_text())['files']
    for rel, sha in expected.items():
        assert digest(pkg / rel) == sha, rel
    shutil.copytree(pkg, OUT / 'frozen/mgt', dirs_exist_ok=True)
    for name in NAMES:
        dest = OUT / 'frozen' / name
        dest.mkdir(exist_ok=True)
        shutil.copy2(ROOT / 'data/public_scout_20260925' / name / 'main.py', dest / 'main.py')
    for folder in ['games', 'logs', 'work']:
        (OUT / folder).mkdir(exist_ok=True)
    master = secrets.randbits(128)
    seeds = random.Random(master).sample(range(1000000000, 2000000000), 8)
    m = dict(created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             incumbent='packaged mgt_v9lite, 2026-09-24', opponents=NAMES, seeds=seeds,
             master_seed=master, seats=[0, 1], expected_games=64,
             design='Natural RNG, same fresh seeds, both seats, responsive agents; official env.run with time accounting; fresh process each game. Complete fixed panel, preserve failures.',
             hashes={str(p.relative_to(OUT)): digest(p) for p in (OUT / 'frozen').rglob('*') if p.is_file()})
    save(manifest_path, m)
    return m


def game(name, seed, seat):
    dest = OUT / 'games' / f'{name}-{seed}-{seat}.json'
    row = dict(opponent=name, seed=seed, mgt_seat=seat, completed=False)
    started = time.perf_counter()
    try:
        # Do not expose the working repository to either agent's imports.
        sys.path[:] = [p for p in sys.path if p and Path(p).resolve() not in {ROOT, ROOT / 'scripts'}]
        os.chdir(OUT / 'work')
        from importlib.metadata import version
        from kaggle_environments import make
        from kaggle_environments.envs.kaggriculture import kaggriculture as engine
        assert version('kaggle-environments') == '1.32.7'
        players = [None, None]
        players[seat] = str(OUT / 'frozen/mgt/main.py')
        players[1-seat] = str(OUT / f'frozen/{name}/main.py')
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed}, debug=False)
        steps = env.run(players)
        final = steps[-1]
        cash = [s['reward'] for s in final]
        row.update(statuses=[s['status'] for s in final], rewards=cash,
                   mgt_cash=cash[seat], opponent_cash=cash[1-seat],
                   margin=cash[seat]-cash[1-seat] if all(isinstance(x, (int, float)) for x in cash) else None,
                   states=len(steps), shops=list(final[0]['observation']['town']['unlocked_shops']),
                   min_bank=[min(s[i]['observation'].get('remainingOverageTime', 60) for s in steps) for i in (0, 1)],
                   engine_version=version('kaggle-environments'), engine_sha256=digest(Path(engine.__file__)),
                   configuration=dict(env.configuration),
                   action_sha256=hashlib.sha256(json.dumps([[s.get('action') for s in state] for state in steps], sort_keys=True).encode()).hexdigest())
        logs = getattr(env, 'logs', [])
        save(OUT / 'logs' / f'{name}-{seed}-{seat}-engine.json', logs)
        row['completed'] = len(steps) == 720 and row['statuses'] == ['DONE', 'DONE']
    except Exception:
        row['error'] = traceback.format_exc()
    row['wall_seconds'] = time.perf_counter() - started
    save(dest, row)


def report():
    m = json.loads((OUT / 'manifest.json').read_text())
    rows = [json.loads(p.read_text()) for p in (OUT / 'games').glob('*.json')]
    result = {'expected_games': m['expected_games'], 'recorded_games': len(rows), 'opponents': {}}
    for name in NAMES:
        games = [g for g in rows if g['opponent'] == name]
        good = [g for g in games if g['completed']]
        margins = [g['margin'] for g in good]
        by_seed = {seed: [g for g in good if g['seed'] == seed] for seed in m['seeds']}
        paired = [sum(g['margin'] for g in pair)/2 for pair in by_seed.values() if len(pair) == 2]
        interval = None
        if paired:
            rng = random.Random(39025)
            samples = sorted(sum(rng.choices(paired, k=len(paired)))/len(paired) for _ in range(10000))
            interval = [samples[250], samples[9750]]
        result['opponents'][name] = dict(games=len(games), completed=len(good), failures=len(games)-len(good),
            mgt_wins=sum(x > 0 for x in margins), ties=sum(x == 0 for x in margins), mgt_losses=sum(x < 0 for x in margins),
            mean_mgt_margin=sum(margins)/len(margins) if margins else None,
            seed_bootstrap_95ci=interval, complete_seed_pairs=len(paired),
            seat_results={str(s): {'wins': sum(g['margin'] > 0 for g in good if g['mgt_seat'] == s),
                                  'games': sum(g['mgt_seat'] == s for g in good)} for s in (0, 1)})
    save(OUT / 'summary.json', result)
    print(json.dumps(result, indent=2), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', nargs=3)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--report', action='store_true')
    args = ap.parse_args()
    if args.game:
        game(args.game[0], int(args.game[1]), int(args.game[2]))
        return
    m = prepare()
    if args.report:
        report()
        return
    jobs = [(name, seed, seat) for seed in m['seeds'] for name in NAMES for seat in (0, 1)
            if not (OUT / 'games' / f'{name}-{seed}-{seat}.json').exists()]
    if args.limit is not None:
        jobs = jobs[:args.limit]
    print(json.dumps({'pending': len(jobs), 'workers': 1}), flush=True)
    for name, seed, seat in jobs:
        dest = OUT / 'games' / f'{name}-{seed}-{seat}.json'
        with (OUT / 'logs' / f'{name}-{seed}-{seat}.log').open('w', encoding='utf-8') as log:
            try:
                p = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--game', name, str(seed), str(seat)],
                                   stdout=log, stderr=subprocess.STDOUT, timeout=600)
                if not dest.exists():
                    save(dest, dict(opponent=name, seed=seed, mgt_seat=seat, completed=False, error=f'Child exit {p.returncode}, no result'))
            except subprocess.TimeoutExpired:
                save(dest, dict(opponent=name, seed=seed, mgt_seat=seat, completed=False, error='600s outer game watchdog exceeded'))
        row = json.loads(dest.read_text())
        print(json.dumps({k: row.get(k) for k in ['opponent', 'seed', 'mgt_seat', 'completed', 'margin', 'wall_seconds', 'error']}), flush=True)
    report()


if __name__ == '__main__':
    main()

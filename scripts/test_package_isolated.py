"""Play a multi-file agent archive the way Kaggle's evaluator would: extract it into an empty directory, run from a
different working directory, load main.py through kaggle_environments' own file loader and time accounting.

usage: test_package_isolated.py <submission.tar.gz | unpacked dir> <opponent.py> <out.json> [seeds=1] [--gunzip]
--gunzip also replaces every *.json.gz in the extracted agent by its decompressed *.json (what Kaggle's DATASET
upload does; tests the package's fallback). Reports status, rewards, overage bank (end, minimum, largest drop), wall.
--cpus=N pins the run to N cores and --stress=K adds K busy processes on the same cores (Linux only), to see what the
bank-aware budget does on less CPU than a Kaggle notebook core (the evaluator's share is not known).
--seed0=K starts at seed index K (to run several copies in parallel on different seeds).
After the games it lists every loaded module whose file lives in the REPO's scripts/, agents/, data/ or results/
(anything the package should have carried itself); the run fails if there is one ("foreign_modules").
"""
import gzip, json, os, shutil, sys, tarfile, tempfile, time
from pathlib import Path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    gunzip = '--gunzip' in sys.argv
    archive, opponent, out = Path(args[0]).resolve(), Path(args[1]).resolve(), Path(args[2]).resolve()
    seeds = int(args[3]) if len(args) > 3 else 1
    seed0 = next((int(a.split('=', 1)[1]) for a in sys.argv if a.startswith('--seed0=')), 0)
    repo = Path(__file__).resolve().parents[1]
    cpus = next((int(a.split('=', 1)[1]) for a in sys.argv if a.startswith('--cpus=')), None)
    stress = next((int(a.split('=', 1)[1]) for a in sys.argv if a.startswith('--stress=')), 0)
    if cpus:
        os.sched_setaffinity(0, set(range(cpus)))
    import subprocess
    burners = [subprocess.Popen([sys.executable, '-c', 'while True: pass']) for _ in range(stress)]
    from kaggle_environments import make
    agent_dir = Path(tempfile.mkdtemp(prefix='kagent_'))
    run_dir = Path(tempfile.mkdtemp(prefix='krun_'))
    if archive.is_dir():                             # an already unpacked agent directory
        shutil.copytree(archive, agent_dir, dirs_exist_ok=True)
    else:
        with tarfile.open(archive) as t:
            t.extractall(agent_dir)
    if gunzip:
        for f in list(agent_dir.rglob('*.json.gz')):
            f.with_suffix('').write_bytes(gzip.decompress(f.read_bytes()))
            f.unlink()
    shutil.copy(opponent, run_dir / 'opponent.py')
    cwd = os.getcwd()
    os.chdir(run_dir)
    rows = []
    try:
        for s in range(seed0, seed0 + seeds):
            for seat in (0, 1):
                env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': 20260924 + 17 * s})
                me = str(agent_dir / 'main.py')
                files = [me, 'opponent.py'] if seat == 0 else ['opponent.py', me]
                t0 = time.time()
                steps = env.run(files)
                bank = [st[seat]['observation'].get('remainingOverageTime') for st in steps]
                bank = [b for b in bank if isinstance(b, (int, float))]
                drops = [bank[i] - bank[i + 1] for i in range(len(bank) - 1)]
                last = steps[-1]
                rows.append(dict(seed=s, seat=seat, gunzip=gunzip, cpus=cpus, stress=stress, steps=len(steps), wall=round(time.time() - t0, 1),
                                 status=[p['status'] for p in last], reward=[p['reward'] for p in last],
                                 bank_end=bank[-1] if bank else None, bank_min=min(bank) if bank else None,
                                 max_bank_drop=round(max(drops), 2) if drops else 0))
                print(json.dumps(rows[-1]), flush=True)
    finally:
        for b in burners:
            b.kill()
        os.chdir(cwd)
        shutil.rmtree(agent_dir, ignore_errors=True)
        shutil.rmtree(run_dir, ignore_errors=True)
    foreign = sorted({str(Path(m.__file__).resolve()) for m in list(sys.modules.values())
                      if getattr(m, '__file__', None) and any(str(Path(m.__file__).resolve()).startswith(str(repo / d))
                                                              for d in ('scripts', 'agents', 'data', 'results'))
                      and Path(m.__file__).resolve() != Path(__file__).resolve()})
    print(json.dumps(dict(foreign_modules=foreign)), flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(games=rows, foreign_modules=foreign), indent=1), encoding='utf-8')
    if foreign:
        raise SystemExit('package loaded modules from the repo: %s' % foreign)


if __name__ == '__main__':
    main()

"""Load and time agents exactly the way Kaggle's evaluator does: copy ONLY the agent files into an empty directory,
chdir there, and play full games with kaggle_environments' own env.run([file, file]) (the file path loader, the
environment's actTimeout / remainingOverageTime accounting). Nothing from the repo is importable from there.

usage: kaggle_load_check.py <out.json> <agent.py> <opponent.py> [seeds=2] [<agent2.py> ...]
KLC_INPLACE=1 (or --inplace) runs the agent file from the repo root instead (for research wrappers such as mgt_v9y3 that import
from scripts/ and data/): same loader and time accounting, but not the isolation check.
Reports per game: statuses, rewards, our remaining overage bank at the end and its minimum (the 60 s bank the
first call's module load and any slow step draw on), the slowest step, and wall time.
"""
import json, os, shutil, sys, tempfile, time
from pathlib import Path


def main():
    if '--inplace' in sys.argv:
        sys.argv.remove('--inplace')
        os.environ['KLC_INPLACE'] = '1'
    out = Path(sys.argv[1]).resolve()
    opponent = Path(sys.argv[3]).resolve()
    seeds = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    agents = [Path(sys.argv[2]).resolve()] + [Path(a).resolve() for a in sys.argv[5:]]
    from kaggle_environments import make
    rows = []
    for agent in agents:
        for s in range(seeds):
            inplace = os.environ.get('KLC_INPLACE') == '1'
            tmp = Path(tempfile.mkdtemp(prefix='kload_'))
            shutil.copy(agent, tmp / 'main.py')
            shutil.copy(opponent, tmp / 'opponent.py')
            cwd = os.getcwd()
            if inplace:
                shutil.copy(opponent, Path(cwd) / '_klc_opponent.py')
            else:
                os.chdir(tmp)
            try:
                for seat in (0, 1):
                    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': 20260924 + 17 * s})
                    me, opp = (str(agent.relative_to(Path(cwd))), '_klc_opponent.py') if inplace else ('main.py', 'opponent.py')
                    files = [me, opp] if seat == 0 else [opp, me]
                    t0 = time.time()
                    steps = env.run(files)
                    wall = time.time() - t0
                    bank = [st[seat]['observation'].get('remainingOverageTime') for st in steps]
                    bank = [b for b in bank if isinstance(b, (int, float))]
                    drops = [bank[i] - bank[i + 1] for i in range(len(bank) - 1)]
                    last = steps[-1]
                    rows.append(dict(agent=agent.name, seed=s, seat=seat, steps=len(steps), wall=round(wall, 1),
                                     status=[p['status'] for p in last], reward=[p['reward'] for p in last],
                                     bank_start=bank[0] if bank else None, bank_end=bank[-1] if bank else None,
                                     bank_min=min(bank) if bank else None, max_bank_drop=round(max(drops), 2) if drops else 0,
                                     config_act_timeout=env.configuration.get('actTimeout')))
                    print(json.dumps(rows[-1]), flush=True)
            finally:
                os.chdir(cwd)
                shutil.rmtree(tmp, ignore_errors=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()

"""Verify frozen source/actions and independently replay a live labor ablation."""
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
import argparse
import gzip
import io
import json
import compare_live_labour as C


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    folder = C.R.OUT / args.tag
    manifest = json.loads((folder / 'manifest.json').read_text())
    for name, digest in manifest['sources'].items():
        assert sha256((C.ROOT / name).read_bytes()).hexdigest() == digest, name
    rows = [json.loads(p.read_text()) for p in folder.glob('[0-9]*.json')]
    assert len(rows) == manifest['arguments']['seeds'] * 3
    for row in rows:
        path = folder / f"{row['seed']}-{row['treatment']}.actions.json.gz"
        actions = json.load(gzip.open(path, 'rt'))
        assert C.S.digest(actions) == row['actions_sha256']
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from kaggle_environments import make
        from kaggle_environments.agent import get_last_callable
    selected = [r for r in rows if r['seed'] == manifest['arguments']['seed_base']]
    checks = []
    for row in selected:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': row['seed']})
        actions = json.load(gzip.open(folder / f"{row['seed']}-{row['treatment']}.actions.json.gz", 'rt'))
        if row['treatment'] == -1:
            path = C.ROOT / 'agents/mgt_m1.py'
            players = [get_last_callable(path.read_text(encoding='utf-8'), path=str(path)) for _ in range(2)]
        else:
            def seat_agent(seat):
                def agent(obs):
                    return actions[seat][obs.step]
                return agent
            players = [seat_agent(s) for s in range(2)]
        env.run(players)
        assert len(env.steps) == 720 and all(s.status == 'DONE' for s in env.state)
        assert [s.reward for s in env.state] == row['cash']
        assert all(env.steps[t + 1][s].action == actions[s][t] for t in range(719) for s in range(2))
        checks.append(dict(seed=row['seed'], treatment=row['treatment'], cash=row['cash'],
                           check='normal_live_loader_parity' if row['treatment'] == -1 else 'official_framework_schedule_replay', passed=True))
    result = dict(passed=True, hash_checked_games=len(rows), checks=checks)
    (folder / 'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

"""Push Kaggle jobs in order as batch sessions free up (the account's cap is 5, shared with other threads).

usage: queue_push.py <jobs.json>
jobs.json: [{"kind": "push", "run": ..., "agents": ..., "submission": ..., "episodes": "@file|a,b|all", "shards": n},
            {"kind": "pushcmd", "run": ..., "cmd": "scripts/x.py --a b", "collect": "glob1,glob2"}, ...]
Each shard of a job is retried every 90 s while the push is refused for the session cap.
"""
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / '.venv/Scripts/python.exe')
RP = str(ROOT / 'scripts/kaggle_remote/remote_panel.py')


def attempt(args):
    p = subprocess.run([PY, RP] + args, capture_output=True, text=True, cwd=ROOT)
    out = p.stdout + p.stderr
    return ('Maximum batch CPU session count' not in out and 'successfully pushed' in out), out.strip().splitlines()[-1:]


def main():
    jobs = json.loads(Path(sys.argv[1]).read_text())
    for j in jobs:
        if j['kind'] == 'push':
            # push shards one at a time so each can wait for its own free session
            eps = j['episodes']
            if eps.startswith('@'):
                eps = json.loads(Path(eps[1:]).read_text())
            elif eps == 'all':
                eps = sorted(p.name.split('.')[0] for s in j['submission'].split(',') for p in (ROOT / 'data/ladder_panel' / s).glob('*.json.gz'))
            else:
                eps = eps.split(',')
            n = j.get('shards', 1)
            for i in range(n):
                part = eps[i::n]
                args = ['push', f"{j['run']}{i}" if n > 1 else j['run'], j['agents'], j['submission'], ','.join(part), '1', str(j.get('workers', 4))]
                while True:
                    ok, tail = attempt(args)
                    print(time.strftime('%H:%M'), j['run'], i, 'ok' if ok else 'waiting', tail, flush=True)
                    if ok:
                        break
                    time.sleep(90)
        else:
            while True:
                ok, tail = attempt(['pushcmd', j['run'], j['cmd'], j['collect']])
                print(time.strftime('%H:%M'), j['run'], 'ok' if ok else 'waiting', tail, flush=True)
                if ok:
                    break
                time.sleep(90)
    print('all jobs pushed', flush=True)


if __name__ == '__main__':
    main()

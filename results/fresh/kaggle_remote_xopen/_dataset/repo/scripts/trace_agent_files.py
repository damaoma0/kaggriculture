"""Which repo files does an agent open or import during one full game? (for packaging a multi-file submission)
usage: trace_agent_files.py <agent.py> <opponent.py> <out.json> [seed]
Runs env.run from the repo root with an audit hook on 'open' and 'import'; writes the repo-relative files touched.
"""
import json, os, sys, time
from pathlib import Path

ROOT = Path.cwd().resolve()
seen = set()


def hook(event, args):
    if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = args[0]
    elif event == 'import' and len(args) > 1 and args[1]:
        p = args[1]
    else:
        return
    try:
        p = Path(os.fsdecode(p)).resolve()
        seen.add(p.relative_to(ROOT).as_posix())
    except Exception:
        pass


def main():
    agent, opponent, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 20260924
    from kaggle_environments import make
    sys.addaudithook(hook)
    env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': seed})
    t0 = time.time()
    steps = env.run([agent, opponent])
    last = steps[-1]
    files = sorted(f for f in seen if not f.startswith('.venv/'))
    sizes = {f: (ROOT / f).stat().st_size for f in files if (ROOT / f).is_file()}
    out.write_text(json.dumps(dict(status=[p['status'] for p in last], reward=[p['reward'] for p in last],
                                   wall=round(time.time() - t0, 1), files=sizes, total_mb=round(sum(sizes.values()) / 1e6, 2)), indent=1))
    print(json.dumps(dict(status=[p['status'] for p in last], reward=[p['reward'] for p in last], n=len(sizes),
                          total_mb=round(sum(sizes.values()) / 1e6, 2))))


if __name__ == '__main__':
    main()

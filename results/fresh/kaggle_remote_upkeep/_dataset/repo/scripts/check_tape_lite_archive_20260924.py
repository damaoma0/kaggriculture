"""One fresh-process game through the official file loader, away from the repo.

The extracted archive and run directory are retained for inspection. No directory
is deleted. Run serially after qualification, with a new --name for every case.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
import gzip
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/coherent_switch_20260924_01a0/release_lite_qualification'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--name', required=True)
    ap.add_argument('--seed', required=True, type=int)
    ap.add_argument('--seat', required=True, type=int, choices=(0, 1))
    ap.add_argument('--opponent', choices=('mgt_m1', 'v56'), default='v56')
    ap.add_argument('--gunzip', action='store_true')
    ap.add_argument('--candidate-dir', type=Path, help='Explicit derived package directory, with archive and MANIFEST.json')
    args = ap.parse_args()
    assert args.name and all(c.isalnum() or c in '-_' for c in args.name)
    case = OUT / 'isolated' / args.name
    assert not case.exists(), 'Never overwrite a previous official-loader check'
    agent_dir, run_dir = case / 'agent', case / 'work'
    agent_dir.mkdir(parents=True)
    run_dir.mkdir()
    if args.candidate_dir:
        candidate_dir = args.candidate_dir.resolve()
        saved_manifest = json.loads((candidate_dir / 'MANIFEST.json').read_text())
        manifest = dict(archive_sha256=saved_manifest['archive_sha256'], package_files=saved_manifest['files'])
        archive = candidate_dir / 'submission.tar.gz'
    else:
        manifest = json.loads((OUT / 'manifest.json').read_text())
        archive = OUT / 'submission.tar.gz'
    assert sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        file_names = set()
        for member in members:
            name = PurePosixPath(member.name)
            assert not name.is_absolute() and '..' not in name.parts
            target = agent_dir.joinpath(*name.parts).resolve()
            assert target.is_relative_to(agent_dir.resolve())
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            assert member.isfile(), 'No archive links or devices permitted'
            key = str(name)
            assert key not in file_names
            file_names.add(key)
            data = tar.extractfile(member).read()
            assert sha256(data).hexdigest() == manifest['package_files'][key], key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        assert file_names == set(manifest['package_files'])
    if args.gunzip:
        for path in sorted(agent_dir.rglob('*.json.gz')):
            destination = path.with_suffix('')
            assert not destination.exists(), str(destination)
            destination.write_bytes(gzip.decompress(path.read_bytes()))
            path.unlink()
    opponent = ROOT / ('agents/mgt_m1.py' if args.opponent == 'mgt_m1' else 'data/router_refresh_20260922/v56/main.py')
    shutil.copyfile(opponent, run_dir / 'opponent.py')
    report_dir = case / 'search_logs'
    report_dir.mkdir()
    os.environ['V9Y3_REPORT_DIR'] = str(report_dir)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from kaggle_environments import make
    # Keep only installed/framework paths plus the extracted package during the
    # actual game. Candidate helper imports must resolve inside this extraction.
    script_dir = ROOT / 'scripts'
    sys.path[:] = [p for p in sys.path if p and Path(p).resolve() not in (ROOT, script_dir)]
    os.chdir(run_dir)
    t0 = time.perf_counter()
    original_stdout, original_stderr = sys.stdout, sys.stderr
    row = dict(name=args.name, seed=args.seed, seat=args.seat, opponent=args.opponent,
               gunzip=args.gunzip, archive_sha256=manifest['archive_sha256'], cwd=str(run_dir),
               extracted_files=len(file_names), passed=False)
    try:
        env = make('kaggriculture', configuration={'episodeSteps': 720}, info={'seed': args.seed})
        files = [str(agent_dir / 'main.py'), str(run_dir / 'opponent.py')]
        if args.seat:
            files.reverse()
        steps = env.run(files)
        row['global_streams_preserved'] = sys.stdout is original_stdout and sys.stderr is original_stderr
        assert row['global_streams_preserved'], 'Agent background work corrupted loader output streams'
        bank = [s[args.seat]['observation'].get('remainingOverageTime') for s in steps]
        bank = [b for b in bank if isinstance(b, (int, float))]
        last = steps[-1]
        search_file = report_dir / 'v9lite_decisions.jsonl'
        reports = [json.loads(line) for line in search_file.read_text().splitlines()] if search_file.exists() else []
        modules = {name: str(Path(module.__file__).resolve()) for name, module in sys.modules.items()
                   if (name.startswith('value_tape_search') or name.startswith('rival_trajectory_model'))
                   and getattr(module, '__file__', None)}
        assert modules and all(Path(path).is_relative_to(agent_dir.resolve()) for path in modules.values()), modules
        row.update(steps=len(steps), status=[s['status'] for s in last], reward=[s['reward'] for s in last],
                   bank_end=bank[-1] if bank else None, bank_min=min(bank) if bank else None,
                   max_bank_drop=max((a-b for a,b in zip(bank,bank[1:])), default=0),
                   package_modules=modules, reports=reports)
        assert len(steps) == 720 and row['status'] == ['DONE', 'DONE'], row['status']
        assert bank and min(bank) > 8, 'Candidate must preserve its declared safety reserve'
        assert len(reports) == 3 and all(r['errors'] == 0 for r in reports), 'All three reveal searches must run without errors'
        row['passed'] = True
    except Exception:
        row['error'] = traceback.format_exc()
    finally:
        row['wall_seconds'] = time.perf_counter()-t0
        (case / 'result.json').write_text(json.dumps(row, indent=2))
    print(json.dumps({k: row[k] for k in ('name','passed','steps','status','bank_min','wall_seconds','error') if k in row}))
    if not row['passed']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()

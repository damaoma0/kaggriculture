"""Kaggle kernel wrapper: refuse to run on a stale dataset version. The bundle carries results/fresh/kaggle_lt/bundle_token.txt
(written just before `remote_panel.py bundle`); a kernel that starts from an older version (Kaggle can serve the previous
version right after `datasets status` says ready) exits at once with a clear message instead of running the wrong code.

usage: kgr_check_run.py <token> <script.py> [args...]"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    token, script, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    f = ROOT / 'results/fresh/kaggle_lt/bundle_token.txt'
    have = f.read_text().strip() if f.exists() else '(missing)'
    if have != token:
        raise SystemExit(f'STALE BUNDLE: token {have!r}, expected {token!r} - re-push after the new version is served')
    print('bundle token ok:', token, flush=True)
    # a subprocess, not runpy: the script's process pool pickles functions by their __main__ module
    raise SystemExit(subprocess.run([sys.executable, str(ROOT / script)] + args, cwd=str(ROOT)).returncode)


if __name__ == '__main__':
    main()

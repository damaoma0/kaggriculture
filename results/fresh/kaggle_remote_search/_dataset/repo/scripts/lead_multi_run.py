"""Run several repo scripts one after the other in ONE process slot (so one Kaggle kernel can do smoke + G1).

usage: lead_multi_run.py <script> <args...> :: <script> <args...> [:: ...]
Commands are separated by a '::' token (remote_panel pushcmd splits its command line on spaces); each is run with
this interpreter from the repo root.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cmds, cur = [], []
    for tok in sys.argv[1:]:
        if tok == '::':
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        cmds.append(cur)
    rc = 0
    for parts in cmds:
        print('== running', parts, flush=True)
        r = subprocess.run([sys.executable] + parts, cwd=ROOT)
        print('== exit', r.returncode, flush=True)
        rc = rc or r.returncode
    sys.exit(rc)


if __name__ == '__main__':
    main()

"""Run several semantic-stack candidates over several panels in one process tree (one Kaggle kernel): for each panel,
scripts/semantic_h2h_20260929.py run --candidate c1,c2,... (a subprocess each, so the process pool pickles its worker from
that script's own __main__).

usage: sem_panel_multi_20260929.py --candidates c1,c2 --panel SEEDS:OUT [--panel SEEDS:OUT ...] [--study DIR]
       [--workers 4] [--no-timeout]
  SEEDS is `dev` (the study's development live cases) or a seeds json; OUT is the output root (one folder per candidate)"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--panel", action="append", required=True)
    ap.add_argument("--study", default="results/fresh/semantic_h2h_20260929/study")
    ap.add_argument("--workers", default="4")
    ap.add_argument("--no-timeout", action="store_true")
    ap.add_argument("--force", action="store_true", help="panel spec SEEDS:OUT:REFDIR - shops forced from REFDIR")
    ap.add_argument("--leader-credit", action="store_true")
    ap.add_argument("--leader-credit-exact", action="store_true")
    ap.add_argument("--leader-weeds", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()
    rc = 0
    for panel in a.panel:
        seeds, out, ref = (panel.split(":") + [None])[:3]
        cmd = [sys.executable, str(ROOT / "scripts/semantic_h2h_20260929.py"), "run", "--study", a.study,
               "--candidate", a.candidates, "--seeds", seeds, "--out", out, "--workers", a.workers]
        if ref:
            cmd += ["--force-shops-from", ref]
        if a.no_timeout:
            cmd.append("--no-timeout")
        if a.leader_credit:
            cmd.append("--leader-credit")
        if a.leader_credit_exact:
            cmd.append("--leader-credit-exact")
        if a.leader_weeds:
            cmd.append("--leader-weeds")
        if a.only:
            cmd += ["--only", a.only]
        print("panel", panel, flush=True)
        rc |= subprocess.run(cmd, cwd=str(ROOT)).returncode
    raise SystemExit(rc)


if __name__ == "__main__":
    main()

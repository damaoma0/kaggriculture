"""Official-runner test of packaged agents (the way Kaggle loads and times a submission): both packages are copied into
a fresh empty directory, the process runs from another empty directory with every repository path removed from
sys.path, and kaggle_environments loads each main.py through its own file loader (get_last_callable) and charges its
own overage bank (actTimeout 1 s, remainingOverageTime 60 s; an agent past the bank ends with status TIMEOUT). One
game at a time.

usage: official_runner_test_20260929.py --pkg DIR --opp DIR --seeds FILE [--ids a,b,...] --out FILE.json
  per game: seed, seat, status of both, final cash, our remaining bank, our largest step, modules loaded from the repo"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--opp", required=True)
    ap.add_argument("--seeds", required=True)
    ap.add_argument("--ids", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--worker", action="store_true", help="internal: play the listed games in this process")
    a = ap.parse_args()
    cases = json.loads(Path(a.seeds).read_text())["cases"]
    if a.ids:
        cases = [c for c in cases if c["id"] in a.ids.split(",")]
    out = Path(a.out).resolve()
    rows = json.loads(out.read_text()) if out.exists() else []
    done = {r["id"] for r in rows}
    if not a.worker:                               # one fresh process per game (a submission gets its own process)
        import subprocess
        for c in cases:
            if c["id"] not in done:
                subprocess.run([sys.executable, str(Path(__file__).resolve()), "--pkg", a.pkg, "--opp", a.opp, "--seeds",
                                a.seeds, "--ids", c["id"], "--out", str(out), "--worker"], cwd=str(ROOT))
        return
    pkg_src, opp_src = Path(a.pkg).resolve(), Path(a.opp).resolve()
    repo = str(ROOT.resolve())

    def in_repo(p_):                               # the repository's own code (an in-repo virtualenv is the runtime)
        p_ = str(Path(p_).resolve())
        return p_.startswith(repo) and "site-packages" not in p_ and ".venv" not in p_
    sys.path[:] = [p for p in sys.path if p and not in_repo(p)]
    for c in cases:
        if c["id"] in done:
            continue
        box = Path(tempfile.mkdtemp(prefix="kgr_official_"))
        shutil.copytree(pkg_src, box / "agent")
        shutil.copytree(opp_src, box / "opponent")
        for f in list(box.rglob("*.gz.raw")):     # remote bundles store .gz payloads as .gz.raw (KGR_GZ_RAW)
            f.rename(str(f)[:-4])
        run_dir = box / "cwd"
        run_dir.mkdir()
        os.chdir(run_dir)
        before = set(sys.modules)
        from kaggle_environments import make
        env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 1}, info={"seed": c["seed"]})
        seat = int(c["seat"])
        agents = [str(box / "opponent" / "main.py")] * 2
        agents[seat] = str(box / "agent" / "main.py")
        t0 = time.time()
        steps = env.run(agents)
        last = steps[-1]
        rem = [s[seat]["observation"].get("remainingOverageTime") for s in steps if s[seat].get("observation")]
        logs = env.logs if hasattr(env, "logs") else []
        our_steps = [lg[seat].get("duration", 0.0) for lg in logs if lg and len(lg) > seat and isinstance(lg[seat], dict)]
        repo_mods = sorted({getattr(m, "__file__", "") for k, m in sys.modules.items() if k not in before
                            and getattr(m, "__file__", None) and in_repo(m.__file__)})
        opp = 1 - seat
        row = dict(id=c["id"], seed=c["seed"], seat=seat, status=[last[0]["status"], last[1]["status"]],
                   reward=[last[0].get("reward"), last[1].get("reward")],
                   our_remaining_bank=rem[-1] if rem else None, our_bank_min=min(rem) if rem else None,
                   our_max_step=round(max(our_steps), 3) if our_steps else None,
                   our_steps_over_1s=sum(1 for x in our_steps if x > 1.0),
                   margin=(last[seat].get("reward") or 0) - (last[opp].get("reward") or 0)
                   if last[seat].get("reward") is not None and last[opp].get("reward") is not None else None,
                   wall=round(time.time() - t0, 1), repo_modules=repo_mods, n_steps=len(steps))
        rows.append(row)
        out.write_text(json.dumps(rows, indent=1))
        print(json.dumps({k: row[k] for k in ("id", "status", "reward", "our_remaining_bank", "our_max_step",
                                              "our_steps_over_1s", "margin", "wall")}), flush=True)
        os.chdir(str(ROOT))
        shutil.rmtree(box, ignore_errors=True)


if __name__ == "__main__":
    main()

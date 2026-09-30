"""Resumable executable benchmark for segment-stitching agents.

This is a runner only: it does not select outcomes, force shops, or alter the
engine.  Each game is executed in a fresh worker process and its failure row is
written so an incomplete panel cannot be mistaken for a complete one.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import re
import traceback
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_PATHS = {
    "mgt_m1": ROOT / "agents/mgt_m1.py",
    "mgt_segment_stitch": ROOT / "agents/mgt_segment_stitch.py",
    "v56": ROOT / "data/router_refresh_20260922/v56/main.py",
}


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def parse_names(value):
    return [x.strip() for x in value.split(",") if x.strip()]


def _source_paths(names):
    paths = {}
    for name in set(names):
        path = DEFAULT_AGENT_PATHS.get(name, ROOT / "agents" / (name + ".py"))
        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
            raise ValueError(f"unsafe agent name: {name}")
        if not path.is_file():
            raise FileNotFoundError(f"missing source for {name}: {path}")
        paths[name] = path
    return paths


def make_manifest(out, agents, opponents, seeds):
    out.mkdir(parents=True, exist_ok=True)
    (out / "games").mkdir(exist_ok=True)
    (out / "logs").mkdir(exist_ok=True)
    names = agents + opponents
    paths = _source_paths(names)
    frozen = out / "frozen"
    frozen.mkdir(exist_ok=True)
    if (out / "manifest.json").exists():
        old = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        if (old.get("agents"), old.get("opponents"), old.get("seeds")) != (agents, opponents, seeds):
            raise RuntimeError("existing manifest parameters differ; use a new --out")
        for name, relative in old["source_paths"].items():
            path = ROOT / relative
            if not path.is_file() or digest(path) != old["source_hashes"][name]:
                raise RuntimeError(f"frozen source changed or missing: {name}")
        return old
    frozen_paths = {}
    for name, path in paths.items():
        target = frozen / (name + ".py")
        target.write_bytes(path.read_bytes())
        frozen_paths[name] = target
    manifest = {
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agents": agents,
        "opponents": opponents,
        "seeds": seeds,
        "seats": [0, 1],
        "episode_steps": 720,
        "expected_games": len(agents) * len(opponents) * len(seeds) * 2,
        "source_paths": {k: str(v.relative_to(ROOT)) for k, v in frozen_paths.items()},
        "source_hashes": {k: digest(v) for k, v in frozen_paths.items()},
        "design": "Natural RNG Kaggriculture games; fresh process per game; no forced shops or early stopping.",
    }
    write_json(out / "manifest.json", manifest)
    return manifest


def _capture_globals(function):
    globs = function.__globals__
    names = ("SEGMENT_REPORT", "_SHP_REPORT", "_MGT_REPORT", "_MGT_HISTORY", "_ROT_REPORT", "_TV_REPORT")
    return {name: globs.get(name) for name in names if name in globs}


def _run_job(job):
    seed, seat, agent_name, opponent_name, manifest, out_text = job
    out = Path(out_text)
    key = f"{agent_name}-{opponent_name}-{seed}-{seat}"
    destination = out / "games" / f"{key}.json"
    started = time.perf_counter()
    row = {
        "seed": seed, "seat": seat, "agent": agent_name,
        "opponent": opponent_name, "completed": False, "errors": [],
        "own_sha256": manifest["source_hashes"][agent_name],
        "opponent_sha256": manifest["source_hashes"][opponent_name],
    }
    log_path = out / "logs" / f"{key}.log"
    with log_path.open("w", encoding="utf-8") as log:
        old_out, old_err = os.dup(1), os.dup(2)
        try:
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
            from importlib.metadata import version
            from kaggle_environments import make
            from kaggle_environments.agent import get_last_callable
            from kaggle_environments.envs.kaggriculture import kaggriculture as E
            import tape_vs_bench as TV

            functions, loading, elapsed = {}, {}, {"own": [], "opponent": []}
            role_sources = {"own": (agent_name, manifest["source_paths"][agent_name]),
                            "opponent": (opponent_name, manifest["source_paths"][opponent_name])}
            for role, (name, relative) in role_sources.items():
                path = ROOT / relative
                if digest(path) != manifest["source_hashes"][name]:
                    raise RuntimeError(f"source changed during run: {name}")
                tick = time.perf_counter()
                functions[role] = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
                loading[role] = time.perf_counter() - tick

            def timed(role):
                def act(obs, step):
                    before = time.perf_counter()
                    try:
                        return functions[role](obs)
                    except Exception:
                        row["errors"].append({"policy": role, "step": step, "trace": traceback.format_exc()})
                        raise
                    finally:
                        elapsed[role].append(time.perf_counter() - before)
                return act

            players = [None, None]
            players[seat] = timed("own")
            players[1 - seat] = timed("opponent")
            env = make("kaggriculture", configuration={"episodeSteps": 720}, info={"seed": seed})
            result = TV._play(E, env, players, seat, None, None, None, seat)
            final = result["final"]
            row.update({
                "cash": final[seat], "opponent_cash": final[1 - seat],
                "margin": final[seat] - final[1 - seat],
                "shops": list(env.state[0].observation.town.unlocked_shops),
                "statuses": [s.status for s in env.state],
                "states": len(env.steps), "actions": len(result["actions"]),
                "ledger_verified": True, "daily": result["daily"],
                "configuration": dict(env.configuration),
                "engine_version": version("kaggle-environments"),
                "loading_seconds": loading,
                "agent_reports": {"own": _capture_globals(functions["own"]),
                                  "opponent": _capture_globals(functions["opponent"])},
                "action_sha256": sha256(json.dumps(result["actions"], sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                "completed": True,
            })
            assert len(result["actions"]) == 719
            assert len(env.steps) == 720
            assert not row["errors"]
        except Exception:
            row["completed"] = False
            row["error"] = traceback.format_exc()
            if "env" in locals():
                row["statuses"] = [s.status for s in env.state]
                row["states"] = len(env.steps)
        finally:
            if "elapsed" in locals():
                row["timing"] = {name: {"calls": len(ts), "max_seconds": max(ts, default=0),
                                        "total_seconds": sum(ts), "over_1s": sum(t > 1 for t in ts)}
                                  for name, ts in elapsed.items()}
            row["wall_seconds"] = time.perf_counter() - started
            os.dup2(old_out, 1); os.dup2(old_err, 2)
            os.close(old_out); os.close(old_err)
            write_json(destination, row)
    return {k: row.get(k) for k in ("seed", "seat", "agent", "opponent", "completed", "margin", "error")}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--agents", default="mgt_m1,mgt_segment_stitch")
    p.add_argument("--seeds", required=True, help="comma-separated integer seeds")
    p.add_argument("--opponents", default="v56,mgt_m1")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    agents, opponents = parse_names(args.agents), parse_names(args.opponents)
    seeds = [int(x) for x in parse_names(args.seeds)]
    if not seeds or len(set(seeds)) != len(seeds):
        p.error("--seeds must contain at least one unique integer")
    out = (ROOT / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
    manifest = make_manifest(out, agents, opponents, seeds)
    jobs = []
    for agent in agents:
        for opponent in opponents:
            for seed in seeds:
                for seat in (0, 1):
                    dest = out / "games" / f"{agent}-{opponent}-{seed}-{seat}.json"
                    if dest.exists():
                        cached = json.loads(dest.read_text(encoding="utf-8"))
                        if ((cached.get('agent'), cached.get('opponent'), cached.get('seed'), cached.get('seat')) !=
                                (agent, opponent, seed, seat) or
                                cached.get('own_sha256') != manifest['source_hashes'][agent] or
                                cached.get('opponent_sha256') != manifest['source_hashes'][opponent]):
                            raise RuntimeError(f"cached row identity/hash mismatch: {dest}")
                        continue
                    jobs.append((seed, seat, agent, opponent, manifest, str(out)))
    print(json.dumps({"expected": manifest["expected_games"], "pending": len(jobs), "workers": args.workers}), flush=True)
    with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
        futures = {pool.submit(_run_job, job): job for job in jobs}
        for future in as_completed(futures):
            try:
                print(json.dumps(future.result()), flush=True)
            except Exception:
                job = futures[future]
                seed, seat, agent, opponent, _, out_text = job
                row = {"seed": seed, "seat": seat, "agent": agent, "opponent": opponent,
                       "completed": False, "errors": [], "error": traceback.format_exc(),
                       "own_sha256": manifest["source_hashes"][agent],
                       "opponent_sha256": manifest["source_hashes"][opponent]}
                write_json(Path(out_text) / "games" / f"{agent}-{opponent}-{seed}-{seat}.json", row)


if __name__ == "__main__":
    main()

"""Paired, resumable crop-replacement benchmark on the official engine.

Each policy/seed/seat/opponent cell runs in a fresh worker process.  Controlled
shop schedules are sampled independently of the engine RNG and exposed only as
the engine reveals shops.  Natural-shop comparisons are paired by seed, but
their realized schedules may diverge when policies change weed/RNG consumption.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import random
import re
from statistics import mean
import time
import traceback


SHARED_ROOT = Path(r"C:\Users\xyygl\Documents\kaggriculture")
DEFAULT_BASELINE = SHARED_ROOT / "agents/v45_event_opening_fixed.py"
OPPONENT_PATHS = {
    name: SHARED_ROOT / "data/router_refresh_20260916" / name / "main.py"
    for name in ("v45", "twocoins", "v44", "farmingv5", "pasture2700")
}
SHOP_SEED_XOR = 0xC20F5EED


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def jsonable(value):
    """Take a compact, detached JSON-safe snapshot of optional agent telemetry."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    try:
        return jsonable(vars(value))
    except TypeError:
        return repr(value)


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


class Ledger:
    """Record successful engine transactions, including exact daily hire spend."""

    def __init__(self, engine):
        self.engine = engine
        self.data = [
            {"revenue": Counter(), "sold_units": Counter(), "spend": Counter(),
             "hire_cost_by_day": Counter()}
            for _ in range(2)
        ]
        self.seats = {}
        self.day = None

    def __enter__(self):
        engine = self.engine
        names = ("_process_market", "_commit_unit", "_do_hire", "_do_buy_land")
        self.original = {name: getattr(engine, name) for name in names}

        def market(state, environment):
            self.seats = {id(farm): seat for seat, farm in enumerate(state[0].observation.farms)}
            self.day = int(state[0].observation.day)
            return self.original["_process_market"](state, environment)

        def commit(operation, item, price, farm, private, market_state, shed_capacity=100):
            result = self.original["_commit_unit"](
                operation, item, price, farm, private, market_state, shed_capacity
            )
            if result:
                row = self.data[self.seats[id(farm)]]
                if operation == "SELL":
                    row["revenue"][item] += price
                    row["sold_units"][item] += 1
                else:
                    row["spend"][operation + ":" + item] += price
            return result

        def atomic(name, category):
            def run(farm, *args):
                before = farm["money"]
                result = self.original[name](farm, *args)
                cost = before - farm["money"]
                row = self.data[self.seats[id(farm)]]
                row["spend"][category] += cost
                if category == "HIRE" and cost:
                    row["hire_cost_by_day"][str(self.day)] += cost
                return result
            return run

        engine._process_market = market
        engine._commit_unit = commit
        engine._do_hire = atomic("_do_hire", "HIRE")
        engine._do_buy_land = atomic("_do_buy_land", "BUY_LAND")
        return self

    def __exit__(self, *exc):
        for name, original in self.original.items():
            setattr(self.engine, name, original)


def crop_counts(farm) -> dict[str, int]:
    crops = Counter()
    for row in farm["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                crops[tile["crop"]] += 1
    return dict(sorted(crops.items()))


def daily_diagnostics(env, ledger: Ledger) -> list[list[dict]]:
    """End-of-day board snapshots; day 29 uses the terminal state at step 719."""
    output = [[], []]
    for day in range(30):
        step = min((day + 1) * 24, 719)
        farms = env.steps[step][0].observation.farms
        for seat in (0, 1):
            output[seat].append({
                "day": day,
                "step": step,
                "crops": crop_counts(farms[seat]),
                "hands": len(farms[seat]["hands"]),
                "hire_cost": ledger.data[seat]["hire_cost_by_day"].get(str(day), 0),
            })
    return output


def load_file_agent(path: Path):
    """Use the competition's actual source-file loader for every participant."""
    from kaggle_environments.agent import get_last_callable

    return get_last_callable(path.read_text(encoding="utf-8"), path=str(path))


def controlled_schedule(seed: int, engine) -> list[str]:
    return random.Random(seed ^ SHOP_SEED_XOR).choices(sorted(engine.SHOPS), k=8)


def game_path(out: Path, job: dict) -> Path:
    return out / "games" / (
        f"{job['shops']}-{job['opponent']}-{job['opponent_hash'][:10]}-"
        f"seed{job['seed']}-seat{job['seat']}-{job['policy_id']}.json"
    )


def compact_job(job: dict) -> dict:
    return {key: job[key] for key in (
        "seed", "seat", "shops", "opponent", "opponent_path", "opponent_hash",
        "policy_kind", "policy_id", "policy_path", "policy_hash",
    )}


def run_game(job: dict) -> dict:
    """Worker entry point: one and only one full game in this process."""
    destination = Path(job["destination"])
    if existing_success(destination, job):
        return {"status": "ok", "path": str(destination), "job": compact_job(job), "resumed": True}
    try:
        from kaggle_environments import make
        from kaggle_environments.envs.kaggriculture import kaggriculture as engine

        policy_path = Path(job["policy_path"])
        opponent_path = Path(job["opponent_path"])
        assert file_hash(policy_path) == job["policy_hash"], "policy source changed after manifest creation"
        assert file_hash(opponent_path) == job["opponent_hash"], "opponent source changed after manifest creation"
        policy = load_file_agent(policy_path)
        opponent = load_file_agent(opponent_path)
        env = make("kaggriculture", configuration={"seed": job["seed"], "episodeSteps": 720})

        planned_shops = None
        original_end = engine._end_of_day
        if job["shops"] == "controlled":
            planned_shops = controlled_schedule(job["seed"], engine)

            def end_of_day(state, environment, day):
                original_end(state, environment, day)
                revealed = state[0].observation.town.unlocked_shops
                revealed[:] = planned_shops[:len(revealed)]

            engine._end_of_day = end_of_day

        calls = [0, 0]
        elapsed = [[], []]

        def timed_agent(agent, participant):
            def call(observation):
                started = time.perf_counter()
                action = agent(observation)
                elapsed[participant].append(time.perf_counter() - started)
                calls[participant] += 1
                assert isinstance(action, dict), (
                    f"participant {participant} returned {type(action).__name__} "
                    f"at step {observation.get('step')}"
                )
                return action
            return call

        players = [None, None]
        players[job["seat"]] = timed_agent(policy, job["seat"])
        players[1 - job["seat"]] = timed_agent(opponent, 1 - job["seat"])
        started = time.perf_counter()
        try:
            with Ledger(engine) as ledger:
                env.run(players)
        finally:
            engine._end_of_day = original_end

        assert len(env.steps) == 720, ("expected 720 states", len(env.steps), env.logs[-3:])
        assert env.steps[-1][0].observation.step == 719
        assert calls == [719, 719], ("expected 719 actions per participant", calls)
        assert all(state.status == "DONE" for state in env.state), (
            "terminal states not DONE", [state.status for state in env.state], env.logs[-3:]
        )
        assert all(
            isinstance(states[seat].action, dict)
            for states in env.steps[1:] for seat in (0, 1)
        ), "non-dict action recorded"

        initial_cash = [env.steps[0][0].observation.farms[i]["money"] for i in (0, 1)]
        final_cash = [env.state[i].reward for i in (0, 1)]
        for seat in (0, 1):
            account = ledger.data[seat]
            calculated = (
                initial_cash[seat]
                + sum(account["revenue"].values())
                - sum(account["spend"].values())
            )
            assert calculated == final_cash[seat], (
                "cash ledger does not reconcile", seat, calculated, final_cash[seat]
            )

        policy_globals = getattr(policy, "__globals__", {})
        cohort_stats = deepcopy(policy_globals["_COHORT_STATS"]) \
            if job["policy_kind"] == "candidate" and "_COHORT_STATS" in policy_globals else None
        row = {
            "status": "ok",
            "job": compact_job(job),
            "hashes": {
                "policy_sha256": job["policy_hash"],
                "opponent_sha256": job["opponent_hash"],
            },
            "shops": {
                "mode": job["shops"],
                "planned": planned_shops,
                "realized": list(env.state[0].observation.town.unlocked_shops),
            },
            "final": {
                "cash": final_cash,
                "policy_cash": final_cash[job["seat"]],
                "opponent_cash": final_cash[1 - job["seat"]],
                "margin": final_cash[job["seat"]] - final_cash[1 - job["seat"]],
            },
            "ledger": jsonable(ledger.data),
            "timing": {
                "wall_seconds": round(time.perf_counter() - started, 4),
                "policy": {
                    "total_seconds": round(sum(elapsed[job["seat"]]), 6),
                    "max_seconds": round(max(elapsed[job["seat"]]), 6),
                },
                "opponent": {
                    "total_seconds": round(sum(elapsed[1 - job["seat"]]), 6),
                    "max_seconds": round(max(elapsed[1 - job["seat"]]), 6),
                },
            },
            "action_counts": calls,
            "candidate_stats": jsonable(cohort_stats),
            "daily": daily_diagnostics(env, ledger),
        }
        atomic_json(destination, row)
        return {"status": "ok", "path": str(destination), "job": compact_job(job)}
    except BaseException as exc:
        failure = {
            "status": "failed",
            "job": compact_job(job),
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        atomic_json(destination, failure)
        return {"status": "failed", "path": str(destination), "job": compact_job(job),
                "error": failure["error"]}


def safe_name(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", path.stem).strip("-") or "agent"
    return stem[:48]


def parse_seeds(text: str) -> list[int]:
    try:
        seeds = list(dict.fromkeys(int(part.strip()) for part in text.split(",") if part.strip()))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("seeds must be comma-separated integers") from exc
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return seeds


def parse_opponents(text: str) -> list[str]:
    opponents = list(dict.fromkeys(part.strip() for part in text.split(",") if part.strip()))
    unknown = [name for name in opponents if name not in OPPONENT_PATHS]
    if not opponents or unknown:
        allowed = ",".join(OPPONENT_PATHS)
        raise argparse.ArgumentTypeError(f"opponents must be comma-separated names from {allowed}")
    return opponents


def require_absolute(parser, path: Path, option: str) -> Path:
    if not path.is_absolute():
        parser.error(f"{option} must be an absolute path: {path}")
    return path.resolve()


def existing_success(path: Path, job: dict) -> bool:
    if not path.exists():
        return False
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return row.get("status") == "ok" and row.get("job") == compact_job(job)


def records_for(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    successes, failures = [], []
    for job in jobs:
        path = Path(job["destination"])
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append({"job": compact_job(job), "error": f"unreadable result: {exc}"})
            continue
        if row.get("status") == "ok":
            successes.append(row)
        else:
            failures.append({"job": row.get("job", compact_job(job)),
                             "error": row.get("error", "unknown failure")})
    return successes, failures


def record(values) -> dict[str, int]:
    values = list(values)
    return {
        "wins": sum(value > 0 for value in values),
        "ties": sum(value == 0 for value in values),
        "losses": sum(value < 0 for value in values),
    }


def build_summary(jobs: list[dict], policies: list[dict], opponents: list[str], shops: str) -> dict:
    rows, failures = records_for(jobs)
    index = {
        (row["job"]["policy_id"], row["job"]["opponent"],
         row["job"]["seed"], row["job"]["seat"]): row
        for row in rows
    }
    baseline_id = next(policy["id"] for policy in policies if policy["kind"] == "baseline")
    candidate_summary = {}
    for policy in (p for p in policies if p["kind"] == "candidate"):
        by_opponent = {}
        for opponent in opponents:
            seeds = sorted({job["seed"] for job in jobs if job["opponent"] == opponent})
            clusters, incomplete = [], []
            for seed in seeds:
                pairs = []
                for seat in (0, 1):
                    baseline = index.get((baseline_id, opponent, seed, seat))
                    candidate = index.get((policy["id"], opponent, seed, seat))
                    if baseline and candidate:
                        pairs.append({
                            "seat": seat,
                            "cash_delta": candidate["final"]["policy_cash"] - baseline["final"]["policy_cash"],
                            "margin_delta": candidate["final"]["margin"] - baseline["final"]["margin"],
                            "candidate_margin": candidate["final"]["margin"],
                            "baseline_margin": baseline["final"]["margin"],
                            "same_realized_shops": (
                                candidate["shops"]["realized"] == baseline["shops"]["realized"]
                            ),
                        })
                if len(pairs) != 2:
                    incomplete.append({"seed": seed, "complete_seat_pairs": len(pairs)})
                    continue
                cluster = {
                    "seed": seed,
                    "seat_pairs": pairs,
                    "mean_cash_delta": mean(pair["cash_delta"] for pair in pairs),
                    "mean_margin_delta": mean(pair["margin_delta"] for pair in pairs),
                    "mean_candidate_margin": mean(pair["candidate_margin"] for pair in pairs),
                    "mean_baseline_margin": mean(pair["baseline_margin"] for pair in pairs),
                    "identical_realized_shops_both_seats": all(
                        pair["same_realized_shops"] for pair in pairs
                    ),
                }
                clusters.append(cluster)
            margin_deltas = [cluster["mean_margin_delta"] for cluster in clusters]
            cash_deltas = [cluster["mean_cash_delta"] for cluster in clusters]
            candidate_margins = [cluster["mean_candidate_margin"] for cluster in clusters]
            worst = min(clusters, key=lambda cluster: cluster["mean_margin_delta"]) if clusters else None
            by_opponent[opponent] = {
                "seed_clusters": clusters,
                "complete_seed_clusters": len(clusters),
                "incomplete_seeds": incomplete,
                "paired_delta_by_seed_cluster": {
                    "mean_cash": mean(cash_deltas) if cash_deltas else None,
                    "mean_margin": mean(margin_deltas) if margin_deltas else None,
                    "candidate_better_tie_worse": record(margin_deltas),
                },
                "candidate_win_tie_loss_by_seed_cluster": record(candidate_margins),
                "worst_seed": ({
                    "seed": worst["seed"],
                    "mean_margin_delta": worst["mean_margin_delta"],
                    "mean_candidate_margin": worst["mean_candidate_margin"],
                } if worst else None),
            }
        candidate_summary[policy["id"]] = {
            "path": policy["path"],
            "sha256": policy["hash"],
            "by_opponent": by_opponent,
        }
    note = (
        "Controlled shops use the same independently seeded hidden schedule for paired games."
        if shops == "controlled" else
        "Natural-shop games share the engine seed, but policy-dependent weed RNG consumption can "
        "change realized schedules; shop equality is reported per pair and is not assumed."
    )
    return {
        "status": "complete" if not failures else "completed_with_failures",
        "valid_games": len(rows),
        "failed_or_missing_games": len(failures),
        "failures": failures,
        "statistical_unit": "seed cluster; the two seat replicates are averaged, not treated as independent",
        "shop_note": note,
        "candidates": candidate_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", type=Path, required=True,
                        help="absolute path to a standalone candidate agent; repeatable")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE,
                        help="baseline agent path (default: shared V45 event-opening agent)")
    parser.add_argument("--out", type=Path, required=True, help="absolute output directory")
    parser.add_argument("--seeds", type=parse_seeds, required=True,
                        help="comma-separated integer seeds")
    parser.add_argument("--opponents", type=parse_opponents, default=parse_opponents("v45,twocoins"),
                        help="comma-separated opponent names (default: v45,twocoins)")
    parser.add_argument("--shops", choices=("natural", "controlled"), default="natural")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()

    out = require_absolute(parser, args.out, "--out")
    baseline = require_absolute(parser, args.baseline, "--baseline")
    candidates = [require_absolute(parser, path, "--candidate") for path in args.candidate]
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    for option, paths in (("--baseline", [baseline]), ("--candidate", candidates)):
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            parser.error(f"{option} file not found: {', '.join(missing)}")
    missing_opponents = [str(OPPONENT_PATHS[name]) for name in args.opponents
                         if not OPPONENT_PATHS[name].is_file()]
    if missing_opponents:
        parser.error("opponent file not found: " + ", ".join(missing_opponents))

    source_paths = [("baseline", baseline), *(("candidate", path) for path in candidates)]
    policies, seen = [], set()
    for kind, path in source_paths:
        digest = file_hash(path)
        identity = (kind, str(path), digest)
        if identity in seen:
            continue
        seen.add(identity)
        prefix = "baseline" if kind == "baseline" else "candidate-" + safe_name(path)
        policies.append({"kind": kind, "path": str(path), "hash": digest,
                         "id": f"{prefix}-{digest[:10]}"})

    opponent_specs = {
        name: {"path": str(OPPONENT_PATHS[name].resolve()), "hash": file_hash(OPPONENT_PATHS[name])}
        for name in args.opponents
    }
    jobs = []
    for opponent in args.opponents:
        spec = opponent_specs[opponent]
        for seed in args.seeds:
            for seat in (0, 1):
                for policy in policies:
                    job = {
                        "seed": seed,
                        "seat": seat,
                        "shops": args.shops,
                        "opponent": opponent,
                        "opponent_path": spec["path"],
                        "opponent_hash": spec["hash"],
                        "policy_kind": policy["kind"],
                        "policy_id": policy["id"],
                        "policy_path": policy["path"],
                        "policy_hash": policy["hash"],
                    }
                    job["destination"] = str(game_path(out, job))
                    jobs.append(job)

    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "engine": version("kaggle-environments"),
        "policies": policies,
        "opponents": opponent_specs,
        "seeds": args.seeds,
        "shops": args.shops,
        "workers": args.workers,
        "games": len(jobs),
        "design": (
            "Baseline and each candidate run in both seats against each opponent. Each game uses "
            "a fresh worker process. Seed is the independent cluster; seats are paired replicates."
        ),
        "controlled_shops": (
            "Eight uniform draws with replacement from sorted engine shops, seeded independently "
            "of farm RNG and installed only after each end-of-day reveal."
        ),
        "natural_shop_caveat": (
            "Natural shops are not guaranteed to match within seed because weed spawning and shop "
            "draws share engine RNG whose consumption can depend on both farms."
        ),
    }
    atomic_json(out / "manifest.json", manifest)

    pending = [job for job in jobs if not existing_success(Path(job["destination"]), job)]
    print(f"{len(jobs) - len(pending)} resumed; {len(pending)} games pending", flush=True)
    if pending:
        with ProcessPoolExecutor(max_workers=args.workers, max_tasks_per_child=1) as pool:
            futures = {pool.submit(run_game, job): job for job in pending}
            for completed, future in enumerate(as_completed(futures), 1):
                job = futures[future]
                try:
                    result = future.result()
                except BaseException as exc:
                    failure = {
                        "status": "failed",
                        "job": compact_job(job),
                        "error": f"worker failure: {type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                    }
                    atomic_json(Path(job["destination"]), failure)
                    result = {"status": "failed", "error": failure["error"]}
                print(f"{completed}/{len(pending)} {job['policy_id']} {job['opponent']} "
                      f"seed={job['seed']} seat={job['seat']} {result['status']}", flush=True)

    summary = build_summary(jobs, policies, args.opponents, args.shops)
    atomic_json(out / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in
                      ("status", "valid_games", "failed_or_missing_games")}), flush=True)


if __name__ == "__main__":
    main()

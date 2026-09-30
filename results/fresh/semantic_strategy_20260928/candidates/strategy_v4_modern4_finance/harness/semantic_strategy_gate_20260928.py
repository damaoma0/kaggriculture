"""Frozen local full-season gates for a causal semantic strategy agent.

prepare                      freeze random development/qualification worlds
freeze --id ID --entry FILE --files FILE,... [--training-episodes JSON]
release --candidate ID       explicitly release a frozen candidate to qualification
run --candidate ID --split development --mode live|recorded [--workers 2]
report --candidate ID --split development --mode live|recorded

No oracle opening or future semantic plan is passed to the candidate. Recorded
opponents keep their native seed, shops and commands. Only original-recording
control failure may trigger a preordered, candidate-blind reserve replacement;
candidate-induced opponent breakage makes that gate incomplete.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import gzip
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import random
import secrets
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDY = ROOT / "results/fresh/semantic_strategy_20260928"
HELPERS = ("tape_vs_bench.py", "analyze_efficiency.py", "evaluate_boards.py", "market_corpus.py")
PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def verify_files(base, hashes):
    for relative, expected in hashes.items():
        if sha(Path(base) / relative) != expected:
            raise ValueError("Frozen source/input changed: " + relative)


def prepare(study):
    destination = study / "protocol.json"
    if destination.exists():
        return read(destination)
    study.mkdir(parents=True, exist_ok=True)
    master = secrets.randbits(128)
    rng = random.Random(master)
    old_seeds = set(range(93021000, 93024000))
    manifests = list((ROOT / "results/fresh").glob("**/manifest.json"))
    for path in manifests:
        try:
            value = read(path)
            old_seeds.update(int(x) for x in value.get("seeds", []) if isinstance(x, (int, str)))
        except (ValueError, TypeError, OSError):
            continue
    seeds = []
    while len(seeds) < 48:
        seed = rng.randrange(1, 2 ** 32)
        if seed not in old_seeds and seed not in seeds:
            seeds.append(seed)
    excluded_episodes = sorted({p.name.split(".")[0] for folder in ("data/leader_semantics", "data/mg_tapes")
                                for p in (ROOT / folder).rglob("*.json.gz")})
    index_path = ROOT / "data/ladder_panel/p2750/index.json"
    index = read(index_path)
    eligible = sorted(ep for ep, item in index["games"].items()
                      if 2750 <= float(item["band_score"]) <= 3000 and ep not in excluded_episodes)
    if len(eligible) < 48:
        raise ValueError("Fewer than 48 training-disjoint historical worlds")
    rng.shuffle(eligible)
    recorded = []
    for episode in eligible:
        source = ROOT / "data/ladder_panel/p2750" / f"{episode}.json.gz"
        target = study / "recordings" / source.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(source, target)
        game = json.loads(gzip.decompress(source.read_bytes()))
        # Rewards are not inspected or used to select/order worlds.
        recorded.append(dict(id="recorded-" + episode, episode=episode, seed=int(game["seed"]),
            seat=int(game["seat"]), file=target.relative_to(study).as_posix(), sha256=sha(target),
            opponent=index["games"][episode]["band_team"],
            opponent_team_id=index["games"][episode]["band_team_id"],
            historical_rating=float(index["games"][episode]["band_score"])))
    opponent_source = ROOT / "submissions/2026-09-24-mgt_v9lite/pkg"
    opponent_manifest = read(opponent_source.parent / "MANIFEST.json")["files"]
    verify_files(opponent_source, opponent_manifest)
    opponent_dest = study / "opponent/pkg"
    shutil.copytree(opponent_source, opponent_dest)
    live = [dict(id=f"live-{i:02d}", seed=seed, seat=i % 2) for i, seed in enumerate(seeds)]
    protocol = dict(schema_version=1, created_utc=utc(), master_seed=master,
        engine="kaggle-environments==1.32.7", episode_steps=720, action_timeout=1.0,
        overage_seconds=60.0, candidate_start_step=0, no_oracle_opening=True,
        candidate_input="Only current official observation and configuration; no episode identity, future shops or future semantic counts are supplied.",
        opponent=dict(name="mgt_v9lite", entry="opponent/pkg/main.py", files=opponent_manifest,
                      source="submissions/2026-09-24-mgt_v9lite/pkg", warmup_thread=False),
        source_index_sha256=sha(index_path), training_episode_exclusions=excluded_episodes,
        seed_exclusion_count=len(old_seeds),
        development=dict(live=live[:8], recorded=recorded[:8]),
        qualification=dict(live=live[8:], recorded=recorded[8:48]),
        recorded_reserve=recorded[48:],
        selection="Outcome-blind random sample/order. Live gate uses 40 distinct fresh seeds and 20 games in each seat. Historical gate samples native seed/shop/script worlds from the dated p2750 corpus, not fresh opponent policies.",
        recorded_validity=dict(extra_failed_commands_limit=40,
            failures="no_effect + missing_worker_commands + malformed_commands",
            source_control="Replay both original action streams, require 720 states, DONE/DONE and both recorded cash totals exactly.",
            replacements="Only a failing original-source control can be replaced, before candidate execution, by the next unused reserve with a valid original control. Every attempt is logged. Candidate-induced breakage is never replaced.",
            incomplete_rule="Any candidate/runtime/ledger failure or material rival-script break makes the fixed gate incomplete; no invalid win is counted and losses are not selectively excluded."),
        live_shops="Natural engine RNG. No forced shops or weeds.",
        recorded_shops="Recorded shops, native seed and native seat; no fresh-seed relabeling and no artificial budget cushion.",
        qualification_rule="Must freeze and explicitly release one candidate before qualification. Do not tune on qualification outcomes.",
        success_threshold="Set by root/user before release; this harness reports counts without inventing a promotion threshold.")
    write(destination, protocol)
    return protocol


def training_ids(path, protocol):
    if path is None:
        return list(protocol["training_episode_exclusions"])
    value = read(path)
    if isinstance(value, dict):
        value = value.get("training_episodes", value.get("episodes", value.get("worlds", value)))
        if isinstance(value, dict):
            value = list(value)
    if not isinstance(value, list) or not all(str(x).isdigit() for x in value):
        raise ValueError("Training episode file must identify episode IDs explicitly")
    return sorted(set(map(str, value)))


def freeze_candidate(study, identifier, entry, files, training_episode_file=None):
    protocol = read(study / "protocol.json")
    if not identifier or entry is None:
        raise ValueError("freeze requires --id and --entry")
    destination = study / "candidates" / identifier
    if destination.exists():
        raise ValueError("Candidate ID already exists; use a new immutable version")
    if not identifier.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Candidate ID must contain only letters, digits, underscores and hyphens")
    episodes = training_ids(training_episode_file, protocol)
    heldout = {x["episode"] for x in protocol["qualification"]["recorded"]}
    if heldout.intersection(episodes):
        raise ValueError("Candidate training overlaps reserved qualification episodes")
    project = destination / "project"
    paths = {Path(entry).resolve()}
    for item in files:
        path = Path(item).resolve()
        if path.is_dir():
            paths.update(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        else:
            paths.add(path)
    hashes = {}
    for path in sorted(paths):
        relative = path.relative_to(ROOT)
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        hashes[relative.as_posix()] = sha(target)
    harness = destination / "harness"
    harness.mkdir()
    harness_hashes = {}
    for name in (Path(__file__).name, *HELPERS):
        source = ROOT / "scripts" / name
        shutil.copy2(source, harness / name)
        harness_hashes[name] = sha(harness / name)
    manifest = dict(candidate_id=identifier, created_utc=utc(), protocol_sha256=sha(study / "protocol.json"),
        repository_at_freeze=str(ROOT),
        entry=Path(entry).resolve().relative_to(ROOT).as_posix(), files=hashes,
        harness_files=harness_hashes, training_episodes=episodes,
        interface="Standard official callable(obs, configuration=None), active from step 0; optional STRATEGY_DIAGNOSTICS dictionary or strategy_diagnostics() for logging only.")
    write(destination / "manifest.json", manifest)
    return manifest


def release(study, identifier):
    manifest_path = study / "candidates" / identifier / "manifest.json"
    manifest = read(manifest_path)
    if manifest["protocol_sha256"] != sha(study / "protocol.json"):
        raise ValueError("Protocol changed after candidate freeze")
    release_path = study / "qualification_release.json"
    value = dict(candidate_id=identifier, candidate_manifest_sha256=sha(manifest_path),
                 protocol_sha256=sha(study / "protocol.json"), released_utc=utc())
    if release_path.exists():
        old = read(release_path)
        if old["candidate_manifest_sha256"] != value["candidate_manifest_sha256"]:
            raise ValueError("Qualification already released to a different frozen candidate")
        return old
    write(release_path, value)
    return value


def load_entry(path, project):
    from kaggle_environments.agent import get_last_callable
    scripts = str(project / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    before = time.perf_counter()
    fn = get_last_callable(path.read_text(encoding="utf-8"), path=str(path))
    elapsed = time.perf_counter() - before
    accepts_config = len(inspect.signature(fn).parameters) >= 2
    return fn, accepts_config, elapsed


def diagnostics(fn):
    scope = getattr(fn, "__globals__", {})
    producer = scope.get("strategy_diagnostics")
    value = producer() if callable(producer) else scope.get("STRATEGY_DIAGNOSTICS", scope.get("_STRATEGY_DIAGNOSTICS"))
    if value is None and "_V9_REPORT" in scope:
        report = scope["_V9_REPORT"]
        value = dict(policy="packaged_v9lite", **{key:report.get(key) for key in ("errors", "switches", "seconds", "budgets", "warm")})
    return json.loads(json.dumps(value, default=str)) if value is not None else None


def physical_failures(row):
    return sum(row.get("physical", {}).get(k, 0) for k in ("no_effect", "missing_worker_commands", "malformed_commands"))


def source_module_audit(manifest, project, study, harness, extension=None):
    """Catch accidental imports from the editable repository or unfrozen files."""
    repository = Path(manifest["repository_at_freeze"]).resolve()
    project = project.resolve()
    allowed = {str((project / name).resolve()).lower() for name in manifest["files"]}
    allowed.update(str((harness / name).resolve()).lower() for name in manifest["harness_files"])
    if extension:
        verify_files(Path(extension["root"]), extension["files"])
        allowed.update(str((Path(extension["root"])/name).resolve()).lower() for name in extension["files"])
    protocol = read(study / "protocol.json")
    allowed.update(str((study / "opponent/pkg" / name).resolve()).lower()
                   for name in protocol["opponent"]["files"])
    imported, unexpected = {}, []
    for name, module in list(sys.modules.items()):
        source = getattr(module, "__file__", None)
        if not source:
            continue
        path = Path(source).resolve()
        if not path.is_relative_to(repository) or path.is_relative_to(repository / ".venv"):
            continue
        imported[name] = str(path)
        if str(path).lower() not in allowed:
            unexpected.append(str(path))
    if unexpected:
        raise ValueError("Unfrozen repository modules imported: " + ", ".join(sorted(set(unexpected))))
    return imported


def play_job(job):
    study = Path(job["study"])
    case, kind = job["case"], job["kind"]
    row = dict(case=case, kind=kind, completed=False, eligible=False, errors=[], created_utc=utc())
    output = Path(job["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    env = None
    entries = {}
    actions, timings, day_logs = [[], []], [[], []], [[], []]
    started = time.perf_counter()
    with output.with_suffix(".log").open("w", encoding="utf-8") as log, redirect_stdout(log), redirect_stderr(log):
        try:
            import kaggle_environments
            from kaggle_environments import make
            from kaggle_environments.envs.kaggriculture import kaggriculture as E
            import tape_vs_bench as TV
            assert kaggle_environments.__version__ == "1.32.7"
            protocol = read(study / "protocol.json")
            row["protocol_sha256"] = sha(study / "protocol.json")
            seat = int(case["seat"])
            game = None
            if "file" in case:
                path = study / case["file"]
                assert sha(path) == case["sha256"], "Recording changed"
                game = json.loads(gzip.decompress(path.read_bytes()))
            env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 1}, info={"seed": case["seed"]})
            entries, loading = {}, {}
            if kind != "source_control":
                candidate_dir = study / "candidates" / job["candidate"]
                manifest = read(candidate_dir / "manifest.json")
                row["candidate_manifest_sha256"] = sha(candidate_dir / "manifest.json")
                assert manifest["protocol_sha256"] == sha(study / "protocol.json")
                verify_files(candidate_dir / "project", manifest["files"])
                verify_files(candidate_dir / "harness", manifest["harness_files"])
                project = candidate_dir / "project"
                os.chdir(project)
                fn, config, loading["candidate"] = load_entry(project / manifest["entry"], project)
                entries[seat] = (fn, config)
            if game is None:
                verify_files(study / "opponent/pkg", protocol["opponent"]["files"])
                fn, config, loading["opponent"] = load_entry(study / protocol["opponent"]["entry"], study / "opponent/pkg")
                entries[1 - seat] = (fn, config)

            def player(index):
                def act(obs, step):
                    tick = time.perf_counter()
                    try:
                        if index in entries:
                            fn, config = entries[index]
                            action = fn(obs, env.configuration) if config else fn(obs)
                            if step % 24 == 0:
                                day_logs[index].append(dict(day=step // 24, visible_observation_sha256=digest(obs),
                                    diagnostics=diagnostics(fn)))
                        else:
                            tape = game["our_actions"] if index == seat else game["opp_actions"]
                            action = deepcopy(tape[step]) if step < len(tape) and tape[step] else deepcopy(PASS)
                        if step % 24 == 0 and index not in entries:
                            day_logs[index].append(dict(day=step // 24, visible_observation_sha256=digest(obs)))
                        if step % 24 == 0:
                            farm = obs["farms"][index]
                            day_logs[index][-1]["farm"] = dict(money=farm["money"], hands=len(farm["hands"]),
                                hires_today=farm["hires_today"], unlocked_quadrants=farm["unlocked_quadrants"])
                            day_logs[index][-1]["current_observation"] = dict(step=step, player=index,
                                own_farm=deepcopy(farm), market=deepcopy(obs["market"]), town=deepcopy(obs["town"]),
                                private=deepcopy(obs.get("private")),
                                remainingOverageTime=obs.get("remainingOverageTime"))
                        actions[index].append(deepcopy(action))
                        return action
                    except Exception:
                        row["errors"].append(dict(seat=index, step=step, traceback=traceback.format_exc()))
                        raise
                    finally:
                        timings[index].append(time.perf_counter() - tick)
                return act

            forced_shops = game["shops"] if game else job.get("force_shops")
            result = TV._play(E, env, [player(0), player(1)], seat,
                              forced_shops, None, None, 1 - seat)
            final = result["final"]
            assert all(math.isfinite(x) for x in final)
            assert all(len(x) == 719 for x in actions)
            assert not row["errors"]
            if kind != "source_control":
                row["source_module_audit"] = source_module_audit(manifest, project, study, candidate_dir / "harness",
                                                               job.get("harness_extension"))
            row.update(completed=True, eligible=True, cash=final[seat], opponent_cash=final[1-seat],
                       margin=final[seat]-final[1-seat], cash_by_seat=final, daily=result["daily"],
                       ledger_verified=True, loading_seconds=loading, shops=list(env.state[0].observation.town.unlocked_shops),
                       action_sha256=[digest(x) for x in actions], diagnostics=day_logs,
                       phase_cash={str(d):[result["daily"][s][d]["money"] for s in range(2)] for d in (0,6,11,12,18,24,30)})
            if kind == "source_control":
                row["recorded_cash_match"] = final == game["rewards"]
                row["eligible"] = row["recorded_cash_match"]
            elif game:
                control = read(Path(job["control"]))
                assert control["completed"] and control["recorded_cash_match"]
                rival = 1 - seat
                excess = physical_failures(result["daily"][rival][-1]) - physical_failures(control["daily"][rival][-1])
                broken = excess > protocol["recorded_validity"]["extra_failed_commands_limit"]
                row["recorded_rival_audit"] = dict(additional_failed_commands=excess,
                    material_command_break=broken, control_sha256=sha(Path(job["control"])),
                    additional_missing_worker_commands=result["daily"][rival][-1]["physical"].get("missing_worker_commands", 0)
                        - control["daily"][rival][-1]["physical"].get("missing_worker_commands", 0),
                    failures_by_day=[physical_failures(result["daily"][rival][d+1])-physical_failures(result["daily"][rival][d])
                        for d in range(30)],
                    note="Frozen commands cannot react to counterfactual prices. Passing this necessary screen is not proof of live policy equivalence.")
                row["eligible"] = not broken
            if job.get("fixed_world"):
                row["fixed_world"] = job["fixed_world"]
                row["forced_shops_sha256"] = digest(forced_shops)
        except Exception:
            row["error"] = traceback.format_exc()
            row["eligible"] = False
        finally:
            row["final_diagnostics"] = {}
            for index, (fn, _) in entries.items():
                try:
                    row["final_diagnostics"][str(index)] = diagnostics(fn)
                except Exception:
                    row["final_diagnostics"][str(index)] = {"diagnostic_error": traceback.format_exc()}
            v9_health = {index: value for index,value in row["final_diagnostics"].items()
                         if isinstance(value,dict) and value.get("policy")=="packaged_v9lite"}
            row["live_opponent_internal_health"] = v9_health or None
            if any(value.get("errors",0) for value in v9_health.values()):
                row["eligible"] = False
                row["opponent_health_failure"] = "Packaged V9lite reported internal search errors/fallbacks"
            row["wall_seconds"] = time.perf_counter() - started
            row["timings"] = timings
            row["measured_overage_used"] = [sum(max(0.0, value-1.0) for value in values) for values in timings]
            row["measured_runtime_valid"] = all(value <= 60.0 for value in row["measured_overage_used"])
            if not row["measured_runtime_valid"]:
                row["eligible"] = False
            if env is not None:
                row["engine_audit"] = dict(statuses=[s.status for s in env.state], steps=len(env.steps),
                    final_step=env.state[0].observation.get("step"), act_timeout=env.configuration.actTimeout,
                    remaining_overage=[s.observation.get("remainingOverageTime") for s in env.state])
            write(output.with_suffix(".actions.json"), actions)
            write(output, row)
    return {k:row.get(k) for k in ("case", "completed", "eligible", "cash", "opponent_cash", "margin", "error")}


def pool_run(jobs, workers):
    if not jobs:
        return []
    results = []
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=1) as pool:
        for future in as_completed([pool.submit(play_job, job) for job in jobs]):
            row = future.result()
            results.append(row)
            print(json.dumps(row, default=str), flush=True)
    return results


def controls_and_selection(study, protocol, split, workers, training_episodes=()):
    training_episodes = set(training_episodes)
    selection_file = study / "selections" / f"{split}.json"
    if selection_file.exists():
        chosen = read(selection_file)
        if chosen["protocol_sha256"] != sha(study / "protocol.json"):
            raise ValueError("Protocol changed after source-control selection")
        for case in chosen["cases"]:
            if case["episode"] in training_episodes:
                raise ValueError("Frozen source-control selection overlaps candidate training")
            control = study / "controls" / f'{case["id"]}.json'
            if sha(control) != chosen["control_sha256"][case["id"]]:
                raise ValueError("Frozen selected source control changed")
            if not read(control).get("eligible"):
                raise ValueError("Frozen selected source control is no longer eligible")
        return chosen["cases"]
    cases = list(protocol[split]["recorded"])
    if any(x["episode"] in training_episodes for x in cases):
        raise ValueError("Reserved recorded cases overlap candidate training")
    log = []
    reserve = iter(protocol["recorded_reserve"])
    used_other = set()
    for file in (study / "selections").glob("*.json") if (study / "selections").exists() else []:
        used_other.update(x["episode"] for x in read(file)["cases"])
    for slot in range(len(cases)):
        while True:
            case = cases[slot]
            control = study / "controls" / f'{case["id"]}.json'
            if not control.exists():
                pool_run([dict(study=str(study), case=case, kind="source_control", output=str(control))], 1)
            result = read(control)
            if result.get("case") != case or result.get("protocol_sha256") != sha(study / "protocol.json"):
                raise ValueError("Cached source control has different input/protocol")
            log.append(dict(slot=slot, episode=case["episode"], accepted=bool(result.get("eligible")),
                            source_control_sha256=sha(control)))
            if result.get("eligible"):
                break
            replacement = next((x for x in reserve if x["episode"] not in used_other
                                and x["episode"] not in training_episodes and x not in cases), None)
            if replacement is None:
                write(selection_file.with_suffix(".failed.json"), dict(attempts=log))
                raise ValueError("No valid unused source-control reserve remains")
            cases[slot] = replacement
    write(selection_file, dict(protocol_sha256=sha(study/"protocol.json"), cases=cases, attempts=log,
        control_sha256={case["id"]:sha(study/"controls"/f'{case["id"]}.json') for case in cases},
        selection_blind_to_candidate=True, created_utc=utc()))
    return cases


def run(study, candidate, split, mode, workers, external_workers):
    protocol = read(study / "protocol.json")
    candidate_dir = study / "candidates" / candidate
    manifest_path = candidate_dir / "manifest.json"
    manifest = read(manifest_path)
    assert manifest["protocol_sha256"] == sha(study / "protocol.json")
    verify_files(candidate_dir / "project", manifest["files"])
    verify_files(candidate_dir / "harness", manifest["harness_files"])
    if split == "qualification":
        released = read(study / "qualification_release.json")
        if released["candidate_manifest_sha256"] != sha(manifest_path):
            raise ValueError("This candidate has not been released to qualification")
    import psutil
    free = psutil.virtual_memory().available / 2 ** 30
    # Packaged V9lite's live rollout cache reached 1.85 GiB in the first smoke.
    workers = min(workers, max(0, 4-external_workers), int((free-1.5)/1.8))
    if workers < 1:
        raise ValueError(f"Insufficient free RAM or worker slots: {free:.2f} GiB")
    print(f"Local only: {workers} workers, {external_workers} reserved external workers, {free:.2f} GiB available", flush=True)
    cases = protocol[split]["live"] if mode == "live" else controls_and_selection(
        study, protocol, split, workers, manifest["training_episodes"])
    jobs = []
    output_dir = study / "runs" / candidate / split / mode
    for case in cases:
        output = output_dir / f'{case["id"]}.json'
        if output.exists():
            previous = read(output)
            if previous.get("candidate_manifest_sha256") != sha(manifest_path):
                raise ValueError("Existing result belongs to a different candidate snapshot")
            continue  # Keep failures too. Never silently rerun to select a better outcome.
        jobs.append(dict(study=str(study), candidate=candidate, case=case, kind=mode,
                         output=str(output), control=str(study/"controls"/f'{case["id"]}.json')))
    pool_run(jobs, workers)
    return report(study, candidate, split, mode)


def report(study, candidate, split, mode):
    protocol = read(study / "protocol.json")
    rows = [read(path) for path in (study/"runs"/candidate/split/mode).glob("*.json") if not path.name.endswith(".actions.json")]
    cases = protocol[split][mode if mode == "live" else "recorded"]
    if mode == "recorded" and (study/"selections"/f"{split}.json").exists():
        cases = read(study/"selections"/f"{split}.json")["cases"]
    expected = len(cases)
    expected_ids = {case["id"] for case in cases}
    observed_ids = [row["case"]["id"] for row in rows]
    valid = [row for row in rows if row.get("completed") and row.get("eligible")
             and row["case"]["id"] in expected_ids and observed_ids.count(row["case"]["id"]) == 1]
    result = dict(candidate=candidate, split=split, mode=mode, expected=expected, recorded=len(rows),
                  valid=len(valid), gate_complete=len(rows)==expected and len(valid)==expected and set(observed_ids)==expected_ids,
                  eligible_wins=sum(row["margin"]>0 for row in valid),
                  invalid_cases=[row["case"]["id"] for row in rows if row not in valid],
                  missing_cases=sorted(expected_ids-set(observed_ids)),
                  mean_valid_margin=sum(row["margin"] for row in valid)/len(valid) if valid else None,
                  warning="No success claim from an incomplete gate; invalid cases are not removed from its planned denominator.")
    write(study/"reports"/f"{candidate}-{split}-{mode}.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "freeze", "release", "run", "report"))
    parser.add_argument("--study", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--id")
    parser.add_argument("--entry", type=Path)
    parser.add_argument("--files", default="", help="Explicit repository file/directory dependencies, comma separated")
    parser.add_argument("--training-episodes", type=Path)
    parser.add_argument("--candidate")
    parser.add_argument("--split", choices=("development", "qualification"), default="development")
    parser.add_argument("--mode", choices=("live", "recorded"), default="live")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--external-workers", type=int, default=0)
    parser.add_argument("--frozen", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.command == "freeze" and (not args.id or args.entry is None):
        parser.error("freeze requires --id and --entry")
    if args.command in ("release", "run", "report") and not args.candidate:
        parser.error(args.command + " requires --candidate")
    if not 1 <= args.workers <= 4 or not 0 <= args.external_workers <= 3:
        parser.error("--workers must be 1..4 and --external-workers must be 0..3")
    study = args.study.resolve()
    if args.command == "prepare":
        value = prepare(study)
        print(json.dumps(dict(protocol=str(study/"protocol.json"), protocol_sha256=sha(study/"protocol.json"),
            development_live=len(value["development"]["live"]), qualification_live=len(value["qualification"]["live"]),
            development_recorded=len(value["development"]["recorded"]), qualification_recorded=len(value["qualification"]["recorded"]),
            reserve=len(value["recorded_reserve"]))))
    elif args.command == "freeze":
        print(json.dumps(freeze_candidate(study, args.id, args.entry, [x for x in args.files.split(",") if x], args.training_episodes), indent=2))
    elif args.command == "release":
        print(json.dumps(release(study, args.candidate), indent=2))
    elif args.command == "run" and not args.frozen:
        frozen = study/"candidates"/args.candidate/"harness"/Path(__file__).name
        cmd = [sys.executable, str(frozen), "run", "--study", str(study), "--candidate", args.candidate,
               "--split", args.split, "--mode", args.mode, "--workers", str(args.workers),
               "--external-workers", str(args.external_workers), "--frozen"]
        raise SystemExit(subprocess.call(cmd))
    elif args.command == "run":
        print(json.dumps(run(study, args.candidate, args.split, args.mode, args.workers, args.external_workers), indent=2))
    else:
        print(json.dumps(report(study, args.candidate, args.split, args.mode), indent=2))


if __name__ == "__main__":
    main()

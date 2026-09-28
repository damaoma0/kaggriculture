"""One authorized snapshot-only V8 live06 replay, normal clock, no profiling."""
import argparse
from copy import deepcopy
import gc
import gzip
import os
from pathlib import Path
import pickle
import sys
import time
import traceback

from profile_semantic_tier_pre_20260928 import read, sha, safe, dump, state_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    study, output = args.study.resolve(), args.out.resolve()
    assert not output.exists(), "Preserve all attempts; do not overwrite"
    assert os.environ.get("KAGG_NO_TIMEOUT") != "1" and gc.isenabled()
    import psutil
    available = psutil.virtual_memory().available / 2**30
    assert available >= 2.5, f"Insufficient memory: {available:.3f}GiB"
    candidate = study / "candidates/strategy_v8_kb115lt2_readiness"
    source = study / "runs/strategy_v8_kb115lt2_readiness/development/live/live-06.json"
    recorded, actions = read(source), read(source.with_suffix(".actions.json"))
    manifest = read(candidate / "manifest.json")
    assert recorded["candidate_manifest_sha256"] == sha(candidate / "manifest.json")
    for folder, key in (("project", "files"), ("harness", "harness_files")):
        for name, expected in manifest[key].items():
            assert sha(candidate / folder / name) == expected, name
    output.mkdir(parents=True)
    helper_path = Path(__file__).with_name("profile_semantic_tier_pre_20260928.py")
    project, harness = candidate / "project", candidate / "harness"
    sys.path[:0] = [str(harness), str(project / "scripts")]
    import semantic_strategy_gate_20260928 as gate
    import kaggle_environments
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as E
    import tape_vs_bench as TV
    assert kaggle_environments.__version__ == "1.32.7"
    os.chdir(project)
    fn, accepts_config, loading = gate.load_entry(project / manifest["entry"], project)
    seat = recorded["case"]["seat"]
    env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 1},
               info={"seed": recorded["case"]["seed"]})
    shops = [recorded["shops"][:min(8, day // 3)] for day in range(31)]
    evaluations, searches, cores, snapshots = [], [], [], []
    mismatches, dawn_checks, timings = [], [], []
    shadow_calls, current_step = 0, -1
    core_day, core18_count, eval_seen = None, 0, set()
    eval_modes = {False: 0, True: 0}
    copy_seconds = [0.0]

    def copy_graph(value):
        tick = time.perf_counter()
        value = deepcopy(value)
        copy_seconds[0] += time.perf_counter() - tick
        return value

    def attach():
        state = fn.__globals__.get("_STATE")
        if not state or getattr(state["kb"], "_eval_snapshot_hook", False):
            return
        kb = state["kb"]
        original_eval, original_search, original_core = kb._tier_eval, kb._tier_search, kb._tier_core
        def globals_():
            return {k: getattr(kb, k) for k in ("CFG", "_TIER_D", "_TIER_SHED_I", "_TIER_WY", "_TIER_ANG", "_TIER_BIG")}

        def evaluate(*a, **kw):
            capture = False
            if core_day == 18 and core18_count == 1:
                hours = bool(kw.get("want_hours", a[2] if len(a) > 2 else False))
                if eval_modes[hours] < (15 if hours else 85):
                    seg = a[0]
                    stops = kw.get("stops", a[1] if len(a) > 1 else None)
                    stops = seg["stops"] if stops is None else stops
                    signature = (hours, seg["p0"], seg["t0"], len(stops),
                        tuple(sorted({o["c"][0] for s in stops for o in s["ops"]})),
                        sum(len(s["ops"]) for s in stops), bool(seg.get("hold0")),
                        bool(seg.get("fpick")), sum(bool(s.get("dawn")) for s in stops))
                    if signature not in eval_seen:
                        eval_seen.add(signature)
                        eval_modes[hours] += 1
                        capture = True
                        entry = copy_graph(dict(args=a, kwargs=kw, globals=globals_(), signature=signature))
            result = original_eval(*a, **kw)
            if capture:
                entry.update(copy_graph(dict(expected_args=a, expected_kwargs=kw, expected_result=result)))
                evaluations.append(entry)
            return result

        def search(*a, **kw):
            if core_day != 18:
                return original_search(*a, **kw)
            entry = copy_graph(dict(args=a, kwargs=kw, globals=globals_(),
                rng_state_before=a[3].getstate(), core_pass=core18_count, step=current_step))
            tick = time.perf_counter()
            result = original_search(*a, **kw)
            entry["original_seconds"] = time.perf_counter() - tick
            entry.update(copy_graph(dict(expected_args=a, expected_kwargs=kw,
                expected_result=result, rng_state_after=a[3].getstate())))
            searches.append(entry)
            return result

        def core(*a, **kw):
            nonlocal core_day, core18_count
            day = int(a[3])
            core_day = day
            if day == 18:
                core18_count += 1
                if core18_count == 1:
                    kb._tier_eval = evaluate
            if day == 28:
                entry = dict(day=day, step=current_step, pass_index=len(cores),
                    xretire=safe(a[0].get("_xretire")), rec48=safe(a[5].get(48)), units=safe(a[6]))
            try:
                result = original_core(*a, **kw)
            finally:
                kb._tier_eval = original_eval
                core_day = None
            if day == 28:
                entry["result_routes"] = safe({u: r for u, r in result.get("routes", {}).items()
                    if int(u) == 11 or any(i.get("tile") == 48 for i in r.get("items", []))})
                entry["summary"] = safe(result.get("summary"))
                cores.append(entry)
            return result
        kb._tier_search, kb._tier_core = search, core
        kb._eval_snapshot_hook = True

    def actor(index):
        def act(obs, step):
            nonlocal current_step, shadow_calls
            expected_action = deepcopy(actions[index][step])
            if index == seat:
                current_step = step
                day, hour = divmod(step, 24)
                if hour == 0:
                    expected = recorded["diagnostics"][seat][day]["current_observation"]
                    dawn_checks.append(dict(day=day, own_farm=obs["farms"][seat] == expected["own_farm"],
                        private=obs["private"] == expected["private"], market=obs["market"] == expected["market"],
                        town=obs["town"] == expected["town"]))
                watch = day == 28 and (hour <= 10 or hour == 23)
                before = state_snapshot(fn, day, hour) if watch else None
                if day <= 28:
                    attach()
                    tick = time.perf_counter()
                    shadow = fn(deepcopy(obs), env.configuration) if accepts_config else fn(deepcopy(obs))
                    timings.append(dict(step=step, seconds=time.perf_counter()-tick))
                    shadow_calls += 1
                    if shadow != expected_action:
                        mismatches.append(dict(step=step, expected=expected_action, shadow=shadow))
                    if watch:
                        farm = obs["farms"][seat]
                        snapshots.append(dict(step=step, day=day, hour=hour, cash=farm["money"],
                            tile48=deepcopy(farm["tiles"][4][8]), private=deepcopy(obs["private"]),
                            positions=dict(farmer=deepcopy(farm["farmer"]), hands=deepcopy(farm["hands"])),
                            market=deepcopy(obs["market"]), before=before, after=state_snapshot(fn, day, hour),
                            action=expected_action, shadow_action=shadow, prefix_equal=not mismatches))
            return expected_action
        return act

    started, replay, error = time.perf_counter(), None, None
    try:
        replay = TV._play(E, env, [actor(0), actor(1)], seat, shops, None, None, seat)
    except BaseException:
        error = traceback.format_exc()
    # All in-callback graph copies are charged normally. Only writing the
    # already captured diagnostic artifacts occurs after the game has ended.
    fixtures_path = output / "eval_search_fixtures.pickle.gz"
    with gzip.open(fixtures_path, "wb") as stream:
        pickle.dump(dict(evaluations=evaluations, searches=searches), stream, protocol=5)
    with gzip.open(output / "d28_retirement_routes.json.gz", "wt", encoding="utf-8") as stream:
        import json
        json.dump(safe(dict(snapshots=snapshots, core_passes=cores)), stream)
    value = dict(scope="SNAPSHOT_ONLY_SAVED_ACTION_SHADOW_NOT_GATE", case=recorded["case"],
        source_result_sha256=sha(source), source_actions_sha256=sha(source.with_suffix(".actions.json")),
        candidate_manifest_sha256=sha(candidate / "manifest.json"), script_sha256=sha(Path(__file__)),
        helper_sha256=sha(helper_path), memory_available_before_GiB=available, loading_seconds=loading,
        elapsed_seconds=time.perf_counter()-started, error=error,
        replay_cash_equal=replay is not None and replay["final"] == recorded["cash_by_seat"],
        replay_complete_ledgers_equal=replay is not None and replay["daily"] == recorded["daily"],
        engine_configuration=dict(env.configuration), engine_statuses=[s.status for s in env.state],
        engine_steps=len(env.steps), remaining_overage=[s.observation.remainingOverageTime for s in env.state],
        shadow_calls=shadow_calls, shadow_mismatches=mismatches, dawn_checks=dawn_checks, call_timings=timings,
        evaluation_fixtures=len(evaluations), evaluation_hours_modes=eval_modes,
        search_fixtures=len(searches), first_D18_core_only_for_evaluations=True,
        fixtures_sha256=sha(fixtures_path), total_in_callback_copy_seconds=copy_seconds[0],
        d28_snapshot_hours=[s["hour"] for s in snapshots], live_opponent_calls=0, shadow_actions_executed=False,
        note="No cProfile, GC instrumentation or clock exemption. Timed search may diverge; exact shadow prefix is checked. Original and expected args are deep-copied as whole graphs, preserving each graph's aliases.")
    value["verified"] = (value["replay_cash_equal"] and value["replay_complete_ledgers_equal"]
        and error is None and not mismatches and shadow_calls == 29*24 and len(dawn_checks) == 30
        and all(all(v for k, v in row.items() if k != "day") for row in dawn_checks)
        and evaluations and searches and {0, 9, 23}.issubset(set(value["d28_snapshot_hours"])))
    dump(output / "manifest.json", value)
    print(json.dumps({k: value[k] for k in ("verified", "shadow_calls", "replay_cash_equal",
        "replay_complete_ledgers_equal", "evaluation_fixtures", "search_fixtures", "elapsed_seconds")}), flush=True)
    assert value["verified"], "Preserve failed/incomplete attempt, no silent retry"


if __name__ == "__main__":
    main()

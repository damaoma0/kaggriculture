"""One saved-action V8 shadow; passive dawn CPU/GC profile, never a gate.

Recorded actions alone control the world. All instrumentation remains inside
the normal engine callback clock; neither timeouts nor GC are changed.
"""
import argparse
from copy import deepcopy
import cProfile
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import pstats
import sys
import time
import traceback


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe(value, depth=0):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth > 12:
        return repr(value)[:500]
    if isinstance(value, dict):
        return {str(k): safe(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(v, depth + 1) for v in value]
    return repr(value)[:500]


def dump(path, value):
    path.write_text(json.dumps(safe(value), indent=2) + "\n", encoding="utf-8")


def state_snapshot(fn, day, hour):
    state = fn.__globals__.get("_STATE")
    if not state or state["kb"]._S is None:
        return None
    kb, S = state["kb"], state["kb"]._S
    tier = S.get("tier") or {}
    routes = {}
    for unit, route in tier.get("routes", {}).items():
        items = route.get("items", [])
        routes[str(unit)] = dict(cursor=route.get("k"), sub=route.get("sub"),
            current_items=items[route.get("k", 0):route.get("k", 0) + 2],
            watched_items=[dict(item_index=i, item=item) for i, item in enumerate(items)
                           if item.get("tile") == 48], done=route.get("done"),
            plan_hours=route.get("plan_hours"), full_route=route if int(unit) == 11 else None)
    return safe(dict(day=day, hour=hour, xretire=S.get("_xretire"), xfeed=S.get("_xfeed"),
        committed_retirements=state["tile_memory"].get("retirements"),
        animal_lookahead=kb._T.animals_by_day[day:min(day + 4, 30)],
        tier_day=tier.get("day"), tier_counts=tier.get("cnt"), tier_log=tier.get("log"),
        tier_summary=tier.get("summary"), routes=routes,
        lower_stats=kb._sd_state(S)["st"], plan_harvest=kb._T.harv_tiles[day],
        daily_diagnostic=state.get("daily_diagnostic")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    study, output = args.study.resolve(), args.out.resolve()
    assert not output.exists(), "Do not overwrite or silently rerun this diagnostic"
    assert os.environ.get("KAGG_NO_TIMEOUT") != "1", "Normal engine clock required"
    import psutil
    available = psutil.virtual_memory().available / 2**30
    assert available >= 2.5, f"Insufficient free memory: {available:.3f}GiB"
    assert gc.isenabled(), "Observe existing enabled GC; do not change it"
    candidate = study / "candidates/strategy_v8_kb115lt2_readiness"
    source = study / "runs/strategy_v8_kb115lt2_readiness/development/live/live-06.json"
    recorded, actions = read(source), read(source.with_suffix(".actions.json"))
    manifest = read(candidate / "manifest.json")
    assert recorded["candidate_manifest_sha256"] == sha(candidate / "manifest.json")
    for folder, key in (("project", "files"), ("harness", "harness_files")):
        for name, expected in manifest[key].items():
            assert sha(candidate / folder / name) == expected, name
    output.mkdir(parents=True)
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
    targets = {18, 24, 28}
    profiles, mismatches, dawn_checks, snapshots, cores, timings = [], [], [], [], [], []
    shadow_calls, current_step = 0, -1
    process = psutil.Process()

    def attach():
        state = fn.__globals__.get("_STATE")
        if not state or getattr(state["kb"], "_tier_profile_hook", False):
            return
        kb = state["kb"]
        original, original_core = kb._tier_pre, kb._tier_core

        def core(*call_args, **kwargs):
            if int(call_args[3]) != 28:
                return original_core(*call_args, **kwargs)
            entry = dict(day=28, step=current_step, pass_index=len(cores),
                xretire=safe(call_args[0].get("_xretire")), rec48=safe(call_args[5].get(48)),
                units=safe(call_args[6]))
            result = original_core(*call_args, **kwargs)
            entry["result_routes"] = safe({u: r for u, r in result.get("routes", {}).items()
                if int(u) == 11 or any(i.get("tile") == 48 for i in r.get("items", []))})
            entry["summary"] = safe(result.get("summary"))
            cores.append(entry)
            return result

        def profile(*call_args, **kwargs):
            day, hour = int(call_args[4]), int(call_args[5])
            if day not in targets or hour != 0:
                return original(*call_args, **kwargs)
            stats_before = safe(call_args[1]["st"])
            gc_before, count_before = gc.get_stats(), gc.get_count()
            rss_before = process.memory_info().rss
            events, pending = [], {}
            def gc_observer(phase, info):
                gen = info["generation"]
                if phase == "start":
                    pending[gen] = time.perf_counter()
                elif phase == "stop":
                    tick = time.perf_counter()
                    start = pending.pop(gen, tick)
                    events.append(dict(generation=gen, seconds=tick-start,
                        collected=info["collected"], uncollectable=info["uncollectable"]))
            profiler = cProfile.Profile()
            gc.callbacks.append(gc_observer)
            wall, cpu = time.perf_counter(), time.process_time()
            error = None
            try:
                profiler.enable()
                return original(*call_args, **kwargs)
            except BaseException:
                error = traceback.format_exc()
                raise
            finally:
                profiler.disable()
                cpu, wall = time.process_time()-cpu, time.perf_counter()-wall
                gc.callbacks.remove(gc_observer)
                # Snapshots and serialization are excluded from the profiled
                # original call, but still charged by the outer engine clock.
                gc_after, count_after = gc.get_stats(), gc.get_count()
                rss_after = process.memory_info().rss
                stats_after = safe(call_args[1]["st"])
                rows = [dict(file=key[0], line=key[1], function=key[2],
                    primitive_calls=value[0], total_calls=value[1],
                    self_seconds=value[2], cumulative_seconds=value[3])
                    for key, value in pstats.Stats(profiler).stats.items()]
                rows.sort(key=lambda row: row["cumulative_seconds"], reverse=True)
                path = output / f"d{day:02}.pstats"
                profiler.dump_stats(str(path))
                value = dict(day=day, step=current_step, original_pre_wall_seconds=wall,
                    original_pre_cpu_seconds=cpu, error=error, rss_before=rss_before, rss_after=rss_after,
                    gc_enabled=gc.isenabled(), gc_threshold=gc.get_threshold(),
                    gc_stats_before=gc_before, gc_stats_after=gc_after,
                    gc_count_before=count_before, gc_count_after=count_after, gc_events=events,
                    gc_seconds=sum(e["seconds"] for e in events), stats_before=stats_before,
                    stats_after=stats_after, numeric_counter_deltas={k: v-stats_before.get(k, 0)
                        for k, v in stats_after.items() if isinstance(v, (int, float))
                        and isinstance(stats_before.get(k, 0), (int, float))
                        and v != stats_before.get(k, 0)},
                    functions=rows, pstats_file=path.name, pstats_sha256=sha(path),
                    shadow_prefix_equal_before_call=not mismatches)
                profiles.append(value)
                dump(output / f"d{day:02}.json", value)
                print(json.dumps(dict(day=day, wall=wall, cpu=cpu, gc_seconds=value["gc_seconds"],
                    core_calls=sum(r["total_calls"] for r in rows if r["function"] == "_tier_core"))), flush=True)

        kb._tier_pre, kb._tier_core = profile, core
        kb._tier_profile_hook = True

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
    payload = dict(scope="SAVED_ACTION_REPLAY_NONCONTROLLING_PROFILE_NOT_GATE", case=recorded["case"],
        source_result_sha256=sha(source), source_actions_sha256=sha(source.with_suffix(".actions.json")),
        candidate_manifest_sha256=sha(candidate / "manifest.json"), script_sha256=sha(Path(__file__)),
        memory_available_before_GiB=available, loading_seconds=loading, elapsed_seconds=time.perf_counter()-started,
        replay_cash_equal=replay is not None and replay["final"] == recorded["cash_by_seat"],
        replay_complete_ledgers_equal=replay is not None and replay["daily"] == recorded["daily"],
        error=error, engine_configuration=dict(env.configuration), engine_statuses=[s.status for s in env.state],
        engine_steps=len(env.steps), dawn_checks=dawn_checks, shadow_calls=shadow_calls,
        shadow_mismatches=mismatches, profiles=[{k: v for k, v in p.items() if k not in
            ("functions", "stats_before", "stats_after")} for p in profiles],
        live_opponent_calls=0, shadow_actions_executed=False, call_timings=timings,
        limitation="Saved opponent actions do not recreate live V9's large search heap. cProfile changes diagnostic wall time; normal outer timeout and GC remain enabled. No runtime or strength claim.")
    payload["verified"] = (payload["replay_cash_equal"] and payload["replay_complete_ledgers_equal"]
        and error is None and not mismatches and shadow_calls == 29*24 and len(dawn_checks) == 30
        and all(all(v for k, v in row.items() if k != "day") for row in dawn_checks)
        and {p["day"] for p in profiles} == targets)
    with gzip.open(output / "d28_retirement_routes.json.gz", "wt", encoding="utf-8") as stream:
        json.dump(safe(dict(snapshots=snapshots, core_passes=cores)), stream)
    dump(output / "manifest.json", payload)
    print(json.dumps({key: payload[key] for key in ("verified", "shadow_calls", "replay_cash_equal",
        "replay_complete_ledgers_equal", "elapsed_seconds", "error")}), flush=True)
    assert payload["verified"], "Preserve incomplete/diverged diagnostic; no silent retry"


if __name__ == "__main__":
    main()

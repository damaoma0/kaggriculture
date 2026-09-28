"""One authorized saved-action replay with noncontrolling frozen V8 shadow.

Fixtures preserve each entire input/output argument graph using pickle. They
are local trusted research artifacts, never policy inputs or gate outcomes.
"""
import argparse
from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import sys
import time


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    study, output = args.study.resolve(), args.out.resolve()
    assert not output.exists(), "No diagnostic reruns or overwritten artifacts"
    import psutil
    available = psutil.virtual_memory().available / 2**30
    assert available >= 2.5, f"Insufficient free RAM: {available:.3f}GiB"
    candidate = study / "candidates/strategy_v8_kb115lt2_readiness"
    source = study / "runs/strategy_v8_kb115lt2_readiness/development/live/live-01.json"
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
    targets = {7, 12, 18, 26}
    fixtures, mismatches, dawn_checks = [], [], []
    shadow_calls, current_step = 0, -1

    def attach():
        state = fn.__globals__.get("_STATE")
        if not state:
            return
        kb = state["kb"]
        if getattr(kb, "_fixture_hook", False):
            return
        # Full S can contain executor classes; preserve their original module
        # identity for trusted pickle loading by the subsequent equality test.
        sys.modules[kb.__name__] = kb
        original = kb._tier_polish

        def capture(*call_args):
            day = int(call_args[4])
            if day not in targets:
                return original(*call_args)
            started = time.perf_counter()
            globals_ = {name: getattr(kb, name) for name in ("CFG", "_TIER_D", "_TIER_SHED_I", "_TIER_WY")}
            before = pickle.dumps(dict(args=call_args, globals=globals_), protocol=5)
            copied_before = time.perf_counter() - started
            tick = time.perf_counter()
            result = original(*call_args)
            original_seconds = time.perf_counter() - tick
            tick = time.perf_counter()
            after = pickle.dumps(call_args, protocol=5)
            copied_after = time.perf_counter() - tick
            identifier = f"d{day:02}-call{sum(x['day'] == day for x in fixtures):02}"
            path = output / (identifier + ".pickle.gz")
            payload = dict(input_pickle=before, reference_output_pickle=after, return_value=result,
                           day=day, step=current_step, executor_module_name=kb.__name__,
                           source_executor_sha256=manifest["files"]["results/fresh/semantic_strategy_20260928/runtime/agents/mgt_lead_kb115lt.py"])
            with gzip.open(path, "wb") as stream:
                pickle.dump(payload, stream, protocol=5)
            fixtures.append(dict(file=path.name, sha256=sha(path), day=day, step=current_step,
                shadow_prefix_equal_before_call=not mismatches, original_polish_seconds=original_seconds,
                input_pickle_seconds=copied_before, output_pickle_seconds=copied_after,
                input_pickle_bytes=len(before), output_pickle_bytes=len(after)))
            return result

        kb._tier_polish = capture
        kb._fixture_hook = True

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
                if day <= 26:
                    attach()
                    shadow = fn(deepcopy(obs), env.configuration) if accepts_config else fn(deepcopy(obs))
                    shadow_calls += 1
                    if shadow != expected_action:
                        mismatches.append(dict(step=step, expected=expected_action, shadow=shadow))
            return expected_action
        return act

    started = time.perf_counter()
    replay = TV._play(E, env, [actor(0), actor(1)], seat, shops, None, None, seat)
    value = dict(scope="SAVED_ACTION_REPLAY_AND_NONCONTROLLING_SHADOW_NOT_GATE", case=recorded["case"],
        source_result_sha256=sha(source), source_actions_sha256=sha(source.with_suffix(".actions.json")),
        candidate_manifest_sha256=sha(candidate / "manifest.json"), script_sha256=sha(Path(__file__)),
        memory_available_before_GiB=available, loading_seconds=loading, elapsed_seconds=time.perf_counter()-started,
        replay_cash_equal=replay["final"] == recorded["cash_by_seat"],
        replay_complete_ledgers_equal=replay["daily"] == recorded["daily"], dawn_checks=dawn_checks,
        shadow_calls=shadow_calls, shadow_mismatches=mismatches, fixtures=fixtures,
        live_opponent_calls=0, shadow_actions_executed=False,
        pickle_loading="Load frozen executor as _strategy_kb115lt first; outer gzip pickle contains input_pickle bytes with {args,globals}; reference_output_pickle bytes contain tuple(S,segs,rest,tiles,day,st).",
        instrumentation_note="Original-polish timing excludes both argument snapshots and file writing. Shadow instrumentation is not a gate runtime measurement.")
    value["verified"] = (value["replay_cash_equal"] and value["replay_complete_ledgers_equal"] and not mismatches
        and all(all(v for k, v in row.items() if k != "day") for row in dawn_checks)
        and {f["day"] for f in fixtures} == targets)
    (output / "manifest.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value[key] for key in ("verified", "shadow_calls", "replay_cash_equal", "replay_complete_ledgers_equal", "elapsed_seconds")}, indent=2))
    print(json.dumps(fixtures, indent=2))
    assert value["verified"], "Preserve diagnostic artifacts; do not use as verified fixtures or silently rerun"


if __name__ == "__main__":
    main()

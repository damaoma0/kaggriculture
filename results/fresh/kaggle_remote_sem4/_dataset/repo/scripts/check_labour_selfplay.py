"""Causality, projection and actual-engine checks for supplied-plan self-play."""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import argparse
import gzip
import io
import json
import test_labour_selfplay as S

R = S.R


def causal_check():
    path = R.OUT / "fixed_ladder/plans/110676097.json.gz"
    game, actions = R.load_game(path)
    own = actions[game["seat"]]
    sim = R.Simulator(game)
    pair = [own, own]
    with sim:
        pre = sim.run(sim.initial, 0, 312, pair)
    obs = pre["state"][0].observation
    projection, initial = S.project_input(obs)
    assert initial[0].observation.farms == obs.farms
    assert initial[0].observation.private == obs.private
    assert initial[0].observation.market == obs.market
    assert initial[0].observation.step == 312
    assert projection.game["seed"] == 0
    assert all(shops == obs.town.unlocked_shops for shops in projection.game["shops"])
    assert all(not inv for inv in initial[1].observation.private["inventories"])
    old_loader = R.load_game
    def forbidden(*args, **kwargs):
        raise AssertionError("A scheduling decision must not read an episode tape.")
    R.load_game = forbidden
    try:
        a, first = S.choose(obs, own[312:360], "forecast")
        changed = deepcopy(pre["state"])
        changed[1].observation.private["shed"]["WOOL"] = 9999
        changed[1].observation.private["seeds"]["MELON"] = 9999
        noisy = deepcopy(changed[0].observation)
        noisy.hidden_seed = 1234567
        noisy.future_shops = [["Yarn Store"]] * 31
        noisy.future_opponent_actions = [{"market": [["SELL", "WOOL", 9999]]}] * 720
        b, second = S.choose(noisy, own[312:360], "forecast")
        assert a == b
        assert first["name"] == second["name"]
        assert first["name"] != "baseline"
    finally:
        R.load_game = old_loader
    return dict(check="visible_initial_state_and_future_information_isolation", passed=True,
                decision=first["name"], decision_output_sha256=S.digest(a))


def framework_check(folder, record, game_row):
    game, _ = R.load_game(R.ROOT / record["source"])
    actions = json.load(gzip.open(R.ROOT / game_row["executed_actions_artifact"], "rt"))
    assert S.digest(actions) == game_row["executed_actions_sha256"]
    with R.Simulator(game) as sim:
        fast = sim.run(sim.initial, 0, 719, actions, snapshots=True)
    assert fast["money"] == game_row["cash"]
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from kaggle_environments import make
        env = make("kaggriculture", configuration={"episodeSteps": 720}, info={"seed": game["seed"]})
        env.reset()
    E = R.engine()
    old_end = E._end_of_day
    def forced_shops(state, environment, day):
        old_end(state, environment, day)
        state[0].observation.town.unlocked_shops[:] = game["shops"][min(30, day + 1)]
    E._end_of_day = forced_shops
    try:
        for t in range(719):
            env.step([actions[0][t], actions[1][t]])
            ref = fast["snapshots"][t + 1] if t + 1 < 719 else fast["state"]
            assert env.state[0].observation.step == ref[0].observation.step == t + 1
            for name in ("farms", "market", "town", "day", "hour"):
                assert env.state[0].observation[name] == ref[0].observation[name], (t, name)
            assert all(env.state[s].observation.private == ref[s].observation.private for s in range(2))
    finally:
        E._end_of_day = old_end
    assert len(env.steps) == 720
    assert all(s.status == "DONE" for s in env.state)
    assert [s.reward for s in env.state] == game_row["cash"]
    return dict(check="independent_official_framework_replay", episode=record["episode"],
                mode=game_row["mode"], seat=game_row["seat"], transitions=719, passed=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="selfplay_causal_v1")
    args = parser.parse_args()
    checks = [causal_check()]
    folder = R.OUT / args.tag
    rows = [json.loads(p.read_text()) for p in sorted(folder.glob("[0-9]*.json"))]
    if rows:
        selected = {}
        for row in rows:
            selected.setdefault(row["panel"], row)
        for row in selected.values():
            for g in row["games"]:
                checks.append(framework_check(folder, row, g))
        manifest = json.loads((folder / "manifest.json").read_text())
        assert len(rows) == len(manifest["paths"]), "Wait for all worlds before final verification."
        from hashlib import sha256
        for name, expected in manifest["sources"].items():
            assert sha256((R.ROOT / name).read_bytes()).hexdigest() == expected
        for row in rows:
            assert sha256((R.ROOT / row["source"]).read_bytes()).hexdigest() == row["source_sha256"]
            for g in row["games"]:
                actions = json.load(gzip.open(R.ROOT / g["executed_actions_artifact"], "rt"))
                assert S.digest(actions) == g["executed_actions_sha256"]
        checks.append(dict(check="all_source_and_executed_schedule_hashes", passed=True, worlds=len(rows)))
    result = dict(passed=True, checks=checks)
    if folder.exists():
        (folder / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

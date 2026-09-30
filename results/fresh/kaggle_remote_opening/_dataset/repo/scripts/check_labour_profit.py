"""Independent framework parity and feasibility checks for labour research."""
from copy import deepcopy
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import research_labour_profit as R


def main():
    checks = []
    paths = sorted((R.ROOT / "data/ladder_panel").glob("*/*.json.gz"))
    # Select one tape per player seat for framework parity.
    selected = {}
    for p in paths:
        g, a = R.load_game(p)
        selected.setdefault(g["seat"], (p, g, a))
        if len(selected) == 2:
            break
    for seat, (path, game, actions) in selected.items():
        with R.Simulator(game) as sim:
            fast = sim.run(sim.initial, 0, 719, actions, snapshots=True)
            assert fast["money"] == game["rewards"]
            assert all(state[0].observation.step == t for t, state in fast["snapshots"].items())
            prefix = sim.run(sim.initial, 0, 264, actions)
            sample_events = [e for e in fast["events"] if 264 <= e[0] < 312]
            assert R.forecast_value(prefix["state"], sample_events, seat) == R.forecast_value(fast["snapshots"][264], sample_events, seat)
        E = R.engine()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle_environments import make
            env = make("kaggriculture", configuration={"episodeSteps": 720}, info={"seed": game["seed"]})
            env.reset()
        end = E._end_of_day
        def locked(state, environment, day):
            end(state, environment, day)
            state[0].observation.town.unlocked_shops[:] = game["shops"][min(30, day + 1)]
        E._end_of_day = locked
        compared = 0
        try:
            for t in range(719):
                env.step([actions[0][t], actions[1][t]])
                ref = fast["snapshots"][t + 1] if t + 1 < 719 else fast["state"]
                assert env.state[0].observation.step == ref[0].observation.step, (t, "timestamp")
                assert env.state[0].observation.farms == ref[0].observation.farms, t
                assert env.state[0].observation.market == ref[0].observation.market, t
                for s in (0, 1):
                    assert env.state[s].observation.private == ref[s].observation.private, (t, s)
                compared += 1
        finally:
            E._end_of_day = end
        assert all(s.status == "DONE" for s in env.state)
        checks.append(dict(check="official_framework_parity", episode=game["episode"], seat=seat,
                           transitions=compared, final=[s.reward for s in env.state]))
        tampered = deepcopy(fast)
        tampered["state"][seat].observation.private["shed"]["MELON"] = 99
        assert R.equivalent(fast, tampered, seat) == "private"
        tampered = deepcopy(fast)
        tampered["state"][0].observation.farms[seat]["tiles"][0][0] = {"kind": "WEED", "test": 1}
        assert R.equivalent(fast, tampered, seat) == "farm"
        checks.append(dict(check="reject_changed_production_or_inventory", episode=game["episode"]))
        initial = fast["snapshots"][264]
        events = [e for e in fast["events"] if 264 <= e[0] < 312]
        score = R.forecast_value(initial, events, seat)
        changed = [e if e[1] == seat else (e[0], e[1], "SELL", "MELON", 999999) for e in events]
        assert score == R.forecast_value(initial, changed, seat)
        checks.append(dict(check="forecast_ignores_future_opponent_trades", episode=game["episode"]))
    jobs = [R.Job(0, (3, 4), [["HARVEST"]], [{"WHEAT": 4}], 2, False, 0),
            R.Job(1, (2, 4), [["FEED"]], [{"WHEAT": -1}], 2, False, 0)]
    finish, cmds = R.compile_route((2, (4, 4), {}), [0, 1], jobs)
    assert not any(c[0] == "PICKUP" for c in cmds)
    reverse_finish, reverse_cmds = R.compile_route((2, (4, 4), {}), [1, 0], jobs)
    assert ["PICKUP", "WHEAT", 1] in reverse_cmds
    checks.append(dict(check="harvest_to_feed_resource_precedence", finish=finish, reverse_finish=reverse_finish))
    out = R.OUT / "verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(passed=True, checks=checks), indent=2))
    print(out.read_text())


if __name__ == "__main__":
    main()

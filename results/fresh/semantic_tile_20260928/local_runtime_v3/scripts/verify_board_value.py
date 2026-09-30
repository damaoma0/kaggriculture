"""Verify restore fidelity and exact cash accounting before board valuation."""
from copy import deepcopy
import json
from pathlib import Path

from evaluate_boards import ROOT, Ledger, restored_env, observation, root_features


def main():
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine
    p = ROOT / "results/fresh/board_value/native/replay.json"
    replay = json.loads(p.read_text())
    root = 300
    before = deepcopy(replay["steps"][root])
    env = restored_env(replay, root, replay["info"]["seed"])
    starting = [f["money"] for f in before[0]["observation"]["farms"]]
    with Ledger(engine) as ledger:
        for states in replay["steps"][root+1:]:
            env.step([s["action"] for s in states])
    assert len(env.steps) == 720
    for i in range(2):
        actual = env.steps[-1][i]
        expected = replay["steps"][-1][i]
        assert actual.reward == expected["reward"]
        assert actual.observation.private == expected["observation"]["private"]
        row = ledger.data[i]
        assert starting[i] + sum(row["revenue"].values()) - sum(row["spend"].values()) == actual.reward
    for field in ("farms", "market", "town", "day", "hour", "step"):
        assert env.steps[-1][0].observation[field] == replay["steps"][-1][0]["observation"][field], field
    assert replay["steps"][root] == before, "Restoration mutated its input"

    # Changing a simulation's future seed must not change its root state.
    alternate = restored_env(replay, root, 987654321)
    for i in range(2):
        assert alternate.state[i].observation.private == before[i]["observation"]["private"]
    assert alternate.state[0].observation.farms == before[0]["observation"]["farms"]

    # Immediate stock liquidation is an exact nonlinear counterfactual sale.
    obs = observation(replay["steps"][root], 0)
    obs["private"]["shed"] = {p: 0 for p in engine.PRODUCTS}
    obs["private"]["shed"]["MELON"] = 100
    observed = root_features(obs, engine)["shed_sale_value_no_other_trades"]
    farm, private = deepcopy(obs["farms"][0]), deepcopy(obs["private"])
    market = deepcopy(obs["market"])
    initial_cash = farm["money"]
    for _ in range(100):
        price = engine.market_price("MELON", market["inventory"]["MELON"])
        assert engine._commit_unit("SELL", "MELON", price, farm, private, market)
    assert farm["money"] - initial_cash == observed
    panel_path = ROOT / "results/fresh/board_value/panel.json"
    if panel_path.exists():
        panel = json.loads(panel_path.read_text())
        assert len(panel) == 180
        roots = {}
        for row in panel:
            if row["root"] not in roots:
                data = json.loads((ROOT / "results/fresh/openings" / row["root"] / "replay.json").read_text())
                roots[row["root"]] = [root_features(observation(data["steps"][-1], i), engine) for i in range(2)]
            assert row["root_features"] == roots[row["root"]]
    print("PASS: 419 restored transitions match terminal state, exact ledger reconciles, input unchanged, future seed isolated, nonlinear stock valuation matches engine.")


if __name__ == "__main__":
    main()

"""Extract explicit successful purchase/sale quantities from recorded worlds.

Oversized and failed tape orders are not production targets. Preserve order
slots while capping each order to its recorded successful quantity, for BOTH
players. Verify every resulting baseline state against the original replay.
This defines a fixed-plan, fixed-opponent-volume counterfactual, not a live rival.
"""
from collections import Counter
from copy import deepcopy
import gzip
from hashlib import sha256
import json
import research_labour_profit as R


class FilledOrders:
    def __init__(self, sim):
        self.sim = sim
        self.fills = Counter()
        self.order_lookup = {}
        self.current = {}

    def __enter__(self):
        E = R.engine()
        self.old = {n: getattr(E, n) for n in ("_process_market", "_parse_order", "_commit_unit", "_do_hire", "_do_buy_land")}
        def market(state, env):
            self.order_lookup = {id(order): (self.sim.t, seat, i) for seat in (0, 1)
                                 for i, order in enumerate((state[seat].action.get("market") or [])[:10])}
            return self.old["_process_market"](state, env)
        def parse(order):
            key = self.order_lookup[id(order)]
            self.current[key[1]] = key
            return self.old["_parse_order"](order)
        def commit(op, item, price, farm, private, market, shed_capacity=100):
            ok = self.old["_commit_unit"](op, item, price, farm, private, market, shed_capacity)
            if ok:
                self.fills[self.current[self.sim.seats[id(farm)]]] += 1
            return ok
        def atomic(name):
            def call(farm, *args, **kwargs):
                before = farm["money"]
                result = self.old[name](farm, *args, **kwargs)
                if farm["money"] != before:
                    self.fills[self.current[self.sim.seats[id(farm)]]] += 1
                return result
            return call
        E._process_market, E._parse_order, E._commit_unit = market, parse, commit
        E._do_hire, E._do_buy_land = atomic("_do_hire"), atomic("_do_buy_land")
        return self

    def __exit__(self, *args):
        for name, fn in self.old.items():
            setattr(R.engine(), name, fn)


def convert(path, folder):
    game, actions = R.load_game(path)
    with R.Simulator(game) as sim:
        with FilledOrders(sim) as filled:
            original = sim.run(sim.initial, 0, 719, actions, snapshots=True)
        planned = deepcopy(actions)
        changed = Counter()
        for seat in (0, 1):
            for t in range(719):
                a = planned[seat][t]
                if not isinstance(a, dict):
                    continue
                for i, order in enumerate((a.get("market") or [])[:10]):
                    if not order:
                        continue
                    n = filled.fills[t, seat, i]
                    if order[0] in ("HIRE", "BUY_LAND"):
                        if not n:
                            a["market"][i] = ["SELL", "WHEAT", 0]
                            changed[f"{seat}:{order[0]}"] += 1
                    elif order[0] in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "SELL") and len(order) >= 3:
                        if int(order[2]) != n:
                            changed[f"{seat}:{order[0]}"] += 1
                        order[2] = n
        baseline = sim.run(sim.initial, 0, 719, planned, snapshots=True)
        assert original["money"] == baseline["money"] == game["rewards"]
        assert original["events"] == baseline["events"]
        assert original["state"][0].observation.farms == baseline["state"][0].observation.farms
        assert original["state"][0].observation.market == baseline["state"][0].observation.market
        assert all(original["state"][s].observation.private == baseline["state"][s].observation.private for s in (0, 1))
        for t in range(719):
            a, b = original["snapshots"][t], baseline["snapshots"][t]
            assert a[0].observation.step == b[0].observation.step == t
            assert a[0].observation.farms == b[0].observation.farms, (game["episode"], t, "farm")
            assert a[0].observation.market == b[0].observation.market, (game["episode"], t, "market")
            assert all(a[s].observation.private == b[s].observation.private for s in (0, 1)), (game["episode"], t, "private")
    game["our_actions"], game["opp_actions"] = planned[game["seat"]], planned[1 - game["seat"]]
    game["plan_provenance"] = dict(source=str(path.relative_to(R.ROOT)), source_sha256=sha256(path.read_bytes()).hexdigest(),
                                    changed_orders=dict(changed), verified_states=720,
                                    meaning="Both players' successful quantities fixed at recorded order slots; complete baseline state and transaction parity checked.")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{game['episode']}.json.gz"
    target.write_bytes(gzip.compress(json.dumps(game, separators=(",", ":")).encode(), mtime=0))
    return dict(episode=game["episode"], path=str(target.relative_to(R.ROOT)), **game["plan_provenance"])


def main():
    output = {}
    for tag, destination in (("ladder_holdout", "fixed_ladder"), ("leaders_holdout", "fixed_leaders")):
        manifest = json.loads((R.OUT / tag / "manifest.json").read_text())
        rows = []
        for name in manifest["paths"]:
            row = convert(R.ROOT / name, R.OUT / destination / "plans")
            rows.append(row)
            print(json.dumps(dict(panel=destination, episode=row["episode"], changed_orders=row["changed_orders"])), flush=True)
        output[destination] = rows
    (R.OUT / "fixed_plan_verification.json").write_text(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

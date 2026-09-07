"""Play candidate vs opponent once and compare where each side's money came from.

Usage: python scripts/compare.py agents/greedy_v2.py agents/public/tschinkel_router_v31.py --seed 1000
Revenue is estimated as units sold x quoted price at order time (ignores intra-order slippage).
"""
import argparse
import collections
import importlib.util

from kaggle_environments import make


def load(path):
    if not path.endswith(".py"):
        return path
    spec = importlib.util.spec_from_file_location("m" + str(abs(hash(path))), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--seed", type=int, default=1000)
    args = ap.parse_args()

    rev = [collections.Counter(), collections.Counter()]
    units = [collections.Counter(), collections.Counter()]
    spend = [collections.Counter(), collections.Counter()]
    peak = [collections.Counter(), collections.Counter()]

    def wrap(fn, idx):
        def w(obs):
            a = fn(obs)
            prices = obs["market"]["prices"]
            farm = obs["farms"][obs["player"]]
            n_anim = sum(1 for row in farm["tiles"] for t in row if isinstance(t, dict) and "animal" in t)
            n_plants = collections.Counter(t["crop"] for row in farm["tiles"] for t in row
                                           if isinstance(t, dict) and t.get("kind") == "PLANT")
            peak[idx]["animals"] = max(peak[idx]["animals"], n_anim)
            for c, n in n_plants.items():
                peak[idx]["plants:" + c] = max(peak[idx]["plants:" + c], n)
            peak[idx]["hands"] = max(peak[idx]["hands"], len(farm["hands"]))
            for o in a.get("market", []):
                if not o:
                    continue
                if o[0] == "SELL":
                    rev[idx][o[1]] += prices[o[1]] * int(o[2])
                    units[idx][o[1]] += int(o[2])
                elif o[0] == "BUY_ANIMAL":
                    spend[idx][o[1]] += int(o[2])
                elif o[0] == "BUY_SEED":
                    spend[idx]["seed:" + o[1]] += int(o[2])
                elif o[0] == "BUY_PRODUCT":
                    spend[idx]["buy:" + o[1]] += int(o[2])
                elif o[0] == "BUY_LAND":
                    spend[idx]["land"] += 1
                elif o[0] == "HIRE":
                    spend[idx]["hires"] += 1
            return a
        return w

    fa, fb = load(args.a), load(args.b)
    pa = wrap(fa, 0) if callable(fa) else fa
    pb = wrap(fb, 1) if callable(fb) else fb
    env = make("kaggriculture", configuration={"seed": args.seed}, debug=True)
    env.run([pa, pb])
    final = env.steps[-1]
    print(f"final banks: A={final[0].reward:.0f}  B={final[1].reward:.0f}")
    print(f"shops: {final[0].observation['town']['unlocked_shops']}")
    prods = sorted(set(rev[0]) | set(rev[1]), key=lambda p: -(rev[0][p] + rev[1][p]))
    print(f"\n{'product':12s} {'A units':>8s} {'A revenue':>10s} {'B units':>8s} {'B revenue':>10s}")
    for p in prods:
        print(f"{p:12s} {units[0][p]:8d} {rev[0][p]:10.0f} {units[1][p]:8d} {rev[1][p]:10.0f}")
    print(f"{'TOTAL':12s} {sum(units[0].values()):8d} {sum(rev[0].values()):10.0f} {sum(units[1].values()):8d} {sum(rev[1].values()):10.0f}")
    print("\npurchases A:", dict(spend[0]))
    print("purchases B:", dict(spend[1]))
    print("peak A:", dict(peak[0]))
    print("peak B:", dict(peak[1]))


if __name__ == "__main__":
    main()

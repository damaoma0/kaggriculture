"""Readable digest of a recorded opening (days 0-5): per day and unit, the non-move commands with hour and tile (moves
counted), the market orders that filled, and the dawn cash / board. The base for a hand-written opening plan.

usage: opening_digest_20260929.py --ep 112570602 [--days 6] [--seat-of leader|other]"""
import argparse
import glob
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
MOVES = ("NORTH", "SOUTH", "EAST", "WEST")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", default="112570602")
    ap.add_argument("--days", type=int, default=6)
    a = ap.parse_args()
    tape = json.load(gzip.open(glob.glob(str(ROOT / f"data/leader_tapes/*/{a.ep}.json.gz"))[0], "rt", encoding="utf-8"))
    seat = int(tape["seat"])
    w = UE.World(tape["seed"], tape["shops"])
    fills = defaultdict(list)
    o_commit, o_hire = E._commit_unit, E._do_hire

    def commit(op, item, price, farm, private, market, *x, **k):
        r = o_commit(op, item, price, farm, private, market, *x, **k)
        if r and farm is w.farms[seat]:
            fills[w.t].append((op, item, price))
        return r

    def hire(farm, *x, **k):
        m0 = farm["money"]
        r = o_hire(farm, *x, **k)
        if farm is w.farms[seat] and farm["money"] != m0:
            fills[w.t].append(("HIRE", "", m0 - farm["money"]))
        return r
    E._commit_unit, E._do_hire = commit, hire
    log = defaultdict(lambda: defaultdict(list))        # day -> unit -> [(hour, cmd, tile)]
    moves = defaultdict(Counter)
    dawn = {}
    try:
        for t in range(24 * a.days):
            d, h = divmod(t, 24)
            farm = w.farms[seat]
            if h == 0:
                b = Counter()
                for row in farm["tiles"]:
                    for x in row:
                        if isinstance(x, dict):
                            b[x.get("animal") or x.get("crop") or x.get("kind")] += 1
                dawn[d] = (farm["money"], dict(b))
            act = UE.tape_action(tape["actions"], t)
            units = [farm["farmer"]] + list(farm["hands"])
            cmds = [act.get("farmer")] + list(act.get("hands") or [])
            for i, c in enumerate(cmds):
                if not c or c[0] == "PASS":
                    continue
                pos = units[i] if i < len(units) else None
                tile = pos[1] * 10 + pos[0] if pos else None
                if c[0] in MOVES:
                    moves[d][i] += 1
                else:
                    log[d][i].append((h, " ".join(str(x) for x in c), tile))
            w.step([act, UE.tape_action(tape["opp_actions"], t)] if seat == 0 else
                   [UE.tape_action(tape["opp_actions"], t), act])
    finally:
        E._commit_unit, E._do_hire = o_commit, o_hire
    for d in range(a.days):
        print(f"\n=== day {d}: dawn cash {dawn[d][0]:.0f}, board {dawn[d][1]}")
        mk = defaultdict(Counter)
        for t in range(24 * d, 24 * d + 24):
            for op, item, price in fills.get(t, []):
                mk[t % 24][(op, item)] += price
        print("  market (hour: filled):", "; ".join(f"h{h}: " + ", ".join(f"{op} {it} {v:.0f}" for (op, it), v in c.items())
                                              for h, c in sorted(mk.items())))
        for i in sorted(log[d]):
            nm = "farmer" if i == 0 else f"hand{i}"
            print(f"  {nm:6s} ({moves[d][i]:2d} moves): " + "  ".join(f"h{h}:{c}@{t}" for h, c, t in log[d][i]))


if __name__ == "__main__":
    main()

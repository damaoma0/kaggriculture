"""Execution-layer sale losses of a finished harness game, per unit, for both farms (user 2026-09-29: the sale timing
losses the execution layer incurs, not the price gap to the rival).

Each game is replayed exactly (seed, forced shops, both recorded action streams; both final cash totals must match).
Engine hooks record, per farm and product:
  collected  a HARVEST / COLLECT_* adding the product to a unit's inventory (step t_c)
  arrived    a PLACE / DROP adding it to the shed, or the midnight drop of the hands' inventories (t_a)
  discarded  what the midnight drop cannot fit under the shed cap
  sold       each committed SELL unit (t_s, price)
Units are matched first in, first out. With q(t) the market quote at the start of step t (before its trades):
  carry    q(t_c) - q(t_a)     the price moved while the unit rode in a hand
  hold     q(t_a) - price      the price moved in the shed until the sale (includes the sale hour)
  lost     q(t_c)              units discarded or still unsold at the end
Quotes ignore the unit's own price impact, so these are gross opportunity measures, not recoverable cash. Wheat and
fertilizer are excluded (bought and consumed as well as collected and sold).

usage: exec_sale_loss_20260929.py --dir <harness result dir> [--dir ...] [--out results/fresh/exec_sale_loss_20260929/x.json]"""
import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402

E = UE.engine()
TRACK = ("MILK", "WOOL", "EGG", "STRAWBERRY", "TOMATO", "CARROT", "MELON")


def _counts(d):
    return Counter({k: int(v) for k, v in (d or {}).items() if k in TRACK and int(v) > 0})


def replay(result, actions):
    w = UE.World(result["case"]["seed"], result["shops"])
    ev = []                                       # (t, side, kind, product, n or price)
    side_of = lambda private: 0 if private is w.private(0) else 1
    o_apply, o_drop, o_commit = E._apply_unit_action, E._drop_inventories_to_shed, E._commit_unit

    def apply(farm, private, idx, action, *a, **k):
        inv0 = _counts(private["inventories"][idx]) if idx < len(private["inventories"]) else Counter()
        shed0 = _counts(private["shed"])
        r = o_apply(farm, private, idx, action, *a, **k)
        inv1 = _counts(private["inventories"][idx]) if idx < len(private["inventories"]) else Counter()
        shed1 = _counts(private["shed"])
        s, op = side_of(private), (action[0] if isinstance(action, (list, tuple)) and action else "")
        for p in TRACK:
            if op in ("HARVEST",) or op.startswith("COLLECT"):
                if inv1[p] > inv0[p]:
                    ev.append((w.t, s, "c", p, inv1[p] - inv0[p]))
            if shed1[p] > shed0[p] and op != "PICKUP":
                ev.append((w.t, s, "a", p, shed1[p] - shed0[p]))
        return r

    def drop(private, capacity):
        held = Counter()
        for inv in private["inventories"]:
            held.update(_counts(inv))
        shed0 = _counts(private["shed"])
        r = o_drop(private, capacity)
        shed1 = _counts(private["shed"])
        s = side_of(private)
        for p in TRACK:
            took = shed1[p] - shed0[p]
            if took > 0:
                ev.append((w.t, s, "a", p, took))
            if held[p] - took > 0:
                ev.append((w.t, s, "d", p, held[p] - took))
        return r

    def commit(op, item, price, farm, private, market, cap=100):
        r = o_commit(op, item, price, farm, private, market, cap)
        if r and op == "SELL" and item in TRACK:
            ev.append((w.t, side_of(private), "s", item, float(price)))
        return r
    quotes = []
    E._apply_unit_action, E._drop_inventories_to_shed, E._commit_unit = apply, drop, commit
    try:
        while w.t < 719:
            quotes.append(dict(w.market["prices"]))
            w.step([UE.tape_action(actions[i], w.t) for i in (0, 1)])
    finally:
        E._apply_unit_action, E._drop_inventories_to_shed, E._commit_unit = o_apply, o_drop, o_commit
    return ev, quotes, [w.farms[0]["money"], w.farms[1]["money"]]


def losses(ev, quotes, side):
    q = lambda t, p: float(quotes[min(t, len(quotes) - 1)].get(p, 0))
    out = defaultdict(Counter)
    carried, shed = defaultdict(deque), defaultdict(deque)
    for t, s, kind, p, x in ev:
        if s != side:
            continue
        if kind == "c":
            for _ in range(int(x)):
                carried[p].append(t)
            out[p]["collected"] += x
        elif kind == "a":
            for _ in range(int(x)):
                tc = carried[p].popleft() if carried[p] else t     # a unit placed without a recorded pickup: arrives as collected
                shed[p].append((tc, t))
                out[p]["carry"] += q(tc, p) - q(t, p)
                out[p]["carry_hours"] += t - tc
        elif kind == "d":
            for _ in range(int(x)):
                tc = carried[p].popleft() if carried[p] else t
                out[p]["discarded"] += 1
                out[p]["lost"] += q(tc, p)
        elif kind == "s":
            if shed[p]:
                tc, ta = shed[p].popleft()
            else:
                tc = ta = t
            out[p]["sold"] += 1
            out[p]["hold"] += q(ta, p) - x
            out[p]["hold_hours"] += t - ta
            out[p]["revenue"] += x
    for p in TRACK:
        left = len(carried[p]) + len(shed[p])
        out[p]["unsold_end"] += left
        out[p]["lost"] += sum(q(t, p) for t in carried[p]) + sum(q(tc, p) for tc, _ in shed[p])
    return {p: dict(v) for p, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = []
    for d in a.dir:
        for f in sorted(glob.glob(os.path.join(ROOT, d, "*.json"))):
            if f.endswith(".actions.json") or f.endswith("summary.json"):
                continue
            r = json.load(open(f))
            if not r.get("completed"):
                continue
            acts = json.load(open(f[:-5] + ".actions.json"))
            ev, quotes, final = replay(r, acts)
            ok = [round(x) for x in final] == [round(x) for x in r["cash_by_seat"]]
            seat = r["case"]["seat"]
            rows.append(dict(dir=d, case=r["case"], margin=r["margin"], replay_matches=ok,
                             own=losses(ev, quotes, seat), rival=losses(ev, quotes, 1 - seat)))
            print(f"{Path(d).name} {r['case']['id']} replay==result {ok}", flush=True)
    if a.out:
        out = ROOT / a.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rows))
    n = max(1, len(rows))
    print(f"\n{len(rows)} games, {sum(r['replay_matches'] for r in rows)} replays reproduce both cash totals; per game:")
    print(f"{'product':11s} {'side':5s} {'collected':>9s} {'sold':>6s} {'disc':>5s} {'unsold':>6s} | {'carry':>7s} {'h/unit':>6s} "
          f"{'hold':>7s} {'h/unit':>6s} {'lost':>7s} | {'total':>7s}")
    tot = Counter()
    for p in TRACK:
        for side in ("own", "rival"):
            c = Counter()
            for r in rows:
                c.update(r[side].get(p, {}))
            loss = (c["carry"] + c["hold"] + c["lost"]) / n
            tot[side] += loss
            tot[side + "_carry"] += c["carry"] / n
            tot[side + "_hold"] += c["hold"] / n
            tot[side + "_lost"] += c["lost"] / n
            print(f"{p:11s} {side:5s} {c['collected'] / n:9.1f} {c['sold'] / n:6.1f} {c['discarded'] / n:5.1f} "
                  f"{c['unsold_end'] / n:6.1f} | {c['carry'] / n:+7.0f} {c['carry_hours'] / max(1, c['collected']):6.1f} "
                  f"{c['hold'] / n:+7.0f} {c['hold_hours'] / max(1, c['sold']):6.1f} {c['lost'] / n:+7.0f} | {loss:+7.0f}")
    for side in ("own", "rival"):
        print(f"TOTAL {side:5s}: carry {tot[side + '_carry']:+.0f}  hold {tot[side + '_hold']:+.0f}  "
              f"lost {tot[side + '_lost']:+.0f}  = {tot[side]:+.0f} per game")


if __name__ == "__main__":
    main()

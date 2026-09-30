"""How DSM reacts to an early melon dump: exact replay of DSM's recorded games (both action streams, recorded shops);
per game both sides' melon plantings, hourly melon sales and prices on days 9-14, melons still on tiles / in the shed,
dawn cash and land purchases. Games are split by who sold melons first on the first melon day.

usage: dsm_melon_reaction_20260929.py [--out results/fresh/dsm_melon_reaction_20260929/games.json]"""
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


def melon_state(farm, private):
    tiles = [t for row in farm["tiles"] for t in row if isinstance(t, dict) and t.get("crop") == "MELON"]
    return dict(tiles=len(tiles), units_on_tiles=sum(int(t.get("yield_units", 0) or 0) for t in tiles),
                shed=int((private.get("shed") or {}).get("MELON", 0)))


def replay(x):
    w = UE.World(x["seed"], x["shops"])
    seat = x["seat"]
    acts = {seat: x["actions"], 1 - seat: x["opp_actions"]}
    sales = []
    plants = [Counter(), Counter()]
    orig_c, orig_a = E._commit_unit, E._apply_unit_action

    def commit(op, item, price, farm, private, market, cap=100):
        r = orig_c(op, item, price, farm, private, market, cap)
        if r and op == "SELL" and item == "MELON":
            sales.append((w.t, 0 if farm is w.farms[0] else 1, float(price)))
        return r

    def apply(farm, private, idx, action, *a, **k):
        if isinstance(action, (list, tuple)) and action[:2] == ["PLANT", "MELON"]:
            side = 0 if farm is w.farms[0] else 1
            before = sum(1 for row in farm["tiles"] for t in row if isinstance(t, dict) and t.get("crop") == "MELON")
            r = orig_a(farm, private, idx, action, *a, **k)
            after = sum(1 for row in farm["tiles"] for t in row if isinstance(t, dict) and t.get("crop") == "MELON")
            if after > before:
                plants[side][w.t // 24] += 1
            return r
        return orig_a(farm, private, idx, action, *a, **k)
    E._commit_unit, E._apply_unit_action = commit, apply
    dawn = defaultdict(dict)
    try:
        while w.t < 719:
            if w.t % 24 == 0 and 8 <= w.t // 24 <= 15:
                d = w.t // 24
                for i in (0, 1):
                    dawn[d][i] = dict(cash=w.farms[i]["money"], quads=len(w.farms[i].get("unlocked_quadrants", [])),
                                      **melon_state(w.farms[i], w.private(i)))
                dawn[d]["stock"] = int(w.market["inventory"]["MELON"]) - 10000
            w.step([UE.tape_action(acts[i], w.t) for i in (0, 1)])
    finally:
        E._commit_unit, E._apply_unit_action = orig_c, orig_a
    return sales, plants, dawn, [w.farms[0]["money"], w.farms[1]["money"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/fresh/dsm_melon_reaction_20260929/games.json")
    a = ap.parse_args()
    rows = []
    for folder in sorted(glob.glob(str(ROOT / "data/leader_tapes/16732748_*"))):
        for p in sorted(glob.glob(folder + "/*.json.gz")):
            x = json.load(gzip.open(p, "rt", encoding="utf-8"))
            try:
                sales, plants, dawn, final = replay(x)
            except Exception as exc:
                print("replay failed", p, repr(exc)[:120])
                continue
            ds, os_ = x["seat"], 1 - x["seat"]
            first_day = min((t // 24 for t, _, _ in sales), default=None)

            def first(side):
                ts = [t for t, s, _ in sales if s == side]
                return min(ts) if ts else None
            fd, fo = first(ds), first(os_)
            by = lambda side, d0, d1: [(t, pr) for t, s, pr in sales if s == side and d0 <= t // 24 <= d1]
            rows.append(dict(
                episode=x["episode"], folder=Path(folder).name, names=x.get("names"), dsm_seat=ds,
                margin=final[ds] - final[os_], recorded_match=[round(v) for v in final] == [round(v) for v in x["rewards"]],
                first_sale_step=dict(dsm=fd, opp=fo), first_melon_day=first_day,
                plants=dict(dsm=dict(plants[ds]), opp=dict(plants[os_])),
                sales_d9_14=dict(dsm=by(ds, 9, 14), opp=by(os_, 9, 14)),
                sales_all=dict(dsm=len([1 for _, s, _ in sales if s == ds]), opp=len([1 for _, s, _ in sales if s == os_])),
                rev_all=dict(dsm=sum(pr for _, s, pr in sales if s == ds), opp=sum(pr for _, s, pr in sales if s == os_)),
                dawn={str(d): dict(dsm=v[ds], opp=v[os_], stock=v["stock"]) for d, v in dawn.items()}))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows))
    print(len(rows), "games replayed;", sum(r["recorded_match"] for r in rows), "reproduce the recorded cash ->", out)


if __name__ == "__main__":
    main()

"""DSM vs Unknown Mother-Goose (MGT's source team) from the recorded tapes: exact replay of both action streams with the
recorded shops; per game and averaged over games, both sides' dawn cash, unlocked quadrants, animals by species and
crops by type per day, revenue / spending by item over the season, and the day each land purchase happened.

usage: dsm_vs_umg_20260929.py [--out results/fresh/dsm_vs_umg_20260929/summary.json]"""
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
DAYS = (1, 3, 5, 6, 8, 10, 11, 12, 14, 16, 18, 21, 24, 27)


def games():
    out = {}
    for folder in glob.glob(str(ROOT / "data/leader_tapes/16732748_*")) + glob.glob(str(ROOT / "data/leader_tapes/16730612_*")):
        for p in glob.glob(folder + "/*.json.gz"):
            x = json.load(gzip.open(p, "rt", encoding="utf-8"))
            nm = [str(n) for n in x.get("names") or []]
            if any("mother" in n.lower() for n in nm) and any(n.strip() == "DSM" for n in nm):
                dsm_seat = next(i for i, n in enumerate(nm) if n.strip() == "DSM")
                out.setdefault(x["episode"], (x, dsm_seat))
    return out


def board(farm):
    c = Counter()
    for row in farm["tiles"]:
        for t in row:
            if isinstance(t, dict):
                if t.get("animal"):
                    c[t["animal"]] += 1
                elif t.get("kind") == "PLANT":
                    c[t["crop"]] += 1
    c["quads"] = len(farm.get("unlocked_quadrants", []))
    c["cash"] = farm["money"]
    return c


def replay(x, dsm_seat):
    w = UE.World(x["seed"], x["shops"])
    seat = x["seat"]
    acts = {seat: x["actions"], 1 - seat: x["opp_actions"]}
    flows = [Counter(), Counter()]
    orig = E._commit_unit

    def commit(op, item, price, farm, private, market, cap=100):
        r = orig(op, item, price, farm, private, market, cap)
        if r:
            i = 0 if farm is w.farms[0] else 1
            flows[i][f"{op}|{item}"] += float(price)
        return r
    E._commit_unit = commit
    daily = [{}, {}]
    try:
        while w.t < 719:
            if w.t % 24 == 0:
                for i in (0, 1):
                    daily[i][w.t // 24] = board(w.farms[i])
            a = [None, None]
            for i in (0, 1):
                a[i] = UE.tape_action(acts[i], w.t)
            w.step(a)
        for i in (0, 1):
            daily[i][30] = board(w.farms[i])
    finally:
        E._commit_unit = orig
    final = [w.farms[0]["money"], w.farms[1]["money"]]
    return dict(dsm=daily[dsm_seat], umg=daily[1 - dsm_seat], flows_dsm=flows[dsm_seat], flows_umg=flows[1 - dsm_seat],
                final=[final[dsm_seat], final[1 - dsm_seat]], recorded=[x["rewards"][dsm_seat], x["rewards"][1 - dsm_seat]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/fresh/dsm_vs_umg_20260929/summary.json")
    a = ap.parse_args()
    G = games()
    print(len(G), "DSM vs Mother-Goose games")
    acc = defaultdict(lambda: defaultdict(float))
    flows = [Counter(), Counter()]
    per = []
    for ep, (x, ds) in sorted(G.items()):
        r = replay(x, ds)
        ok = [round(v) for v in r["final"]] == [round(v) for v in r["recorded"]]
        land_d = [d for d in range(1, 31) if r["dsm"][d]["quads"] > r["dsm"][d - 1]["quads"]]
        land_u = [d for d in range(1, 31) if r["umg"][d]["quads"] > r["umg"][d - 1]["quads"]]
        per.append(dict(episode=ep, dsm_seat=ds, final=r["final"], replay_matches_recording=ok, land_dsm=land_d,
                        land_umg=land_u, cash_d10_14=[[round(r[s][d]["cash"]) for d in (10, 11, 12, 14)] for s in ("dsm", "umg")]))
        print(f"{ep} margin DSM {r['final'][0] - r['final'][1]:+7.0f} replay==recording {ok} | land DSM {land_d} UMG {land_u} | "
              f"cash d10/11/12/14 DSM {[round(r['dsm'][d]['cash']) for d in (10, 11, 12, 14)]} "
              f"UMG {[round(r['umg'][d]['cash']) for d in (10, 11, 12, 14)]}", flush=True)
        for s in ("dsm", "umg"):
            for d in DAYS + (30,):
                for k, v in r[s][d].items():
                    acc[(s, d)][k] += v / len(G)
        flows[0].update({k: v / len(G) for k, v in r["flows_dsm"].items()})
        flows[1].update({k: v / len(G) for k, v in r["flows_umg"].items()})
    keys = ["cash", "quads", "SHEEP", "COW", "GOOSE", "MELON", "STRAWBERRY", "WHEAT", "CARROT", "TOMATO"]
    print("\nmean board at dawn, DSM / Mother-Goose:")
    print("day  " + " ".join(f"{k[:6]:>13s}" for k in keys))
    for d in DAYS + (30,):
        print(f"d{d:2d}  " + " ".join(f"{acc[('dsm', d)][k]:6.0f}/{acc[('umg', d)][k]:<6.0f}" if k == "cash" else
                                    f"{acc[('dsm', d)][k]:6.1f}/{acc[('umg', d)][k]:<6.1f}" for k in keys))
    print("\nseason flows, mean per game: DSM / Mother-Goose / difference")
    for k in sorted(set(flows[0]) | set(flows[1]), key=lambda k: -(flows[0][k] - flows[1][k]) if k.startswith("SELL") else 0):
        print(f"   {k:26s} {flows[0][k]:9.0f} {flows[1][k]:9.0f} {flows[0][k] - flows[1][k]:+9.0f}")
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(games=per, flows_dsm=flows[0], flows_umg=flows[1],
                                   board={f"{s}|{d}": dict(acc[(s, d)]) for s in ("dsm", "umg") for d in DAYS + (30,)}), indent=1))


if __name__ == "__main__":
    main()

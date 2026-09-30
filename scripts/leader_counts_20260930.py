"""Tile count figures from every leader tape (user 2026-09-30: "Could we also obtain new tile count figures from other
leaders"): each game in data/leader_tapes/<team>_<sub>/ replayed exactly (both seats' recorded actions, forced shops,
scripts/upkeep_engine.World) with the leader's counts at every dawn (crops, animals, empty, weeds), quadrants owned
and hands on the farm at noon. Then, for days 8-27, how well each source's median counts per revealed shop-type mix
(MILK / WOOL / EGG / FARM, as the DSM cassette) predict DSM-new's counts (DSM itself leave-one-out).

usage: leader_counts_20260930.py run [--workers 2]     -> results/fresh/leader_counts_20260930.json
       leader_counts_20260930.py report"""
import argparse
import gzip
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAPES = ROOT / "data/leader_tapes"
OUT = ROOT / "results/fresh/leader_counts_20260930.json"
DSM = "16732748_56692773"
FOURQ = {"16621497_56686384", "16623559_56688636", "16681125_56679033", "16718819_56663513", "16730326_56678954",
         "16730357_56688520"}
MILK = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
EGG = {"BAKERY", "BRUNCH_SPOT", "PET_CAFE"}
KINDS = ["STRAWBERRY", "TOMATO", "MELON", "CARROT", "WHEAT", "COW", "SHEEP", "GOOSE", "EMPTY", "WEED"]
CORE = ["STRAWBERRY", "TOMATO", "MELON", "COW", "SHEEP", "GOOSE"]


def shop_type(s):
    return "MILK" if s in MILK else ("WOOL" if s == "YARN_STORE" else ("EGG" if s in EGG else "FARM"))


def lab(t):
    if t is None:
        return "EMPTY"
    if t == "LOCKED":
        return "LOCKED"
    return t.get("crop") or t.get("animal") or t.get("kind")


def replay(path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import upkeep_engine as UE
    t = json.load(gzip.open(path, "rt", encoding="utf-8"))
    seat = int(t["seat"])
    w = UE.World(t["seed"], t["shops"])
    days = {}
    while w.t < 720:
        f = w.farms[seat]
        if w.t % 24 == 0:
            c = Counter(lab(x) for row in f["tiles"] for x in row)
            days[w.t // 24] = dict(c={k: c[k] for k in KINDS}, q=len(f.get("unlocked_quadrants") or []))
        if w.t % 24 == 12:
            days[w.t // 24]["hands"] = len(f.get("hands") or [])
        acts = [None, None]
        acts[seat] = UE.tape_action(t["actions"], w.t)
        acts[1 - seat] = UE.tape_action(t["opp_actions"], w.t)
        w.step(acts)
    return dict(team=path.parent.name, ep=t["episode"], name=t["names"][seat], shops=t["shops"],
                reward=t["rewards"][seat], margin=t["rewards"][seat] - t["rewards"][1 - seat], days=days)


def run(a):
    paths = sorted(p for d in TAPES.iterdir() if d.is_dir() and not d.name.startswith("_") for p in d.glob("*.json.gz"))
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(replay, paths, chunksize=8))
    OUT.write_text(json.dumps(rows), encoding="utf-8")
    print(len(rows), "games ->", OUT)


def report(a):
    rows = json.loads(OUT.read_text(encoding="utf-8"))
    for r in rows:
        r["days"] = {int(k): v for k, v in r["days"].items()}
    dsm = [r for r in rows if r["team"] == DSM]

    def key(r, d):
        return tuple(sorted(shop_type(s) for s in r["shops"][:d // 3]))

    def med(games, k, d):
        cs = [g["days"][d]["c"] for g in games if d in g["days"] and key(g, d) == k]
        return {kk: st.median(c[kk] for c in cs) for kk in KINDS} if cs else None

    def err(p, x, ks):
        return sum(abs(p[k] - x[k]) for k in ks) / 2
    same_open = {r["team"] for r in rows if r["team"] not in FOURQ | {DSM}}
    sources = {
        "DSM only (LOO)": lambda g: [x for x in dsm if x["ep"] != g["ep"]],
        "4Q others": lambda g: [x for x in rows if x["team"] in FOURQ],
        "4Q incl. DSM (LOO)": lambda g: [x for x in rows if (x["team"] in FOURQ or x["team"] == DSM) and x["ep"] != g["ep"]],
        "3Q / other leaders": lambda g: [x for x in rows if x["team"] in same_open],
        "all leaders (LOO)": lambda g: [x for x in rows if not (x["team"] == DSM and x["ep"] == g["ep"])],
    }
    days = (8, 11, 14, 17, 20, 23, 26)
    print(f"{len(rows)} leader games; DSM-new {len(dsm)}. Predicting DSM's counts at a dawn from the median counts of a source's "
          "games with the same revealed shop-type mix: core error / total error in tiles (DSM worlds covered)")
    print("source | " + " | ".join(f"day {d}" for d in days))
    for name, f in sources.items():
        cells = []
        for d in days:
            ec, et = [], []
            for g in dsm:
                if d not in g["days"]:
                    continue
                p = med(f(g), key(g, d), d)
                if p is None:
                    continue
                x = g["days"][d]["c"]
                ec.append(err(p, x, CORE))
                et.append(err(p, x, KINDS[:8]))
            cells.append(f"{st.mean(ec):4.1f}/{st.mean(et):4.1f} ({len(ec)})" if ec else "-")
        print(f"{name:20s} | " + " | ".join(cells))
    print("\nquadrants at dawn (median) and hands at noon (median) by team group, days 6 / 9 / 11 / 14 / 20:")
    for name, games in (("DSM-new", dsm), ("4Q others", [x for x in rows if x["team"] in FOURQ]),
                        ("3Q / other leaders", [x for x in rows if x["team"] in same_open])):
        print(f"   {name:20s} q " + " ".join(f"{st.median(g['days'][d]['q'] for g in games if d in g['days'])}" for d in (6, 9, 11, 14, 20))
              + " | hands " + " ".join(f"{st.median(g['days'][d].get('hands', 0) for g in games if d in g['days'])}" for d in (6, 9, 11, 14, 20)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=2)
    sub.add_parser("report")
    a = ap.parse_args()
    {"run": run, "report": report}[a.cmd](a)


if __name__ == "__main__":
    main()

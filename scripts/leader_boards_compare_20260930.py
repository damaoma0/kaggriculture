"""Other leaders' boards against DSM-new's (user 2026-09-30: "investigate other leaders as well" - can their games widen
a DSM board-retrieval library keyed by shop prefix?).

Replays every leader tape in data/leader_tapes/<team>_<sub>/ (both seats' recorded actions, forced shops,
scripts/upkeep_engine.World) to the day-11 dawn and compares the leader's boards with DSM-new's (16732748_56692773):
- quadrant timing (tape quadrants_by_day): day the 3rd / 4th quadrant is owned;
- day-6 board vs DSM's modal day-6 board (DSM's opening is fixed: 97 of 100 tiles identical over its 43 games);
- day-8 / day-11 boards vs the DSM games with the same first two shops: tiles off, non-filler tiles off (wheat, carrot,
  empty, weed = filler) and non-filler composition distance.

usage: leader_boards_compare_20260930.py [--workers 1] [--out results/fresh/leader_boards_20260930.json]"""
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
DSM = "16732748_56692773"
DAYS = (6, 8, 9, 11)
FILL = {"WHEAT", "EMPTY", "WEED", "CARROT"}


def lab(t):
    if t is None:
        return "EMPTY"
    if t == "LOCKED":
        return "LOCKED"
    return t.get("crop") or t.get("animal") or t.get("kind")


def core(x):
    return "FILL" if x in FILL else x


def replay(path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import upkeep_engine as UE
    t = json.load(gzip.open(path, "rt", encoding="utf-8"))
    seat = int(t["seat"])
    w = UE.World(t["seed"], t["shops"])
    boards = {}
    while w.t <= 24 * max(DAYS):
        if w.t % 24 == 0 and w.t // 24 in DAYS:
            boards[w.t // 24] = [lab(x) for row in w.farms[seat]["tiles"] for x in row]
        if w.t == 24 * max(DAYS):
            break
        acts = [None, None]
        acts[seat] = UE.tape_action(t["actions"], w.t)
        acts[1 - seat] = UE.tape_action(t["opp_actions"], w.t)
        w.step(acts)
    # quadrants_by_day[d] = [seat 0, seat 1] quadrants owned at day d's dawn: the quadrant counted at dawn d was bought
    # on day d - 1
    q = [(int(n[seat]) if isinstance(n, list) else int(n or 0)) for n in (t.get("quadrants_by_day") or [])]
    q3 = next((d - 1 for d, n in enumerate(q) if n >= 3), None)
    q4 = next((d - 1 for d, n in enumerate(q) if n >= 4), None)
    return dict(team=path.parent.name, ep=t["episode"], name=t["names"][seat], shops=t["shops"], q3=q3, q4=q4,
                reward=t["rewards"][seat], margin=t["rewards"][seat] - t["rewards"][1 - seat], boards=boards)


def off(a, b, f=lambda x: x):
    return sum(1 for x, y in zip(a, b) if f(x) != f(y))


def comp(a, b):
    ca, cb = Counter(map(core, a)), Counter(map(core, b))
    return sum(abs(ca[k] - cb[k]) for k in set(ca) | set(cb) if k not in ("FILL", "LOCKED")) / 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out", default=str(ROOT / "results/fresh/leader_boards_20260930.json"))
    a = ap.parse_args()
    paths = sorted(p for d in TAPES.iterdir() if d.is_dir() and not d.name.startswith("_") for p in d.glob("*.json.gz"))
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(replay, paths, chunksize=8))
    Path(a.out).write_text(json.dumps(rows), encoding="utf-8")
    dsm = [r for r in rows if r["team"] == DSM]
    mode6 = [Counter(r["boards"][6][i] for r in dsm).most_common(1)[0][0] for i in range(100)]
    by12 = defaultdict(list)
    for r in dsm:
        by12[tuple(r["shops"][:2])].append(r)
    dsm12 = set(by12)
    print(f"{len(rows)} leader games replayed; DSM-new {len(dsm)} games, {len(dsm12)} distinct first-two-shop pairs")
    print("team_sub (name) | games | 3rd quad by day 8 / 4th by day 10 | day-6 tiles off DSM's opening (non-filler) | "
          "games with a DSM same-2-shop match: day-8 non-filler off / comp, day-11 non-filler off / comp | new (s1,s2) pairs")
    teams = defaultdict(list)
    for r in rows:
        teams[r["team"]].append(r)
    for tm, rs in sorted(teams.items(), key=lambda kv: -len(kv[1])):
        m = lambda f: st.mean(f(r) for r in rs)  # noqa: E731
        q3 = sum(1 for r in rs if r["q3"] is not None and r["q3"] <= 8) / len(rs)
        q4 = sum(1 for r in rs if r["q4"] is not None and r["q4"] <= 10) / len(rs)
        o6 = m(lambda r: off(r["boards"][6], mode6))
        o6c = m(lambda r: off(r["boards"][6], mode6, core))
        matched = [r for r in rs if any(p["ep"] != r["ep"] for p in by12.get(tuple(r["shops"][:2]), []))]

        def vs(r, d, f):
            peers = [p for p in by12[tuple(r["shops"][:2])] if p["ep"] != r["ep"]]
            return st.mean(f(r["boards"][d], p["boards"][d]) for p in peers)
        s8 = (st.mean(vs(r, 8, lambda x, y: off(x, y, core)) for r in matched), st.mean(vs(r, 8, comp) for r in matched)) if matched else (float("nan"),) * 2
        s11 = (st.mean(vs(r, 11, lambda x, y: off(x, y, core)) for r in matched), st.mean(vs(r, 11, comp) for r in matched)) if matched else (float("nan"),) * 2
        new_pairs = len({tuple(r["shops"][:2]) for r in rs} - dsm12) if tm != DSM else 0
        name = Counter(r["name"] for r in rs).most_common(1)[0][0]
        print(f"{tm} ({name[:18]}) | {len(rs):3d} | {q3:4.0%} / {q4:4.0%} | {o6:5.1f} ({o6c:4.1f}) | n={len(matched):2d}: "
              f"{s8[0]:5.1f} / {s8[1]:4.1f}, {s11[0]:5.1f} / {s11[1]:4.1f} | {new_pairs}")


if __name__ == "__main__":
    main()

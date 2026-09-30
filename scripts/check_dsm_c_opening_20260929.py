"""Leave-one-out check of a tape-router agent's days 0-5 (default agents/mgt_dsm_c.py, the current DSM library): in each
recorded current-DSM world, load the agent without that world's own tape (MGT_EXCLUDE), play steps 0-143 against the
recorded opponent and compare the dawn-6 board and cash with DSM's own recording there.

usage: check_dsm_c_opening_20260929.py [--agent agents/mgt_dsm_c.py] [--limit 30]"""
import argparse, glob, gzip, importlib.util, json, os, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import upkeep_engine as UE  # noqa: E402


def load(path, exclude):
    os.environ["MGT_EXCLUDE"] = str(exclude)
    name = f"_loo_{exclude}"
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m)
    os.environ.pop("MGT_EXCLUDE", None)
    return getattr(m, "mgt_kaggle_entry", None) or [v for k, v in vars(m).items() if callable(v) and not k.startswith("__")][-1]


def board(f):
    return Counter((v.get("animal") or v.get("crop")) for row in f["tiles"] for v in row if isinstance(v, dict) and v.get("kind") != "WEED" and (v.get("animal") or v.get("crop")))


def run(x, entry=None):
    seat = int(x["seat"]); w = UE.World(x["seed"], x["shops"])
    for t in range(144):
        a = entry(w.obs(seat), None) if entry else UE.tape_action(x["actions"], t)
        o = UE.tape_action(x["opp_actions"], t)
        w.step([a, o] if seat == 0 else [o, a])
    f = w.farms[seat]
    return int(f["money"]), board(f)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--agent", default="agents/mgt_dsm_c.py"); ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    files = sorted(glob.glob(str(ROOT / "data/leader_tapes/16732748_56619023/*.json.gz")))[:a.limit]
    same = 0; gaps = []; rows = []
    for p in files:
        x = json.load(gzip.open(p, "rt"))
        dc, db = run(x)
        oc, ob = run(x, load(a.agent, x["episode"]))
        same += (ob == db); gaps.append(oc - dc); rows.append((x["episode"], oc - dc, dict(ob - db), dict(db - ob)))
    n = len(files)
    print(f"{n} worlds (own tape excluded): same day-6 crop/animal counts as DSM in {same}; dawn-6 cash vs DSM: mean {sum(gaps)/n:+.0f}, min {min(gaps):+d}, max {max(gaps):+d}")
    for r in rows[:12]:
        print("  ", r)


if __name__ == "__main__":
    main()

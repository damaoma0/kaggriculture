"""40 new random worlds against MGT (user 2026-09-29: "test out n17 and n18 on full 40 worlds random seed vs mgt"):
one game per world, seats alternating, seeds never used by the study's protocol or this thread's panels. The shops of
every world are drawn once, by the engine itself, in a game where both farms PASS all season (the shop draw shares the
RNG with weed spawning, so any pair of farms gives a valid draw); every arm is then forced onto them (fixed-shop paired
panel, --force-shops-from).

usage: build_panel40_20260929.py [--n 40]
  -> results/fresh/semantic_h2h_20260929/seeds_r40.json, shops_ref/r40/<case>.json ({"shops": [...8 names]})"""
import argparse
import json
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
sys.path.insert(0, str(ROOT / "scripts"))
from semantic_h2h_20260929 import all_seeds  # noqa: E402


def draw_shops(seed):
    from kaggle_environments import make
    env = make("kaggriculture", configuration={"episodeSteps": 720, "actTimeout": 100}, info={"seed": seed})
    env.run([lambda obs, cfg: {}, lambda obs, cfg: {}])
    shops = env.steps[-1][0]["observation"]["town"]["unlocked_shops"]
    return [s if isinstance(s, str) else s.get("name") for s in shops]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    a = ap.parse_args()
    used = set()
    for p in [H / "study/protocol.json", H / "seeds.json", H / "seeds_fresh8.json", H / "leaders_cases.json"]:
        if p.exists():
            all_seeds(json.loads(p.read_text()), used)
    seeds = []
    while len(seeds) < a.n:
        s = secrets.randbits(32)
        if s not in used and s not in seeds:
            seeds.append(s)
    cases = [dict(id=f"r40-{i:02d}-s{i % 2}", seed=s, seat=i % 2) for i, s in enumerate(seeds)]
    out = H / "shops_ref/r40"
    out.mkdir(parents=True, exist_ok=True)
    for c in cases:
        shops = draw_shops(c["seed"])
        assert len(shops) == 8, (c, shops)
        (out / f"{c['id']}.json").write_text(json.dumps(dict(case=c, shops=shops, source="PASS vs PASS engine draw")))
        print(c["id"], c["seed"], shops[:3], flush=True)
    (H / "seeds_r40.json").write_text(json.dumps(dict(
        note="40 new random worlds vs MGT, one game each, alternating seats; shops drawn by a PASS-vs-PASS game "
             "(shops_ref/r40); built 2026-09-29 before any outcome", excluded=len(used), cases=cases), indent=1))
    print(len(cases), "cases ->", H / "seeds_r40.json")


if __name__ == "__main__":
    main()

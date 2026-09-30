"""Recorded-opponent cases from current leader games, in the semantic study's recording format (user 2026-09-29: test
against someone that is not MGT but has a high rating, credibly).

A leader tape (data/leader_tapes/<team>_<submission>/<episode>.json.gz: the leader's seat, actions and the other farm's
actions, seed, recorded shops, rewards) becomes a study recording seen from the seat we replace: `seat` = the leader's
opponent's seat, `our_actions` = that opponent's recorded actions (used only by the source control, which must reproduce
both recorded cash totals), `opp_actions` = the leader's recorded actions, `shops` = the recorded shop list per day
(the engine's day // 3 schedule). The harness then plays the candidate in that seat against the leader's frozen commands
and flags games where the leader's commands fail materially more than in the control (study protocol).

usage: build_leader_recorded_20260929.py [--per-team 16] [--seed 20260929]"""
import argparse
import gzip
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"
TEAMS = {"DSM": ("data/leader_tapes/16732748_56619023", 3027.2),
         "M & M & P & Q": ("data/leader_tapes/16681125_56612150", 3039.1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-team", type=int, default=16)
    ap.add_argument("--seed", type=int, default=20260929)
    a = ap.parse_args()
    protocol = json.loads((STUDY / "protocol.json").read_text())
    used = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("seed", "episode") and isinstance(v, (int, str)):
                    used.add(str(v))
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
                if isinstance(v, (int, str)):
                    used.add(str(v))
    walk(protocol)
    rng = random.Random(a.seed)
    out_dir = STUDY / "recordings_leaders"
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = []
    for team, (folder, rating) in TEAMS.items():
        files = sorted((ROOT / folder).glob("*.json.gz"))
        rng.shuffle(files)
        n = 0
        for p in files:
            x = json.load(gzip.open(p, "rt", encoding="utf-8"))
            if str(x["episode"]) in used or str(x["seed"]) in used:
                continue
            lead = int(x["seat"])
            ours = 1 - lead
            rec = dict(episode=x["episode"], seat=ours, seed=x["seed"], names=x["names"], rewards=x["rewards"],
                       opponent=dict(team=team, index=lead, reward=x["rewards"][lead], rating=rating),
                       shops=[list(x["shops"][:min(len(x["shops"]), d // 3)]) for d in range(31)],
                       our_actions=x["opp_actions"], opp_actions=x["actions"], source=str(p.relative_to(ROOT)))
            f = out_dir / f"{x['episode']}.json.gz"
            f.write_bytes(gzip.compress(json.dumps(rec).encode(), mtime=0))
            cases.append(dict(id=f"lead-{'dsm' if team == 'DSM' else 'mmpq'}-{x['episode']}", episode=str(x["episode"]),
                              seed=x["seed"], seat=ours, file=f"recordings_leaders/{f.name}",
                              sha256=hashlib.sha256(f.read_bytes()).hexdigest(), opponent=team,
                              replaced=x["names"][ours], historical_rating=rating))
            n += 1
            if n >= a.per_team:
                break
    out = ROOT / "results/fresh/semantic_h2h_20260929/leaders_cases.json"
    out.write_text(json.dumps(dict(note="current leader games, recorded opponent = the leader; our seat replaces the "
                                        "leader's opponent", cases=cases), indent=1))
    print(len(cases), "cases ->", out, "| replaced opponents:", sorted({c["replaced"] for c in cases}))


if __name__ == "__main__":
    main()

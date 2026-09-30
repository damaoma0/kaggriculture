"""Validation cases from our live submission's ladder games (user 2026-09-29: "use a few ladder games as validation for
improvement as they come in"). A compact ladder game (scripts/ladder_panel_fetch.py: data/ladder_panel/<sub>/<ep>.json.gz,
seat = OUR seat, our_actions = our live agent, opp_actions = the real opponent, shops per day) is already in the study's
recording format; it is copied into study/recordings_ladder/ and listed in ladder_cases.json. The harness then plays a
candidate in our seat against the opponent's frozen commands (the source control replays both and must reproduce both
recorded cash totals = the live agent's real result). Re-running adds the new games.

usage: build_ladder_cases_20260929.py [--sub 56651013[,56655029...]]  (several live submissions: one combined panel)"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
STUDY = H / "study"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", default="56651013")
    a = ap.parse_args()
    out_dir = STUDY / "recordings_ladder"
    out_dir.mkdir(exist_ok=True)
    cases = []
    for p in sorted(q for sub in a.sub.split(",") for q in (ROOT / "data/ladder_panel" / sub).glob("*.json.gz")):
        x = json.load(gzip.open(p, "rt", encoding="utf-8"))
        rec = dict(episode=x["episode"], seat=int(x["seat"]), seed=int(x["seed"]), names=x["names"], rewards=x["rewards"],
                   opponent=x.get("opponent"), shops=x["shops"], our_actions=x["our_actions"], opp_actions=x["opp_actions"],
                   source=p.relative_to(ROOT).as_posix())
        dst = out_dir / p.name
        dst.write_bytes(gzip.compress(json.dumps(rec).encode(), mtime=0))
        opp = x.get("opponent") or {}
        seat = int(x["seat"])
        cases.append(dict(id=f"lad-{x['episode']}", episode=str(x["episode"]), seed=int(x["seed"]), seat=seat,
                          file=f"recordings_ladder/{p.name}", sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),
                          opponent=(opp.get("team") if isinstance(opp, dict) else None) or x["names"][1 - seat],
                          replaced=f"our live submission {a.sub}", live_margin=x["rewards"][seat] - x["rewards"][1 - seat],
                          opponent_submission=opp.get("submission") if isinstance(opp, dict) else None))
    (H / "ladder_cases.json").write_text(json.dumps(dict(note=f"ladder games of submission {a.sub} (validation)",
                                                         cases=cases), indent=1), encoding="utf-8")
    won = sum(c["live_margin"] > 0 for c in cases)
    print(f"{len(cases)} ladder cases ({won} won live) -> {H / 'ladder_cases.json'}")


if __name__ == "__main__":
    main()

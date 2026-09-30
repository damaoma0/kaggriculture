"""DSM-new (56692773, four quadrants) seat-swap cases (2026-09-30): our seat = DSM's seat, the opponent = its recorded
commands. With semantic_h2h_20260929.py run --prefix-steps 264 our seat replays DSM's own commands through day 10 (the
4th quadrant is bought and planted by DSM on day 10) and the candidate plays from day 11 hour 0 - the farm the
"opening = the leaders' tapes through day 10" handoff produces. Same recording format as study/recordings_dsmseat
(our_actions = DSM, opp_actions = the opponent, shops = 31 per-day lists).

usage: build_dsm4q_cases_20260930.py [--episodes 115561922,...] [--tapes data/leader_tapes/16732748_56692773]
  -> results/fresh/semantic_h2h_20260929/study/recordings_dsm4q/<episode>.json.gz
     results/fresh/retrain4q_20260930/dsm4q_cases.json
  then: scripts/leader_commits_20260929.py --cases results/fresh/retrain4q_20260930/dsm4q_cases.json"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results/fresh/semantic_h2h_20260929"
STUDY = H / "study"
# strongest recorded opponents (smallest DSM margins), mixed shop types and both seats
DEFAULT = "115561922,115563541,115561000,115557062,115550561,115547341"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", default=DEFAULT)
    ap.add_argument("--tapes", default="data/leader_tapes/16732748_56692773")
    ap.add_argument("--out", default="results/fresh/retrain4q_20260930/dsm4q_cases.json")
    a = ap.parse_args()
    rec_dir = STUDY / "recordings_dsm4q"
    rec_dir.mkdir(exist_ok=True)
    cases = []
    for ep in a.episodes.split(","):
        src = ROOT / a.tapes / f"{ep}.json.gz"
        t = json.load(gzip.open(src, "rt", encoding="utf-8"))
        seat = int(t["seat"])
        assert t["names"][seat] != t["names"][1 - seat], "self-play"
        shops = [list(t["shops"][:min(8, d // 3)]) for d in range(31)]
        rec = dict(episode=int(t["episode"]), seat=seat, seed=int(t["seed"]), names=t["names"], rewards=t["rewards"],
                   opponent=None, shops=shops, our_actions=t["actions"], opp_actions=t["opp_actions"],
                   source=f"{a.tapes}/{ep}.json.gz (DSM new 56692773, our seat = DSM)")
        dst = rec_dir / f"{ep}.json.gz"
        dst.write_bytes(gzip.compress(json.dumps(rec).encode(), mtime=0))
        cases.append(dict(id=f"dsm4q-{ep}", episode=str(ep), seed=int(t["seed"]), seat=seat,
                          file=f"recordings_dsm4q/{ep}.json.gz", sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),
                          opponent=t["names"][1 - seat], replaced="DSM new 56692773 (exact prefix, our seat)",
                          recorded_margin=t["rewards"][seat] - t["rewards"][1 - seat]))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(note="DSM new (4Q) seat swapped in: our seat replays DSM through the prefix "
                                        "(--prefix-steps 264 = exact day-11 start with 4 quadrants)", cases=cases), indent=1),
                   encoding="utf-8")
    for c in cases:
        print(c["id"], "seat", c["seat"], "opp", c["opponent"], "recorded margin", c["recorded_margin"])
    print(len(cases), "cases ->", out)


if __name__ == "__main__":
    main()

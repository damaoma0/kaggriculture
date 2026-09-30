"""Compact existing Mother-Goose replays for labour research; no downloads."""
import gzip
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/fresh/labour_profit/leader_panel/mother_goose"


def main():
    sample = json.loads((ROOT / "results/fresh/leader_segments/sample.json").read_text())
    rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    for entry in sample["sample"]:
        seats = [i for i, a in enumerate(entry["agents"]) if a["sub"] == 56266758]
        if not seats:
            continue
        path = ROOT / f"data/leaders_20260917/episode-{entry['id']}-replay.json"
        if not path.exists():
            continue
        seat = seats[0]
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert len(raw["steps"]) == 720
        steps = raw["steps"]
        game = dict(episode=entry["id"], seat=seat, submission=56266758,
                    seed=raw["info"]["seed"], rewards=raw["rewards"],
                    names=raw["info"].get("TeamNames"), opponent=entry["agents"][1 - seat],
                    shops=[steps[min(719, d * 24)][0]["observation"]["town"]["unlocked_shops"] for d in range(31)],
                    our_actions=[steps[t + 1][seat].get("action") or {} for t in range(719)],
                    opp_actions=[steps[t + 1][1 - seat].get("action") or {} for t in range(719)])
        target = OUT / f"{entry['id']}.json.gz"
        # Deterministic gzip headers for reproducible source fingerprints.
        payload = json.dumps(game, separators=(",", ":")).encode()
        target.write_bytes(gzip.compress(payload, mtime=0))
        rows.append(dict(episode=entry["id"], source=str(path.relative_to(ROOT)),
                         raw_sha256=sha256(path.read_bytes()).hexdigest(), compact_sha256=sha256(target.read_bytes()).hexdigest()))
    (OUT.parent / "sources.json").write_text(json.dumps(rows, indent=2))
    print(json.dumps(dict(episodes=len(rows), folder=str(OUT))))


if __name__ == "__main__":
    main()

"""Semantic-planner training rows from DSM's CURRENT submission (56619023) - the planner's rows come from DSM 56498734,
which planted melons only on days 0-1; the current version adds a 4-tile melon wave on day 6, buys its 3rd quadrant on
day 8 (never a 4th) and keeps ~7 geese (2026-09-29 leader breakdown). Same row construction as
scripts/build_semantic_strategy_modern_data_20260928.py (its functions are imported unchanged; nothing of the shared
corpus or of the other thread's outputs is written): features from the observed prefix only, labels from the day's
successful tile changes.

Excluded episodes: the study protocol's reserved recordings AND every episode of the recorded-leader panel
(results/fresh/semantic_h2h_20260929/leaders_cases.json), so the leader panels stay held out.

usage: build_semantic_rows_dsmc_20260929.py [--sem data/leader_semantics_dsmc/16732748]
       [--tapes data/leader_tapes/16732748_56619023] [--out results/fresh/semantic_h2h_20260929/models/causal_daily_rows_dsmc.json]"""
import argparse
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_semantic_strategy_modern_data_20260928 as B  # noqa: E402
from semantic_tile_inputs_20260928 import extract_game, load_executor, strict_input  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sem", default="data/leader_semantics_dsmc/16732748")
    ap.add_argument("--tapes", default="data/leader_tapes/16732748_56619023")
    ap.add_argument("--submission", type=int, default=56619023)
    ap.add_argument("--out", default="results/fresh/semantic_h2h_20260929/models/causal_daily_rows_dsmc.json")
    a = ap.parse_args()
    started = time.perf_counter()
    reserved, _ = B.exclusions(B.read(B.OUT / "protocol.json"), "")
    panel = {int(c["episode"]) for c in json.loads((ROOT / "results/fresh/semantic_h2h_20260929/leaders_cases.json")
                                                     .read_text())["cases"]}
    excluded = reserved | panel
    executor = load_executor()
    rows, sources, skipped = [], [], []
    for path in sorted((ROOT / a.sem).glob("*.json.gz")):
        sem = B.read(path)
        episode, seat = int(sem["meta"]["episode"]), int(sem["meta"]["seat"])
        if episode in excluded:
            skipped.append(episode)
            continue
        tape = B.read(ROOT / a.tapes / path.name)
        assert (episode, seat) == (int(tape["episode"]), int(tape["seat"]))
        assert sem["meta"]["cash_match"] and len(sem["days"]) == 30
        exact = executor.TilePlanView(executor.Target(sem)).to_dict()
        strict = strict_input(extract_game(sem, exact)[0])
        meta = dict(episode=episode, seat=seat, submission=a.submission, family="DSM", source=path.relative_to(ROOT).as_posix(),
                    source_format="compact_semantics")
        for day in range(6, 30):
            observed = [s["shop"] for s in sem["shops"] if int(s["reveal_day"]) <= day]
            features = B.features_from_prefix(sem["days"][:day], sem["days"][day]["board"], sem["days"][day]["cash_start"],
                                              observed)
            B.check_features(features, sem, exact, day)
            target = deepcopy(strict["days"][day])
            target.pop("day")
            end = target.pop("end_occupancy_counts")
            target["end_crop_counts"] = end["crops"] if end else None
            target["end_animal_counts"] = end["animals"] if end else None
            target["owned_quadrants"] = [q for q in ("NW", "NE", "SW", "SE") if q == "NW" or exact["land_day"].get(q, 99) <= day]
            rows.append(dict(meta=meta.copy(), day=day, features=features, target=target, row_id=len(rows)))
        sources.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=B.sha(path)))
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = dict(schema_version=1, feature_time="start of day before any current-day action",
               label_time="successful current-day tile changes and observed two-night retirement",
               excluded_episodes=sorted(excluded), training_games=len({r["meta"]["episode"] for r in rows}),
               training_seats=len(sources), rows=rows, sources=sources,
               note="DSM 56619023 rows (2026-09-29); leader-panel episodes and protocol reserves excluded")
    out.write_text(json.dumps(doc), encoding="utf-8")
    print(json.dumps(dict(rows=len(rows), games=doc["training_games"], skipped=len(skipped),
                          seconds=round(time.perf_counter() - started, 1), out=str(out))))


if __name__ == "__main__":
    main()

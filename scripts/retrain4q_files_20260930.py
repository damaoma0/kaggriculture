"""4-quadrant (4Q) retraining helpers (2026-09-30). Writes patched copies of frozen-candidate files for
scripts/sem_arms_20260929.py make ... --add-file SRC:DEST (the frozen candidates themselves are never edited).

  entry_keep_policy_land   agents/semantic_strategy_20260928.py of a base candidate + the default-off option
                           config cassette.keep_policy_land: on the cassette days (6..until_day-1) the cassette row
                           used to OVERWRITE the policy's target_land_count with DSM-old's land count (3 on days 10-11),
                           so policy.land_by_day {"4": 10} (sem_arms --land-gate) only took effect on day 12 (n18rc244d:
                           4th quadrant bought day 12 hour 2). With keep_policy_land the cassette keeps the larger of its
                           row's land and the policy's own target (which already respects land_limit and one quadrant a
                           day). Without the option the entry behaves exactly as before.

  merge_rows               several causal_daily_rows files (scripts/build_semantic_rows_dsmc_20260929.py outputs, e.g.
                           one per 4Q leader team) -> one rows file for scripts/build_semantic_block_model_20260928.py
                           (a pooled block model); rows are renumbered, sources concatenated.

usage: retrain4q_files_20260930.py entry_keep_policy_land [--base n18rc223d]
       -> results/fresh/retrain4q_20260930/files/semantic_strategy_20260928.<base>.keep_policy_land.py
       retrain4q_files_20260930.py merge_rows --rows A.json,B.json,... --out POOLED.json"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "results/fresh/semantic_h2h_20260929/study"
OUT = ROOT / "results/fresh/retrain4q_20260930/files"


def keep_policy_land(src):
    old = '''    owned = len(farm.get("unlocked_quadrants") or ["NW"])
    today = proposal["today"]
    today.update(plant_counts={k: v for k, v in plants.items() if v}, animal_add_counts={k: v for k, v in adds.items() if v},
                 animal_retire_counts={}, hands=int(row["hands"]), target_land_count=max(owned, int(row["land"])),
                 land_add_count=max(0, int(row["land"]) - owned),'''
    new = '''    owned = len(farm.get("unlocked_quadrants") or ["NW"])
    today = proposal["today"]
    land_ = int(row["land"])
    if cfg.get("keep_policy_land"):                # research option (2026-09-30, default off): the policy's own land
        # target (e.g. policy.land_by_day {"4": 10}) survives the cassette row (DSM-old rows say 3 on days 10-11)
        land_ = max(land_, int(today.get("target_land_count", owned) or owned))
    today.update(plant_counts={k: v for k, v in plants.items() if v}, animal_add_counts={k: v for k, v in adds.items() if v},
                 animal_retire_counts={}, hands=int(row["hands"]), target_land_count=max(owned, land_),
                 land_add_count=max(0, land_ - owned),'''
    if "keep_policy_land" in src:
        return src
    assert src.count(old) == 1, "anchor not found"
    return src.replace(old, new)


def merge_rows(paths, out):
    rows, sources, excluded, notes = [], [], set(), []
    for p in paths:
        doc = json.loads((ROOT / p).read_text(encoding="utf-8"))
        for r in doc["rows"]:
            r = dict(r, row_id=len(rows))
            rows.append(r)
        sources += doc.get("sources", [])
        excluded |= set(doc.get("excluded_episodes", []))
        notes.append(f"{p}: {doc.get('training_games')} games")
    keys = {(int(r["meta"]["episode"]), int(r["meta"]["seat"])) for r in rows}
    doc = dict(schema_version=1, feature_time="start of day before any current-day action",
               label_time="successful current-day tile changes and observed two-night retirement",
               excluded_episodes=sorted(excluded), training_games=len({e for e, _ in keys}), training_seats=len(keys),
               rows=rows, sources=sources, note="pooled 4Q leader rows (2026-09-30): " + "; ".join(notes))
    (ROOT / out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / out).write_text(json.dumps(doc), encoding="utf-8")
    print(json.dumps(dict(rows=len(rows), seats=len(keys), out=out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("entry_keep_policy_land", "merge_rows"))
    ap.add_argument("--base", default="n18rc223d")
    ap.add_argument("--rows", help="merge_rows: comma-separated repo-relative rows files")
    ap.add_argument("--out", help="merge_rows: repo-relative output file")
    a = ap.parse_args()
    if a.what == "merge_rows":
        merge_rows(a.rows.split(","), a.out)
        return
    OUT.mkdir(parents=True, exist_ok=True)
    if a.what == "entry_keep_policy_land":
        src = (STUDY / "candidates" / a.base / "project/agents/semantic_strategy_20260928.py").read_text(encoding="utf-8")
        dst = OUT / f"semantic_strategy_20260928.{a.base}.keep_policy_land.py"
        dst.write_text(keep_policy_land(src), encoding="utf-8", newline="\n")
        print(dst.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()

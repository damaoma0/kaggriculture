"""Read-only coverage audit for own m1 worlds versus 584 compact UMG tapes."""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "fresh" / "shop_prefix_predictability"
DAYS = (3, 6, 9, 12, 15, 18, 21, 24)
CHECKPOINTS = (12, 15, 18, 21, 24)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def coverage(shops, tape_sets):
    ordered, unordered = {}, {}
    for x, day in enumerate(DAYS, 1):
        # Compact tapes store a 31-day schedule; smoke rows store only the
        # final flat ordered eight-shop list.
        seq = tuple(shops[day]) if len(shops) > 8 else tuple(shops[:x])
        ordered[x] = seq in tape_sets["ordered"][x]
        unordered[x] = tuple(sorted(seq)) in tape_sets["unordered"][x]
    first_missing = next((3 * x for x in range(1, 9) if not ordered[x]), None)
    longest = 8 if first_missing is None else (first_missing // 3) - 1
    return ordered, unordered, longest, first_missing


def group_summary(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    out = {}
    for name, rs in sorted(groups.items(), key=lambda z: str(z[0])):
        margins = [r["margin"] for r in rs]
        out[str(name)] = dict(n=len(rs), wins=sum(x > 0 for x in margins), ties=sum(x == 0 for x in margins),
                               losses=sum(x < 0 for x in margins), mean_margin=sum(margins) / len(margins))
    return out


def main():
    tape_sets = {"ordered": defaultdict(set), "unordered": defaultdict(set)}
    for sub in ("56266758", "56266899"):
        for path in sorted((ROOT / "data" / "mg_tapes" / sub).glob("*.json.gz")):
            tape = load_gz(path)
            for x, day in enumerate(DAYS, 1):
                seq = tuple(tape["shops"][day])
                tape_sets["ordered"][x].add(seq)
                tape_sets["unordered"][x].add(tuple(sorted(seq)))

    dataset = read(ROOT / "results" / "fresh" / "tape_gap_plans" / "dataset_primary.json")
    games = {int(g["episode"]): g for g in dataset["games"]}
    game_rows = []
    for game in dataset["games"]:
        # Both seats in one episode share the public shop path; keep each
        # recorded own seat because rewards/margins are seat-specific.
        shops = game["checkpoints"]["12"]["observation"]["town"]["unlocked_shops"]
        # The checkpoint contains only the first four shops, so recover the
        # complete recorded path from the compact own tape.
        compact = load_gz(ROOT / "data" / "ladder_panel" / "56395605" / f"{game['episode']}.json.gz")
        ordered, unordered, longest, first_missing = coverage(compact["shops"], tape_sets)
        reward = game.get("rewards") or compact["rewards"]
        margin = float(reward[int(game["seat"])] - reward[1 - int(game["seat"])])
        game_rows.append(dict(episode=int(game["episode"]), seat=int(game["seat"]), ordered=ordered,
                              unordered=unordered, longest_ordered_prefix=longest, first_missing_day=first_missing,
                              margin=margin))

    # Rank-1 rows are selected using the frozen compact candidate ranking;
    # outcome is joined only after selection for descriptive grouping.
    candidates = read(ROOT / "results" / "fresh" / "tape_gap_plans" / "primary_candidates.json")["candidates"]
    rank1 = [c for c in candidates if c["rank"] == 1]
    outcomes = {(r["episode"], r["seat"]): r["margin"] for r in game_rows}
    selected = []
    for c in rank1:
        t = c["target"]
        key = (int(t["episode"]), int(t["seat"]))
        comp = c["difference_components"]
        replacement = float(comp["shop_replacement_count"])
        asset = float(comp["asset_count_l1_half"])
        state_bucket = "shop_exact" if replacement == 0 else ("shop_1" if replacement <= 1 else "shop_2plus")
        cohort_bucket = "asset_0" if asset == 0 else ("asset_0to2" if asset <= 2 else "asset_gt2")
        selected.append(dict(episode=key[0], seat=key[1], day=int(t["day"]), margin=outcomes[key],
                             state_distance=[replacement, asset, int(comp["crop_animal_tile_label_mismatch"])],
                             state_bucket=state_bucket, cohort_bucket=cohort_bucket))

    break_groups = {}
    for bucket, pred in (("<=D9", lambda d: d is not None and d <= 9),
                         ("D12", lambda d: d == 12), ("D15+", lambda d: d is not None and d >= 15),
                         ("never_missing", lambda d: d is None)):
        break_groups[bucket] = group_summary([r for r in game_rows if pred(r["first_missing_day"])], "first_missing_day")
        # Flatten the bucket summary into a stable single row as well.
        rs = [r for r in game_rows if pred(r["first_missing_day"])]
        ms = [r["margin"] for r in rs]
        break_groups[bucket]["overall"] = dict(n=len(rs), wins=sum(x > 0 for x in ms), ties=sum(x == 0 for x in ms),
                                                losses=sum(x < 0 for x in ms), mean_margin=(sum(ms) / len(ms) if ms else None))

    v56 = None
    smoke = ROOT / "results" / "fresh" / "tape_gap_plans" / "v56_baseline_smoke" / "summary.json"
    if smoke.exists():
        sr = read(smoke)
        v56rows = []
        for r in sr["rows"]:
            ordered, unordered, longest, first_missing = coverage(r["shops"], tape_sets)
            v56rows.append(dict(seed=r["seed"], seat=r["seat"], ordered=ordered, unordered=unordered,
                                longest_ordered_prefix=longest, first_missing_day=first_missing))
        v56 = dict(games=len(v56rows), rows=v56rows,
                   missing_by_x={str(x): sum(not r["ordered"][x] for r in v56rows) for x in range(1, 9)})

    result = dict(schema_version=1, source="86 verified m1 replay seats versus 584 compact UMG tapes",
                  tape_counts={"56266758": 310, "56266899": 274, "total": 584},
                  own_games=len(game_rows), observed_rates={
                      "ordered_by_x": {str(x): sum(r["ordered"][x] for r in game_rows) / len(game_rows) for x in range(1, 9)},
                      "unordered_by_x": {str(x): sum(r["unordered"][x] for r in game_rows) / len(game_rows) for x in range(1, 9)},
                  },
                  counts_by_x={str(x): {"ordered_available": sum(r["ordered"][x] for r in game_rows),
                                       "unordered_available": sum(r["unordered"][x] for r in game_rows), "n": len(game_rows)} for x in range(1, 9)},
                  first_break={"counts": dict(Counter(str(r["first_missing_day"]) if r["first_missing_day"] is not None else "never" for r in game_rows)),
                               "longest_prefix_counts": dict(Counter(str(r["longest_ordered_prefix"]) for r in game_rows)),
                               "outcome_groups": break_groups},
                  nearest_rank1={"n": len(selected), "by_state_bucket": group_summary(selected, "state_bucket"),
                                 "by_cohort_bucket": group_summary(selected, "cohort_bucket"),
                                 "note":"Outcome joined after frozen rank-1 selection; descriptive association only."},
                  v56_smoke=v56,
                  qualification_note="This is not the qualification 128-world protocol. The original 64 UMG-tape worlds are known-path controls, not gap stress. New untaped quota should require first break by D12, exclude exact-prefix worlds beyond D12, stratify shop compositions, and log actual candidate activation.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "coverage.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"own_games": len(game_rows), "observed_rates": result["observed_rates"], "first_break_counts": result["first_break"]["counts"], "v56": v56}, indent=2))


if __name__ == "__main__":
    main()

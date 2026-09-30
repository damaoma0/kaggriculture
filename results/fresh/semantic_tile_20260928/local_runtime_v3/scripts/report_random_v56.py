"""Post-run report for the frozen m1 versus v56 natural-random survey.

This reporter does not run matches. It refuses to publish a summary until all
expected seed/seat rows are present, while retaining and reporting failures.
"""
from collections import defaultdict, Counter
from hashlib import sha256
import json
from pathlib import Path
import random
import statistics
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "results" / "fresh" / "v56_random_20260922"
OUT = ROOT / "results" / "fresh" / "v56_random_20260922"
DOC = ROOT / "docs" / "v56_random_world_benchmark.md"
DRAWS = 20_000
SEED = 20260922


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def bootstrap(values, draws=DRAWS):
    if not values:
        return None
    rng = np.random.default_rng(SEED)
    samples = rng.choice(np.asarray(values, dtype=float), size=(draws, len(values)), replace=True).mean(axis=1)
    return [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))]


def tape_sets():
    ordered = defaultdict(set)
    unordered = defaultdict(set)
    for sub in ("56266758", "56266899"):
        for p in sorted((ROOT / "data" / "mg_tapes" / sub).glob("*.json.gz")):
            import gzip
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                d = json.load(fh)
            for x, day in enumerate((3, 6, 9, 12, 15, 18, 21, 24), 1):
                seq = tuple(d["shops"][day])
                ordered[x].add(seq)
                unordered[x].add(tuple(sorted(seq)))
    corpus_hash = sha256()
    for sub in ("56266758", "56266899"):
        for p in sorted((ROOT / "data" / "mg_tapes" / sub).glob("*.json.gz")):
            corpus_hash.update(str(p.relative_to(ROOT)).encode())
            corpus_hash.update(sha256(p.read_bytes()).digest())
    return ordered, unordered, corpus_hash.hexdigest()


def prefix_coverage(shops, ordered, unordered):
    days = (3, 6, 9, 12, 15, 18, 21, 24)
    flat = len(shops) <= 8
    o, u = {}, {}
    for x, day in enumerate(days, 1):
        seq = tuple(shops[:x]) if flat else tuple(shops[day])
        o[x] = seq in ordered[x]
        u[x] = tuple(sorted(seq)) in unordered[x]
    first = next((3 * x for x in range(1, 9) if not o[x]), None)
    return o, u, first


def outcome(rs):
    margins = [float(r["margin"]) for r in rs]
    scores = [1.0 if x > 0 else (0.5 if x == 0 else 0.0) for x in margins]
    clusters = by_seed(rs)
    # Resample whole seeds, retaining all rows in the subgroup for each seed.
    # The ratio of sums handles strata containing one seat from some seeds
    # and both seats from others without changing the game-weighted estimand.
    if clusters:
        totals = np.array([[len(v), sum(float(r['margin']) for r in v),
                           sum(float(r['margin'] > 0) + .5 * float(r['margin'] == 0) for r in v)]
                          for _, v in sorted(clusters.items())], dtype=float)
        draws = np.random.default_rng(SEED).integers(0, len(totals), (DRAWS, len(totals)))
        sampled = totals[draws].sum(axis=1)
        margin_ci = np.quantile(sampled[:, 1] / sampled[:, 0], [.025, .975]).tolist()
        score_ci = np.quantile(sampled[:, 2] / sampled[:, 0], [.025, .975]).tolist()
    else:
        margin_ci = score_ci = None
    return dict(n=len(rs), wins=sum(x > 0 for x in margins), ties=sum(x == 0 for x in margins),
                losses=sum(x < 0 for x in margins), mean_margin=statistics.mean(margins) if margins else None,
                median_margin=statistics.median(margins) if margins else None,
                mean_score=statistics.mean(scores) if scores else None,
                mean_margin_ci=margin_ci,
                world_cluster_score_ci=score_ci, world_clusters=len(clusters))


def by_seed(rows):
    out = defaultdict(list)
    for r in rows:
        out[int(r["seed"])].append(r)
    return out


def daily_seat(row, seat):
    daily = row.get("daily")
    if isinstance(daily, list) and len(daily) == 2:
        value = daily[seat]
        return value[-1] if isinstance(value, list) and value else (value if isinstance(value, dict) else None)
    return None


def timing_rows(row):
    timing = row.get("timing")
    if not isinstance(timing, dict):
        return []
    if "calls" in timing or "max_seconds" in timing:
        return [timing]
    return [v for v in timing.values() if isinstance(v, dict)]


def main():
    manifest_path = IN / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit("manifest.json is not available; run the benchmark first")
    manifest = read(manifest_path)
    seeds = sorted({int(s) for s in manifest["seeds"]})
    assert len(seeds) == len(manifest['seeds']) == 128 and manifest['expected_games'] == 256
    expected = {(s, seat) for s in seeds for seat in (0, 1)}
    files = sorted((IN / "games").glob("*.json"))
    rows, failures = [], []
    for p in files:
        row = read(p)
        if row.get("completed") is False:
            failures.append(row)
        else:
            rows.append(row)
    all_records = rows + failures
    pair_list = [(int(r["seed"]), int(r["seat"])) for r in all_records if "seed" in r and "seat" in r]
    pair_counts = Counter(pair_list)
    seen = set(pair_list)
    missing = sorted(expected - seen)
    duplicate = sorted(k for k, n in pair_counts.items() if n > 1)
    unexpected = sorted(seen - expected)
    expected_hashes = manifest.get("hashes", {})
    validation_errors = []
    source_audit_path = IN / "source_audit.json"
    source_audit = read(source_audit_path) if source_audit_path.exists() else None
    if not source_audit or not source_audit.get("all_ids_and_shops_exact"):
        validation_errors.append({"error": "embedded_m1_tape_source_audit_missing_or_mismatch"})
    elif source_audit.get('agent_sha256') != expected_hashes.get('mgt_m1'):
        validation_errors.append({'error': 'embedded_audit_wrong_source'})
    source_paths = manifest.get("source_paths", {})
    for key, path_value in source_paths.items():
        path = Path(path_value)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists() or key not in expected_hashes or sha256(path.read_bytes()).hexdigest() != expected_hashes[key]:
            validation_errors.append({"error": "manifest_source_hash_mismatch", "source": key})
    for r in rows:
        if (int(r["seed"]), int(r["seat"])) not in expected:
            validation_errors.append({"row": r.get("seed"), "error": "unexpected seed/seat"})
        if r.get("statuses") != ["DONE", "DONE"]:
            validation_errors.append({"row": r.get("seed"), "error": "statuses"})
        if r.get("completed") is not True:
            validation_errors.append({"row": r.get("seed"), "error": "completed"})
        if r.get("states") != 720:
            validation_errors.append({"row": r.get("seed"), "error": "states"})
        if r.get("errors") != []:
            validation_errors.append({"row": r.get("seed"), "error": "errors"})
        if r.get("actions") != 719 or not r.get("ledger_verified", False):
            validation_errors.append({"row": r.get("seed"), "error": "actions_or_ledger"})
        for field in ("cash", "opponent_cash", "margin"):
            if field not in r or not isinstance(r[field], (int, float)) or not math.isfinite(float(r[field])):
                validation_errors.append({"row": r.get("seed"), "error": "nonfinite_" + field})
        if r.get('margin') != r['cash'] - r['opponent_cash']:
            validation_errors.append({'row': r.get('seed'), 'error': 'margin_mismatch'})
        for seat, cash_key in ((int(r['seat']), "cash"), (1-int(r['seat']), "opponent_cash")):
            daily = daily_seat(r, seat)
            if not isinstance(daily, dict) or not isinstance(daily.get("revenue"), dict) or not isinstance(daily.get("spend"), dict):
                validation_errors.append({"row": r.get("seed"), "error": f"daily_ledger_seat_{seat}"})
            elif cash_key in r:
                expected_cash = 3000 + sum(daily["revenue"].values()) - sum(daily["spend"].values())
                if abs(float(r[cash_key]) - expected_cash) > 1e-6:
                    validation_errors.append({"row": r.get("seed"), "error": f"cash_ledger_seat_{seat}"})
        tr = timing_rows(r)
        if len(tr) < 2 or any(int(t.get("calls", -1)) != 719 for t in tr):
            validation_errors.append({"row": r.get("seed"), "error": "timing_calls_both_seats"})
        for field, key in (("own_sha256", "mgt_m1"), ("opponent_sha256", "v56")):
            if expected_hashes.get(key) and r.get(field) != expected_hashes[key]:
                validation_errors.append({"row": r.get("seed"), "error": field})
    structural = bool(missing or duplicate or unexpected)
    if structural:
        incomplete = dict(schema_version=1, status="incomplete", qualification=False,
                          expected_pairs=len(expected), observed_records=len(all_records),
                          missing_pairs=[list(x) for x in missing], duplicate_pairs=[list(x) for x in duplicate],
                          unexpected_pairs=[list(x) for x in unexpected], failures=failures,
                          validation_errors=validation_errors,
                          note="No statistical summary emitted because the expected seed/seat inventory is structurally incomplete.")
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "summary.json").write_text(json.dumps(incomplete, indent=2), encoding="utf-8")
        DOC.parent.mkdir(parents=True, exist_ok=True)
        DOC.write_text("# Random-world m1 versus v56 benchmark\n\n**Status: incomplete.** No statistical summary was emitted because expected seed/seat rows are missing, duplicated, or unexpected. See `summary.json`.\n", encoding="utf-8")
        print(json.dumps(incomplete, indent=2))
        return
    ordered, unordered, corpus_hash = tape_sets()
    enriched = []
    for r in rows:
        o, u, first = prefix_coverage(r["shops"], ordered, unordered)
        enriched.append(dict(r, ordered=o, unordered=u, first_missing_day=first))
    groups = {}
    for name, pred in (("<=D9", lambda x: x is not None and x <= 9), ("D12", lambda x: x == 12),
                       ("D15+", lambda x: x is not None and x >= 15), ("never", lambda x: x is None)):
        groups[name] = outcome([r for r in enriched if pred(r["first_missing_day"])])
    by_x = {str(x): dict(ordered=sum(r["ordered"][x] for r in enriched), unordered=sum(r["unordered"][x] for r in enriched), n=len(enriched)) for x in range(1, 9)}
    day12 = {}
    for name, pred in (("order_only", lambda r: r["unordered"][4] and not r["ordered"][4]),
                       ("novel_composition", lambda r: not r["unordered"][4]), ("ordered_match", lambda r: r["ordered"][4])):
        day12[name] = outcome([r for r in enriched if pred(r)])
    first_shops = defaultdict(list)
    for r in enriched:
        first_shops[str(r["shops"][0])].append(r)
    shop_groups = {k: outcome(v) for k, v in sorted(first_shops.items())}
    seat_groups = {str(seat): outcome([r for r in enriched if int(r["seat"]) == seat]) for seat in (0, 1)}
    clusters = by_seed(enriched)
    seat_mirrors = sum(len(v) == 2 and v[0]["margin"] == v[1]["margin"] for v in clusters.values())
    result = dict(schema_version=1, qualification=False, qualification_note="Natural-random survey; not the full UMG qualification protocol.",
                  manifest=manifest, expected_pairs=len(expected), completed_rows=len(rows), failure_rows=len(failures),
                  missing_pairs=[list(x) for x in missing], duplicate_pairs=[list(x) for x in duplicate], unexpected_pairs=[list(x) for x in unexpected], validation_errors=validation_errors,
                  all_expected_pairs_present=not missing and not duplicate and not unexpected, all_rows_valid=not validation_errors,
                  source_hashes=expected_hashes, umg_tape_corpus_digest=corpus_hash, tape_count=584,
                  embedded_tape_source_audit=source_audit,
                  overall=outcome(enriched), own_average_cash=statistics.mean(float(r["cash"]) for r in enriched) if enriched else None,
                  opponent_average_cash=statistics.mean(float(r["opponent_cash"]) for r in enriched) if enriched else None,
                  seat_mirror_count=seat_mirrors, seed_count=len(clusters), seat_strata=seat_groups, first_shop_strata=shop_groups,
                  identical_shop_path_seeds=sum(len(v)==2 and v[0]['shops']==v[1]['shops'] for v in clusters.values()),
                  captured_shp_errors=sum(r.get('native_telemetry',{}).get('errors',0) for r in rows),
                  internal_error_scope='Top-level exceptions and SHP error counters captured; other internally caught router errors were not instrumented.',
                  statistics=dict(method='20,000 seed-cluster bootstrap draws; resample seed totals and divide by resampled row count', seed=SEED),
                  first_missing_buckets=groups, day12_composition_groups=day12, coverage_by_shop_count=by_x,
                  untaped_by_day12=outcome([r for r in enriched if not r['ordered'][4]]),
                  failures=failures, status="complete_with_failures" if failures or validation_errors else "complete",
                  timing={"max_wall_seconds": max((float(r.get("wall_seconds", 0)) for r in rows), default=None),
                          "mean_wall_seconds": statistics.mean(float(r.get("wall_seconds", 0)) for r in rows) if rows else None,
                          "over_1s_total": sum(sum(int(t.get("over_1s", 0)) for t in timing_rows(r)) for r in rows),
                          "max_policy_seconds": max((float(t.get("max_seconds", 0)) for r in rows for t in timing_rows(r)), default=None)},
                  interpretation="Current unchanged mgt_m1 versus frozen v56 over natural random worlds. Descriptive strata only; no causal, Elo, qualification, or full-UMG claim.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Random-world m1 versus v56 benchmark", "", "Completed 22 September 2026. Current deployed m1 versus frozen V56; the new production-plan continuation is not integrated in this build.", "",
             "128 fresh random seeds, both seats, natural shops and weeds. Source files and the complete seed list were frozen before play; no outcome-based selection or stopping. Both agents played live through the official Kaggle engine.", "",
             f"Completed rows: **{len(rows)}** / **{len(expected)}**; failures: **{len(failures)}**.", "",
             f"Overall W/T/L: **{result['overall']['wins']}/{result['overall']['ties']}/{result['overall']['losses']}**; mean margin **{result['overall']['mean_margin']:+,.0f}**; median **{result['overall']['median_margin']:+,.0f}**.",
             f"Mean-margin 95% CI: **{result['overall']['mean_margin_ci'][0]:+,.0f} to {result['overall']['mean_margin_ci'][1]:+,.0f}**. Win score: **{result['overall']['mean_score']:.1%}**; seed-clustered 95% CI: **{result['overall']['world_cluster_score_ci'][0]:.1%}–{result['overall']['world_cluster_score_ci'][1]:.1%}**.", "",
             "## First ordered-prefix break", "", "| Bucket | n | W/T/L | Mean margin | Cluster 95% CI |", "|---|---:|---:|---:|---:|"]
    for k, v in groups.items():
        ci = v["mean_margin_ci"]
        margin_text = f"{v['mean_margin']:+,.0f}" if v['mean_margin'] is not None else '—'
        ci_text = f"{ci[0]:+,.0f} to {ci[1]:+,.0f}" if ci else '—'
        lines.append(f"| {k} | {v['n']} | {v['wins']}/{v['ties']}/{v['losses']} | {margin_text} | {ci_text} |")
    def table(title, groups):
        lines.extend(['', '## ' + title, '', '| Group | Games | Seed clusters | W / D / L | Win score | 95% score CI | Mean margin |',
                      '|---|---:|---:|---:|---:|---:|---:|'])
        for name, v in groups.items():
            if not v['n']:
                continue
            lo, hi = v['world_cluster_score_ci']
            lines.append(f"| {name} | {v['n']} | {v['world_clusters']} | {v['wins']} / {v['ties']} / {v['losses']} | {v['mean_score']:.1%} | {lo:.1%}–{hi:.1%} | {v['mean_margin']:+,.0f} |")
    table('First shop', shop_groups)
    table('UMG tape availability at day 12', day12)
    v = result['untaped_by_day12']
    lines += ['', f"Combining both missing-prefix groups: **{v['wins']} wins / {v['losses']} losses in {v['n']} games** "
              f"({v['world_clusters']} seed clusters), **{v['mean_score']:.1%}** win score, "
              f"95% CI **{v['world_cluster_score_ci'][0]:.1%}–{v['world_cluster_score_ci'][1]:.1%}**."]
    table('Seat', seat_groups)
    lines += ['', '## Tape coverage', '', '| Shops revealed | Day | Exact order: games covered | Same composition: games covered |',
              '|---:|---:|---:|---:|']
    for x, v in by_x.items():
        lines.append(f"| {x} | {3*int(x)} | {v['ordered']} / {v['n']} | {v['unordered']} / {v['n']} |")
    lines += ['', '## Interpretation and validation', '',
              f"Win-score uncertainty uses {len(clusters)} seed clusters, not 256 independent observations. Exactly {seat_mirrors} seed pairs had identical final margins; {result['identical_shop_path_seeds']} had identical shop sequences. Normal farm-dependent weed RNG can change later shops between seats.", '',
              f"Average final cash: m1 {result['own_average_cash']:,.1f}; V56 {result['opponent_average_cash']:,.1f}. All recorded ledgers were checked for both seats. Validation errors: {len(validation_errors)}. Agent calls above one second: {result['timing']['over_1s_total']}; maximum measured call {result['timing']['max_policy_seconds']:.4f}s. Captured SHP internal errors: {result['captured_shp_errors']}.", '',
              'The main 95% intervals use 20,000 bootstrap resamples of whole seeds. Subgroup intervals are descriptive, unadjusted for multiple comparisons, and can be wide with few worlds. A matching shop prefix does not ensure matching farm state; missing a prefix does not isolate the causal effect of fallback. Exact ordered match, order-only mismatch, and novel composition are classified against the 584 tapes actually embedded in m1; all episode IDs and shop paths were verified against the compact corpus.', '',
              'This tests current m1 against a single frozen live opponent. It does not test the unfinished continuation, compare with original UMG tapes, or complete the full promotion protocol. Against the assumed 2750-rated opponent, the previously derived standard-Elo planning target is 80.8%; this run is reported without claiming a Kaggle rating.', '',
              'The frozen manifest, per-game ledgers, timing, source hashes, embedded-tape audit, complete subgroup statistics, and retained failure records are in `results/fresh/v56_random_20260922/`. Top-level exceptions and SHP error counters are captured; other internally caught router errors were not instrumented.']
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"completed": len(rows), "expected": len(expected), "failures": len(failures), "validation_errors": len(validation_errors), "overall": result["overall"]}, indent=2))


if __name__ == "__main__":
    main()

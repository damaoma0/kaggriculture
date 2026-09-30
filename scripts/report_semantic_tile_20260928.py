"""Paired DSM40 evaluation of semantic tiling on the frozen KB115LT executor.

Example:
  python scripts/report_semantic_tile_20260928.py --roots <exact-run> <candidate-run>
    --baseline ST28EXACT --candidates ST28COHORT,ST28REUSE --panel <panel40.txt>
    --development-panel <panel8.txt> --stage full40 --out <report-directory>

Searches only sector/multi/<arm>/<episode>.json, with neighboring ledgers.  The
competitive statistic is our cash minus the responsive-price recorded rival's
cash, paired by the same world.  The one-sided regression test has H1 mean delta
< 0; failure to reject does NOT establish equivalence or noninferiority.  The
requested gate is >=20 wins on all40 AND no significant regression at alpha=.05.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats


def read_panel(path):
    if path is None:
        return None
    text = Path(path).read_text(encoding="utf-8-sig").replace("\n", ",")
    return [g.strip().split(":")[-1] for g in text.split(",") if g.strip()]


def wilson(wins, n, alpha=.05):
    if not n:
        return [None, None]
    z = float(stats.norm.ppf(1 - alpha / 2))
    p = wins / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    width = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [center - width, center + width]


def summarize(values, seed=20260928, draws=20000):
    """Deterministic world-paired bootstrap, t CI and one-sided lower-tail test."""
    a = np.asarray(values, dtype=float)
    n = len(a)
    if not n:
        return dict(n=0, mean=None, bootstrap95=None, t95=None,
                    regression_p_one_sided=None, significantly_worse=None)
    avg = float(a.mean())
    rng = np.random.default_rng(seed)
    means = np.empty(draws)
    for lo in range(0, draws, 2048):
        hi = min(draws, lo + 2048)
        means[lo:hi] = a[rng.integers(0, n, size=(hi - lo, n))].mean(axis=1)
    ci_boot = [float(v) for v in np.quantile(means, [.025, .975])]
    if n < 2:
        ci_t, p, t_value, se = None, None, None, None
    else:
        se = float(a.std(ddof=1) / math.sqrt(n))
        if se == 0:
            ci_t, p, t_value = [avg, avg], (0.0 if avg < 0 else 1.0), None
        else:
            t_value = avg / se
            p = float(stats.t.cdf(t_value, n - 1))
            half = float(stats.t.ppf(.975, n - 1)) * se
            ci_t = [avg - half, avg + half]
    return dict(n=n, mean=avg, median=float(np.median(a)), minimum=float(a.min()),
                maximum=float(a.max()), bootstrap95=ci_boot, bootstrap_draws=draws,
                bootstrap_seed=seed, t95=ci_t, standard_error=se, t_statistic=t_value,
                regression_p_one_sided=p, significantly_worse=None if p is None else p < .05,
                improved=int((a > .5).sum()), unchanged=int((np.abs(a) <= .5).sum()),
                worse=int((a < -.5).sum()))


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _numeric_counter(value):
    return Counter({str(k): float(v) for k, v in (value or {}).items()
                    if isinstance(v, (int, float)) and v != 0})


def load_world(path):
    raw = _json(path)
    money = raw.get("money") or {}
    days_present = sorted(int(d) for d in money)
    final = money.get("30")
    # An incomplete game stays in the integrity report, never becomes a 30-day result.
    complete = final is not None and all(str(d) in money for d in range(11, 31))
    if final is None:
        final = money[str(max(days_present))] if days_present else [None, None]
    ep, arm = str(raw.get("episode", path.stem)), raw.get("arm", path.parent.name)
    tier = raw.get("tier_err") or {}
    leak_max = Counter()
    for info in (raw.get("tier_days") or {}).values():
        # These are cumulative agent counters copied into each day's log.
        leak_max |= _numeric_counter(info.get("tp_leak"))
    ledger_path = None
    for ancestor in path.parents:
        possible = ancestor / "ledgers" / arm / f"{ep}.json"
        if possible.exists():
            ledger_path = possible
            break
    ledger = _json(ledger_path) if ledger_path else None
    errors = int(tier.get("errors") or 0)
    runtime_bank = tier.get("bank_used")
    info = dict(episode=ep, arm=arm, result_path=str(path.resolve()),
                ledger_path=str(ledger_path.resolve()) if ledger_path else None,
                complete=complete, reported_money_series_complete=complete,
                completion_issues=[] if complete else ["missing day30 or daily money series"],
                observed_daily_cash_complete=None, ours=final[0], rival=final[1],
                margin=None if None in final else float(final[0]) - float(final[1]),
                executor_errors=errors, last_error=tier.get("last_error"),
                tp_leak=dict(leak_max), runtime_bank_used=runtime_bank,
                steps_over_1s=tier.get("steps_over_1s"),
                bank_exceeds_60s=None if runtime_bank is None else runtime_bank > 60,
                own_cash_reconciled=None, final_matches_ledger=None,
                failed_market_requests={}, no_effect_commands={}, ineffective_moves=None,
                crop_and_animal_deaths={}, wall_seconds=None, ledger_issue=None,
                engine_audit=None, engine_verified_complete=None, provenance=None)
    for ancestor in path.parents:
        manifest_path = ancestor / "run_manifest.json"
        if manifest_path.exists():
            manifest = _json(manifest_path)
            spec = (manifest.get("spec") or {}).get(arm, {})
            hashes = manifest.get("source_hashes") or {}
            agent = spec.get("agent")
            policy_cfg = dict(spec.get("cfg") or {})
            tile_path = policy_cfg.pop("sd_tp_file", None)
            info["provenance"] = dict(manifest_path=str(manifest_path.resolve()), agent=agent,
                                      executor_sha256=hashes.get(agent), base=spec.get("base", "K5b"),
                                      policy_cfg=policy_cfg, tile_plan_path=tile_path,
                                      tile_plan_sha256=hashes.get(tile_path),
                                      no_timeout=manifest.get("no_timeout"),
                                      source_hashes=hashes)
            break
    if ledger is not None:
        final_l = [ledger.get("final"), ledger.get("opp_final")]
        info["final_matches_ledger"] = (complete and all(v is not None for v in final_l)
                                         and all(abs(float(x) - float(y)) < 1e-6
                                                 for x, y in zip(final, final_l)))
        info["wall_seconds"] = ledger.get("wall_seconds")
        info["engine_audit"] = ledger.get("engine_audit")
        day_entries = ledger.get("days", [])
        if isinstance(day_entries, dict):
            day_entries = [day_entries.get(str(d), {}) for d in range(30)]
        missing_cash_days = [d for d in range(11,30)
                             if d >= len(day_entries) or day_entries[d].get("cash") is None]
        info["observed_daily_cash_complete"] = not missing_cash_days
        if missing_cash_days:
            info["completion_issues"].append("ledger missing observed morning cash on days " + ",".join(map(str,missing_cash_days)))
            info["complete"] = False
        failed, noeff, died = Counter(), Counter(), Counter()
        moves, residuals = 0, []
        for d in range(11, min(30, len(day_entries))):
            entry = day_entries[d]
            failed.update(_numeric_counter(entry.get("failed")))
            noeff.update(_numeric_counter(entry.get("noeff")))
            died.update(_numeric_counter(entry.get("died")))
            moves += int(entry.get("move_noeff") or 0)
            start = entry.get("cash")
            end = day_entries[d + 1].get("cash") if d < 29 and d + 1 < len(day_entries) else ledger.get("final")
            if start is not None and end is not None:
                expected = (float(start) + sum(_numeric_counter(entry.get("rev")).values())
                            - sum(_numeric_counter(entry.get("spend")).values())
                            - float(entry.get("wages") or 0) - float(entry.get("land") or 0))
                residuals.append([d, float(end) - expected])
        info.update(failed_market_requests=dict(failed), no_effect_commands=dict(noeff),
                    ineffective_moves=moves, crop_and_animal_deaths=dict(died),
                    own_cash_reconciled=(len(residuals) == 19 and all(abs(r) < 1e-6 for _, r in residuals)),
                    own_cash_residuals=[[d, r] for d, r in residuals if abs(r) >= 1e-6])
    if info["engine_audit"] is None:
        for ancestor in path.parents:
            possible = ancestor / "engine_audits" / arm / f"{ep}.json"
            if possible.exists():
                info["engine_audit"] = _json(possible)
                break
    engine = info["engine_audit"]
    if engine:
        info["engine_verified_complete"] = (engine.get("statuses") == ["DONE", "DONE"]
                                            and engine.get("steps") == 720 and not engine.get("runner_error"))
        if not info["engine_verified_complete"]:
            info["completion_issues"].append("explicit engine audit is not DONE/DONE with 720 states")
            info["complete"] = False
    else:
        # sector_run can pad its daily money map with the last state after an
        # early engine termination.  A full-looking map or ledger final equality
        # therefore cannot substitute for actual DONE/DONE + 720-state evidence.
        info["completion_issues"].append("engine completion unverified: no explicit status/720-state audit")
        info["complete"] = False
    if info["ledger_path"] is None:
        info["completion_issues"].append("full execution ledger unavailable")
        info["complete"] = False
    return info


def compare_provenance(baseline, candidate):
    """Ignore tile plan and read-only runner wrappers; require the frozen policy."""
    b, c = baseline.get("provenance"), candidate.get("provenance")
    if not b or not c or not b.get("executor_sha256") or not c.get("executor_sha256"):
        return dict(policy_match=None, runtime_match=None, reason="missing source manifest or executor hash")
    differences = []
    if b["executor_sha256"] != c["executor_sha256"]:
        differences.append("executor_sha256")
    if b["base"] != c["base"]:
        differences.append("base")
    for key in sorted(set(b["policy_cfg"]) | set(c["policy_cfg"])):
        if key not in b["policy_cfg"] or key not in c["policy_cfg"] or b["policy_cfg"][key] != c["policy_cfg"][key]:
            differences.append("cfg." + key)
    # Compare measured engine timeout when present, then explicit manifest mode.
    be, ce = baseline.get("engine_audit") or {}, candidate.get("engine_audit") or {}
    bt, ct = be.get("act_timeout"), ce.get("act_timeout")
    if bt is not None and ct is not None:
        runtime_match = bt == ct
    elif b.get("no_timeout") is not None and c.get("no_timeout") is not None:
        runtime_match = b["no_timeout"] == c["no_timeout"]
    else:
        runtime_match = None
    return dict(policy_match=not differences, runtime_match=runtime_match,
                differences=differences, baseline_executor_sha256=b["executor_sha256"],
                candidate_executor_sha256=c["executor_sha256"],
                baseline_act_timeout=bt, candidate_act_timeout=ct,
                runtime_note="Explicit engine audit unavailable for one or both games" if bt is None or ct is None else "Measured engine timeout compared")


def discover(roots, arms):
    paths = set()
    for root in roots:
        for arm in arms:
            root = Path(root)
            if root.name == arm and root.parent.name == "multi":
                paths.update(root.glob("*.json"))
            paths.update(root.glob(f"**/sector/multi/{arm}/*.json"))
            # Also accept an existing sector result root used by local identity checks.
            paths.update(root.glob(f"multi/{arm}/*.json"))
    result, duplicates = {}, []
    for path in sorted(paths):
        row = load_world(path)
        key = (row["arm"], row["episode"])
        if key in result:
            first = result[key]
            conflicting = any(first[k] != row[k] for k in ("complete", "ours", "rival"))
            duplicates.append(dict(arm=key[0], episode=key[1], conflicting=conflicting,
                                   first=first["result_path"], duplicate=row["result_path"]))
        else:
            result[key] = row
    return result, duplicates


def integrity_summary(rows):
    leak, failed, noeff, died = Counter(), Counter(), Counter(), Counter()
    for r in rows:
        leak.update(r["tp_leak"])
        failed.update(r["failed_market_requests"])
        noeff.update(r["no_effect_commands"])
        died.update(r["crop_and_animal_deaths"])
    banks = [float(r["runtime_bank_used"]) for r in rows if r["runtime_bank_used"] is not None]
    return dict(games=len(rows), complete_games=sum(r["complete"] for r in rows),
                ledgers_found=sum(r["ledger_path"] is not None for r in rows),
                cash_reconciled_games=sum(r["own_cash_reconciled"] is True for r in rows),
                final_matches_ledger_games=sum(r["final_matches_ledger"] is True for r in rows),
                executor_errors=sum(r["executor_errors"] for r in rows),
                games_with_executor_errors=sum(bool(r["executor_errors"]) for r in rows),
                tp_leak=dict(leak), games_with_tp_leak=sum(bool(r["tp_leak"]) for r in rows),
                failed_market_requests=dict(failed), no_effect_commands=dict(noeff),
                ineffective_moves=sum(r["ineffective_moves"] or 0 for r in rows),
                crop_and_animal_deaths=dict(died),
                runtime_games_measured=len(banks), runtime_bank_max=max(banks) if banks else None,
                runtime_bank_mean=sum(banks) / len(banks) if banks else None,
                games_exceeding_60s_bank=sum(r["bank_exceeds_60s"] is True for r in rows),
                steps_over_1s=sum(r["steps_over_1s"] or 0 for r in rows),
                engine_audit_games=sum(bool(r.get("engine_audit")) for r in rows),
                engine_audits={r["episode"]:r["engine_audit"] for r in rows if r.get("engine_audit")},
                engine_verified_complete_games=sum(r.get("engine_verified_complete") is True for r in rows),
                engine_verified_failed_games=sum(r.get("engine_verified_complete") is False for r in rows),
                engine_status_unverified_games=sum(r.get("engine_verified_complete") is None for r in rows),
                observed_daily_cash_complete_games=sum(r.get("observed_daily_cash_complete") is True for r in rows),
                padded_or_missing_cash_games=sum(r.get("observed_daily_cash_complete") is False for r in rows),
                incomplete_with_overage_above60_games=sum(not r["complete"] and r["bank_exceeds_60s"] is True for r in rows),
                legality_note="Counters cover instrumented engine execution: no-effect commands and rejected market requests are reported, not equated with invalid action syntax. Animal deaths include intentional retirement. This offline harness does not certify official timeout compliance.")


def comparison(rows, baseline, candidate, expected, stage, seed, draws):
    paired, missing = [], []
    provenance = []
    for ep in expected:
        b, c = rows.get((baseline, ep)), rows.get((candidate, ep))
        if b is None or c is None or not b["complete"] or not c["complete"]:
            missing.append(ep)
            continue
        paired.append(dict(episode=ep, baseline_ours=b["ours"], baseline_rival=b["rival"],
                           baseline_margin=b["margin"], candidate_ours=c["ours"],
                           candidate_rival=c["rival"], candidate_margin=c["margin"],
                           margin_delta=c["margin"] - b["margin"],
                           own_cash_delta=c["ours"] - b["ours"],
                           rival_cash_delta=c["rival"] - b["rival"],
                           baseline_win=b["margin"] > 0, candidate_win=c["margin"] > 0))
        provenance.append(dict(episode=ep, **compare_provenance(b, c)))
    n = len(paired)
    delta = summarize([r["margin_delta"] for r in paired], seed, draws)
    bwin, cwin = sum(r["baseline_win"] for r in paired), sum(r["candidate_win"] for r in paired)
    # Integrity includes failed/unverified attempts as well as admitted pairs.
    grows = [rows[(candidate, ep)] for ep in expected if (candidate, ep) in rows]
    brows = [rows[(baseline, ep)] for ep in expected if (baseline, ep) in rows]
    audit_c, audit_b = integrity_summary(grows), integrity_summary(brows)
    all40 = n == 40 and len(expected) == 40 and not missing and stage == "full40"
    regression_known = delta["significantly_worse"] is not None
    protocol_pass = all40 and cwin >= 20 and regression_known and not delta["significantly_worse"]
    clean = all(a["games"] == a["cash_reconciled_games"] == a["final_matches_ledger_games"]
                and a["executor_errors"] == 0 and a["games_with_tp_leak"] == 0
                and a["engine_verified_failed_games"] == 0
                for a in (audit_b, audit_c))
    policy_match = bool(provenance) and all(p["policy_match"] is True for p in provenance)
    runtime_conflict = any(p["runtime_match"] is False for p in provenance)
    return dict(candidate=candidate, baseline=baseline, stage=stage, expected_games=len(expected),
                paired_games=n, missing_or_incomplete=missing, margin_delta=delta,
                own_cash_delta=summarize([r["own_cash_delta"] for r in paired], seed, draws),
                rival_cash_delta=summarize([r["rival_cash_delta"] for r in paired], seed, draws),
                baseline_score=dict(wins=bwin, ties=sum(r["baseline_margin"] == 0 for r in paired),
                              mean_margin=sum(r["baseline_margin"] for r in paired) / n if n else None,
                              win_rate=bwin / n if n else None, wilson95=wilson(bwin, n)),
                candidate_score=dict(wins=cwin, ties=sum(r["candidate_margin"] == 0 for r in paired),
                                     mean_margin=sum(r["candidate_margin"] for r in paired) / n if n else None,
                                     win_rate=cwin / n if n else None, wilson95=wilson(cwin, n)),
                win_flips=dict(loss_or_tie_to_win=sum(not r["baseline_win"] and r["candidate_win"] for r in paired),
                               win_to_loss_or_tie=sum(r["baseline_win"] and not r["candidate_win"] for r in paired)),
                requested_competitive_gate=dict(eligible_full40=all40, wins_at_least20=cwin >= 20 if all40 else None,
                                               no_significant_regression=(not delta["significantly_worse"])
                                               if regression_known else None,
                                               pass_=bool(protocol_pass)),
                integrity_gate_pass=bool(clean and policy_match and not runtime_conflict and not missing and n > 0),
                evidence_supports_requested_gate=bool(protocol_pass and clean and policy_match and not runtime_conflict),
                source_and_regime=dict(policy_matches_all=policy_match,
                                       confirmed_runtime_conflict=runtime_conflict,
                                       runtime_pairs_unverified=sum(p["runtime_match"] is None for p in provenance),
                                       pairs=provenance),
                noninferiority_proven=False,
                inference_note="No noninferiority margin was specified. A nonsignificant one-sided regression test is not proof of equivalence. Full40 includes any development worlds reused to select a candidate; report the disjoint remainder separately.",
                baseline_integrity=audit_b, candidate_integrity=audit_c, worlds=paired)


def _fmt(x, digits=0):
    return "unavailable" if x is None else f"{x:,.{digits}f}"


def arm_summary(rows, arm, expected, seed, draws):
    present = [rows[(arm, ep)] for ep in expected if (arm, ep) in rows]
    complete = [r for r in present if r["complete"]]
    n = len(complete)
    wins = sum(r["margin"] > 0 for r in complete)
    return dict(arm=arm, expected_games=len(expected), complete_games=n,
                missing_or_incomplete=[ep for ep in expected if (arm, ep) not in rows or not rows[(arm, ep)]["complete"]],
                wins=wins, ties=sum(r["margin"] == 0 for r in complete),
                win_rate=wins/n if n else None, wilson95=wilson(wins,n),
                margin=summarize([r["margin"] for r in complete],seed,draws),
                integrity=integrity_summary(present))


def markdown(report):
    baseline = report["baseline_summary"]
    bci = baseline["margin"]["bootstrap95"] or [None,None]
    ba = baseline["integrity"]
    text = ["# Semantic tile planner on KB115LT", "",
            f"Stage: **{report['stage']}**. Input contract: **{report['input_contract']}**. Baseline: `{report['baseline']}`. "
            f"Bootstrap: {report['bootstrap_draws']:,} world-paired draws, seed {report['seed']}.", "",
            f"Exact-tiling baseline: **{baseline['wins']}/{baseline['complete_games']} wins**, "
            f"mean competitive margin {_fmt(baseline['margin']['mean'])} "
            f"(bootstrap 95% {_fmt(bci[0])} to {_fmt(bci[1])}). "
            f"Own cash reconciled {ba['cash_reconciled_games']}/{ba['games']}; "
            f"explicit complete-engine audits {ba['engine_verified_complete_games']}/{ba['games']}; "
            f"engine status unverified in {ba['engine_status_unverified_games']} earlier artifacts.", "",
            "| Candidate | Paired worlds | Wins | Mean margin delta | Bootstrap 95% CI | Regression p (one-sided) | Requested gate |",
            "|---|---:|---:|---:|---|---:|---|"]
    for comp in report["comparisons"]:
        d, score = comp["margin_delta"], comp["candidate_score"]
        ci = d["bootstrap95"] or [None, None]
        gate = "pass" if comp["evidence_supports_requested_gate"] else ("not eligible" if not comp["requested_competitive_gate"]["eligible_full40"] else "not met")
        text.append(f"| {comp['candidate']} | {comp['paired_games']} | {score['wins']}/{comp['paired_games']} | "
                    f"{_fmt(d['mean'])} | {_fmt(ci[0])} to {_fmt(ci[1])} | {_fmt(d['regression_p_one_sided'], 4)} | {gate} |")
    text += ["", "The requested full40 gate is at least 20 wins and no statistically significant paired regression at one-sided α=0.05. "
             "Passing this test does **not** prove equivalence or noninferiority: no acceptable loss margin was declared. "
             "These are fixed-shop worlds against recorded opponent actions; prices still respond to our changed supply.", ""]
    if report["input_contract"] != "strict" and report["comparisons"]:
        text += ["The strict tile-change-only input contract is not declared for these candidates; numerical results cannot qualify them for the requested strict shipping gate.", ""]
    for comp in report["comparisons"]:
        d, c = comp["margin_delta"], comp["candidate_integrity"]
        ci = d["t95"] or [None, None]
        text += [f"## {comp['candidate']}", "",
                 f"Margin improved / unchanged / worse: {d.get('improved', 0)} / {d.get('unchanged', 0)} / {d.get('worse', 0)}. "
                 f"Paired t 95% CI: {_fmt(ci[0])} to {_fmt(ci[1])}. "
                 f"Win flips gained / lost: {comp['win_flips']['loss_or_tie_to_win']} / {comp['win_flips']['win_to_loss_or_tie']}.", "",
                 f"Complete games {c['complete_games']}/{c['games']}; own cash reconciled {c['cash_reconciled_games']}/{c['games']}; "
                 f"both final cash figures agree with ledgers {c['final_matches_ledger_games']}/{c['games']}. "
                 f"Executor errors {c['executor_errors']}; games with interface leaks {c['games_with_tp_leak']}. "
                 f"Maximum measured overage bank {_fmt(c['runtime_bank_max'], 2)} s; {c['games_exceeding_60s_bank']} games exceed 60 s.", "",
                 f"Frozen executor and policy configuration match: {comp['source_and_regime']['policy_matches_all']}. "
                 f"Confirmed runtime-regime conflict: {comp['source_and_regime']['confirmed_runtime_conflict']}; "
                 f"runtime pairing unverified for {comp['source_and_regime']['runtime_pairs_unverified']} worlds. "
                 f"Explicit complete-engine audits {c['engine_verified_complete_games']}/{c['games']}; "
                 f"engine status unverified {c['engine_status_unverified_games']}.", "",
                 "Failed market requests and no-effect commands are retained in the JSON report. Intentional animal retirement is included in death counters. "
                 "Offline execution does not certify Kaggle action-time compliance.", ""]
        if comp.get("heldout_remainder"):
            h = comp["heldout_remainder"]
            hci = h["margin_delta"]["bootstrap95"] or [None, None]
            text += [f"Disjoint non-development remainder: {h['paired_games']} worlds, "
                     f"{h['candidate_score']['wins']} wins, mean paired margin {_fmt(h['margin_delta']['mean'])} "
                     f"(bootstrap 95% {_fmt(hci[0])} to {_fmt(hci[1])}).", ""]
    if report["duplicates"]:
        text += [f"Duplicate artifacts: {len(report['duplicates'])}; see JSON. Conflicting duplicates invalidate all gates.", ""]
    return "\n".join(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--roots", nargs="+", required=True)
    ap.add_argument("--baseline", default="ST28EXACT")
    ap.add_argument("--candidates", default="", help="Comma-separated arms; omit for baseline-only report")
    ap.add_argument("--panel", required=True)
    ap.add_argument("--development-panel")
    ap.add_argument("--stage", choices=["exploratory8", "full40", "diagnostic"], default="diagnostic")
    ap.add_argument("--input-contract", choices=["strict", "timing_extended", "unknown"], default="unknown")
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--bootstrap", type=int, default=20000)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    candidates = [c.strip() for c in args.candidates.split(",") if c.strip()]
    expected = read_panel(args.panel)
    if len(expected) != len(set(expected)):
        raise ValueError("panel repeats an episode; paired unit must be a distinct world")
    rows, duplicates = discover(args.roots, [args.baseline] + candidates)
    dev = set(read_panel(args.development_panel) or [])
    comps = []
    for c in candidates:
        comp = comparison(rows, args.baseline, c, expected, args.stage, args.seed, args.bootstrap)
        comp["declared_input_contract"] = args.input_contract
        if args.input_contract != "strict":
            comp["evidence_supports_requested_gate"] = False
        if args.stage == "full40" and dev:
            other = [ep for ep in expected if ep not in dev]
            comp["development_episodes_in_full40"] = [ep for ep in expected if ep in dev]
            comp["heldout_remainder"] = comparison(rows, args.baseline, c, other, "disjoint_remainder", args.seed, args.bootstrap)
        if any(d["conflicting"] for d in duplicates if d["arm"] in (args.baseline, c)):
            comp["integrity_gate_pass"] = comp["evidence_supports_requested_gate"] = False
        comps.append(comp)
    report = dict(stage=args.stage, input_contract=args.input_contract, baseline=args.baseline, seed=args.seed, bootstrap_draws=args.bootstrap,
                  roots=[str(Path(r).resolve()) for r in args.roots], panel=str(Path(args.panel).resolve()),
                  panel_sha256=hashlib.sha256(Path(args.panel).read_bytes()).hexdigest(),
                  duplicates=duplicates, comparisons=comps,
                  baseline_summary=arm_summary(rows,args.baseline,expected,args.seed,args.bootstrap),
                  raw_world_audits=[r for (a, ep), r in sorted(rows.items()) if ep in expected])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    (out / "report.md").write_text(markdown(report), encoding="utf-8")
    for comp in comps:
        if not comp["worlds"]:
            continue
        with (out / f"{comp['candidate']}_paired.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(comp["worlds"][0]))
            writer.writeheader()
            writer.writerows(comp["worlds"])
    brief = {c["candidate"]: dict(n=c["paired_games"], wins=c["candidate_score"]["wins"],
                                          mean_delta=c["margin_delta"]["mean"],
                                          p_regression=c["margin_delta"]["regression_p_one_sided"],
                                          requested_gate=c["evidence_supports_requested_gate"])
                      for c in comps}
    if not comps:
        brief = dict(baseline=args.baseline, wins=report["baseline_summary"]["wins"],
                     n=report["baseline_summary"]["complete_games"],
                     mean_margin=report["baseline_summary"]["margin"]["mean"])
    print(json.dumps(brief, indent=2))
    return report


if __name__ == "__main__":
    main()

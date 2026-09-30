"""At-game-time ratings for the ladder panel, redo of the win/seat/opponent analysis.

Direction (2026-09-23 follow-up to analyze_ladder_losses_2800.py): the earlier logistic
regression joined each game to the opponent's CURRENT leaderboard score, which is biased for
games played days ago (the pool's ratings, and ours, have drifted since). This script:

1. Checks whether the Kaggle API exposes a per-episode rating (before/after each game). It does
   not: `competition_list_episodes` returns `ApiEpisode`/`ApiEpisodeAgent` objects with only
   id/create_time/end_time/state/agents and submission_id/index/reward/state/team_name/team_id
   (see .venv/Lib/site-packages/kagglesdk/competitions/types/competition_api_service.py — no
   score/rating field on either class); the replay JSON's `info` block carries only
   Agents/EpisodeId/TeamNames/seed. The only place a per-episode Initial/UpdatedScore exists is
   the meta-kaggle dataset's EpisodeAgents.csv (26.9 GB) / Episodes.csv (8.0 GB) — checked via
   `api.dataset_list_files('kaggle/meta-kaggle')` — which is impractical to download for this
   scope (it covers every Kaggle simulation competition ever run, not just ours). So there is no
   API path to an exact at-game rating; this is reported as a real limitation, not silently
   worked around.
2. Falls back to the best available real (not reconstructed) history: four full leaderboard
   snapshots already on disk from this project's earlier work, at 2026-09-18 19:25,
   2026-09-20 03:15, 2026-09-20 19:39 (`results/fresh/leaderboard_20260918`,
   `..._20260920`, `..._live`, all ~9.5-9.7k teams) plus a fresh full pull fetched by this
   script's companion `fetch_full_leaderboard.py` output used today
   (`results/fresh/newphase_20260923/leaderboard_full.json`, ~9.9k teams, fetched 2026-09-23).
   For each game we take BOTH teams' rating from whichever of these four snapshots is CLOSEST
   IN TIME to the game's `created` timestamp (ties/missing-team fall through to the next
   closest snapshot that has that team_id). This is a real historical value, not an
   extrapolation, but it is a step function with gaps up to ~2.8 days (worst: the 09-20 19:39 to
   09-23 15:09 gap covers most of the 09-21..09-23 games) — the per-game staleness (hours from
   game time to the snapshot used) is recorded and its distribution reported so the residual
   bias is visible rather than assumed away. We do NOT attempt to reconstruct our own rating
   trajectory from the sequence of game outcomes (no public Elo/TrueSkill update rule for this
   competition) — only real recorded snapshot values are used.

Outputs under results/fresh/newphase_20260923/ladder_ratings/:
  merged_games.json  - per game: at-game ratings, snapshot used, staleness, diff, Elo prediction
  summary.json        - every table below, machine-readable
  summary.md           - the same, formatted

No game simulation, no replay downloads (only already-fetched `.csv`/`.json` leaderboard
snapshots and the existing `ladder_games.json` panel are read); one process.
"""
import csv
import io
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
GAMES_PATH = ROOT / 'results/fresh/newphase_20260923/ladder_games.json'
LEADERBOARD_FULL = ROOT / 'results/fresh/newphase_20260923/leaderboard_full.json'
OUT = ROOT / 'results/fresh/newphase_20260923/ladder_ratings'

OUR_TEAM_ID = 16823930  # Ghost Rule (confirmed in every snapshot below)
OUR_TEAM_NAME = 'Ghost Rule'

SUB_T10 = '56368334'
SUB_M1 = '56395605'
SUB_LEGACY = '56341683'
SUB_LABEL = {SUB_T10: 't10', SUB_M1: 'm1', SUB_LEGACY: 'legacy_56341683'}
MAIN_SUBS = (SUB_T10, SUB_M1)  # the two live submissions named in the task context

SNAPSHOT_CSVS = [
    ROOT / 'results/fresh/leaderboard_20260918/kaggriculture-publicleaderboard-2026-09-18T19_25_17.csv',
    ROOT / 'results/fresh/leaderboard_20260920/kaggriculture-publicleaderboard-2026-09-20T03_15_36.csv',
    ROOT / 'results/fresh/leaderboard_live/kaggriculture-publicleaderboard-2026-09-20T19_39_19.csv',
]

Z = 1.959963984540054  # 97.5th pct of N(0,1), for 95% CIs


# ---------------------------------------------------------------- snapshots

def parse_csv_snapshot(path):
    m = re.search(r'(\d{4}-\d{2}-\d{2})T(\d{2})_(\d{2})_(\d{2})', path.name)
    y, mo, d = (int(x) for x in m.group(1).split('-'))
    dt = datetime(y, mo, d, int(m.group(2)), int(m.group(3)), int(m.group(4)))
    scores = {}
    with io.open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            try:
                scores[int(row['TeamId'])] = float(row['Score'])
            except (KeyError, ValueError):
                continue
    return dt, scores


def load_snapshots():
    snaps = [parse_csv_snapshot(p) for p in SNAPSHOT_CSVS]
    lb = json.loads(LEADERBOARD_FULL.read_text(encoding='utf-8'))
    cur_dt = datetime.fromtimestamp(LEADERBOARD_FULL.stat().st_mtime)
    cur_scores = {}
    for r in lb:
        try:
            cur_scores[int(r['team_id'])] = float(r['score'])
        except (TypeError, ValueError):
            continue
    snaps.append((cur_dt, cur_scores))
    snaps.sort(key=lambda s: s[0])
    return snaps


def lookup_rating(snaps, team_id, when):
    if team_id is None:
        return None, None, None
    order = sorted(snaps, key=lambda s: abs((s[0] - when).total_seconds()))
    for dt, scores in order:
        if team_id in scores:
            hrs = abs((when - dt).total_seconds()) / 3600.0
            return scores[team_id], dt.isoformat(), hrs
    return None, None, None


def parse_created(s):
    return datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')


# ---------------------------------------------------------------- stats helpers

def wilson_ci(k, n, z=Z):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (center - half, center + half)


def logistic_fit(X, y, max_iter=200, tol=1e-12):
    """IRLS logistic regression. X includes an intercept column. Returns coef/se/z/p/cov."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n, p = X.shape
    beta = np.zeros(p)
    for _ in range(max_iter):
        eta = X @ beta
        eta = np.clip(eta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-10, None)
        grad = X.T @ (y - mu)
        H = (X.T * w) @ X
        try:
            delta = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            delta = np.linalg.lstsq(H, grad, rcond=None)[0]
        beta_new = beta + delta
        if np.max(np.abs(beta_new - beta)) < tol:
            beta = beta_new
            break
        beta = beta_new
    eta = np.clip(X @ beta, -30, 30)
    mu = 1.0 / (1.0 + np.exp(-eta))
    w = np.clip(mu * (1 - mu), 1e-10, None)
    H = (X.T * w) @ X
    try:
        cov = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(H)
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    z = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    pval = 2 * stats.norm.sf(np.abs(z))
    ll = float(np.sum(y * np.log(np.clip(mu, 1e-12, 1)) + (1 - y) * np.log(np.clip(1 - mu, 1e-12, 1))))
    return dict(beta=beta.tolist(), se=se.tolist(), z=z.tolist(), p=pval.tolist(), cov=cov.tolist(), loglik=ll, n=n)


def elo_pred(diff):
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def bootstrap_mean_ci(values, n_boot=4000, seed=0):
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return (float('nan'), float('nan'))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(values), size=(n_boot, len(values)))
    boots = values[idx].mean(axis=1)
    return (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))


def bootstrap_diff_ci(a, b, n_boot=4000, seed=0):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    if len(a) == 0 or len(b) == 0:
        return (float('nan'), float('nan'))
    ai = rng.integers(0, len(a), size=(n_boot, len(a)))
    bi = rng.integers(0, len(b), size=(n_boot, len(b)))
    boots = a[ai].mean(axis=1) - b[bi].mean(axis=1)
    return (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))


# ---------------------------------------------------------------- world type

def world_type(shops):
    seq = shops[:8]
    late = any(s == 'YARN_STORE' for s in seq[4:8])
    early = any(s == 'YARN_STORE' for s in seq[0:4])
    if late:
        return 'late_yarn'
    if early:
        return 'early_yarn_only'
    return 'no_yarn'


# ---------------------------------------------------------------- main

def build_merged():
    rows = json.loads(GAMES_PATH.read_text(encoding='utf-8'))
    snaps = load_snapshots()
    merged = []
    for r in rows:
        created = parse_created(r['created'])
        our_r, our_snap, our_stale = lookup_rating(snaps, OUR_TEAM_ID, created)
        opp_r, opp_snap, opp_stale = lookup_rating(snaps, r.get('opp_team_id'), created)
        diff = (our_r - opp_r) if (our_r is not None and opp_r is not None) else None
        merged.append(dict(
            submission=r['submission'], sub_label=SUB_LABEL.get(r['submission'], r['submission']),
            episode=r['episode'], created=r['created'], seat=r['seat'],
            ours=r['ours'], theirs=r['theirs'], margin=r['margin'], win=r['win'],
            opp_team=r.get('opp_team'), opp_team_id=r.get('opp_team_id'),
            opp_rating_current=r.get('opp_rating'),
            our_rating_atgame=our_r, our_snapshot=our_snap, our_stale_hours=our_stale,
            opp_rating_atgame=opp_r, opp_snapshot=opp_snap, opp_stale_hours=opp_stale,
            diff_atgame=diff, elo_pred=elo_pred(diff) if diff is not None else None,
            world_type=world_type(r['shops']), shops=r['shops'],
        ))
    return merged, snaps


def section_coverage(merged, snaps):
    main = [m for m in merged if m['submission'] in MAIN_SUBS]
    n_missing_opp = sum(1 for m in main if m['opp_rating_atgame'] is None)
    stale_our = [m['our_stale_hours'] for m in main if m['our_stale_hours'] is not None]
    stale_opp = [m['opp_stale_hours'] for m in main if m['opp_stale_hours'] is not None]
    return dict(
        snapshots=[dict(time=dt.isoformat(), n_teams=len(sc)) for dt, sc in snaps],
        n_games_total=len(merged), n_games_main=len(main),
        n_legacy_excluded=len(merged) - len(main),
        n_missing_opp_rating=n_missing_opp,
        our_stale_hours=dict(mean=float(np.mean(stale_our)), median=float(np.median(stale_our)),
                              p90=float(np.percentile(stale_our, 90)), max=float(np.max(stale_our))),
        opp_stale_hours=dict(mean=float(np.mean(stale_opp)), median=float(np.median(stale_opp)),
                              p90=float(np.percentile(stale_opp, 90)), max=float(np.max(stale_opp))),
        our_rating_trajectory_note='Ghost Rule at-game rating from the 4 snapshots: 2261.4 (09-18 19:25) -> '
                                    '2309.7 (09-20 03:15) -> 2471.6 (09-20 19:39) -> current ~2800 (09-23).',
    )


def section_elo(merged):
    out = {}
    for scope, subset in [('pooled', [m for m in merged if m['submission'] in MAIN_SUBS])] + \
                          [(SUB_LABEL[s], [m for m in merged if m['submission'] == s]) for s in MAIN_SUBS]:
        d = [m for m in subset if m['diff_atgame'] is not None]
        diffs = np.array([m['diff_atgame'] for m in d])
        wins = np.array([m['win'] for m in d], dtype=float)
        preds = np.array([m['elo_pred'] for m in d])
        # bucketed table
        edges = [-1e9, -300, -200, -100, -50, 0, 50, 100, 200, 300, 1e9]
        labels = ['<-300', '-300..-200', '-200..-100', '-100..-50', '-50..0',
                  '0..50', '50..100', '100..200', '200..300', '>300']
        buckets = []
        for lo, hi, lab in zip(edges[:-1], edges[1:], labels):
            sel = (diffs >= lo) & (diffs < hi)
            n = int(sel.sum())
            if n == 0:
                continue
            k = int(wins[sel].sum())
            lo_ci, hi_ci = wilson_ci(k, n)
            buckets.append(dict(bucket=lab, n=n, wins=k, win_rate=k / n, wilson_lo=lo_ci, wilson_hi=hi_ci,
                                 mean_diff=float(diffs[sel].mean()), mean_elo_pred=float(preds[sel].mean())))
        # logistic fit win ~ a + b*diff
        X = np.column_stack([np.ones(len(d)), diffs])
        fit = logistic_fit(X, wins)
        a, b = fit['beta']
        se_a, se_b = fit['se']
        cov_ab = fit['cov'][0][1]
        diff0 = -a / b if b != 0 else float('nan')
        # delta method variance of diff0 = -a/b
        var_diff0 = (1 / b) ** 2 * (se_a ** 2 + (a / b) ** 2 * se_b ** 2 - 2 * (a / b) * cov_ab)
        se_diff0 = math.sqrt(var_diff0) if var_diff0 > 0 else float('nan')
        mean_opp_rating = float(np.mean([m['opp_rating_atgame'] for m in d]))
        r_sat = mean_opp_rating + diff0
        se_r_sat = se_diff0
        overall_gap = float(wins.mean() - preds.mean())
        gap_ci = bootstrap_mean_ci(wins - preds)
        out[scope] = dict(
            n=len(d), buckets=buckets,
            logistic=dict(intercept=a, intercept_se=se_a, slope=b, slope_se=se_b,
                           ideal_slope=math.log(10) / 400,
                           intercept_p=fit['p'][0], slope_p=fit['p'][1]),
            saturation_diff=diff0, saturation_diff_se=se_diff0,
            saturation_diff_ci=[diff0 - Z * se_diff0, diff0 + Z * se_diff0] if not math.isnan(se_diff0) else None,
            mean_opp_rating_in_sample=mean_opp_rating,
            estimated_saturation_rating=r_sat,
            estimated_saturation_rating_ci=[r_sat - Z * se_r_sat, r_sat + Z * se_r_sat] if not math.isnan(se_r_sat) else None,
            overall_actual_minus_elo=overall_gap, overall_actual_minus_elo_ci=list(gap_ci),
            mean_actual_win_rate=float(wins.mean()), mean_elo_predicted=float(preds.mean()),
        )
    # by world type (pooled main subs)
    main = [m for m in merged if m['submission'] in MAIN_SUBS and m['diff_atgame'] is not None]
    by_world = {}
    resid = {}
    for wt in ('no_yarn', 'early_yarn_only', 'late_yarn'):
        sub = [m for m in main if m['world_type'] == wt]
        if not sub:
            continue
        wins = np.array([m['win'] for m in sub], dtype=float)
        preds = np.array([m['elo_pred'] for m in sub])
        r = wins - preds
        resid[wt] = r
        lo, hi = bootstrap_mean_ci(r)
        by_world[wt] = dict(n=len(sub), mean_actual=float(wins.mean()), mean_elo_pred=float(preds.mean()),
                             actual_minus_elo=float(r.mean()), ci95=[lo, hi])
    # late_yarn vs no_yarn difference + permutation p-value
    if 'late_yarn' in resid and 'no_yarn' in resid:
        obs_diff = float(resid['late_yarn'].mean() - resid['no_yarn'].mean())
        ci = bootstrap_diff_ci(resid['late_yarn'], resid['no_yarn'])
        pooled = np.concatenate([resid['late_yarn'], resid['no_yarn']])
        n1 = len(resid['late_yarn'])
        rng = np.random.default_rng(1)
        n_perm = 5000
        perm_diffs = np.empty(n_perm)
        for i in range(n_perm):
            rng.shuffle(pooled)
            perm_diffs[i] = pooled[:n1].mean() - pooled[n1:].mean()
        p_perm = float((np.sum(np.abs(perm_diffs) >= abs(obs_diff)) + 1) / (n_perm + 1))
        by_world['late_yarn_minus_no_yarn'] = dict(diff=obs_diff, ci95=list(ci), permutation_p=p_perm)
    out['by_world_type'] = by_world
    return out


def section_seats(merged):
    out = {}
    for scope, subset in [('pooled', [m for m in merged if m['submission'] in MAIN_SUBS])] + \
                          [(SUB_LABEL[s], [m for m in merged if m['submission'] == s]) for s in MAIN_SUBS]:
        s0 = [m for m in subset if m['seat'] == 0]
        s1 = [m for m in subset if m['seat'] == 1]
        w0, n0 = sum(m['win'] for m in s0), len(s0)
        w1, n1 = sum(m['win'] for m in s1), len(s1)
        table = [[w0, n0 - w0], [w1, n1 - w1]]
        odds_ratio, fisher_p = stats.fisher_exact(table)
        chi2, chi2_p, _, _ = stats.chi2_contingency(table, correction=False)
        lo0, hi0 = wilson_ci(w0, n0)
        lo1, hi1 = wilson_ci(w1, n1)
        rate0, rate1 = (w0 / n0 if n0 else float('nan')), (w1 / n1 if n1 else float('nan'))
        diff_lo, diff_hi = bootstrap_diff_ci([1] * w0 + [0] * (n0 - w0), [1] * w1 + [0] * (n1 - w1))
        # rating-controlled logistic: win ~ a + b*diff + c*seat1
        d = [m for m in subset if m['diff_atgame'] is not None]
        seat1 = np.array([1.0 if m['seat'] == 1 else 0.0 for m in d])
        diffs = np.array([m['diff_atgame'] for m in d])
        wins = np.array([m['win'] for m in d], dtype=float)
        X = np.column_stack([np.ones(len(d)), diffs, seat1])
        fit = logistic_fit(X, wins)
        c, se_c, p_c = fit['beta'][2], fit['se'][2], fit['p'][2]
        or_seat = math.exp(c)
        or_ci = [math.exp(c - Z * se_c), math.exp(c + Z * se_c)]
        out[scope] = dict(
            seat0=dict(n=n0, wins=w0, win_rate=rate0, wilson_ci=[lo0, hi0]),
            seat1=dict(n=n1, wins=w1, win_rate=rate1, wilson_ci=[lo1, hi1]),
            raw_diff_seat1_minus_seat0=rate1 - rate0, raw_diff_ci95=[diff_lo, diff_hi],
            fisher_exact_p=float(fisher_p), chi2_p=float(chi2_p),
            # fisher_exact(table) with table=[[w0,l0],[w1,l1]] gives (w0*l1)/(l0*w1): seat0 odds over seat1 odds
            raw_odds_ratio_seat0_over_seat1=float(odds_ratio),
            rating_controlled=dict(n=len(d), seat1_coef=c, seat1_coef_se=se_c, seat1_odds_ratio=or_seat,
                                    seat1_odds_ratio_ci95=or_ci, seat1_p=p_c),
        )
    return out


def section_opponents(merged):
    main = [m for m in merged if m['submission'] in MAIN_SUBS]
    lb = json.loads(LEADERBOARD_FULL.read_text(encoding='utf-8'))
    rank_by_team = {}
    name_by_team = {}
    for r in lb:
        try:
            tid = int(r['team_id'])
        except (TypeError, ValueError):
            continue
        rank_by_team[tid] = r['rank']
        name_by_team[tid] = r['team']
    by_team = defaultdict(list)
    for m in main:
        if m['opp_team_id'] is not None:
            by_team[m['opp_team_id']].append(m)
    agg = []
    for tid, games in by_team.items():
        n = len(games)
        w = sum(g['win'] for g in games)
        l = n - w
        margins = [g['margin'] for g in games]
        ratings = [g['opp_rating_atgame'] for g in games if g['opp_rating_atgame'] is not None]
        agg.append(dict(
            team_id=tid, team=name_by_team.get(tid) or games[-1]['opp_team'],
            n=n, wins=w, losses=l, mean_margin=float(np.mean(margins)),
            mean_opp_rating_atgame=float(np.mean(ratings)) if ratings else None,
            current_rank=rank_by_team.get(tid),
        ))
    agg.sort(key=lambda a: (-a['losses'], -a['n']))
    top15 = agg[:15]
    total_losses = sum(a['losses'] for a in agg)
    top15_losses = sum(a['losses'] for a in top15)
    top100_losses = sum(a['losses'] for a in agg if a['current_rank'] is not None and a['current_rank'] <= 100)
    # repeat opponents: played us >=3 times
    repeat = [a for a in agg if a['n'] >= 3]
    repeat_losses = sum(a['losses'] for a in repeat)
    # fraction of losses to opponent rated above us at game time
    losses_with_diff = [m for m in main if m['win'] == 0 and m['diff_atgame'] is not None]
    above_us = sum(1 for m in losses_with_diff if m['diff_atgame'] < 0)
    return dict(
        n_unique_opponents=len(agg), total_losses=total_losses,
        top15=top15,
        top15_share_of_losses=top15_losses / total_losses if total_losses else None,
        top100_current_rank_losses=top100_losses,
        top100_share_of_losses=top100_losses / total_losses if total_losses else None,
        repeat_opponents_n=len(repeat), repeat_opponents_losses=repeat_losses,
        repeat_opponents_loss_share=repeat_losses / total_losses if total_losses else None,
        losses_with_valid_diff=len(losses_with_diff),
        losses_to_opponent_rated_above_us=above_us,
        losses_to_opponent_rated_above_us_share=above_us / len(losses_with_diff) if losses_with_diff else None,
    )


def section_decomposition(merged):
    main = [m for m in merged if m['submission'] in MAIN_SUBS and m['our_rating_atgame'] is not None]
    # our at-game rating only takes as many distinct values as there are snapshots actually used
    # by these 856 games (3, in practice: the fallback is a step function, not a continuum) -- band
    # by the exact snapshot value rather than a quantile split, which would otherwise cut arbitrarily
    # inside one snapshot's block of games.
    uniq = sorted({m['our_rating_atgame'] for m in main})

    def decompose(rows, label):
        wins = [r for r in rows if r['win'] == 1]
        losses = [r for r in rows if r['win'] == 0]
        if not wins or not losses:
            return None
        ours_w = np.array([r['ours'] for r in wins]); ours_l = np.array([r['ours'] for r in losses])
        th_w = np.array([r['theirs'] for r in wins]); th_l = np.array([r['theirs'] for r in losses])
        c_ours = float(ours_w.mean() - ours_l.mean())
        c_theirs = float(th_l.mean() - th_w.mean())
        total = c_ours + c_theirs
        return dict(band=label, n=len(rows), n_win=len(wins), n_loss=len(losses),
                    mean_ours_win=float(ours_w.mean()), mean_ours_loss=float(ours_l.mean()),
                    mean_theirs_win=float(th_w.mean()), mean_theirs_loss=float(th_l.mean()),
                    contribution_ours=c_ours, contribution_theirs=c_theirs,
                    total_margin_gap=total,
                    share_ours=c_ours / total if total else None,
                    share_theirs=c_theirs / total if total else None)

    overall = decompose(main, 'overall')
    bands = []
    for val in uniq:
        sel = [r for r in main if r['our_rating_atgame'] == val]
        created = sorted(r['created'][:10] for r in sel)
        lab = f'{val:.0f} ({created[0]}..{created[-1]})'
        d = decompose(sel, lab)
        if d:
            bands.append(d)
    return dict(rating_values_used=uniq, overall=overall, by_band=bands)


def write_markdown(summary):
    L = []
    L.append('# Ladder win analysis with at-game-time ratings\n')
    L.append('Direction: redo the 2026-09-23 win/seat/opponent analysis using ratings taken as of '
             'each game\'s creation time instead of the CURRENT leaderboard score for the opponent.\n')

    L.append('## 1. At-game rating availability\n')
    cov = summary['coverage']
    L.append('The Kaggle API does **not** expose a per-episode rating. `competition_list_episodes` '
              'returns `ApiEpisode`/`ApiEpisodeAgent` objects with only '
              'id/create_time/end_time/state/agents and submission_id/index/reward/state/team_name/'
              'team_id — no score or rating field on either class (checked against the SDK source, '
              '`kagglesdk/competitions/types/competition_api_service.py`). The replay JSON `info` '
              'block similarly carries only Agents/EpisodeId/TeamNames/seed. The only place a true '
              'per-episode Initial/UpdatedScore exists is the meta-kaggle dataset '
              '(`EpisodeAgents.csv`, 26.9 GB; `Episodes.csv`, 8.0 GB, per `dataset_list_files`), which '
              'covers every Kaggle simulation competition ever run and is impractical to fetch for '
              'this scope. **Exact at-game ratings are unavailable within these constraints.**\n')
    L.append('Fallback used: four already-fetched full leaderboard snapshots '
             f"({', '.join(s['time'][:16] for s in cov['snapshots'])}, {', '.join(str(s['n_teams']) for s in cov['snapshots'])} teams "
             'respectively). Each game is joined to whichever snapshot is closest in time to its '
             '`created` timestamp, separately for our team and the opponent (falls through to the '
             'next-closest snapshot if the team is missing from the closest one).\n')
    L.append(f"- Games: {cov['n_games_total']} total in ladder_games.json; {cov['n_games_main']} on the two live "
             f"submissions (t10, m1) used below; {cov['n_legacy_excluded']} on the older submission 56341683 excluded.")
    L.append(f"- Missing opponent at-game rating: {cov['n_missing_opp_rating']} games (opponent team not present in any snapshot).")
    L.append(f"- Staleness (hours between game time and snapshot used) — ours: mean {cov['our_stale_hours']['mean']:.1f}h, "
             f"median {cov['our_stale_hours']['median']:.1f}h, p90 {cov['our_stale_hours']['p90']:.1f}h, max {cov['our_stale_hours']['max']:.1f}h; "
             f"opponent: mean {cov['opp_stale_hours']['mean']:.1f}h, median {cov['opp_stale_hours']['median']:.1f}h, "
             f"p90 {cov['opp_stale_hours']['p90']:.1f}h, max {cov['opp_stale_hours']['max']:.1f}h.")
    L.append(f"- {cov['our_rating_trajectory_note']}\n")
    L.append('This is real recorded history, not reconstruction, but it is coarse (4 checkpoints over '
             '~5 days) — treat every number below as approximate, and the staleness figures above as '
             'the honest error bar on "at-game-time".\n')

    L.append('## 2. Win rate vs at-game rating difference, vs Elo\n')
    for scope in ('pooled', 't10', 'm1'):
        e = summary['elo'][scope]
        L.append(f"### {scope} (n={e['n']})\n")
        L.append('| diff bucket | n | wins | win rate | 95% CI | mean diff | mean Elo pred |')
        L.append('|---|---|---|---|---|---|---|')
        for b in e['buckets']:
            L.append(f"| {b['bucket']} | {b['n']} | {b['wins']} | {b['win_rate']:.1%} | "
                      f"[{b['wilson_lo']:.1%}, {b['wilson_hi']:.1%}] | {b['mean_diff']:+.0f} | {b['mean_elo_pred']:.1%} |")
        lg = e['logistic']
        L.append('')
        L.append(f"Logistic fit win ~ a + b*diff: a={lg['intercept']:+.3f} (se {lg['intercept_se']:.3f}, p={lg['intercept_p']:.3g}), "
                  f"b={lg['slope']:.5f} (se {lg['slope_se']:.5f}, p={lg['slope_p']:.3g}); Elo's implied slope is "
                  f"{lg['ideal_slope']:.5f}.")
        L.append(f"Overall actual win rate {e['mean_actual_win_rate']:.1%} vs mean Elo-predicted "
                  f"{e['mean_elo_predicted']:.1%} (actual-Elo = {e['overall_actual_minus_elo']:+.1%}, "
                  f"95% CI [{e['overall_actual_minus_elo_ci'][0]:+.1%}, {e['overall_actual_minus_elo_ci'][1]:+.1%}]).")
        sd, sdci = e['saturation_diff'], e['saturation_diff_ci']
        rs, rsci = e['estimated_saturation_rating'], e['estimated_saturation_rating_ci']
        if sdci:
            L.append(f"Fitted 50%-win rating gap: {sd:+.0f} (95% CI [{sdci[0]:+.0f}, {sdci[1]:+.0f}]) — i.e. our fitted "
                      f"curve predicts a 50% expected score against opponents rated {sd:+.0f} relative to us, not 0 as "
                      f"Elo assumes. Given the mean opponent rating actually faced in this sample "
                      f"({e['mean_opp_rating_in_sample']:.0f}), that implies an equilibrium/saturation rating of roughly "
                      f"**{rs:.0f}** (95% CI [{rsci[0]:.0f}, {rsci[1]:.0f}]) — the rating at which we'd expect to score 50% "
                      f"against a similarly-composed future pool. This assumes the future opponent pool resembles the "
                      f"one observed here; it is not a forecast.")
        L.append('')

    L.append('### By world type (pooled t10+m1)\n')
    bw = summary['elo']['by_world_type']
    L.append('| world type | n | actual win rate | mean Elo pred | actual-Elo | 95% CI |')
    L.append('|---|---|---|---|---|---|')
    for wt in ('no_yarn', 'early_yarn_only', 'late_yarn'):
        if wt not in bw:
            continue
        b = bw[wt]
        L.append(f"| {wt} | {b['n']} | {b['mean_actual']:.1%} | {b['mean_elo_pred']:.1%} | "
                  f"{b['actual_minus_elo']:+.1%} | [{b['ci95'][0]:+.1%}, {b['ci95'][1]:+.1%}] |")
    if 'late_yarn_minus_no_yarn' in bw:
        d = bw['late_yarn_minus_no_yarn']
        L.append(f"\nlate_yarn minus no_yarn (actual-Elo residual): {d['diff']:+.1%}, 95% CI "
                  f"[{d['ci95'][0]:+.1%}, {d['ci95'][1]:+.1%}], permutation p={d['permutation_p']:.3g}.\n")

    L.append('## 3. Seat asymmetry (rating-controlled)\n')
    L.append('| scope | seat0 n/win% | seat1 n/win% | raw diff (s1-s0) | 95% CI | Fisher p | rating-controlled OR (seat1) | OR 95% CI | p |')
    L.append('|---|---|---|---|---|---|---|---|---|')
    for scope in ('pooled', 't10', 'm1'):
        s = summary['seats'][scope]
        rc = s['rating_controlled']
        L.append(f"| {scope} | {s['seat0']['n']}/{s['seat0']['win_rate']:.1%} | {s['seat1']['n']}/{s['seat1']['win_rate']:.1%} | "
                  f"{s['raw_diff_seat1_minus_seat0']:+.1%} | [{s['raw_diff_ci95'][0]:+.1%}, {s['raw_diff_ci95'][1]:+.1%}] | "
                  f"{s['fisher_exact_p']:.3g} | {rc['seat1_odds_ratio']:.3f} | "
                  f"[{rc['seat1_odds_ratio_ci95'][0]:.3f}, {rc['seat1_odds_ratio_ci95'][1]:.3f}] | {rc['seat1_p']:.3g} |")
    L.append('')

    L.append('## 4. Opponent identity\n')
    op = summary['opponents']
    L.append(f"{op['n_unique_opponents']} unique opponent teams across {cov['n_games_main']} games (t10+m1); "
              f"{op['total_losses']} total losses.")
    L.append(f"Top-15 opponents by loss count account for {op['top15_share_of_losses']:.1%} of all losses. "
              f"Opponents we've played >=3 times ({op['repeat_opponents_n']} teams) account for "
              f"{op['repeat_opponents_loss_share']:.1%} of losses. Losses to teams currently ranked in the top 100: "
              f"{op['top100_current_rank_losses']} ({op['top100_share_of_losses']:.1%} of losses). "
              f"Of losses with a valid at-game rating for both sides, {op['losses_to_opponent_rated_above_us_share']:.1%} "
              f"were to an opponent rated above us at game time ({op['losses_to_opponent_rated_above_us']}/{op['losses_with_valid_diff']}).\n")
    L.append('| team | current rank | games | W-L | mean margin | mean opp rating (at game) |')
    L.append('|---|---|---|---|---|---|')
    for a in op['top15']:
        L.append(f"| {a['team']} | {a['current_rank']} | {a['n']} | {a['wins']}-{a['losses']} | {a['mean_margin']:+,.0f} | "
                  f"{a['mean_opp_rating_atgame']:.0f} |" if a['mean_opp_rating_atgame'] is not None else
                  f"| {a['team']} | {a['current_rank']} | {a['n']} | {a['wins']}-{a['losses']} | {a['mean_margin']:+,.0f} | n/a |")
    L.append('')

    L.append('## 5. Own vs opponent cash: win/loss margin decomposition by rating band\n')
    dec = summary['decomposition']
    ov = dec['overall']
    L.append(f"Overall (n={ov['n']}): mean own cash in wins {ov['mean_ours_win']:,.0f} vs losses {ov['mean_ours_loss']:,.0f} "
              f"(contributes {ov['contribution_ours']:+,.0f} to the margin gap); mean opponent cash in losses "
              f"{ov['mean_theirs_loss']:,.0f} vs wins {ov['mean_theirs_win']:,.0f} (contributes {ov['contribution_theirs']:+,.0f}). "
              f"Share of the win/loss margin gap from our own cash: {ov['share_ours']:.1%}; from the opponent's cash: "
              f"{ov['share_theirs']:.1%}.\n")
    L.append('Bands below are the exact at-game rating value used (only 3 distinct values occur among these 856 '
              'games, one per snapshot era -- see section 1), not a quantile split, so each band is a clean '
              'time slice rather than an arbitrary cut through one snapshot\'s block of games.\n')
    L.append('| our at-game rating (games created) | n (W/L) | ours: win vs loss | theirs: win vs loss | share ours | share theirs |')
    L.append('|---|---|---|---|---|---|')
    for b in dec['by_band']:
        L.append(f"| {b['band']} | {b['n']} ({b['n_win']}/{b['n_loss']}) | {b['mean_ours_win']:,.0f} vs {b['mean_ours_loss']:,.0f} | "
                  f"{b['mean_theirs_win']:,.0f} vs {b['mean_theirs_loss']:,.0f} | {b['share_ours']:.1%} | {b['share_theirs']:.1%} |")
    L.append('')

    return '\n'.join(L) + '\n'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    merged, snaps = build_merged()
    with io.open(OUT / 'merged_games.json', 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False)

    summary = dict(
        coverage=section_coverage(merged, snaps),
        elo=section_elo(merged),
        seats=section_seats(merged),
        opponents=section_opponents(merged),
        decomposition=section_decomposition(merged),
    )
    with io.open(OUT / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    md = write_markdown(summary)
    with io.open(OUT / 'summary.md', 'w', encoding='utf-8') as f:
        f.write(md)

    import sys
    sys.stdout.buffer.write(md.encode('utf-8', errors='replace'))
    sys.stdout.buffer.write(b'\n')


if __name__ == '__main__':
    main()

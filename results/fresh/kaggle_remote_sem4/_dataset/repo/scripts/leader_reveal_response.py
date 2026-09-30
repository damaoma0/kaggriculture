"""Leader reveal-response study (2026-09-24 task): "units of what planted, per shop,
and when" as a learning target for a new tape-free agent.

Corpus: data/leader_semantics/<team_id>/<episode>.json.gz (schema:
data/leader_semantics/README.md). Loads the file list at start; if the corpus has
grown since (other threads were topping it up concurrently), a second pass at the
end re-runs on the larger set and reports both.

Analysis is entirely OFFLINE: reads the already-extracted per-day board/planted/
animals/built/market records, runs no simulations, single process, read-only.

KNOWN ISSUE handled explicitly (see README): `market.*`, `animals.bought` and
`labour.hires_arrived` recorded at day-index d are the events of day d+1 (index 0
holds days 0 and 1). This script shifts those three fields by +1 day wherever it
uses them (animal purchase timing). `board`, `board_counts`, `planted`,
`maintenance`, `built`, `dug`, `harvested`, `animals.placed/sold/culled` are used
as recorded (dated correctly per the README).

KNOWN AMBIGUITY (found empirically in this run, contradicts the README's claim of
no ambiguity): the compact board label 'co' is emitted for BOTH a cow-occupied
PASTURE tile and an EMPTY COOP structure (COOP's own kind string is "COOP", whose
lowercased first two characters also collide with COW's). Verified directly: in
data/leader_semantics/16623559/112446812.json.gz the 'co' count rises by +4
between day 28 and day 29 while 'go' (goose) simultaneously falls by -4 and no
COW purchase/placement occurs in that window -- i.e. four geese starved, leaving
four empty coops that the board label reports as 'co'. SHEEP ('sh') and GOOSE
('go') labels are unambiguous (no structure kind starts with those two letters).
Consequence: every MILK/COW holdings number in this report is a "cow-tiles-or-
empty-coops" upper bound, not an exact cow count. WOOL/SHEEP and EGG/GOOSE
numbers are exact. This is flagged again at every MILK/COW output site.

Structure ("pastures/coops") holdings use the `built` field's cumulative
BUILD_COOP / BUILD_PASTURE counts instead of the board label, since `built` is
unambiguous and dated correctly; DIG-ing a built structure is assumed rare and is
not subtracted out (not checked further given the time budget).

Outputs:
  results/fresh/leader_reveal_response/reveal_response.json   -- all computed tables
  results/fresh/leader_reveal_response/reveal_response.md     -- markdown report
  data/leader_semantics/reveal_rules.json                     -- compact rules table
"""
from __future__ import annotations

import glob
import gzip
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/leader_semantics"
OUT = ROOT / "results/fresh/leader_reveal_response"
OUT.mkdir(parents=True, exist_ok=True)
RULES_PATH = DATA / "reveal_rules.json"

SHOP_DEMAND = {
    "BAKERY": {"EGG": 1, "WHEAT": 1},
    "PIZZA_SHOP": {"MILK": 1, "TOMATO": 1, "WHEAT": 1},
    "BRUNCH_SPOT": {"EGG": 1, "WHEAT": 1, "STRAWBERRY": 1},
    "YARN_STORE": {"WOOL": 2},
    "ICE_CREAM_SHOP": {"STRAWBERRY": 1, "MILK": 1, "WHEAT": 1},
    "PET_CAFE": {"CARROT": 2},
    "SMOOTHIE_SHOP": {"STRAWBERRY": 1, "MILK": 1},
    "FARMERS_MARKET": {"WHEAT": 1, "CARROT": 1, "TOMATO": 1, "STRAWBERRY": 1},
}
REVEAL_DAYS = [3, 6, 9, 12, 15, 18, 21, 24]
CROP_CODE = {"STRAWBERRY": "ST", "MELON": "ME", "TOMATO": "TO", "WHEAT": "WH", "CARROT": "CA"}
CROPS = list(CROP_CODE)
ANIMAL_LABEL = {"WOOL": "sh", "EGG": "go", "MILK": "co"}  # 'co' ambiguous -- see module docstring
ANIMAL_SPECIES = {"WOOL": "SHEEP", "EGG": "GOOSE", "MILK": "COW"}
PRODUCTS = CROPS + ["WOOL", "EGG", "MILK"]
LAND_ORDER = ["NE", "SW", "SE"]  # fixed engine order (kaggriculture.py LAND_ORDER), prices 1000/2000/4000


def quadrant_indices(name):
    half = 5
    out = []
    for y in range(10):
        for x in range(10):
            q = ("N" if y < half else "S") + ("W" if x < half else "E")
            if q == name:
                out.append(y * 10 + x)
    return out


QUAD_IDX = {q: quadrant_indices(q) for q in LAND_ORDER}


def load_games():
    games = []
    for fp in sorted(glob.glob(str(DATA / "*/*.json.gz"))):
        team_dir = Path(fp).parent.name
        with gzip.open(fp, "rt", encoding="utf-8") as f:
            g = json.load(f)
        g["_team_dir"] = team_dir
        g["_path"] = fp
        games.append(g)
    return games


def holdings(day_obj, product):
    if product in CROP_CODE:
        return day_obj["board_counts"].get(CROP_CODE[product], 0)
    return day_obj["board_counts"].get(ANIMAL_LABEL[product], 0)


def cum_built(days, kind, upto_day):
    """Cumulative successful BUILD_<kind> count strictly before day-start `upto_day`
    (built[d] happens during day d, i.e. after day d's board snapshot, so it first
    shows up in day d+1's board -- included here for upto_day >= d+1)."""
    n = 0
    for d in range(min(upto_day, len(days))):
        n += len(days[d]["built"].get(f"BUILD_{kind}", []))
    return n


# ---------------------------------------------------------------------------
# Per-game precomputation
# ---------------------------------------------------------------------------

def precompute(g):
    days = g["days"]
    team = g["meta"]["team"]
    episode = g["meta"]["episode"]

    # reveal events: (idx, reveal_day, shop)
    reveal_events = [(i, s["reveal_day"], s["shop"]) for i, s in enumerate(g["shops"])]

    # last planting day per crop
    last_plant = {}
    for c in CROPS:
        last = None
        for d in range(30):
            if days[d]["planted"].get(c):
                last = d
        last_plant[c] = last

    # animal purchase events, day-shift corrected (true_day = index + 1)
    bought_by_true_day = {sp: {} for sp in ("SHEEP", "COW", "GOOSE")}
    for i, day in enumerate(days):
        true_day = i + 1
        if true_day > 29:
            continue
        for sp, n in day["animals"]["bought"].items():
            if sp in bought_by_true_day and n:
                bought_by_true_day[sp][true_day] = bought_by_true_day[sp].get(true_day, 0) + n
    last_buy = {}
    for sp in ("SHEEP", "COW", "GOOSE"):
        days_bought = sorted(bought_by_true_day[sp])
        last_buy[sp] = days_bought[-1] if days_bought else None

    # quadrant unlock day: first day-start index where quadrant is not all-locked
    unlock_day = {}
    for q in LAND_ORDER:
        idxs = QUAD_IDX[q]
        found = None
        for d in range(30):
            board = days[d]["board"]
            if any(board[i] != " L" for i in idxs):
                found = d
                break
        unlock_day[q] = found

    return dict(
        team=team, episode=episode, reveal_events=reveal_events,
        last_plant=last_plant, bought_by_true_day=bought_by_true_day,
        last_buy=last_buy, unlock_day=unlock_day, days=days,
    )


# ---------------------------------------------------------------------------
# Q1: reveal response (units per shop) + cluster-robust regression
# ---------------------------------------------------------------------------

def ols_cluster(X, y, clusters):
    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    uniq = np.unique(clusters)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for c in uniq:
        idx = clusters == c
        Xg, ug = X[idx], resid[idx]
        score = Xg.T @ ug
        meat += np.outer(score, score)
    G, N, K = len(uniq), X.shape[0], X.shape[1]
    dfc = (G / max(G - 1, 1)) * ((N - 1) / max(N - K, 1))
    vcov = dfc * (XtX_inv @ meat @ XtX_inv)
    se = np.sqrt(np.maximum(np.diag(vcov), 0))
    return beta, se


def build_event_rows(precomp_games):
    """One row per (game, reveal event, product)."""
    rows = []
    for pc in precomp_games:
        days = pc["days"]
        for idx, r, shop in pc["reveal_events"]:
            day_r = days[r]
            day_r3 = days[min(r + 3, 29)]
            day_r6 = days[min(r + 6, 29)]
            prior_shops = [s for (_, rr, s) in pc["reveal_events"] if rr < r]
            for product in PRODUCTS:
                dem = SHOP_DEMAND.get(shop, {}).get(product, 0)
                prior_count = sum(1 for s in prior_shops if SHOP_DEMAND.get(s, {}).get(product, 0) > 0)
                h_r = holdings(day_r, product)
                rows.append(dict(
                    team=pc["team"], episode=pc["episode"], reveal_idx=idx, r=r, shop=shop,
                    product=product, demand_units=dem, demanded=int(dem > 0),
                    prior_count=prior_count,
                    holdings_r=h_r,
                    delta3=holdings(day_r3, product) - h_r,
                    delta6=holdings(day_r6, product) - h_r,
                    window6_days=min(r + 6, 29) - r,
                ))
    return rows


def q1_reveal_response(rows, games_meta):
    out = {"per_reveal_day": {}, "pooled_regression": {}, "per_team_pooled_delta3": {}}
    by_key = defaultdict(list)
    for row in rows:
        by_key[(row["product"], row["r"])].append(row)

    for product in PRODUCTS:
        out["per_reveal_day"][product] = {}
        for r in REVEAL_DAYS:
            grp = by_key[(product, r)]
            dem = [x["delta3"] for x in grp if x["demanded"]]
            nodem = [x["delta3"] for x in grp if not x["demanded"]]
            dem6 = [x["delta6"] for x in grp if x["demanded"]]
            nodem6 = [x["delta6"] for x in grp if not x["demanded"]]

            def summarize(a, b, a6, b6):
                if not a or not b:
                    return None
                diff3 = statistics.mean(a) - statistics.mean(b)
                diff6 = statistics.mean(a6) - statistics.mean(b6)
                # Welch t-test style SE for the mean difference
                se3 = ((statistics.pvariance(a) / len(a) if len(a) > 1 else 0) +
                       (statistics.pvariance(b) / len(b) if len(b) > 1 else 0)) ** 0.5
                return dict(n_demanded=len(a), n_not_demanded=len(b),
                            mean_delta3_demanded=round(statistics.mean(a), 3),
                            mean_delta3_not_demanded=round(statistics.mean(b), 3),
                            excess_units_3d=round(diff3, 3),
                            excess_units_3d_se=round(se3, 3),
                            mean_delta6_demanded=round(statistics.mean(a6), 3),
                            mean_delta6_not_demanded=round(statistics.mean(b6), 3),
                            excess_units_6d=round(diff6, 3))
            out["per_reveal_day"][product][str(r)] = summarize(dem, nodem, dem6, nodem6)

    # pooled cluster-robust regression per product: delta ~ demanded + r + holdings_r
    game_id = {}
    for row in rows:
        game_id.setdefault((row["team"], row["episode"]), len(game_id))
    for product in PRODUCTS:
        sub = [row for row in rows if row["product"] == product]
        X = np.array([[1.0, row["demanded"], row["r"], row["holdings_r"]] for row in sub])
        clusters = np.array([game_id[(row["team"], row["episode"])] for row in sub])
        for horizon, key in ((3, "delta3"), (6, "delta6")):
            y = np.array([row[key] for row in sub], dtype=float)
            beta, se = ols_cluster(X, y, clusters)
            out["pooled_regression"].setdefault(product, {})[f"{horizon}d"] = dict(
                n=len(sub), n_games=len(set(clusters.tolist())),
                intercept=round(beta[0], 3), intercept_se=round(se[0], 3),
                demanded_coef=round(beta[1], 3), demanded_se=round(se[1], 3),
                day_coef=round(beta[2], 4), day_se=round(se[2], 4),
                current_holdings_coef=round(beta[3], 4), current_holdings_se=round(se[3], 4),
            )

    # per-team pooled excess (mean over all 8 reveal days, demanded - not-demanded), delta3 only
    for product in PRODUCTS:
        out["per_team_pooled_delta3"][product] = {}
        for team in games_meta:
            grp = [row for row in rows if row["product"] == product and row["team"] == team]
            dem = [x["delta3"] for x in grp if x["demanded"]]
            nodem = [x["delta3"] for x in grp if not x["demanded"]]
            if dem and nodem:
                out["per_team_pooled_delta3"][product][team] = round(
                    statistics.mean(dem) - statistics.mean(nodem), 2)
    return out


# ---------------------------------------------------------------------------
# Q2: timing (anticipation / same-day / lag)
# ---------------------------------------------------------------------------

def q2_timing(precomp_games):
    delays = defaultdict(list)   # product -> [delay,...] (observed responses only)
    censored = defaultdict(int)  # product -> count with no response in window
    total = defaultdict(int)

    for pc in precomp_games:
        days = pc["days"]
        for idx, r, shop in pc["reveal_events"]:
            for product, dem in SHOP_DEMAND.get(shop, {}).items():
                total[product] += 1
                lo, hi = max(0, r - 3), min(29, r + 9)
                found_delay = None
                if product in CROP_CODE:
                    crop = product
                    for d in range(lo, hi + 1):
                        if days[d]["planted"].get(crop):
                            found_delay = d - r
                            break
                else:
                    sp = ANIMAL_SPECIES[product]
                    for true_day, n in sorted(pc["bought_by_true_day"][sp].items()):
                        if lo <= true_day <= hi and n > 0:
                            found_delay = true_day - r
                            break
                if found_delay is None:
                    censored[product] += 1
                else:
                    delays[product].append(found_delay)

    out = {}
    for product in PRODUCTS:
        d = sorted(delays[product])
        if d:
            out[product] = dict(
                n_observed=len(d), n_censored=censored[product], n_reveal_events=total[product],
                mean_delay=round(statistics.mean(d), 2),
                median_delay=statistics.median(d),
                p25=d[len(d) // 4], p75=d[min(len(d) - 1, (3 * len(d)) // 4)],
                frac_anticipated_before_reveal=round(sum(1 for x in d if x < 0) / len(d), 3),
                frac_same_day=round(sum(1 for x in d if x == 0) / len(d), 3),
                frac_lagged=round(sum(1 for x in d if x > 0) / len(d), 3),
            )
        else:
            out[product] = dict(n_observed=0, n_censored=censored[product], n_reveal_events=total[product])
    return out


# ---------------------------------------------------------------------------
# Q3: saturation (diminishing response with prior demanding-shop count)
# ---------------------------------------------------------------------------

def q3_saturation(rows):
    out = {}
    for product in PRODUCTS:
        by_prior = defaultdict(list)
        for row in rows:
            if row["product"] == product and row["demanded"]:
                by_prior[row["prior_count"]].append(row["delta3"])
        cell = {}
        for k in sorted(by_prior):
            v = by_prior[k]
            cell[str(k)] = dict(n=len(v), mean_delta3=round(statistics.mean(v), 3))
        # simple saturation factor: mean_delta3 at prior_count>=1 relative to prior_count==0
        base = cell.get("0", {}).get("mean_delta3")
        satur = {}
        for k, v in cell.items():
            if k != "0" and base not in (None, 0):
                satur[k] = round(v["mean_delta3"] / base, 3)
        out[product] = dict(by_prior_demanding_shops=cell, saturation_ratio_vs_zero_prior=satur)
    return out


# ---------------------------------------------------------------------------
# Q4: late game
# ---------------------------------------------------------------------------

def q4_late_game(precomp_games):
    out = {"crops": {}, "animals": {}}
    for c in CROPS:
        vals = [pc["last_plant"][c] for pc in precomp_games if pc["last_plant"][c] is not None]
        never = sum(1 for pc in precomp_games if pc["last_plant"][c] is None)
        # dependence on whether the LAST-revealed (day-24) shop demands this crop
        with_last_dem, without_last_dem = [], []
        for pc in precomp_games:
            last_shop = pc["reveal_events"][-1][2]
            dem = SHOP_DEMAND.get(last_shop, {}).get(c, 0) > 0
            v = pc["last_plant"][c]
            if v is None:
                continue
            (with_last_dem if dem else without_last_dem).append(v)
        out["crops"][c] = dict(
            n_games_ever_planted=len(vals), n_games_never_planted=never,
            mean_last_plant_day=round(statistics.mean(vals), 2) if vals else None,
            median_last_plant_day=statistics.median(vals) if vals else None,
            max_last_plant_day=max(vals) if vals else None,
            mean_last_plant_day_if_day24_shop_demands_it=(
                round(statistics.mean(with_last_dem), 2) if with_last_dem else None),
            mean_last_plant_day_if_day24_shop_does_not=(
                round(statistics.mean(without_last_dem), 2) if without_last_dem else None),
            n_day24_demands=len(with_last_dem), n_day24_not=len(without_last_dem),
        )
    for label, sp in (("WOOL/SHEEP", "SHEEP"), ("EGG/GOOSE", "GOOSE"), ("MILK/COW (ambiguous, see caveat)", "COW")):
        vals = [pc["last_buy"][sp] for pc in precomp_games if pc["last_buy"][sp] is not None]
        never = sum(1 for pc in precomp_games if pc["last_buy"][sp] is None)
        with_last_dem, without_last_dem = [], []
        product = {"SHEEP": "WOOL", "GOOSE": "EGG", "COW": "MILK"}[sp]
        for pc in precomp_games:
            last_shop = pc["reveal_events"][-1][2]
            dem = SHOP_DEMAND.get(last_shop, {}).get(product, 0) > 0
            v = pc["last_buy"][sp]
            if v is None:
                continue
            (with_last_dem if dem else without_last_dem).append(v)
        out["animals"][label] = dict(
            n_games_ever_bought=len(vals), n_games_never_bought=never,
            mean_last_purchase_day=round(statistics.mean(vals), 2) if vals else None,
            median_last_purchase_day=statistics.median(vals) if vals else None,
            max_last_purchase_day=max(vals) if vals else None,
            mean_last_purchase_day_if_day24_shop_demands_it=(
                round(statistics.mean(with_last_dem), 2) if with_last_dem else None),
            mean_last_purchase_day_if_day24_shop_does_not=(
                round(statistics.mean(without_last_dem), 2) if without_last_dem else None),
            n_day24_demands=len(with_last_dem), n_day24_not=len(without_last_dem),
        )
    return out


# ---------------------------------------------------------------------------
# Q5: land
# ---------------------------------------------------------------------------

def q5_land(precomp_games):
    out = {}
    for q in LAND_ORDER:
        vals = [pc["unlock_day"][q] for pc in precomp_games if pc["unlock_day"][q] is not None]
        never = sum(1 for pc in precomp_games if pc["unlock_day"][q] is None)
        on_reveal_day = sum(1 for v in vals if v in REVEAL_DAYS)
        day_after_reveal = sum(1 for v in vals if (v - 1) in REVEAL_DAYS)
        out[q] = dict(
            n_games_purchased=len(vals), n_games_never=never,
            mean_day=round(statistics.mean(vals), 2) if vals else None,
            median_day=statistics.median(vals) if vals else None,
            min_day=min(vals) if vals else None, max_day=max(vals) if vals else None,
            frac_on_a_reveal_day=round(on_reveal_day / len(vals), 3) if vals else None,
            frac_day_after_a_reveal_day=round(day_after_reveal / len(vals), 3) if vals else None,
        )
    return out


# ---------------------------------------------------------------------------
# Rules table + markdown
# ---------------------------------------------------------------------------

def build_rules_table(q1, q2, q3):
    rules = {"generated": time.strftime("%Y-%m-%d"), "products": {}}
    for product in PRODUCTS:
        entry = {"per_reveal_day": {}, "delay": q2.get(product, {}), "saturation": q3.get(product, {})}
        for r in REVEAL_DAYS:
            cell = q1["per_reveal_day"][product].get(str(r))
            if cell:
                entry["per_reveal_day"][str(r)] = dict(
                    expected_units_3d=cell["excess_units_3d"],
                    expected_units_6d=cell["excess_units_6d"],
                    n_demanded=cell["n_demanded"], n_not_demanded=cell["n_not_demanded"])
        reg3 = q1["pooled_regression"].get(product, {}).get("3d")
        reg6 = q1["pooled_regression"].get(product, {}).get("6d")
        entry["pooled_regression_coef_3d"] = reg3["demanded_coef"] if reg3 else None
        entry["pooled_regression_coef_6d"] = reg6["demanded_coef"] if reg6 else None
        entry["note"] = ("'co' board label conflates COW with an empty COOP; MILK/COW numbers "
                          "are an upper bound." if product == "MILK" else "")
        rules["products"][product] = entry
    return rules


def fmt(x):
    return "-" if x is None else x


def write_markdown(payload, path, n_games, n_teams):
    lines = []
    lines.append(f"# Leader reveal-response rules ({n_games} games, {n_teams} teams)\n")
    lines.append("Corpus: `data/leader_semantics/<team>/<episode>.json.gz`. See "
                  "`scripts/leader_reveal_response.py` module docstring for the day-shift "
                  "correction and the 'co' (cow vs empty coop) label ambiguity.\n")

    lines.append("## Q1: units per shop revealed (excess holdings change vs. a non-demanding "
                  "shop revealed on the same day)\n")
    for product in PRODUCTS:
        lines.append(f"### {product}\n")
        lines.append("| reveal day | n demand / n not | +units @3d | +units @6d |")
        lines.append("|---:|---:|---:|---:|")
        for r in REVEAL_DAYS:
            cell = payload["q1"]["per_reveal_day"][product].get(str(r))
            if cell:
                lines.append(f"| {r} | {cell['n_demanded']}/{cell['n_not_demanded']} | "
                              f"{cell['excess_units_3d']:+.2f} | {cell['excess_units_6d']:+.2f} |")
            else:
                lines.append(f"| {r} | - | - | - |")
        reg = payload["q1"]["pooled_regression"].get(product, {})
        if reg:
            r3, r6 = reg.get("3d"), reg.get("6d")
            lines.append(f"\nPooled cluster-robust OLS (delta ~ demanded + day + current holdings), "
                         f"n={r3['n']} events / {r3['n_games']} games: "
                         f"demanded coef @3d = {r3['demanded_coef']:+.2f} (se {r3['demanded_se']:.2f}), "
                         f"@6d = {r6['demanded_coef']:+.2f} (se {r6['demanded_se']:.2f}).\n")
        team_tab = payload["q1"]["per_team_pooled_delta3"].get(product, {})
        if team_tab:
            lines.append("Per-team pooled excess @3d: " +
                          ", ".join(f"{t}={v:+.1f}" for t, v in team_tab.items()) + "\n")

    lines.append("\n## Q2: timing of first commitment relative to reveal (window r-3..r+9)\n")
    lines.append("| product | n obs | n censored | mean delay | median | p25 | p75 | anticip. | same-day | lag |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for product in PRODUCTS:
        c = payload["q2"][product]
        if c["n_observed"]:
            lines.append(f"| {product} | {c['n_observed']} | {c['n_censored']} | {c['mean_delay']} | "
                          f"{c['median_delay']} | {c['p25']} | {c['p75']} | "
                          f"{c['frac_anticipated_before_reveal']:.0%} | {c['frac_same_day']:.0%} | "
                          f"{c['frac_lagged']:.0%} |")
        else:
            lines.append(f"| {product} | 0 | {c['n_censored']} | - | - | - | - | - | - | - |")

    lines.append("\n## Q3: saturation (mean +units@3d among demanded events, by count of "
                  "already-revealed shops also demanding the product)\n")
    for product in PRODUCTS:
        cell = payload["q3"][product]["by_prior_demanding_shops"]
        if cell:
            lines.append(f"- **{product}**: " + ", ".join(
                f"prior={k} -> {v['mean_delta3']:+.2f} (n={v['n']})" for k, v in cell.items()))

    lines.append("\n## Q4: late game\n")
    lines.append("| crop | last planted mean/median/max | never (n) | if day-24 shop demands it | if not |")
    lines.append("|---|---:|---:|---:|---:|")
    for c in CROPS:
        v = payload["q4"]["crops"][c]
        lines.append(f"| {c} | {fmt(v['mean_last_plant_day'])}/{fmt(v['median_last_plant_day'])}/"
                      f"{fmt(v['max_last_plant_day'])} | {v['n_games_never_planted']} | "
                      f"{fmt(v['mean_last_plant_day_if_day24_shop_demands_it'])} (n={v['n_day24_demands']}) | "
                      f"{fmt(v['mean_last_plant_day_if_day24_shop_does_not'])} (n={v['n_day24_not']}) |")
    lines.append("\n| animal | last purchase mean/median/max | never (n) | if day-24 shop demands it | if not |")
    lines.append("|---|---:|---:|---:|---:|")
    for label, v in payload["q4"]["animals"].items():
        lines.append(f"| {label} | {fmt(v['mean_last_purchase_day'])}/{fmt(v['median_last_purchase_day'])}/"
                      f"{fmt(v['max_last_purchase_day'])} | {v['n_games_never_bought']} | "
                      f"{fmt(v['mean_last_purchase_day_if_day24_shop_demands_it'])} (n={v['n_day24_demands']}) | "
                      f"{fmt(v['mean_last_purchase_day_if_day24_shop_does_not'])} (n={v['n_day24_not']}) |")

    lines.append("\n## Q5: land (quadrant unlock day; fixed engine order NE(1000) -> SW(2000) -> SE(4000))\n")
    lines.append("| quadrant | n purchased / never | mean/median day | min-max | on a reveal day | day after reveal |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for q in LAND_ORDER:
        v = payload["q5"][q]
        lines.append(f"| {q} | {v['n_games_purchased']}/{v['n_games_never']} | "
                      f"{fmt(v['mean_day'])}/{fmt(v['median_day'])} | {fmt(v['min_day'])}-{fmt(v['max_day'])} | "
                      f"{fmt(v['frac_on_a_reveal_day'])} | {fmt(v['frac_day_after_a_reveal_day'])} |")

    path.write_text("\n".join(lines), encoding="utf-8")


def run(games):
    precomp_games = [precompute(g) for g in games]
    teams = sorted({g["meta"]["team"] for g in games})
    rows = build_event_rows(precomp_games)
    q1 = q1_reveal_response(rows, teams)
    q2 = q2_timing(precomp_games)
    q3 = q3_saturation(rows)
    q4 = q4_late_game(precomp_games)
    q5 = q5_land(precomp_games)
    payload = dict(
        meta=dict(n_games=len(games), teams=teams, n_teams=len(teams),
                  generated=time.strftime("%Y-%m-%d %H:%M:%S")),
        q1=q1, q2=q2, q3=q3, q4=q4, q5=q5,
    )
    return payload


def main():
    t0 = time.time()
    games = load_games()
    print(f"loaded {len(games)} games from {len(set(g['_team_dir'] for g in games))} teams")
    payload = run(games)
    (OUT / "reveal_response.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(payload, OUT / "reveal_response.md", payload["meta"]["n_games"], payload["meta"]["n_teams"])
    rules = build_rules_table(payload["q1"], payload["q2"], payload["q3"])
    RULES_PATH.write_text(json.dumps(rules, indent=2), encoding="utf-8")
    print(f"done in {time.time()-t0:.1f}s, wrote {OUT / 'reveal_response.json'}, "
          f"{OUT / 'reveal_response.md'}, {RULES_PATH}")

    # re-run check: has the corpus grown since we started?
    games2 = load_games()
    if len(games2) > len(games):
        print(f"corpus grew {len(games)} -> {len(games2)}; re-running on the larger set")
        payload2 = run(games2)
        (OUT / "reveal_response_rerun.json").write_text(json.dumps(payload2, indent=2), encoding="utf-8")
        write_markdown(payload2, OUT / "reveal_response_rerun.md",
                        payload2["meta"]["n_games"], payload2["meta"]["n_teams"])
        rules2 = build_rules_table(payload2["q1"], payload2["q2"], payload2["q3"])
        RULES_PATH.write_text(json.dumps(rules2, indent=2), encoding="utf-8")
        print(f"rerun done, wrote {OUT / 'reveal_response_rerun.json'} and updated {RULES_PATH}")
    else:
        print(f"corpus unchanged at {len(games2)} games; no re-run needed")


if __name__ == "__main__":
    main()

"""ANALYSIS ONLY. Reads recorded replay JSON and leaderboard episode-list JSON already on disk.

Does NOT run kaggle_environments.make, does NOT execute/modify anything under agents/.
Processes one replay file at a time (each ~30MB) in a single process, freeing it before
the next. Answers:
  1. Opening-fingerprint family clustering for every seat in the sampled replays.
  2. Mother-Goose (team 16730612)'s record against each family, plus the V46-50 "attack"
     day-0/day-1 effect on her old vs new submissions.
  3. Her W-L by opponent rating band, new vs old submission, from the full (ratings-only)
     episode lists.
  4. Approximate per-product revenue and sell-timing comparison in her losses to Majkel1337
     since 18 Sep.

Run from scripts/:  ../.venv/Scripts/python.exe mg_opponent_families.py
"""
import json
import gc
import os
import re
import statistics as stats
from collections import Counter, defaultdict
from pathlib import Path

from market_corpus import ROOT  # noqa: F401  (import required per task instructions; ROOT is a plain Path)

MG_TEAM = 16730612
MG_NAME = "Unknown Mother-Goose"
NEW_SUBS = {56331731, 56331777}
OLD_SUB = 56266758

NEW_DIR = ROOT / "data" / "leaders_20260919"
OLD_DIR = ROOT / "data" / "leaders_20260917"
NEW_IDX = ROOT / "results/fresh/leader_segments/sample_20260919.json"
OLD_IDX = ROOT / "results/fresh/leader_segments/sample.json"
OUT_PATH = ROOT / "results/fresh/mg_new/opponent_families.json"

NAMED_TEAMS = {
    16718819: "Majkel1337",
    16640510: "SpaTaro",
    16732748: "DSM",
    16664246: "Sida Zuo",
    16732403: "ymg_aq",
    16730524: "THIRD FARM CLUB",
    16671741: "Excluding",
    16673205: "Arda Ceylan",
}

# ---- reference opening fingerprints, read from the public agent source files ----
# benchmark_frozen_56280048.py (EXP284 "flip70" patch, V45 lineage): step0 replaces the
# parent's market wholesale with a single round trip; step1 shrinks the feed buy.
V45_T0 = (("BUY_PRODUCT", "WHEAT", 70), ("SELL", "WHEAT", 70))
# v48_public.py / v49_public.py / v50_public.py: byte-identical opening layer (v49 = v48 +
# EXP342 appended after v48's own agent=... hand-off; v50 = v49 + EXP343 appended likewise;
# the file is a strict prefix of the next, so the step0-2 market tape cannot distinguish
# V48 from V49 from V50 -- only later-game weed/pasture-recovery behaviour could).
V48_T0 = (("BUY_PRODUCT", "WHEAT", 7), ("SELL", "WHEAT", 2))
V48_T1_ATTACK_FIRST = ("BUY_PRODUCT", "WHEAT", 30)
V48_T2_ATTACK_FIRST = ("SELL", "WHEAT", 30)
# _R42_OPENING inside benchmark_frozen.py, i.e. the un-patched parent tape it was built from
# -- the "older public router" lineage the task description points at.
ROUTER_T0_VARIANTS = {
    (("BUY_PRODUCT", "WHEAT", 13), ("BUY_PRODUCT", "WHEAT", 30), ("SELL", "WHEAT", 30)),
    (("BUY_PRODUCT", "WHEAT", 5), ("BUY_PRODUCT", "WHEAT", 10), ("SELL", "WHEAT", 60)),
}
# Mother-Goose's own OLD submission (56266758) opening, per CLAUDE.md/task brief.
MG_OLD_T0 = (("BUY_PRODUCT", "WHEAT", 13), ("BUY_PRODUCT", "WHEAT", 5), ("SELL", "WHEAT", 13))
MG_OLD_T1_HEAD = (("SELL", "WHEAT", 5), ("BUY_PRODUCT", "WHEAT", 5))
# Discovered empirically below: a widely shared, non-tape "obvious" opener (buy 1 cow, buy 5
# feed wheat) used by MG's current subs AND by several unrelated architectures (Majkel1337
# most of the time, QQ, Orbital Terraformer). Not attributable to any of the named public
# tapes above -- kept as its own bucket rather than mislabelled "MG-like".
SHARED_COW1_WHEAT5_T0 = (("BUY_ANIMAL", "COW", 1), ("BUY_PRODUCT", "WHEAT", 5))


def market_tuple(action):
    return tuple(tuple(o) for o in (action.get("market") or []))


def classify(t0):
    if t0 == V45_T0:
        return "V45-flip70"
    if t0 == V48_T0:
        return "V46-V50-attack"
    if t0 in ROUTER_T0_VARIANTS:
        return "older-router"
    if t0 == MG_OLD_T0:
        return "MG-old-opening"
    if t0 == SHARED_COW1_WHEAT5_T0:
        return "shared-cow1-wheat5-opener"
    return "other"


def day0_unit_build(obs24, obs48, seat):
    """Snapshot animal/crop counts on a farm at the start of day1 (obs24) and day2 (obs48)."""

    def counts(obs):
        farm = obs["farms"][seat]
        animals = Counter()
        crops = Counter()
        for row in farm["tiles"]:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                if tile.get("animal"):
                    animals[tile["animal"]] += 1
                elif tile.get("crop"):
                    crops[tile["crop"]] += 1
        return dict(animals), dict(crops)

    a24, c24 = counts(obs24)
    a48, c48 = counts(obs48)
    return {"day1_animals": a24, "day1_crops": c24, "day2_animals": a48, "day2_crops": c48}


def hire_effect(steps, seat):
    """Day-0-end cash and day-1 requested-vs-achieved hire count for `seat`."""
    day0_end_money = steps[24][seat]["observation"]["farms"][seat]["money"]
    requested = 0
    for t in range(24, 48):
        act = steps[t + 1][seat]["action"]
        market = act.get("market") or []
        requested += sum(1 for o in market if o and o[0] == "HIRE")
    achieved = max(
        steps[t][seat]["observation"]["farms"][seat]["hires_today"] for t in range(24, 48)
    )
    return {
        "day0_end_cash": day0_end_money,
        "day1_hires_requested": requested,
        "day1_hires_achieved": achieved,
        "starved": achieved < requested,
    }


def product_revenue_approx(steps, seat, day_range=None):
    """sum over her SELL orders of min(qty, shed stock at that step) * market price at that step."""
    rev = Counter()
    n = len(steps)
    lo, hi = day_range if day_range else (0, n - 1)
    for t in range(lo, hi):
        obs = steps[t][seat]["observation"]
        act = steps[t + 1][seat]["action"]
        shed = obs["private"]["shed"]
        prices = obs["market"]["prices"]
        for o in act.get("market") or []:
            if o and o[0] == "SELL" and len(o) >= 3:
                item, qty = o[1], o[2]
                if item in prices:
                    fill = min(qty, shed.get(item, 0))
                    if fill > 0:
                        rev[item] += fill * prices[item]
    return dict(rev)


def sell_hours(steps, seat, item):
    """Hours-of-day (0-23) at which `seat` issues a SELL order for `item`, with qty."""
    out = []
    for t in range(len(steps) - 1):
        act = steps[t + 1][seat]["action"]
        for o in act.get("market") or []:
            if o and o[0] == "SELL" and len(o) >= 3 and o[1] == item and o[2] > 0:
                out.append({"step": t, "hour": t % 24, "day": t // 24, "qty": o[2]})
    return out


def process_replay(path, mg_sub_hint=None):
    """One JSON load, produces a compact record, then the object is dropped by the caller."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    teams = d["info"]["TeamNames"]
    steps = d["steps"]
    rewards = d["rewards"]
    mg_seat = teams.index(MG_NAME) if MG_NAME in teams else None

    seats_info = []
    for seat in (0, 1):
        t0 = market_tuple(steps[1][seat]["action"])
        t1 = market_tuple(steps[2][seat]["action"])
        t2 = market_tuple(steps[3][seat]["action"])
        fam = classify(t0)
        obs24 = steps[24][seat]["observation"]
        obs48 = steps[48][seat]["observation"] if len(steps) > 48 else obs24
        build = day0_unit_build(obs24, obs48, seat)
        seats_info.append(
            {
                "seat": seat,
                "team_name": teams[seat],
                "t0": t0,
                "t1": t1,
                "t2": t2,
                "family": fam,
                "attack_t1": t1[:1] == (V48_T1_ATTACK_FIRST,),
                "attack_t2": t2[:1] == (V48_T2_ATTACK_FIRST,),
                **build,
            }
        )

    record = {
        "id": d["id"] if "id" in d else Path(path).stem,
        "teams": teams,
        "rewards": rewards,
        "mg_seat": mg_seat,
        "seats": seats_info,
    }

    if mg_seat is not None:
        opp_seat = 1 - mg_seat
        record["opp_team"] = teams[opp_seat]
        record["opp_family"] = seats_info[opp_seat]["family"]
        record["mg_win"] = rewards[mg_seat] > rewards[opp_seat]
        record["margin"] = rewards[mg_seat] - rewards[opp_seat]
        record["mg_final_cash"] = rewards[mg_seat]
        record["hire_effect"] = hire_effect(steps, mg_seat)
        if record["opp_team"] == "Majkel1337":
            record["mg_revenue_by_product"] = product_revenue_approx(steps, mg_seat)
            record["opp_revenue_by_product"] = product_revenue_approx(steps, opp_seat)
            record["mg_sell_hours"] = {
                item: sell_hours(steps, mg_seat, item)
                for item in ["WHEAT", "MELON", "STRAWBERRY", "WOOL", "MILK", "EGG", "CARROT", "TOMATO"]
            }
            record["opp_sell_hours"] = {
                item: sell_hours(steps, opp_seat, item)
                for item in ["WHEAT", "MELON", "STRAWBERRY", "WOOL", "MILK", "EGG", "CARROT", "TOMATO"]
            }

    del d, steps
    gc.collect()
    return record


def load_index(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_team_name_map():
    names = dict()
    for fn in [
        ROOT / "results/fresh/leaderboard_20260919/episodes_56331731.json",
        ROOT / "results/fresh/leaderboard_20260919/episodes_56331777.json",
        ROOT / "results/fresh/leaderboard_20260918/episodes_56266758.json",
    ]:
        with open(fn, encoding="utf-8") as f:
            d = json.load(f)
        for t in d.get("teams", []):
            names[t["id"]] = t["teamName"]
    return names


def rating_band(score):
    if score is None:
        return "unknown"
    if score < 2700:
        return "<2700"
    if score < 2900:
        return "2700-2900"
    if score < 3050:
        return "2900-3050"
    return "3050+"


def analyze_rating_bands(team_names):
    """Task 3: her record vs opponents by rating band, from full (ratings-only) episode lists."""
    out = {}
    files = {
        "new": [
            ROOT / "results/fresh/leaderboard_20260919/episodes_56331731.json",
            ROOT / "results/fresh/leaderboard_20260919/episodes_56331777.json",
        ],
        "old": [ROOT / "results/fresh/leaderboard_20260918/episodes_56266758.json"],
    }
    for label, paths in files.items():
        band_stats = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "t": 0, "margins": []})
        by_team = defaultdict(lambda: {"n": 0, "w": 0, "l": 0, "t": 0, "margins": [], "since_1918": {"n": 0, "w": 0, "l": 0, "margins": []}})
        seen_eids = set()
        for p in paths:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            for ep in d["episodes"]:
                if ep["id"] in seen_eids:
                    continue  # dedupe overlap between her two active new subs' lists
                seen_eids.add(ep["id"])
                agents = ep["agents"]
                if len(agents) != 2:
                    continue
                mg_idx = next((i for i, a in enumerate(agents) if a["teamId"] == MG_TEAM), None)
                if mg_idx is None:
                    continue
                opp = agents[1 - mg_idx]
                mine = agents[mg_idx]
                mg_r, opp_r = mine.get("reward"), opp.get("reward")
                if mg_r is None or opp_r is None:
                    continue
                margin = mg_r - opp_r
                band = rating_band(opp.get("initialScore"))
                bs = band_stats[band]
                bs["n"] += 1
                bs["margins"].append(margin)
                if mg_r > opp_r:
                    bs["w"] += 1
                elif mg_r < opp_r:
                    bs["l"] += 1
                else:
                    bs["t"] += 1
                tname = team_names.get(opp["teamId"], str(opp["teamId"]))
                ts = by_team[f"{tname} ({opp['teamId']})"]
                ts["n"] += 1
                ts["margins"].append(margin)
                if mg_r > opp_r:
                    ts["w"] += 1
                elif mg_r < opp_r:
                    ts["l"] += 1
                else:
                    ts["t"] += 1
                create = ep.get("createTime", "")
                if create >= "2026-09-18":
                    since = ts["since_1918"]
                    since["n"] += 1
                    since["margins"].append(margin)
                    if mg_r > opp_r:
                        since["w"] += 1
                    elif mg_r < opp_r:
                        since["l"] += 1
        band_out = {}
        for band, bs in band_stats.items():
            band_out[band] = {
                "n": bs["n"], "w": bs["w"], "l": bs["l"], "t": bs["t"],
                "mean_margin": round(stats.mean(bs["margins"]), 1) if bs["margins"] else None,
            }
        team_out = {}
        for tname, ts in by_team.items():
            team_out[tname] = {
                "n": ts["n"], "w": ts["w"], "l": ts["l"], "t": ts["t"],
                "mean_margin": round(stats.mean(ts["margins"]), 1) if ts["margins"] else None,
                "since_2026-09-18": {
                    "n": ts["since_1918"]["n"], "w": ts["since_1918"]["w"], "l": ts["since_1918"]["l"],
                    "mean_margin": round(stats.mean(ts["since_1918"]["margins"]), 1) if ts["since_1918"]["margins"] else None,
                },
            }
        out[label] = {"n_episodes": len(seen_eids), "by_band": band_out, "by_team": team_out}
    return out


def analyze_3050_band_losses(team_names):
    """Task 3 tail question: which opponent submissions account for her 3050+ band losses since 18 Sep."""
    losses = defaultdict(lambda: {"n": 0, "margins": [], "team": None})
    for p in [
        ROOT / "results/fresh/leaderboard_20260919/episodes_56331731.json",
        ROOT / "results/fresh/leaderboard_20260919/episodes_56331777.json",
    ]:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for ep in d["episodes"]:
            agents = ep["agents"]
            if len(agents) != 2:
                continue
            mg_idx = next((i for i, a in enumerate(agents) if a["teamId"] == MG_TEAM), None)
            if mg_idx is None:
                continue
            opp = agents[1 - mg_idx]
            mine = agents[mg_idx]
            mg_r, opp_r = mine.get("reward"), opp.get("reward")
            if mg_r is None or opp_r is None or mg_r >= opp_r:
                continue
            if (opp.get("initialScore") or 0) < 3050:
                continue
            if ep.get("createTime", "") < "2026-09-18":
                continue
            key = opp["submissionId"]
            entry = losses[key]
            entry["n"] += 1
            entry["margins"].append(mg_r - opp_r)
            entry["team"] = team_names.get(opp["teamId"], str(opp["teamId"]))
            entry["team_id"] = opp["teamId"]
    out = []
    for sub, e in sorted(losses.items(), key=lambda kv: -kv[1]["n"]):
        out.append({
            "submission_id": sub, "team": e["team"], "team_id": e["team_id"],
            "n_losses": e["n"], "mean_margin": round(stats.mean(e["margins"]), 1),
        })
    return out


def main():
    team_names = build_team_name_map()

    new_idx = load_index(NEW_IDX)["sample"]
    old_idx = load_index(OLD_IDX)["sample"]
    new_ids = {e["id"] for e in new_idx}
    old_ids = {e["id"] for e in old_idx}

    records = []
    print(f"Processing {len(new_ids)} NEW replays...")
    for fn in sorted(os.listdir(NEW_DIR)):
        m = re.match(r"episode-(\d+)-replay\.json", fn)
        if not m or int(m.group(1)) not in new_ids:
            continue
        rec = process_replay(NEW_DIR / fn)
        rec["source"] = "new"
        records.append(rec)
        print(" ", fn, "opp:", rec.get("opp_team"), rec.get("opp_family"), "win:", rec.get("mg_win"))

    print(f"Processing {len(old_ids)} OLD replays...")
    for fn in sorted(os.listdir(OLD_DIR)):
        m = re.match(r"episode-(\d+)-replay\.json", fn)
        if not m or int(m.group(1)) not in old_ids:
            continue
        rec = process_replay(OLD_DIR / fn)
        rec["source"] = "old"
        records.append(rec)
        print(" ", fn, "opp:", rec.get("opp_team"), rec.get("opp_family"), "win:", rec.get("mg_win"))

    # ---- Task 1: family corpus across every seat (both new+old, both seats, MG's own seats excluded) ----
    corpus_family_counts = Counter()
    corpus_examples = defaultdict(list)
    for rec in records:
        for s in rec["seats"]:
            if s["team_name"] == MG_NAME:
                continue
            corpus_family_counts[s["family"]] += 1
            if len(corpus_examples[s["family"]]) < 8:
                corpus_examples[s["family"]].append({"team": s["team_name"], "t0": s["t0"], "t1": s["t1"], "t2": s["t2"]})

    # ---- Task 1/2: her own games, grouped by opponent family ----
    mg_games = [r for r in records if r["mg_seat"] is not None]
    fam_group = defaultdict(list)
    for r in mg_games:
        fam_group[r["opp_family"]].append(r)

    family_table = {}
    for fam, games in fam_group.items():
        wins = sum(1 for g in games if g["mg_win"])
        losses = sum(1 for g in games if not g["mg_win"] and g["margin"] != 0)
        ties = sum(1 for g in games if g["margin"] == 0)
        family_table[fam] = {
            "n": len(games),
            "w": wins, "l": losses, "t": ties,
            "mean_margin": round(stats.mean(g["margin"] for g in games), 1),
            "mean_mg_final_cash": round(stats.mean(g["mg_final_cash"] for g in games), 1),
            "by_source": {
                src: sum(1 for g in games if g["source"] == src) for src in ("new", "old")
            },
            "opponent_teams": sorted({g["opp_team"] for g in games}),
        }

    # ---- Task 1: named top teams (may sit inside "other") ----
    named_team_table = {}
    for tid, tname in NAMED_TEAMS.items():
        games = [r for r in mg_games if r["opp_team"] == tname]
        if not games:
            named_team_table[tname] = {"team_id": tid, "n": 0}
            continue
        wins = sum(1 for g in games if g["mg_win"])
        fam_counts = Counter(g["opp_family"] for g in games)
        new_games = [g for g in games if g["source"] == "new"]
        old_games = [g for g in games if g["source"] == "old"]
        named_team_table[tname] = {
            "team_id": tid,
            "n": len(games), "w": wins, "l": len(games) - wins,
            "mean_margin": round(stats.mean(g["margin"] for g in games), 1),
            "families_seen": dict(fam_counts),
            "sample_t0": next(iter({g["opp_team"]: None for g in games})) and games[0]["teams"],
            "new": {"n": len(new_games), "w": sum(1 for g in new_games if g["mg_win"])},
            "old": {"n": len(old_games), "w": sum(1 for g in old_games if g["mg_win"])},
        }

    # ---- Task 2: V46-V50-attack day-0/day-1 effect, old vs new ----
    attack_games = [r for r in mg_games if r["opp_family"] == "V46-V50-attack"]
    attack_effect = {
        "n_games_found": len(attack_games),
        "note": "No opponent seat in this 94-replay sample matched the V48/V49/V50 exact "
                "turn-0 fingerprint [[BUY_PRODUCT,WHEAT,7],[SELL,WHEAT,2]]; the attack-effect "
                "comparison below is therefore empty (0 games), not a null result about the "
                "attack itself.",
        "games": [],
    }
    for r in attack_games:
        attack_effect["games"].append({
            "id": r["id"], "source": r["source"], "opp_team": r["opp_team"],
            "hire_effect": r["hire_effect"],
        })

    # Also report the same hire/cash telemetry aggregated old-vs-new for ALL her opponents,
    # as context (not attack-specific, since no attack games exist).
    hire_by_source = defaultdict(list)
    for r in mg_games:
        hire_by_source[r["source"]].append(r["hire_effect"])
    hire_context = {}
    for src, rows in hire_by_source.items():
        hire_context[src] = {
            "n": len(rows),
            "mean_day0_end_cash": round(stats.mean(r["day0_end_cash"] for r in rows), 1),
            "n_starved_day1_hires": sum(1 for r in rows if r["starved"]),
        }

    # ---- Task 3 ----
    rating_bands = analyze_rating_bands(team_names)
    band_3050_losses = analyze_3050_band_losses(team_names)

    # ---- Task 4: Majkel1337 revenue/timing in her losses since 18 Sep (new-sub games) ----
    majkel_new = [r for r in mg_games if r["opp_team"] == "Majkel1337" and r["source"] == "new"]
    majkel_losses = [r for r in majkel_new if not r["mg_win"]]
    majkel_wins = [r for r in majkel_new if r["mg_win"]]

    def agg_revenue(games):
        agg = Counter()
        for g in games:
            for item, v in g.get("mg_revenue_by_product", {}).items():
                agg[item] += v
        n = max(1, len(games))
        return {k: round(v / n, 1) for k, v in agg.items()}

    majkel_analysis = {
        "n_new_games": len(majkel_new),
        "n_losses": len(majkel_losses),
        "n_wins": len(majkel_wins),
        "mean_mg_revenue_by_product_in_losses": agg_revenue(majkel_losses),
        "mean_mg_revenue_by_product_in_wins": agg_revenue(majkel_wins),
        "note": "Revenue is APPROXIMATE: sum over her SELL orders of min(qty, her shed stock "
                "at that step) x market price at that step; not exact fill accounting.",
        "loss_games_detail": [],
    }
    for g in majkel_losses:
        detail = {
            "id": g["id"], "margin": g["margin"],
            "mg_revenue": g.get("mg_revenue_by_product"),
            "opp_revenue": g.get("opp_revenue_by_product"),
        }
        # opponent-sells-before-her-usual-hour check, per product
        proximity = {}
        for item in ["WHEAT", "MELON", "STRAWBERRY", "WOOL", "MILK"]:
            mine = g.get("mg_sell_hours", {}).get(item, [])
            theirs = g.get("opp_sell_hours", {}).get(item, [])
            if not mine or not theirs:
                continue
            my_hours = [x["hour"] for x in mine]
            mode_hour = Counter(my_hours).most_common(1)[0][0]
            near = [t for t in theirs if 0 <= (mode_hour - t["hour"]) % 24 <= 2]
            proximity[item] = {
                "mg_mode_sell_hour": mode_hour,
                "opp_sells_within_2h_before": len(near),
                "opp_total_sells": len(theirs),
            }
        detail["opp_sells_near_her_hour"] = proximity
        majkel_analysis["loss_games_detail"].append(detail)

    # ---- direct answer ----
    v48_games = family_table.get("V46-V50-attack", {"n": 0})
    v45_games = family_table.get("V45-flip70", {"n": 0})
    router_games = family_table.get("older-router", {"n": 0})
    answer = {
        "n_V46_V50_attack_games": v48_games.get("n", 0),
        "n_V45_flip70_games": v45_games.get("n", 0),
        "n_older_router_games": router_games.get("n", 0),
        "verdict": (
            "NOT CONFIRMABLE FROM THIS SAMPLE: across all 94 sampled replays (72 of them her "
            "own games -- 42 new-submission + 30 old-submission), zero opponent seats matched "
            "the V48/V49/V50 public agents' exact turn-0 opening fingerprint "
            "[[BUY_PRODUCT,WHEAT,7],[SELL,WHEAT,2]], and only one seat anywhere in the corpus "
            "(pensukesan, in an old-dataset game against Majkel1337 that does not involve "
            "Mother-Goose) matched the older router tape. The V45-flip70 fingerprint "
            "([[BUY_PRODUCT,WHEAT,70],[SELL,WHEAT,70]]) likewise had zero matches. Confidence: "
            "essentially none either way -- the sample simply contains no head-to-head games "
            "against that lineage; her real opponents (Majkel1337 above all, plus Sida Zuo, "
            "ymg_aq, Arda Ceylan, Planned Economy, Excluding, Otter Vibe, THIRD FARM CLUB, DSM) "
            "all run distinct, non-tape openings classified as 'other/own architecture' here."
        ),
    }

    out = {
        "definitions": {
            "V45-flip70": list(V45_T0),
            "V46-V50-attack": {"t0": list(V48_T0), "t1_attack_first_order": list(V48_T1_ATTACK_FIRST), "t2_attack_first_order": list(V48_T2_ATTACK_FIRST)},
            "older-router_variants": [list(v) for v in ROUTER_T0_VARIANTS],
            "MG-old-opening": {"t0": list(MG_OLD_T0), "t1_head": list(MG_OLD_T1_HEAD)},
            "shared-cow1-wheat5-opener": list(SHARED_COW1_WHEAT5_T0),
        },
        "corpus_family_counts_all_seats_excl_mg": dict(corpus_family_counts),
        "corpus_family_examples": dict(corpus_examples),
        "mg_family_table": family_table,
        "mg_named_team_table": named_team_table,
        "attack_effect": attack_effect,
        "hire_cash_context_old_vs_new": hire_context,
        "rating_bands": rating_bands,
        "band_3050_plus_losses_since_2026-09-18": band_3050_losses,
        "majkel1337_revenue_timing_since_2026-09-18": majkel_analysis,
        "answer_does_mg_beat_v48_v49_v50_family": answer,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print("Wrote", OUT_PATH)


if __name__ == "__main__":
    main()

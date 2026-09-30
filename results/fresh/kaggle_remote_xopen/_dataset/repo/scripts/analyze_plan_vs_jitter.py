"""Plan-vs-jitter analysis: how divergent can current top agents' plans get on the
same seed, across the full 30-day game (days 7-29; days 0-6 already shown to be pure
jitter in results/fresh/newphase_20260923/openings/summary.md)?

SEARCH JITTER = actions differ but the underlying PRODUCTION PLAN does not (same
crop/animal counts, same land, same broad schedule; different tile choices/routing).
GENUINE PLAN DIVERGENCE = same shop-reveal prefix -> materially different production.

NO GAME SIMULATION IS RUN. Everything here is parsed from already-recorded replay/tape
JSON, either already on disk or downloaded once with `kaggle competitions replay` and
deleted immediately after parsing.

HARD MEMORY RULE (shared machine, game workers may be running): one Python process, no
multiprocessing/threading. Before every full-replay parse (local OR downloaded) this
script checks psutil.virtual_memory().available >= 2.5 GB, sleeping/retrying otherwise.
Full replays (32 MB DSM files, and downloaded leader replays) are parsed strictly one at
a time; the parsed object is `del`ed and `gc.collect()`ed before the next; any downloaded
raw file is deleted right after parsing. Small local files (mg_tapes/leader_tapes compact
gzip tapes, a few KB each) are loaded in bulk as prior scripts in this repo already do.

Data sources:
  - DSM: 108 full replays, data/dsm_replays/episode-*-replay.json (local, no download).
    A day0-8 cache already exists (results/fresh/newphase_20260923/leader_response/
    dsm_cache.json) but lacks per-hour actions and world seed, so this script reparses
    the local files once (no network) to add those, producing dsm_full_cache.json
    (all 30 days: day_counts/money/quadrants/hands + 719 per-hour action hashes + seed).
  - UMG-old: 584 compact tapes, data/mg_tapes/<sub>/*.json.gz (local, tiny). Reparsed
    once into umg_full_cache.json (all 30 days + action hashes + seed + derived
    quadrants from locked-tile counts).
  - Other 5 current leaders: data/leader_tapes/<teamid>_<sub>/*.json.gz (compact tapes,
    already carry seed, the 8-shop reveal list, and both farms' hourly actions -- no
    download needed for seed/action-divergence/same-seed analysis). Board state (tile
    counts, quadrants, cash-by-day) requires downloading the full replay; per the task,
    this is done for DECEM (16623559) and Vadim Vasilenko (16770421), 40 episodes each,
    and for the current Mother-Goose (16730612) if time allows. Boey and M&M&P&Q get
    action-divergence/seed analysis only (no board download), which is called out in the
    caveats every time board data would be needed but is unavailable for them.

Outputs (under results/fresh/newphase_20260923/plan_jitter/):
  dsm_full_cache.json, umg_full_cache.json, leader_local_cache.json,
  <folder>_full_cache.json (per downloaded leader team)
  analysis.json, summary.md

Usage:
  .venv/Scripts/python.exe scripts/analyze_plan_vs_jitter.py --stage all
  (or --stage dsm|umg|leader-local|leader-full|analysis; --stage leader-full needs
   --team <folder> or defaults to the required DECEM+Vadim pair)
"""
from __future__ import annotations

import argparse
import gc
import gzip
import json
import random
import statistics
import subprocess
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSM_DIR = ROOT / "data/dsm_replays"
MG_DIR = ROOT / "data/mg_tapes"
LEADER_DIR = ROOT / "data/leader_tapes"
KAGGLE = ROOT / ".venv/Scripts/kaggle.exe"

OUT = ROOT / "results/fresh/newphase_20260923/plan_jitter"
RAW_DL = OUT / "_raw_dl"

CROPS = ["WHEAT", "STRAWBERRY", "TOMATO", "CARROT", "MELON"]
ANIMALS = ["SHEEP", "COW", "GOOSE"]
FEATURES = CROPS + ANIMALS
CROP_CODE = {"WH": "WHEAT", "ST": "STRAWBERRY", "TO": "TOMATO", "CA": "CARROT", "ME": "MELON"}
ANIMAL_CODE = {"sh": "SHEEP", "go": "GOOSE"}
COW_OR_EMPTY_COOP_CODE = "co"

N_DAYS = 30
CHECK_DAYS = [6, 9, 12, 15, 18, 21, 24, 27]
REVEAL_DAYS = [3, 6, 9, 12, 15, 18, 21, 24]
MIN_MATCHED_PAIRS = 5
DIVERGENCE_THRESHOLD = 3

LEADER_TEAMS = {
    "16623559_56489091": "DECEM",
    "16770421_56491543": "Vadim Vasilenko",
    "16730612_56489080": "Unknown Mother-Goose (current)",
    "16681125_56464621": "M & M & P & Q",
    "16915014_56484772": "Boey",
}
REQUIRED_DOWNLOAD_TEAMS = ["16623559_56489091", "16770421_56491543"]
OPTIONAL_DOWNLOAD_TEAMS = ["16730612_56489080"]
N_FULL_PER_LEADER = 40

RNG_SEED = 20260923


# --------------------------------------------------------------------------
# Memory guard (HARD MEMORY RULE)
# --------------------------------------------------------------------------

def wait_for_memory(threshold_gb: float = 2.5, sleep_s: float = 30.0):
    import psutil
    while True:
        avail = psutil.virtual_memory().available / 1e9
        if avail >= threshold_gb:
            return avail
        print(f"  low memory ({avail:.2f} GB available < {threshold_gb} GB); sleeping {sleep_s:.0f}s",
              file=sys.stderr)
        time.sleep(sleep_s)


# --------------------------------------------------------------------------
# Tile counting / quadrant derivation
# --------------------------------------------------------------------------

def count_engine_tiles(tiles) -> Counter:
    c = Counter()
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            kind = t.get("kind")
            if kind == "PLANT":
                crop = t.get("crop")
                if crop in CROPS:
                    c[crop] += 1
            elif kind in ("COOP", "PASTURE"):
                animal = t.get("animal")
                if animal in ANIMALS:
                    c[animal] += 1
    return c


def count_compact_board(rows) -> Counter:
    c = Counter()
    for row in rows:
        for i in range(0, len(row), 2):
            code = row[i:i + 2]
            if code in CROP_CODE:
                c[CROP_CODE[code]] += 1
            elif code in ANIMAL_CODE:
                c[ANIMAL_CODE[code]] += 1
            elif code == COW_OR_EMPTY_COOP_CODE:
                c["COW"] += 1
    return c


def quadrants_from_compact_board(rows) -> float:
    """4 quadrants x 25 tiles = 100. A locked (unpurchased) quadrant's 25 tiles are
    all coded ' L'. quadrants_owned = 4 - locked_tile_count/25."""
    locked = 0
    total = 0
    for row in rows:
        for i in range(0, len(row), 2):
            code = row[i:i + 2]
            total += 1
            if code == " L":
                locked += 1
    if total == 0:
        return None
    return round(4 - locked / 25.0, 2)


def action_hash(act) -> int:
    if act is None:
        return -1
    try:
        return zlib.crc32(json.dumps(act, sort_keys=True).encode("utf-8"))
    except Exception:
        return -2


# --------------------------------------------------------------------------
# DSM: reparse local full replays (no download) to add seed + action hashes to
# the existing day/board/cash/quadrant/hands extraction.
# --------------------------------------------------------------------------

def parse_dsm_full(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        d = json.load(f)
    team_names = list(d["info"]["TeamNames"])
    dsm_indices = [i for i, n in enumerate(team_names) if n == "DSM"]
    seed = d["info"].get("seed")
    steps = d["steps"]
    n_days = len(steps) // 24
    shops_by_day = []
    per_farm = {i: {"day_counts": [], "money": [], "hands": [], "quadrants": []} for i in (0, 1)}
    for day in range(n_days):
        hour = day * 24
        obs = steps[hour][0]["observation"]
        shops_by_day.append(list(obs["town"]["unlocked_shops"]))
        mid_hour = min(hour + 12, len(steps) - 1)
        mid_obs = steps[mid_hour][0]["observation"]
        for i in (0, 1):
            farm = obs["farms"][i]
            per_farm[i]["day_counts"].append(dict(count_engine_tiles(farm["tiles"])))
            per_farm[i]["money"].append(farm["money"])
            per_farm[i]["hands"].append(len(mid_obs["farms"][i]["hands"]))
            per_farm[i]["quadrants"].append(len(farm["unlocked_quadrants"]))
    max_action_hour = min(len(steps) - 1, n_days * 24)
    action_hashes = {i: [] for i in (0, 1)}
    for i in (0, 1):
        for h in range(max_action_hour):
            act = steps[h + 1][i]["action"] if h + 1 < len(steps) else None
            action_hashes[i].append(action_hash(act))
    last = len(steps) - 1
    final_cash = {str(i): steps[last][i]["reward"] for i in (0, 1)}
    episode_id = d["info"].get("EpisodeId") or path.stem
    record = {
        "episode": episode_id, "team_names": team_names, "dsm_indices": dsm_indices,
        "self_play": len(dsm_indices) == 2, "seed": seed, "n_days": n_days,
        "shops_by_day": shops_by_day,
        "per_farm": {str(i): {**per_farm[i], "action_hashes": action_hashes[i]} for i in (0, 1)},
        "final_cash": final_cash,
    }
    del d, steps, per_farm, action_hashes
    return record


def build_dsm_cache() -> dict:
    cache_path = OUT / "dsm_full_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    paths = sorted(DSM_DIR.glob("episode-*-replay.json"))
    changed = False
    for path in paths:
        key = path.stem
        if key in cache:
            continue
        wait_for_memory()
        attempts = 0
        record = None
        while record is None:
            try:
                record = parse_dsm_full(path)
            except MemoryError:
                attempts += 1
                print(f"  MemoryError parsing {path.name}, retry {attempts} in 10s", file=sys.stderr)
                gc.collect()
                time.sleep(10)
                if attempts > 5:
                    raise
        cache[key] = record
        changed = True
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        print(f"  DSM {key}: seed={record['seed']} dsm_idx={record['dsm_indices']}", flush=True)
        del record
        gc.collect()
    if changed:
        print(f"DSM full cache built/updated: {len(cache)} episodes -> {cache_path}")
    else:
        print(f"DSM full cache reused unchanged: {len(cache)} episodes <- {cache_path}")
    return cache


# --------------------------------------------------------------------------
# UMG-old: reparse local compact tapes (small, bulk load fine)
# --------------------------------------------------------------------------

def parse_umg_tape_full(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        t = json.load(f)
    boards = t["boards"][:N_DAYS]
    day_counts = [dict(count_compact_board(b)) for b in boards]
    quadrants = [quadrants_from_compact_board(b) for b in boards]
    shops_by_day = [list(s) for s in t["shops"][:N_DAYS]]
    cash = t["cash"][:N_DAYS] if t.get("cash") else []
    actions = t.get("actions") or []
    action_hashes = [action_hash(a) for a in actions]
    own_final = None
    try:
        own_final = t["rewards"][t["seat"]]
    except Exception:
        pass
    return {
        "episode": t["episode"], "submission": t.get("submission"), "seat": t.get("seat"),
        "seed": t.get("seed"), "n_days": len(boards), "shops_by_day": shops_by_day,
        "day_counts": day_counts, "quadrants": quadrants, "cash": cash,
        "action_hashes": action_hashes, "own_final_cash": own_final,
    }


def build_umg_cache() -> dict:
    cache_path = OUT / "umg_full_cache.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"UMG-old full cache reused: {len(cache)} tapes <- {cache_path}")
        return cache
    cache = {}
    for path in sorted(MG_DIR.glob("*/*.json.gz")):
        rec = parse_umg_tape_full(path)
        cache[str(rec["episode"])] = rec
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    print(f"UMG-old full cache built: {len(cache)} tapes -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Other leaders: local compact-tape extraction (seed, reveal list, action
# hashes) for all 5 teams -- no download needed for this part.
# --------------------------------------------------------------------------

def build_leader_local_cache() -> dict:
    cache_path = OUT / "leader_local_cache.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"Leader-local cache reused: {sum(len(v) for v in cache.values())} tapes <- {cache_path}")
        return cache
    cache = {}
    for folder, team_name in LEADER_TEAMS.items():
        entries = {}
        for path in sorted((LEADER_DIR / folder).glob("*.json.gz")):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                t = json.load(f)
            actions = t.get("actions") or []
            action_hashes = [action_hash(a) for a in actions]
            own_final = None
            try:
                own_final = t["rewards"][t["seat"]]
            except Exception:
                pass
            entries[str(t["episode"])] = {
                "episode": t["episode"], "team": t["names"][t["seat"]], "seat": t["seat"],
                "seed": t.get("seed"), "reveal_list": list(t["shops"]),
                "action_hashes": action_hashes, "own_final_cash": own_final,
            }
        cache[folder] = entries
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    n = sum(len(v) for v in cache.values())
    print(f"Leader-local cache built: {n} tapes across {len(cache)} teams -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Other leaders: full-replay download for board state (DECEM/Vadim required,
# MG-current optional).
# --------------------------------------------------------------------------

def load_index(folder):
    return json.loads((LEADER_DIR / folder / "index.json").read_text(encoding="utf-8"))


def download_replay(episode_id: int, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"episode-{episode_id}-replay.json"
    if path.exists():
        return path
    r = subprocess.run([str(KAGGLE), "competitions", "replay", str(episode_id), "-p", str(dest_dir), "-q"],
                        capture_output=True, timeout=300)
    if not path.exists():
        raise RuntimeError(f"download failed for {episode_id}: {r.stderr.decode(errors='replace')[-300:]}")
    return path


def parse_leader_full(path: Path, match_name: str) -> dict:
    with path.open("r", encoding="utf-8") as f:
        d = json.load(f)
    team_names = list(d["info"]["TeamNames"])
    target = [i for i, n in enumerate(team_names) if n == match_name]
    seed = d["info"].get("seed")
    steps = d["steps"]
    n_days = len(steps) // 24
    shops_by_day = []
    per_farm = {i: {"day_counts": [], "money": [], "hands": [], "quadrants": []} for i in target}
    for day in range(n_days):
        hour = day * 24
        obs = steps[hour][0]["observation"]
        shops_by_day.append(list(obs["town"]["unlocked_shops"]))
        mid_hour = min(hour + 12, len(steps) - 1)
        mid_obs = steps[mid_hour][0]["observation"]
        for i in target:
            farm = obs["farms"][i]
            per_farm[i]["day_counts"].append(dict(count_engine_tiles(farm["tiles"])))
            per_farm[i]["money"].append(farm["money"])
            per_farm[i]["hands"].append(len(mid_obs["farms"][i]["hands"]))
            per_farm[i]["quadrants"].append(len(farm["unlocked_quadrants"]))
    last = len(steps) - 1
    final_cash = {str(i): steps[last][i]["reward"] for i in range(len(team_names))}
    episode_id = d["info"].get("EpisodeId") or path.stem
    record = {
        "episode": episode_id, "team_names": team_names, "target_indices": target,
        "seed": seed, "n_days": n_days, "shops_by_day": shops_by_day,
        "per_farm": {str(i): per_farm[i] for i in target},
        "final_cash": final_cash,
    }
    del d, steps, per_farm
    return record


def build_leader_full_cache(folder: str, n_target: int = N_FULL_PER_LEADER) -> dict:
    team_name = LEADER_TEAMS[folder]
    cache_path = OUT / f"{folder}_full_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    idx = load_index(folder)
    match_name = idx["team"]
    episodes = idx["episodes"][:n_target]
    for ep in episodes:
        key = str(ep)
        if key in cache:
            continue
        wait_for_memory()
        try:
            path = download_replay(ep, RAW_DL)
        except Exception as e:
            print(f"  {team_name} {ep}: DOWNLOAD FAILED: {e}", file=sys.stderr)
            continue
        try:
            attempts = 0
            record = None
            while record is None:
                try:
                    record = parse_leader_full(path, match_name)
                except MemoryError:
                    attempts += 1
                    gc.collect()
                    time.sleep(10)
                    if attempts > 5:
                        raise
            cache[key] = record
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            print(f"  {team_name} {ep}: seed={record['seed']} target={record['target_indices']}", flush=True)
        finally:
            path.unlink(missing_ok=True)
        gc.collect()
    print(f"{team_name} full cache: {len(cache)}/{len(episodes)} episodes -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Normalize every source into one common per-farm-observation record shape:
#   agent, episode, farm_key, seed, reveal_list (<=8), day_counts (<=30),
#   cash (<=30), quadrants (<=30), action_hashes (<=719), final_cash, self_play
# --------------------------------------------------------------------------

def normalize_dsm(cache: dict) -> list:
    out = []
    for rec in cache.values():
        reveal_list = rec["shops_by_day"][-1] if rec["shops_by_day"] else []
        for i in rec["dsm_indices"]:
            farm = rec["per_farm"][str(i)]
            out.append({
                "agent": "DSM", "episode": rec["episode"], "farm_key": f"{rec['episode']}:{i}",
                "seed": rec.get("seed"), "reveal_list": reveal_list,
                "day_counts": farm["day_counts"], "cash": farm["money"],
                "quadrants": farm["quadrants"], "action_hashes": farm["action_hashes"],
                "final_cash": rec["final_cash"].get(str(i)), "self_play": rec["self_play"],
            })
    return out


def normalize_umg(cache: dict) -> list:
    out = []
    for rec in cache.values():
        reveal_list = rec["shops_by_day"][-1] if rec["shops_by_day"] else []
        out.append({
            "agent": "UMG-old", "episode": rec["episode"], "farm_key": f"{rec['episode']}:0",
            "seed": rec.get("seed"), "reveal_list": reveal_list,
            "day_counts": rec["day_counts"], "cash": rec.get("cash", []),
            "quadrants": rec.get("quadrants", []), "action_hashes": rec.get("action_hashes", []),
            "final_cash": rec.get("own_final_cash"), "self_play": False,
        })
    return out


def normalize_leader(folder: str, local_cache: dict, full_cache: dict | None) -> list:
    team_name = LEADER_TEAMS[folder]
    out = []
    local = local_cache.get(folder, {})
    for key, loc in local.items():
        full = (full_cache or {}).get(key)
        day_counts = cash = quadrants = None
        if full:
            ti = full["target_indices"]
            if ti:
                farm = full["per_farm"][str(ti[0])]
                day_counts = farm["day_counts"]
                cash = farm["money"]
                quadrants = farm["quadrants"]
        out.append({
            "agent": team_name, "episode": loc["episode"], "farm_key": f"{loc['episode']}:{loc['seat']}",
            "seed": loc.get("seed"), "reveal_list": loc.get("reveal_list") or [],
            "day_counts": day_counts, "cash": cash, "quadrants": quadrants,
            "action_hashes": loc.get("action_hashes", []),
            "final_cash": loc.get("own_final_cash"), "self_play": False,
            "has_board": day_counts is not None,
        })
    return out


# --------------------------------------------------------------------------
# Distance & grouping primitives
# --------------------------------------------------------------------------

def board_distance(a: dict, b: dict) -> int:
    return sum(abs((a or {}).get(f, 0) - (b or {}).get(f, 0)) for f in FEATURES)


def k_of_day(day: int) -> int:
    return min(8, day // 3)


def get_day(seq, day):
    if seq is None or day >= len(seq):
        return None
    return seq[day]


def build_prefix_groups(records, k):
    groups = defaultdict(list)
    for r in records:
        rl = r.get("reveal_list") or []
        if len(rl) < k:
            continue
        groups[tuple(rl[:k])].append(r)
    return groups


def count_pairs(groups):
    return sum(len(v) * (len(v) - 1) // 2 for v in groups.values() if len(v) >= 2)


def find_k_with_min_pairs(records, day, k_start, min_pairs=MIN_MATCHED_PAIRS):
    """Decrease k until >=min_pairs groups-with->=2-members exist whose members
    all have board data at `day`; returns (k_used, valid_groups, n_pairs, fallback)."""
    k = k_start
    fallback = False
    while True:
        groups = build_prefix_groups(records, k)
        valid = {key: [r for r in v if get_day(r.get("day_counts"), day) is not None]
                 for key, v in groups.items()}
        valid = {key: v for key, v in valid.items() if len(v) >= 2}
        n_pairs = count_pairs(valid)
        if n_pairs >= min_pairs or k == 0:
            return k, valid, n_pairs, fallback
        k -= 1
        fallback = True


MAX_PAIRS_PER_CELL = 4000


def pairs_from_groups(groups, rng, cap=MAX_PAIRS_PER_CELL):
    pairs = []
    for members in groups.values():
        n = len(members)
        for i in range(n):
            for j in range(i + 1, n):
                pairs.append((members[i], members[j]))
    if len(pairs) > cap:
        pairs = rng.sample(pairs, cap)
    return pairs


def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def median_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 3) if xs else None


# --------------------------------------------------------------------------
# Method 1: matched vs unmatched board distance, per agent per check day
# --------------------------------------------------------------------------

def matched_vs_unmatched(records, day, rng):
    k_start = k_of_day(day)
    k_used, valid_groups, n_pairs, fallback = find_k_with_min_pairs(records, day, k_start)
    matched_pairs = pairs_from_groups(valid_groups, rng)
    matched_dist = [board_distance(get_day(a["day_counts"], day), get_day(b["day_counts"], day))
                    for a, b in matched_pairs]
    matched_cash = [abs(get_day(a["cash"], day) - get_day(b["cash"], day))
                    for a, b in matched_pairs
                    if get_day(a.get("cash"), day) is not None and get_day(b.get("cash"), day) is not None]

    # Unmatched: random pairs whose k_used-prefix differs, both with board data at `day`.
    eligible = [r for r in records if get_day(r.get("day_counts"), day) is not None
                and len(r.get("reveal_list") or []) >= k_used]
    unmatched_pairs = []
    if len(eligible) >= 2:
        target_n = max(len(matched_pairs), MIN_MATCHED_PAIRS)
        attempts = 0
        seen = set()
        while len(unmatched_pairs) < min(target_n, MAX_PAIRS_PER_CELL) and attempts < target_n * 50 + 200:
            attempts += 1
            a, b = rng.sample(eligible, 2)
            if tuple(a["reveal_list"][:k_used]) == tuple(b["reveal_list"][:k_used]):
                continue
            key = tuple(sorted((a["farm_key"], b["farm_key"])))
            if key in seen:
                continue
            seen.add(key)
            unmatched_pairs.append((a, b))
    unmatched_dist = [board_distance(get_day(a["day_counts"], day), get_day(b["day_counts"], day))
                       for a, b in unmatched_pairs]
    unmatched_cash = [abs(get_day(a["cash"], day) - get_day(b["cash"], day))
                       for a, b in unmatched_pairs
                       if get_day(a.get("cash"), day) is not None and get_day(b.get("cash"), day) is not None]

    return {
        "day": day, "k_target": k_start, "k_used": k_used, "fallback_used": fallback,
        "n_matched_pairs": len(matched_pairs), "n_unmatched_pairs": len(unmatched_pairs),
        "matched_distance_mean": mean_or_none(matched_dist), "matched_distance_median": median_or_none(matched_dist),
        "unmatched_distance_mean": mean_or_none(unmatched_dist), "unmatched_distance_median": median_or_none(unmatched_dist),
        "matched_cash_diff_mean": mean_or_none(matched_cash), "matched_cash_diff_median": median_or_none(matched_cash),
        "unmatched_cash_diff_mean": mean_or_none(unmatched_cash), "unmatched_cash_diff_median": median_or_none(unmatched_cash),
    }


# --------------------------------------------------------------------------
# Variance-explained: R^2 / one-way ANOVA of each feature at day d, grouped by
# the k(d)-shop-prefix (groups with >=2 members only).
# --------------------------------------------------------------------------

def variance_explained(records, day, feature):
    k = k_of_day(day)
    groups = build_prefix_groups(records, k)
    valid = {}
    for key, members in groups.items():
        vals = [get_day(m.get("day_counts"), day) for m in members]
        vals = [(m, v) for m, v in zip(members, vals) if v is not None]
        if len(vals) >= 2:
            valid[key] = [v.get(feature, 0) for _, v in vals]
    if len(valid) < 2:
        return {"day": day, "k_used": k, "feature": feature, "n_groups": len(valid),
                "n_obs": sum(len(v) for v in valid.values()), "r2": None, "p_value": None}
    all_vals = [x for v in valid.values() for x in v]
    grand_mean = statistics.mean(all_vals)
    ss_total = sum((x - grand_mean) ** 2 for x in all_vals)
    ss_within = 0.0
    for v in valid.values():
        gm = statistics.mean(v)
        ss_within += sum((x - gm) ** 2 for x in v)
    r2 = None if ss_total == 0 else round(1 - ss_within / ss_total, 4)
    p_value = None
    try:
        from scipy import stats as sstats
        groups_vals = list(valid.values())
        if len(groups_vals) >= 2 and any(len(set(v)) > 1 for v in groups_vals + [all_vals]):
            f_stat, p_value = sstats.f_oneway(*groups_vals)
            p_value = round(float(p_value), 5)
    except Exception:
        pass
    return {"day": day, "k_used": k, "feature": feature, "n_groups": len(valid),
            "n_obs": sum(len(v) for v in valid.values()), "r2": r2, "p_value": p_value}


# --------------------------------------------------------------------------
# Method 2: first MATERIAL divergence (board) vs first ACTION divergence, for
# pairs sharing a meaningful shop-prefix (k_max >= 2). Bucket by k=2 first to
# bound pairwise comparisons, then extend to the true common-prefix length.
# --------------------------------------------------------------------------

def common_prefix_len(a, b, cap=8):
    n = min(len(a), len(b), cap)
    k = 0
    while k < n and a[k] == b[k]:
        k += 1
    return k


def first_divergence_pairs(records, threshold=DIVERGENCE_THRESHOLD):
    groups2 = build_prefix_groups(records, 2)
    out = []
    seen = set()
    for members in groups2.values():
        n = len(members)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = members[i], members[j]
                key = tuple(sorted((a["farm_key"], b["farm_key"])))
                if key in seen:
                    continue
                seen.add(key)
                kmax = common_prefix_len(a.get("reveal_list") or [], b.get("reveal_list") or [])
                if kmax < 2:
                    continue
                first_board_day = None
                dcA, dcB = a.get("day_counts"), b.get("day_counts")
                if dcA is not None and dcB is not None:
                    n_days_cmp = min(len(dcA), len(dcB))
                    for d in range(n_days_cmp):
                        if board_distance(dcA[d], dcB[d]) >= threshold:
                            first_board_day = d
                            break
                first_action_day = None
                ahA, ahB = a.get("action_hashes") or [], b.get("action_hashes") or []
                n_h = min(len(ahA), len(ahB))
                for h in range(n_h):
                    if ahA[h] != ahB[h]:
                        first_action_day = h // 24
                        break
                out.append({
                    "pair": key, "agent": a["agent"], "k_max": kmax,
                    "first_board_divergence_day": first_board_day,
                    "n_days_compared_board": (min(len(dcA), len(dcB)) if (dcA is not None and dcB is not None) else 0),
                    "first_action_divergence_day": first_action_day,
                    "n_hours_compared_action": n_h,
                })
    return out


def summarize_divergence_pairs(pairs):
    by_kmax = defaultdict(list)
    for p in pairs:
        by_kmax[p["k_max"]].append(p)
    out = {}
    for kmax, ps in sorted(by_kmax.items()):
        board_days = [p["first_board_divergence_day"] for p in ps if p["first_board_divergence_day"] is not None]
        board_never = sum(1 for p in ps if p["n_days_compared_board"] > 0 and p["first_board_divergence_day"] is None)
        board_no_data = sum(1 for p in ps if p["n_days_compared_board"] == 0)
        action_days = [p["first_action_divergence_day"] for p in ps if p["first_action_divergence_day"] is not None]
        action_never = sum(1 for p in ps if p["n_hours_compared_action"] > 0 and p["first_action_divergence_day"] is None)
        out[str(kmax)] = {
            "n_pairs": len(ps),
            "n_pairs_with_board_data": len(ps) - board_no_data,
            "median_first_board_divergence_day": median_or_none(board_days),
            "mean_first_board_divergence_day": mean_or_none(board_days),
            "n_never_diverged_board_within_window": board_never,
            "median_first_action_divergence_day": median_or_none(action_days),
            "mean_first_action_divergence_day": mean_or_none(action_days),
            "n_never_diverged_action_within_window": action_never,
        }
    return out


# --------------------------------------------------------------------------
# Method 3: same-seed repeats
# --------------------------------------------------------------------------

def same_seed_report(records):
    by_seed = defaultdict(list)
    for r in records:
        if r.get("seed") is not None:
            by_seed[r["seed"]].append(r)
    cross_episode_dupes = []
    same_episode_groups = []
    for seed, members in by_seed.items():
        episodes = set(m["episode"] for m in members)
        if len(episodes) > 1:
            cross_episode_dupes.append({"seed": seed, "farm_keys": [m["farm_key"] for m in members],
                                          "episodes": sorted(episodes)})
        elif len(members) > 1:
            same_episode_groups.append({"seed": seed, "episode": members[0]["episode"],
                                          "farm_keys": [m["farm_key"] for m in members]})
    return {"n_records_with_seed": sum(len(v) for v in by_seed.values()),
            "n_distinct_seeds": len(by_seed),
            "cross_episode_seed_duplicates": cross_episode_dupes,
            "same_episode_multi_farm_groups": same_episode_groups}


# --------------------------------------------------------------------------
# Method 4: final-score spread within matched-prefix groups vs overall
# --------------------------------------------------------------------------

def final_score_spread(records, k=4):
    groups = build_prefix_groups(records, k)
    valid = {key: [r["final_cash"] for r in v if r.get("final_cash") is not None]
             for key, v in groups.items()}
    valid = {key: v for key, v in valid.items() if len(v) >= 2}
    within_group_stats = []
    for key, vals in valid.items():
        within_group_stats.append({
            "prefix": list(key), "n": len(vals),
            "std": round(statistics.pstdev(vals), 1) if len(vals) > 1 else 0.0,
            "range": round(max(vals) - min(vals), 1),
        })
    all_final = [r["final_cash"] for r in records if r.get("final_cash") is not None]
    overall_std = round(statistics.pstdev(all_final), 1) if len(all_final) > 1 else None
    overall_range = round(max(all_final) - min(all_final), 1) if all_final else None
    mean_within_std = mean_or_none([g["std"] for g in within_group_stats])
    mean_within_range = mean_or_none([g["range"] for g in within_group_stats])
    return {
        "k": k, "n_groups_with_2plus": len(valid), "n_records_overall": len(all_final),
        "overall_std": overall_std, "overall_range": overall_range,
        "mean_within_group_std": mean_within_std, "mean_within_group_range": mean_within_range,
        "groups": sorted(within_group_stats, key=lambda g: -g["n"])[:15],
        "note": "Opponents differ between games even within a matched shop-prefix group; "
                "within-group spread is not purely plan-variance.",
    }


# --------------------------------------------------------------------------
# Method 5: late-game plan stability (days 18/21/24) for k=5/6 matched groups
# --------------------------------------------------------------------------

def late_game_stability(records, k):
    groups = build_prefix_groups(records, k)
    valid = {key: v for key, v in groups.items() if len(v) >= 2}
    rows = []
    for key, members in valid.items():
        row = {"prefix": list(key), "n": len(members)}
        for day in (18, 21, 24):
            for feat in FEATURES:
                vals = [get_day(m.get("day_counts"), day) for m in members]
                vals = [v.get(feat, 0) for v in vals if v is not None]
                if vals:
                    row.setdefault(f"day{day}", {})[feat] = {
                        "mean": mean_or_none(vals), "min": min(vals), "max": max(vals), "n": len(vals)}
        rows.append(row)
    return {"k": k, "n_groups_with_2plus": len(valid), "rows": rows}


# --------------------------------------------------------------------------
# DSM self-play natural experiment
# --------------------------------------------------------------------------

def dsm_self_play_report(dsm_cache):
    out = []
    for rec in dsm_cache.values():
        if not rec["self_play"]:
            continue
        f0, f1 = rec["per_farm"]["0"], rec["per_farm"]["1"]
        n = min(len(f0["day_counts"]), len(f1["day_counts"]))
        day_distances = [board_distance(f0["day_counts"][d], f1["day_counts"][d]) for d in range(n)]
        first_div = next((d for d, dist in enumerate(day_distances) if dist >= DIVERGENCE_THRESHOLD), None)
        ah0, ah1 = f0["action_hashes"], f1["action_hashes"]
        nh = min(len(ah0), len(ah1))
        first_action_div = next((h // 24 for h in range(nh) if ah0[h] != ah1[h]), None)
        out.append({
            "episode": rec["episode"], "seed": rec.get("seed"),
            "final_cash_0": rec["final_cash"].get("0"), "final_cash_1": rec["final_cash"].get("1"),
            "final_cash_diff": (rec["final_cash"].get("0") - rec["final_cash"].get("1"))
                                 if rec["final_cash"].get("0") is not None and rec["final_cash"].get("1") is not None else None,
            "board_distance_by_day": day_distances,
            "first_board_divergence_day_ge3": first_div,
            "first_action_divergence_day": first_action_div,
        })
    return out


# --------------------------------------------------------------------------
# Stages / CLI
# --------------------------------------------------------------------------

def stage_dsm():
    return build_dsm_cache()


def stage_umg():
    return build_umg_cache()


def stage_leader_local():
    return build_leader_local_cache()


def stage_leader_full(team_folders):
    for folder in team_folders:
        build_leader_full_cache(folder)


def load_all_caches():
    dsm_cache = json.loads((OUT / "dsm_full_cache.json").read_text(encoding="utf-8"))
    umg_cache = json.loads((OUT / "umg_full_cache.json").read_text(encoding="utf-8"))
    local_cache = json.loads((OUT / "leader_local_cache.json").read_text(encoding="utf-8"))
    leader_full = {}
    for folder in LEADER_TEAMS:
        p = OUT / f"{folder}_full_cache.json"
        leader_full[folder] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return dsm_cache, umg_cache, local_cache, leader_full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                     choices=["dsm", "umg", "leader-local", "leader-full", "leader-full-optional", "analysis", "all"])
    ap.add_argument("--team", default=None, help="single leader folder key for --stage leader-full")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.stage in ("dsm", "all"):
        print("Stage: DSM (reparse local, no download)...")
        stage_dsm()
    if args.stage in ("umg", "all"):
        print("Stage: UMG-old (reparse local)...")
        stage_umg()
    if args.stage in ("leader-local", "all"):
        print("Stage: leader local (5 teams, no download)...")
        stage_leader_local()
    if args.stage == "leader-full":
        teams = [args.team] if args.team else REQUIRED_DOWNLOAD_TEAMS
        print(f"Stage: leader full download for {teams}...")
        stage_leader_full(teams)
    if args.stage == "leader-full-optional":
        print(f"Stage: leader full download (optional) for {OPTIONAL_DOWNLOAD_TEAMS}...")
        stage_leader_full(OPTIONAL_DOWNLOAD_TEAMS)
    if args.stage == "all":
        print(f"Stage: leader full download (required) for {REQUIRED_DOWNLOAD_TEAMS}...")
        stage_leader_full(REQUIRED_DOWNLOAD_TEAMS)

    if args.stage in ("analysis", "all"):
        print("Stage: analysis...")
        run_analysis()


def run_analysis():
    dsm_cache, umg_cache, local_cache, leader_full = load_all_caches()

    rng = random.Random(RNG_SEED)

    agents = {}
    agents["DSM"] = normalize_dsm(dsm_cache)
    agents["UMG-old"] = normalize_umg(umg_cache)
    for folder, team_name in LEADER_TEAMS.items():
        agents[team_name] = normalize_leader(folder, local_cache, leader_full.get(folder))

    analysis = {"generated_by": "scripts/analyze_plan_vs_jitter.py", "check_days": CHECK_DAYS,
                "reveal_days": REVEAL_DAYS, "divergence_threshold": DIVERGENCE_THRESHOLD,
                "min_matched_pairs": MIN_MATCHED_PAIRS, "rng_seed": RNG_SEED, "agents": {}}

    for name, recs in agents.items():
        n_board = sum(1 for r in recs if r.get("day_counts") is not None)
        n_seed = sum(1 for r in recs if r.get("seed") is not None)
        n_actions = sum(1 for r in recs if r.get("action_hashes"))
        agent_out = {"n_records": len(recs), "n_with_board_data": n_board,
                     "n_with_seed": n_seed, "n_with_action_hashes": n_actions}

        agent_out["matched_vs_unmatched_by_day"] = {}
        for day in CHECK_DAYS:
            agent_out["matched_vs_unmatched_by_day"][str(day)] = matched_vs_unmatched(recs, day, rng)

        agent_out["variance_explained_by_day_feature"] = {}
        for day in CHECK_DAYS:
            agent_out["variance_explained_by_day_feature"][str(day)] = {
                feat: variance_explained(recs, day, feat) for feat in FEATURES
            }

        div_pairs = first_divergence_pairs(recs)
        agent_out["first_divergence_by_kmax"] = summarize_divergence_pairs(div_pairs)
        agent_out["n_divergence_pairs_considered"] = len(div_pairs)

        agent_out["same_seed"] = same_seed_report(recs)
        agent_out["final_score_spread_k4"] = final_score_spread(recs, k=4)
        agent_out["late_game_stability_k5"] = late_game_stability(recs, k=5)
        agent_out["late_game_stability_k6"] = late_game_stability(recs, k=6)

        analysis["agents"][name] = agent_out

    analysis["dsm_self_play"] = dsm_self_play_report(dsm_cache)

    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {OUT / 'analysis.json'}")

    report = build_report(analysis)
    (OUT / "summary.md").write_text(report, encoding="utf-8")
    print(f"Wrote {OUT / 'summary.md'}")


def fmt(x):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:,.2f}"
    return f"{x:,}"


def build_report(analysis: dict) -> str:
    L = []
    L.append("# Plan vs jitter: how divergent can top agents' plans get on the same seed (days 7-29)?")
    L.append("")
    L.append("Generated by `scripts/analyze_plan_vs_jitter.py`. No games simulated; all numbers parsed "
              "from recorded replay/tape JSON. Board distance = L1 over 8 counts (5 crop tile counts + "
              "3 animal counts); cash and quadrant differences are reported separately. "
              f"k(d) = min(8, d//3) shop-reveal-prefix length; matched-pair cells fall back to a smaller "
              f"k when fewer than {analysis['min_matched_pairs']} matched pairs exist at the target k "
              "(noted per cell). Unmatched pairs are random pairs (same agent) whose prefix differs at "
              "the k actually used.")
    L.append("")
    L.append("## Caveats (apply throughout)")
    L.append("")
    L.append("- Opponents differ between games (except DSM self-play and any noted same-seed pair), so "
              "final-cash spread mixes plan variance with opponent variance.")
    L.append("- UMG-old cow counts are an upper bound (the compact board encoding collides an occupied "
              "cow pasture with an empty coop, code 'co'); sheep/goose/crops are exact.")
    L.append("- Board state for DECEM and Vadim Vasilenko comes from downloaded full replays (exact "
              "tiles); board state for 'M & M & P & Q' and 'Boey' was NOT downloaded for this analysis "
              "(out of the required scope) -- only their seed/action-divergence/same-seed results are "
              "reported. 'Unknown Mother-Goose (current)' board data is downloaded only if the "
              "leader-full-optional stage was run before this report; check n_with_board_data.")
    L.append("- Weeds and the exact opponent farm depend on the seed and the opponent, not on shops "
              "alone, so even a perfectly matched shop-prefix pair are not literally the same world.")
    L.append("- Small-n cells (n<5) are anecdotal; every table reports n.")
    L.append("")

    for name, a in analysis["agents"].items():
        L.append(f"## {name}")
        L.append("")
        L.append(f"n_records={a['n_records']}, with board data={a['n_with_board_data']}, "
                  f"with seed={a['n_with_seed']}, with action hashes={a['n_with_action_hashes']}")
        L.append("")
        L.append("### Method 1: matched vs unmatched board distance by day")
        L.append("")
        L.append("| Day | k target | k used | fallback | n matched | matched dist median (mean) | "
                  "n unmatched | unmatched dist median (mean) | matched cash-diff median | unmatched cash-diff median |")
        L.append("|---:|---:|---:|:---:|---:|---:|---:|---:|---:|---:|")
        for day in analysis["check_days"]:
            c = a["matched_vs_unmatched_by_day"][str(day)]
            L.append(f"| {day} | {c['k_target']} | {c['k_used']} | {'Y' if c['fallback_used'] else ''} | "
                      f"{c['n_matched_pairs']} | {fmt(c['matched_distance_median'])} ({fmt(c['matched_distance_mean'])}) | "
                      f"{c['n_unmatched_pairs']} | {fmt(c['unmatched_distance_median'])} ({fmt(c['unmatched_distance_mean'])}) | "
                      f"{fmt(c['matched_cash_diff_median'])} | {fmt(c['unmatched_cash_diff_median'])} |")
        L.append("")

        L.append("### Variance explained (R^2) by revealed-shop-prefix, per feature, at each check day")
        L.append("")
        L.append("| Day | " + " | ".join(FEATURES) + " |")
        L.append("|---:|" + "---:|" * len(FEATURES))
        for day in analysis["check_days"]:
            row = a["variance_explained_by_day_feature"][str(day)]
            cells = []
            for feat in FEATURES:
                v = row[feat]
                r2 = fmt(v["r2"]) if v["r2"] is not None else "n/a"
                cells.append(f"{r2} (n={v['n_obs']},g={v['n_groups']})")
            L.append(f"| {day} | " + " | ".join(cells) + " |")
        L.append("")

        L.append("### Method 2: first MATERIAL (board, L1>=3) vs first ACTION divergence, by shared-prefix length k_max")
        L.append("")
        L.append(f"{a['n_divergence_pairs_considered']} candidate pairs considered (same agent, sharing "
                  "at least the first 2 revealed shops).")
        L.append("")
        L.append("| k_max | n pairs | n w/ board data | median first board-div day | median first action-div day | "
                  "never diverged (board) | never diverged (action) |")
        L.append("|---:|---:|---:|---:|---:|---:|---:|")
        for kmax, row in a["first_divergence_by_kmax"].items():
            L.append(f"| {kmax} | {row['n_pairs']} | {row['n_pairs_with_board_data']} | "
                      f"{fmt(row['median_first_board_divergence_day'])} | "
                      f"{fmt(row['median_first_action_divergence_day'])} | "
                      f"{row['n_never_diverged_board_within_window']} | {row['n_never_diverged_action_within_window']} |")
        L.append("")

        ss = a["same_seed"]
        L.append(f"### Method 3: same-seed repeats -- {ss['n_distinct_seeds']} distinct seeds across "
                  f"{ss['n_records_with_seed']} records with a seed")
        L.append("")
        if ss["cross_episode_seed_duplicates"]:
            L.append("Cross-episode seed duplicates found:")
            for d in ss["cross_episode_seed_duplicates"]:
                L.append(f"- seed {d['seed']}: episodes {d['episodes']}, farms {d['farm_keys']}")
        else:
            L.append("No cross-episode seed duplicates found (expected: seeds are drawn fresh per episode).")
        if ss["same_episode_multi_farm_groups"]:
            L.append("")
            L.append("Same-episode multi-farm groups (self-play; trivially share a seed by construction):")
            for g in ss["same_episode_multi_farm_groups"]:
                L.append(f"- episode {g['episode']}: farms {g['farm_keys']}")
        L.append("")

        fss = a["final_score_spread_k4"]
        L.append(f"### Method 4: final-cash spread within k=4 matched-prefix groups vs overall "
                  f"(n groups w/ 2+ = {fss['n_groups_with_2plus']}, n records = {fss['n_records_overall']})")
        L.append("")
        L.append(f"Overall std={fmt(fss['overall_std'])}, overall range={fmt(fss['overall_range'])}. "
                  f"Mean within-matched-group std={fmt(fss['mean_within_group_std'])}, "
                  f"mean within-matched-group range={fmt(fss['mean_within_group_range'])}. {fss['note']}")
        L.append("")

        for k in (5, 6):
            lg = a[f"late_game_stability_k{k}"]
            L.append(f"### Method 5: late-game (days 18/21/24) stability, k={k} matched groups "
                      f"(n groups w/2+ = {lg['n_groups_with_2plus']})")
            if lg["n_groups_with_2plus"] == 0:
                L.append("No groups with 2+ members at this k -- sample too small to say anything about "
                          "late-game plan stability at this match depth for this agent.")
            else:
                L.append("")
                for row in sorted(lg["rows"], key=lambda r: -r["n"])[:6]:
                    d24 = row.get("day24", {})
                    parts = [f"{feat}={d24[feat]['mean']}[{d24[feat]['min']}-{d24[feat]['max']}]"
                             for feat in FEATURES if feat in d24]
                    L.append(f"- prefix {row['prefix']} (n={row['n']}): day24 " + ", ".join(parts))
            L.append("")

    sp = analysis.get("dsm_self_play", [])
    L.append(f"## DSM self-play natural experiment (n={len(sp)} episode(s), same world/seed, two DSM farms)")
    L.append("")
    if not sp:
        L.append("No DSM-vs-DSM self-play episodes found in the 108 available replays.")
    else:
        L.append("| Episode | Seed | Final cash farm0 | Final cash farm1 | Diff | First board div day (>=3) | First action div day |")
        L.append("|---:|---:|---:|---:|---:|---:|---:|")
        for r in sp:
            L.append(f"| {r['episode']} | {fmt(r['seed'])} | {fmt(r['final_cash_0'])} | {fmt(r['final_cash_1'])} | "
                      f"{fmt(r['final_cash_diff'])} | {fmt(r['first_board_divergence_day_ge3'])} | "
                      f"{fmt(r['first_action_divergence_day'])} |")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    main()

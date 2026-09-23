"""Opening profiles for the field's first 6-7 days: DSM (rank-1), five other current
leaders, our own old Mother-Goose tape library, our own agent, and a field-wide
clustering of every recorded ladder opponent's opening.

Question: has the field converged on the Mother-Goose/V45 "field-standard" opening
(day-3 board 3 cows/2 sheep/12 melons/7 wheat; 2nd quadrant day 6, 3rd days 9-11;
turn-0/1 wheat round trip; fixed hire schedule), or have top players moved to
different -- and different-from-each-other -- openings?

NO GAME SIMULATION IS RUN ANYWHERE IN THIS SCRIPT. Everything below is parsed from
already-recorded replay/tape JSON, either already on disk or downloaded once with
`kaggle competitions replay` and deleted immediately after parsing.

Data sources (see module docstring sections below for exact fields):
  - DSM:            data/dsm_replays/*.json               (108 full replays, local, no download)
  - 5 other leaders: data/leader_tapes/<team>/*.json.gz    (compact action tapes, local, orders only)
                      + 12 downloaded full replays/team    (board state, exact)
  - Mother-Goose old: data/mg_tapes/<sub>/*.json.gz        (584 compact tapes: boards+cash+actions, local)
  - Ours:            data/ladder_panel/56368334|56395605/*.json.gz (856 games, action-only, local)
                      + 12 downloaded full replays          (board state, exact; submission 56368334,
                        preferring the highest-rated recorded opponents)
  - Field-wide:      the same 856 ladder_panel games' opp_actions, joined to
                      results/fresh/newphase_20260923/ladder_games.json for opponent rating/margin/win.

Exact vs requested, everywhere: tile counts, cash, hands and quadrant counts read from a
FULL REPLAY's raw engine observation are exact board state. Anything read from an
*action* (BUY_SEED, BUY_ANIMAL, BUY_LAND, HIRE, the wheat BUY/SELL "flip") is a
REQUESTED command -- the compact tapes used for the 5-leader/MG-old/field-wide sources
carry no board, so a request there could have failed (insufficient cash/stock, the
10-orders-per-turn cap). Every output table and this script's docstring say which is
which; see also CLAUDE.md's documented over-requesting behaviour.

HARD MEMORY RULE (shared machine, a 4-worker game batch may be running): one Python
process, no multiprocessing/threading for parsing. Before every full-replay
download+parse this script checks psutil.virtual_memory().available >= 2.5 GB,
sleeping and rechecking otherwise. Full replays are parsed strictly one at a time,
the parsed object is `del`ed and `gc.collect()`ed before the next, and the raw
downloaded file is deleted right after. No game is ever simulated.

Outputs (under results/fresh/newphase_20260923/openings/):
  dsm_profile_cache.json     -- per-episode DSM day0-8 profile (cache, reusable)
  leader_orders_cache.json   -- per-tape order stats for the 5 other leaders (all local tapes)
  leader_full_cache.json     -- per-episode day0-8 profile from 12 downloaded replays/leader
  mg_profile_cache.json      -- per-tape day0-8 profile for the 584 Mother-Goose-old tapes
  our_orders_cache.json      -- per-game order stats for our agent (all 856 ladder_panel games)
  our_full_cache.json        -- per-episode day0-8 profile from 12 downloaded our-agent replays
  field_cache.json           -- per-opponent-game opening features for all 856 ladder games
  analysis.json              -- every computed table in one document
  summary.md                 -- the markdown report (tables, n per cell, caveats)

Usage:
  .venv/Scripts/python.exe scripts/analyze_openings_2026.py --stage all
  (or --stage dsm|leader-local|leader-full|mg|our-local|our-full|field|report to run one part)
"""
from __future__ import annotations

import argparse
import gc
import glob
import gzip
import json
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSM_DIR = ROOT / "data/dsm_replays"
LEADER_DIR = ROOT / "data/leader_tapes"
MG_DIR = ROOT / "data/mg_tapes"
LADDER_DIR = ROOT / "data/ladder_panel"
KAGGLE = ROOT / ".venv/Scripts/kaggle.exe"
LADDER_GAMES_JSON = ROOT / "results/fresh/newphase_20260923/ladder_games.json"

OUT = ROOT / "results/fresh/newphase_20260923/openings"
RAW_DL = ROOT / "results/fresh/newphase_20260923/openings/_raw_dl"  # deleted-after-parse scratch

CROPS = ["WHEAT", "STRAWBERRY", "TOMATO", "CARROT", "MELON"]
ANIMALS = ["SHEEP", "COW", "GOOSE"]
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_INCREMENTAL_PRICE = [1000, 2000, 4000]  # cost of the 2nd, 3rd, 4th quadrant (kaggriculture.py LAND_PRICES)
CROP_CODE = {"WH": "WHEAT", "ST": "STRAWBERRY", "TO": "TOMATO", "CA": "CARROT", "ME": "MELON"}
ANIMAL_CODE = {"sh": "SHEEP", "go": "GOOSE"}
COW_OR_EMPTY_COOP_CODE = "co"  # ambiguous in the compact board encoding; reported as an upper bound

MAX_DAY = 8          # board/cash/hands/quadrants captured for day-start 0..MAX_DAY
ORDER_MAX_DAY = 8    # orders (seeds/animals/hires/land requests) grouped by day 0..ORDER_MAX_DAY
FIVE_LEADERS = {
    "16623559_56489091": "DECEM",
    "16681125_56464621": "M & M & P & Q",
    "16730612_56489080": "Unknown Mother-Goose (current)",
    "16770421_56491543": "Vadim Vasilenko",
    "16915014_56484772": "Boey",
}
N_FULL_PER_LEADER = 12
N_FULL_OURS = 12
OUR_SUBMISSION_FOR_DOWNLOAD = "56368334"


# --------------------------------------------------------------------------
# Memory guard (HARD MEMORY RULE)
# --------------------------------------------------------------------------

def wait_for_memory(threshold_gb: float = 2.5, sleep_s: float = 30.0):
    import psutil
    while True:
        avail = psutil.virtual_memory().available / 1e9
        if avail >= threshold_gb:
            return avail
        print(f"  low memory ({avail:.2f} GB available < {threshold_gb} GB); sleeping {sleep_s:.0f}s", file=sys.stderr)
        time.sleep(sleep_s)


# --------------------------------------------------------------------------
# Tile counting (shared by full-replay and compact-board sources)
# --------------------------------------------------------------------------

def count_engine_tiles(tiles) -> Counter:
    """Exact counts from a raw engine farm['tiles'] grid (full replays)."""
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
    """Counts from a 2-char-per-tile compact board (mg_tapes 'boards' field).
    COW is an upper bound: code 'co' also matches an empty (animal-less) coop.
    See CLAUDE.md and docs/mg_policy.md for the same caveat on this encoding."""
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


# --------------------------------------------------------------------------
# Order extraction from an hourly action stream (works for engine-format
# actions {"farmer":[...], "hands":[[...]], "market":[...]} whether they come
# from a full replay's steps[h][i]["action"], a compact tape's "actions" list,
# or a ladder_panel "our_actions"/"opp_actions" list -- same schema.
# --------------------------------------------------------------------------

def extract_orders(actions: list, max_day: int = ORDER_MAX_DAY) -> dict:
    max_hour = min(len(actions), (max_day + 1) * 24)
    wheat_buy = [0, 0]   # [hour0, hour1]
    wheat_sell = [0, 0]
    seeds_by_day = defaultdict(lambda: defaultdict(int))     # day -> crop -> units requested
    animals_by_day = defaultdict(lambda: defaultdict(int))   # day -> species -> units requested
    hires_by_day = defaultdict(int)
    land_requests_by_day = defaultdict(int)
    for hour in range(max_hour):
        act = actions[hour]
        if not isinstance(act, dict):
            continue
        day = hour // 24
        for cmd in (act.get("market") or []):
            if not cmd:
                continue
            op = cmd[0]
            if op == "HIRE":
                hires_by_day[day] += 1
            elif op == "BUY_LAND":
                land_requests_by_day[day] += 1
            elif op == "BUY_PRODUCT" and len(cmd) >= 3 and cmd[1] == "WHEAT" and hour < 2:
                wheat_buy[hour] += int(cmd[2])
            elif op == "SELL" and len(cmd) >= 3 and cmd[1] == "WHEAT" and hour < 2:
                wheat_sell[hour] += int(cmd[2])
            elif op == "BUY_SEED" and len(cmd) >= 3 and cmd[1] in SEED_COST:
                seeds_by_day[day][cmd[1]] += int(cmd[2])
            elif op == "BUY_ANIMAL" and len(cmd) >= 3 and cmd[1] in ANIMAL_COST:
                animals_by_day[day][cmd[1]] += int(cmd[2])
    return {
        "wheat_buy_hour0": wheat_buy[0], "wheat_buy_hour1": wheat_buy[1],
        "wheat_sell_hour0": wheat_sell[0], "wheat_sell_hour1": wheat_sell[1],
        "wheat_net_flip_units": (wheat_buy[0] + wheat_buy[1]) - (wheat_sell[0] + wheat_sell[1]),
        "seeds_by_day": {str(d): dict(v) for d, v in seeds_by_day.items()},
        "animals_by_day": {str(d): dict(v) for d, v in animals_by_day.items()},
        "hires_by_day": {str(d): n for d, n in hires_by_day.items()},
        "land_requests_by_day": {str(d): n for d, n in land_requests_by_day.items()},
        "first_land_request_day": min(land_requests_by_day) if land_requests_by_day else None,
    }


def new_shop_at(shops_by_day, day):
    if day <= 0 or day >= len(shops_by_day):
        return None
    prev, cur = shops_by_day[day - 1], shops_by_day[day]
    if len(cur) == len(prev) + 1:
        return cur[-1]
    return None


# --------------------------------------------------------------------------
# Full-replay parsing (exact board state). Shared by DSM (local), 5-leader and
# our-agent downloaded samples. Strictly one file in memory at a time.
# --------------------------------------------------------------------------

def parse_full_replay(path: Path, target_indices, max_day: int = MAX_DAY) -> dict:
    """target_indices: iterable of farm indices (0/1) whose profile to extract."""
    with path.open("r", encoding="utf-8") as f:
        d = json.load(f)
    team_names = list(d["info"]["TeamNames"])
    steps = d["steps"]
    n_days_full = len(steps) // 24
    n_days = min(max_day + 1, n_days_full)
    shops_by_day = []
    per_farm = {i: {"day_counts": [], "money": [], "hands_midday": [], "quadrants": [],
                     "orders": None} for i in target_indices}
    action_streams = {i: [] for i in target_indices}
    for day in range(n_days):
        hour = day * 24
        obs = steps[hour][0]["observation"]
        shops_by_day.append(list(obs["town"]["unlocked_shops"]))
        mid_hour = min(hour + 12, len(steps) - 1)
        mid_obs = steps[mid_hour][0]["observation"]
        for i in target_indices:
            farm = obs["farms"][i]
            per_farm[i]["day_counts"].append(dict(count_engine_tiles(farm["tiles"])))
            per_farm[i]["money"].append(farm["money"])
            per_farm[i]["hands_midday"].append(len(mid_obs["farms"][i]["hands"]))
            per_farm[i]["quadrants"].append(len(farm["unlocked_quadrants"]))
    max_action_hour = min(len(steps) - 1, (n_days) * 24)
    for i in target_indices:
        for h in range(max_action_hour):
            action_streams[i].append(steps[h + 1][i]["action"] if h + 1 < len(steps) else None)
    for i in target_indices:
        per_farm[i]["orders"] = extract_orders(action_streams[i], max_day=min(max_day, ORDER_MAX_DAY))
    last = len(steps) - 1
    final_cash = {str(i): steps[last][i]["reward"] for i in (0, 1)}
    episode_id = d["info"].get("EpisodeId") or path.stem
    record = {
        "episode": episode_id, "team_names": team_names, "n_days_full": n_days_full,
        "shops_by_day": shops_by_day,
        "per_farm": {str(i): per_farm[i] for i in target_indices},
        "final_cash": final_cash,
    }
    del d, steps, per_farm, action_streams
    return record


def parse_with_retry(path: Path, target_indices, max_day: int = MAX_DAY) -> dict:
    attempts = 0
    while True:
        wait_for_memory()
        try:
            return parse_full_replay(path, target_indices, max_day)
        except MemoryError:
            attempts += 1
            print(f"  MemoryError parsing {path.name}, retry {attempts} in 10s", file=sys.stderr)
            gc.collect()
            time.sleep(10)
            if attempts > 5:
                raise


# --------------------------------------------------------------------------
# Stage: DSM (local, all 108 replays; both DSM indices when self-play)
# --------------------------------------------------------------------------

def stage_dsm():
    cache_path = OUT / "dsm_profile_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    paths = sorted(DSM_DIR.glob("episode-*-replay.json"))
    for path in paths:
        key = path.stem
        if key in cache:
            continue
        # DSM index is discovered per-file (need TeamNames first); read just that header cheaply
        # is not worth a second pass -- parse with both indices requested, then keep only DSM's.
        record = parse_with_retry(path, target_indices=(0, 1), max_day=MAX_DAY)
        dsm_idx = [i for i, n in enumerate(record["team_names"]) if n == "DSM"]
        record["dsm_indices"] = dsm_idx
        record["self_play"] = len(dsm_idx) == 2
        cache[key] = record
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        print(f"  DSM {key}: {record['team_names']} dsm_idx={dsm_idx}", flush=True)
        del record
        gc.collect()
    print(f"DSM profile cache: {len(cache)} episodes -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Stage: 5 other leaders, local compact tapes (orders only, ALL available tapes)
# --------------------------------------------------------------------------

def stage_leader_local():
    cache_path = OUT / "leader_orders_cache.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"Leader-local order cache reused: {sum(len(v) for v in cache.values())} tapes <- {cache_path}")
        return cache
    cache = defaultdict(list)
    for folder, team_name in FIVE_LEADERS.items():
        for path in sorted((LEADER_DIR / folder).glob("*.json.gz")):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                t = json.load(f)
            orders = extract_orders(t["actions"], max_day=ORDER_MAX_DAY)
            cache[folder].append({
                "episode": t["episode"], "team": t["names"][t["seat"]], "seat": t["seat"],
                "shops": t["shops"], "orders": orders,
            })
    cache = dict(cache)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    n = sum(len(v) for v in cache.values())
    print(f"Leader-local order cache built: {n} tapes across {len(cache)} teams -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Stage: 5 other leaders, 12 downloaded full replays each (board state)
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


def stage_leader_full():
    cache_path = OUT / "leader_full_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    for folder, team_name in FIVE_LEADERS.items():
        idx = load_index(folder)
        match_name = idx["team"]  # exact TeamNames string, e.g. "Unknown Mother-Goose" (no "(current)" suffix)
        episodes = idx["episodes"][:N_FULL_PER_LEADER]
        cache.setdefault(folder, {})
        for ep in episodes:
            key = str(ep)
            if key in cache[folder]:
                continue
            wait_for_memory()
            try:
                path = download_replay(ep, RAW_DL)
            except Exception as e:
                print(f"  {team_name} {ep}: DOWNLOAD FAILED: {e}", file=sys.stderr)
                continue
            try:
                record = parse_with_retry(path, target_indices=(0, 1), max_day=MAX_DAY)
                target_idx = [i for i, n in enumerate(record["team_names"]) if n == match_name]
                record["target_indices"] = target_idx
                cache[folder][key] = record
                cache_path.write_text(json.dumps(cache), encoding="utf-8")
                print(f"  {team_name} {ep}: names={record['team_names']} target={target_idx}", flush=True)
            finally:
                path.unlink(missing_ok=True)
            gc.collect()
    print(f"Leader-full cache: {{{', '.join(f'{k}: {len(v)}' for k, v in cache.items())}}} -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Stage: Mother-Goose old, local compact tapes (584; boards+cash+actions)
# --------------------------------------------------------------------------

def stage_mg():
    cache_path = OUT / "mg_profile_cache.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"MG-old profile cache reused: {len(cache)} tapes <- {cache_path}")
        return cache
    cache = {}
    for path in sorted(MG_DIR.glob("*/*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            t = json.load(f)
        boards = t["boards"][:MAX_DAY + 1]
        day_counts = [dict(count_compact_board(b)) for b in boards]
        cash = t["cash"][:MAX_DAY + 1] if t.get("cash") else []
        shops_by_day = [list(s) for s in t["shops"][:MAX_DAY + 1]]
        orders = extract_orders(t["actions"], max_day=ORDER_MAX_DAY)
        own_final = None
        try:
            own_final = t["rewards"][t["seat"]]
        except Exception:
            pass
        cache[str(t["episode"])] = {
            "episode": t["episode"], "submission": t["submission"], "seat": t["seat"],
            "shops_by_day": shops_by_day, "day_counts": day_counts, "cash": cash,
            "orders": orders, "own_final_cash": own_final,
        }
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    print(f"MG-old profile cache built: {len(cache)} tapes -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Stage: our own agent, local ladder_panel actions (ALL 856 games, orders only)
# --------------------------------------------------------------------------

def stage_our_local():
    cache_path = OUT / "our_orders_cache.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"Our-local order cache reused: {len(cache)} games <- {cache_path}")
        return cache
    cache = {}
    for sub in ("56368334", "56395605"):
        for path in sorted((LADDER_DIR / sub).glob("*.json.gz")):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                t = json.load(f)
            orders = extract_orders(t["our_actions"], max_day=ORDER_MAX_DAY)
            cache[str(t["episode"])] = {
                "episode": t["episode"], "submission": sub, "seat": t["seat"],
                "shops": t["shops"], "orders": orders, "rewards": t.get("rewards"),
            }
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    print(f"Our-local order cache built: {len(cache)} games -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Stage: our own agent, 12 downloaded full replays (board state)
# --------------------------------------------------------------------------

def pick_our_download_targets(n=N_FULL_OURS):
    games = json.loads(LADDER_GAMES_JSON.read_text(encoding="utf-8"))
    rows = [r for r in games if r["submission"] == OUR_SUBMISSION_FOR_DOWNLOAD and r.get("opp_rating")]
    rows.sort(key=lambda r: float(r["opp_rating"]), reverse=True)
    return rows[:n]


def stage_our_full():
    cache_path = OUT / "our_full_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    targets = pick_our_download_targets()
    for row in targets:
        ep = row["episode"]
        key = str(ep)
        if key in cache:
            continue
        wait_for_memory()
        try:
            path = download_replay(ep, RAW_DL)
        except Exception as e:
            print(f"  ours {ep}: DOWNLOAD FAILED: {e}", file=sys.stderr)
            continue
        try:
            record = parse_with_retry(path, target_indices=(0, 1), max_day=MAX_DAY)
            our_idx = [i for i, n in enumerate(record["team_names"]) if n == "Ghost Rule"]
            record["our_indices"] = our_idx
            record["opp_rating"] = row.get("opp_rating")
            record["opp_team"] = row.get("opp_team")
            cache[key] = record
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
            print(f"  ours {ep}: names={record['team_names']} our_idx={our_idx} opp_rating={row.get('opp_rating')}", flush=True)
        finally:
            path.unlink(missing_ok=True)
        gc.collect()
    print(f"Our-full cache: {len(cache)} episodes -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Stage: field-wide opponent-opening features from all 856 ladder_panel games
# --------------------------------------------------------------------------

def load_ladder_games_index():
    games = json.loads(LADDER_GAMES_JSON.read_text(encoding="utf-8"))
    return {int(r["episode"]): r for r in games}


def stage_field():
    cache_path = OUT / "field_cache.json"
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"Field cache reused: {len(cache)} games <- {cache_path}")
        return cache
    ladder_idx = load_ladder_games_index()
    cache = {}
    for sub in ("56368334", "56395605"):
        for path in sorted((LADDER_DIR / sub).glob("*.json.gz")):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                t = json.load(f)
            ep = t["episode"]
            orders = extract_orders(t["opp_actions"], max_day=ORDER_MAX_DAY)
            row = ladder_idx.get(ep, {})
            cache[str(ep)] = {
                "episode": ep, "submission": sub, "shops": t["shops"],
                "opponent": t.get("opponent"), "orders": orders,
                "opp_rating": row.get("opp_rating"), "opp_rank": row.get("opp_rank"),
                "opp_team": row.get("opp_team"),
                "our_margin": row.get("margin"), "our_win": row.get("win"),
            }
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    print(f"Field cache built: {len(cache)} games -> {cache_path}")
    return cache


# --------------------------------------------------------------------------
# Analysis helpers
# --------------------------------------------------------------------------

def mean_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def median_or_none(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 3) if xs else None


def spread(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    return min(xs), max(xs)


def get_count(day_counts, day, product):
    if day is None or day >= len(day_counts):
        return None
    return day_counts[day].get(product, 0)


def flatten_full_cache_observations(cache: dict, indices_key: str) -> list:
    """cache: {folder_or_key: {episode: record}} or {episode: record} directly."""
    obs = []
    if not cache:
        return obs
    sample_val = next(iter(cache.values()))
    # Detect nesting depth: DSM/our-full caches are {episode: record}; the
    # 5-leader full cache is {folder: {episode: record}}.
    if "per_farm" in sample_val:
        records = list(cache.values())
    else:
        records = [rec for group in cache.values() for rec in group.values()]
    for rec in records:
        idxs = rec.get(indices_key) or rec.get("dsm_indices") or rec.get("target_indices") or rec.get("our_indices") or []
        for i in idxs:
            farm = rec["per_farm"].get(str(i))
            if not farm:
                continue
            opp_i = 1 - i
            opp_final = rec["final_cash"].get(str(opp_i))
            obs.append({
                "episode": rec["episode"], "farm_index": i,
                "shops_by_day": rec["shops_by_day"], "day_counts": farm["day_counts"],
                "money": farm["money"], "hands": farm["hands_midday"], "quadrants": farm["quadrants"],
                "orders": farm["orders"], "final_cash": rec["final_cash"].get(str(i)),
                "opp_final_cash": opp_final,
            })
    return obs


def land_days_from_quadrants(quadrants: list) -> dict:
    """Day index (0-based) each quadrant count first increases, exact from board state."""
    out = {}
    for day in range(1, len(quadrants)):
        if quadrants[day] > quadrants[day - 1]:
            out[quadrants[day]] = day  # keyed by resulting quadrant count (2,3,4)
    return out


def profile_summary(observations: list, label: str) -> dict:
    """Per-day-start means/spread for tile counts, cash, hands, quadrants, plus
    order aggregates (flip, seeds, animals, hires) and land-day histogram."""
    by_day = {}
    for day in range(MAX_DAY + 1):
        row = {}
        for product in CROPS + ANIMALS:
            vals = [get_count(o["day_counts"], day, product) for o in observations]
            vals = [v for v in vals if v is not None]
            lo, hi = spread(vals)
            row[product] = {"mean": mean_or_none(vals), "n": len(vals), "min": lo, "max": hi}
        cash_vals = [o["money"][day] for o in observations if day < len(o["money"])]
        hands_vals = [o["hands"][day] for o in observations if day < len(o["hands"])]
        quad_vals = [o["quadrants"][day] for o in observations if day < len(o["quadrants"])]
        row["CASH"] = {"mean": mean_or_none(cash_vals), "n": len(cash_vals), **dict(zip(("min", "max"), spread(cash_vals)))}
        row["HANDS"] = {"mean": mean_or_none(hands_vals), "n": len(hands_vals), **dict(zip(("min", "max"), spread(hands_vals)))}
        row["QUADRANTS"] = {"mean": mean_or_none(quad_vals), "n": len(quad_vals), **dict(zip(("min", "max"), spread(quad_vals)))}
        by_day[str(day)] = row

    land_hist = Counter()
    for o in observations:
        for q, day in land_days_from_quadrants(o["quadrants"]).items():
            land_hist[f"quadrant{q}_day{day}"] += 1

    flip_units = [o["orders"]["wheat_net_flip_units"] for o in observations if o.get("orders")]
    buy0 = [o["orders"]["wheat_buy_hour0"] for o in observations if o.get("orders")]
    sell0 = [o["orders"]["wheat_sell_hour0"] for o in observations if o.get("orders")]
    buy1 = [o["orders"]["wheat_buy_hour1"] for o in observations if o.get("orders")]

    seeds_by_day_crop = defaultdict(lambda: defaultdict(list))
    animals_by_day_species = defaultdict(lambda: defaultdict(list))
    hires_by_day = defaultdict(list)
    for o in observations:
        ordrs = o.get("orders") or {}
        for day_s, crops in (ordrs.get("seeds_by_day") or {}).items():
            for crop, n in crops.items():
                seeds_by_day_crop[day_s][crop].append(n)
        for day_s, species in (ordrs.get("animals_by_day") or {}).items():
            for sp, n in species.items():
                animals_by_day_species[day_s][sp].append(n)
        for day_s, n in (ordrs.get("hires_by_day") or {}).items():
            hires_by_day[day_s].append(n)

    def agg_nested(nested):
        out = {}
        for day_s, inner in nested.items():
            out[day_s] = {k: {"mean": mean_or_none(v), "n": len(v), "sum": sum(v)} for k, inner_v in [(k, v)] for k, v in inner.items()}
        return out

    return {
        "source": label, "n_observations": len(observations),
        "by_day": by_day,
        "land_purchase_day_histogram": dict(sorted(land_hist.items())),
        "wheat_flip": {
            "net_units_mean": mean_or_none(flip_units), "net_units_n": len(flip_units),
            "buy_hour0_mean": mean_or_none(buy0), "sell_hour0_mean": mean_or_none(sell0),
            "buy_hour1_mean": mean_or_none(buy1),
            "pct_with_any_hour01_activity": round(100 * sum(1 for o in observations if o.get("orders") and (o["orders"]["wheat_buy_hour0"] or o["orders"]["wheat_sell_hour0"] or o["orders"]["wheat_buy_hour1"])) / len(observations), 1) if observations else None,
        },
        "seeds_by_day": {day_s: {crop: {"mean": mean_or_none(v), "n": len(v)} for crop, v in crops.items()}
                         for day_s, crops in seeds_by_day_crop.items()},
        "animals_by_day": {day_s: {sp: {"mean": mean_or_none(v), "n": len(v)} for sp, v in species.items()}
                           for day_s, species in animals_by_day_species.items()},
        "hires_by_day": {day_s: {"mean": mean_or_none(v), "n": len(v)} for day_s, v in hires_by_day.items()},
    }


def mg_observations(mg_cache: dict) -> list:
    obs = []
    for rec in mg_cache.values():
        obs.append({
            "episode": rec["episode"], "shops_by_day": rec["shops_by_day"],
            "day_counts": rec["day_counts"], "money": rec["cash"], "hands": [], "quadrants": [],
            "orders": rec["orders"], "final_cash": rec.get("own_final_cash"), "opp_final_cash": None,
        })
    return obs


def orders_only_observations(cache: dict, key="orders") -> list:
    """For sources that only have order data (no board): wrap so profile_summary's
    order-aggregation logic works, with empty day_counts/money/hands/quadrants."""
    obs = []
    items = cache.values() if not any(isinstance(v, list) for v in cache.values()) else [t for lst in cache.values() for t in lst]
    for rec in items:
        obs.append({
            "episode": rec.get("episode"), "shops_by_day": rec.get("shops"),
            "day_counts": [], "money": [], "hands": [], "quadrants": [],
            "orders": rec[key], "final_cash": None, "opp_final_cash": None,
        })
    return obs


# --------------------------------------------------------------------------
# Consistency (task 2): within-agent spread, and shop-conditioning
# --------------------------------------------------------------------------

def consistency_table(observations: list, day: int, products=("COW", "SHEEP", "GOOSE", "MELON", "WHEAT")) -> dict:
    out = {}
    for p in products:
        vals = [get_count(o["day_counts"], day, p) for o in observations]
        vals = [v for v in vals if v is not None]
        if not vals:
            out[p] = {"n": 0}
            continue
        out[p] = {"mean": mean_or_none(vals), "stdev": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
                   "min": min(vals), "max": max(vals), "n": len(vals)}
    return out


def shop_conditioned_table(observations: list, day: int, reveal_day: int, product: str) -> dict:
    """Group day-`day` product count by the shop revealed at `reveal_day` (3 or 6)."""
    groups = defaultdict(list)
    for o in observations:
        sbd = o["shops_by_day"]
        shop = new_shop_at(sbd, reveal_day) if reveal_day > 0 else None
        if reveal_day == 3 and len(sbd) > 3:
            shop = sbd[3][0] if sbd[3] else None
        if shop is None:
            continue
        v = get_count(o["day_counts"], day, product)
        if v is not None:
            groups[shop].append(v)
    return {shop: {"mean": mean_or_none(v), "n": len(v)} for shop, v in sorted(groups.items())}


# --------------------------------------------------------------------------
# Field-wide clustering (task 4): rule-based clusters from opponent opening features
# --------------------------------------------------------------------------

def classify_opening(orders: dict) -> str:
    animals_d6 = Counter()
    for day_s, species in (orders.get("animals_by_day") or {}).items():
        if int(day_s) <= 6:
            for sp, n in species.items():
                animals_d6[sp] += n
    melon_d6 = 0
    for day_s, crops in (orders.get("seeds_by_day") or {}).items():
        if int(day_s) <= 6:
            melon_d6 += crops.get("MELON", 0)
    flip = orders.get("wheat_net_flip_units", 0) or 0
    land_day = orders.get("first_land_request_day")
    sheep, cow, goose = animals_d6.get("SHEEP", 0), animals_d6.get("COW", 0), animals_d6.get("GOOSE", 0)
    total_animals = sheep + cow + goose

    # Herd axis
    if total_animals == 0:
        herd = "no-herd-by-d6"
    elif sheep >= cow and sheep >= goose and sheep >= 2:
        herd = "sheep-led"
    elif cow >= sheep and cow >= goose and cow >= 2:
        herd = "cow-led"
    elif goose > sheep and goose > cow:
        herd = "goose-led"
    else:
        herd = "mixed-small"

    # Flip axis (V45/MG-old style large opening wheat round trip is ~13-18 net units
    # requested at hour 0-1; treat >=10 units of hour0-1 wheat activity as "has a flip")
    has_flip = "flip" if abs(flip) >= 8 or (orders.get("wheat_buy_hour0", 0) + orders.get("wheat_buy_hour1", 0)) >= 10 else "no-flip"

    # Land axis: field-standard is day 6 (2nd quadrant); early = before day5, late = after day7/none
    if land_day is None:
        land = "land-none-by-d8"
    elif land_day <= 4:
        land = "land-early"
    elif land_day in (5, 6):
        land = "land-d6-standard"
    else:
        land = "land-late"

    melon = "melon-heavy" if melon_d6 >= 10 else ("melon-light" if melon_d6 > 0 else "melon-none")
    return f"{herd}/{has_flip}/{land}/{melon}"


def cluster_field(field_cache: dict) -> dict:
    rows = list(field_cache.values())
    for r in rows:
        r["_cluster"] = classify_opening(r["orders"])
    counts = Counter(r["_cluster"] for r in rows)
    top_clusters = [c for c, _ in counts.most_common(12)]

    def rating_band(r):
        rt = r.get("opp_rating")
        try:
            rt = float(rt)
        except (TypeError, ValueError):
            return "unknown"
        if rt >= 2900:
            return "2900+"
        if rt >= 2500:
            return "2500-2899"
        if rt >= 1500:
            return "1500-2499"
        return "<1500"

    by_cluster = {}
    for c in top_clusters:
        members = [r for r in rows if r["_cluster"] == c]
        margins = [r["our_margin"] for r in members if r.get("our_margin") is not None]
        wins = [r["our_win"] for r in members if r.get("our_win") is not None]
        band_counts = Counter(rating_band(r) for r in members)
        by_cluster[c] = {
            "n": len(members), "share_pct": round(100 * len(members) / len(rows), 2),
            "band_counts": dict(band_counts),
            "our_mean_margin": mean_or_none(margins), "our_win_rate_pct": round(100 * sum(wins) / len(wins), 1) if wins else None,
            "n_with_margin": len(margins),
        }
    band_totals = Counter(rating_band(r) for r in rows)
    umg_like = sum(1 for r in rows if r["_cluster"].startswith("cow-led/flip/land-d6-standard")
                   or r["_cluster"].startswith("mixed-small/flip/land-d6-standard"))
    return {
        "n_games": len(rows), "n_clusters_total": len(counts), "by_cluster_top12": by_cluster,
        "band_totals": dict(band_totals),
        "umg_v45_like_n": umg_like, "umg_v45_like_pct": round(100 * umg_like / len(rows), 2) if rows else None,
        "umg_v45_like_definition": "cow-or-mixed herd by day 6 AND an opening wheat flip (>=8 net units or >=10 units bought hour0-1) AND land purchase requested day 5-6",
    }


# --------------------------------------------------------------------------
# Task 5: day-6/7 valuation
# --------------------------------------------------------------------------

def valuation_at_day(observations: list, day: int) -> dict:
    """Value = cash + animals(at purchase price) + land(cumulative price) + crops(seed cost).
    Land value approximated from quadrant COUNT (exact for full-replay sources; None
    for order-only sources, whose 'quadrants' list is empty)."""
    vals = []
    for o in observations:
        cash = o["money"][day] if day < len(o["money"]) else None
        if cash is None:
            continue
        counts = o["day_counts"][day] if day < len(o["day_counts"]) else {}
        animal_value = sum(ANIMAL_COST[a] * counts.get(a, 0) for a in ANIMALS)
        crop_value = sum(SEED_COST[c] * counts.get(c, 0) for c in CROPS)
        land_value = 0
        if day < len(o["quadrants"]):
            q = o["quadrants"][day]
            land_value = sum(LAND_INCREMENTAL_PRICE[:max(0, q - 1)])
        vals.append(cash + animal_value + crop_value + land_value)
    return {"day": day, "mean_installed_value": mean_or_none(vals), "n": len(vals),
            "min": min(vals) if vals else None, "max": max(vals) if vals else None,
            "note": "cash + animals*purchase_price + crops*seed_cost + land*cumulative_price; "
                    "land term is 0 for sources with no board (order-only)."}


# --------------------------------------------------------------------------
# Report rendering
# --------------------------------------------------------------------------

def fmt(x):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:,.1f}"
    return f"{x:,}"


def render_profile_markdown(prof: dict) -> str:
    L = [f"### {prof['source']} (n={prof['n_observations']})", ""]
    L.append("| Day | Cows | Sheep | Geese | Melon | Wheat | Straw | Tomato | Carrot | Cash | Hands | Quadrants |")
    L.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for day in range(MAX_DAY + 1):
        row = prof["by_day"][str(day)]
        def c(p):
            r = row[p]
            return f"{fmt(r['mean'])}" + (f" [{r['min']}-{r['max']}]" if r["n"] and r["min"] != r["max"] else "")
        L.append(f"| {day} | {c('COW')} | {c('SHEEP')} | {c('GOOSE')} | {c('MELON')} | {c('WHEAT')} | "
                  f"{c('STRAWBERRY')} | {c('TOMATO')} | {c('CARROT')} | {fmt(row['CASH']['mean'])} | "
                  f"{fmt(row['HANDS']['mean'])} | {fmt(row['QUADRANTS']['mean'])} |")
    L.append("")
    L.append(f"Land purchase day histogram (exact, from quadrant-count transitions where board state is available): "
              f"{prof['land_purchase_day_histogram']}")
    wf = prof["wheat_flip"]
    L.append(f"Wheat flip (hour0/1 requests): net units mean {fmt(wf['net_units_mean'])} (n={wf['net_units_n']}), "
              f"buy@h0 {fmt(wf['buy_hour0_mean'])}, sell@h0 {fmt(wf['sell_hour0_mean'])}, buy@h1 {fmt(wf['buy_hour1_mean'])}, "
              f"{fmt(wf['pct_with_any_hour01_activity'])}% of games touch wheat at hour 0-1.")
    L.append("")
    hires = prof["hires_by_day"]
    hire_line = ", ".join(f"d{d}:{fmt(v['mean'])}" for d, v in sorted(hires.items(), key=lambda kv: int(kv[0])))
    L.append(f"HIREs requested/day (0-{ORDER_MAX_DAY}): {hire_line}")
    L.append("")
    for label, nested in (("Seeds requested by crop/day", prof["seeds_by_day"]),
                           ("Animals requested by species/day", prof["animals_by_day"])):
        L.append(f"{label}:")
        for d in sorted(nested, key=int):
            parts = ", ".join(f"{k}:{fmt(v['mean'])}(n={v['n']})" for k, v in nested[d].items())
            L.append(f"  - day {d}: {parts}")
        L.append("")
    return "\n".join(L)


def build_report(analysis: dict) -> str:
    L = ["# Top-player opening profiles, days 0-7: is the field converging on Mother-Goose/V45?", "",
         "Generated by `scripts/analyze_openings_2026.py`. No games simulated; all numbers parsed from "
         "recorded replay/tape JSON. Tile/cash/hands/quadrant counts from FULL REPLAYS are exact board "
         "state; anything under 'orders' (wheat flip, seed/animal buys, hires, land) is a REQUESTED "
         "command from an action stream and may not have been filled (see module docstring).", ""]
    L.append("## Headline")
    L.append("")
    for b in analysis["headline"]:
        L.append(f"- {b}")
    L.append("")
    L.append("## 1. Opening profiles by agent")
    L.append("")
    for key in ("dsm", "mg_old", "ours_full", "ours_orders_only"):
        if key in analysis["profiles"]:
            L.append(render_profile_markdown(analysis["profiles"][key]))
    for folder, team in FIVE_LEADERS.items():
        pk = f"leader_full_{folder}"
        ok = f"leader_orders_{folder}"
        if pk in analysis["profiles"]:
            L.append(f"#### {team} -- board state (downloaded full replays)")
            L.append(render_profile_markdown(analysis["profiles"][pk]))
        if ok in analysis["profiles"]:
            L.append(f"#### {team} -- orders only (all local compact tapes, larger n)")
            L.append(render_profile_markdown(analysis["profiles"][ok]))
    L.append("## 2. Consistency: fixed opening or shop-dependent?")
    L.append("")
    for name, tbl in analysis["consistency"].items():
        L.append(f"### {name}")
        L.append("")
        L.append("| Day | Product | Mean | Stdev | Min | Max | n |")
        L.append("|---|---|---:|---:|---:|---:|---:|")
        for day, prods in tbl.items():
            for p, row in prods.items():
                if row.get("n", 0) == 0:
                    continue
                L.append(f"| {day} | {p} | {fmt(row.get('mean'))} | {fmt(row.get('stdev'))} | "
                          f"{fmt(row.get('min'))} | {fmt(row.get('max'))} | {row['n']} |")
        L.append("")
    L.append("### Shop-conditioning: day-6 herd count by day-3 (first) shop revealed")
    L.append("")
    for name, tbl in analysis["shop_conditioned"].items():
        L.append(f"**{name}**: " + ", ".join(f"{shop}: {fmt(v['mean'])} (n={v['n']})" for shop, v in tbl.items()))
    L.append("")
    L.append("## 3. Divergence: pairwise day-3/day-6 comparison")
    L.append("")
    L.append("| Agent | Day3 cow/sheep/goose/melon/wheat | Day6 cow/sheep/goose/melon/wheat | Day6 cash |")
    L.append("|---|---|---|---:|")
    for name, row in analysis["divergence_rows"].items():
        L.append(f"| {name} | {row['day3']} | {row['day6']} | {fmt(row['day6_cash'])} |")
    L.append("")
    L.append("## 4. Field-wide clustering of all recorded ladder opponents")
    L.append("")
    fc = analysis["field_clusters"]
    L.append(f"n={fc['n_games']} opponent games across {fc['n_clusters_total']} distinct opening signatures. "
              f"Rating-band totals: {fc['band_totals']}. UMG/V45-like openings "
              f"({fc['umg_v45_like_definition']}): {fc['umg_v45_like_n']} games ({fmt(fc['umg_v45_like_pct'])}%).")
    L.append("")
    L.append("| Cluster (herd/flip/land/melon by day 6-8) | n | share% | rating bands | our mean margin | our win% |")
    L.append("|---|---:|---:|---|---:|---:|")
    for c, row in sorted(fc["by_cluster_top12"].items(), key=lambda kv: -kv[1]["n"]):
        L.append(f"| {c} | {row['n']} | {row['share_pct']} | {row['band_counts']} | "
                  f"{fmt(row['our_mean_margin'])} (n={row['n_with_margin']}) | {fmt(row['our_win_rate_pct'])} |")
    L.append("")
    L.append("## 5. Is it worth anything? Installed value at day 6/7")
    L.append("")
    L.append("Valuation: cash + animals x purchase price + crops(tile count) x seed cost + land x cumulative "
              "quadrant price. Land term is 0 wherever board state is unavailable (order-only sources).")
    L.append("")
    L.append("| Agent | Day6 installed value | n | Day7 installed value | n |")
    L.append("|---|---:|---:|---:|---:|")
    for name, row in analysis["valuation"].items():
        d6, d7 = row["day6"], row["day7"]
        L.append(f"| {name} | {fmt(d6['mean_installed_value'])} | {d6['n']} | {fmt(d7['mean_installed_value'])} | {d7['n']} |")
    L.append("")
    L.append("## Caveats")
    L.append("")
    for c in analysis["caveats"]:
        L.append(f"- {c}")
    L.append("")
    return "\n".join(L)


# --------------------------------------------------------------------------
# Main analysis assembly
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                     choices=["all", "dsm", "leader-local", "leader-full", "mg", "our-local", "our-full", "field", "report"])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    stages = {
        "dsm": stage_dsm, "leader-local": stage_leader_local, "leader-full": stage_leader_full,
        "mg": stage_mg, "our-local": stage_our_local, "our-full": stage_our_full, "field": stage_field,
    }
    if args.stage != "all" and args.stage != "report":
        stages[args.stage]()
        return
    if args.stage == "all":
        print("== Stage: DSM (local) ==")
        dsm_cache = stage_dsm()
        print("== Stage: 5-leader local orders ==")
        leader_orders_cache = stage_leader_local()
        print("== Stage: 5-leader full (download) ==")
        leader_full_cache = stage_leader_full()
        print("== Stage: Mother-Goose old (local) ==")
        mg_cache = stage_mg()
        print("== Stage: our local orders ==")
        our_orders_cache = stage_our_local()
        print("== Stage: our full (download) ==")
        our_full_cache = stage_our_full()
        print("== Stage: field-wide (local) ==")
        field_cache = stage_field()
    else:  # report: load whatever caches exist
        def maybe(fn, path):
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        dsm_cache = maybe(None, OUT / "dsm_profile_cache.json")
        leader_orders_cache = maybe(None, OUT / "leader_orders_cache.json")
        leader_full_cache = maybe(None, OUT / "leader_full_cache.json")
        mg_cache = maybe(None, OUT / "mg_profile_cache.json")
        our_orders_cache = maybe(None, OUT / "our_orders_cache.json")
        our_full_cache = maybe(None, OUT / "our_full_cache.json")
        field_cache = maybe(None, OUT / "field_cache.json")

    print("== Assembling analysis ==")
    dsm_obs = flatten_full_cache_observations(dsm_cache, "dsm_indices")
    ours_full_obs = flatten_full_cache_observations(our_full_cache, "our_indices")
    mg_obs = mg_observations(mg_cache)

    analysis = {"profiles": {}, "consistency": {}, "shop_conditioned": {}, "divergence_rows": {},
                "field_clusters": {}, "valuation": {}, "caveats": [], "headline": []}

    analysis["profiles"]["dsm"] = profile_summary(dsm_obs, "DSM (full replays, exact board)")
    analysis["profiles"]["mg_old"] = profile_summary(mg_obs, "Mother-Goose old (584 tapes; cow count is an upper bound)")
    analysis["profiles"]["ours_full"] = profile_summary(ours_full_obs, "Ours / Ghost Rule (12 downloaded full replays, exact board)")
    ours_orders_obs = orders_only_observations(our_orders_cache)
    analysis["profiles"]["ours_orders_only"] = profile_summary(ours_orders_obs, "Ours / Ghost Rule (856 ladder games, orders only)")

    leader_full_profile_obs = {}
    for folder, team in FIVE_LEADERS.items():
        group = leader_full_cache.get(folder, {})
        obs = flatten_full_cache_observations({folder: group} if group else {}, "target_indices") if group else []
        leader_full_profile_obs[folder] = obs
        if obs:
            analysis["profiles"][f"leader_full_{folder}"] = profile_summary(obs, f"{team} (12 downloaded full replays, exact board)")
        orders_obs = orders_only_observations({folder: leader_orders_cache.get(folder, [])}) if leader_orders_cache.get(folder) else []
        if orders_obs:
            analysis["profiles"][f"leader_orders_{folder}"] = profile_summary(orders_obs, f"{team} (all local compact tapes, orders only)")

    # Task 2: consistency
    analysis["consistency"]["DSM"] = {str(d): consistency_table(dsm_obs, d) for d in (1, 3, 6)}
    analysis["consistency"]["Mother-Goose-old"] = {str(d): consistency_table(mg_obs, d) for d in (1, 3, 6)}
    analysis["consistency"]["Ours"] = {str(d): consistency_table(ours_full_obs, d) for d in (1, 3, 6)}
    for folder, team in FIVE_LEADERS.items():
        obs = leader_full_profile_obs.get(folder, [])
        if obs:
            analysis["consistency"][team] = {str(d): consistency_table(obs, d) for d in (1, 3, 6)}

    analysis["shop_conditioned"]["DSM day6 cow-count by day3 shop"] = shop_conditioned_table(dsm_obs, 6, 3, "COW")
    analysis["shop_conditioned"]["MG-old day6 sheep-count by day3 shop"] = shop_conditioned_table(mg_obs, 6, 3, "SHEEP")
    analysis["shop_conditioned"]["Ours day6 cow-count by day3 shop"] = shop_conditioned_table(ours_full_obs, 6, 3, "COW")

    # Task 3: divergence rows
    def board_tuple(obs, day):
        return tuple(round(get_count(o["day_counts"], day, p) or 0, 1) for o in [None] if False) or None

    def mean_board(obs, day):
        vals = {p: mean_or_none([get_count(o["day_counts"], day, p) for o in obs]) for p in ("COW", "SHEEP", "GOOSE", "MELON", "WHEAT")}
        return "/".join(fmt(vals[p]) for p in ("COW", "SHEEP", "GOOSE", "MELON", "WHEAT"))

    def mean_cash(obs, day):
        return mean_or_none([o["money"][day] for o in obs if day < len(o["money"])])

    div_sources = {"DSM": dsm_obs, "Mother-Goose-old": mg_obs, "Ours": ours_full_obs}
    for folder, team in FIVE_LEADERS.items():
        div_sources[team] = leader_full_profile_obs.get(folder, [])
    for name, obs in div_sources.items():
        if not obs:
            continue
        analysis["divergence_rows"][name] = {"day3": mean_board(obs, 3), "day6": mean_board(obs, 6), "day6_cash": mean_cash(obs, 6)}

    # Task 4: field-wide clustering
    analysis["field_clusters"] = cluster_field(field_cache)

    # Task 5: valuation at day 6/7
    for name, obs in list(div_sources.items()) + [("Ours (orders only, 856 games)", ours_orders_obs), ("Mother-Goose-old", mg_obs)]:
        if not obs:
            continue
        analysis["valuation"][name] = {"day6": valuation_at_day(obs, 6), "day7": valuation_at_day(obs, 7)}

    analysis["caveats"] = [
        "Tile/cash/hands/quadrant counts are EXACT board state only for sources parsed from full replays "
        "(DSM: all 108 local; 5 leaders and ours: 12 downloaded each). Mother-Goose-old's cow count is an "
        "UPPER BOUND (its compact board encoding conflates an occupied cow pasture with an empty coop, code 'co').",
        "'orders' fields (wheat flip, seed/animal buys, HIREs, land) are REQUESTED commands from an action "
        "stream, not confirmed fills, for every source except when cross-checked against the same full "
        "replay's own board (DSM, and the 12-game full samples for the 5 leaders and ours). The 10-orders-"
        "per-turn cap and insufficient cash/stock can silently drop or shrink a request.",
        "5-leader and our-agent full-replay samples are 12 games each (small-n for day-by-day spread); "
        "the much larger local order-only samples (all locally available compact tapes / all 856 ladder "
        "games) only see requests, not board state.",
        "Field-wide clustering (task 4) uses a hand-built rule-based classifier on day<=6/8 opponent order "
        "features (herd species mix, opening wheat-flip size, first land request day, melon seed volume); "
        "it groups games with only order-level information, so a cluster boundary can be crossed by a "
        "request that was actually dropped by the engine.",
        "Our win-rate/margin by opponent cluster (task 4/5) is confounded by opponent strength: stronger "
        "opponents may cluster differently AND be harder to beat regardless of opening. Rating-band counts "
        "are reported alongside each cluster so this confound is visible, not controlled for.",
        f"Downloaded-full-replay samples: 5 leaders take the {N_FULL_PER_LEADER} most recent episodes listed "
        f"in each team's data/leader_tapes/<team>/index.json; ours takes the {N_FULL_OURS} highest-opp_rating "
        f"games recorded for submission {OUR_SUBMISSION_FOR_DOWNLOAD} in ladder_games.json (8 of them are "
        "rated 2900+; the rest are the next-highest available, down to ~2855).",
    ]

    # Headline bullets
    dsm_p = analysis["profiles"]["dsm"]["by_day"]["3"]
    mg_p = analysis["profiles"]["mg_old"]["by_day"]["3"]
    ours_p = analysis["profiles"]["ours_full"]["by_day"]["3"] if analysis["profiles"]["ours_full"]["n_observations"] else None
    def board_str(row):
        return f"{fmt(row['COW']['mean'])}c/{fmt(row['SHEEP']['mean'])}s/{fmt(row['MELON']['mean'])}me/{fmt(row['WHEAT']['mean'])}wh"
    headline = [
        f"Field-standard reference (docs/mg_policy.md, docs/leader_segments.md): day-3 board 3 cows/2 sheep/"
        f"12 melons/7 wheat. DSM day-3 (n={analysis['profiles']['dsm']['n_observations']}): {board_str(dsm_p)}. "
        f"Mother-Goose-old day-3 (n={analysis['profiles']['mg_old']['n_observations']}): {board_str(mg_p)}."
        + (f" Ours day-3 (n={analysis['profiles']['ours_full']['n_observations']}): {board_str(ours_p)}." if ours_p else ""),
        f"UMG/V45-like opening share among all {analysis['field_clusters']['n_games']} recorded ladder "
        f"opponents: {fmt(analysis['field_clusters']['umg_v45_like_pct'])}% "
        f"({analysis['field_clusters']['umg_v45_like_definition']}).",
        f"{analysis['field_clusters']['n_clusters_total']} distinct herd/flip/land/melon opening signatures "
        f"appear among {analysis['field_clusters']['n_games']} opponent games; see section 4 for the top 12 "
        f"by share and their rating-band composition and our margin/win-rate against each.",
        "See section 3 for exact day-3/day-6 pairwise comparisons across DSM, the 5 other current leaders, "
        "Mother-Goose-old and our own agent, and section 5 for whether differing openings reach different "
        "installed-value positions by day 6-7.",
    ]
    analysis["headline"] = headline

    (OUT / "analysis.json").write_text(json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    report = build_report(analysis)
    (OUT / "summary.md").write_text(report, encoding="utf-8")
    print(f"Wrote {OUT / 'analysis.json'}")
    print(f"Wrote {OUT / 'summary.md'}")


if __name__ == "__main__":
    main()

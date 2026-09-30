"""Gate G2: select which leader recording(s) to FOLLOW using only what an agent can see
(shops revealed so far, the day, and its own current board).

Deliverable per the 2026-09-24 task brief:
  - retrieve(...): pure-Python (stdlib only) k-NN selector over the leader-semantics corpus,
    usable standalone inside an agent (loads the corpus index once, module-level cache).
  - Evaluation code (retrieval vs ridge regression, LOGO / LOTO / same-family variants,
    grid over k in {1,3,5} x lambda in {0,0.25,0.5,1}) comparing against two baselines.

Corpus: data/leader_semantics/<team_id>/<episode>.json.gz (240 games, 6 teams x 40).
Demand/weights/checkpoint reuse the values in scripts/build_mg_tape_agent.py's ROUTER
template (_MGT_DEMAND, _MGT_WEIGHT, _mgt_vec, _mgt_distance, _mgt_hamming) - that template
is a raw string used for codegen, not an importable module, so the same constants/formulas
are reproduced verbatim below rather than imported.

Run as a script to execute the full evaluation:
    .venv/Scripts/python.exe scripts/leader_plan_retrieval.py
"""
import gzip
import json
import glob
import os
import math
import collections

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_GLOB = os.path.join(REPO_ROOT, 'data', 'leader_semantics', '*', '*.json.gz')
RESULTS_DIR = os.path.join(REPO_ROOT, 'results', 'fresh', 'leader_retrieval')

DECISION_DAYS = (3, 6, 9, 12, 15, 18, 21)
HORIZONS = (3, 6)
K_GRID = (1, 3, 5)
LAM_GRID = (0.0, 0.25, 0.5, 1.0)

# ---------------------------------------------------------------------------
# Demand / weight model - copied verbatim from the ROUTER template in
# scripts/build_mg_tape_agent.py (_MGT_DEMAND / _MGT_WEIGHT / _mgt_vec / _mgt_distance).
# ---------------------------------------------------------------------------
_DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
           'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
           'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
           'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
           'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}
_WEIGHT = {'STRAWBERRY': 3.0, 'TOMATO': 2.0, 'WOOL': 2.0, 'CARROT': 1.5, 'MILK': 1.5, 'EGG': 1.0, 'WHEAT': 0.5}
_PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
_W = tuple(_WEIGHT[p] for p in _PRODUCTS)

# Fixed 11-label board vocabulary observed across the whole corpus (data/leader_semantics).
LABELS = (' L', 'WH', 'ST', ' .', 'co', 'CA', 'sh', 'TO', 'go', 'ME', 'pa')


def demand_vec(shop_names):
    """Cumulative per-product demand over an ordered list of visible shop names."""
    c = [0] * len(_PRODUCTS)
    for s in shop_names:
        for p, n in _DEMAND.get(s, {}).items():
            c[_PRODUCTS.index(p)] += n
    return tuple(c)


def shop_distance(vec_a, vec_b):
    return sum(w * abs(x - y) for w, x, y in zip(_W, vec_a, vec_b))


def hamming(board_a, board_b):
    return sum(1 for x, y in zip(board_a, board_b) if x != y)


def counts_of(board):
    c = dict.fromkeys(LABELS, 0)
    for lbl in board:
        c[lbl] = c.get(lbl, 0) + 1
    return c


# ---------------------------------------------------------------------------
# Corpus loading (module-level cache: parsed once, reused by every retrieve() call).
# ---------------------------------------------------------------------------
_CORPUS = None       # list of game dicts
_MEDOIDS = None      # 3 canonical day-6 boards (family reference patterns)


def _parse_game(path):
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        d = json.load(fh)
    team_id = os.path.basename(os.path.dirname(path))
    shop_names = [s['shop'] for s in d['shops']]
    boards = [tuple(day['board']) for day in d['days']]
    vecs = [demand_vec(shop_names[:j]) for j in range(0, len(shop_names) + 1)]
    return {
        'team_id': team_id,
        'team': d['meta']['team'],
        'episode': d['meta']['episode'],
        'shops': shop_names,
        'boards': boards,
        'vecs': vecs,
    }


def load_corpus():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = [_parse_game(p) for p in sorted(glob.glob(CORPUS_GLOB))]
    return _CORPUS


# The corpus covers exactly 3 distinct day-6 openings (see docs/... and CLAUDE.md
# 2026-09-24 conventions): DSM/Vadim/Mother-Goose/DECEM share one opening, Boey and
# "M & M & P & Q" each play their own. A k-medoids clustering on raw day-6 Hamming
# distance was tried first and did NOT cleanly separate these (M & M & P & Q has high
# within-family variance - 35 distinct day-6 boards across its 40 games - comparable to
# its between-family distance to the shared opening), so family ground truth here is the
# team-opening-group, which matches the corpus's actual generating process. The per-family
# REFERENCE pattern used by classify_family() (so a live agent can classify its OWN board
# without knowing team identities) is each family's most common ("modal") day-6 board.
_TEAM_FAMILY = {
    'DSM': 0, 'Vadim Vasilenko': 0, 'Unknown Mother-Goose': 0, 'DECEM': 0,
    'M & M & P & Q': 1, 'Boey': 2,
}


def _ensure_families():
    """Lazily label every corpus game with its family id (0/1/2) and compute each family's
    modal day-6 board as the reference pattern for classify_family()."""
    global _MEDOIDS
    corpus = load_corpus()
    if 'family' in corpus[0]:
        return
    for g in corpus:
        g['family'] = _TEAM_FAMILY[g['team']]
    by_family = collections.defaultdict(collections.Counter)
    for g in corpus:
        by_family[g['family']][g['boards'][6]] += 1
    _MEDOIDS = [by_family[f].most_common(1)[0][0] for f in sorted(by_family)]


def classify_family(board_labels, day=6):
    """Nearest of the 3 canonical day-6 opening patterns, by Hamming distance on `board_labels`
    (a 100-entry list/tuple in the same encoding as a corpus board). `day` is accepted for
    interface symmetry but the reference patterns are always the day-6 medoids."""
    _ensure_families()
    dists = [hamming(board_labels, m) for m in _MEDOIDS]
    return min(range(len(dists)), key=lambda i: dists[i])


def _normalize_shops(visible_shops_by_day_or_list):
    """Accepts either a flat ordered list of shop-name strings (visible so far) or a
    {reveal_day: shop_name} mapping; returns the flat ordered list."""
    if isinstance(visible_shops_by_day_or_list, dict):
        return [v for _, v in sorted(visible_shops_by_day_or_list.items())]
    return list(visible_shops_by_day_or_list)


def retrieve(visible_shops_by_day_or_list, board_labels, day, k=1, lam=0.0, family=None,
             exclude_episode=None, exclude_team=None):
    """k nearest leader games by (weighted shop-demand L1 distance) + lam * (board Hamming at
    `day`), optionally restricted to a given `family` id (see classify_family). Returns
    [(team_id, episode, weight), ...] with weight inverse-distance-normalised (sums to 1).

    `exclude_episode` / `exclude_team` are evaluation-only hooks (leave-one-game-out /
    leave-one-team-out); production callers leave them None and search the whole corpus.
    """
    corpus = load_corpus()
    if family is not None:
        _ensure_families()
    shops = _normalize_shops(visible_shops_by_day_or_list)
    qvec = demand_vec(shops)
    day = max(0, min(29, int(day)))
    scored = []
    for g in corpus:
        if exclude_episode is not None and g['episode'] == exclude_episode:
            continue
        if exclude_team is not None and g['team_id'] == exclude_team:
            continue
        if family is not None and g.get('family') != family:
            continue
        j = min(len(shops), len(g['vecs']) - 1)
        d = shop_distance(qvec, g['vecs'][j])
        if lam:
            d += lam * hamming(board_labels, g['boards'][day])
        scored.append((d, g['team_id'], g['episode'], g))
    if not scored:
        return []
    scored.sort(key=lambda t: t[0])
    top = scored[:max(1, k)]
    eps = 1e-6
    inv = [1.0 / (d + eps) for d, _, _, _ in top]
    tot = sum(inv)
    return [(team_id, ep, w / tot) for (d, team_id, ep, _), w in zip(top, inv)]


def retrieve_games(visible_shops_by_day_or_list, board_labels, day, k=1, lam=0.0, family=None,
                    exclude_episode=None, exclude_team=None):
    """Like retrieve(), but returns the full corpus game dicts (for evaluation code that needs
    the neighbours' future boards) instead of (team_id, episode, weight) tuples."""
    corpus = load_corpus()
    if family is not None:
        _ensure_families()
    shops = _normalize_shops(visible_shops_by_day_or_list)
    qvec = demand_vec(shops)
    day = max(0, min(29, int(day)))
    scored = []
    for g in corpus:
        if exclude_episode is not None and g['episode'] == exclude_episode:
            continue
        if exclude_team is not None and g['team_id'] == exclude_team:
            continue
        if family is not None and g.get('family') != family:
            continue
        j = min(len(shops), len(g['vecs']) - 1)
        d = shop_distance(qvec, g['vecs'][j])
        if lam:
            d += lam * hamming(board_labels, g['boards'][day])
        scored.append((d, g))
    if not scored:
        return []
    scored.sort(key=lambda t: t[0])
    top = scored[:max(1, k)]
    eps = 1e-6
    inv = [1.0 / (d + eps) for d, _ in top]
    tot = sum(inv)
    return [(g, w / tot) for (d, g), w in zip(top, inv)]


def predict_board_majority(neighbour_games, target_day):
    """Per-tile majority vote (ties -> first/highest-weight neighbour) among neighbours'
    boards at `target_day` (clipped to 0..29)."""
    target_day = max(0, min(29, target_day))
    if len(neighbour_games) == 1:
        return neighbour_games[0][0]['boards'][target_day]
    boards = [g['boards'][target_day] for g, _ in neighbour_games]
    weights = [w for _, w in neighbour_games]
    out = []
    for tile_i in range(len(boards[0])):
        votes = collections.OrderedDict()
        for b, w in zip(boards, weights):
            votes[b[tile_i]] = votes.get(b[tile_i], 0.0) + w
        out.append(max(votes.items(), key=lambda kv: kv[1])[0])
    return tuple(out)


if __name__ == '__main__':
    from evaluate_leader_plan_retrieval import main
    main()

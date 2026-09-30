"""Direction 1: systematic characterisation of ladder wins vs losses for our live submissions.

Reads the compact ladder-panel games on disk (data/ladder_panel/<submission>/*.json.gz), joins the
opponent's CURRENT leaderboard score, and derives per-game world properties (shop draw, late shops)
and tape-library coverage (does the 584-tape UMG library contain this world's ordered shop prefix /
unordered composition at each reveal day?).

Writes results/fresh/newphase_20260923/ladder_games.json (one row per game) and prints the tables.
"""
import gzip, io, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923'
DAYS = (3, 6, 9, 12, 15, 18, 21, 24)

# products each shop type buys (from docs/environment.md conventions used across the repo)
SHOP_PRODUCTS = {   # engine data/kaggriculture.py SHOPS (8 types, drawn with replacement)
    'BAKERY': ('egg', 'wheat'),
    'PIZZA_SHOP': ('milk', 'tomato', 'wheat'),
    'BRUNCH_SPOT': ('egg', 'wheat', 'strawberry'),
    'YARN_STORE': ('wool',),
    'ICE_CREAM_SHOP': ('strawberry', 'milk', 'wheat'),
    'PET_CAFE': ('carrot',),
    'SMOOTHIE_SHOP': ('strawberry', 'milk'),
    'FARMERS_MARKET': ('wheat', 'carrot', 'tomato', 'strawberry'),
}


def load_gz(p):
    with gzip.open(p, 'rt', encoding='utf-8') as f:
        return json.load(f)


def shop_seq(shops_by_day):
    """shops_by_day is a 31-entry list of unlocked-shop lists; return the ordered 8 reveals."""
    seq, seen = [], 0
    for day in range(31):
        cur = shops_by_day[day]
        while len(cur) > seen:
            seq.append(cur[seen]); seen += 1
        if len(seq) >= 8:
            break
    return seq[:8]


def build_library():
    prof = json.loads((ROOT / 'results/fresh/semantic_tapes/compact_profiles.json').read_text(encoding='utf-8'))
    ordered = {k: set() for k in range(1, 9)}
    unordered = {k: set() for k in range(1, 9)}
    seqs = []
    for t in prof:
        s = shop_seq(t['shops'])
        seqs.append(tuple(s))
        for k in range(1, 9):
            ordered[k].add(tuple(s[:k]))
            unordered[k].add(tuple(sorted(s[:k])))
    return ordered, unordered, seqs


def main():
    lb = json.loads((OUT / 'leaderboard_full.json').read_text(encoding='utf-8'))
    by_team = {r['team_id']: r for r in lb}
    ordered, unordered, tape_seqs = build_library()

    rows = []
    for subdir in sorted((ROOT / 'data/ladder_panel').iterdir()):
        if not subdir.is_dir() or subdir.name == '_raw':
            continue
        for p in sorted(subdir.glob('*.json.gz')):
            g = load_gz(p)
            seat = g['seat']
            ours, theirs = g['rewards'][seat], g['rewards'][1 - seat]
            opp = g.get('opponent') or {}
            lbrow = by_team.get(opp.get('team_id'))
            seq = shop_seq(g['shops'])
            cov_ord = [tuple(seq[:k]) in ordered[k] for k in range(1, 9)]
            cov_un = [tuple(sorted(seq[:k])) in unordered[k] for k in range(1, 9)]
            first_missing = next((3 * k for k in range(1, 9) if not cov_ord[k - 1]), None)
            prod = Counter()
            for s in seq:
                for x in SHOP_PRODUCTS.get(s, ()):
                    prod[x] += 1
            prod_late = Counter()
            for s in seq[4:]:
                for x in SHOP_PRODUCTS.get(s, ()):
                    prod_late[x] += 1
            rows.append(dict(
                submission=subdir.name, episode=g['episode'], created=g['created'], seat=seat,
                ours=ours, theirs=theirs, margin=ours - theirs, win=int(ours > theirs),
                opp_team=opp.get('team'), opp_team_id=opp.get('team_id'), opp_sub=opp.get('submission'),
                opp_rating=(lbrow or {}).get('score'), opp_rank=(lbrow or {}).get('rank'),
                shops=seq, first_missing_ordered=first_missing,
                cov_ordered=cov_ord, cov_unordered=cov_un,
                demand=dict(prod), demand_late=dict(prod_late),
            ))
    OUT.mkdir(parents=True, exist_ok=True)
    with io.open(OUT / 'ladder_games.json', 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False)
    print(f'{len(rows)} games')
    for sub in sorted({r['submission'] for r in rows}):
        rs = [r for r in rows if r['submission'] == sub]
        w = sum(r['win'] for r in rs)
        print(f"  {sub}: {len(rs)} games, {w}-{len(rs)-w}, mean margin {sum(r['margin'] for r in rs)/len(rs):+,.0f}")


if __name__ == '__main__':
    main()

"""Direction 3, offline part: how does tape-library size buy shop-demand coverage?

Reproduces the live router's demand distance (_mgt_distance with future_weight=0) between a world's
revealed shop prefix and each library tape, then measures, for random library subsets of size N, the
best achievable distance at each reveal day on the 856 real ladder worlds we played.

Also reports library redundancy: distinct 8-shop sequences, distinct day-12 prefixes, and how many
tapes are exact duplicates of another tape at each prefix length.

Writes results/fresh/newphase_20260923/coverage_curve_offline.json
"""
import io, json, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/fresh/newphase_20260923'
PRODUCTS = ('STRAWBERRY', 'TOMATO', 'WOOL', 'CARROT', 'MILK', 'EGG', 'WHEAT')
W = np.array([3.0, 2.0, 2.0, 1.5, 1.5, 1.0, 0.5])
CHECKPOINTS = (2, 4, 5, 6, 8)
DEMAND = {'BAKERY': {'EGG': 1, 'WHEAT': 1}, 'PIZZA_SHOP': {'MILK': 1, 'TOMATO': 1, 'WHEAT': 1},
          'BRUNCH_SPOT': {'EGG': 1, 'WHEAT': 1, 'STRAWBERRY': 1}, 'YARN_STORE': {'WOOL': 2},
          'ICE_CREAM_SHOP': {'STRAWBERRY': 1, 'MILK': 1, 'WHEAT': 1}, 'PET_CAFE': {'CARROT': 2},
          'SMOOTHIE_SHOP': {'STRAWBERRY': 1, 'MILK': 1},
          'FARMERS_MARKET': {'WHEAT': 1, 'CARROT': 1, 'TOMATO': 1, 'STRAWBERRY': 1}}


def vecs(seq):
    """cumulative weighted demand vector after each of the 8 reveals (index 0 = nothing revealed)."""
    out = [np.zeros(7)]
    cur = np.zeros(7)
    for s in seq:
        d = DEMAND.get(s, {})
        cur = cur + np.array([d.get(p, 0) for p in PRODUCTS], float)
        out.append(cur.copy())
    while len(out) < 9:
        out.append(out[-1].copy())
    return np.array(out)


def dist(ours_v, tape_v, k):
    d = 0.0
    for j in CHECKPOINTS:
        jj = min(j, k)
        d += float(np.sum(W * np.abs(ours_v[jj] - tape_v[jj])))
        if j >= k:
            break
    return d


def shop_seq(shops_by_day):
    seq, seen = [], 0
    for day in range(min(31, len(shops_by_day))):
        cur = shops_by_day[day]
        while len(cur) > seen:
            seq.append(cur[seen]); seen += 1
        if len(seq) >= 8:
            break
    return seq[:8]


def main():
    prof = json.loads((ROOT / 'results/fresh/semantic_tapes/compact_profiles.json').read_text(encoding='utf-8'))
    tape_seq = [tuple(shop_seq(t['shops'])) for t in prof]
    tape_v = np.array([vecs(s) for s in tape_seq])                       # (584, 9, 7)
    games = json.loads((OUT / 'ladder_games.json').read_text(encoding='utf-8'))
    games = [g for g in games if g['submission'] in ('56368334', '56395605')]
    world_seq = [tuple(g['shops']) for g in games]
    world_v = np.array([vecs(s) for s in world_seq])

    res = {}
    # --- redundancy of the library ---
    red = {}
    for k in range(1, 9):
        pref = Counter(s[:k] for s in tape_seq)
        red[k] = dict(distinct_ordered=len(pref),
                      distinct_unordered=len({tuple(sorted(s[:k])) for s in tape_seq}),
                      distinct_demand_vec=len({tuple(v[k]) for v in tape_v}),
                      largest_cluster=max(pref.values()))
    res['library_redundancy'] = red
    res['library_size'] = len(tape_seq)

    # --- coverage curve: best achievable distance vs library size ---
    rng = np.random.default_rng(7)
    sizes = [1, 2, 4, 8, 16, 32, 64, 128, 256, 400, 584]
    curve = {}
    # full distance matrix per k
    for k in (2, 4, 5, 6, 8):
        D = np.zeros((len(world_v), len(tape_v)))
        for i in range(len(world_v)):
            for j in CHECKPOINTS:
                jj = min(j, k)
                D[i] += (np.abs(world_v[i][jj] - tape_v[:, jj, :]) * W).sum(axis=1)
                if j >= k:
                    break
        rowbest = {}
        for N in sizes:
            best = []
            for _ in range(40):
                idx = rng.choice(len(tape_v), size=min(N, len(tape_v)), replace=False)
                best.append(D[:, idx].min(axis=1))
            best = np.array(best)
            rowbest[N] = dict(mean_best=float(best.mean()), median_best=float(np.median(best)),
                              frac_exact=float((best <= 1e-9).mean()))
        # exhaustive best (all 584)
        rowbest['all'] = dict(mean_best=float(D.min(axis=1).mean()), frac_exact=float((D.min(axis=1) <= 1e-9).mean()))
        curve[f'day{3*k}_k{k}'] = rowbest
    res['coverage_curve'] = curve

    # --- how many distinct demand vectors exist at all (theoretical world space) ---
    from itertools import combinations_with_replacement
    types = sorted(DEMAND)
    allv = set()
    for comb in combinations_with_replacement(types, 8):
        v = np.zeros(7)
        for s in comb:
            d = DEMAND[s]
            v += np.array([d.get(p, 0) for p in PRODUCTS], float)
        allv.add(tuple(v))
    res['world_space'] = dict(shop_types=len(types), multisets=len(list(combinations_with_replacement(types, 8))),
                              distinct_full_demand_vectors=len(allv))
    OUT.mkdir(parents=True, exist_ok=True)
    with io.open(OUT / 'coverage_curve_offline.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1)[:4000])


if __name__ == '__main__':
    main()
